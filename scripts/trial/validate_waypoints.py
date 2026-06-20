#!/usr/bin/env python3
"""Validate configs/waypoints.yaml has all required keys (§4)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REQUIRED = (
	"entrance",
	"barista",
	"table_1",
	"table_2",
	"table_3",
	"table_4",
	"table_5",
	"docking_station",
)
REPO_ROOT = Path(__file__).resolve().parents[2]
WAYPOINTS = REPO_ROOT / "configs" / "waypoints.yaml"


def main() -> int:
	data = yaml.safe_load(WAYPOINTS.read_text())
	missing = [key for key in REQUIRED if key not in data]
	if missing:
		print(f"FAIL: missing waypoint keys: {missing}")
		return 1

	placeholders = []
	for key in REQUIRED:
		pose = data[key]
		if pose.get("x") == 0.0 and pose.get("y") == 0.0 and pose.get("yaw") == 0.0:
			placeholders.append(key)

	if placeholders:
		print(f"WARN: placeholders (0,0,0) — record on robot: {', '.join(placeholders)}")

	print(f"OK: all {len(REQUIRED)} waypoint keys present in {WAYPOINTS}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
