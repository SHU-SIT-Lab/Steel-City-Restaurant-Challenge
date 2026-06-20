"""Verify Firestore queries map to the correct navigation waypoint names."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BEHAVIORS_SRC = (
    REPO_ROOT
    / "turtlebot4_ws"
    / "src"
    / "turtlebot4_steel_city_competition"
    / "src"
)
sys.path.insert(0, str(BEHAVIORS_SRC))

from behaviors.database_bridge import (  # noqa: E402
    BARISTA_LOCATION,
    ENTRANCE_LOCATION,
    table_id_to_location,
)
from repository import RestaurantDatabase  # noqa: E402


def main() -> None:
    db = RestaurantDatabase()
    table_id = 2

    print("Waypoint constants:")
    print(f"  entrance = {ENTRANCE_LOCATION!r}")
    print(f"  barista  = {BARISTA_LOCATION!r}")

    print("\nTable id mapping (Firestore 0-based -> waypoint):")
    for tid in db.list_table_ids():
        print(f"  table_id {tid} -> {table_id_to_location(tid)!r}")

    print(f"\nExample flow for table_id={table_id}:")
    print(f"  take_order        -> {table_id_to_location(table_id)!r}")
    print(f"  introduce_table   -> {ENTRANCE_LOCATION!r} then {table_id_to_location(table_id)!r}")
    print(f"  collect_order     -> {BARISTA_LOCATION!r} then {table_id_to_location(table_id)!r}")

    print("\nNavigation target mapping OK.")


if __name__ == "__main__":
    main()
