# How to run everything (a pick-up guide)

Every decision-logic piece in this repo runs **headless — no Docker, no ROS, no
robot** (pure Python / JAX). Only driving the *real* TurtleBot4 needs ROS 2 Jazzy
(Docker or native). This guide lets anyone pick up any single piece and run it.

For *what* these pieces are and how they fit together, read
**[aif_architecture.md](aif_architecture.md)** first; this doc is the *how to run*.

## The two decision cores

The robot's "what do I do next" brain comes in two interchangeable forms:

- **Reactive** (`scripts/reactive_sim/`) — the original hand-coded
  `argmax(order × precondition)` arbiter over the 7 behaviors.
- **Active inference** (`scripts/aif/`) — an EFE-minimising agent over the same
  task. Adds: perception under uncertainty (epistemic value), and law-as-code.

Run them side by side with `scripts/compare/compare.py`.

## One-time setup

Run on **Linux or WSL** (JAX's XLA compiles slowly on native Windows).

```bash
# JAX/pymdp for the AIF pieces (numpy alone is enough for the reactive sim):
pip install -r scripts/aif/requirements.txt
# for the test suites:
pip install pytest
```

## Run any piece

| Want to… | Command | You'll see |
| --- | --- | --- |
| **Run the reactive system** | `python scripts/reactive_sim/coordinator.py` | one customer served to *delivered* via the 7 behaviors |
| **Run the AIF over the 6 phases** (V1) | `python scripts/aif/game_phases.py` | the EFE agent serves the full 6-phase cycle (1200/1200); `AMBIGUOUS` readings show it navigating to perceive |
| **Run AIF multi-customer + law** (V2) | `python scripts/aif/game_phases_multi.py` | a law orders 3 customers (context-sensitive), AIF serves each; 3800 pts |
| **Run the AIF table model** | `python scripts/aif/aif_coordinator.py` | the original AIF agent serves one table EMPTY→DELIVERED |
| **See "look when unsure"** | `python scripts/aif/epistemic_test.py` | the agent checks a cue board only when uncertain |
| **See law-as-code reshape by context** | `python scripts/aif/law_as_code.py` *(PR #18)* | a precedence rule, soft/hard + precision knob, reshaped by party/wait/busyness |
| **Evaluate the AIF over many seeds** | `python scripts/aif/evaluate.py` | success rate + steps-to-serve, matched vs noisy |
| **Compare reactive vs AIF** | `python scripts/compare/compare.py` | both on the same scenarios + a conceptual table |

## Run the tests

```bash
python3 -m pytest scripts/aif/test_e2e.py -q          # AIF: 15 tests (structural + full agent runs)
python3 -m pytest scripts/reactive_sim/ -q            # reactive sim: 14 tests
python3 -m pytest scripts/compare/test_compare.py -q  # the comparison
```

## Drive the real TurtleBot4 (needs ROS 2 Jazzy)

The decision cores above are the *brain*; to move the robot they run as ROS nodes
in a Jazzy environment. Two ways, both reusing the same networking fixes:

- **Docker:** `./docker/run_container_wsl.sh` (WSL) — see [OPERATIONS.md](OPERATIONS.md).
- **No Docker (native):** a WSL Ubuntu 24.04 distro with apt ros-jazzy — see
  [run_without_docker.md](run_without_docker.md).

Either way, then `ros2 topic list` should show `/scan`, `/oakd/*`, `/battery_state`.
If "ping works but ROS sees nothing", read [troubleshooting_dds_wsl.md](troubleshooting_dds_wsl.md).

## Where each piece lives (PRs, until merged to main)

| Piece | Path | PR |
| --- | --- | --- |
| AIF core (table model) + design | `scripts/aif/generative_model.py`, `aif_coordinator.py`, `epistemic_test.py`, `evaluate.py` | #17 |
| Law-as-code | `scripts/aif/law_as_code.py` | #18 |
| AIF game phases V1 | `scripts/aif/game_phases.py` | #19 |
| AIF game phases V2 + e2e tests | `scripts/aif/game_phases_multi.py`, `test_e2e.py` | #20 |
| Docker-free Jazzy runtime | `scripts/native/`, `docs/run_without_docker.md` | #21 |
| Reactive (non-AIF) sim | `scripts/reactive_sim/` | #22 |
| This guide + comparison | `docs/how_to_run.md`, `scripts/compare/` | (this branch) |

## Doc map
[aif_architecture.md](aif_architecture.md) (architecture & integration) ·
[aif_design.md](aif_design.md) (AIF rationale) ·
[aif_game_phases.md](aif_game_phases.md) (the phase models) ·
[task_manager.md](task_manager.md) (the reactive system it mirrors) ·
[OPERATIONS.md](OPERATIONS.md) (operator runbook).
