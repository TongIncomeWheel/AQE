"""Tests for the anchored VWAP engine (src/engines/anchored_vwap.py) —
flexible-anchor VWAP, run forward from a structural pivot or swing low
rather than a rolling window or the session open."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.anchored_vwap import compute_anchored_vwap

# Declining to a trough at idx 14 (the swing low), rising to a confirmed
# pivot high at idx 25, then wobbling -- enough bars after idx 25 (k=5) to
# confirm that pivot, and enough bars after that to anchor a VWAP from it.
_HIGHS = [
    140, 138, 136, 134, 132, 130, 128, 126, 124, 122, 120, 118, 116, 114, 112,
    116, 120, 124, 128, 132, 136, 140, 144, 148, 152, 160,
    150, 148, 146, 144, 142,
    141, 139, 143, 137, 145, 133, 147, 131, 149, 129,
]


def _bars(highs=None, last_high=None) -> pd.DataFrame:
    h = np.array(_HIGHS if highs is None else highs, dtype=float)
    if last_high is not None:
        h[-1] = last_high
    n = len(h)
    dates = pd.bdate_range("2026-06-01", periods=n)
    return pd.DataFrame({
        "date": dates, "high": h, "low": h - 6.0, "close": h - 3.0,
        "volume": np.full(n, 1000.0),
    })


def test_structure_anchor_finds_the_confirmed_pivot_and_its_date():
    out = compute_anchored_vwap(_bars())
    assert out["avwap_structure_date"] == "2026-07-06"   # idx 25, the peak
    assert out["avwap_structure_bars"] == 16


def test_swing_anchor_finds_the_up_swings_launchpad_low():
    out = compute_anchored_vwap(_bars())
    assert out["avwap_swing_date"] == "2026-06-19"        # idx 14, the trough
    assert out["avwap_swing_bars"] == 27


def test_both_anchors_report_below_when_price_has_since_rolled_over():
    out = compute_anchored_vwap(_bars())
    assert out["avwap_structure_position"] == "BELOW"
    assert out["avwap_swing_position"] == "BELOW"
    assert out["avwap_structure"] == 139.75
    assert out["avwap_swing"] == 135.37


def test_both_anchors_flip_above_on_a_fresh_spike():
    out = compute_anchored_vwap(_bars(last_high=250.0))
    assert out["avwap_structure_position"] == "ABOVE"
    assert out["avwap_swing_position"] == "ABOVE"


def test_too_few_bars_degrades_to_null():
    out = compute_anchored_vwap(_bars().iloc[:10])
    assert out["avwap_structure"] is None
    assert out["avwap_swing"] is None


def test_none_input_degrades_to_null():
    out = compute_anchored_vwap(None)
    assert out["avwap_structure"] is None
    assert out["avwap_swing"] is None


def test_missing_required_column_degrades_to_null():
    out = compute_anchored_vwap(_bars().drop(columns=["volume"]))
    assert out["avwap_structure"] is None
    assert out["avwap_swing"] is None


def test_zero_volume_degrades_to_null_not_a_fabricated_level():
    df = _bars()
    df["volume"] = 0.0
    out = compute_anchored_vwap(df)
    assert out["avwap_structure"] is None
    assert out["avwap_swing"] is None


def test_no_structure_or_swing_yet_leaves_both_anchors_null():
    """A strictly declining series has no confirmed pivot high (the true
    local max of any window is always its left edge, never the centre) and
    no up-swing (the overall peak sits at bar 0, leaving no room for a
    launchpad) -- both anchors must stay null rather than fabricate one."""
    n = 20
    highs = [200.0 - i for i in range(n)]
    dates = pd.bdate_range("2026-06-01", periods=n)
    declining = pd.DataFrame({"date": dates, "high": highs,
                              "low": [h - 1.0 for h in highs],
                              "close": [h - 0.5 for h in highs],
                              "volume": [1000.0] * n})
    out = compute_anchored_vwap(declining)
    assert out["avwap_structure"] is None
    assert out["avwap_swing"] is None


def test_never_raises_on_malformed_values():
    df = _bars()
    df.loc[df.index[-1], "close"] = float("nan")
    out = compute_anchored_vwap(df)  # must not raise
    assert "avwap_structure" in out and "avwap_swing" in out
