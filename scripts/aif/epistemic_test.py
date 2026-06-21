"""Epistemic stress-test: does the agent LOOK when it is uncertain?

A restaurant-flavoured T-maze. A latent variable -- *which* table needs service
-- is unknown at the start. The robot can only resolve it by visiting the BOARD
(a cue location). Serving the WRONG table is penalised. So the rational policy
is: when uncertain, go to the BOARD first (an epistemic action with no direct
reward), then serve the right table; when already confident, skip the board and
serve directly.

We sweep the prior certainty P(table A needs service) and measure whether the
agent checks the board, and whether it serves correctly. "Look when unsure"
should emerge from expected-free-energy minimisation -- it is not coded.

Run on Linux/WSL:  python scripts/aif/epistemic_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

# locations (controllable factor) and latent "which table needs service"
LOBBY, BOARD, TABLE_A, TABLE_B = range(4)
N_LOC = 4
A_NEEDS, B_NEEDS = range(2)
N_WHICH = 2
# observations
CUE_NONE, CUE_A, CUE_B = range(3)
R_NEUTRAL, R_SERVED, R_WRONG = range(3)


def _build_arrays():
    # A0: loc_obs | loc  (fully observed location)
    A0 = np.eye(N_LOC)
    # A1: cue | loc, which  -> the BOARD reveals which table needs service
    A1 = np.zeros((3, N_LOC, N_WHICH))
    for w in range(N_WHICH):
        for l in range(N_LOC):
            if l == BOARD:
                A1[CUE_A if w == A_NEEDS else CUE_B, l, w] = 1.0
            else:
                A1[CUE_NONE, l, w] = 1.0
    # A2: reward | loc, which  -> SERVED at the right table, WRONG at the other
    A2 = np.zeros((3, N_LOC, N_WHICH))
    for w in range(N_WHICH):
        for l in range(N_LOC):
            if l == TABLE_A:
                A2[R_SERVED if w == A_NEEDS else R_WRONG, l, w] = 1.0
            elif l == TABLE_B:
                A2[R_SERVED if w == B_NEEDS else R_WRONG, l, w] = 1.0
            else:
                A2[R_NEUTRAL, l, w] = 1.0
    # B0: loc | loc, action  -> action a moves to location a (deterministic)
    B0 = np.zeros((N_LOC, N_LOC, N_LOC))
    for a in range(N_LOC):
        B0[a, :, a] = 1.0
    # B1: which | which, (no control)  -> latent, fixed within an episode
    B1 = np.zeros((N_WHICH, N_WHICH, 1))
    for w in range(N_WHICH):
        B1[w, w, 0] = 1.0
    # C: prefer SERVED, strongly avoid WRONG (serving the wrong table is costly);
    # location and cue are neutral. The penalty magnitude sets how much prior
    # certainty is needed before the agent will skip checking the board.
    C = [np.zeros(N_LOC), np.zeros(3), np.array([0.0, 4.0, -8.0])]
    return [A0, A1, A2], [B0, B1], C


def _make_agent(p_a: float, policy_len: int = 3, gamma: float = 16.0):
    import jax.numpy as jnp
    from pymdp.agent import Agent
    from pymdp.control import construct_policies

    A, B, C = _build_arrays()
    A = [jnp.array(a[None, ...]) for a in A]
    B = [jnp.array(b[None, ...]) for b in B]
    C = [jnp.array(c[None, ...]) for c in C]
    D = [jnp.array(np.eye(N_LOC)[LOBBY][None, :]),
         jnp.array(np.array([p_a, 1.0 - p_a])[None, :])]
    policies = construct_policies([N_LOC, N_WHICH], [N_LOC, 1],
                                  policy_len=policy_len, control_fac_idx=[0])
    return Agent(A=A, B=B, C=C, D=D,
                 A_dependencies=[[0], [0, 1], [0, 1]], B_dependencies=[[0], [1]],
                 num_controls=[N_LOC, 1], control_fac_idx=[0],
                 policies=policies, policy_len=policy_len, gamma=gamma,
                 action_selection="deterministic", inference_algo="fpi",
                 num_iter=16, batch_size=1)


def _episode(p_a: float, which: int, policy_len: int = 3, max_steps: int = 5):
    """Returns (checked_board, served_correctly)."""
    import jax
    import jax.numpy as jnp

    agent = _make_agent(p_a, policy_len)
    loc = LOBBY
    prior = list(agent.D)
    key = jax.random.PRNGKey(0)
    checked = False
    for _ in range(max_steps):
        o0 = loc
        o1 = (CUE_A if which == A_NEEDS else CUE_B) if loc == BOARD else CUE_NONE
        if loc == TABLE_A:
            o2 = R_SERVED if which == A_NEEDS else R_WRONG
        elif loc == TABLE_B:
            o2 = R_SERVED if which == B_NEEDS else R_WRONG
        else:
            o2 = R_NEUTRAL
        qs = agent.infer_states([jnp.array([o0]), jnp.array([o1]), jnp.array([o2])], prior)
        q_pi, _ = agent.infer_policies(qs)
        key, sub = jax.random.split(key)
        action = agent.sample_action(q_pi, rng_key=sub[None, :])
        loc = int(np.asarray(action).ravel()[0])
        # roll the prior forward: loc is set by the action; belief over `which`
        # persists (latent). qs has a trailing time axis -> reshape to (batch, n).
        which_belief = np.asarray(qs[1]).reshape(1, N_WHICH)
        prior = [jnp.array(np.eye(N_LOC)[loc][None, :]), jnp.array(which_belief)]
        if loc == BOARD:
            checked = True
        if loc in (TABLE_A, TABLE_B):
            correct = (loc == TABLE_A and which == A_NEEDS) or (loc == TABLE_B and which == B_NEEDS)
            return checked, bool(correct)
    return checked, False


def main() -> None:
    print("Epistemic stress-test: check the BOARD when unsure which table needs service")
    print("(serving the wrong table is penalised; checking the board has no direct reward)\n")
    print(f"{'P(A needs)':>10}  {'checks board?':>13}  {'serves correctly':>17}")
    for p_a in (0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.99):
        # look decision does not depend on the true `which`; accuracy averages over it
        checked_A, ok_A = _episode(p_a, A_NEEDS)
        checked_B, ok_B = _episode(p_a, B_NEEDS)
        checks = checked_A and checked_B
        acc = p_a * ok_A + (1.0 - p_a) * ok_B
        print(f"{p_a:>10.2f}  {('YES' if checks else 'no'):>13}  {acc*100:>15.0f}%")


if __name__ == "__main__":
    main()
