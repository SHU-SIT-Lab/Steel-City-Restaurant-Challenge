#!/usr/bin/env python3
from __future__ import annotations

import time
from typing import Any, Optional

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import (
	RestaurantDatabase,
	set_navigation_target,
	shared_state,
	table_id_to_location,
)
from behaviors.speech_utils import ask, bind_context_interfaces, say

try:
	from llm.order_taker import OrderTaker
except Exception as exc:
	print(f"[TAKE_ORDER] OrderTaker unavailable ({exc}). Conversation disabled.")
	OrderTaker = None


class TakeOrderBehavior(DeliberativeBehavior):
	def __init__(self) -> None:
		super().__init__(name="take_order")
		self.wait_time = 5.0
		self.order = 5
		self.max_dialogue_turns = 8
		self.ask_timeout = 8.0
		self.max_no_reply = 3
		self._order_taker: Optional[OrderTaker] = None
		self.db = RestaurantDatabase()
		self.navigation: Any = None

	def plan(self, ctx: Any) -> None:
		bind_context_interfaces(self, ctx)

		try:
			table_id = self._get_table_awaiting_order()
			if table_id is None:
				print("[TAKE_ORDER] no table awaiting order.")
				return

			location_id = table_id_to_location(table_id)
			set_navigation_target(ctx, location_id, table_id=table_id)
			state = shared_state(ctx)
			state["current_table_id"] = table_id

			result = self._take_order()
			if result is None:
				say(self, "No problem, I'll come back in a little while.", tag="TAKE_ORDER")
				return

			saved = self._save_order_to_db(
				table_id=table_id,
				items=result.get("items", []),
				notes=result.get("notes", ""),
			)

			if saved:
				say(self, "Thank you. I have sent your order to the kitchen.", tag="TAKE_ORDER")
			else:
				say(self, "I have taken your order, but I could not save it just now.", tag="TAKE_ORDER")

		except Exception as exc:
			print(f"[TAKE_ORDER] step failed ({exc}); abandoning this attempt.")

	def compute_priority(self) -> float:
		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
			return self.priority

		table_id = self._get_table_awaiting_order()
		self.priority = float(self.order) if table_id is not None else 0.0
		return self.priority

	def _take_order(self) -> Optional[dict]:
		taker = self._get_order_taker()
		if taker is None:
			return None

		taker.reset()
		say(
			self,
			"Hello! I'm ServerBot. We have Menu One through Menu Five. Which menu would you like?",
			tag="TAKE_ORDER",
		)

		no_reply = 0
		for _ in range(self.max_dialogue_turns):
			answer = ask(self, tag="TAKE_ORDER", timeout=self.ask_timeout)
			if not answer:
				no_reply += 1
				if no_reply >= self.max_no_reply:
					print("[TAKE_ORDER] no reply after several tries; giving up for now.")
					return None
				say(self, "Sorry, I didn't catch that. Could you repeat, please?", tag="TAKE_ORDER")
				continue

			no_reply = 0
			reply, recorded_order = taker.chat(answer)
			say(self, reply, tag="TAKE_ORDER")
			if recorded_order is not None:
				return recorded_order

		return None

	def _get_order_taker(self) -> Optional[OrderTaker]:
		if self._order_taker is None and OrderTaker is not None:
			try:
				self._order_taker = OrderTaker()
			except Exception as exc:
				print(f"[TAKE_ORDER] LLM unavailable ({exc}).")
				return None
		return self._order_taker

	def _get_table_awaiting_order(self) -> Optional[int]:
		try:
			table_id = self.db.find_table_needing_order()
			if table_id is None:
				print("[TAKE_ORDER] DB: no table needs an order right now.")
			else:
				print(f"[TAKE_ORDER] DB: table {table_id} needs an order.")
			return table_id
		except Exception as exc:
			print(f"[TAKE_ORDER] DB read failed ({exc}).")
			return None

	def _save_order_to_db(self, table_id: int, items: list, notes: str) -> bool:
		try:
			clean_items = [str(item).strip() for item in items if str(item).strip()]
			clean_notes = str(notes or "").strip()
			if not clean_items:
				print(f"[TAKE_ORDER] DB: empty order for table {table_id}; not saving.")
				return False

			menu_ids = self.db.normalize_order_menus(clean_items)
			self.db.save_order(table_id, items=menu_ids, notes=clean_notes)
			print(
				f"[TAKE_ORDER] DB saved for table {table_id}: "
				f"menus={menu_ids} notes={clean_notes!r}"
			)
			return True
		except ValueError as exc:
			print(f"[TAKE_ORDER] DB: invalid menu order for table {table_id}: {exc}")
			say(
				self,
				"Sorry, I can only take orders for Menu One through Menu Five. "
				"Which menu would you like?",
				tag="TAKE_ORDER",
			)
			return False
		except Exception as exc:
			print(f"[TAKE_ORDER] DB save failed for table {table_id} ({exc}).")
			return False
