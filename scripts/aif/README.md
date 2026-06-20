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
| `law_as_code.py` | Compile a precedence rule into the model (soft/hard) + precision knob. |
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

### Law as code — compile a rule, watch context reshape it
`python scripts/aif/law_as_code.py` — the precedence/fairness rule "serve who
waited longest" is compiled into the preferences **C**, then reshaped by party
size, wait time, and how busy the kitchen is (context enters through C, not `if`
branches):

```
  equal tables                          order: A, B   (arrival order)
  B has the bigger party (2 vs 6)       order: B, A   (throughput)
  A waited much longer (12 vs 3 min)    order: A, B   (fairness)
  conflict (A waited longer, B bigger):
     quiet kitchen  (busy=0)            order: A, B   (fairness holds)
     slammed kitchen (busy=1)           order: B, A   (throughput wins)
  A flagged priority/accessibility      order: A, B   (priority)
  hard mask: B-before-A forbidden       order: A, B   (inviolable)
```

The standout: **busyness flips the same conflict** — quiet, fairness serves the
longer-waiting table; slammed, throughput serves the bigger party. The law's
strength is a **precision knob** (`fairness_lambda`) that crosses from throughput
to fairness where the norm outweighs the efficiency gain. These are the
`(C, E, B-mask)` seams from [the design doc](../../docs/aif_design.md): norms
compiled into the generative model and conditioned on restaurant context, not
bolted on as rules.

**Wired into the service agent too.** The same `Norms` seam feeds the main
`AIFWaiter`, not only this standalone model: `forbidden_actions` compile to a
B-mask in `generative_model.build_model`, so a norm changes the *real* service
agent's policy. `python scripts/aif/aif_coordinator.py` shows forbidding
`MARK_READY` ("only the kitchen may mark orders ready") drops it from the agent's
actions (1 → 0 uses). The single-table service model has no clean alternative
path, so the *behavioural* law-as-code story lives in this 2-table model;
unifying them is the multi-table service-model work.

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
