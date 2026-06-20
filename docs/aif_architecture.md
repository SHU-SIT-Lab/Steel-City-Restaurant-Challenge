# Active Inference: architecture & integration

How the active-inference (AIF) subsystem is built, how its pieces relate, and how
it sits inside the rest of the Steel City / EMSRC robot system. This is the map;
the per-piece docs are linked at the bottom.

> **Just want to run something?** See **[how_to_run.md](how_to_run.md)** — every
> piece, its command, and what to expect.

## 1. The one-sentence idea

The competition robot already has a decision core — `ReactiveCoordinator` in
`turtlebot4_run.py` — that picks the next behavior by `argmax(order × precondition)`.
The AIF subsystem is a **drop-in replacement for that decision core**: instead of a
hand-tuned priority arbiter, the robot selects actions by **minimising expected
free energy (EFE)** over a generative model of the service task. Everything else
(navigation, vision, speech, the database, the webapp) is unchanged.

In AIF terms the old arbiter is a degenerate EFE (`argmax` = the `γ→∞` limit with
no epistemic term); AIF generalises it so that **information-gathering** and
**goal-seeking** are traded off automatically.

## 2. Where it sits (layered architecture)

AIF replaces **only the task/decision layer**. It does *not* do metric navigation
or perception — it consumes their outputs and emits high-level decisions.

```
                 ┌──────────────────────────────────────────────┐
   TASK LAYER    │  AIF agent  (or the old ReactiveCoordinator)  │   <-- AIF lives here
  (what to do)   │  infer_states → infer_policies(EFE) → action  │
                 └───────────────┬───────────────┬──────────────┘
                                 │ decision      │ belief Q(s)
        observations ↑           ▼               ▼
        (phase/loc)   │   set_navigation_target  Firestore (shared blackboard)
                      │          │                     ▲
   ┌──────────────────┴───┐   ┌──▼─────────────────┐   │ read/write
   │  PERCEPTION          │   │  METRIC NAVIGATION  │   │
   │  vision (YOLO),      │   │  Nav2 + AMCL +      │   │  webapp, collaborator
   │  speech (STT/LLM/TTS)│   │  online furniture   │   │  robots see the same state
   │  → phase evidence    │   │  costmap (OAK-D)    │   │
   └──────────────────────┘   └─────────────────────┘   │
            robot sensors  ◄────────  TurtleBot4  ───────┘   (ROS 2 Jazzy)
```

Two layers, kept separate on purpose:

| Layer | Owner | Job |
| --- | --- | --- |
| **Task / decision** | **AIF agent** (this subsystem) | *what* to do next: greet, go to table, take order, verify, serve, return |
| **Metric navigation** | **Nav2** (+ the OAK-D furniture costmap) | *how* to get there: path planning, obstacle/furniture avoidance |

When the AIF agent decides `GO_TABLE`, it writes a waypoint via
`set_navigation_target` and Nav2 drives there — the **same handoff the reactive
behaviors already use** (`navigation_handoff.py` → `/navigation/navigate_to_waypoint`).

## 3. The generative model

A discrete POMDP, built on the JAX `pymdp.agent.Agent` (same stack as
`leader_follower_aif`). Components:

- **Hidden state `s`** — `(phase, location)`. The *phase* is the service-cycle
  stage; *location* is the robot station. The state is what the agent infers; it
  is **not** observed directly.
- **Observations `o`** — a **location-gated, noisy** `phase_evidence` modality
  with an `AMBIGUOUS` outcome. A phase reads sharply only at its station; off-station
  it reads `AMBIGUOUS`. This is what makes the `GO_*` actions *epistemic* (the
  robot must move to perceive). Grounded in real sensors: vision → detect/seat,
  speech/LLM → order, the counter/tray check → verify, nav/AMCL → location.
- **Actions `u`** — the service primitives (greet, take order, verify, serve,
  return) + navigation (`GO_*`). Precondition-gated: a service action only
  advances the phase at the right station.
- **Preferences `C`** — over observations, shaped so the **completed cycle
  dominates** (the agent acts to finish service / maximise rulebook score) with a
  gentle gradient to climb and `AMBIGUOUS` dispreferred.
- **Law-as-code seam** — norms compile into `(C, E, B-mask)`: soft preferences
  (`C`), policy priors (`E`), and hard transition masks (`B`). A precision knob
  trades strict-vs-flexible compliance. See §5.

