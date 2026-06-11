#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior


class CollectOrderBehavior(DeliberativeBehavior):
	"""Minimal behavior template for updating new customer count."""

	def __init__(self) -> None:
		super().__init__(name="collect_order")
		self.wait_time = 5.0
		self.order = 6
		self.number_of_tables = 5

	def plan(self, ctx: Any) -> None:
		for table_id in range(self.number_of_tables):
			# TODO 1: Navigation
			# Move to barista.

			# TODO 2: LLM
			# Ask barista if order for table_id is ready to deliver every 1 minute

			# TODO 3: Navigation
			# Move to the table.

			# TODO 4: LLM
			# Ask customer if they are done collecting every 1 minute

			# TODO 5: Database
			# Update database on table status (order delivered)
		pass

	def compute_priority(self) -> float:
		# TODO 6: Database
		# Check if table is occupied, has ordered and if the order is ready, 0 if no and 1 if yes
		self.order_ready = 0

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
        else:
            self.priority = 1.0 * self.order * self.order_ready

		return self.priority
