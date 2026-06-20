#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import (
	BARISTA_LOCATION,
	RestaurantDatabase,
	get_bool,
	set_navigation_target,
	shared_state,
	table_id_to_location,
)
from behaviors.speech_utils import ask, bind_context_interfaces, say


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
				say(self, "Thank you. Enjoy your meal!", tag="COLLECT_ORDER")
			except Exception as exc:
				print(f"[COLLECT_ORDER] Firestore write failed ({exc}).")

	def compute_priority(self) -> float:
		self.order_ready = 1 if self.db.has_ready_order() else 0

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order * self.order_ready

		return self.priority
