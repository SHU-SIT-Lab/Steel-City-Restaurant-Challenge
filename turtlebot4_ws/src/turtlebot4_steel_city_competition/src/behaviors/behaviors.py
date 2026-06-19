#!/usr/bin/env python3

from __future__ import annotations

from abc import ABC, abstractmethod
import time
from typing import Any, Dict, List, Optional

_SHARED_OBJECT_DETECTION = None
_SHARED_SPEECH_TO_TEXT = None
_SHARED_TEXT_TO_SPEECH = None


def _get_shared_object_detection():
    global _SHARED_OBJECT_DETECTION

    if _SHARED_OBJECT_DETECTION is None:
        try:
            from actions.obj_detection import ObjectDetection
            _SHARED_OBJECT_DETECTION = ObjectDetection()
        except Exception as exc:
            print(f"[BEHAVIOR] ObjectDetection unavailable ({exc}).")
            _SHARED_OBJECT_DETECTION = False

    return None if _SHARED_OBJECT_DETECTION is False else _SHARED_OBJECT_DETECTION


def _get_shared_speech_to_text():
    global _SHARED_SPEECH_TO_TEXT

    if _SHARED_SPEECH_TO_TEXT is None:
        try:
            from actions.speech_to_text import SpeechToText
            _SHARED_SPEECH_TO_TEXT = SpeechToText()
        except Exception as exc:
            print(f"[BEHAVIOR] SpeechToText unavailable ({exc}).")
            _SHARED_SPEECH_TO_TEXT = False

    return None if _SHARED_SPEECH_TO_TEXT is False else _SHARED_SPEECH_TO_TEXT


def _get_shared_text_to_speech():
    global _SHARED_TEXT_TO_SPEECH

    if _SHARED_TEXT_TO_SPEECH is None:
        try:
            from actions.text_to_speech import TextToSpeech
            _SHARED_TEXT_TO_SPEECH = TextToSpeech()
        except Exception as exc:
            print(f"[BEHAVIOR] TextToSpeech unavailable ({exc}).")
            _SHARED_TEXT_TO_SPEECH = False

    return None if _SHARED_TEXT_TO_SPEECH is False else _SHARED_TEXT_TO_SPEECH


class DeliberativeBehavior(ABC):
    def __init__(self, name: str) -> None:
        self.name = name
        self.priority: float = 0.0
        self.planned_actions: List[Dict[str, Any]] = []
        self.last_run_time: float = 0.0

        self.object_detection = _get_shared_object_detection()
        self.speech_to_text = _get_shared_speech_to_text()
        self.text_to_speech = _get_shared_text_to_speech()

    def run(self, ctx: Any) -> None:
        self._bind_context(ctx)
        self._reset_state()
        self.plan(ctx)
        self.last_run_time = time.monotonic()
        self._reset_state()

    def _bind_context(self, ctx: Any) -> None:
        if ctx is None:
            return

        if isinstance(ctx, dict):
            for attr_name in ("object_detection", "vision", "obj_detection"):
                value = ctx.get(attr_name)
                if value is not None:
                    self.object_detection = value
                    break
            for attr_name in ("speech_to_text", "stt", "speech"):
                value = ctx.get(attr_name)
                if value is not None:
                    self.speech_to_text = value
                    break
            for attr_name in ("text_to_speech", "tts"):
                value = ctx.get(attr_name)
                if value is not None:
                    self.text_to_speech = value
                    break
        else:
            for attr_name in ("object_detection", "vision", "obj_detection"):
                value = getattr(ctx, attr_name, None)
                if value is not None:
                    self.object_detection = value
                    break

            for attr_name in ("speech_to_text", "stt", "speech"):
                value = getattr(ctx, attr_name, None)
                if value is not None:
                    self.speech_to_text = value
                    break

            for attr_name in ("text_to_speech", "tts"):
                value = getattr(ctx, attr_name, None)
                if value is not None:
                    self.text_to_speech = value
                    break

    @abstractmethod
    def plan(self, ctx: Any) -> None:
        pass

    @abstractmethod
    def compute_priority(self) -> float:
        pass

    def add_action(self, name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self.planned_actions.append({"name": name, "payload": payload or {}})

    def _reset_state(self) -> None:
        self.planned_actions.clear()
