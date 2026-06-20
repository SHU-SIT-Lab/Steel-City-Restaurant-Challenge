"""Quick check that Firestore credentials and collections work."""

from __future__ import annotations

from config import credentials_path
from repository import RestaurantDatabase


def main() -> None:
    print(f"Using credentials: {credentials_path()}")
    db = RestaurantDatabase()

    table_id = 2
    db.assign_table(table_id)
    print(f"Needs order: {db.find_table_needing_order()}")

    db.save_order(table_id, items=["burger", "coke"], notes="no pickles")
    print(f"After save - needs order: {db.find_table_needing_order()}")
    print(f"Pending kitchen: {db.find_table_with_pending_order()}")
    print(f"Ready to collect: {db.find_table_with_ready_order()}")

    db.mark_order_ready(table_id)
    print(f"After mark ready - pending: {db.find_table_with_pending_order()}")
    print(f"Ready to collect: {db.find_table_with_ready_order()}")

    db.mark_order_delivered(table_id)
    print(f"After delivery: {db.get_table(table_id)}")

    db.clear_table(table_id)
    tables = db.list_tables()
    state = db.get_restaurant_state()
    print("Connection OK.")
    print(f"Restaurant state: {state}")
    print(f"Tables loaded: {len(tables)}")


if __name__ == "__main__":
    main()
