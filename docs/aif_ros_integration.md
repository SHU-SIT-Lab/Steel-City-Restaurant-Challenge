# Wiring the AIF agent into the robot (`turtlebot4_run.py`)

The active-inference agent can now **drive the real TurtleBot4** as a drop-in
alternative to the reactive coordinator. It selects the next action by **EFE
minimisation** and executes it through the **same behaviors and navigation** the
reactive system already uses — only the *selection* changes.

## How to run it

Set one env var; everything else is unchanged:

```bash
# in the ROS 2 Jazzy env (Docker or native), with jax+pymdp installed:
pip install -r scripts/aif/requirements.txt        # --break-system-packages on apt ROS
AIF_COORDINATOR=1 ros2 launch turtlebot4_steel_city_competition steel_city.launch.py
```

`turtlebot4_run.py` sees `AIF_COORDINATOR` and delegates to `aif_run.py`
(`AIFCoordinator`) instead of `ReactiveCoordinator`. Unset the var → the original
reactive behavior, byte-for-byte. You can also run the node directly:
`ros2 run turtlebot4_steel_city_competition aif_run.py`.

## What it does each tick

```
  read restaurant state (Firestore)  ──►  AIF observation (service phase)
                                            │  AIFWaiter.act(obs)  → action (min EFE)
                                            ▼
        action ──► nav target (GO_*)  OR  a service behavior (SEAT/TAKE_ORDER/…)
                                            │
                                            ▼
                          set_navigation_target / behavior.run(ctx) → drive_navigation
```

- **Observation** — the active table's phase is read from the DB
  (`empty → EMPTY`, `occupied → SEATED`, `has_ordered → ORDERED`,
  `order_ready → READY`, `order_delivered → DELIVERED`). The **perception
  behaviors** (`check_*`) are *replaced by this observation* — the agent
  *observes* the phase instead of running a look-behavior.
- **Action → execution** (`ACTION_TO_TARGET` in `aif_coordinator.py`):
  `GO_ENTRANCE/GO_TABLE/GO_BARISTA → navigation`, and
  `SEAT → introduce_table`, `TAKE_ORDER → take_order`,
  `MARK_READY → mark_order_ready`, `DELIVER → collect_order` — the **real
  behaviors**, so all the LLM/speech/nav/DB work is reused unchanged.

## Design

`aif_run.py` keeps the decision logic in **`AIFBehaviorSelector`** (no rclpy — so
it's unit-testable headless) and wraps it in **`AIFCoordinator(Node)`**, which
mirrors `ReactiveCoordinator`'s ctx / behaviors / navigation. The agent ticks once
a second (each tick is a deliberate EFE inference + a behavior execution).

## Status (honest)

- **Validated headless:** `scripts/aif/test_ros_integration.py` (3 tests) — the
  observation encoding, action selection, and a full mock-restaurant run where the
  EFE selector drives a table **EMPTY → DELIVERED**. Both ROS files `py_compile`.
- **Not yet validated on hardware** — needs the robot + a colcon build of the
  workspace in a Jazzy env with jax/pymdp installed. JAX's first XLA compile at
  node start is slow (seconds–minutes); the agent is fine after that.
- **Single-table for now** — uses the table model. Multi-customer ordering (the
  law-as-code in V2) is not yet wired into the live node.

See [aif_architecture.md](aif_architecture.md) for where this sits, and
[run_without_docker.md](run_without_docker.md) / [OPERATIONS.md](OPERATIONS.md)
for standing up the Jazzy environment.
