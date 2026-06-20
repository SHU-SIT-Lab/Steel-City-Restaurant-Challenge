# AIF over the EMSRC competition phases (Docker-free)

An active-inference agent structured around the **six EMSRC Restaurant Challenge
phases**, with preferences grounded in the **rulebook points**. Pure Python/JAX —
**no Docker, no ROS** to run the decision logic. Two versions:

- **V1 — `scripts/aif/game_phases.py`** — the six phases, no law-as-code.
- **V2 — `scripts/aif/game_phases_multi.py`** *(branch `aif-game-phases-law`)* —
  multiple customers, with a law-as-code rule ordering who is served.

## The six phases (from the score sheet)

| Phase | Reached by | Rulebook points |
| --- | --- | --- |
| DETECTED | start (detect a calling customer) | 100 |
| SEATED | GREET at the entrance (welcome + seat) | +200 |
| ORDERED | TAKE_ORDER at the table | +250 |
| VERIFIED | VERIFY at the counter (tell barman + check tray) | +275 |
| SERVED | SERVE at the table | +250 |
| STANDBY | RETURN to the counter | +125 |
| | **full cycle** | **1200 base** |

The state is `(phase, location)`; phase-advancing actions only fire at the right
station (GREET@entrance, TAKE_ORDER@table, VERIFY@counter, SERVE@table,
RETURN@counter). The preference vector **C is the cumulative rulebook points**, so
the EFE-minimising agent literally acts to maximise its expected competition
score, and the correct Phase 1→6 order *emerges*.

## V1 result

```
python scripts/aif/game_phases.py
```
The agent completes the full six-phase cycle in 9 steps, scoring 1200/1200 (base):
`GREET, GO_TABLE, TAKE_ORDER, GO_COUNTER, VERIFY, GO_TABLE, SERVE, GO_COUNTER, RETURN`.

## Run

Linux/WSL (fast JAX XLA), deps in `scripts/aif/requirements.txt`:
```bash
pip install -r scripts/aif/requirements.txt
python scripts/aif/game_phases.py
```

## Notes
- This is the *decision core*. To drive the real TurtleBot4 it runs as an
  `rclpy` node inside a **ROS 2 Jazzy** environment (native Ubuntu 24.04, no
  Docker — see the host setup docs).
- Fully observed model (phase + location known); the epistemic-value machinery is
  demonstrated separately on the table model.
