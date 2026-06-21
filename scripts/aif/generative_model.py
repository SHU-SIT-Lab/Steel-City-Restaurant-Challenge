"""Active-inference generative model for one table's service cycle.

Single combined state factor `s = (phase, robot_loc)` so that transitions can be
precondition-gated (e.g. TAKE_ORDER only advances phase when at the table) and
observations can be location-gated (you only resolve table occupancy *at* the
table) — the latter is what gives the `GO_*` actions epistemic value.

Returns plain numpy arrays (A, B, C, D) in pymdp's convention. Build a pymdp
`Agent` from them in aif_coordinator.py. Kept framework-light so it imports
without pymdp installed; see docs/aif_design.md for the full rationale and the
port path to the JAX/equinox planner used in leader_follower_aif.

STATUS: scaffold / WIP — dimensions and structure are faithful; the numeric
likelihood/transition values are first-pass and need tuning + validation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# ----- phase lifecycle (mirrors Firestore TableDocument) ---------------------
EMPTY, SEATED, ORDERED, READY, DELIVERED = range(5)
PHASES = ("EMPTY", "SEATED", "ORDERED", "READY", "DELIVERED")
N_PHASE = len(PHASES)

# ----- robot location --------------------------------------------------------
ENTRANCE, TABLE, BARISTA = range(3)
LOCS = ("ENTRANCE", "TABLE", "BARISTA")
N_LOC = len(LOCS)

N_STATE = N_PHASE * N_LOC  # 15 combined states

# ----- actions (the seven behaviors, + WAIT) ---------------------------------
GO_ENTRANCE, GO_TABLE, GO_BARISTA, SEAT, TAKE_ORDER, MARK_READY, DELIVER, WAIT = range(8)
ACTIONS = (
    "GO_ENTRANCE", "GO_TABLE", "GO_BARISTA", "SEAT",
    "TAKE_ORDER", "MARK_READY", "DELIVER", "WAIT",
)
N_ACTION = len(ACTIONS)

# ----- observation: noisy readout of phase (+ AMBIGUOUS) ---------------------
AMBIGUOUS = N_PHASE  # 6th outcome
N_OBS = N_PHASE + 1

# station where each phase is acted upon / observed sharply
PHASE_STATION = {EMPTY: ENTRANCE, SEATED: TABLE, ORDERED: TABLE, READY: BARISTA, DELIVERED: TABLE}


def s_idx(phase: int, loc: int) -> int:
    return phase * N_LOC + loc


def s_unpack(s: int) -> tuple[int, int]:
    return divmod(s, N_LOC)


# ---------------------------------------------------------------------------
# A : P(o | s)  — location-gated likelihood (epistemic value lives here)
# ---------------------------------------------------------------------------
def build_A(sharp: float = 0.9) -> np.ndarray:
    """Sharp phase readout when the robot is at the phase's station, else mostly
    AMBIGUOUS. Ambiguity at the wrong station is what makes GO_* informative."""
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


# ---------------------------------------------------------------------------
# B : P(s' | s, a)  — movement + precondition-gated phase advances
# ---------------------------------------------------------------------------
def build_B(p_kitchen: float = 0.3) -> np.ndarray:
    """B[:, :, a] is a column-stochastic transition for action a."""
    B = np.zeros((N_STATE, N_STATE, N_ACTION))

    def set_T(a, s_from, s_to, p=1.0):
        B[s_to, s_from, a] += p

    for s in range(N_STATE):
        phase, loc = s_unpack(s)

        # --- movement actions: change loc, hold phase ---
        for a, dst in ((GO_ENTRANCE, ENTRANCE), (GO_TABLE, TABLE), (GO_BARISTA, BARISTA)):
            set_T(a, s, s_idx(phase, dst))

        # --- WAIT: identity, except the exogenous kitchen transition ---
        if phase == ORDERED:
            set_T(WAIT, s, s_idx(READY, loc), p_kitchen)
            set_T(WAIT, s, s, 1.0 - p_kitchen)
        else:
            set_T(WAIT, s, s)

        # --- service actions: advance phase iff at the right station, else identity ---
        def service(a, need_phase, need_loc, next_phase):
            if phase == need_phase and loc == need_loc:
                set_T(a, s, s_idx(next_phase, loc))
            else:
                set_T(a, s, s)  # no-op if precondition unmet

        service(SEAT,       EMPTY,   ENTRANCE, SEATED)
        service(TAKE_ORDER, SEATED,  TABLE,    ORDERED)
        service(MARK_READY, ORDERED, TABLE,    READY)    # sim parity; really exogenous
        # DELIVER carries the ready order from the barista to the table: the robot
        # ends AT THE TABLE (where DELIVERED is observable), not at the barista.
        if phase == READY and loc == BARISTA:
            set_T(DELIVER, s, s_idx(DELIVERED, TABLE))
        else:
            set_T(DELIVER, s, s)

    return B


# ---------------------------------------------------------------------------
# C : log-preference over observations — the goal replaces the `order` ranks
# ---------------------------------------------------------------------------
def build_C(reward: float = 4.0) -> np.ndarray:
    """Monotonic preference toward DELIVERED; AMBIGUOUS is mildly dispreferred
    (encourages disambiguation). Values are in log space (pymdp C convention)."""
    C = np.zeros(N_OBS)
    for phase in range(N_PHASE):
        C[phase] = reward * (phase / (N_PHASE - 1))  # 0 .. reward
    C[AMBIGUOUS] = -0.5
    return C


def build_D(prior_phase: int = EMPTY, prior_loc: int = ENTRANCE) -> np.ndarray:
    D = np.full(N_STATE, 1e-4)
    D[s_idx(prior_phase, prior_loc)] = 1.0
    D /= D.sum()
    return D


# ---------------------------------------------------------------------------
# Law-as-code seam — norms compile into (C, E, B-mask). See docs/aif_design.md.
# ---------------------------------------------------------------------------
@dataclass
class Norms:
    """Structured norms to be compiled in from the law-as-code front end.

    forbidden_actions : actions hard-masked (prior 0)        -> E / policy mask
    action_priors     : soft log-priors per action            -> E
    obs_penalties     : extra log-preference per observation   -> C
    """
    forbidden_actions: tuple[int, ...] = ()
    action_priors: dict[int, float] | None = None
    obs_penalties: dict[int, float] | None = None


def apply_norms(C: np.ndarray, norms: Norms) -> tuple[np.ndarray, np.ndarray]:
    """Return (C', E) with soft norms folded into preferences and a policy prior.
    Hard constraints (forbidden_actions) are returned as an action-level E prior;
    the coordinator multiplies it into q(pi) (or masks B) before action sampling."""
    C2 = C.copy()
    for o, pen in (norms.obs_penalties or {}).items():
        C2[o] += pen

    E = np.ones(N_ACTION)
    for a, lp in (norms.action_priors or {}).items():
        E[a] *= np.exp(lp)
    for a in norms.forbidden_actions:
        E[a] = 0.0
    E = E / E.sum() if E.sum() > 0 else np.full(N_ACTION, 1.0 / N_ACTION)
    return C2, E


def build_model(norms: Norms | None = None):
    """Convenience: return (A, B, C, D, E) ready for a pymdp Agent."""
    A, B, C, D = build_A(), build_B(), build_C(), build_D()
    C, E = apply_norms(C, norms or Norms())
    return A, B, C, D, E
