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
RETURN@counter). The correct Phase 1→6 order *emerges* from EFE minimisation.

## Observations (location-gated, like PR #17)

The agent does **not** see its state directly. There is one **noisy,
location-gated** observation modality — `phase_evidence` ∈ {DETECTED, SEATED,
ORDERED, VERIFIED, SERVED, STANDBY, **AMBIGUOUS**}:

- at a phase's **station** the phase reads sharply (`build_A(sharp=0.9)`);
- **off-station** it reads `AMBIGUOUS`.

So the robot can only resolve a phase where it is observable (detect at the
entrance, confirm the order at the table, check the tray at the counter, ...). The
`GO_*` actions therefore earn **information gain** — the agent must *move to
perceive*. This is the same epistemic structure as the PR #17 table model (an
earlier version used a fully-observed identity likelihood, which made the
epistemic term ~0; this restores it).

**Preferences `C`** are a monotonic gradient over the phase observations with a
**dominant terminal preference** for STANDBY, so the agent does not *farm* a
high-scoring mid-phase observation under the finite horizon (re-observing VERIFIED
forever would otherwise beat progressing through the AMBIGUOUS dip). The reported
*score* still uses the rulebook points.

## V1 result

```
python scripts/aif/game_phases.py
```
The agent completes the full six-phase cycle in 9 steps, scoring 1200/1200 (base):
`GREET, GO_TABLE, TAKE_ORDER, GO_COUNTER, VERIFY, GO_TABLE, SERVE, GO_COUNTER, RETURN`.

## V2 result — multi-customer + law-as-code

```
python scripts/aif/game_phases_multi.py
```
A precedence/fairness **law** (party size, wait time, busyness, accessibility)
orders the waiting customers; **AIF serves each through all six phases**. The
same law gives different orders as context changes:

```
quiet kitchen (fairness)      order: A -> C -> B    score 3800 (3x1200 + 200 bonus)
slammed kitchen (throughput)  order: B -> A -> C    score 3800
B flagged priority            order: B -> A -> C    score 3800
```

Busyness flips fairness↔throughput; an accessibility flag is a hard priority.
Each served customer is a full 1200-point six-phase cycle, plus the rulebook's
**+200 "serve multiple customers in a single run"** bonus.

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
- The agent operates under **partial observability** (location-gated noisy
  `phase_evidence`), so it must navigate to perceive — see *Observations* above.
  The trace shows `AMBIGUOUS` readings whenever the robot is off a phase's station.
