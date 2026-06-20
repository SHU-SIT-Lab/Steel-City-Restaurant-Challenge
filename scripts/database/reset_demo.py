"""Reset Firestore to a clean demo state (fixes common stale-data issues)."""

from __future__ import annotations

import argparse

from repository import RestaurantDatabase


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset Firestore tables and optional entrance queue for testing."
    )
    parser.add_argument(
        "--waiting",
        type=int,
        default=1,
        help="customers_waiting after reset (default: 1, use 0 for fully idle entrance)",
    )
    parser.add_argument(
        "--no-entrance",
        action="store_true",
        help="Only clear tables; leave restaurant_state at customers_waiting=0",
    )
    args = parser.parse_args()

    db = RestaurantDatabase()
    db.reset_all_tables()
    if args.no_entrance:
        db.reset_restaurant_state()
    else:
        db.prepare_demo_entrance(customers_waiting=args.waiting)

    print("Firestore reset complete.")
    print(f"Tables: {[table.table_id for table in db.list_tables()]}")
    print(f"Restaurant state: {db.get_restaurant_state()}")


if __name__ == "__main__":
    main()
