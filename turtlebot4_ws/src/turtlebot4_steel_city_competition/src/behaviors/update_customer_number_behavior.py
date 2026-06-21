#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import ENTRANCE_LOCATION, RestaurantDatabase, set_navigation_target, shared_state
from behaviors.speech_utils import ask, bind_context_interfaces, parse_party_size, say


class CheckCustomerNumberBehavior(DeliberativeBehavior):
	"""Ask how many customers are waiting and update Firestore."""

	def __init__(self) -> None:
		super().__init__(name="check_customer_number")
		self.wait_time = 5.0
		self.order = 4
		self.ask_timeout = 8.0
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		bind_context_interfaces(self, ctx)
		set_navigation_target(ctx, ENTRANCE_LOCATION)
		state = shared_state(ctx)

		if not self.db.customers_detected_at_entrance():
			return

		say(
			self,
			"Hello! Welcome to Steel City Restaurant. How many people are in your party?",
			tag="CHECK_CUSTOMER_NUMBER",
		)
		answer = ask(self, tag="CHECK_CUSTOMER_NUMBER", timeout=self.ask_timeout)
		customer_count = parse_party_size(answer, default=1)

		state["customers_waiting"] = customer_count
		state["customer_present"] = customer_count > 0
		try:
			self.db.set_customers_waiting(customer_count)
			self.db.set_customers_detected_at_entrance(customer_count > 0)
			print(f"[CHECK_CUSTOMER_NUMBER] DB: customers_waiting={customer_count}")
		except Exception as exc:
			print(f"[CHECK_CUSTOMER_NUMBER] Firestore write failed ({exc}).")

	def compute_priority(self) -> float:
		try:
			state = self.db.get_restaurant_state()
			customers_detected = state.customers_detected_at_entrance
			already_counted = state.customers_waiting > 0
		except Exception:
			customers_detected = self.db.customers_detected_at_entrance()
			already_counted = False

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time or not customers_detected or already_counted:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order

		return self.sequence_gate(self.priority)
