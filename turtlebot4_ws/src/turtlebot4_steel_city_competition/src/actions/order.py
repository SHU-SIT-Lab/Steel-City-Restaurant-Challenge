#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

ORDERS_FILE = Path(__file__).resolve().parent / "orders.json"

_current_order: dict[str, Any] = {}
_order_counter: int = 0


def update(order_dict: dict[str, Any]) -> None:
    global _current_order

    _current_order = {
        "confirmed": bool(order_dict.get("confirmed", False)),
        "items": list(order_dict.get("items", [])),
        "notes": str(order_dict.get("notes", "")),
    }

    items = _current_order.get("items", [])
    confirmed = _current_order.get("confirmed", False)
    notes = _current_order.get("notes", "")

    status = "CONFIRMED" if confirmed else "pending"
    print(f"[ORDER] {status} — items: {items}" + (f" notes: {notes}" if notes else ""))


def is_confirmed() -> bool:
    return bool(_current_order.get("confirmed", False))


def get_current_order() -> dict[str, Any]:
    return dict(_current_order)


def reset() -> None:
    global _current_order
    _current_order = {}


def _load_existing_orders() -> list[dict[str, Any]]:
    if not ORDERS_FILE.exists():
        return []

    try:
        with ORDERS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except json.JSONDecodeError:
        return []


def _save_orders(records: list[dict[str, Any]]) -> None:
    with ORDERS_FILE.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)


def save_and_reset(table_id: int | None = None) -> dict[str, Any]:
    global _current_order, _order_counter

    _order_counter += 1

    record: dict[str, Any] = {
        "order_id": _order_counter,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "table_id": table_id,
        "items": list(_current_order.get("items", [])),
        "notes": str(_current_order.get("notes", "")),
    }

    existing = _load_existing_orders()
    existing.append(record)
    _save_orders(existing)

    print(f"[ORDER] Saved order #{_order_counter} -> {ORDERS_FILE}")

    _current_order = {}

    return record


def save_order_for_table(table_id: int, items: list[Any], notes: str = "") -> dict[str, Any]:
    global _current_order

    _current_order = {
        "confirmed": True,
        "items": list(items),
        "notes": notes,
    }

    return save_and_reset(table_id=table_id)
