#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior


class CheckCustomerBehavior(DeliberativeBehavior):
	"""Minimal example behavior with TODO markers for implementation."""

	def __init__(self) -> None:
		super().__init__(name="check_customer")
		self.wait_time = 5.0
        self.order = 1

	def plan(self, ctx: Any) -> None:
		# TODO 1: Navigation
		# Move robot to entrance.

		# TODO 2: Vision
		# Check camera for new customers.

		# TODO 3: Database
		# Use collaborator database integration to update if a new customer is detected.
		pass

	def compute_priority(self) -> float:
		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
        else:
            self.priority = 1.0 * self.order

		return self.priority
