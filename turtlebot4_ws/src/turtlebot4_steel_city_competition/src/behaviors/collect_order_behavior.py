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


class CollectOrderBehavior(DeliberativeBehavior):
	"""Collect a ready order from the barista and deliver it to the table."""

	def __init__(self) -> None:
		super().__init__(name="collect_order")
		self.wait_time = 5.0
		self.order = 6
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		table_id = self.db.find_table_with_ready_order()
		if table_id is None:
			return

		set_navigation_target(
			ctx,
			BARISTA_LOCATION,
			table_id=table_id,
			next_location=table_id_to_location(table_id),
		)

		# TODO: Navigation team — navigate to target_location, then next_target_location.
		# TODO: LLM — confirm with barista and customer.

		state = shared_state(ctx)
		delivered = state.get("order_delivered", state.get("customer_collected_order"))
		if get_bool(delivered, default=False):
			self.db.mark_order_delivered(table_id)
			state.pop("next_target_location", None)

	def compute_priority(self) -> float:
		self.order_ready = 1 if self.db.has_ready_order() else 0

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order * self.order_ready

		return self.priority
