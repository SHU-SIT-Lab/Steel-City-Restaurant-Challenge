#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior


class TakeOrderBehavior(DeliberativeBehavior):
	"""Minimal behavior template for updating new customer count."""

	def __init__(self) -> None:
		super().__init__(name="take_order")
		self.wait_time = 5.0
		self.order = 5

	def plan(self, ctx: Any) -> None:
		# TODO 1: Database
		# Get table id that is occupied with customer that havent order.

		# TODO 2: Navigation
		# Move to the table.

		# TODO 3: LLM
		# Greet and ask if they are ready to order, if no pass else you continue.

		# TODO 4: LLM
		# Ask and get list of customer order. Interact and get an array of the order.

		# TODO 5: Database
		# Update database with order and set the table to be occupied and that customer have ordered.
		pass

	def compute_priority(self) -> float:
		# TODO 6: Database
		# Check if there is an occupied table with customer that havent order, 0 if no and 1 if yes
		self.customers_detected = 0

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
        else:
            self.priority = 1.0 * self.order * self.customers_detected

		return self.priority