Full rationale: **[aif_design.md](aif_design.md)**.

## 4. The variants (one model, four lenses)

| Piece | Files | What it adds | PR |
| --- | --- | --- | --- |
| **Table model** | `generative_model.py`, `aif_coordinator.py` | the core EFE agent + epistemic observations; serves one table | #17 |
| **Epistemic test** | `epistemic_test.py` | proves "look when unsure" emerges (a cue-resolving T-maze) | #17 |
| **Law-as-code** | `law_as_code.py` | a rule compiled into the model, reshaped by context (party size, wait, busyness) | #18 |
| **Game phases V1** | `game_phases.py` | the model recast over the **6 EMSRC competition phases**, no law | #19 |
| **Game phases V2** | `game_phases_multi.py` | **multi-customer**: a law orders customers, AIF serves each | #20 |

All share the **same observation design** (location-gated noisy `phase_evidence`)
and the same EFE machinery. The game-phases models ground the phases and the
preference `C` in the **rulebook score sheet** (Phase 1→6, the +200 multi-customer
bonus). See **[aif_game_phases.md](aif_game_phases.md)**.

## 5. Hierarchical structure (multi-customer)

Real service is two levels, which V2 makes explicit:

```
  HIGH (law-as-code):  order the waiting customers
       precedence/fairness rule, reshaped by party size, wait time, busyness,
       accessibility  →  a serving order
                          │  for each customer, in order:
  LOW  (active inf.):   ▼  serve through the 6 phases by EFE minimisation
```

This composes the law-as-code (who) with the AIF service agent (how) and keeps the
problem tractable — a single flat multi-table POMDP would blow up the policy space.
The full *joint/interleaved* version (serve A's order while B's food cooks) is a
research item (needs sophisticated inference).

## 6. Integration points with the existing system

The AIF agent is a `ReactiveCoordinator` look-alike, so the rest of the stack is
untouched:

- **Same action handoff** — actions map to `set_navigation_target` / `say` /
  `ask` / DB writes (the `ACTION_TO_TARGET` table in `aif_coordinator.py`), the
  same primitives the 7 behaviors use.
- **Firestore is `Q(s)`** — the agent seeds its belief from the Firestore document
  and writes it back, so the webapp and collaborator robots share one belief. The
  DB is the multi-agent blackboard, now interpreted probabilistically.
- **Observations from real perception** — YOLO vision (customer present / table
  state), STT+LLM (order), the tray check, AMCL (location) feed the
  `phase_evidence` observation.
- **Runtime** — the agent is a Python/JAX module; on the robot it runs as an
  `rclpy` node inside **ROS 2 Jazzy** (Docker, *or* the native WSL path — see
  [run_without_docker.md](run_without_docker.md)). The decision *logic* needs
  neither Docker nor ROS, which is why the models are validated headless on Linux/WSL.

## 7. Status (honest)

**Done & validated (headless):** the core EFE agent; epistemic value (looks when
unsure); law-as-code (soft `C` + hard `B-mask` + precision knob, reshaped by
context); the 6 game phases (V1) and multi-customer law ordering (V2); all under
partial (location-gated) observation; a Docker-free runtime (Docker, or native
Jazzy in WSL Ubuntu 24.04).

**Not done yet:** wiring the agent into `turtlebot4_run.py` as a live `rclpy`
node (the ROS integration); grounding observations in the *actual* vision/speech
topics; the full joint/interleaved multi-table POMDP; on-robot evaluation;
pytest. The numeric preferences are first-pass.

## 8. Document map

| Topic | Doc |
| --- | --- |
| AIF design & rationale | [aif_design.md](aif_design.md) |
| Game phases (V1/V2) | [aif_game_phases.md](aif_game_phases.md) |
| The behavior system it replaces | [task_manager.md](task_manager.md) |
| Navigation layer (Nav2) | [navigation.md](navigation.md) |
| Online furniture costmap | [furniture_costmap.md](furniture_costmap.md) |
| Docker-free Jazzy runtime | [run_without_docker.md](run_without_docker.md) |
| Operator runbook | [OPERATIONS.md](OPERATIONS.md) |

### Code
`scripts/aif/` — `generative_model.py`, `aif_coordinator.py` (table model);
`game_phases.py`, `game_phases_multi.py` (competition phases); `law_as_code.py`
(norms); `epistemic_test.py`, `evaluate.py` (validation); `requirements.txt`.
