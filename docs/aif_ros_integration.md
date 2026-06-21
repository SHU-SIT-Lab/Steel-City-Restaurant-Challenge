# Wiring the AIF agent into the robot (`turtlebot4_run.py`)

The active-inference agent can now **drive the real TurtleBot4** as a drop-in
alternative to the reactive coordinator. It selects the next action by **EFE
minimisation** and executes it through the **same behaviors and navigation** the
reactive system already uses — only the *selection* changes.

## Turn-key deploy (one command)

On the laptop, inside the ROS 2 Jazzy env (native Ubuntu 24.04 WSL distro or
Docker) and on the robot's Wi-Fi, from the repo root:

```bash
scripts/native/deploy.sh aif-law      # active inference + law-as-code
scripts/native/deploy.sh aif          # active inference, no law (FIFO)   [default]
scripts/native/deploy.sh reactive     # the original reactive coordinator
```

That single command **installs the AIF deps** (jax + pymdp), **builds the
workspace** (`colcon`), **configures the discovery server + FastDDS Wi-Fi
whitelist** for the robot (`ROBOT_IP` from `docker/nav.env`, default
`192.168.8.111`), **sets the brain flags**, prints a 5-second robot-topic sanity
check, and **launches**. Re-run knobs: `BUILD=0` (skip build), `DEPS=0` (skip pip),
`NO_LAUNCH=1` (set up only). Prereq: ROS 2 Jazzy installed
(`scripts/native/install_jazzy.sh`).

## How to run it (manual / under the hood)

`deploy.sh` just sets these env vars and launches. To do it by hand:

```bash
# in the ROS 2 Jazzy env (Docker or native), with jax+pymdp installed:
pip install -r scripts/aif/requirements.txt        # --break-system-packages on apt ROS
AIF_COORDINATOR=1 ros2 launch turtlebot4_steel_city_competition steel_city.launch.py
```

`turtlebot4_run.py` sees `AIF_COORDINATOR` and delegates to `aif_run.py`
(`AIFCoordinator`) instead of `ReactiveCoordinator`. Unset the var → the original
reactive behavior, byte-for-byte. You can also run the node directly:
`ros2 run turtlebot4_steel_city_competition aif_run.py`.

## Options (env-var flags)

Two flags, both **off by default** — so the default is reactive, and within AIF
the default is *no* law-as-code, exactly as requested:

| Flag | Unset (default) | Set (`=1`) |
| --- | --- | --- |
| `AIF_COORDINATOR` | **reactive** coordinator (`ReactiveCoordinator`) | **active-inference** coordinator (`AIFCoordinator`) |
| `AIF_LAW` | within AIF, pick the next table **FIFO** (no law) | within AIF, pick the next table by the **precedence law** (fairness / throughput / accessibility) |

`AIF_LAW` only matters when `AIF_COORDINATOR=1` (it tunes how the AIF coordinator
chooses *which* in-progress table to serve next). The three useful combinations:

```bash
# 1) default — reactive system, unchanged
ros2 launch turtlebot4_steel_city_competition steel_city.launch.py

# 2) active inference, no law (FIFO table choice)
AIF_COORDINATOR=1 ros2 launch turtlebot4_steel_city_competition steel_city.launch.py

# 3) active inference + law-as-code multi-customer ordering
AIF_COORDINATOR=1 AIF_LAW=1 ros2 launch turtlebot4_steel_city_competition steel_city.launch.py
```

When `AIF_LAW=1` and several tables are in progress, the node builds a `Customer`
per table (party size, wait time, accessibility flag), orders them with
`game_phases_multi.law_order` (busyness derived from how many tables are waiting),
and serves the top one — **locking onto it until it's delivered** so service never
thrashes mid-table.

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

- **Validated headless:** `scripts/aif/test_ros_integration.py` (6 tests) — the
  observation encoding, action selection, a full mock-restaurant run where the EFE
  selector drives a table **EMPTY → DELIVERED**, and the table-choice policy
  (FIFO by default; the law picks the higher-precedence table; the accessibility
  flag is a hard override). Both ROS files `py_compile`.
- **Not yet validated on hardware** — needs the robot + a colcon build of the
  workspace in a Jazzy env with jax/pymdp installed. JAX's first XLA compile at
  node start is slow (seconds–minutes); the agent is fine after that.
- **Scope** — each table is served via the table model; `AIF_LAW=1` adds the
  multi-customer precedence ordering. Still uses the **Firestore phase** as the
  observation (not yet the live vision/speech topics); a fully *joint* multi-table
  POMDP (serve A while B's food cooks) remains future work.

See [aif_architecture.md](aif_architecture.md) for where this sits, and
[run_without_docker.md](run_without_docker.md) / [OPERATIONS.md](OPERATIONS.md)
for standing up the Jazzy environment.
