"""Headless test of the AIF<->ROS integration (aif_run.AIFBehaviorSelector).

No rclpy, no firebase, no robot: a mock restaurant DB feeds phase observations,
and we check the EFE selector drives EMPTY -> DELIVERED by choosing the service
actions. Run on Linux/WSL (JAX):
    python3 -m pytest scripts/aif/test_ros_integration.py -q
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "turtlebot4_ws" / "src" / "turtlebot4_steel_city_competition" / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "aif"))

import aif_run            # noqa: E402  imports without rclpy/firebase/jax
import generative_model as gm  # noqa: E402


class FakeTable:
    def __init__(self, status="empty", has_ordered=False, order_ready=False, order_delivered=False):
        self.status = status
        self.has_ordered = has_ordered
        self.order_ready = order_ready
        self.order_delivered = order_delivered


class FakeDB:
    def __init__(self):
        self.tables = {0: FakeTable()}

    def get_table(self, tid):
        return self.tables[int(tid)]

    def find_table_needing_order(self):
        for i, t in self.tables.items():
            if t.status != "empty" and not t.has_ordered:
                return i
        return None

    def find_table_with_ready_order(self):
        for i, t in self.tables.items():
            if t.order_ready and not t.order_delivered:
                return i
        return None

    def find_table_with_pending_order(self):
        return None


def test_observe_maps_restaurant_state_to_phase():
    sel = aif_run.AIFBehaviorSelector()
    db = FakeDB()
    ctx = {"shared_state": {"current_table_id": 0}}
    cases = {
        FakeTable(status="empty"): gm.EMPTY,
        FakeTable(status="occupied"): gm.SEATED,
        FakeTable(status="occupied", has_ordered=True): gm.ORDERED,
        FakeTable(status="occupied", has_ordered=True, order_ready=True): gm.READY,
        FakeTable(order_delivered=True): gm.DELIVERED,
    }
    for table, expected in cases.items():
        db.tables[0] = table
        assert sel.observe(db, ctx) == expected


def test_select_returns_valid_action():
    sel = aif_run.AIFBehaviorSelector()
    a, kind, target = sel.select(gm.EMPTY)
    assert 0 <= a < gm.N_ACTION
    assert kind in ("nav", "behavior", "noop")


def test_efe_selection_drives_to_delivered():
    """A mock restaurant that advances the table's phase when the EFE selector
    picks the corresponding service action -> the AIF coordinator should serve."""
    sel = aif_run.AIFBehaviorSelector()
    db = FakeDB()
    ctx = {"shared_state": {"current_table_id": 0}}
    t = db.tables[0]
    for _ in range(40):
        obs = sel.observe(db, ctx)
        a, _kind, _target = sel.select(obs)
        # apply the effect of the chosen service action to the mock restaurant
        if a == gm.SEAT:
            t.status = "occupied"
        elif a == gm.TAKE_ORDER and t.status == "occupied":
            t.has_ordered = True
        elif a == gm.MARK_READY and t.has_ordered:
            t.order_ready = True
        elif a == gm.DELIVER and t.order_ready:
            t.order_delivered = True
        if t.order_delivered:
            break
    assert t.order_delivered, "AIF coordinator did not drive the table to DELIVERED"
