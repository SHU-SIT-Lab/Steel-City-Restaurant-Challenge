#!/usr/bin/env python3
"""Rename waypoint keys to match competition code expectations.

Mappings:
  kitchen  -> barista
  table1   -> table_1  (and table2/3/4/5 similarly)
  table_1  kept as-is

Adds placeholder table_4/table_5 if missing (copied from table_3).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = REPO_ROOT / "configs" / "waypoints.yaml"

ALIASES = {
    "kitchen": "barista",
    "kitchen_bar": "barista",
}

TABLE_RENAMES = {f"table{i}": f"table_{i}" for i in range(1, 10)}


def normalize(data: dict) -> dict:
    out: dict = {}
    for name, pose in data.items():
        if not isinstance(pose, dict):
            continue
        canonical = ALIASES.get(name, TABLE_RENAMES.get(name, name))
        if canonical in out and out[canonical] != pose:
            print(f"WARN: duplicate source for {canonical!r}; keeping first entry")
            continue
        out[canonical] = {
            "x": float(pose.get("x", 0.0)),
            "y": float(pose.get("y", 0.0)),
            "yaw": float(pose.get("yaw", 0.0)),
        }

    if "table_3" in out:
        for key in ("table_4", "table_5"):
            if key not in out:
                out[key] = dict(out["table_3"])
                print(f"Added placeholder {key} (copy of table_3) — record on robot.")

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--waypoints",
        type=Path,
        default=DEFAULT_PATH,
        help="Path to waypoints YAML",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print result without writing",
    )
    args = parser.parse_args()

    if not args.waypoints.is_file():
        print(f"FAIL: {args.waypoints} not found", file=sys.stderr)
        return 1

    raw = yaml.safe_load(args.waypoints.read_text(encoding="utf-8")) or {}
    normalized = normalize(raw)

    header = (
        "# Named poses for restaurant navigation (map frame).\n"
        "# Keys normalized for competition stack (barista, table_1, ...).\n\n"
    )
    body = yaml.safe_dump(normalized, default_flow_style=False, sort_keys=True)

    if args.dry_run:
        print(header + body)
        return 0

    args.waypoints.write_text(header + body, encoding="utf-8")
    print(f"Normalized waypoint keys in {args.waypoints}")
    print(f"  keys: {', '.join(sorted(normalized))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
