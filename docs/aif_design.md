# Active Inference reformulation of the waiter behaviors

Reframe the `ReactiveCoordinator` (hand-coded `order × precondition`, argmax) as a
**single active-inference agent** that selects actions by minimising expected
free energy (EFE). The restaurant workflow becomes a generative model; the seven
behaviors become the agent's actions; the `self.order` ranks become a preference
vector; and **law-as-code** norms enter as priors/masks on the policy space.

This is a drop-in alternative to `turtlebot4_run.py::ReactiveCoordinator`: same
ROS interface (writes `shared_state["target_location"]`, calls speech/vision/DB),
different decision core. See `scripts/aif/`.

## Implementation status (validated)

Built on the **JAX `pymdp.agent.Agent`** (same stack as `leader_follower_aif`)
and validated headless: the agent drives one table EMPTY → DELIVERED in the
optimal 6 steps (`SEAT, GO_TABLE, TAKE_ORDER, MARK_READY, GO_BARISTA, DELIVER`)
by EFE minimisation alone — the serve order *emerges*, it is not the `self.order`
ranks. Run `scripts/aif/aif_coordinator.py` (deps in `scripts/aif/requirements.txt`).

Two findings worth recording:

- **Planning horizon matters.** With `policy_len=1` the agent dithers, because the
  payoff (a `DELIVERED` observation) is only reachable several steps ahead and —
  with location-gated observations — is not visible one step out. `policy_len=4`
  (deterministic selection) recovers the optimal policy. This is the pragmatic
  cost of the epistemic structure: looking is only worthwhile if the planner can
  see far enough to use what it learns.
- **Run on Linux/WSL.** JAX's first XLA compile is impractically slow on native
  Windows Python (minutes, CPU-pegged); it is seconds on Linux. The miniforge
  base env and WSL both already have `jax` + `pymdp`.

## Why AIF is the *right* generalisation here

The current arbiter is, in AIF terms, a **degenerate EFE with γ→∞**:

| Reactive system | Active inference |
| --- | --- |
| `compute_priority() = order × precondition` | EFE per policy `G(π) = pragmatic + epistemic` |
| `argmax` over behaviors | `q(π) = σ(−γ·G)`, then sample (γ→∞ ⇒ argmax) |
| `self.order` ranks (hand-tuned) | preference vector **C** (log-preferred observations) |
| Firestore document = ground truth | Firestore document = persisted posterior **Q(s)** |
| vision/speech reads = facts | vision/speech = noisy **observations** updating Q(s) |
| `check_*` behaviors (look) vs `take/collect` (act) | **epistemic** vs **pragmatic** value — arbitrated automatically |

The key payoff: the `check_customer` / `check_empty_table` behaviors exist purely
to *reduce uncertainty*. In the reactive system their priority is hand-set; in
AIF they are selected exactly when the **information gain** about table phase /
occupancy outweighs the pragmatic pull toward serving — i.e. "look when unsure,
act when confident" falls out of the maths instead of being tuned.

## Generative model (per table; restaurant = factorised product)

Model one table's service lifecycle, then run N independent (optionally coupled)
copies — one per competition table — sharing the robot-location factor.

### Hidden state factors `s`
- **phase** ∈ {`EMPTY`, `SEATED`, `ORDERED`, `READY`, `DELIVERED`} — the service
  lifecycle. Maps 1:1 to the Firestore `TableDocument` fields
  (`status`/`has_ordered`/`order_ready`/`order_delivered`).
- **robot_loc** ∈ {`ENTRANCE`, `TABLE`, `BARISTA`} — controllable; gates which
  observations are informative (you only resolve table occupancy *at* the table).

### Observation modalities `o`
- **phase_evidence** ∈ {EMPTY…DELIVERED, `AMBIGUOUS`} — vision/speech/DB readout
  of phase. The **A** matrix is *location-gated*: sharp (low entropy) when
  `robot_loc` matches the phase's relevant station, near-uniform otherwise. This
  is what creates epistemic value for the `go_*`/`check_*` actions.

