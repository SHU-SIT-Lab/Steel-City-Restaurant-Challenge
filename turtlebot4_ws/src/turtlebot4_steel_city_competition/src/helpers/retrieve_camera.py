#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Any, Optional, Tuple

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image


# Global settings: change these values when you want different behavior.
CAMERA_CONFIG = {
	"topic": "/oakd/rgb/preview/image_raw",
	"queue_size": 10,
	"upsample_scale": 2.0,
	"downsample_scale": 0.5,
	"target_size": (320, 240),
}


@dataclass
class CameraFrames:
	raw: Optional[Any] = None
	upsampled: Optional[Any] = None
	downsampled: Optional[Any] = None
	resized: Optional[Any] = None


def upsample_frame(frame: Any, scale: Optional[float] = None) -> Any:
	value = scale if scale is not None else CAMERA_CONFIG["upsample_scale"]
	return cv2.resize(frame, None, fx=value, fy=value, interpolation=cv2.INTER_CUBIC)


def downsample_frame(frame: Any, scale: Optional[float] = None) -> Any:
	value = scale if scale is not None else CAMERA_CONFIG["downsample_scale"]
	return cv2.resize(frame, None, fx=value, fy=value, interpolation=cv2.INTER_AREA)


def resize_frame(frame: Any, size: Optional[Tuple[int, int]] = None) -> Any:
	target = size if size is not None else CAMERA_CONFIG["target_size"]
	return cv2.resize(frame, target, interpolation=cv2.INTER_AREA)


def process_frame(frame: Any) -> CameraFrames:
	return CameraFrames(
		raw=frame,
		upsampled=upsample_frame(frame),
		downsampled=downsample_frame(frame),
		resized=resize_frame(frame),
	)


class RetrieveCamera(Node):
	def __init__(self) -> None:
		super().__init__("retrieve_camera")
		self.bridge = CvBridge()
		self.frames = CameraFrames()

		# Subscribe to camera topic and store the latest processed frames.
		self.subscription = self.create_subscription(
			Image,
			CAMERA_CONFIG["topic"],
			self._camera_callback,
			CAMERA_CONFIG["queue_size"],
		)

	def _camera_callback(self, msg: Image) -> None:
		frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
		self.frames = process_frame(frame)

	def upsample(self, frame) -> Any:
		return upsample_frame(frame)

	def downsample(self, frame) -> Any:
		return downsample_frame(frame)

	def resize_to_target(self, frame, size: Optional[Tuple[int, int]] = None) -> Any:
		return resize_frame(frame, size=size)

	def get_latest_frames(self) -> CameraFrames:
		return self.frames


def main(args=None) -> None:
	rclpy.init(args=args)
	node = RetrieveCamera()
	try:
		rclpy.spin(node)
	except KeyboardInterrupt:
		pass
	finally:
		node.destroy_node()
		rclpy.shutdown()


if __name__ == "__main__":
	main()
