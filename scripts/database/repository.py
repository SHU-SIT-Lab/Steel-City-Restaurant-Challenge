"""Firestore read/write helpers used by competition behaviors."""

from __future__ import annotations

from typing import Optional

from client import get_firestore_client
from config import collection_name, number_of_tables
from models import OrderStatus, RestaurantStateDocument, TableDocument, TableStatus

_STATE_DOC_ID = "current"


class RestaurantDatabase:
    """High-level API for table and entrance state in Firestore."""

    def __init__(self) -> None:
        self._db = get_firestore_client()
        self._tables = collection_name("tables")
        self._state = collection_name("restaurant_state")

    # --- seed / setup ---

    def seed_tables(self, table_count: Optional[int] = None) -> None:
        """Create empty table documents if they do not exist."""
        count = table_count if table_count is not None else number_of_tables()
        batch = self._db.batch()
        for table_id in range(count):
            ref = self._db.collection(self._tables).document(str(table_id))
            batch.set(
                ref,
                TableDocument(table_id=table_id).to_dict(),
                merge=True,
            )
        batch.commit()

    def seed_restaurant_state(self) -> None:
        ref = self._db.collection(self._state).document(_STATE_DOC_ID)
        ref.set(RestaurantStateDocument().to_dict(), merge=True)

    # --- tables ---

    def get_table(self, table_id: int) -> TableDocument:
        snap = self._db.collection(self._tables).document(str(table_id)).get()
        if not snap.exists:
            return TableDocument(table_id=table_id)
        return TableDocument.from_dict(snap.to_dict())

    def list_tables(self) -> list[TableDocument]:
        docs = self._db.collection(self._tables).stream()
        tables = [TableDocument.from_dict(doc.to_dict()) for doc in docs]
        return sorted(tables, key=lambda table: table.table_id)

    def update_table_status(self, table_id: int, status: TableStatus) -> None:
        ref = self._db.collection(self._tables).document(str(table_id))
        ref.set({"table_id": table_id, "status": status.value}, merge=True)

    def assign_table(self, table_id: int) -> None:
        ref = self._db.collection(self._tables).document(str(table_id))
        ref.set(
            {
                "table_id": table_id,
                "status": TableStatus.OCCUPIED.value,
                "has_ordered": False,
                "order_ready": False,
                "order_delivered": False,
                "order_items": [],
                "order_notes": "",
            },
            merge=True,
        )

    def save_order(
        self,
        table_id: int,
        items: list[str],
        notes: str = "",
    ) -> None:
        ref = self._db.collection(self._tables).document(str(table_id))
        ref.set(
            {
                "table_id": table_id,
                "status": TableStatus.OCCUPIED.value,
                "has_ordered": True,
                "order_items": items,
                "order_notes": notes,
                "order_ready": False,
                "order_delivered": False,
            },
            merge=True,
        )

    def mark_order_ready(self, table_id: int) -> None:
        ref = self._db.collection(self._tables).document(str(table_id))
        ref.update({"order_ready": True})

    def mark_order_delivered(self, table_id: int) -> None:
        ref = self._db.collection(self._tables).document(str(table_id))
        ref.set(
            {
                "table_id": table_id,
                "status": TableStatus.EMPTY.value,
                "has_ordered": False,
                "order_ready": False,
                "order_delivered": True,
                "order_items": [],
                "order_notes": "",
            },
            merge=True,
        )

    def clear_table(self, table_id: int) -> None:
        ref = self._db.collection(self._tables).document(str(table_id))
        ref.set(TableDocument(table_id=table_id).to_dict(), merge=True)

    # --- queries for behavior priorities ---

    def find_empty_table(self) -> Optional[int]:
        for table in self.list_tables():
            if table.status == TableStatus.EMPTY.value:
                return table.table_id
        return None

    def find_table_needing_order(self) -> Optional[int]:
        for table in self.list_tables():
            if (
                table.status == TableStatus.OCCUPIED.value
                and not table.has_ordered
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

    def has_ready_order(self) -> bool:
        return self.find_table_with_ready_order() is not None

    # --- restaurant / collaborator state ---

    def get_restaurant_state(self) -> RestaurantStateDocument:
        snap = (
            self._db.collection(self._state).document(_STATE_DOC_ID).get()
        )
        if not snap.exists:
            return RestaurantStateDocument()
        return RestaurantStateDocument.from_dict(snap.to_dict())

    def set_customers_waiting(self, count: int) -> None:
        ref = self._db.collection(self._state).document(_STATE_DOC_ID)
        ref.set({"customers_waiting": max(0, count)}, merge=True)

    def set_customers_detected_at_entrance(self, detected: bool) -> None:
        ref = self._db.collection(self._state).document(_STATE_DOC_ID)
        ref.set({"customers_detected_at_entrance": detected}, merge=True)

    def decrement_customers_waiting(self) -> None:
        state = self.get_restaurant_state()
        self.set_customers_waiting(max(0, state.customers_waiting - 1))

    def should_guide_customer_to_table(self) -> bool:
        state = self.get_restaurant_state()
        return state.customers_waiting > 0 and self.find_empty_table() is not None

    def customers_detected_at_entrance(self) -> bool:
        return self.get_restaurant_state().customers_detected_at_entrance
