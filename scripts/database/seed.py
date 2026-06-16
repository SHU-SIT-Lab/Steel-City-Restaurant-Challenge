"""Initialize Firestore collections with default documents."""

from __future__ import annotations

from repository import RestaurantDatabase


def main() -> None:
    db = RestaurantDatabase()
    db.seed_tables()
    db.seed_restaurant_state()
    print("Firestore seed complete.")
    print(f"Tables: {[table.table_id for table in db.list_tables()]}")


if __name__ == "__main__":
    main()
