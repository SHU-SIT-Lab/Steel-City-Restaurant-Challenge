"""Reactive vs Active Inference — run the same service scenarios through both
decision cores and compare them.

  - Reactive  (scripts/reactive_sim/): the original hand-coded argmax-priority
    arbiter over the 7 behaviors.
  - AIF        (scripts/aif/):         the EFE-minimising agent over the 6
    competition phases (+ the law-as-code customer ordering in V2).

Run on Linux/WSL (the AIF side needs JAX):
    python scripts/compare/compare.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "reactive_sim"))
sys.path.insert(0, str(ROOT / "scripts" / "aif"))


def run_reactive_single(max_ticks: int = 60):
    """One customer through the reactive coordinator. Returns (served, ticks, seq)."""
    import coordinator as rc
    from sim_state import SimRestaurant

    db = SimRestaurant(number_of_tables=5)
    db.script_customer_arrival(party_size=1)
    coord = rc.ReactiveCoordinator(db)
    behaviors = []
    for t in range(max_ticks):
        ran = coord.step()
        if ran:
            behaviors.append(ran)
        if any(tbl.order_delivered for tbl in db.list_tables()):
            seq = [b for i, b in enumerate(behaviors) if i == 0 or behaviors[i - 1] != b]
            return True, t + 1, seq
    return False, max_ticks, behaviors


def run_aif_single(seed: int = 0, max_steps: int = 18):
    """One customer through the AIF phase agent. Returns (served, steps, actions)."""
    import game_phases as gp

    rng = np.random.default_rng(seed)
    waiter = gp.PhaseWaiter(seed=seed)
    A, B = gp.build_A(), gp.build_B()
    s = gp.s_idx(gp.DETECTED, gp.ENTRANCE)
    actions = []
    for t in range(max_steps):
        o = int(rng.choice(gp.N_OBS, p=A[:, s]))
        a = waiter.act(o)
        actions.append(gp.ACTIONS[a])
        s = int(np.argmax(B[:, s, a]))
        if gp.s_unpack(s)[0] == gp.STANDBY:
            return True, t + 1, actions
    return False, max_steps, actions


def aif_order(custs, busy: float, lam: float = 1.0):
    import game_phases_multi as gpm
    return [c.name for c in gpm.law_order(custs, busy=busy, fairness_lambda=lam)]


def main() -> None:
    line = "=" * 72
    print(line)
    print("REACTIVE (argmax priorities)   vs   ACTIVE INFERENCE (min EFE)")
    print(line)

    print("\n# Scenario 1 — one customer, full service cycle")
    r_ok, r_ticks, r_seq = run_reactive_single()
    a_ok, a_steps, a_seq = run_aif_single()
    print(f"  reactive : served={r_ok}  ticks={r_ticks}")
    print(f"             {' -> '.join(r_seq)}")
    print(f"  AIF      : served={a_ok}  steps={a_steps}")
    print(f"             {' -> '.join(a_seq)}")
    print("  note: tick vs step counts are NOT apples-to-apples — the reactive loop")
    print("        re-evaluates all behaviors each tick; AIF steps are phase actions.")
    print("        Both complete the service cycle.")

    print("\n# Scenario 2 — who to serve first? (3 customers, with context)")
    import game_phases_multi as gpm
    a, b, c = gpm.Customer("A", 2, 12), gpm.Customer("B", 6, 3), gpm.Customer("C", 3, 7)
    bp = gpm.Customer("B", 6, 3, priority=True)
    print("  customers: A(party 2, waited 12m)  B(party 6, waited 3m)  C(party 3, waited 7m)")
    print("  reactive : A -> B -> C   (arrival/FIFO — party size & wait time are not")
    print("             even inputs to the reactive behaviors; no precedence concept)")
    print(f"  AIF V2 quiet    : {' -> '.join(aif_order([a, b, c], 0.0))}   (law: fairness — longest wait)")
    print(f"  AIF V2 slammed  : {' -> '.join(aif_order([a, b, c], 1.0))}   (law: throughput — big party)")
    print(f"  AIF V2 B=priority: {' -> '.join(aif_order([a, bp, c], 0.0))}   (law: accessibility — hard)")
    print("  -> reactive serves FIFO; AIF re-orders by a context-sensitive law.")

    print("\n# Conceptual")
    print("  arbitration  reactive = argmax(order x precondition)  |  AIF = argmin EFE")
    print("  observation  reactive = facts from DB/sensors         |  AIF = noisy, location-gated (must look)")
    print("  epistemics   reactive = none                          |  AIF = information gain (look when unsure)")
    print("  norms / law  reactive = hand-coded if-branches        |  AIF = compiled (C, E, B-mask) + precision knob")
    print("  tuning       reactive = hand-set priority ranks       |  AIF = preferences C (+ the model)")


if __name__ == "__main__":
    main()
