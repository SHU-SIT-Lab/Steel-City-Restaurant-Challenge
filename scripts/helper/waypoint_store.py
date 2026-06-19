"""Load and save configs/waypoints.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def default_waypoints_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "configs" / "waypoints.yaml"


def load_waypoints(path: Path) -> Dict[str, Dict[str, float]]:
    if not path.is_file():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Invalid waypoints file: {path}")

    return {
        name: {
            "x": float(entry.get("x", 0.0)),
            "y": float(entry.get("y", 0.0)),
            "yaw": float(entry.get("yaw", 0.0)),
        }
        for name, entry in data.items()
        if isinstance(entry, dict)
    }


def save_waypoints(path: Path, waypoints: Dict[str, Dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: Dict[str, Any] = {}
    for name in sorted(waypoints):
        entry = waypoints[name]
        payload[name] = {
            "x": round(float(entry["x"]), 4),
            "y": round(float(entry["y"]), 4),
            "yaw": round(float(entry["yaw"]), 4),
        }

    header = (
        "# Named poses for restaurant navigation (map frame).\n"
        "# Update x/y/yaw after mapping the competition arena.\n\n"
    )
    with path.open("w", encoding="utf-8") as handle:
        handle.write(header)
        yaml.safe_dump(payload, handle, default_flow_style=False, sort_keys=True)
