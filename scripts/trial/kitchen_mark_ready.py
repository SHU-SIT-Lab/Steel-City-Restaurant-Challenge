#!/usr/bin/env python3
"""Kitchen operator script — mark order ready on robot Firestore schema (§6 Option A)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "database"))

from repository import RestaurantDatabase  # noqa: E402


def main() -> int:
	parser = argparse.ArgumentParser(description="Mark order ready for a table (0-based id)")
	parser.add_argument("table_id", type=int, help="Firestore table id (0 = table_1)")
	args = parser.parse_args()

	db = RestaurantDatabase()
	db.mark_order_ready(args.table_id)
	print(f"Order marked ready for table_id={args.table_id} (waypoint table_{args.table_id + 1})")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
