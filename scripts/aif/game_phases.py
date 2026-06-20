"""V1 — Active-inference agent structured around the EMSRC Restaurant Challenge's
six competition phases. No Docker, no ROS, no law-as-code: pure Python/JAX.

Phases (from the rulebook score sheet) and the rulebook points earned on reaching
each one:

  DETECTED  100   detect a calling/waving customer            (Phase 1)
  SEATED   +200   welcome (75) + guide/seat to a table (125)  (Phase 1)
  ORDERED  +250   take order (150) + confirm it back (100)    (Phase 3, via nav P2)
  VERIFIED +275   counter nav (75) + tell barman (100) + verify tray (100)  (Phase 4)
  SERVED   +250   return to table (100) + serve correct customer (150)      (Phase 5)
  STANDBY  +125   return to counter (75) + standby (50)       (Phase 6)
                  ----  a full cycle = 1200 base points

The agent serves a customer through all six phases by EFE minimisation. Its
preferences C are the *cumulative rulebook points*, so the agent literally acts
to maximise its expected competition score. No norms (that's V2).

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
# points earned on *reaching* each phase (rulebook score sheet)
PHASE_POINTS = (100, 200, 250, 275, 250, 125)
CUM_POINTS = np.cumsum(PHASE_POINTS)            # [100, 300, 550, 825, 1075, 1200]

# ----- robot location --------------------------------------------------------
ENTRANCE, TABLE, COUNTER = range(3)
LOCS = ("ENTRANCE", "TABLE", "COUNTER")
N_LOC = 3
N_STATE = N_PHASE * N_LOC                        # 18

# ----- actions ---------------------------------------------------------------
GO_ENTRANCE, GO_TABLE, GO_COUNTER, GREET, TAKE_ORDER, VERIFY, SERVE, RETURN = range(8)
ACTIONS = ("GO_ENTRANCE", "GO_TABLE", "GO_COUNTER",
           "GREET", "TAKE_ORDER", "VERIFY", "SERVE", "RETURN")
N_ACTION = 8

# the station where each phase-advancing action must happen
#   GREET @ ENTRANCE, TAKE_ORDER @ TABLE, VERIFY @ COUNTER, SERVE @ TABLE, RETURN @ COUNTER


def s_idx(phase: int, loc: int) -> int:
    return phase * N_LOC + loc


def s_unpack(s: int) -> tuple[int, int]:
    return divmod(s, N_LOC)


def build_A() -> np.ndarray:
    """Fully observed (phase + location are known)."""
    return np.eye(N_STATE)


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
    """Preference over states = cumulative rulebook points (scaled). The agent acts
    to maximise expected competition score; STANDBY (full cycle) dominates."""
    C = np.zeros(N_STATE)
    for s in range(N_STATE):
        phase, _ = s_unpack(s)
        C[s] = CUM_POINTS[phase] / 100.0
    return C


def build_D() -> np.ndarray:
    D = np.full(N_STATE, 1e-4)
    D[s_idx(DETECTED, ENTRANCE)] = 1.0
    return D / D.sum()


def make_agent(policy_len: int = 4, gamma: float = 16.0):
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


def serve(steps: int = 16, seed: int = 0) -> None:
    """Run one customer through the six phases by EFE minimisation; report score."""
    import jax
    import jax.numpy as jnp

    agent = make_agent()
    B = build_B()
    key = jax.random.PRNGKey(seed)
    s = s_idx(DETECTED, ENTRANCE)
    prior = list(agent.D)
    reached = {DETECTED}
    print(f"{'t':>2}  {'action':<12} {'phase@loc':<20} {'score':>6}")
    print(f"{'-':>2}  {'(start)':<12} {PHASES[DETECTED]+'@'+LOCS[ENTRANCE]:<20} {PHASE_POINTS[DETECTED]:>6}")
    for t in range(steps):
        qs = agent.infer_states([jnp.array([s])], prior)
        q_pi, _ = agent.infer_policies(qs)
        key, sub = jax.random.split(key)
        a = int(np.asarray(agent.sample_action(q_pi, rng_key=sub[None, :])).ravel()[0])
        s = int(np.argmax(B[:, s, a]))
        prior = [jnp.array(np.eye(N_STATE)[s][None, :])]
        phase, loc = s_unpack(s)
        reached.add(phase)
        score = int(sum(PHASE_POINTS[p] for p in reached))
        print(f"{t:>2}  {ACTIONS[a]:<12} {PHASES[phase]+'@'+LOCS[loc]:<20} {score:>6}")
        if phase == STANDBY:
            print(f"-> full 6-phase cycle in {t + 1} steps; rulebook score {score}/1200 (base).")
            break


if __name__ == "__main__":
    serve()
