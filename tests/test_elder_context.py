"""Tests for the Elder Context engine (Instruction v1.1)."""

from __future__ import annotations

from datetime import datetime, timedelta

from src.engines.elder_context import elder_pattern, compute_elder_context


def test_elder_pattern_spec_examples():
    cases = {
        "ACCUMULATION_BASE": [[3, 5, 6, 7, 8], [5, 6, 7, 7, 8]],
        "ACCELERATION": [[5, 7, 10, 10, 10], [4, 6, 9, 10, 10]],
        "CORRECTION_REENTRY": [[10, 10, 10, 7, 10], [8, 10, 5, 10, 10], [10, 7, 8, 9, 10]],
        "SUSTAINED": [[9, 10, 10, 10, 10], [10, 10, 10, 10, 10]],
        "INTERRUPTED": [[7, 3, 2, 5, 8]],
    }
    for want, arrs in cases.items():
        for a in arrs:
            assert elder_pattern(a) == want, f"{a} -> {elder_pattern(a)} (want {want})"


def test_elder_pattern_degrades():
    assert elder_pattern([]) is None
    assert elder_pattern([10]) is None


def _daily(n=20, base=100.0):
    out = []
    d = datetime(2026, 6, 1)
    for i in range(n):
        c = base + i * 0.1
        out.append({"date": (d + timedelta(days=i)).strftime("%Y-%m-%d"),
                    "open": c, "high": c + 1, "low": c - 1, "close": c,
                    "volume": 1_000_000})
    return out


def _hourly(n=35, base=100.0, up=True):
    out = []
    d = datetime(2026, 6, 16, 9, 30)
    for i in range(n):
        c = base + (i * 0.05 if up else -i * 0.05)
        o = c - 0.1 if up else c + 0.1
        out.append({"date": (d + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S"),
                    "open": o, "high": max(o, c) + 0.1, "low": min(o, c) - 0.1,
                    "close": c, "volume": 100_000 + i * 1000})
    return out


def test_compute_elder_context_full_block():
    ctx = compute_elder_context([10, 10, 10, 7, 10], _hourly(), _daily(),
                                resistance_price=200.0)
    assert ctx["elder_pattern"] == "CORRECTION_REENTRY"
    assert ctx["vwap_5d"]["value"] is not None
    assert ctx["vwap_5d"]["position"] in ("ABOVE", "BELOW")
    assert ctx["volume"]["avg_vol_20d"] is not None
    assert ctx["vcp"]["vcp_label"] in ("VCP_SETUP", "VCP_PARTIAL", "VCP_ABSENT")
    assert ctx["exhaustion_check"]["exhaustion_flag"] in ("CLEAR", "CAUTION", "RISK")


def test_compute_elder_context_no_hourly():
    """Daily-only path (export): hourly fields None, daily/VCP still present."""
    ctx = compute_elder_context([3, 5, 6, 7, 8], [], _daily())
    assert ctx["elder_pattern"] == "ACCUMULATION_BASE"
    assert ctx["vwap_5d"]["value"] is None          # no hourly bars
    assert ctx["hourly_bars_used"] == 0
    assert ctx["vcp"]["base_range_pct"] is not None  # daily VCP computed
