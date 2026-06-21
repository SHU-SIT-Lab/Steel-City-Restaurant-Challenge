"""Firestore document shapes used by the restaurant challenge."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TableStatus(str, Enum):
    EMPTY = "empty"
    OCCUPIED = "occupied"


class OrderStatus(str, Enum):
    NONE = "none"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    READY = "ready"
    DELIVERED = "delivered"


@dataclass
class TableDocument:
    table_id: int
    status: str = TableStatus.EMPTY.value
    has_ordered: bool = False
    order_ready: bool = False
    order_delivered: bool = False
    order_items: list[str] = field(default_factory=list)
    order_notes: str = ""
    occupied_since: datetime | None = None
    order_placed_at: datetime | None = None
    order_ready_at: datetime | None = None
    order_delivered_at: datetime | None = None
    last_updated: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TableDocument":
        return cls(
            table_id=int(data.get("table_id", 0)),
            status=data.get("status", TableStatus.EMPTY.value),
            has_ordered=bool(data.get("has_ordered", False)),
            order_ready=bool(data.get("order_ready", False)),
            order_delivered=bool(data.get("order_delivered", False)),
            order_items=list(data.get("order_items", [])),
            order_notes=str(data.get("order_notes", "")),
            occupied_since=data.get("occupied_since"),
            order_placed_at=data.get("order_placed_at"),
            order_ready_at=data.get("order_ready_at"),
            order_delivered_at=data.get("order_delivered_at"),
            last_updated=data.get("last_updated"),
        )


@dataclass
class RestaurantStateDocument:
    """Shared state for collaborator robots (entrance queue)."""

    customers_waiting: int = 0
    customers_detected_at_entrance: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RestaurantStateDocument":
        return cls(
            customers_waiting=int(data.get("customers_waiting", 0)),
            customers_detected_at_entrance=bool(
                data.get("customers_detected_at_entrance", False)
            ),
        )
