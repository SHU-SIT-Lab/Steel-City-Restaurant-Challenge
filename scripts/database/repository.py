"""Firestore read/write helpers used by competition behaviors."""

from __future__ import annotations

from typing import Optional

from client import get_firestore_client
from config import collection_name, number_of_tables
from google.cloud.firestore import SERVER_TIMESTAMP
from menu_catalog import (
    ALL_MENU_ITEMS,
    MENU_BY_ID,
    MenuDocument,
    normalize_menu_reference,
    resolve_order_items_to_vision_counts,
)
from models import OrderStatus, RestaurantStateDocument, TableDocument, TableStatus

_STATE_DOC_ID = "current"


class RestaurantDatabase:
    """High-level API for table and entrance state in Firestore."""

    def __init__(self) -> None:
        self._db = get_firestore_client()
        self._tables = collection_name("tables")
        self._state = collection_name("restaurant_state")
        self._menu = collection_name("menu")
        self._menu_cache: dict[str, MenuDocument] | None = None

    # --- seed / setup ---

    def seed_menu(self) -> None:
        """Create or refresh set-menu reference documents in Firestore."""
        for menu in ALL_MENU_ITEMS:
            ref = self._db.collection(self._menu).document(menu.id)
            data = menu.to_dict()
            data["updated_at"] = SERVER_TIMESTAMP
            if not ref.get().exists:
                data["created_at"] = SERVER_TIMESTAMP
            ref.set(data, merge=True)
        self._menu_cache = None

    def list_menus(self, *, refresh: bool = False) -> list[MenuDocument]:
        if not refresh and self._menu_cache is not None:
            return list(self._menu_cache.values())

        docs = self._db.collection(self._menu).stream()
        menus = [
            MenuDocument.from_dict(doc.to_dict())
            for doc in docs
            if doc.id and doc.to_dict().get("id")
        ]
        if not menus:
            menus = list(ALL_MENU_ITEMS)

        self._menu_cache = {menu.id: menu for menu in menus}
        return menus

    def get_menu(self, menu_id: str) -> MenuDocument | None:
        normalized = normalize_menu_reference(menu_id)
        if normalized is None:
            return None

        if self._menu_cache and normalized in self._menu_cache:
            return self._menu_cache[normalized]

        snap = self._db.collection(self._menu).document(normalized).get()
        if snap.exists:
            menu = MenuDocument.from_dict(snap.to_dict())
            if self._menu_cache is None:
                self._menu_cache = {}
            self._menu_cache[normalized] = menu
            return menu

        return MENU_BY_ID.get(normalized)

    def normalize_order_menus(self, items: list[str]) -> list[str]:
        """Validate and canonicalize customer order entries to set-menu ids."""
        normalized_items: list[str] = []
        for raw_item in items:
            menu_id = normalize_menu_reference(raw_item)
            if menu_id is None:
                raise ValueError(f"unknown menu item: {raw_item!r}")

            menu = self.get_menu(menu_id) or MENU_BY_ID.get(menu_id)
            if menu is None:
                raise ValueError(f"unknown menu item: {raw_item!r}")
            if menu.category != "set_menu":
                raise ValueError(
                    f"{menu.name} is a condiment; add it in order notes, not as a menu."
                )
            if menu_id not in normalized_items:
                normalized_items.append(menu_id)
        return normalized_items

    def resolve_order_vision_counts(self, order_items: list[str]) -> dict[str, int]:
        menus = {menu.id: menu for menu in self.list_menus()}
        counts = resolve_order_items_to_vision_counts(order_items, menus=menus)
        return dict(counts)

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

    def reset_all_tables(self, table_count: Optional[int] = None) -> None:
        """Clear every table document back to empty defaults."""
        count = table_count if table_count is not None else number_of_tables()
        batch = self._db.batch()
        for table_id in range(count):
            ref = self._db.collection(self._tables).document(str(table_id))
            batch.set(
                ref,
                {
                    **TableDocument(table_id=table_id).to_dict(),
                    "occupied_since": None,
                    "order_placed_at": None,
                    "order_ready_at": None,
                    "order_delivered_at": None,
                    "last_updated": SERVER_TIMESTAMP,
                },
            )
        batch.commit()

    def reset_restaurant_state(
        self,
        *,
        customers_waiting: int = 0,
        customers_detected_at_entrance: bool = False,
    ) -> None:
        """Replace entrance queue state (does not merge stale fields)."""
        ref = self._db.collection(self._state).document(_STATE_DOC_ID)
        ref.set(
            RestaurantStateDocument(
                customers_waiting=max(0, customers_waiting),
                customers_detected_at_entrance=customers_detected_at_entrance,
            ).to_dict()
        )

    def prepare_demo_entrance(self, customers_waiting: int = 1) -> None:
        """Set entrance state so introduce_table can run in tests."""
        self.reset_restaurant_state(
            customers_waiting=max(1, customers_waiting),
            customers_detected_at_entrance=True,
        )

    def reset_for_demo(self, customers_waiting: int = 1) -> None:
        """Clear all tables and seed a waiting customer at the entrance."""
        self.reset_all_tables()
        self.prepare_demo_entrance(customers_waiting=customers_waiting)

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

    def list_table_ids(self) -> list[int]:
        return [table.table_id for table in self.list_tables()]

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
                "occupied_since": SERVER_TIMESTAMP,
                "order_placed_at": None,
                "order_ready_at": None,
                "order_delivered_at": None,
                "last_updated": SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def save_order(
        self,
        table_id: int,
        items: list[str],
        notes: str = "",
    ) -> None:
        menu_ids = self.normalize_order_menus(items)
        ref = self._db.collection(self._tables).document(str(table_id))
        ref.set(
            {
                "table_id": table_id,
                "status": TableStatus.OCCUPIED.value,
                "has_ordered": True,
                "order_items": menu_ids,
                "order_notes": notes,
                "order_ready": False,
                "order_delivered": False,
                "order_placed_at": SERVER_TIMESTAMP,
                "order_ready_at": None,
                "order_delivered_at": None,
                "last_updated": SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def mark_order_ready(self, table_id: int) -> None:
        ref = self._db.collection(self._tables).document(str(table_id))
        ref.update(
            {
                "order_ready": True,
                "order_ready_at": SERVER_TIMESTAMP,
                "last_updated": SERVER_TIMESTAMP,
            }
        )

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
                "occupied_since": None,
                "order_placed_at": None,
                "order_ready_at": None,
                "order_delivered_at": SERVER_TIMESTAMP,
                "last_updated": SERVER_TIMESTAMP,
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

    def find_table_with_pending_order(self) -> Optional[int]:
        """Return a table that ordered but is not marked ready yet."""
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
