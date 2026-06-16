#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import RestaurantDatabase, shared_state, table_empty_status


class CheckEmptyTableBehavior(DeliberativeBehavior):
	"""Minimal behavior template for updating new customer count."""

	def __init__(self) -> None:
		super().__init__(name="check_empty_table")
		self.wait_time = 5.0
		self.order = 1
		self.number_of_tables = 5
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		for table_id in range(self.number_of_tables):
			# TODO 1: Navigation
			# Move to table_id.

			# TODO 2: Vision
			# Check if table_id is empty or occupied.

			# TODO 3: Database
			# Update database on table status (empty or occupied).
			state = shared_state(ctx)
			table_empty = state.get("table_empty", self.object_detection.table_empty)
			if isinstance(table_empty, dict):
				table_empty = table_empty.get(table_id)
			if table_empty is None:
				continue

			self.db.update_table_status(table_id, table_empty_status(table_empty))

	def compute_priority(self) -> float:

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order

		return self.priority
