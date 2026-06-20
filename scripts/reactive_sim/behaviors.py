#!/usr/bin/env python3
"""Headless mirror of the seven competition behaviours.

Each class here is a plain-Python twin of the corresponding file under
``turtlebot4_ws/.../src/behaviors/``. We keep:

  * the same ``name``
  * the same ``order`` rank (the integer/float that scales priority)
  * the same ``compute_priority`` *gate* (precondition -> priority = order, else 0)
  * the same precondition -> effect on the world (SimRestaurant) and shared_state

Where the real behaviour calls ROS navigation / TTS / STT / vision / the LLM,
we substitute the deterministic ``SimRestaurant`` equivalents.

Cooldown note
-------------
The real behaviours gate on ``time.monotonic() - last_run_time < wait_time``
(``wait_time = 5.0`` s at a 10 Hz tick). For a *deterministic* headless sim we
replace wall-clock with the coordinator's integer tick counter and a
``cooldown`` expressed in ticks. ``cooldown`` defaults to 0 so a behaviour is
eligible on every tick (the practical steady state of the real system once the
5 s window elapses). The gate is preserved and configurable so the arbitration
structure matches the original exactly and can be unit-tested.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sim_state import SimRestaurant, TableStatus

# Waypoint names, mirroring database_bridge.py.
ENTRANCE_LOCATION = "entrance"
BARISTA_LOCATION = "barista"


def table_id_to_location(table_id: int) -> str:
    """Mirror of database_bridge.table_id_to_location."""
    return f"table_{table_id + 1}"


def set_navigation_target(
    state: Dict[str, Any],
    location_id: str,
    table_id: Optional[int] = None,
    next_location: Optional[str] = None,
) -> None:
    """Mirror of database_bridge.set_navigation_target (operates on shared_state)."""
    state["target_location"] = location_id
    if table_id is not None and location_id not in (
        ENTRANCE_LOCATION,
        BARISTA_LOCATION,
    ):
        state["current_table_id"] = table_id
    elif location_id in (ENTRANCE_LOCATION, BARISTA_LOCATION):
        state.pop("current_table_id", None)
        if table_id is not None:
            state["delivery_table_id"] = table_id
    if next_location is not None:
        state["next_target_location"] = next_location
    else:
        state.pop("next_target_location", None)


class SimBehavior:
    """Headless twin of DeliberativeBehavior (no ROS, no shared singletons)."""

    def __init__(self, name: str, order: float, db: SimRestaurant) -> None:
        self.name = name
        self.order = order
        self.priority: float = 0.0
        self.db = db
        self.cooldown: int = 0            # in ticks; 0 == eligible every tick
        self.last_run_tick: int = -(10 ** 9)
        self.current_tick: int = 0

    # The coordinator calls set_tick() before compute_priority() each step so
    # the cooldown gate is deterministic (replaces time.monotonic()).
    def set_tick(self, tick: int) -> None:
        self.current_tick = tick

    def _cooldown_active(self) -> bool:
        return (self.current_tick - self.last_run_tick) < self.cooldown

    def run(self, state: Dict[str, Any]) -> None:
        self.plan(state)
        self.last_run_tick = self.current_tick

    def plan(self, state: Dict[str, Any]) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def compute_priority(self) -> float:  # pragma: no cover - abstract
        raise NotImplementedError


class CheckCustomerBehavior(SimBehavior):
    """Detect customers at the entrance (vision) and record it. order = 1."""

    def __init__(self, db: SimRestaurant) -> None:
        super().__init__("check_customer", order=1, db=db)

    def plan(self, state: Dict[str, Any]) -> None:
        set_navigation_target(state, ENTRANCE_LOCATION)
        detected = state.get("customer_present")
        if detected is None:
            detected = self.db.vision_people_detected()
        state["customer_present"] = detected
        self.db.set_customers_detected_at_entrance(bool(detected))

    def compute_priority(self) -> float:
        if self._cooldown_active():
            self.priority = 0.0
        else:
            self.priority = 1.0 * self.order
        return self.priority


class CheckEmptyTableBehavior(SimBehavior):
    """Update occupancy of the table the robot is at (vision). order = 1."""

    def __init__(self, db: SimRestaurant) -> None:
        super().__init__("check_empty_table", order=1, db=db)

    def plan(self, state: Dict[str, Any]) -> None:
        table_id = state.get("current_table_id")
        if table_id is None:
            return
        table_id = int(table_id)
        table_location = table_id_to_location(table_id)

        if state.get("next_target_location") is not None:
            return
        if state.get("target_location") != table_location:
            set_navigation_target(state, table_location, table_id=table_id)
            return

        table_empty = state.get("table_empty")
        if table_empty is None:
            table_empty = self.db.vision_table_empty(table_id)
        if table_empty is None:
            return

        state["table_empty"] = table_empty
        status = TableStatus.EMPTY if table_empty else TableStatus.OCCUPIED
        self.db.update_table_status(table_id, status)

    def compute_priority(self) -> float:
        if self._cooldown_active():
            self.priority = 0.0
        else:
            self.priority = 1.0 * self.order
        return self.priority


class IntroduceTableBehavior(SimBehavior):
    """Seat a waiting customer at a free table. order = 3."""

    def __init__(self, db: SimRestaurant) -> None:
        super().__init__("introduce_table", order=3, db=db)
        self.guide_customer = 0

    def plan(self, state: Dict[str, Any]) -> None:
        if not self.db.should_guide_customer_to_table():
            return
        table_id = self.db.find_empty_table()
        if table_id is None:
            return

        table_location = table_id_to_location(table_id)
        set_navigation_target(
            state, ENTRANCE_LOCATION, next_location=table_location
        )
        state["assigned_table_id"] = table_id
        self.db.assign_table(table_id)
        self.db.decrement_customers_waiting()
        print(f"[INTRODUCE_TABLE] say: Please follow me to table {table_id + 1}.")
        print("[INTRODUCE_TABLE] say: Please have a seat. When you are ready, I will take your order.")

    def compute_priority(self) -> float:
        self.guide_customer = 1 if self.db.should_guide_customer_to_table() else 0
        if self._cooldown_active():
            self.priority = 0.0
        else:
            self.priority = 1.0 * self.order * self.guide_customer
        return self.priority


class CheckCustomerNumberBehavior(SimBehavior):
    """Ask how many are in the waiting party (speech). order = 4."""

    def __init__(self, db: SimRestaurant) -> None:
        super().__init__("check_customer_number", order=4, db=db)

    def plan(self, state: Dict[str, Any]) -> None:
        set_navigation_target(state, ENTRANCE_LOCATION)
        if not self.db.customers_detected_at_entrance():
            return

        print("[CHECK_CUSTOMER_NUMBER] say: Welcome! How many people are in your party?")
        # Speech stub: the scripted arrival's party size, default 1.
        arrivals = getattr(self.db, "_scripted_arrivals", [])
        customer_count = arrivals[0] if arrivals else 1

        state["customers_waiting"] = customer_count
        state["customer_present"] = customer_count > 0
        self.db.set_customers_waiting(customer_count)
        self.db.set_customers_detected_at_entrance(customer_count > 0)
        print(f"[CHECK_CUSTOMER_NUMBER] DB: customers_waiting={customer_count}")

    def compute_priority(self) -> float:
        state = self.db.get_restaurant_state()
        customers_detected = state.customers_detected_at_entrance
        already_counted = state.customers_waiting > 0

        if self._cooldown_active() or not customers_detected or already_counted:
            self.priority = 0.0
        else:
            self.priority = 1.0 * self.order
        return self.priority


class TakeOrderBehavior(SimBehavior):
    """Take a seated customer's order (speech + LLM). order = 5."""

    def __init__(self, db: SimRestaurant) -> None:
        super().__init__("take_order", order=5, db=db)

    def _get_table_awaiting_order(self) -> Optional[int]:
        return self.db.find_table_needing_order()

    def plan(self, state: Dict[str, Any]) -> None:
        table_id = self._get_table_awaiting_order()
        if table_id is None:
            return
        location_id = table_id_to_location(table_id)
        set_navigation_target(state, location_id, table_id=table_id)
        state["current_table_id"] = table_id

        # Speech/LLM stub: customer places the scripted order.
        order = self.db.scripted_order()
        items = [str(i).strip() for i in order.get("items", []) if str(i).strip()]
        notes = str(order.get("notes", "")).strip()
        if not items:
            print(f"[TAKE_ORDER] empty order for table {table_id}; not saving.")
            return
        self.db.save_order(table_id, items=items, notes=notes)
        print(f"[TAKE_ORDER] DB saved for table {table_id}: items={items} notes={notes!r}")
        print("[TAKE_ORDER] say: Thank you. I have sent your order to the kitchen.")

    def compute_priority(self) -> float:
        if self._cooldown_active():
            self.priority = 0.0
            return self.priority
        table_id = self._get_table_awaiting_order()
        self.priority = float(self.order) if table_id is not None else 0.0
        return self.priority


