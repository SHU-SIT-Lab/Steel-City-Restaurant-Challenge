#!/usr/bin/env python3

from __future__ import annotations

from collections import deque
from pathlib import Path
import sys
from typing import Deque, Dict, List, Optional

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

# Make sibling modules in src importable when this script is run directly.
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
	sys.path.insert(0, str(SRC_DIR))

from behaviors.behaviors import DeliberativeBehavior
from behaviors.check_customer_behavior import CheckCustomerBehavior
from behaviors.check_empty_table_behavior import CheckEmptyTableBehavior
from behaviors.collect_order_behavior import CollectOrderBehavior
from behaviors.introduce_table_behavior import IntroduceTableBehavior
from behaviors.mark_order_ready_behavior import MarkOrderReadyBehavior
from behaviors.take_order_behavior import TakeOrderBehavior
from behaviors.update_customer_number_behavior import CheckCustomerNumberBehavior

from actions.obj_detection import ObjectDetection
from actions.speech_to_text import SpeechToText
from actions.text_to_speech import TextToSpeech


class ReactiveCoordinator(Node):
	def __init__(self) -> None:
		super().__init__("reactive_coordinator")
		self._behaviors: List[DeliberativeBehavior] = []
		self._behavior_index: Dict[str, DeliberativeBehavior] = {}
		self._behavior_queue: Deque[str] = deque()
		self.first_behavior: Optional[str] = None
		self._first_behavior_done = False
		self.shared_state: Dict[str, Optional[str]] = {
			"customer_present": None,
			"table_empty": None,
			"last_speech_text": None,
		}
		self.ctx: Dict[str, object] = {"shared_state": self.shared_state}

		# Register behaviors and pick the first one to run at startup.
		self._register_default_behaviors()

		self.create_timer(0.1, self._reactive_step)

	def _register_default_behaviors(self) -> None:
		self.register_behavior(CheckCustomerBehavior())
		self.register_behavior(CheckEmptyTableBehavior())
		self.register_behavior(IntroduceTableBehavior())
		self.register_behavior(TakeOrderBehavior())
		self.register_behavior(MarkOrderReadyBehavior())
		self.register_behavior(CollectOrderBehavior())
		self.register_behavior(CheckCustomerNumberBehavior())
		self.first_behavior = "check_customer"
		self.set_priority_behavior("check_customer")
		self.get_logger().info("Registered sample customer-check behaviors.")

	def register_behavior(self, behavior: DeliberativeBehavior) -> None:
		self._behaviors.append(behavior)
		self._behavior_index[behavior.name] = behavior
		self.get_logger().info(f"Registered behavior: {behavior.name}")

	def set_priority_behavior(self, behavior_name: str) -> None:
		for behavior in self._behaviors:
			behavior.priority = 0.0

		selected = self._behavior_index.get(behavior_name)
		if selected is None:
			self.get_logger().warn(f"Cannot set priority behavior; unknown: {behavior_name}")
			return

		selected.priority = 1.0

	def _choose_highest_priority_behavior(self) -> Optional[str]:
		best_behavior_name: Optional[str] = None
		best_priority = -1.0

		for behavior in self._behaviors:
			try:
				priority = behavior.compute_priority()
			except Exception as exc:
				self.get_logger().error(f"Failed to compute priority for {behavior.name}: {exc}")
				continue

			if priority > best_priority:
				best_priority = priority
				best_behavior_name = behavior.name

		if best_priority <= 0:
			return None

		return best_behavior_name

	def _reactive_step(self) -> None:
		if not self._behavior_queue:
			if not self._first_behavior_done and self.first_behavior:
				self._behavior_queue.append(self.first_behavior)
				self._first_behavior_done = True
			else:
				next_behavior = self._choose_highest_priority_behavior()
				if next_behavior is not None:
					self._behavior_queue.append(next_behavior)

		if not self._behavior_queue:
			return

		behavior_name = self._behavior_queue.popleft()
		behavior = self._behavior_index.get(behavior_name)
		if behavior is None:
			self.get_logger().warn(f"Skipping unknown queued behavior: {behavior_name}")
			return

		self.ctx["selected_behavior"] = behavior_name
		try:
			behavior.run(self.ctx)
		except Exception as exc:
			self.get_logger().error(f"Behavior '{behavior.name}' failed: {exc}")


def build_nodes() -> List[Node]:
	coordinator = ReactiveCoordinator()
	nodes: List[Node] = [coordinator]
	nodes.append(ObjectDetection())
	nodes.append(SpeechToText())
	nodes.append(TextToSpeech())

	return nodes


def main(args=None) -> None:
	rclpy.init(args=args)
	nodes = build_nodes()
	executor = MultiThreadedExecutor()

	for node in nodes:
		executor.add_node(node)

	try:
		executor.spin()
	except KeyboardInterrupt:
		pass
	finally:
		for node in nodes:
			node.destroy_node()
		if rclpy.ok():
			rclpy.shutdown()


if __name__ == "__main__":
	main()
