#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys
from typing import Optional

import rclpy
from rclpy.node import Node

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from turtlebot4_steel_city_competition.srv import NavigateToWaypoint


class NavigationClient(Node):
    """Thin service client exposing the same method names as RestaurantNavigator."""

    def __init__(
        self,
        service_name: str = "/navigation/navigate_to_waypoint",
        wait_timeout_sec: float = 10.0,
    ) -> None:
        super().__init__("navigation_client")
        self._service_name = service_name
        self._wait_timeout_sec = wait_timeout_sec
        self._client = self.create_client(NavigateToWaypoint, service_name)

    def _wait_for_service(self) -> bool:
        if self._client.wait_for_service(timeout_sec=self._wait_timeout_sec):
            return True
        self.get_logger().warn(
            f"Navigation service {self._service_name!r} unavailable "
            f"after {self._wait_timeout_sec}s."
        )
        return False

    def _call(self, destination: str) -> bool:
        if not self._wait_for_service():
            return False

        request = NavigateToWaypoint.Request()
        request.destination = destination
        future = self._client.call_async(request)
        rclpy.spin_until_future_complete(self, future)

        if not future.done() or future.result() is None:
            self.get_logger().error(f"Navigation service call to {destination!r} failed.")
            return False

        response = future.result()
        if not response.success:
            self.get_logger().warn(response.message)
        return response.success

    def navigate_to(self, location_id: str, timeout_sec: float = 300.0, dock_after: bool = False) -> bool:
        del timeout_sec, dock_after
        return self._call(location_id)

    def go_to(self, location_id: str) -> bool:
        return self.navigate_to(location_id)

    def go_to_location(self, location_id: str) -> bool:
        return self.navigate_to(location_id)

    def send_goal(self, location_id: str) -> bool:
        return self.navigate_to(location_id)

    def navigate(self, location_id: str) -> bool:
        return self.navigate_to(location_id)
