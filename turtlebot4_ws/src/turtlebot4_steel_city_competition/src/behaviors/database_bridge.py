"""Bridge ROS behavior code to the repository database module."""

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[5]
DATABASE_DIR = REPO_ROOT / "scripts" / "database"

if str(DATABASE_DIR) not in sys.path:
	sys.path.insert(0, str(DATABASE_DIR))

from models import TableStatus
from repository import RestaurantDatabase


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
