"""Tools the waiter LLM can call (OpenAI function calling).

Each tool has two parts:
  1. A JSON *schema* in TOOLS — this is what we send to the model so it knows
     the tool exists and what arguments it takes.
  2. A Python *implementation* — run by execute_tool() when the model asks for it.

`navigate_to` calls the competition navigation ROS service when available.
"""

from __future__ import annotations

import order

_NAV_CLIENT = None
_ROS_INITIALIZED = False


def _call_navigation_service(destination: str) -> dict:
    global _NAV_CLIENT, _ROS_INITIALIZED

    try:
        import rclpy
        from rclpy.node import Node
        from turtlebot4_steel_city_competition.srv import NavigateToWaypoint
    except ImportError as exc:
        print(f"[NAV] ROS navigation unavailable ({exc}); pretending success.")
        return {"success": True, "destination": destination, "message": "ros_unavailable"}

    if not _ROS_INITIALIZED:
        rclpy.init()
        _ROS_INITIALIZED = True

    if _NAV_CLIENT is None:
        class _SpeechNavClient(Node):
            def __init__(self) -> None:
                super().__init__("speech_navigation_client")
                self._client = self.create_client(
                    NavigateToWaypoint,
                    "/navigation/navigate_to_waypoint",
                )

            def navigate(self, target: str) -> dict:
                if not self._client.wait_for_service(timeout_sec=5.0):
                    return {
                        "success": False,
                        "destination": target,
                        "message": "Navigation service unavailable.",
                    }
                request = NavigateToWaypoint.Request()
                request.destination = target
                future = self._client.call_async(request)
                rclpy.spin_until_future_complete(self, future)
                if not future.done() or future.result() is None:
                    return {
                        "success": False,
                        "destination": target,
                        "message": "Navigation service call failed.",
                    }
                response = future.result()
                return {
                    "success": response.success,
                    "destination": target,
                    "message": response.message,
                }

        _NAV_CLIENT = _SpeechNavClient()

    result = _NAV_CLIENT.navigate(destination)
    print(f"[NAV] navigate_to({destination!r}) -> {result}")
    return result


def navigate_to(destination: str) -> dict:
    """Drive the robot to a named location."""
    return _call_navigation_service(destination)


def record_order(items: list[str], notes: str = "") -> dict:
    """Persist a confirmed customer order via the order module."""
    order.update({"items": items, "notes": notes, "confirmed": True})
    saved = order.save_and_reset()
    return {"success": True, "order_id": saved["order_id"], "items": saved["items"]}


# --------------------------------------------------------------------------- #
#  Tool schemas (sent to the model)
# --------------------------------------------------------------------------- #

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate_to",
            "description": (
                "Drive the robot to a named location in the restaurant. "
                "Use this to go to a customer's table, the kitchen bar (barista), "
                "or the entrance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": (
                            "Where to go. Examples: 'table_1', 'table_2', "
                            "'barista', 'entrance'."
                        ),
                    }
                },
                "required": ["destination"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_order",
            "description": (
                "Save the customer's confirmed food and drink order. "
                "Call this ONLY after the customer has explicitly confirmed the order."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The list of ordered items, e.g. ['burger', 'cola'].",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Dietary needs or special requests. Empty string if none.",
                    },
                },
                "required": ["items"],
            },
        },
    },
]


# --------------------------------------------------------------------------- #
#  Dispatch
# --------------------------------------------------------------------------- #

_DISPATCH = {
    "navigate_to": navigate_to,
    "record_order": record_order,
}


def execute_tool(name: str, arguments: dict) -> dict:
    """Run the tool the model requested and return a JSON-serialisable result."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"success": False, "error": f"unknown tool: {name}"}
    try:
        return fn(**arguments)
    except Exception as e:
        return {"success": False, "error": str(e)}
