#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import ENTRANCE_LOCATION, RestaurantDatabase, get_bool, set_navigation_target, shared_state


class CheckCustomerBehavior(DeliberativeBehavior):
	"""Minimal example behavior with TODO markers for implementation."""

	def __init__(self) -> None:
		super().__init__(name="check_customer")
		self.wait_time = 5.0
		self.order = 1
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		set_navigation_target(ctx, ENTRANCE_LOCATION)
		state = shared_state(ctx)

		if self.object_detection is not None:
			self.object_detection.current_table_id = None

		detected = state.get("customer_present")
		if detected is None and self.object_detection is not None:
			detected = getattr(self.object_detection, "customer_present", False)
		if detected is None:
			detected = False

		state["customer_present"] = detected
		try:
			self.db.set_customers_detected_at_entrance(get_bool(detected, default=False))
		except Exception as exc:
			print(f"[CHECK_CUSTOMER] Firestore write failed ({exc}).")

	def compute_priority(self) -> float:
		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order

		return self.priority
