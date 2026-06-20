#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import ENTRANCE_LOCATION, RestaurantDatabase, get_int, set_navigation_target, shared_state


class CheckCustomerNumberBehavior(DeliberativeBehavior):
	"""Minimal behavior template for updating new customer count."""

	def __init__(self) -> None:
		super().__init__(name="check_customer_number")
		self.wait_time = 5.0
		self.order = 4
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		set_navigation_target(ctx, ENTRANCE_LOCATION)
		state = shared_state(ctx)

		if self.object_detection is not None:
			self.object_detection.current_table_id = None

		count = state.get("customers_waiting", state.get("customer_number"))
		if count is None and self.object_detection is not None:
			count = getattr(self.object_detection, "customers_waiting", None)
		if count is None:
			count = 1 if self.db.customers_detected_at_entrance() else 0

		customer_count = get_int(count)
		state["customers_waiting"] = customer_count
		state["customer_present"] = customer_count > 0
		try:
			self.db.set_customers_waiting(customer_count)
			self.db.set_customers_detected_at_entrance(customer_count > 0)
		except Exception as exc:
			print(f"[CHECK_CUSTOMER_NUMBER] Firestore write failed ({exc}).")

	def compute_priority(self) -> float:
		# TODO 4: Database
		# Check if customers is detected at front door, 0 if no and 1 if yes
		self.customers_detected = 1 if self.db.customers_detected_at_entrance() else 0

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order * self.customers_detected

		return self.priority
