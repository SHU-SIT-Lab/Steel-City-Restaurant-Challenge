"""Law-as-code: compile a service rule into the generative model, and show that
the *same* rule produces *different* behaviour as the restaurant state changes.

Decision: which of two waiting tables (A, B) to serve first. In active inference
the context enters through the **preferences C** (and precision), not through
`if` branches — so party size, wait time and how busy the kitchen is reshape the
same norm automatically.

Forces on the choice:
  - throughput  : serving a bigger party is worth more  (scales with `busy`)
  - fairness    : a precedence / FIFO norm — serving the later-arriving table
                  first is penalised in proportion to the wait-time gap and the
                  law's strength `fairness_lambda` (the strict-vs-flexible knob);
                  when slammed, fairness is relaxed in favour of throughput
  - priority    : an accessibility flag -> a hard preference for that table
  - hard mask   : optionally make "B before A" impossible (an inviolable rule)

These map to the (C, E, B-mask) seams in docs/aif_design.md. Run on Linux/WSL:
    python scripts/aif/law_as_code.py
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

# combined state = (served_A, served_B)
SNN, SYN, SNY, SYY = range(4)
N_STATE = 4
SERVE_A, SERVE_B = range(2)
N_ACTION = 2
ACTION_NAME = {SERVE_A: "A", SERVE_B: "B"}
GOAL_PREF = 50.0  # "both served" must dominate every intermediate bonus so the
                  # agent always *completes* service; the serve ORDER is then
                  # decided by the (smaller) intermediate C[A-first] vs C[B-first].


@dataclass
class Context:
    size_a: int = 3          # party size at table A
    size_b: int = 3          # party size at table B
    wait_a: float = 5.0      # minutes table A has waited
    wait_b: float = 5.0      # minutes table B has waited
    busy: float = 0.0        # kitchen load in [0, 1]
    fairness_lambda: float = 1.0   # strength of the precedence norm (the "law")
    priority_a: bool = False       # accessibility flag on table A
    hard_mask: bool = False        # inviolable: B cannot be served before A


def preferences(ctx: Context) -> np.ndarray:
    """Compile the rule + context into the preference vector C (the C-seam)."""
    throughput = 1.0 + ctx.busy                      # busy -> throughput matters more
    fairness = ctx.fairness_lambda * (1.0 - 0.5 * ctx.busy)  # busy -> relax fairness
    # serving X first "jumps the queue" only if the other table waited longer
    pen_a_first = fairness * max(ctx.wait_b - ctx.wait_a, 0.0)
    pen_b_first = fairness * max(ctx.wait_a - ctx.wait_b, 0.0)
    C = np.zeros(N_STATE)
    C[SYY] = GOAL_PREF
    C[SYN] = throughput * ctx.size_a - pen_a_first + (20.0 if ctx.priority_a else 0.0)
    C[SNY] = throughput * ctx.size_b - pen_b_first
    return C


def _make_agent(C: np.ndarray, hard_mask: bool, policy_len: int = 2, gamma: float = 16.0):
    import jax.numpy as jnp
    from pymdp.agent import Agent
    from pymdp.control import construct_policies

    A = np.eye(N_STATE)
    B = np.zeros((N_STATE, N_STATE, N_ACTION))
    for s, sp in {SNN: SYN, SNY: SYY, SYN: SYN, SYY: SYY}.items():
        B[sp, s, SERVE_A] = 1.0
    snn_b = SNN if hard_mask else SNY                # hard norm: B-before-A impossible
    for s, sp in {SNN: snn_b, SYN: SYY, SNY: SNY, SYY: SYY}.items():
        B[sp, s, SERVE_B] = 1.0
    policies = construct_policies([N_STATE], [N_ACTION], policy_len=policy_len, control_fac_idx=[0])
    return Agent(A=[jnp.array(A[None])], B=[jnp.array(B[None])], C=[jnp.array(C[None])],
                 D=[jnp.array(np.eye(N_STATE)[SNN][None, :])],
                 A_dependencies=[[0]], B_dependencies=[[0]],
                 num_controls=[N_ACTION], control_fac_idx=[0], policies=policies,
                 policy_len=policy_len, gamma=gamma, action_selection="deterministic",
                 inference_algo="fpi", num_iter=16, batch_size=1), B


def serve_order(ctx: Context) -> str:
    import jax
    import jax.numpy as jnp

    agent, B = _make_agent(preferences(ctx), ctx.hard_mask)
    Bm = np.asarray(B)
    s = SNN
    prior = list(agent.D)
    key = jax.random.PRNGKey(0)
    order = []
    for _ in range(2):
        qs = agent.infer_states([jnp.array([s])], prior)
        q_pi, _ = agent.infer_policies(qs)
        key, sub = jax.random.split(key)
        a = int(np.asarray(agent.sample_action(q_pi, rng_key=sub[None, :])).ravel()[0])
        order.append(ACTION_NAME[a])
        s = int(np.argmax(Bm[:, s, a]))
        prior = [jnp.array(np.eye(N_STATE)[s][None, :])]
        if s == SYY:
            break
    return ", ".join(order)


def _row(label: str, ctx: Context, driver: str) -> None:
    print(f"  {label:<42} order: {serve_order(ctx):<6}  {driver}")


def main() -> None:
    print('Law-as-code: rule = precedence/fairness ("serve who waited longest"),')
    print("reshaped by party size, wait time and busyness via the preferences C.\n")

    print("Context-sensitive serving:")
    _row("equal tables", Context(), "tie -> arrival order")
    _row("B has the bigger party (A=2, B=6)",
         Context(size_a=2, size_b=6), "throughput -> serve B")
    _row("A waited much longer (A=12m, B=3m)",
         Context(wait_a=12, wait_b=3), "fairness -> serve A")
    print()
    print("  conflict: A waited longer (12 vs 3) BUT B is a big party (A=2, B=6)")
    _row("    quiet kitchen (busy=0.0)",
         Context(size_a=2, size_b=6, wait_a=12, wait_b=3, busy=0.0), "fairness holds -> A")
    _row("    slammed kitchen (busy=1.0)",
         Context(size_a=2, size_b=6, wait_a=12, wait_b=3, busy=1.0), "throughput wins -> B")
    print()
    _row("A flagged priority/accessibility",
         Context(size_a=2, size_b=6, wait_a=3, wait_b=12, priority_a=True), "hard priority -> A")
    _row("hard mask: B-before-A forbidden",
         Context(size_a=2, size_b=6, hard_mask=True), "inviolable -> A")

    print("\nThe law's strength is a precision knob (fairness_lambda) on the same conflict")
    print("(A waited 12 vs 3, B bigger party 2 vs 6, quiet):")
    for lam in (0.0, 0.5, 1.0, 2.0):
        ctx = Context(size_a=2, size_b=6, wait_a=12, wait_b=3, busy=0.0, fairness_lambda=lam)
        order = serve_order(ctx)
        print(f"    fairness_lambda={lam:<4} -> order: {order:<6} "
              f"({'fairness' if order.startswith('A') else 'throughput'})")


if __name__ == "__main__":
    main()
