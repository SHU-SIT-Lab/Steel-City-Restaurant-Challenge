"""Initialize Firestore collections with default documents."""

from __future__ import annotations

import argparse

from repository import RestaurantDatabase


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or refresh Firestore documents.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear all tables to empty before seeding (fixes stale occupied/order flags)",
    )
    args = parser.parse_args()

    db = RestaurantDatabase()
    if args.reset:
        db.reset_all_tables()
    db.seed_tables()
    db.seed_restaurant_state()
    print("Firestore seed complete.")
    print(f"Tables: {[table.table_id for table in db.list_tables()]}")
    if args.reset:
        print("Tip: run `python reset_demo.py` to also set customers_waiting=1 for seating tests.")


if __name__ == "__main__":
    main()
