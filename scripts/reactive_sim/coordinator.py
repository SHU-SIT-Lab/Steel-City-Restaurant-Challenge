#!/usr/bin/env python3
"""Headless ReactiveCoordinator (no ROS Node, no rclpy timer).

This mirrors ``turtlebot4_run.ReactiveCoordinator`` exactly:

  * the same shared_state seed,
  * the same seven behaviours registered in the same order,
  * ``first_behavior = "check_customer"`` seeded once,
  * per tick: if the behaviour queue is empty, either seed the first behaviour
    or pick the highest-priority behaviour (argmax of ``compute_priority``,
    requiring priority > 0); then run one behaviour and drive navigation,
  * navigation handoff via shared_state ``target_location`` /
    ``next_target_location`` — here it just teleports a simulated robot.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Optional

try:  # allow both `python coordinator.py` and `import scripts.reactive_sim...`
    from behaviors import SimBehavior, build_behaviors
    from sim_state import SimRestaurant, TableStatus
except ImportError:  # pragma: no cover - package-import fallback
    from .behaviors import SimBehavior, build_behaviors
    from .sim_state import SimRestaurant, TableStatus


def drive_navigation(state: Dict[str, Any], robot: "SimRobot") -> None:
    """Headless mirror of navigation_handoff.drive_navigation."""
    target = state.get("target_location")
    if not target:
        return

    last_nav = state.get("_last_navigated_location")
    if last_nav != target:
        robot.navigate_to(target)
        state["_last_navigated_location"] = target
        return

    next_target = state.get("next_target_location")
    if next_target and last_nav != next_target:
        robot.navigate_to(next_target)
        state["target_location"] = next_target
        state["_last_navigated_location"] = next_target
        state.pop("next_target_location", None)


class SimRobot:
    """Trivial simulated mobile base: navigation just sets the location."""

    def __init__(self, db: SimRestaurant) -> None:
        self.db = db

    def navigate_to(self, location_id: str) -> bool:
        self.db.robot_location = location_id
        print(f"[NAV] robot arrived at {location_id!r}")
        return True


class ReactiveCoordinator:
    """Pure-Python twin of the ROS ReactiveCoordinator."""

    def __init__(self, db: Optional[SimRestaurant] = None) -> None:
        self.db = db if db is not None else SimRestaurant()
        self.robot = SimRobot(self.db)
        self.shared_state: Dict[str, Any] = {
            "customer_present": None,
            "table_empty": None,
            "last_speech_text": None,
            "target_location": None,
            "next_target_location": None,
            "_last_navigated_location": None,
        }
        self._behaviors: List[SimBehavior] = build_behaviors(self.db)
        self._behavior_index: Dict[str, SimBehavior] = {
            b.name: b for b in self._behaviors
        }
        self._behavior_queue: Deque[str] = deque()
        self.first_behavior: Optional[str] = "check_customer"
        self._first_behavior_done = False
        self.tick: int = 0

    def _choose_highest_priority_behavior(self) -> Optional[str]:
        """argmax over compute_priority, requiring priority > 0 (as in ROS)."""
        best_name: Optional[str] = None
        best_priority = -1.0
        for behavior in self._behaviors:
            behavior.set_tick(self.tick)
            try:
                priority = behavior.compute_priority()
            except Exception as exc:  # pragma: no cover
                print(f"[COORD] compute_priority failed for {behavior.name}: {exc}")
                continue
            if priority > best_priority:
                best_priority = priority
                best_name = behavior.name
        if best_priority <= 0:
            return None
        return best_name

    def step(self) -> Optional[str]:
        """One reactive tick. Returns the behaviour name that ran (or None)."""
        if not self._behavior_queue:
            if not self._first_behavior_done and self.first_behavior:
                self._behavior_queue.append(self.first_behavior)
                self._first_behavior_done = True
            else:
                next_behavior = self._choose_highest_priority_behavior()
                if next_behavior is not None:
                    self._behavior_queue.append(next_behavior)

        if not self._behavior_queue:
            self.tick += 1
            return None

        behavior_name = self._behavior_queue.popleft()
        behavior = self._behavior_index.get(behavior_name)
        if behavior is None:
            self.tick += 1
            return None

        behavior.set_tick(self.tick)
        behavior.run(self.shared_state)
        drive_navigation(self.shared_state, self.robot)
        self.tick += 1
        return behavior_name

    def run(self, steps: int = 60, verbose: bool = True) -> List[str]:
        """Drive the loop for ``steps`` ticks; return the trace of behaviours."""
        trace: List[str] = []
        for _ in range(steps):
            ran = self.step()
            trace.append(ran or "<idle>")
            if verbose:
                print(f"tick {self.tick - 1:>3}: {ran or '<idle>'}  | {self._state_summary()}")
        return trace

    def _state_summary(self) -> str:
        st = self.db.get_restaurant_state()
        parts = [
            f"waiting={st.customers_waiting}",
            f"detected={st.customers_detected_at_entrance}",
        ]
        for t in self.db.list_tables():
            flags = []
            if t.status == TableStatus.OCCUPIED.value:
                flags.append("occ")
            if t.has_ordered:
                flags.append("ordered")
            if t.order_ready:
                flags.append("ready")
            if t.order_delivered:
                flags.append("delivered")
            if flags:
                parts.append(f"T{t.table_id}[{','.join(flags)}]")
        return " ".join(parts)


def main() -> None:
    db = SimRestaurant(number_of_tables=5)
    db.script_customer_arrival(party_size=1)
    coord = ReactiveCoordinator(db)

    print("=== Headless reactive simulation: one customer, full service cycle ===")
    coord.run(steps=40, verbose=True)

    delivered = any(t.order_delivered for t in db.list_tables()) or any(
        t.status == TableStatus.EMPTY.value for t in db.list_tables()
    )
    any_delivered = any(t.order_delivered for t in db.list_tables())
    print("\n=== Result ===")
    print(f"reached delivered: {any_delivered}")


if __name__ == "__main__":
    main()
