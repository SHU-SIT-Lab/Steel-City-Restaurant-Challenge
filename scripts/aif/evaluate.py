"""Quick evaluation of the AIF waiter beyond the single-run demo.

Runs the headless service episode over many seeds and reports success rate and
steps-to-serve, both with the environment matched to the agent's model and with
a noisier environment (model mismatch / robustness).

Run on Linux/WSL:  python scripts/aif/evaluate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generative_model as gm  # noqa: E402
from aif_coordinator import AIFWaiter  # noqa: E402

LOOK_ACTIONS = {gm.GO_ENTRANCE, gm.GO_TABLE, gm.GO_BARISTA}


def episode(seed: int, max_steps: int = 20, env_sharp: float = 0.9):
    """One service episode. env_sharp < 0.9 = noisier than the agent's model."""
    rng = np.random.default_rng(seed)
    waiter = AIFWaiter(seed=seed)            # agent's internal A uses sharp=0.9
    A = gm.build_A(sharp=env_sharp)          # the *environment's* observation noise
    B = gm.build_B()
    s = gm.s_idx(gm.EMPTY, gm.ENTRANCE)
    looks = 0
    for t in range(max_steps):
        o = int(rng.choice(gm.N_OBS, p=A[:, s]))
        a = waiter.act(o)
        looks += int(a in LOOK_ACTIONS)
        s = int(rng.choice(gm.N_STATE, p=B[:, s, a]))
        if gm.s_unpack(s)[0] == gm.DELIVERED:
            return True, t + 1, looks
    return False, max_steps, looks


def summarise(label: str, results: list[tuple[bool, int, int]], n: int) -> None:
    succ = [r for r in results if r[0]]
    steps = [r[1] for r in succ]
    looks = [r[2] for r in results]
    if succ:
        print(f"{label:<22} success={len(succ)}/{n}  steps: min={min(steps)} "
              f"mean={np.mean(steps):.1f} max={max(steps)}  avg look/ep={np.mean(looks):.1f}")
    else:
        print(f"{label:<22} success=0/{n}")


def main(n: int = 10) -> None:
    print(f"AIF waiter evaluation — {n} seeds (optimal serve = 6 steps)\n")
    summarise("matched (sharp=0.9)", [episode(s, env_sharp=0.9) for s in range(n)], n)
    summarise("noisy env (sharp=0.6)", [episode(s, env_sharp=0.6) for s in range(n)], n)


if __name__ == "__main__":
    main()
