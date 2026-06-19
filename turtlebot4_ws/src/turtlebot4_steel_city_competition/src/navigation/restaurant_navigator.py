#!/usr/bin/env python3

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional

import yaml
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import TaskResult
from turtlebot4_navigation.turtlebot4_navigator import TurtleBot4Navigator

DOCKING_STATION_ID = "docking_station"


def default_waypoints_path() -> Path:
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "configs" / "waypoints.yaml"


def _yaw_to_quaternion(yaw: float) -> tuple[float, float, float, float]:
    return 0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0)


class RestaurantNavigator(TurtleBot4Navigator):
    """Nav2 + TurtleBot4 docking wrapper used by the navigation server."""

    def __init__(self, waypoints_file: Optional[str] = None) -> None:
        super().__init__()
        self._waypoints = self._load_waypoints(waypoints_file)
        self.waitUntilNav2Active()

    def _load_waypoints(self, waypoints_file: Optional[str]) -> Dict[str, Dict[str, float]]:
        path = Path(waypoints_file) if waypoints_file else default_waypoints_path()
        if not path.is_file():
            self.get_logger().warn(f"Waypoints file not found: {path}")
            return {}

        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        if not isinstance(data, dict):
            raise ValueError(f"Invalid waypoints file: {path}")

        return data

    def reload_waypoints(self, waypoints_file: Optional[str] = None) -> None:
        self._waypoints = self._load_waypoints(waypoints_file)

    def list_waypoints(self) -> list[str]:
        return sorted(self._waypoints.keys())

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

    def _wait_for_navigation(self, timeout_sec: float) -> bool:
        start = self.get_clock().now()
        while not self.isTaskComplete():
            if (self.get_clock().now() - start).nanoseconds / 1e9 > timeout_sec:
                self.cancelTask()
                self.get_logger().error("Navigation timed out.")
                return False
        return self.getResult() == TaskResult.SUCCEEDED

    def _navigate_to_pose(self, location_id: str, timeout_sec: float) -> bool:
        goal = self._make_pose(location_id)
        self.goToPose(goal)
        return self._wait_for_navigation(timeout_sec)

    def navigate_to(
        self,
        location_id: str,
        timeout_sec: float = 300.0,
        dock_after: bool = False,
    ) -> bool:
        if location_id not in self._waypoints:
            self.get_logger().error(f"Unknown location_id: {location_id!r}")
            return False

        should_dock = dock_after or location_id == DOCKING_STATION_ID

        if should_dock:
            if not self._navigate_to_pose(location_id, timeout_sec):
                return False
            self.dock()
            return self.getDockedStatus()

        if self.getDockedStatus():
            self.undock()

        return self._navigate_to_pose(location_id, timeout_sec)

    def go_to(self, location_id: str) -> bool:
        return self.navigate_to(location_id)

    def go_to_location(self, location_id: str) -> bool:
        return self.navigate_to(location_id)

    def send_goal(self, location_id: str) -> bool:
        return self.navigate_to(location_id)

    def navigate(self, location_id: str) -> bool:
        return self.navigate_to(location_id)
