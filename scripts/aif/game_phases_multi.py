"""V2 — multi-customer AIF over the six EMSRC phases, with a law-as-code rule
deciding WHO is served first. Builds on game_phases.py (V1).

Two levels (hierarchical):
  - HIGH (law-as-code): a precedence/fairness rule, compiled into a serving-
    priority score and reshaped by party size, wait time, busyness and an
    accessibility flag, orders the waiting customers.
  - LOW (active inference): each customer is served through the six competition
    phases by the V1 EFE agent (game_phases).

Scoring follows the rulebook: a full six-phase cycle per customer is 1200 base
points, and "serve multiple customers in a single run" is the +200 bonus.

Run on Linux/WSL:  python scripts/aif/game_phases_multi.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import game_phases as gp  # noqa: E402

MULTI_CUSTOMER_BONUS = 200   # rulebook: serve multiple customers in a single run
FULL_CYCLE = int(gp.CUM_POINTS[-1])  # 1200 base points per fully-served customer


@dataclass
class Customer:
    name: str
    size: int = 2          # party size
    wait: float = 5.0      # minutes waited
    priority: bool = False  # accessibility / priority flag


def law_score(c: Customer, busy: float = 0.0, fairness_lambda: float = 1.0) -> float:
    """The serving-precedence LAW, compiled into a score (higher = serve sooner).
    throughput rewards bigger parties (amplified when busy); fairness rewards
    longer waits (relaxed when busy); an accessibility flag is a hard priority."""
    throughput = (1.0 + busy) * c.size
    fairness = fairness_lambda * (1.0 - 0.5 * busy) * c.wait
    return throughput + fairness + (1000.0 if c.priority else 0.0)


def law_order(customers, busy: float = 0.0, fairness_lambda: float = 1.0):
    return sorted(customers, key=lambda c: law_score(c, busy, fairness_lambda), reverse=True)


def serve_one(seed: int = 0, max_steps: int = 16) -> bool:
    """Serve one customer through the six phases via the V1 EFE agent."""
    import jax
    import jax.numpy as jnp

    agent = gp.make_agent()
    B = gp.build_B()
    key = jax.random.PRNGKey(seed)
    s = gp.s_idx(gp.DETECTED, gp.ENTRANCE)
    prior = list(agent.D)
    for _ in range(max_steps):
        qs = agent.infer_states([jnp.array([s])], prior)
        q_pi, _ = agent.infer_policies(qs)
        key, sub = jax.random.split(key)
        a = int(np.asarray(agent.sample_action(q_pi, rng_key=sub[None, :])).ravel()[0])
        s = int(np.argmax(B[:, s, a]))
        prior = [jnp.array(np.eye(gp.N_STATE)[s][None, :])]
        if gp.s_unpack(s)[0] == gp.STANDBY:
            return True
    return False


def run(customers, busy: float = 0.0, fairness_lambda: float = 1.0, label: str = "") -> None:
    order = law_order(customers, busy, fairness_lambda)
    served = sum(serve_one(seed=i) for i in range(len(order)))
    base = served * FULL_CYCLE
    bonus = MULTI_CUSTOMER_BONUS if served > 1 else 0
    names = " -> ".join(c.name for c in order)
    print(f"  {label:<34} order: {names:<14} served {served}  "
          f"score {base + bonus} ({served}x{FULL_CYCLE} + {bonus} bonus)")


def main() -> None:
    print("Law-as-code decides WHO to serve; AIF serves each through the 6 phases.\n")
    base = [Customer("A", size=2, wait=12),   # small party, waited longest
            Customer("B", size=6, wait=3),    # big party, just arrived
            Customer("C", size=3, wait=7)]
    run(base, busy=0.0, label="quiet kitchen (fairness)")
    run(base, busy=1.0, label="slammed kitchen (throughput)")
    run([Customer("A", 2, 12), Customer("B", 6, 3, priority=True), Customer("C", 3, 7)],
        label="B flagged priority/accessibility")
    print("\nSame customers, same law — the order changes with context (busyness flips")
    print("fairness<->throughput; an accessibility flag is a hard priority). Each served")
    print("customer is a full six-phase AIF cycle; +200 for serving multiple in one run.")


if __name__ == "__main__":
    main()
