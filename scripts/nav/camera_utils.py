"""Camera topic resolution, QoS, and multi-subscriber helpers for GUI + vision nodes."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple, Union

import cv2
import numpy as np
from cv_bridge import CvBridge
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
    qos_profile_sensor_data,
)
from sensor_msgs.msg import CompressedImage, Image as RosImage

if TYPE_CHECKING:
    from rclpy.node import Node
    from rclpy.subscription import Subscription

DEFAULT_CAMERA_TOPIC = "/oakd/rgb/preview/image_raw"
DEFAULT_COMPRESSED_TOPIC = f"{DEFAULT_CAMERA_TOPIC}/compressed"
SENSOR_QOS = qos_profile_sensor_data

CameraMessage = Union[RosImage, CompressedImage]


def camera_qos_profiles() -> List[Union[QoSProfile, int]]:
    """QoS profiles to try; OAK-D may use best-effort or reliable depending on driver."""
    return [
        qos_profile_sensor_data,
        QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            durability=DurabilityPolicy.VOLATILE,
        ),
        QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            durability=DurabilityPolicy.VOLATILE,
        ),
        10,
    ]


def _topic_priority(name: str, types: List[str]) -> Tuple[int, str]:
    """Lower tuple sorts first."""
    is_image = "sensor_msgs/msg/Image" in types
    is_compressed = "sensor_msgs/msg/CompressedImage" in types
    if not (is_image or is_compressed):
        return (99, name)

    score = 50
    if "oakd" in name:
        score -= 20
    if "preview" in name:
        score -= 10
    if "rgb" in name:
        score -= 5
    if is_image and name.endswith("/image_raw"):
        score -= 5
    if is_compressed and name.endswith("/compressed"):
        score -= 3
    if "depth" in name or "theora" in name:
        score += 20
    if name.endswith("/compressedDepth"):
        score += 30
    return (score, name)


def resolve_camera_topics(node: "Node", preferred: str = DEFAULT_CAMERA_TOPIC) -> List[str]:
    """Return camera topics to try, best match first."""
    names_and_types: List[Tuple[str, List[str]]] = node.get_topic_names_and_types()
    topic_map = {name: types for name, types in names_and_types}
    candidates: List[str] = []

    for name, types in names_and_types:
        if "sensor_msgs/msg/Image" not in types and "sensor_msgs/msg/CompressedImage" not in types:
            continue
        if "oakd" not in name and "camera" not in name:
            continue
        if name.endswith("/camera_info"):
            continue
        candidates.append(name)

    candidates.sort(key=lambda n: _topic_priority(n, topic_map.get(n, [])))

    ordered: List[str] = []
    for topic in [preferred, DEFAULT_COMPRESSED_TOPIC, *candidates]:
        if topic not in ordered:
            ordered.append(topic)

    if ordered != [preferred, DEFAULT_COMPRESSED_TOPIC]:
        node.get_logger().info(f"Camera topics to try: {ordered[:5]}")
    elif not candidates:
        node.get_logger().warn(
            f"No OAK-D camera topics discovered yet; will retry ({preferred})"
        )
    return ordered


def ros_image_to_bgr(bridge: CvBridge, msg: RosImage) -> Any:
    """Convert a sensor_msgs/Image to a BGR OpenCV frame."""
    encoding = (msg.encoding or "").lower()
    if encoding in {"bgr8", "rgb8", "mono8", "8uc3"}:
        return bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
    return bridge.imgmsg_to_cv2(msg)


def ros_message_to_bgr(bridge: CvBridge, msg: CameraMessage) -> Any:
    """Convert raw or compressed camera messages to BGR."""
    if isinstance(msg, CompressedImage):
        frame = cv2.imdecode(np.frombuffer(msg.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Failed to decode compressed camera frame")
        return frame
    return ros_image_to_bgr(bridge, msg)


def resolve_camera_topic(node: "Node", preferred: str = DEFAULT_CAMERA_TOPIC) -> str:
    """Return the first preferred camera topic (legacy helper)."""
    topics = resolve_camera_topics(node, preferred)
    return topics[0] if topics else preferred


class CameraSubscriber:
    """Subscribe to camera topics with multiple QoS profiles until frames arrive."""

    RESUBSCRIBE_SEC = 3.0

    def __init__(
        self,
        node: "Node",
        on_frame: Callable[[Any], None],
        preferred_topic: str = DEFAULT_CAMERA_TOPIC,
    ) -> None:
        self._node = node
        self._on_frame = on_frame
        self._preferred_topic = preferred_topic
        self._bridge = CvBridge()
        self._subs: List["Subscription"] = []
        self._enabled = False
        self._active_topic: Optional[str] = None
        self._frame_count = 0
        self._last_resubscribe = 0.0
        self._last_warn = 0.0

    @property
    def active_topic(self) -> Optional[str]:
        return self._active_topic

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled and not self._subs:
            self._subscribe()
        elif not enabled:
            self._destroy_subscriptions()
            self._active_topic = None
            self._frame_count = 0

    def tick(self) -> None:
        """Retry discovery when enabled but no frames have arrived yet."""
        if not self._enabled or self._frame_count > 0:
            return
        now = time.monotonic()
        if now - self._last_resubscribe < self.RESUBSCRIBE_SEC:
            return
        self._last_resubscribe = now
        self._destroy_subscriptions()
        self._subscribe()

    def _subscribe(self) -> None:
        topics = resolve_camera_topics(self._node, self._preferred_topic)
        for topic in topics:
            msg_type = CompressedImage if topic.endswith("/compressed") else RosImage
            for qos in camera_qos_profiles():
                sub = self._node.create_subscription(
                    msg_type,
                    topic,
                    lambda msg, t=topic: self._handle_message(msg, t),
                    qos,
                )
                self._subs.append(sub)
        if self._subs:
            self._node.get_logger().info(
                f"Camera listening on {len(topics)} topic(s) with "
                f"{len(camera_qos_profiles())} QoS profile(s) each"
            )

    def _destroy_subscriptions(self) -> None:
        for sub in self._subs:
            try:
                self._node.destroy_subscription(sub)
            except Exception:
                pass
        self._subs.clear()

    def _handle_message(self, msg: CameraMessage, topic: str) -> None:
        if not self._enabled:
            return
        try:
            frame = ros_message_to_bgr(self._bridge, msg)
            self._active_topic = topic
            self._frame_count += 1
            self._on_frame(frame)
        except Exception as exc:
            now = time.monotonic()
            if now - self._last_warn > 5.0:
                self._last_warn = now
                self._node.get_logger().warn(f"Camera conversion failed on {topic}: {exc}")
