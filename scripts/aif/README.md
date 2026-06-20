# AIF waiter (active-inference behavior core)

An active-inference reformulation of the `ReactiveCoordinator` waiter logic:
instead of `argmax(order x precondition)`, the agent minimises expected free
energy over a generative model of the service lifecycle. The info-gathering
behaviors become **epistemic** actions and the service behaviors **pragmatic**
ones — arbitrated automatically. Norms ("law as code") enter as priors/masks.

Full rationale and the behavior -> generative-model mapping: **[../../docs/aif_design.md](../../docs/aif_design.md)**.

## Files
| File | Role |
| --- | --- |
| `generative_model.py` | POMDP: state = phase x robot_loc; A (location-gated), B (precondition-gated), C (preference toward DELIVERED), D, and the `Norms` law-as-code seam. |
| `aif_coordinator.py` | `AIFWaiter` EFE decision core + `run_headless()` demo. |

## Run the headless demo
```bash
pip install inferactively-pymdp numpy
python scripts/aif/aif_coordinator.py
```
Watch one table go EMPTY -> DELIVERED, with the agent choosing `GO_*` (look) when
uncertain and service actions when confident.

## Status
Scaffold / WIP. Structure is faithful; numeric likelihoods/preferences are
first-pass and need tuning. Next: multi-table factorisation, law-as-code norm
compilation, and the ROS wiring (swap into `turtlebot4_run.py`). See the "Open
modelling decisions" in the design doc.
