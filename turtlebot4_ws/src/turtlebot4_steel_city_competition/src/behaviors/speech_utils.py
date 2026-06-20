"""Shared speech, navigation, and context binding for deliberative behaviors."""

from __future__ import annotations

import re
from typing import Any, Optional

_WORD_NUMBERS = {
	"zero": 0,
	"one": 1,
	"two": 2,
	"three": 3,
	"four": 4,
	"five": 5,
	"six": 6,
	"seven": 7,
	"eight": 8,
	"nine": 9,
	"ten": 10,
}


def bind_context_interfaces(behavior: Any, ctx: Any) -> None:
	"""Wire speech, navigation, and database from coordinator ctx."""
	if ctx is None or not isinstance(ctx, dict):
		return

	for name in ("speech_to_text", "stt", "speech"):
		value = ctx.get(name)
		if value is not None:
			behavior.speech_to_text = value
			break

	for name in ("text_to_speech", "tts"):
		value = ctx.get(name)
		if value is not None:
			behavior.text_to_speech = value
			break

	for name in ("navigation", "navigator", "nav"):
		value = ctx.get(name)
		if value is not None:
			behavior.navigation = value
			break

	for name in ("database", "db", "restaurant_database"):
		value = ctx.get(name)
		if value is not None:
			behavior.db = value
			break


def say(behavior: Any, text: str, *, tag: str) -> None:
	print(f"[{tag}] say: {text!r}")
	speaker = getattr(behavior, "text_to_speech", None)
	if speaker is None:
		print(f"[{tag}] text_to_speech not wired; printed only.")
		return

	for method_name in ("generate_speech", "generate_and_publish_speech", "speak"):
		method = getattr(speaker, method_name, None)
		if callable(method):
			try:
				method(text)
				return
			except Exception as exc:
				print(f"[{tag}] TTS method {method_name} failed ({exc}).")
				return

	print(f"[{tag}] no compatible TTS method found; printed only.")


def ask(
	behavior: Any,
	*,
	tag: str,
	timeout: float = 8.0,
	prompt: Optional[str] = None,
) -> Optional[str]:
	if prompt:
		say(behavior, prompt, tag=tag)

	listener = getattr(behavior, "speech_to_text", None)
	if listener is None:
		print(f"[{tag}] speech_to_text not wired.")
		return None

	getter = getattr(listener, "get_next_utterance", None)
	if not callable(getter):
		print(f"[{tag}] speech_to_text has no get_next_utterance(timeout).")
		return None

	try:
		return getter(timeout)
	except Exception as exc:
		print(f"[{tag}] speech request failed ({exc}).")
		return None


def navigate(behavior: Any, location_id: str, *, tag: str) -> bool:
	navigator = getattr(behavior, "navigation", None)
	if navigator is None:
		print(
			f"[{tag}] navigation not wired; "
			f"pretending navigation to {location_id!r} succeeded."
		)
		return True

	for method_name in ("navigate_to", "go_to", "go_to_location", "send_goal", "navigate"):
		method = getattr(navigator, method_name, None)
		if callable(method):
			try:
				return bool(method(location_id))
			except Exception as exc:
				print(f"[{tag}] navigation via {method_name} failed ({exc}).")
				return False

	print(f"[{tag}] navigator has no compatible method for {location_id!r}.")
	return False


def parse_party_size(text: Optional[str], default: int = 1) -> int:
	if not text:
		return default

	match = re.search(r"\d+", text.strip())
	if match:
		return max(1, min(int(match.group()), 20))

	for word, value in _WORD_NUMBERS.items():
		if re.search(rf"\b{word}\b", text.strip().lower()):
			return max(1, value)

	return default


def vision_people_detected(object_detection: Any) -> bool:
	if object_detection is None:
		return False

	getter = getattr(object_detection, "get_people_detected", None)
	if callable(getter):
		return (getter() or 0) > 0

	return bool(getattr(object_detection, "customer_present", False))


def vision_table_empty(object_detection: Any, table_id: int) -> Optional[bool]:
	if object_detection is None:
		return None

	object_detection.current_table_id = table_id
	free = object_detection.get_free_table() if callable(getattr(object_detection, "get_free_table", None)) else 0
	occupied = (
		object_detection.get_occupied_table()
		if callable(getattr(object_detection, "get_occupied_table", None))
		else 0
	)
	free = free or 0
	occupied = occupied or 0

	if occupied > 0:
		return False
	if free > 0:
		return True
	return None
