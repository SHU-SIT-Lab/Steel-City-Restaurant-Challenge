#!/usr/bin/env python3
"""Generate Jazzy-safe Nav2 and localization params for competition day.

Copies TurtleBot4's installed nav2.yaml and localization.yaml, sets
use_sim_time: false everywhere, and writes launch-ready files under configs/.

Run inside Docker with ROS sourced:
    python3 scripts/nav/apply_nav2_competition.py
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required (pip install pyyaml).")

REPO_ROOT = Path(__file__).resolve().parents[2]
NAV2_OUTPUT = REPO_ROOT / "configs" / "nav2_competition.yaml"
LOCALIZATION_OUTPUT = REPO_ROOT / "configs" / "localization_competition.yaml"


def pkg_config_dir() -> Path:
    try:
        out = subprocess.check_output(
            ["ros2", "pkg", "prefix", "turtlebot4_navigation"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.exit(
            f"Could not locate turtlebot4_navigation ({exc}). "
            "Source ROS inside Docker, or pass --config-dir explicitly."
        )
    candidate = Path(out) / "share" / "turtlebot4_navigation" / "config"
    if not candidate.is_dir():
        sys.exit(f"Config directory not found: {candidate}")
    return candidate


def strip_use_sim_time(text: str) -> tuple[str, int]:
    """Remove use_sim_time lines so launch use_sim_time:=false propagates (Jazzy TB4 #550)."""
    count = len(re.findall(r"^\s*use_sim_time:\s*(true|false)\s*$", text, re.MULTILINE))
    patched = re.sub(r"^\s*use_sim_time:\s*(true|false)\s*\n", "", text, flags=re.MULTILINE)
    return patched, count


def patch_scan_topics(text: str) -> str:
    """Use absolute /scan for discovery-server (TB4 issue #255)."""
    return re.sub(
        r"((?:scan_topic|topic):\s*)scan\b",
        r"\1/scan",
        text,
    )


def patch_collision_monitor(text: str) -> str:
    """Relax collision monitor for discovery-server / Wi-Fi latency."""
    text = re.sub(
        r"(collision_monitor:\s*\n\s*ros__parameters:\s*\n(?:.*\n)*?\s*)source_timeout:\s*[\d.]+",
        r"\1source_timeout: 2.0",
        text,
        count=1,
    )
    text = re.sub(
        r"(collision_monitor:\s*\n\s*ros__parameters:\s*\n(?:.*\n)*?\s*)transform_tolerance:\s*[\d.]+",
        r"\1transform_tolerance: 0.5",
        text,
        count=1,
    )
    # FootprintApproach stops cmd_vel when scan/TF arrive late over the discovery server.
    text = re.sub(
        r"(FootprintApproach:\s*\n(?:.*\n)*?\s*)enabled:\s*True",
        r"\1enabled: False",
        text,
        count=1,
    )
    return text


def patch_progress_checker(text: str) -> str:
    """Avoid FAILED_TO_MAKE_PROGRESS (105) when Wi-Fi adds controller latency."""
    text = re.sub(
        r"(progress_checker:\s*\n\s*plugin:.*\n\s*)required_movement_radius:\s*[\d.]+",
        r"\1required_movement_radius: 0.2",
        text,
        count=1,
    )
    text = re.sub(
        r"(progress_checker:\s*\n(?:.*\n)*?\s*)movement_time_allowance:\s*[\d.]+",
        r"\1movement_time_allowance: 30.0",
        text,
        count=1,
    )
    return text


def check_footprint(data: dict) -> None:
    """Warn if costmaps rely on robot_radius without a polygon footprint."""
    for section in ("local_costmap", "global_costmap"):
        try:
            params = data[section][section]["ros__parameters"]
        except (KeyError, TypeError):
            continue
        has_radius = "robot_radius" in params
        has_footprint = "footprint" in params
        if has_radius and not has_footprint:
            print(
                f"  [WARN] {section} uses robot_radius without footprint — "
                "Jazzy Nav2 may fail (see turtlebot4 issue #591)."
            )
        elif has_footprint:
            print(f"  [OK] {section} has polygon footprint.")


def process_file(source: Path, dest: Path) -> None:
    raw = source.read_text(encoding="utf-8")
    patched, count = strip_use_sim_time(raw)
    if source.name == "nav2.yaml":
        patched = patch_scan_topics(patched)
        patched = patch_collision_monitor(patched)
        patched = patch_progress_checker(patched)
    elif source.name == "localization.yaml":
        patched = patch_scan_topics(patched)
    dest.write_text(patched, encoding="utf-8")
    data = yaml.safe_load(patched) or {}
    print(f"Wrote {dest}")
    print(f"  removed use_sim_time lines ({count} occurrence(s))")
    if source.name == "nav2.yaml":
        check_footprint(data)
        print("  collision_monitor source_timeout=2.0, transform_tolerance=0.5")
        print("  FootprintApproach disabled (discovery-server safe)")
        print("  progress_checker radius=0.2 m, allowance=30 s")
        print("  scan topics patched to /scan (discovery-server safe)")
    elif source.name == "localization.yaml":
        print("  scan_topic patched to /scan (discovery-server safe)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=None,
        help="Directory containing nav2.yaml and localization.yaml",
    )
    args = parser.parse_args()

    config_dir = args.config_dir or pkg_config_dir()
    nav2_src = config_dir / "nav2.yaml"
    loc_src = config_dir / "localization.yaml"

    for path in (nav2_src, loc_src):
        if not path.is_file():
            sys.exit(f"Missing upstream config: {path}")

    print(f"Source config dir: {config_dir}")
    process_file(nav2_src, NAV2_OUTPUT)
    process_file(loc_src, LOCALIZATION_OUTPUT)
    print("\nLaunch with:")
    print("  ros2 launch turtlebot4_steel_city_competition competition_localization.launch.py")
    print("  ros2 launch turtlebot4_steel_city_competition competition_nav2.launch.py")


if __name__ == "__main__":
    main()
