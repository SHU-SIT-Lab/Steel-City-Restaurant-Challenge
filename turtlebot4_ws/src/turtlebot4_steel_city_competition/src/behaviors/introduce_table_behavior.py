#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior


class IntroduceTableBehavior(DeliberativeBehavior):
	"""Minimal behavior template for updating new customer count."""

	def __init__(self) -> None:
		super().__init__(name="introduce_table")
		self.wait_time = 5.0
		self.order = 3

	def plan(self, ctx: Any) -> None:
		# TODO 1: Navigation
		# Move robot to entrance.

		# TODO 2: LLM
		# Ask customer to follow you
		
		# TODO 3: Database
		# Check which table is assigned to the customer and update database with table assignment. Set table to occupied.
		
		# TODO 4: Navigation
		# Move robot to assigned table.

		# TODO 5: LLM
		# Tell customer to sit and how to order
		pass

	def compute_priority(self) -> float:
		# TODO 6: Database
		# Check if customer_number at front door is not zero
		# Check if there is empty table
		# If customer number is at front door is not zero and there is empty table, then set customers_detected to 1, else 0
		self.guide_customer = 0

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
        else:
            self.priority = 1.0 * self.order * self.guide_customer

		return self.priority
