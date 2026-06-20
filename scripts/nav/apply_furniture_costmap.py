#!/usr/bin/env python3
"""Merge the OAK-D voxel-layer overlay into the robot's real default nav2.yaml.

Run this ON the Docker host (ROS sourced), not on the dev laptop. It avoids
hand-editing a 400-line params file: it loads TurtleBot4's installed default
nav2.yaml, deep-merges configs/oakd_voxel_layer.overlay.yaml on top, makes sure
the relevant costmap plugins are enabled, substitutes the real point-cloud
topic, and writes a launch-ready configs/nav2_furniture.yaml.

Usage (from repo root inside the container):
    python3 scripts/nav/apply_furniture_costmap.py \
        --pointcloud-topic /oakd/points

Then launch Nav2 with the generated file:
    ros2 launch turtlebot4_navigation nav2.launch.py \
        params_file:=$(pwd)/configs/nav2_furniture.yaml

Override the default source if `ros2 pkg prefix` is not usable:
    --default /opt/ros/jazzy/share/turtlebot4_navigation/config/nav2.yaml
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required (pip install pyyaml).")

REPO_ROOT = Path(__file__).resolve().parents[2]
OVERLAY = REPO_ROOT / "configs" / "oakd_voxel_layer.overlay.yaml"
OUTPUT = REPO_ROOT / "configs" / "nav2_furniture.yaml"
PLACEHOLDER = "__OAKD_POINTCLOUD_TOPIC__"


def find_default_nav2() -> Path:
    """Locate TurtleBot4's installed default nav2.yaml via `ros2 pkg prefix`."""
    try:
        out = subprocess.check_output(
            ["ros2", "pkg", "prefix", "turtlebot4_navigation"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.exit(
            f"Could not locate turtlebot4_navigation ({exc}). "
            "Source ROS, or pass --default explicitly."
        )
    candidate = Path(out) / "share" / "turtlebot4_navigation" / "config" / "nav2.yaml"
    if not candidate.is_file():
        sys.exit(f"Default nav2.yaml not found at {candidate}; pass --default.")
    return candidate


def deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge overlay into base; overlay leaf values win."""
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def ensure_plugin(costmap_params: dict, plugin_name: str) -> None:
    """Make sure `plugin_name` is present in the costmap's `plugins` list."""
    plugins = costmap_params.get("plugins")
    if isinstance(plugins, list) and plugin_name not in plugins:
        # Insert before inflation_layer so inflation runs last.
        if "inflation_layer" in plugins:
            plugins.insert(plugins.index("inflation_layer"), plugin_name)
        else:
            plugins.append(plugin_name)
        print(f"  + added '{plugin_name}' to plugins: {plugins}")


def substitute_topic(node, topic: str):
    """Replace the placeholder topic everywhere it appears (recursively)."""
    if isinstance(node, dict):
        return {k: substitute_topic(v, topic) for k, v in node.items()}
    if isinstance(node, list):
        return [substitute_topic(v, topic) for v in node]
    if node == PLACEHOLDER:
        return topic
    return node


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pointcloud-topic",
        default="/oakd/points",
        help="OAK-D PointCloud2 topic (confirm with `ros2 topic list`).",
    )
    parser.add_argument(
        "--default",
        type=Path,
        default=None,
        help="Path to the default nav2.yaml (auto-detected if omitted).",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    if not OVERLAY.is_file():
        sys.exit(f"Overlay not found: {OVERLAY}")

    default_path = args.default or find_default_nav2()
    print(f"Default nav2.yaml : {default_path}")
    print(f"Overlay           : {OVERLAY}")
    print(f"Point cloud topic : {args.pointcloud_topic}")

    base = yaml.safe_load(default_path.read_text(encoding="utf-8")) or {}
    overlay = yaml.safe_load(OVERLAY.read_text(encoding="utf-8")) or {}
    overlay = substitute_topic(overlay, args.pointcloud_topic)

    merged = deep_merge(base, overlay)

    # Guarantee the layers we extended are actually in the plugin chain.
    try:
        ensure_plugin(
            merged["local_costmap"]["local_costmap"]["ros__parameters"], "voxel_layer"
        )
        ensure_plugin(
            merged["global_costmap"]["global_costmap"]["ros__parameters"],
            "obstacle_layer",
        )
    except KeyError as exc:
        print(f"  ! could not verify plugin list ({exc}); check the output by hand.")

    args.output.write_text(
        yaml.safe_dump(merged, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(f"\nWrote {args.output}")
    print(
        "Launch with:\n"
        f"  ros2 launch turtlebot4_navigation nav2.launch.py "
        f"params_file:={args.output}"
    )


if __name__ == "__main__":
    main()
