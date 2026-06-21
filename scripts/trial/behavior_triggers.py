#!/usr/bin/env python3
"""§8 dry-run helpers — set Firestore state to trigger each behavior."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "database"))

from repository import RestaurantDatabase  # noqa: E402


def trigger_check_customer_number(db: RestaurantDatabase) -> None:
	db.set_customers_detected_at_entrance(True)
	db.set_customers_waiting(0)
	print("Trigger check_customer_number: detected=true, waiting=0")


def trigger_introduce_table(db: RestaurantDatabase, count: int = 1) -> None:
	db.set_customers_detected_at_entrance(True)
	db.set_customers_waiting(count)
	print(f"Trigger introduce_table: waiting={count}, need empty table in DB")


def trigger_take_order(db: RestaurantDatabase, table_id: int = 0) -> None:
	db.assign_table(table_id)
	print(f"Trigger take_order: table {table_id} assigned, no order yet")


def trigger_collect_order(db: RestaurantDatabase, table_id: int = 0) -> None:
	db.assign_table(table_id)
	db.save_order(table_id, ["menu_one"], "")
	db.mark_order_ready(table_id)
	print(f"Trigger collect_order: table {table_id} order_ready=true")


def reset_demo(db: RestaurantDatabase) -> None:
	db.reset_for_demo(customers_waiting=0)
	print("Database reset for next demo run")


def main() -> int:
	parser = argparse.ArgumentParser(description="Set DB state for behavior dry runs")
	parser.add_argument(
		"behavior",
		choices=[
			"check_customer_number",
			"introduce_table",
			"take_order",
			"collect_order",
			"reset",
		],
	)
	parser.add_argument("--table-id", type=int, default=0)
	parser.add_argument("--count", type=int, default=1)
	args = parser.parse_args()

	db = RestaurantDatabase()
	actions = {
		"check_customer_number": lambda: trigger_check_customer_number(db),
		"introduce_table": lambda: trigger_introduce_table(db, args.count),
		"take_order": lambda: trigger_take_order(db, args.table_id),
		"collect_order": lambda: trigger_collect_order(db, args.table_id),
		"reset": lambda: reset_demo(db),
	}
	actions[args.behavior]()
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
