"""AIF decision core for the waiter — a ReactiveCoordinator look-alike.

`AIFWaiter` selects one action per tick by EFE minimisation over the generative
model in generative_model.py, replacing the hand-coded `order x precondition`
argmax. Two entry points:

  - act(obs)         : one decision step, for wiring into the ROS coordinator.
  - run_headless(...) : a self-contained simulation (no ROS/Firestore) that runs
                        the generative process and prints the action trace, to
                        validate that sensible serve-order behavior emerges.

ROS integration (TODO): in turtlebot4_run.py, swap ReactiveCoordinator for a thin
node that, each timer tick, builds `obs` from Firestore + the latest vision/speech
(encode_observation) and routes the chosen action through the SAME primitives the
reactive behaviors use (set_navigation_target / say / ask / db writes). The map
from action -> primitive is ACTION_TO_TARGET below.

STATUS: scaffold / WIP. Requires `pip install inferactively-pymdp`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generative_model as gm  # noqa: E402

# action -> the navigation/behavior primitive the reactive system already uses.
# (location ids match database_bridge: "entrance" / "barista" / table_{n}.)
ACTION_TO_TARGET = {
    gm.GO_ENTRANCE: ("nav", "entrance"),
    gm.GO_TABLE: ("nav", "table"),       # resolved to table_{current+1} at runtime
    gm.GO_BARISTA: ("nav", "barista"),
    gm.SEAT: ("behavior", "introduce_table"),
    gm.TAKE_ORDER: ("behavior", "take_order"),
    gm.MARK_READY: ("behavior", "mark_order_ready"),
    gm.DELIVER: ("behavior", "collect_order"),
    gm.WAIT: ("noop", None),
}


def _make_agent(norms: gm.Norms | None = None):
    try:
        from pymdp import utils
        from pymdp.agent import Agent
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "pymdp not installed. `pip install inferactively-pymdp` to run the AIF agent."
        ) from exc

    A_, B_, C_, D_, E_ = gm.build_model(norms)
    A = utils.obj_array(1); A[0] = A_
    B = utils.obj_array(1); B[0] = B_
    C = utils.obj_array(1); C[0] = C_
    D = utils.obj_array(1); D[0] = D_
    return Agent(A=A, B=B, C=C, D=D, E=E_, policy_len=1, use_utility=True, use_states_info_gain=True)


class AIFWaiter:
    """One active-inference decision core for the waiter."""

    def __init__(self, norms: gm.Norms | None = None):
        self.norms = norms
        self.agent = _make_agent(norms)

    def act(self, obs_idx: int) -> int:
        """obs_idx in [0, N_OBS): a phase readout (or AMBIGUOUS). Returns an action."""
        self.agent.infer_states([obs_idx])
        self.agent.infer_policies()
        action = self.agent.sample_action()
        return int(action[0])


def run_headless(steps: int = 14, seed: int = 0, norms: gm.Norms | None = None) -> None:
    """Simulate the generative process with the model's own B/A and watch the
    EFE-minimising agent drive one table from EMPTY to DELIVERED."""
    rng = np.random.default_rng(seed)
    waiter = AIFWaiter(norms)
    A, B = gm.build_A(), gm.build_B()

    true_s = gm.s_idx(gm.EMPTY, gm.ENTRANCE)
    print(f"{'t':>2}  {'action':<12} {'true (phase@loc)':<22} obs")
    for t in range(steps):
        o = int(rng.choice(gm.N_OBS, p=A[:, true_s]))
        a = waiter.act(o)
        true_s = int(rng.choice(gm.N_STATE, p=B[:, true_s, a]))
        phase, loc = gm.s_unpack(true_s)
        o_lbl = "AMBIGUOUS" if o == gm.AMBIGUOUS else gm.PHASES[o]
        print(f"{t:>2}  {gm.ACTIONS[a]:<12} {gm.PHASES[phase]+'@'+gm.LOCS[loc]:<22} {o_lbl}")
        if phase == gm.DELIVERED:
            print(f"-> served in {t + 1} steps.")
            break


if __name__ == "__main__":
    # Example: a "serve-in-arrival-order" soft norm would down-weight DELIVER
    # before earlier phases; here we run the un-normed agent.
    run_headless()
