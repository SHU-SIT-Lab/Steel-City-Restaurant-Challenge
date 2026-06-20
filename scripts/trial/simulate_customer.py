#!/usr/bin/env python3
"""§7 fallback — simulate customer at entrance (Tier 2 manual vision)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "database"))

from repository import RestaurantDatabase  # noqa: E402


def main() -> int:
	parser = argparse.ArgumentParser(description="Simulate customers at entrance")
	parser.add_argument("--count", type=int, default=1, help="customers_waiting")
	args = parser.parse_args()

	db = RestaurantDatabase()
	db.set_customers_detected_at_entrance(True)
	db.set_customers_waiting(max(1, args.count))
	print(f"Simulated customer at entrance: customers_waiting={args.count}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
