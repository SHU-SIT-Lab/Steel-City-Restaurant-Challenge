#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import (
	ENTRANCE_LOCATION,
	RestaurantDatabase,
	set_navigation_target,
	shared_state,
	table_id_to_location,
)


class IntroduceTableBehavior(DeliberativeBehavior):
	"""Seat waiting customers by assigning a free table in Firestore."""

	def __init__(self) -> None:
		super().__init__(name="introduce_table")
		self.wait_time = 5.0
		self.order = 3
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		table_id = self.db.find_empty_table()
		if table_id is None:
			return

		table_location = table_id_to_location(table_id)
		set_navigation_target(
			ctx,
			ENTRANCE_LOCATION,
			table_id=table_id,
			next_location=table_location,
		)

		self.db.assign_table(table_id)
		self.db.decrement_customers_waiting()
		shared_state(ctx)["assigned_table_id"] = table_id

		# TODO: Navigation team — entrance first, then next_target_location (table).
		# TODO: LLM — guide customer and explain how to order.

	def compute_priority(self) -> float:
		self.guide_customer = 1 if self.db.should_guide_customer_to_table() else 0

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order * self.guide_customer

		return self.priority
