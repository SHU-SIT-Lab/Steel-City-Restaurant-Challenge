"""Order state tracking — saves confirmed orders to orders.json."""

import json
import os
from datetime import datetime

ORDERS_FILE = os.path.join(os.path.dirname(__file__), "orders.json")

_current_order: dict = {}
_order_counter: int = 0


def update(order_dict: dict) -> None:
    """Update the in-progress order with latest data from the LLM."""
    global _current_order
    _current_order = order_dict
    items = order_dict.get("items", [])
    confirmed = order_dict.get("confirmed", False)
    notes = order_dict.get("notes", "")

    status = "CONFIRMED" if confirmed else "pending"
    print(f"[ORDER] {status} — items: {items}" + (f"  notes: {notes}" if notes else ""))


def is_confirmed() -> bool:
    return bool(_current_order.get("confirmed", False))


def save_and_reset() -> dict:
    """Persist the confirmed order to orders.json and return it."""
    global _current_order, _order_counter
    _order_counter += 1

    record = {
        "order_id": _order_counter,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "items": _current_order.get("items", []),
        "notes": _current_order.get("notes", ""),
    }

    # Append to orders.json
    existing = []
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

    existing.append(record)
    with open(ORDERS_FILE, "w") as f:
        json.dump(existing, f, indent=2)

    print(f"[ORDER] Saved order #{_order_counter} -> {ORDERS_FILE}")
    _current_order = {}
    return record
