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
| `evaluate.py` | Multi-seed evaluation of the service task (success rate, steps). |
| `epistemic_test.py` | Epistemic stress-test: does the agent *look when unsure*? |
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
beyond what its model assumes.

### Epistemic stress-test — does it look when unsure?
`python scripts/aif/epistemic_test.py` — a restaurant T-maze where a *latent*
"which table needs service" can only be resolved by visiting the BOARD (a cue),
and serving the wrong table is penalised. Sweeping the prior certainty:

| P(table A needs) | checks board? | serves correctly |
| --- | --- | --- |
| 0.50 | **YES** | 100% |
| 0.60 | **YES** | 100% |
| 0.70 | no | 70% |
| 0.90 | no | 90% |
| 0.99 | no | 99% |

The agent **chooses the information-gathering action exactly when uncertain**
(P ≤ 0.6 → check the board → serve correctly) and skips it once confident
(exploiting the prior). "Look when unsure" *emerges* from EFE — it is not coded.
The look/skip boundary is the value of information: raising the wrong-serve
penalty widens the band where the agent looks.

Remaining gaps: still self-play (env dynamics = the agent's own B; only the
observation noise was mismatched in the service eval), and no pytest unit tests.

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
