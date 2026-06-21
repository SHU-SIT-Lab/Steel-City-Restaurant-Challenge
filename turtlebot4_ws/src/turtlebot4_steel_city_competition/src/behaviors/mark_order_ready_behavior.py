#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any, Optional

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import RestaurantDatabase, shared_state
from behaviors.speech_utils import bind_context_interfaces
from models import TableStatus


class MarkOrderReadyBehavior(DeliberativeBehavior):
	"""Mark placed orders as ready in Firestore (simulated kitchen step)."""

	def __init__(self) -> None:
		super().__init__(name="mark_order_ready")
		self.wait_time = 5.0
		self.order = 5.5
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		bind_context_interfaces(self, ctx)
		try:
			table_id = self._get_table_with_pending_order(ctx)
			if table_id is None:
				return

			self._mark_order_ready_in_db(table_id)
			shared_state(ctx)["order_ready_table_id"] = table_id
		except Exception as exc:
			print(f"[MARK_ORDER_READY] plan failed ({exc}); abandoning this attempt.")

	def compute_priority(self) -> float:
		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			has_pending = self._get_table_with_pending_order(None) is not None
			self.priority = 1.0 * self.order if has_pending else 0.0
		return self.sequence_gate(self.priority)

	def _get_table_with_pending_order(self, ctx: Any) -> Optional[int]:
		"""Return a table with a placed order that is not ready yet."""
		state = shared_state(ctx) if ctx is not None else {}
		override = state.get("pending_order_table_id")
		if override is not None:
			table_id = int(override)
			table = self.db.get_table(table_id)
			if (
				table.status == TableStatus.OCCUPIED.value
				and table.has_ordered
				and not table.order_ready
			):
				return table_id

		try:
			table_id = self.db.find_table_with_pending_order()
			if table_id is None:
				print("[MARK_ORDER_READY] DB: no pending orders to mark ready.")
			else:
				print(f"[MARK_ORDER_READY] DB: table {table_id} order pending kitchen ready.")
			return table_id
		except Exception as exc:
			print(f"[MARK_ORDER_READY] DB read failed ({exc}).")
			return None

	def _mark_order_ready_in_db(self, table_id: int) -> bool:
		"""Write order_ready=true for the given table."""
		try:
			table = self.db.get_table(table_id)
			if table.order_ready:
				print(f"[MARK_ORDER_READY] DB unchanged: table {table_id} already ready.")
				return True

			self.db.mark_order_ready(table_id)
			print(f"[MARK_ORDER_READY] DB updated: table {table_id} order_ready=true")
			return True
		except Exception as exc:
			print(f"[MARK_ORDER_READY] DB update failed for table {table_id} ({exc}).")
			return False
