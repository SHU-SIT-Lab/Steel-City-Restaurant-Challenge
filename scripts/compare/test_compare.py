"""Tests for the reactive-vs-AIF comparison harness.

Run on Linux/WSL (the AIF side needs JAX):
    python3 -m pytest scripts/compare/test_compare.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare  # noqa: E402  (also sets up reactive_sim + aif import paths)


def test_both_decision_cores_serve_one_customer():
    r_ok, r_ticks, r_seq = compare.run_reactive_single()
    a_ok, a_steps, a_seq = compare.run_aif_single()
    assert r_ok, "reactive failed to serve the customer"
    assert a_ok, "AIF failed to serve the customer"
    assert "collect_order" in r_seq      # reactive reached the deliver behavior
    assert a_seq[-1] == "RETURN"         # AIF finished the cycle (Phase 6)


def test_aif_is_context_sensitive_reactive_is_not():
    import game_phases_multi as gpm
    custs = [gpm.Customer("A", 2, 12), gpm.Customer("B", 6, 3), gpm.Customer("C", 3, 7)]
    quiet = compare.aif_order(custs, 0.0)
    slammed = compare.aif_order(custs, 1.0)
    # AIF re-orders with context; the reactive system serves FIFO (no context inputs)
    assert quiet != slammed
    assert quiet[0] == "A"               # fairness: longest-waiting first
    assert slammed[0] == "B"             # throughput: big party first when busy
