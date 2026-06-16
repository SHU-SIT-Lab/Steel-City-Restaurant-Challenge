#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import RestaurantDatabase, get_int, shared_state


class CheckCustomerNumberBehavior(DeliberativeBehavior):
	"""Minimal behavior template for updating new customer count."""

	def __init__(self) -> None:
		super().__init__(name="check_customer_number")
		self.wait_time = 5.0
		self.order = 4
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		# TODO 1: Navigation
		# Move robot to entrance.

		# TODO 2: LLM
		# Greet and ask for number of customers.

		# TODO 3: Database
		# Update collaborator database with the number of new customers waiting.
		state = shared_state(ctx)
		count = state.get("customers_waiting", state.get("customer_number"))
		if count is None:
			count = 1 if self.db.customers_detected_at_entrance() else 0

		customer_count = get_int(count)
		self.db.set_customers_waiting(customer_count)
		self.db.set_customers_detected_at_entrance(customer_count > 0)

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
