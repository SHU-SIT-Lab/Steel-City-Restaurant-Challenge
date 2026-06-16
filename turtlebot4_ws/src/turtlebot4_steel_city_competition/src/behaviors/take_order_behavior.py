#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import Any

from behaviors.behaviors import DeliberativeBehavior
from behaviors.database_bridge import RestaurantDatabase, shared_state


class TakeOrderBehavior(DeliberativeBehavior):
	"""Minimal behavior template for updating new customer count."""

	def __init__(self) -> None:
		super().__init__(name="take_order")
		self.wait_time = 5.0
		self.order = 5
		self.db = RestaurantDatabase()

	def plan(self, ctx: Any) -> None:
		# TODO 1: Database
		# Get table id that is occupied with customer that havent order.
		table_id = self.db.find_table_needing_order()
		if table_id is None:
			return
		shared_state(ctx)["current_table_id"] = table_id

		# TODO 2: Navigation
		# Move to the table.

		# TODO 3: LLM
		# Greet and ask if they are ready to order, if no pass else you continue.

		# TODO 4: LLM
		# Ask and get list of customer order. Interact and get an array of the order.

		# TODO 5: Database
		# Update database with order and set the table to be occupied and that customer have ordered.
		state = shared_state(ctx)
		items = state.get("order_items", state.get("last_order_items", []))
		notes = state.get("order_notes", state.get("last_order_notes", ""))
		if isinstance(items, str):
			items = [item.strip() for item in items.split(",") if item.strip()]
		if not items:
			return
		self.db.save_order(table_id, items=list(items), notes=str(notes))

	def compute_priority(self) -> float:
		# TODO 6: Database
		# Check if there is an occupied table with customer that havent order, 0 if no and 1 if yes
		self.customers_detected = 1 if self.db.has_table_needing_order() else 0

		elapsed_time = time.monotonic() - self.last_run_time
		if elapsed_time < self.wait_time:
			self.priority = 0.0
		else:
			self.priority = 1.0 * self.order * self.customers_detected

		return self.priority
