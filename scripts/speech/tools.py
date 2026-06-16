"""Tools the waiter LLM can call (OpenAI function calling).

Each tool has two parts:
  1. A JSON *schema* in TOOLS — this is what we send to the model so it knows
     the tool exists and what arguments it takes.
  2. A Python *implementation* — run by execute_tool() when the model asks for it.

NAVIGATION IS JUST A PLACEHOLDER. 
`navigate_to` always returns success. When the real navigation module is pushed,
replace the body of `_navigate_placeholder` with a call into it — the schema and
the rest of the pipeline do not need to change.
"""

import order

# --------------------------------------------------------------------------- #
#  Robot action implementations
# --------------------------------------------------------------------------- #

def _navigate_placeholder(destination: str) -> dict:
    """Stand-in for the navigation module. Always succeeds.

    Swap this for the real navigation call when available, e.g.:
        from navigation import go_to
        return {"success": go_to(destination)}
    """
    print(f"[NAV] (placeholder) Navigating to {destination!r} ... success")
    return {"success": True, "destination": destination}


def navigate_to(destination: str) -> dict:
    """Drive the robot to a named location."""
    return _navigate_placeholder(destination)


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
                            "'kitchen_bar', 'entrance'."
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
