#!/usr/bin/env python3

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import cv2
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

# Make sibling modules in src importable when this script is run directly.
SRC_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[5]
VISION_DIR = REPO_ROOT / "scripts" / "vision"
NAV_DIR = REPO_ROOT / "scripts" / "nav"
if str(SRC_DIR) not in sys.path:
	sys.path.insert(0, str(SRC_DIR))
if str(VISION_DIR) not in sys.path:
	sys.path.insert(0, str(VISION_DIR))
if str(NAV_DIR) not in sys.path:
	sys.path.insert(0, str(NAV_DIR))

from camera_utils import CameraSubscriber  # noqa: E402
from helpers.retrieve_camera import CAMERA_CONFIG
from helpers.process_camera import process_frame

try:
	from order_verification import OrderVerificationResult, verify_order
except ImportError:
	verify_order = None  # type: ignore[assignment]
	OrderVerificationResult = None  # type: ignore[assignment,misc]

# Global params for this action.
OBJ_DETECTION_CONFIG = {
	"debug": True,
	"debug_window_name": "turtlebot_img_debug",
}


class ObjectDetection(Node):
	def __init__(self) -> None:
		super().__init__("object_detection")
		self.debug = OBJ_DETECTION_CONFIG["debug"]
		self.turtlebot_img: Optional[Any] = None
		self._camera = CameraSubscriber(self, self._camera_callback, CAMERA_CONFIG["topic"])
		self._camera.set_enabled(True)
		self.create_timer(3.0, lambda: self._camera.tick())

		self.people_detected = None
		self.table_detected = None
		self.occupied_table = None
		self.free_table = None
		self.objects_detected = None

		# Fields database behaviors read (see check_customer_behavior.py )
		self.customer_present = False
		self.customers_waiting = 0
		self.table_empty = None  # bool for current view, or dict {table_id: bool}
		self.current_table_id = None  # set by nav/behaviors when robot is at a table

	def _camera_callback(self, raw_frame) -> None:
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

		people = self.people_detected or 0
		occupied = self.occupied_table or 0
		free = self.free_table or 0
		# Entrance: any person in frame
		self.customer_present = people > 0
		self.customers_waiting = people

		# Table: empty if YOLO sees a free table and no occupied table
		# (robot should be facing ONE table when this is used)
		if self.table_detected and self.table_detected > 0:
			if occupied > 0:
				is_empty = False
			else:
				is_empty = free > 0
			if self.current_table_id is not None:
				self.table_empty = {self.current_table_id: is_empty}
			else:
				self.table_empty = is_empty
		else:
			self.table_empty = None

		
		print(f"[VISION] people={people} customer_present={self.customer_present} table_empty={self.table_empty}")

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
		return self.objects_detected or {}

	def verify_order_items(
		self,
		order_items: List[str],
		menu_lookup: Optional[dict] = None,
	) -> Optional[Any]:
		"""Compare expected menu order entries with the latest camera detections."""
		if verify_order is None:
			print("[VISION] order verification unavailable (order_verification import failed).")
			return None

		detected = self.get_objects_detected()
		result = verify_order(order_items, detected, menus=menu_lookup)
		print(
			"[VISION] order verify "
			f"correct={result.is_correct} required={dict(result.required)} "
			f"detected={dict(result.detected)} missing={dict(result.missing)} "
			f"extra={dict(result.extra)}"
		)
		return result

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