#!/usr/bin/env python3
"""In-memory restaurant world that replaces Firestore + vision + speech.

This module is the headless, no-ROS/no-Docker/no-Firebase substitute for the
real system's data plane:

  * ``scripts/database/repository.py``    (Firestore-backed RestaurantDatabase)
  * ``scripts/database/models.py``         (TableDocument / RestaurantStateDocument)
  * ``actions/obj_detection.py``           (vision: people / table occupancy)
  * ``actions/speech_to_text.py`` etc.     (speech)

``SimRestaurant`` exposes exactly the query/mutate methods that the seven
competition behaviours call on ``RestaurantDatabase`` (find_empty_table,
find_table_needing_order, find_table_with_pending_order,
find_table_with_ready_order, has_ready_order, should_guide_customer_to_table,
set_customers_detected_at_entrance, ...), backed by plain Python state instead
of Firestore. Vision and speech are stubbed deterministically from that state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class TableStatus(str, Enum):
    """Mirror of ``scripts/database/models.TableStatus``."""

    EMPTY = "empty"
    OCCUPIED = "occupied"


@dataclass
class SimTable:
    """Mirror of ``scripts/database/models.TableDocument``."""

    table_id: int
    status: str = TableStatus.EMPTY.value
    has_ordered: bool = False
    order_ready: bool = False
    order_delivered: bool = False
    order_items: List[str] = field(default_factory=list)
    order_notes: str = ""


@dataclass
class SimRestaurantState:
    """Mirror of ``scripts/database/models.RestaurantStateDocument``."""

    customers_waiting: int = 0
    customers_detected_at_entrance: bool = False


class SimRestaurant:
    """Headless stand-in for Firestore + vision + speech.

    The method names and semantics deliberately match the real
    ``RestaurantDatabase`` so the simulated behaviours can call them verbatim.
    """

    def __init__(self, number_of_tables: int = 5) -> None:
        self.tables: List[SimTable] = [
            SimTable(table_id=i) for i in range(number_of_tables)
        ]
        self.state = SimRestaurantState()
        # Robot pose in the headless world (a waypoint name).
        self.robot_location: Optional[str] = None
        # Scripted "world": customers that will arrive at the entrance and the
        # fixed order they will place when asked. This is what makes vision and
        # speech deterministic without any sensors.
        self._scripted_arrivals: List[int] = []
        self._scripted_order_items: List[str] = ["burger", "fries"]
        self._scripted_order_notes: str = "no onions"

    # ------------------------------------------------------------------
    # Scripted world (replaces real sensors / customers)
    # ------------------------------------------------------------------
    def script_customer_arrival(self, party_size: int = 1) -> None:
        """Queue a customer party that vision will "see" at the entrance."""
        self._scripted_arrivals.append(max(1, int(party_size)))

    def scripted_order(self) -> dict:
        """The deterministic order a customer places (stand-in for the LLM)."""
        return {
            "items": list(self._scripted_order_items),
            "notes": self._scripted_order_notes,
        }

    # ------------------------------------------------------------------
    # Vision stubs (replace actions/obj_detection.ObjectDetection)
    # ------------------------------------------------------------------
    def vision_people_detected(self) -> bool:
        """True when a scripted party is currently at the entrance."""
        return len(self._scripted_arrivals) > 0

    def vision_table_empty(self, table_id: int) -> Optional[bool]:
        table = self.get_table(table_id)
        if table is None:
            return None
        return table.status == TableStatus.EMPTY.value

    # ------------------------------------------------------------------
    # Tables (mirror RestaurantDatabase)
    # ------------------------------------------------------------------
    def get_table(self, table_id: int) -> Optional[SimTable]:
        for table in self.tables:
            if table.table_id == table_id:
                return table
        return None

    def list_tables(self) -> List[SimTable]:
        return sorted(self.tables, key=lambda t: t.table_id)

    def update_table_status(self, table_id: int, status: TableStatus) -> None:
        table = self.get_table(table_id)
        if table is not None:
            table.status = status.value

    def assign_table(self, table_id: int) -> None:
        table = self.get_table(table_id)
        if table is None:
            return
        table.status = TableStatus.OCCUPIED.value
        table.has_ordered = False
        table.order_ready = False
        table.order_delivered = False
        table.order_items = []
        table.order_notes = ""

    def save_order(self, table_id: int, items: List[str], notes: str = "") -> None:
        table = self.get_table(table_id)
        if table is None:
            return
        table.status = TableStatus.OCCUPIED.value
        table.has_ordered = True
        table.order_items = list(items)
        table.order_notes = notes
        table.order_ready = False
        table.order_delivered = False

    def mark_order_ready(self, table_id: int) -> None:
        table = self.get_table(table_id)
        if table is not None:
            table.order_ready = True

    def mark_order_delivered(self, table_id: int) -> None:
        table = self.get_table(table_id)
        if table is None:
            return
        table.status = TableStatus.EMPTY.value
        table.has_ordered = False
        table.order_ready = False
        table.order_delivered = True
        table.order_items = []
        table.order_notes = ""

    # ------------------------------------------------------------------
    # Queries used by behaviour priorities (mirror RestaurantDatabase)
    # ------------------------------------------------------------------
    def find_empty_table(self) -> Optional[int]:
        for table in self.list_tables():
            if table.status == TableStatus.EMPTY.value:
                return table.table_id
        return None

    def find_table_needing_order(self) -> Optional[int]:
        for table in self.list_tables():
            if table.status == TableStatus.OCCUPIED.value and not table.has_ordered:
                return table.table_id
        return None

    def find_table_with_pending_order(self) -> Optional[int]:
        for table in self.list_tables():
            if (
                table.status == TableStatus.OCCUPIED.value
                and table.has_ordered
                and not table.order_ready
            ):
                return table.table_id
        return None

    def find_table_with_ready_order(self) -> Optional[int]:
        for table in self.list_tables():
            if (
                table.status == TableStatus.OCCUPIED.value
                and table.has_ordered
                and table.order_ready
                and not table.order_delivered
            ):
                return table.table_id
        return None

    def has_table_needing_order(self) -> bool:
        return self.find_table_needing_order() is not None

    def has_pending_order(self) -> bool:
        return self.find_table_with_pending_order() is not None

    def has_ready_order(self) -> bool:
        return self.find_table_with_ready_order() is not None

    # ------------------------------------------------------------------
    # Restaurant / entrance state (mirror RestaurantDatabase)
    # ------------------------------------------------------------------
    def get_restaurant_state(self) -> SimRestaurantState:
        return self.state

    def set_customers_waiting(self, count: int) -> None:
        self.state.customers_waiting = max(0, int(count))

    def set_customers_detected_at_entrance(self, detected: bool) -> None:
        self.state.customers_detected_at_entrance = bool(detected)

    def decrement_customers_waiting(self) -> None:
        self.set_customers_waiting(max(0, self.state.customers_waiting - 1))
        # When the last waiting party is seated, the entrance is clear and the
        # scripted arrival has been consumed.
        if self.state.customers_waiting == 0:
            self.state.customers_detected_at_entrance = False
            if self._scripted_arrivals:
                self._scripted_arrivals.pop(0)

    def should_guide_customer_to_table(self) -> bool:
        return (
            self.state.customers_waiting > 0 and self.find_empty_table() is not None
        )

    def customers_detected_at_entrance(self) -> bool:
        return self.state.customers_detected_at_entrance
