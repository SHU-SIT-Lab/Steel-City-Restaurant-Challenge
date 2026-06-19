"""Quick check that Firestore credentials and collections work."""

from __future__ import annotations

from config import credentials_path
from repository import RestaurantDatabase


def main() -> None:
    print(f"Using credentials: {credentials_path()}")
    db = RestaurantDatabase()
    db.assign_table(2)   # occupied, has_ordered=False
    print(db.find_table_needing_order()) # 2
    db.save_order(2, items=["burger", "coke"], notes="no pickles")
    print(db.get_table(2))
    print(db.find_table_needing_order())  # should be None now
    state = db.get_restaurant_state()
    print(state)
    db.clear_table(2)
    db.assign_table(2)

    tables = db.list_tables()
    print("Connection OK.")
    print(f"Restaurant state: {state}")
    print(f"Tables loaded: {len(tables)}")


if __name__ == "__main__":
    main()
