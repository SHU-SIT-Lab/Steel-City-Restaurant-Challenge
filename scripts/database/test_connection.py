"""Quick check that Firestore credentials and collections work."""

from __future__ import annotations

from config import credentials_path
from repository import RestaurantDatabase


def main() -> None:
    print(f"Using credentials: {credentials_path()}")
    db = RestaurantDatabase()
    state = db.get_restaurant_state()
    tables = db.list_tables()
    print("Connection OK.")
    print(f"Restaurant state: {state}")
    print(f"Tables loaded: {len(tables)}")


if __name__ == "__main__":
    main()
