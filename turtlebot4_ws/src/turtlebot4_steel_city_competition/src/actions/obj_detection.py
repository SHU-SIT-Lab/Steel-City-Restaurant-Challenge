#!/usr/bin/env python3

from pathlib import Path
import sys
from typing import Any, Optional

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image

# Make sibling modules in src importable when this script is run directly.
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
	sys.path.insert(0, str(SRC_DIR))

from helpers.retrieve_camera import CAMERA_CONFIG, process_frame


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
        self.table_empty = None # TODO: to be updated by callback
        self.customer_present = None # TODO: to be updated by callback

	def _camera_callback(self, msg: Image) -> None:
		raw_frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
		processed = process_frame(raw_frame)

		# Use resized image as the default image for model input.
		self.turtlebot_img = processed.resized

		if self.debug and self.turtlebot_img is not None:
			cv2.imshow(OBJ_DETECTION_CONFIG["debug_window_name"], self.turtlebot_img)
			cv2.waitKey(1)

		self.todo_detect_objects(self.turtlebot_img)

        # TODO: Update table_empty and customer_present based on object detection results
        self.table_empty = self.check_table()
        self.customer_present = self.check_customer()

	def todo_detect_objects(self, turtlebot_img) -> None:
		# TODO: Send turtlebot_img to your object detection model.
		# TODO: Parse model output and publish action result.
		_ = turtlebot_img

    def check_customer(self) -> bool:
        # TODO: Check if there are any customers at the entrance
        return True

    def check_table(self) -> bool:
        # TODO: Check if the table is empty or not
        return True

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
	finally:
		node.destroy_node()
		rclpy.shutdown()


if __name__ == "__main__":
	main()
