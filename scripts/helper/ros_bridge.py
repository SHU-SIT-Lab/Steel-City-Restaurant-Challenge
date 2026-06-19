"""ROS bridge for the waypoint recorder helper GUI."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
from rclpy.node import Node
from sensor_msgs.msg import Image
from turtlebot4_steel_city_competition.srv import NavigateToWaypoint


CAMERA_TOPIC = "/oakd/rgb/preview/image_raw"
AMCL_POSE_TOPIC = "/amcl_pose"
CMD_VEL_TOPIC = "/cmd_vel"
NAV_SERVICE = "/navigation/navigate_to_waypoint"


@dataclass
class RobotPose:
    x: float
    y: float
    yaw: float


def quaternion_to_yaw(qx: float, qy: float, qz: float, qw: float) -> float:
    return math.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))


class HelperRosBridge(Node):
    def __init__(self) -> None:
        super().__init__("waypoint_recorder_bridge")
        self._bridge = CvBridge()
        self._camera_enabled = False
        self._latest_frame = None
        self._latest_pose: Optional[RobotPose] = None
        self._pose_received = False
        self._nav_client = self.create_client(NavigateToWaypoint, NAV_SERVICE)
        self._cmd_vel_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self._camera_sub = None
        self._pose_sub = self.create_subscription(
            PoseWithCovarianceStamped,
            AMCL_POSE_TOPIC,
            self._pose_callback,
            10,
        )

    def _pose_callback(self, msg: PoseWithCovarianceStamped) -> None:
        orientation = msg.pose.pose.orientation
        self._latest_pose = RobotPose(
            x=msg.pose.pose.position.x,
            y=msg.pose.pose.position.y,
            yaw=quaternion_to_yaw(
                orientation.x,
                orientation.y,
                orientation.z,
                orientation.w,
            ),
        )
        self._pose_received = True

    def _camera_callback(self, msg: Image) -> None:
        if not self._camera_enabled:
            return
        try:
            self._latest_frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as exc:
            self.get_logger().warn(f"Camera conversion failed: {exc}")

    def set_camera_enabled(self, enabled: bool) -> None:
        self._camera_enabled = enabled
        if enabled and self._camera_sub is None:
            self._camera_sub = self.create_subscription(
                Image,
                CAMERA_TOPIC,
                self._camera_callback,
                10,
            )
        if not enabled:
            self._latest_frame = None

    def get_latest_frame(self):
        return self._latest_frame

    def get_current_pose(self) -> Optional[RobotPose]:
        return self._latest_pose

    def has_pose(self) -> bool:
        return self._pose_received and self._latest_pose is not None

    def navigation_service_available(self) -> bool:
        return self._nav_client.service_is_ready()

    def wait_for_navigation_service(self, timeout_sec: float = 2.0) -> bool:
        return self._nav_client.wait_for_service(timeout_sec=timeout_sec)

    def navigate_to(self, destination: str) -> Tuple[bool, str]:
        if not self.wait_for_navigation_service(timeout_sec=5.0):
            return False, "Navigation service unavailable."

        request = NavigateToWaypoint.Request()
        request.destination = destination
        future = self._nav_client.call_async(request)
        rclpy.spin_until_future_complete(self, future)
        if not future.done() or future.result() is None:
            return False, "Navigation service call failed."

        response = future.result()
        return response.success, response.message

    def publish_cmd_vel(self, linear_x: float, angular_z: float) -> None:
        twist = Twist()
        twist.linear.x = linear_x
        twist.angular.z = angular_z
        self._cmd_vel_pub.publish(twist)

    def stop(self) -> None:
        self.publish_cmd_vel(0.0, 0.0)


def start_ros_spin(node: HelperRosBridge, on_error: Optional[Callable[[Exception], None]] = None) -> threading.Thread:
    def _spin() -> None:
        try:
            rclpy.spin(node)
        except Exception as exc:
            if on_error:
                on_error(exc)

    thread = threading.Thread(target=_spin, daemon=True)
    thread.start()
    return thread