### Control / actions `u` (the seven behaviors)
| Action | Behavior | Type | Effect (B) |
| --- | --- | --- | --- |
| `GO_ENTRANCE` | check_customer | epistemic | robot_loc→ENTRANCE; observe entrance |
| `COUNT_PARTY` | check_customer_number | epistemic+ | resolve party size |
| `SEAT` | introduce_table | pragmatic | EMPTY→SEATED |
| `GO_TABLE` | (move) / check_empty_table | epistemic | robot_loc→TABLE; observe occupancy |
| `TAKE_ORDER` | take_order | pragmatic | SEATED→ORDERED (LLM dialogue) |
| `MARK_READY` | mark_order_ready | exogenous* | ORDERED→READY (kitchen) |
| `COLLECT_DELIVER`| collect_order | pragmatic | READY→DELIVERED via BARISTA |

\*`MARK_READY` is really an exogenous kitchen transition; model it as a
stochastic B transition that fires independent of the robot, not a chosen action
(the agent *waits/observes* rather than *causes* it). Kept as an action only for
parity with the current sim.

### Transitions `B(s'|s,u)`
Service actions advance `phase` along the lifecycle **iff** preconditions hold
(else identity); epistemic actions leave `phase` unchanged and move `robot_loc`.
`MARK_READY` is a slow stochastic `ORDERED→READY` transition.

### Preferences `C`
Log-preference over **phase_evidence**: monotonically increasing toward
`DELIVERED` (served customer = goal). This single vector replaces *all* the
hand-tuned `self.order` ranks — the ordering of behaviors emerges because each
pragmatic action's expected observation moves probability mass toward the
preferred `DELIVERED` outcome, discounted by how many steps away it is.

### Priors `D`
Start near `EMPTY` / `ENTRANCE`. On each tick, **seed Q(s) from the Firestore
document** (the persisted posterior) so the agent and the webapp/peers share one
belief — the DB *is* the multi-agent blackboard, now interpreted probabilistically.

## Law-as-code: where norms enter

Norms compile into the same generative model at three seams (increasing
hardness), connecting to the `Law-as-code-aif` work:

1. **Soft norms → `C` augmentation.** Dispreferred observations carry negative
   preference: e.g. *serve tables in arrival order*, *don't leave a seated party
   waiting > T*, hygiene/precedence rules. Tunable, tradeable against service.
2. **Policy priors → `E`.** A prior over policies `E(π)` down-weights
   norm-discouraged action sequences (e.g. approaching a customer who declined
   service). Soft, probabilistic deontics.
3. **Hard constraints → `B`/policy masks.** Legally-impossible transitions are
   zeroed (e.g. *cannot serve a restricted item to an ineligible party* → the
   `DELIVER` transition is masked for that state). Inviolable.

A **precision γ_norm** over the norm channel tunes strict-vs-flexible compliance,
exactly as rank→γ does in `leader_follower_aif`. This gives a graded, auditable
"how legal vs how efficient" knob — the law-as-code contribution: statutes/service
rules parsed into structured (C, E, B-mask, γ) tuples rather than `if` branches.

See [[law-as-code-aif]] for the norm-compilation front end.

## Mapping to the existing ROS interface

`AIFCoordinator` (scripts/aif/aif_coordinator.py) is a `ReactiveCoordinator`
look-alike:
- **Observe**: read Firestore + the latest vision/speech into an observation
  vector (`encode_observation`).
- **Infer**: `agent.infer_states(o)` → Q(s) (and persist back to Firestore).
- **Plan**: `agent.infer_policies()` → q(π), EFE.
- **Act**: `agent.sample_action()` → action → the *same* `set_navigation_target`
  / `say` / `ask` / DB writes the reactive behaviors already use.

So the navigation team, speech team, and webapp are unaffected — only the
*selection* of what to do next changes from argmax-priority to EFE-min.

## Open modelling decisions (flagged for review)

1. **State factorisation** — independent per-table POMDPs (simple, scalable) vs a
   joint model with a shared robot-location and queue factor (captures "serve in
   order" coupling natively). Scaffold does per-table; norm #1 above is the cheap
   way to add ordering without a joint state space.
2. **Framework** — *resolved*: built directly on the **JAX `pymdp.agent.Agent`**
   (not the legacy numpy pymdp, which is install-fragile and was deprecated to
   JAX). This matches `leader_follower_aif`. Its custom `HierarchicalAIFPlanner`
   (ToM, continuous energy factors) is too domain-specific to reuse here, so we
   drive the raw `Agent`; that wrapper is the porting target if precision
   modulation / continuous factors are later needed.
3. **MARK_READY** — exogenous transition (principled) vs action (sim parity).
4. **Epistemic source** — location-gated A (in scaffold) vs explicit
   ambiguity/precision over vision; the latter lets the LLM/vision confidence
   feed γ directly.
