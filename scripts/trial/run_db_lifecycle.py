#!/usr/bin/env python3
"""§6 acceptance test — full order lifecycle on robot Firestore schema."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "database"))

from repository import RestaurantDatabase  # noqa: E402


def main() -> int:
	db = RestaurantDatabase()
	print("Tables:", [t.table_id for t in db.list_tables()])

	db.assign_table(0)
	assert db.find_table_needing_order() == 0

	db.save_order(0, ["coffee"], "no dairy")
	assert db.find_table_with_ready_order() is None

	db.mark_order_ready(0)
	assert db.find_table_with_ready_order() == 0

	db.mark_order_delivered(0)
	print("Full order lifecycle OK")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
