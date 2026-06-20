"""AIF decision core for the waiter (JAX pymdp) — a ReactiveCoordinator look-alike.

`AIFWaiter` selects one action per tick by EFE minimisation over the generative
model in generative_model.py, replacing the hand-coded `order x precondition`
argmax. Uses the JAX `pymdp.agent.Agent` (same stack as leader_follower_aif).

Two entry points:
  - act(obs)          : one decision step, for wiring into the ROS coordinator.
  - run_headless(...)  : a self-contained simulation (no ROS/Firestore) that runs
                         the generative process and prints the action trace.

NOTE: run on Linux/WSL — JAX's first XLA compile is far faster there than on
native Windows. Deps: scripts/aif/requirements.txt.

ROS integration (TODO): in turtlebot4_run.py, each timer tick build `obs` from
Firestore + the latest vision/speech, call act(), and route the chosen action
through the SAME primitives the reactive behaviors use (ACTION_TO_TARGET below).

STATUS: scaffold / WIP.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generative_model as gm  # noqa: E402

# action -> the navigation/behavior primitive the reactive system already uses.
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


def _build_agent(norms: gm.Norms | None = None, gamma: float = 16.0,
                 action_selection: str = "deterministic", policy_len: int = 4):
    try:
        import jax.numpy as jnp
        from pymdp.agent import Agent
        from pymdp.control import construct_policies
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "JAX pymdp not installed. `pip install -r scripts/aif/requirements.txt` "
            "(run on Linux/WSL for fast XLA compile)."
        ) from exc

    A_, B_, C_, D_, _E = gm.build_model(norms)
    # JAX pymdp wants a leading batch dimension on every array.
    A = [jnp.array(A_[None, ...])]   # (1, N_OBS, N_STATE)
    B = [jnp.array(B_[None, ...])]   # (1, N_STATE, N_STATE, N_ACTION)
    C = [jnp.array(C_[None, ...])]   # (1, N_OBS)
    D = [jnp.array(D_[None, ...])]   # (1, N_STATE)
    policies = construct_policies([gm.N_STATE], [gm.N_ACTION], policy_len=policy_len, control_fac_idx=[0])
    agent = Agent(
        A=A, B=B, C=C, D=D,
        A_dependencies=[[0]], B_dependencies=[[0]],
        num_controls=[gm.N_ACTION], control_fac_idx=[0],
        policies=policies, policy_len=policy_len, gamma=gamma,
        action_selection=action_selection, inference_algo="fpi", num_iter=16,
        batch_size=1,
    )
    return agent


class AIFWaiter:
    """One active-inference decision core for the waiter (JAX pymdp)."""

    def __init__(self, norms: gm.Norms | None = None, gamma: float = 16.0, seed: int = 0):
        import jax
        self.agent = _build_agent(norms, gamma)
        self.key = jax.random.PRNGKey(seed)
        self.prior = list(self.agent.D)  # empirical prior over states (rolled forward each step)

    def act(self, obs_idx: int) -> int:
        """obs_idx in [0, N_OBS): a phase readout (or AMBIGUOUS). Returns an action."""
        import jax
        import jax.numpy as jnp

        qs = self.agent.infer_states([jnp.array([obs_idx])], self.prior)
        q_pi, _G = self.agent.infer_policies(qs)
        self.key, sub = jax.random.split(self.key)
        action = self.agent.sample_action(q_pi, rng_key=sub[None, :])  # batch dim for vmap
        a = int(np.asarray(action).ravel()[0])

        # Roll the state prior forward through the chosen action: prior = B[:,:,a] qs.
        qs0 = np.asarray(qs[0]).reshape(-1)
        B0 = np.asarray(self.agent.B[0]).reshape(gm.N_STATE, gm.N_STATE, gm.N_ACTION)
        prior0 = B0[:, :, a] @ qs0
        prior0 = prior0 / max(prior0.sum(), 1e-12)
        self.prior = [jnp.array(prior0[None, :])]
        return a


def run_headless(steps: int = 14, seed: int = 0, norms: gm.Norms | None = None) -> None:
    """Simulate the generative process with the model's own B/A and watch the
    EFE-minimising agent drive one table from EMPTY to DELIVERED."""
    rng = np.random.default_rng(seed)
    waiter = AIFWaiter(norms=norms, seed=seed)
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


def run_norm_demo(seed: int = 1, steps: int = 12) -> None:
    """Proof that a law-as-code norm is wired into the *service* agent (not just the
    standalone law_as_code.py model): forbidding MARK_READY ("the robot may not mark
    orders ready — only the kitchen may") flows through build_model -> AIFWaiter as a
    B-mask, so the EFE agent drops that action from its policy."""
    A, Benv = gm.build_A(), gm.build_B()
    print(f"{'norm':<22} {'MARK_READY used':>16}   served")
    for label, norms in (("(none)", None),
                          ("forbid MARK_READY", gm.Norms(forbidden_actions=(gm.MARK_READY,)))):
        rng = np.random.default_rng(seed)
        waiter = AIFWaiter(norms=norms, seed=seed)
        s = gm.s_idx(gm.EMPTY, gm.ENTRANCE)
        actions = []
        for _ in range(steps):
            o = int(rng.choice(gm.N_OBS, p=A[:, s]))
            a = waiter.act(o)
            actions.append(a)
            s = int(rng.choice(gm.N_STATE, p=Benv[:, s, a]))
            if gm.s_unpack(s)[0] == gm.DELIVERED:
                break
        served = gm.s_unpack(s)[0] == gm.DELIVERED
        print(f"{label:<22} {actions.count(gm.MARK_READY):>16}   {served}")
    print("\nThe agent obeys the norm (0 uses when forbidden). On this single-table")
    print("model the kitchen-wait alternative is observability-limited, so the full")
    print("behavioural law-as-code demo lives in law_as_code.py (2-table precedence).")


if __name__ == "__main__":
    print("=== service agent: serve one table by EFE ===")
    run_headless()
    print("\n=== law-as-code norm wired into the service agent ===")
    run_norm_demo()
