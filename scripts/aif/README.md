# AIF waiter (active-inference behavior core)

An active-inference reformulation of the `ReactiveCoordinator` waiter logic:
instead of `argmax(order x precondition)`, the agent minimises expected free
energy (EFE) over a generative model of the service lifecycle, using the JAX
`pymdp.agent.Agent` (same stack as `leader_follower_aif`). The info-gathering
behaviors become **epistemic** actions and the service behaviors **pragmatic**
ones — arbitrated automatically. Norms ("law as code") enter as priors/masks.

Full rationale and the behavior -> generative-model mapping: **[../../docs/aif_design.md](../../docs/aif_design.md)**.

## Files
| File | Role |
| --- | --- |
| `generative_model.py` | POMDP: state = phase x robot_loc; A (location-gated), B (precondition-gated), C (preference toward DELIVERED), D, and the `Norms` law-as-code seam. |
| `aif_coordinator.py` | `AIFWaiter` EFE decision core (JAX pymdp) + `run_headless()` demo. |
| `requirements.txt` | `inferactively-pymdp` (JAX) + `jax[cpu]` + `numpy`. |

## Run the headless demo
**Run on Linux / WSL** — JAX's first XLA compile is far faster than on native
Windows (minutes vs seconds).
```bash
pip install -r scripts/aif/requirements.txt
python scripts/aif/aif_coordinator.py
```
Expected output — the agent serves one table by EFE minimisation alone (no
hand-coded priorities), in the optimal 6 steps:
```
 0  SEAT         SEATED@ENTRANCE
 1  GO_TABLE     SEATED@TABLE
 2  TAKE_ORDER   ORDERED@TABLE
 3  MARK_READY   READY@TABLE
 4  GO_BARISTA   READY@BARISTA
 5  DELIVER      DELIVERED@TABLE   -> served in 6 steps.
```

## Evaluation
`python scripts/aif/evaluate.py` runs the episode over many seeds:

| Environment | Success | Steps-to-serve |
| --- | --- | --- |
| matched (obs sharp 0.9) | 10/10 | 6 (optimal) |
| noisy env (obs sharp 0.6) | 10/10 | 6 (optimal) |

The agent serves optimally every seed and is robust to observation noise well
beyond what its model assumes. **Caveat:** as modelled the task is
near-deterministic from the agent's view, so this does **not** yet stress the
*epistemic* machinery (the ~2 move actions/episode are required, not
uncertainty-driven extra looks). Demonstrating "look when unsure" needs a harder
variant (latent table state, stochastic customers / party size). The env-vs-agent
mismatch here is observation-noise only (shared B); no pytest unit tests yet.

## Status
**Validated end-to-end**: the JAX agent constructs, infers, and drives a table
EMPTY -> DELIVERED optimally (10/10 seeds, 6 steps). The serve *order* emerges
from EFE, not from `self.order` ranks.

Note: `policy_len=4` (deterministic) is needed because the payoff (DELIVERED) is
only observable several steps ahead — a 1-step agent dithers. The numeric
likelihoods/preferences are still first-pass.

Next: multi-table factorisation, law-as-code norm compilation, and the ROS
wiring (swap into `turtlebot4_run.py`). See the "Open modelling decisions" in the
design doc.
