#!/usr/bin/env python3
"""AIF coordinator — a drop-in alternative to ``ReactiveCoordinator`` that selects
the next action by **expected-free-energy minimisation** instead of
``argmax(order x precondition)``, then executes it through the SAME behaviors and
navigation the reactive system already uses.

Decision logic lives in ``AIFBehaviorSelector`` (no rclpy — testable headless);
``AIFCoordinator`` is the ROS node wrapper.

Run it instead of the reactive coordinator with the env var:
    AIF_COORDINATOR=1 ros2 launch turtlebot4_steel_city_competition steel_city.launch.py
or directly. Requires the AIF deps in the ROS Python env:
    pip install -r scripts/aif/requirements.txt        # jax + pymdp
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
# the AIF model + agent live in <repo>/scripts/aif
AIF_DIR = SRC_DIR.parents[3] / "scripts" / "aif"
if str(AIF_DIR) not in sys.path:
    sys.path.insert(0, str(AIF_DIR))

# Minimal pure helpers mirroring behaviors.database_bridge, defined inline so the
# selector imports without firebase/ROS (the node imports the real DB lazily).
ENTRANCE_LOCATION = "entrance"
BARISTA_LOCATION = "barista"


def shared_state(ctx: Any) -> Dict[str, Any]:
    if isinstance(ctx, dict):
        s = ctx.get("shared_state", {})
        if isinstance(s, dict):
            return s
    return {}


def table_id_to_location(table_id: int) -> str:
    return f"table_{table_id + 1}"


class AIFBehaviorSelector:
    """Encode the restaurant state as an AIF observation, pick an action by EFE,
    and map it to a behavior or a navigation target. Pure Python — no ROS — so the
    selection logic is unit-testable without the robot.

    The AIF action set (table model) maps to the existing primitives:
        GO_ENTRANCE/GO_TABLE/GO_BARISTA -> navigation targets
        SEAT -> introduce_table,  TAKE_ORDER -> take_order,
        MARK_READY -> mark_order_ready,  DELIVER -> collect_order,  WAIT -> no-op
    The perception behaviors (check_*) are replaced by the observation encoding:
    the agent *observes* the restaurant phase instead of running a look-behavior.
    """

    def __init__(self, use_law: bool = False) -> None:
        import generative_model as gm
        from aif_coordinator import ACTION_TO_TARGET, AIFWaiter

        self.gm = gm
        self.action_to_target = ACTION_TO_TARGET
        self.waiter = AIFWaiter()

        # Optional law-as-code: when several tables are in progress, a precedence
        # rule (fairness / throughput / accessibility) chooses which to serve next.
        self.use_law = use_law
        self._law_order = None
        self._customer_cls = None
        if use_law:
            try:
                from game_phases_multi import Customer, law_order

                self._customer_cls = Customer
                self._law_order = law_order
            except Exception:
                self.use_law = False
        self._tick = 0
        self._first_seen: Dict[int, int] = {}

    def observe(self, db: Any, ctx: Any) -> int:
        """Read the active table's service phase from the DB -> AIF phase observation."""
        gm = self.gm
        state = shared_state(ctx)
        table_id = self._active_table(db, state)
        if table_id is None:
            return gm.EMPTY  # nothing in progress: treat as "needs a customer"
        try:
            table = db.get_table(int(table_id))
        except Exception:
            return gm.EMPTY
        if getattr(table, "order_delivered", False):
            return gm.DELIVERED
        if getattr(table, "order_ready", False):
            return gm.READY
        if getattr(table, "has_ordered", False):
            return gm.ORDERED
        status = getattr(table, "status", "")
        if status and status != "empty":
            return gm.SEATED
        return gm.EMPTY

    def _active_table(self, db: Any, state: Dict[str, Any]) -> Optional[int]:
        """Which table to serve now. We *lock* onto a table until it's delivered
        (no mid-service thrashing); when free, pick the next one — by the
        precedence law if enabled, else FIFO (lowest table id)."""
        self._tick += 1
        locked = state.get("current_table_id")
        if locked is not None:
            return int(locked)  # serve this table until the node releases it (on DELIVERED)

        candidates = self._candidates(db)
        if not candidates:
            return None
        for tid in candidates:
            self._first_seen.setdefault(tid, self._tick)

        if self.use_law and self._law_order is not None and len(candidates) > 1:
            chosen = self._law_pick(db, candidates)
        else:
            chosen = min(candidates)  # FIFO
        state["current_table_id"] = chosen
        return chosen

    def _table_ids(self, db: Any):
        fn = getattr(db, "list_tables", None)
        if callable(fn):
            try:
                return [getattr(t, "table_id", i) for i, t in enumerate(fn())]
            except Exception:
                pass
        ids = []
        for i in range(8):  # fallback: probe a handful of ids
            try:
                if db.get_table(i) is not None:
                    ids.append(i)
            except Exception:
                continue
        return ids

    def _candidates(self, db: Any):
        """Table ids with a customer in progress (occupied, not yet delivered)."""
        out = []
        for tid in self._table_ids(db):
            try:
                t = db.get_table(int(tid))
            except Exception:
                continue
            if getattr(t, "order_delivered", False):
                continue
            status = getattr(t, "status", "")
            if status and status != "empty":
                out.append(int(tid))
        return out

    def _law_pick(self, db: Any, candidates) -> int:
        """Order in-progress tables by the precedence law; return the top table id."""
        custs = []
        for tid in candidates:
            t = db.get_table(int(tid))
            size = (getattr(t, "party_size", None)
                    or getattr(t, "number_of_customers", None) or 2)
            wait = getattr(t, "wait_minutes", None)
            if wait is None:
                wait = self._tick - self._first_seen.get(tid, self._tick)
            priority = bool(getattr(t, "priority", False)
                            or getattr(t, "accessibility", False))
            custs.append(self._customer_cls(name=str(tid), size=int(size),
                                            wait=int(wait), priority=priority))
        busy = min(1.0, (len(candidates) - 1) / 4.0)  # more waiting tables -> busier
        ordered = self._law_order(custs, busy=busy)
        return int(ordered[0].name)

    def select(self, obs_idx: int):
        """Return (action_index, kind, target) for the EFE-chosen action."""
        action = self.waiter.act(obs_idx)
        kind, target = self.action_to_target.get(action, ("noop", None))
        return action, kind, target


