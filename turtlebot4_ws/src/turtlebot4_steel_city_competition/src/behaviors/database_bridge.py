"""Bridge ROS behavior code to the repository database module."""

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[5]
DATABASE_DIR = REPO_ROOT / "scripts" / "database"

if str(DATABASE_DIR) not in sys.path:
	sys.path.insert(0, str(DATABASE_DIR))

from models import TableStatus
from repository import RestaurantDatabase

ENTRANCE_LOCATION = "entrance"
BARISTA_LOCATION = "barista"


def table_id_to_location(table_id: int) -> str:
	"""Map Firestore table id (0-based) to waypoint name (table_1 … table_N)."""
	return f"table_{table_id + 1}"


def set_navigation_target(
	ctx: Any,
	location_id: str,
	table_id: Optional[int] = None,
	next_location: Optional[str] = None,
) -> None:
	"""Publish navigation targets for the navigation team via shared_state."""
	state = shared_state(ctx)
	state["target_location"] = location_id
	if table_id is not None:
		state["current_table_id"] = table_id
	if next_location is not None:
		state["next_target_location"] = next_location
	else:
		state.pop("next_target_location", None)


def shared_state(ctx: Any) -> dict[str, Any]:
	if isinstance(ctx, dict):
		state = ctx.get("shared_state", {})
		if isinstance(state, dict):
			return state
	return {}


def get_bool(value: Any, default: bool = False) -> bool:
	if value is None:
		return default
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "y", "ready", "delivered"}
	return bool(value)


def get_int(value: Any, default: int = 0) -> int:
	if value is None:
		return default
	if isinstance(value, int):
		return value
	if isinstance(value, str):
		match = re.search(r"\d+", value)
		if match:
			return int(match.group(0))
	return default


def table_empty_status(value: Any) -> TableStatus:
	if isinstance(value, str):
		status = value.strip().lower()
		if status in {"empty", "available", "free", "true", "1", "yes", "y"}:
			return TableStatus.EMPTY
		return TableStatus.OCCUPIED
	return TableStatus.EMPTY if get_bool(value) else TableStatus.OCCUPIED
