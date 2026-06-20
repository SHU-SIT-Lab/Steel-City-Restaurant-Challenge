"""Execute navigation legs published by behaviors via shared_state."""

from __future__ import annotations

from typing import Any, Optional


def drive_navigation(ctx: Any, navigation: Any) -> None:
	"""Navigate to target_location and optional next_target_location in shared_state."""
	if navigation is None or not isinstance(ctx, dict):
		return

	state = ctx.get("shared_state")
	if not isinstance(state, dict):
		return

	target = state.get("target_location")
	if not target:
		return

	last_nav = state.get("_last_navigated_location")
	if last_nav != target:
		if _navigate(navigation, target):
			state["_last_navigated_location"] = target
		return

	next_target = state.get("next_target_location")
	if next_target and last_nav != next_target:
		if _navigate(navigation, next_target):
			state["target_location"] = next_target
			state["_last_navigated_location"] = next_target
			state.pop("next_target_location", None)


def _navigate(navigation: Any, location_id: str) -> bool:
	for method_name in ("navigate_to", "go_to", "go_to_location", "send_goal", "navigate"):
		method = getattr(navigation, method_name, None)
		if callable(method):
			try:
				return bool(method(location_id))
			except Exception as exc:
				print(f"[NAV_HANDOFF] navigation via {method_name} failed ({exc}).")
				return False

	print(f"[NAV_HANDOFF] no navigation method for {location_id!r}.")
	return False
