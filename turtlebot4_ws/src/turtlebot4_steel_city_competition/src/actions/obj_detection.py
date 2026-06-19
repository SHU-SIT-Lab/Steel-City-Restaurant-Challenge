#!/usr/bin/env python3

from pathlib import Path
import sys
from typing import Any, Dict, Optional

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Image

# Make sibling modules in src importable when this script is run directly.
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
	sys.path.insert(0, str(SRC_DIR))

from helpers.retrieve_camera import CAMERA_CONFIG
from helpers.process_camera import process_frame

# Global params for this action.
OBJ_DETECTION_CONFIG = {
	"debug": True,
	"debug_window_name": "turtlebot_img_debug",
}


class ObjectDetection(Node):
	def __init__(self) -> None:
		super().__init__("object_detection")
		self.bridge = CvBridge()
		self.debug = OBJ_DETECTION_CONFIG["debug"]
		self.turtlebot_img: Optional[Any] = None

		# Subscribe to TurtleBot camera topic.
		self.subscription = self.create_subscription(
			Image,
			CAMERA_CONFIG["topic"],
			self._camera_callback,
			CAMERA_CONFIG["queue_size"],
		)

		self.people_detected = None
		self.table_detected = None
		self.occupied_table = None
		self.free_table = None
		self.objects_detected = None

	def _camera_callback(self, msg: Image) -> None:
		raw_frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
		
		# Store raw frame for display
		self.turtlebot_img = raw_frame

		(
			self.processed_img,
			self.people_detected,
			self.table_detected,
			self.occupied_table,
			self.free_table,
			self.objects_detected
		) = process_frame(raw_frame)

		if self.debug and self.turtlebot_img is not None:
			cv2.imshow(OBJ_DETECTION_CONFIG["debug_window_name"], self.processed_img)
			cv2.waitKey(1)


	def get_people_detected(self) -> int:
		return self.people_detected

	def get_table_detected(self) -> int:
		return self.table_detected

	def get_occupied_table(self) -> int:
		return self.occupied_table
	
	def get_free_table(self) -> int:
		return self.free_table
	
	def get_objects_detected(self) -> Dict[str, int]:
		return self.objects_detected

	def destroy_node(self) -> bool:
		if self.debug:
			cv2.destroyAllWindows()
		return super().destroy_node()


def main(args=None) -> None:
	rclpy.init(args=args)
	node = ObjectDetection()
	try:
		rclpy.spin(node)
	except KeyboardInterrupt:
		pass
	except ExternalShutdownException:
		pass
	finally:
		node.destroy_node()
		if rclpy.ok():
			rclpy.shutdown()


if __name__ == "__main__":
	main()