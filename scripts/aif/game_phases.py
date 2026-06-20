"""V1 — Active-inference agent structured around the EMSRC Restaurant Challenge's
six competition phases. No Docker, no ROS, no law-as-code: pure Python/JAX.

Observations follow the PR #17 table model: a single **location-gated, noisy**
`phase_evidence` modality with an `AMBIGUOUS` outcome. The robot reads a phase
sharply only when it is at that phase's station (detect at the entrance, confirm
the order at the table, check the tray at the counter, ...); elsewhere it sees
`AMBIGUOUS`. So the `GO_*` navigation actions earn **information gain** — the
agent must *move to perceive*, not just plan. (V0 used a fully-observed identity
likelihood, which made the epistemic term ~0; this restores it.)

Phases (rulebook score sheet) and the points earned on reaching each one:

  DETECTED  100   detect a calling/waving customer            (Phase 1)
  SEATED   +200   welcome (75) + guide/seat to a table (125)  (Phase 1)
  ORDERED  +250   take order (150) + confirm it back (100)    (Phase 3, via nav P2)
  VERIFIED +275   counter nav (75) + tell barman (100) + verify tray (100)  (Phase 4)
  SERVED   +250   return to table (100) + serve correct customer (150)      (Phase 5)
  STANDBY  +125   return to counter (75) + standby (50)       (Phase 6)
                  ----  a full cycle = 1200 base points

C is the cumulative rulebook points over the *observations*, so the agent acts to
maximise expected competition score (pragmatic value) while navigating to resolve
its phase belief (epistemic value). `AMBIGUOUS` is dispreferred.

Run on Linux/WSL:  python scripts/aif/game_phases.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ----- the six competition phases -------------------------------------------
DETECTED, SEATED, ORDERED, VERIFIED, SERVED, STANDBY = range(6)
PHASES = ("DETECTED", "SEATED", "ORDERED", "VERIFIED", "SERVED", "STANDBY")
N_PHASE = 6
PHASE_POINTS = (100, 200, 250, 275, 250, 125)       # earned on reaching each phase
CUM_POINTS = np.cumsum(PHASE_POINTS)                 # [100, 300, 550, 825, 1075, 1200]

# ----- robot location --------------------------------------------------------
ENTRANCE, TABLE, COUNTER = range(3)
LOCS = ("ENTRANCE", "TABLE", "COUNTER")
N_LOC = 3
N_STATE = N_PHASE * N_LOC                            # 18

# ----- actions ---------------------------------------------------------------
GO_ENTRANCE, GO_TABLE, GO_COUNTER, GREET, TAKE_ORDER, VERIFY, SERVE, RETURN = range(8)
ACTIONS = ("GO_ENTRANCE", "GO_TABLE", "GO_COUNTER",
           "GREET", "TAKE_ORDER", "VERIFY", "SERVE", "RETURN")
N_ACTION = 8

# ----- observation: location-gated noisy phase readout (+ AMBIGUOUS) ---------
AMBIGUOUS = N_PHASE                                  # 7th outcome
N_OBS = N_PHASE + 1
# where each phase is observed (and acted upon) sharply
PHASE_STATION = {DETECTED: ENTRANCE, SEATED: TABLE, ORDERED: TABLE,
                 VERIFIED: COUNTER, SERVED: TABLE, STANDBY: COUNTER}


def s_idx(phase: int, loc: int) -> int:
    return phase * N_LOC + loc


def s_unpack(s: int) -> tuple[int, int]:
    return divmod(s, N_LOC)


def build_A(sharp: float = 0.9) -> np.ndarray:
    """Sharp phase readout at the phase's station, else mostly AMBIGUOUS — this
    location gating is what makes the GO_* actions informative (epistemic value)."""
    A = np.zeros((N_OBS, N_STATE))
    for s in range(N_STATE):
        phase, loc = s_unpack(s)
        if loc == PHASE_STATION[phase]:
            A[phase, s] = sharp
            A[AMBIGUOUS, s] = 1.0 - sharp
        else:
            A[AMBIGUOUS, s] = sharp
            A[phase, s] = 1.0 - sharp
    return A


def build_B() -> np.ndarray:
    """Movement actions change location; phase-advancing actions advance the phase
    only when the robot is at the right station, else they are no-ops."""
    B = np.zeros((N_STATE, N_STATE, N_ACTION))

    def move(a, dst):
        for s in range(N_STATE):
            phase, _ = s_unpack(s)
            B[s_idx(phase, dst), s, a] = 1.0

    move(GO_ENTRANCE, ENTRANCE)
    move(GO_TABLE, TABLE)
    move(GO_COUNTER, COUNTER)

    def advance(a, need_phase, need_loc, next_phase):
        for s in range(N_STATE):
            phase, loc = s_unpack(s)
            if phase == need_phase and loc == need_loc:
                B[s_idx(next_phase, loc), s, a] = 1.0
            else:
                B[s, s, a] = 1.0  # no-op

    advance(GREET,      DETECTED, ENTRANCE, SEATED)
    advance(TAKE_ORDER, SEATED,   TABLE,    ORDERED)
    advance(VERIFY,     ORDERED,  COUNTER,  VERIFIED)
    advance(SERVE,      VERIFIED, TABLE,    SERVED)
    advance(RETURN,     SERVED,   COUNTER,  STANDBY)
    return B


def build_C() -> np.ndarray:
    """Monotonic preference toward the full cycle. Intermediate phases give a
    gentle gradient to climb; STANDBY (the completed cycle) dominates so the agent
    does not *farm* a high-scoring mid-phase observation under the finite horizon
    (re-observing VERIFIED forever would otherwise beat progressing through the
    AMBIGUOUS dip). AMBIGUOUS is dispreferred. (Rulebook points are still used for
    the reported score; this is the agent's shaped preference.)"""
    #               DETECTED SEATED ORDERED VERIFIED SERVED STANDBY  AMBIGUOUS
    return np.array([0.0,    1.0,   2.0,    3.0,     4.0,   25.0,    -0.5])


def build_D() -> np.ndarray:
    D = np.full(N_STATE, 1e-4)
    D[s_idx(DETECTED, ENTRANCE)] = 1.0
    return D / D.sum()


def _make_agent(policy_len: int = 4, gamma: float = 16.0):
    import jax.numpy as jnp
    from pymdp.agent import Agent
    from pymdp.control import construct_policies

    A, B, C, D = build_A(), build_B(), build_C(), build_D()
    policies = construct_policies([N_STATE], [N_ACTION], policy_len=policy_len, control_fac_idx=[0])
    return Agent(
        A=[jnp.array(A[None])], B=[jnp.array(B[None])],
        C=[jnp.array(C[None])], D=[jnp.array(D[None])],
        A_dependencies=[[0]], B_dependencies=[[0]],
        num_controls=[N_ACTION], control_fac_idx=[0],
        policies=policies, policy_len=policy_len, gamma=gamma,
        action_selection="deterministic", inference_algo="fpi", num_iter=16, batch_size=1,
    )


class PhaseWaiter:
    """AIF agent over the six phases under partial (location-gated) observation."""

    def __init__(self, policy_len: int = 4, seed: int = 0):
        import jax
        self.agent = _make_agent(policy_len)
        self.key = jax.random.PRNGKey(seed)
        self.prior = list(self.agent.D)

    def act(self, obs_idx: int) -> int:
        import jax
        import jax.numpy as jnp
        qs = self.agent.infer_states([jnp.array([obs_idx])], self.prior)
        q_pi, _ = self.agent.infer_policies(qs)
        self.key, sub = jax.random.split(self.key)
        a = int(np.asarray(self.agent.sample_action(q_pi, rng_key=sub[None, :])).ravel()[0])
        qs0 = np.asarray(qs[0]).reshape(-1)
        B0 = np.asarray(self.agent.B[0]).reshape(N_STATE, N_STATE, N_ACTION)
        prior0 = B0[:, :, a] @ qs0
        self.prior = [jnp.array((prior0 / max(prior0.sum(), 1e-12))[None, :])]
        return a


def serve(steps: int = 18, seed: int = 0) -> bool:
    """Run one customer through the six phases under partial observation. The agent
    must navigate to perceive: it sees AMBIGUOUS until it reaches a phase's station."""
    rng = np.random.default_rng(seed)
    waiter = PhaseWaiter(seed=seed)
    A, B = build_A(), build_B()
    true_s = s_idx(DETECTED, ENTRANCE)
    reached = {DETECTED}
    print(f"{'t':>2}  {'action':<11} {'true phase@loc':<20} {'obs':<10} {'score':>5}")
    for t in range(steps):
        o = int(rng.choice(N_OBS, p=A[:, true_s]))
        a = waiter.act(o)
        true_s = int(np.argmax(B[:, true_s, a]))
        phase, loc = s_unpack(true_s)
        reached.add(phase)
        o_lbl = "AMBIGUOUS" if o == AMBIGUOUS else PHASES[o]
        score = int(sum(PHASE_POINTS[p] for p in reached))
        print(f"{t:>2}  {ACTIONS[a]:<11} {PHASES[phase]+'@'+LOCS[loc]:<20} {o_lbl:<10} {score:>5}")
        if phase == STANDBY:
            print(f"-> full 6-phase cycle in {t + 1} steps; score {score}/1200 (base).")
            return True
    return False


if __name__ == "__main__":
    serve()
