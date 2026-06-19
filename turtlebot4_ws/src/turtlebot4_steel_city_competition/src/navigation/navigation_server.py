#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import sys
from typing import Optional

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from navigation.restaurant_navigator import RestaurantNavigator
from turtlebot4_steel_city_competition.srv import NavigateToWaypoint


class NavigationServer(Node):
    """ROS service bridge between high-level callers and RestaurantNavigator."""

    def __init__(self, waypoints_file: Optional[str] = None) -> None:
        super().__init__("navigation_server")
        self._service_group = ReentrantCallbackGroup()
        self._navigator = RestaurantNavigator(waypoints_file=waypoints_file)
        self._service = self.create_service(
            NavigateToWaypoint,
            "/navigation/navigate_to_waypoint",
            self._handle_navigate,
            callback_group=self._service_group,
        )
        self.get_logger().info("Navigation server ready on /navigation/navigate_to_waypoint")

    def _handle_navigate(
        self,
        request: NavigateToWaypoint.Request,
        response: NavigateToWaypoint.Response,
    ) -> NavigateToWaypoint.Response:
        destination = request.destination.strip()
        if not destination:
            response.success = False
            response.message = "Destination must not be empty."
            return response

        self.get_logger().info(f"Navigating to {destination!r}")
        try:
            success = self._navigator.navigate_to(destination)
        except Exception as exc:
            response.success = False
            response.message = f"Navigation failed: {exc}"
            self.get_logger().error(response.message)
            return response

        if success:
            response.success = True
            response.message = f"Reached {destination!r}."
        else:
            response.success = False
            response.message = f"Failed to reach {destination!r}."

        self.get_logger().info(response.message)
        return response


def main(args=None) -> None:
    rclpy.init(args=args)
    server = NavigationServer()
    executor = MultiThreadedExecutor()
    executor.add_node(server)
    executor.add_node(server._navigator)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        server._navigator.destroy_node()
        server.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