class MarkOrderReadyBehavior(SimBehavior):
    """Simulated kitchen marks a placed order ready. order = 5.5."""

    def __init__(self, db: SimRestaurant) -> None:
        super().__init__("mark_order_ready", order=5.5, db=db)

    def _get_table_with_pending_order(self) -> Optional[int]:
        return self.db.find_table_with_pending_order()

    def plan(self, state: Dict[str, Any]) -> None:
        table_id = self._get_table_with_pending_order()
        if table_id is None:
            return
        table = self.db.get_table(table_id)
        if table is not None and not table.order_ready:
            self.db.mark_order_ready(table_id)
            print(f"[MARK_ORDER_READY] DB updated: table {table_id} order_ready=true")
        state["order_ready_table_id"] = table_id

    def compute_priority(self) -> float:
        if self._cooldown_active():
            self.priority = 0.0
        else:
            has_pending = self._get_table_with_pending_order() is not None
            self.priority = 1.0 * self.order if has_pending else 0.0
        return self.priority


class CollectOrderBehavior(SimBehavior):
    """Collect a ready order from the barista and deliver it. order = 6."""

    def __init__(self, db: SimRestaurant) -> None:
        super().__init__("collect_order", order=6, db=db)
        self.order_ready = 0

    def plan(self, state: Dict[str, Any]) -> None:
        table_id = self.db.find_table_with_ready_order()
        if table_id is None:
            return
        table_location = table_id_to_location(table_id)
        current_target = state.get("target_location")

        # Leg 1: collect the order at the barista (until picked up). The
        # `collected_order` flag prevents bouncing back to the barista after we
        # have already picked up and headed to the table.
        if not state.get("collected_order"):
            if current_target != BARISTA_LOCATION:
                set_navigation_target(
                    state, BARISTA_LOCATION, table_id=table_id, next_location=table_location,
                )
                print(f"[COLLECT_ORDER] say: I am here to collect the order for table {table_id + 1}.")
                return
            state["collected_order"] = True          # picked up at the barista
            set_navigation_target(state, table_location, table_id=table_id)
            return

        # Leg 2: drive from barista to the customer's table.
        if current_target != table_location:
            set_navigation_target(state, table_location, table_id=table_id)
            return

        # Leg 3: hand over and mark delivered.
        print("[COLLECT_ORDER] say: Hello, I have your order from the kitchen.")
        self.db.mark_order_delivered(table_id)
        state["order_delivered"] = True
        state["collected_order"] = False
        state.pop("next_target_location", None)
        state.pop("delivery_table_id", None)
        print(f"[COLLECT_ORDER] DB: table {table_id} order_delivered=true")
        print("[COLLECT_ORDER] say: Thank you. Enjoy your meal!")

    def compute_priority(self) -> float:
        self.order_ready = 1 if self.db.has_ready_order() else 0
        if self._cooldown_active():
            self.priority = 0.0
        else:
            self.priority = 1.0 * self.order * self.order_ready
        return self.priority


def build_behaviors(db: SimRestaurant) -> List[SimBehavior]:
    """Register the seven behaviours in the same order as ReactiveCoordinator."""
    return [
        CheckCustomerBehavior(db),
        CheckEmptyTableBehavior(db),
        IntroduceTableBehavior(db),
        TakeOrderBehavior(db),
        MarkOrderReadyBehavior(db),
        CollectOrderBehavior(db),
        CheckCustomerNumberBehavior(db),
    ]
