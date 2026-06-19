#!/usr/bin/env python3

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional

import yaml
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult


def _default_waypoints_path() -> Path:
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "configs" / "waypoints.yaml"


def _yaw_to_quaternion(yaw: float) -> tuple[float, float, float, float]:
    return 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)


class RestaurantNavigator(BasicNavigator):
    """Nav2 wrapper used by competition behaviors."""

    def __init__(self, waypoints_file: Optional[str] = None) -> None:
        super().__init__()
        self._waypoints = self._load_waypoints(waypoints_file)
        self.waitUntilNav2Active()

    def _load_waypoints(self, waypoints_file: Optional[str]) -> Dict[str, Dict[str, float]]:
        path = Path(waypoints_file) if waypoints_file else _default_waypoints_path()
        if not path.is_file():
            self.get_logger().warn(f"Waypoints file not found: {path}")
            return {}

        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        if not isinstance(data, dict):
            raise ValueError(f"Invalid waypoints file: {path}")

        return data

    def _make_pose(self, location_id: str) -> PoseStamped:
        if location_id not in self._waypoints:
            raise KeyError(f"Unknown location_id: {location_id!r}")

        waypoint = self._waypoints[location_id]
        pose = PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = float(waypoint.get("x", 0.0))
        pose.pose.position.y = float(waypoint.get("y", 0.0))
        qx, qy, qz, qw = _yaw_to_quaternion(float(waypoint.get("yaw", 0.0)))
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        return pose

    def navigate_to(self, location_id: str, timeout_sec: float = 300.0) -> bool:
        if location_id not in self._waypoints:
            self.get_logger().error(f"Unknown location_id: {location_id!r}")
            return False

        goal = self._make_pose(location_id)
        self.goToPose(goal)
        start = self.get_clock().now()
        while not self.isTaskComplete():
            if (self.get_clock().now() - start).nanoseconds / 1e9 > timeout_sec:
                self.cancelTask()
                return False

        return self.getResult() == TaskResult.SUCCEEDED

    def go_to(self, location_id: str) -> bool:
        return self.navigate_to(location_id)

    def go_to_location(self, location_id: str) -> bool:
        return self.navigate_to(location_id)

    def send_goal(self, location_id: str) -> bool:
        return self.navigate_to(location_id)

    def navigate(self, location_id: str) -> bool:
        return self.navigate_to(location_id)
