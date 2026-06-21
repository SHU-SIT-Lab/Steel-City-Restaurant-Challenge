#!/usr/bin/env python3

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple

import cv2
import rclpy
from rclpy.node import Node

NAV_DIR = Path(__file__).resolve().parents[5] / "scripts" / "nav"
if str(NAV_DIR) not in sys.path:
	sys.path.insert(0, str(NAV_DIR))

from camera_utils import DEFAULT_CAMERA_TOPIC, CameraSubscriber  # noqa: E402


# Global settings: change these values when you want different behavior.
CAMERA_CONFIG = {
	"topic": DEFAULT_CAMERA_TOPIC,
	"queue_size": 10,
	"upsample_scale": 2.0,
	"downsample_scale": 0.5,
	"target_size": (320, 240),
}

# Kept for callers that imported CAMERA_QOS before the CameraSubscriber refactor.
CAMERA_QOS = 10


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
		self.frames = CameraFrames()
		self._camera = CameraSubscriber(self, self._store_frame, CAMERA_CONFIG["topic"])
		self._camera.set_enabled(True)
		self.create_timer(3.0, lambda: self._camera.tick())

	def _store_frame(self, frame: Any) -> None:
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
