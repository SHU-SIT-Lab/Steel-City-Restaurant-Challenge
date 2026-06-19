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
		# TODO 1: Navigation
		# Move robot to entrance.

		# TODO 2: Vision
		# Check camera for new customers.

		# TODO 3: Database
		# Use collaborator database integration to update if a new customer is detected.
		set_navigation_target(ctx, ENTRANCE_LOCATION)
		state = shared_state(ctx)
		detected = state.get("customer_present", self.object_detection.customer_present)
		self.db.set_customers_detected_at_entrance(get_bool(detected))

	def compute_priority(self) -> float:
		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order

		return self.priority