def _make_coordinator_class():
    """Defer rclpy import so this module is importable (and testable) without ROS."""
    import rclpy
    from rclpy.node import Node

    from behaviors.behaviors import (
        _get_shared_object_detection,
        _get_shared_speech_to_text,
        _get_shared_text_to_speech,
    )
    from behaviors.collect_order_behavior import CollectOrderBehavior
    from behaviors.database_bridge import RestaurantDatabase, set_navigation_target
    from behaviors.introduce_table_behavior import IntroduceTableBehavior
    from behaviors.mark_order_ready_behavior import MarkOrderReadyBehavior
    from behaviors.navigation_handoff import drive_navigation
    from behaviors.take_order_behavior import TakeOrderBehavior

    class AIFCoordinator(Node):
        """EFE-driven coordinator: same ctx / behaviors / navigation as
        ReactiveCoordinator, but the *selection* is active inference."""

        def __init__(self) -> None:
            super().__init__("aif_coordinator")
            self.db = RestaurantDatabase()
            self.shared_state: Dict[str, Any] = {
                "customer_present": None,
                "table_empty": None,
                "last_speech_text": None,
                "target_location": None,
                "next_target_location": None,
                "_last_navigated_location": None,
            }
            self.ctx: Dict[str, Any] = {
                "shared_state": self.shared_state,
                "object_detection": _get_shared_object_detection(),
                "database": self.db,
                "restaurant_database": self.db,
                "speech_to_text": _get_shared_speech_to_text(),
                "text_to_speech": _get_shared_text_to_speech(),
            }
            # behaviors reused for EXECUTION of the service actions
            self._behaviors = {
                "introduce_table": IntroduceTableBehavior(),
                "take_order": TakeOrderBehavior(),
                "mark_order_ready": MarkOrderReadyBehavior(),
                "collect_order": CollectOrderBehavior(),
            }
            import os

            use_law = bool(os.environ.get("AIF_LAW"))
            self.selector = AIFBehaviorSelector(use_law=use_law)
            mode = "law-as-code multi-customer ordering" if use_law else "FIFO (no law)"
            self.get_logger().info(f"AIF coordinator ready (EFE selection; table choice: {mode}).")
            # one deliberate decision per second (AIF inference + behavior execution)
            self.create_timer(1.0, self._aif_step)

        def _resolve_nav(self, target: Optional[str]) -> Optional[str]:
            if target == "entrance":
                return ENTRANCE_LOCATION
            if target == "barista":
                return BARISTA_LOCATION
            if target == "table":
                tid = self.shared_state.get("current_table_id", 0) or 0
                return table_id_to_location(int(tid))
            return target

        def _aif_step(self) -> None:
            try:
                obs = self.selector.observe(self.db, self.ctx)
                if obs == self.selector.gm.DELIVERED:
                    # table served -> release the lock so the next one is chosen
                    self.shared_state.pop("current_table_id", None)
                action, kind, target = self.selector.select(obs)
                self.ctx["selected_action"] = action
                if kind == "nav":
                    loc = self._resolve_nav(target)
                    if loc:
                        set_navigation_target(self.ctx, loc)
                elif kind == "behavior":
                    behavior = self._behaviors.get(target)
                    if behavior is not None:
                        behavior.run(self.ctx)
                drive_navigation(self.ctx, self.ctx.get("navigation"))
            except Exception as exc:  # pragma: no cover
                self.get_logger().error(f"AIF step failed: {exc}")

    return AIFCoordinator


def build_nodes():
    AIFCoordinator = _make_coordinator_class()
    coordinator = AIFCoordinator()
    nodes = [coordinator]
    try:
        from navigation.navigation_client import NavigationClient

        nav_client = NavigationClient()
        coordinator.ctx["navigation"] = nav_client
        nodes.append(nav_client)
        coordinator.get_logger().info("NavigationClient connected.")
    except Exception as exc:  # pragma: no cover
        coordinator.get_logger().warn(f"NavigationClient unavailable ({exc}); stub navigation.")
    return nodes


def main(args=None) -> None:
    import rclpy
    from rclpy.executors import MultiThreadedExecutor

    rclpy.init(args=args)
    executor = MultiThreadedExecutor()
    nodes = build_nodes()
    for node in nodes:
        executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        for node in nodes:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
