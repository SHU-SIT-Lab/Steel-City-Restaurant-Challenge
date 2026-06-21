#!/usr/bin/env python3

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Optional

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import (
	BARISTA_LOCATION,
	REPO_ROOT,
	RestaurantDatabase,
	get_bool,
	set_navigation_target,
	shared_state,
	table_id_to_location,
)
from behaviors.speech_utils import ask, bind_context_interfaces, say

VISION_DIR = REPO_ROOT / "scripts" / "vision"
if str(VISION_DIR) not in sys.path:
	sys.path.insert(0, str(VISION_DIR))

try:
	from order_verification import OrderVerificationResult, format_verification_speech
except ImportError:
	format_verification_speech = None  # type: ignore[assignment]
	OrderVerificationResult = None  # type: ignore[assignment,misc]


class CollectOrderBehavior(DeliberativeBehavior):
	"""Collect a ready order from the barista and deliver it to the table."""

	def __init__(self) -> None:
		super().__init__(name="collect_order")
		self.wait_time = 5.0
		self.order = 6
		self.ask_timeout = 8.0
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		bind_context_interfaces(self, ctx)
		table_id = self.db.find_table_with_ready_order()
		if table_id is None:
			return

		table_location = table_id_to_location(table_id)
		state = shared_state(ctx)
		current_target = state.get("target_location")
		delivery_table_id = state.get("delivery_table_id")
		verified_table_id = state.get("verified_table_id")

		if current_target != BARISTA_LOCATION:
			set_navigation_target(
				ctx,
				BARISTA_LOCATION,
				table_id=table_id,
				next_location=table_location,
			)
			say(
				self,
				f"I am here to collect the order for table {table_id + 1}.",
				tag="COLLECT_ORDER",
			)
			barista_reply = ask(
				self,
				tag="COLLECT_ORDER",
				timeout=self.ask_timeout,
				prompt="Is the order ready for me to deliver?",
			)
			if barista_reply:
				print(f"[COLLECT_ORDER] barista reply: {barista_reply!r}")
			state.pop("verified_table_id", None)
			return

		if verified_table_id != table_id:
			verification = self._verify_order_at_barista(ctx, table_id)
			if verification is None:
				say(
					self,
					"I could not verify the order with my camera. "
					"Please make sure all items are visible, then tell me when it is ready.",
					tag="COLLECT_ORDER",
				)
				return

			say(
				self,
				format_verification_speech(verification)
				if format_verification_speech is not None
				else (
					"The order looks correct. I will deliver it to the table now."
					if verification.is_correct
					else "The order is not correct. Please fix it before I deliver."
				),
				tag="COLLECT_ORDER",
			)
			if not verification.is_correct:
				state.pop("verified_table_id", None)
				return

			state["verified_table_id"] = table_id
			set_navigation_target(ctx, table_location, table_id=table_id)
			return

		if current_target != table_location:
			set_navigation_target(ctx, table_location, table_id=table_id)
			return

		if delivery_table_id is not None and int(delivery_table_id) != table_id:
			return

		say(
			self,
			f"Hello, I have your order from the kitchen. Did you receive everything?",
			tag="COLLECT_ORDER",
		)
		customer_reply = ask(self, tag="COLLECT_ORDER", timeout=self.ask_timeout)
		delivered = customer_reply is not None or get_bool(state.get("order_delivered"), default=True)

		if get_bool(delivered, default=True):
			try:
				self.db.mark_order_delivered(table_id)
				state["order_delivered"] = True
				state.pop("next_target_location", None)
				state.pop("delivery_table_id", None)
				state.pop("verified_table_id", None)
				say(self, "Thank you. Enjoy your meal!", tag="COLLECT_ORDER")
			except Exception as exc:
				print(f"[COLLECT_ORDER] Firestore write failed ({exc}).")

	def _verify_order_at_barista(
		self,
		ctx: Any,
		table_id: int,
	) -> Optional[Any]:
		"""Use vision to check the tray against the customer's order."""
		import os

		if os.environ.get("RESTAURANT_SKIP_ORDER_VISION", "").strip().lower() in {
			"1",
			"true",
			"yes",
		}:
			print("[COLLECT_ORDER] RESTAURANT_SKIP_ORDER_VISION set; skipping camera check.")
			if OrderVerificationResult is None:
				return None
			return OrderVerificationResult(is_correct=True)

		table = self.db.get_table(table_id)
		order_items = [str(item).strip() for item in table.order_items if str(item).strip()]
		if not order_items:
			print(f"[COLLECT_ORDER] table {table_id} has no order_items; skipping vision check.")
			if OrderVerificationResult is None:
				return None
			return OrderVerificationResult(is_correct=True)

		menu_lookup = {menu.id: menu for menu in self.db.list_menus()}

		vision = self.object_detection
		if vision is None or not hasattr(vision, "verify_order_items"):
			print("[COLLECT_ORDER] object detection unavailable; cannot verify order.")
			return None

		result = vision.verify_order_items(order_items, menu_lookup=menu_lookup)
		if result is None:
			return None

		print(
			f"[COLLECT_ORDER] vision check table={table_id} "
			f"items={order_items} correct={result.is_correct}"
		)
		return result

	def compute_priority(self) -> float:
		self.order_ready = 1 if self.db.has_ready_order() else 0

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order * self.order_ready

		return self.sequence_gate(self.priority)
