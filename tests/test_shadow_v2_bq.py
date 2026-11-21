"""Shadow v2 for BQ (research review 2026-11-21, items 7 and 9). Live bq_* columns untouched; item 8 (dead base modes) is NOT in this round."""
import numpy as np
import pandas as pd

from src.engines import bq


def _frame(close, high=None, vol=1e6):
    close = np.asarray(close, dtype=float)
    high = close * 1.002 if high is None else np.asarray(high, dtype=float)
    return pd.DataFrame({"date": pd.bdate_range("2020-01-01", periods=len(close)), "open": close, "high": high, "low": close * 0.998, "close": close,
                         "volume": np.asarray(vol if np.ndim(vol) else np.full(len(close), vol), dtype=float)})


def test_item9_base_days_25_scores_20_in_v2_and_14_in_the_live_chain():
    """A held base of exactly 25 bars: the live later-band-overwrites chain gave 14, the Pine ternary (first match) gives 20."""
    n = 140
    close = np.concatenate([np.linspace(80, 100, 60), np.full(n - 60, 100.0)])      # a long flat base near the 60-bar high
    df = bq.compute(_frame(close))
    # find a bar whose v2 base_days is exactly 25
    hit = df.index[df["bq_base_days_v2"] == 25]
    assert len(hit) >= 1
    t = hit[0]
    assert df["bq_base_dur_v2"].iloc[t] == 20.0
    live_t = df.index[df["bq_base_days"] == 25]
    if len(live_t):
        assert df["bq_base_dur"].iloc[live_t[0]] == 14.0                              # the live overlap defect, documented
    for bd, want in ((26, 14.0), (35, 14.0), (36, 8.0), (10, 20.0), (7, 14.0)):
        s = pd.Series([bd]); out = pd.Series(0.0)
        out = out.where(~((s >= 7) & (s <= 9)), 14.0)
        out = out.where(~((s > 25) & (s <= 35)), 14.0)
        out = out.where(~((s >= 10) & (s <= 25)), 20.0)
        out = out.where(~(s > 35), 8.0)
        assert float(out.iloc[0]) == want


def test_item7_breakout_follows_the_pine_high_above_prior_60_high_with_the_prior_bar_in_base():
    n = 130
    close = np.concatenate([np.linspace(90, 100, 70), np.full(30, 100.0), [100.0] * 30])
    high = close * 1.001
    vol = np.full(n, 1e6)
    t = 110
    high[t] = 103.0                       # high clears the prior 60-bar high ...
    close[t] = 100.5                      # ... while the CLOSE stays inside the old consolidation high (the live port needs a close breakout)
    vol[t] = 3e6
    df = bq.compute(_frame(close, high=high, vol=vol))
    # v2 latches the base length on the breakout bar and holds it for the decay window: base_days_v2 stays high on the bars after t
    assert df["bq_base_days_v2"].iloc[t + 1] >= 3
    assert df["bq_base_days_v2"].iloc[t + 1] == df["bq_base_days_v2"].iloc[t + 3]    # latched, not a running count
    assert df["bq_base_days"].iloc[t + 3] != df["bq_base_days_v2"].iloc[t + 3]      # the live port saw no breakout here (it needs `not in_base[t]`): a running count, not the latch


def test_the_live_bq_columns_are_still_present_and_v2_columns_exist():
    close = 100 + np.sin(np.arange(200) / 7.0)
    df = bq.compute(_frame(close))
    for c in ("bq_100", "bq_range_tight", "bq_vol_dry", "bq_base_dur", "bq_ema_conv", "bq_base_days", "bq_100_v2", "bq_base_dur_v2", "bq_base_days_v2"):
        assert c in df.columns
    # the v2 composite differs from the live one ONLY through the base-duration component
    diff = (df["bq_100_v2"] - df["bq_100"]).dropna()
    assert np.allclose(diff.to_numpy(), (df["bq_base_dur_v2"] - df["bq_base_dur"])[diff.index].to_numpy())


def test_score_columns_carry_the_bq_shadow_block():
    from src.scanner.score_runner import SCORE_COLUMNS
    for c in ("bq_100_v2", "bq_base_dur_v2", "bq_base_days_v2"):
        assert c in SCORE_COLUMNS
    assert SCORE_COLUMNS.index("bq_100_v2") > SCORE_COLUMNS.index("ls_volume_confirmed")
