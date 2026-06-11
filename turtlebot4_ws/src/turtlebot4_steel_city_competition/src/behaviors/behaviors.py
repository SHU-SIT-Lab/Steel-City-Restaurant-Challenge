#!/usr/bin/env python3

from __future__ import annotations

from abc import ABC, abstractmethod
import time
from typing import Any, Dict, List, Optional

from actions.obj_detection import ObjectDetection
from actions.speech_to_text import SpeechToText
from actions.text_to_speech import TextToSpeech


class DeliberativeBehavior(ABC):
	"""Parent class for planning-style behaviors.

	Child classes compute priority and implement planning in ``plan``.
	The base class only manages lifecycle and lightweight reset.
	"""

	def __init__(self, name: str) -> None:
		self.name = name
		self.priority: float = 0.0
		self.planned_actions: List[Dict[str, Any]] = []
		self.last_run_time: float = 0.0
		self.object_detection = ObjectDetection()
		self.speech_to_text = SpeechToText()
		self.text_to_speech = TextToSpeech()

	def run(self, ctx: Any) -> None:
		self._reset_state()
		self.plan(ctx)
		self.last_run_time = time.monotonic()
		self._reset_state()

	@abstractmethod
	def plan(self, ctx: Any) -> None:
		"""Build the plan for this behavior."""

	@abstractmethod
	def compute_priority(self) -> float:
		"""Return the priority to use for this behavior."""

	def add_action(self, name: str, payload: Optional[Dict[str, Any]] = None) -> None:
		self.planned_actions.append({"name": name, "payload": payload or {}})

	def _reset_state(self) -> None:
		self.planned_actions.clear()
