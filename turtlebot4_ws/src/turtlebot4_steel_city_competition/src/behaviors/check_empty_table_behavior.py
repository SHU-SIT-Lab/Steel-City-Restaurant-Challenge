#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import (
	RestaurantDatabase,
	set_navigation_target,
	shared_state,
	table_empty_status,
	table_id_to_location,
)


class CheckEmptyTableBehavior(DeliberativeBehavior):
	"""Update table occupancy in Firestore after vision checks at each table."""

	def __init__(self) -> None:
		super().__init__(name="check_empty_table")
		self.wait_time = 5.0
		self.order = 1
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		state = shared_state(ctx)
		table_id = state.get("current_table_id")
		if table_id is None:
			return

		table_id = int(table_id)
		table_location = table_id_to_location(table_id)

		if state.get("next_target_location") is not None:
			return

		if state.get("target_location") != table_location:
			set_navigation_target(ctx, table_location, table_id=table_id)
			return

		if self.object_detection is not None:
			self.object_detection.current_table_id = table_id

		table_empty = state.get("table_empty")
		if table_empty is None and self.object_detection is not None:
			table_empty = getattr(self.object_detection, "table_empty", None)

		if isinstance(table_empty, dict):
			table_empty = table_empty.get(table_id)
		if table_empty is None:
			return

		state["table_empty"] = table_empty
		try:
			self.db.update_table_status(table_id, table_empty_status(table_empty))
		except Exception as exc:
			print(f"[CHECK_EMPTY_TABLE] Firestore write failed ({exc}).")

	def compute_priority(self) -> float:
		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order

		return self.priority
