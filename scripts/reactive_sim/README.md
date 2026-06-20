# Headless reactive simulation (no Docker, no ROS, no Firebase)

This package is a pure-Python, headless re-implementation of the **original
reactive (non-AIF) decision system** that runs on the TurtleBot4 in
`turtlebot4_ws/src/turtlebot4_steel_city_competition/`. It lets you run and
test the reactive arbitration logic on any machine — no robot, no ROS/rclpy,
no Docker, no Firestore credentials — and serves as a baseline for comparison
against the Active-Inference models documented in
[`docs/aif_architecture.md`](../../docs/aif_architecture.md).

## What it mirrors

| Real system (ROS) | Headless twin here |
| --- | --- |
| `src/turtlebot4_run.py` `ReactiveCoordinator` (10 Hz timer, argmax of `compute_priority`, first_behavior seed) | `coordinator.py` `ReactiveCoordinator` (tick loop, same argmax + seed) |
| `src/behaviors/behaviors.py` `DeliberativeBehavior` | `behaviors.py` `SimBehavior` |
| the 7 behaviour files in `src/behaviors/` | `behaviors.py` (7 twins, same names/ranks) |
| `behaviors/database_bridge.py` + `scripts/database/repository.py` (Firestore) | `sim_state.py` `SimRestaurant` (in-memory) |
| `behaviors/navigation_handoff.py` + ROS NavigationClient | `coordinator.drive_navigation` + `SimRobot` (teleport) |
| `actions/obj_detection.py` (vision) | `SimRestaurant.vision_*` stubs |
| `actions/speech_to_text` / `text_to_speech` / `llm.order_taker` | scripted, deterministic stubs |

## Behaviour parity

Same behaviour set, same `order` ranks, same arbitration (highest
`compute_priority`, requiring priority > 0; `check_customer` seeded first):

| behaviour | `order` rank | precondition gate |
| --- | --- | --- |
| `check_customer` | 1 | always (cooldown only) |
| `check_empty_table` | 1 | always (cooldown only) |
| `introduce_table` | 3 | a party is waiting **and** a table is free |
| `check_customer_number` | 4 | customers detected **and** not yet counted |
| `take_order` | 5 | an occupied table has not ordered |
| `mark_order_ready` | 5.5 | an order is placed but not ready (sim kitchen) |
| `collect_order` | 6 | a ready order awaits delivery |

The real behaviours gate on `time.monotonic() - last_run_time < wait_time`
(5 s at 10 Hz). For determinism this sim replaces wall-clock with the
coordinator's integer **tick** counter and a `cooldown` (in ticks), defaulting
to 0 so behaviours are eligible every tick — the practical steady state once
the 5 s window elapses. The gating *structure* is preserved and unit-tested.

## Run it

```bash
python scripts/reactive_sim/coordinator.py
```

A single customer is detected -> counted -> seated -> order taken -> kitchen
marks it ready -> order collected and delivered -> table check. The trace
prints which behaviour fires each tick and the resulting world state, and ends
with `reached delivered: True`.

## Test it

```bash
python -m pytest scripts/reactive_sim/test_reactive_sim.py -q
```

Covers: behaviour set and `order` ranks match the real system, registration
order matches `ReactiveCoordinator`, each `compute_priority` gate, the cooldown
gate, the `check_customer` first-behaviour seed, a single customer driven
end-to-end to delivered, and serving multiple customers.

## Parity gaps / stubs (honest notes)

* Vision, speech (STT/TTS) and the order-taking LLM are replaced by
  deterministic scripted stubs (`SimRestaurant.script_customer_arrival`,
  `scripted_order`). No NLP/LLM is exercised.
* Navigation is a teleport (`SimRobot.navigate_to`) using the same
  `shared_state` `target_location` / `next_target_location` handoff protocol as
  the real `navigation_handoff.drive_navigation`; no path planning or costmaps.
* `mark_order_ready` represents the kitchen as an immediate sim step (the real
  system also treats this as a simulated kitchen write).
* The wall-clock `wait_time` cooldown is modelled as a tick cooldown
  (default 0) for determinism, as described above.
* This is a single-robot, single-DB model; it does not simulate the multi-robot
  / collaborator entrance handoff beyond the `customers_waiting` counter.
