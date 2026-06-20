"""End-to-end tests for the active-inference subsystem.

Run on Linux/WSL (JAX):
    python3 -m pytest scripts/aif/test_e2e.py -q

Structural tests use numpy only (fast); behavioural tests build JAX agents and
run them to completion (slower — the EFE agent must actually serve).
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import game_phases as gp            # noqa: E402  V1: 6 competition phases
import game_phases_multi as gpm     # noqa: E402  V2: multi-customer + law
import generative_model as tm       # noqa: E402  the PR#17 table model


def _col_stochastic(B):
    for a in range(B.shape[2]):
        assert np.allclose(B[:, :, a].sum(0), 1.0), f"B action {a} not column-stochastic"


# ---------------------------------------------------------------------------
# Structural — game-phases model (numpy, fast)
# ---------------------------------------------------------------------------
def test_game_phases_A_normalized():
    A = gp.build_A()
    assert A.shape == (gp.N_OBS, gp.N_STATE)
    assert np.allclose(A.sum(0), 1.0)


def test_game_phases_B_col_stochastic():
    _col_stochastic(gp.build_B())


def test_game_phases_C_terminal_dominates():
    C = gp.build_C()
    assert C.shape == (gp.N_OBS,)
    assert C[gp.STANDBY] == C[: gp.N_PHASE].max()    # completed cycle dominates
    assert C[gp.AMBIGUOUS] < 0                        # disambiguation is preferred


def test_game_phases_D_starts_detected_entrance():
    D = gp.build_D()
    assert np.isclose(D.sum(), 1.0)
    assert np.argmax(D) == gp.s_idx(gp.DETECTED, gp.ENTRANCE)


def test_game_phases_observations_location_gated():
    A = gp.build_A()
    on = gp.s_idx(gp.DETECTED, gp.ENTRANCE)          # DETECTED's station
    off = gp.s_idx(gp.DETECTED, gp.TABLE)
    assert A[gp.DETECTED, on] > 0.5                   # sharp on-station
    assert A[gp.AMBIGUOUS, off] > 0.5                 # AMBIGUOUS off-station


def test_game_phases_scripted_optimal_reaches_standby():
    B = gp.build_B()
    s = gp.s_idx(gp.DETECTED, gp.ENTRANCE)
    for a in (gp.GREET, gp.GO_TABLE, gp.TAKE_ORDER, gp.GO_COUNTER, gp.VERIFY,
              gp.GO_TABLE, gp.SERVE, gp.GO_COUNTER, gp.RETURN):
        s = int(np.argmax(B[:, s, a]))
    assert gp.s_unpack(s) == (gp.STANDBY, gp.COUNTER)


# ---------------------------------------------------------------------------
# Structural — table model (numpy, fast)
# ---------------------------------------------------------------------------
def test_table_model_valid():
    A, B, C, D, _E = tm.build_model()
    assert np.allclose(A.sum(0), 1.0)
    _col_stochastic(B)
    assert np.isclose(D.sum(), 1.0)


# ---------------------------------------------------------------------------
# Law-as-code ordering (numpy, fast)
# ---------------------------------------------------------------------------
def test_law_order_context_sensitive():
    custs = [gpm.Customer("A", size=2, wait=12),
             gpm.Customer("B", size=6, wait=3),
             gpm.Customer("C", size=3, wait=7)]
    quiet = [c.name for c in gpm.law_order(custs, busy=0.0)]
    slammed = [c.name for c in gpm.law_order(custs, busy=1.0)]
    assert quiet[0] == "A"        # fairness: longest-waiting served first
    assert slammed[0] == "B"      # throughput: big party first when busy
    assert quiet != slammed       # same law, context changes the order


def test_law_priority_is_hard():
    custs = [gpm.Customer("A", size=2, wait=12),
             gpm.Customer("B", size=6, wait=3, priority=True)]
    assert [c.name for c in gpm.law_order(custs, busy=0.0)][0] == "B"


# ---------------------------------------------------------------------------
# Behavioural — full EFE agents run to completion (JAX, slower)
# ---------------------------------------------------------------------------
def test_game_phases_agent_serves_full_cycle():
    assert gp.serve(seed=0) is True            # reaches STANDBY (full 6-phase cycle)


def test_game_phases_multi_serves_all_customers():
    custs = [gpm.Customer("A", 2, 12), gpm.Customer("B", 6, 3), gpm.Customer("C", 3, 7)]
    served = sum(gpm.serve_one(seed=i) for i in range(len(custs)))
    assert served == 3


def test_table_agent_serves_to_delivered():
    import aif_coordinator as ac
    waiter = ac.AIFWaiter(seed=0)
    A, B = tm.build_A(), tm.build_B()
    rng = np.random.default_rng(0)
    s = tm.s_idx(tm.EMPTY, tm.ENTRANCE)
    served = False
    for _ in range(20):
        o = int(rng.choice(tm.N_OBS, p=A[:, s]))
        a = waiter.act(o)
        s = int(rng.choice(tm.N_STATE, p=B[:, s, a]))
        if tm.s_unpack(s)[0] == tm.DELIVERED:
            served = True
            break
    assert served


def test_epistemic_looks_when_uncertain():
    import epistemic_test as ep
    checked_uncertain, _ = ep._episode(0.5, ep.A_NEEDS)
    checked_confident, _ = ep._episode(0.99, ep.A_NEEDS)
    assert checked_uncertain is True     # uncertain -> check the board (epistemic)
    assert checked_confident is False    # confident -> exploit the prior


def test_epistemic_serves_correctly_when_it_looks():
    import epistemic_test as ep
    checked, correct = ep._episode(0.5, ep.B_NEEDS)
    assert checked and correct           # looked -> served the right table


def test_evaluate_optimal_serve():
    import evaluate as ev
    ok, steps, _ = ev.episode(0)
    assert ok and steps == 6             # serves the table in the optimal 6 steps
