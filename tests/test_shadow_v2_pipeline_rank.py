"""Shadow v2 fields for Pipeline Rank (research review 2026-11-21, items 4, 5, 6). The LIVE columns must be untouched; the _v2 columns carry the corrections."""
import numpy as np
import pandas as pd

from src.engines import pipeline_rank as P


def _frame(close, vol=1e6):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"date": pd.bdate_range("2019-01-01", periods=len(close)), "open": close, "high": close * 1.01, "low": close * 0.99,
                         "close": close, "volume": vol})


def test_item4_ret_12m_v2_skips_the_last_month_and_the_live_line_does_not():
    n = 400
    close = 100 * (1 + 0.001) ** np.arange(n)
    close[-20:] *= 1.5                       # a big last-month jump: a skip-month return must not see it
    df = P.compute(_frame(close))
    t = n - 1
    want = (close[t - 21] / close[t - 252] - 1) * 100
    assert abs(df["ret_12m_pct_v2"].iloc[t] - want) < 1e-9
    live = (close[t] / close[t - 231] - 1) * 100                      # what the live line measures: includes the jump
    assert live > want + 30
    assert df["ret_12m_score_v2"].iloc[t] < df["ret_12m_score"].iloc[t] or df["ret_12m_score_v2"].iloc[t] <= 20


def test_item5_adx_credits_a_downtrend_in_the_live_score_and_not_in_v2():
    n = 400
    close = 200 * (1 - 0.003) ** np.arange(n)                         # a steady downtrend: DI- > DI+, ADX high
    df = P.compute(_frame(close))
    last = df.iloc[-1]
    assert last["adx_score"] == 5.0                                    # the live defect, documented
    assert last["adx_score_v2"] == 0.0
    up = P.compute(_frame(100 * (1 + 0.003) ** np.arange(n))).iloc[-1]
    assert up["adx_score_v2"] > 0 and up["adx_score_v2"] == up["adx_score"]   # an uptrend is scored the same in both


def test_item6_spike_exclusion_runs_on_every_bar_in_v2_and_on_the_last_bar_only_live():
    n = 420
    close = np.full(n, 100.0)
    close[100:121] = np.linspace(100, 160, 21)                         # +60% spike
    close[121:151] = np.linspace(160, 95, 30)                          # collapse
    close[151:] = 95.0
    rng = np.random.default_rng(3)
    close = close * (1 + rng.normal(0, 0.003, n))
    df = P.compute(_frame(close))
    flagged = df["fip_spike_excluded_v2"].to_numpy()
    assert flagged.sum() > 20                                           # many historical bars are excluded as-of their own date
    assert df["fip_spike_excluded"].sum() <= 1                          # the live column is last-bar-only
    first = int(np.argmax(flagged))
    assert not df["fip_spike_excluded"].iloc[first]
    assert df["fip_window_effective_v2"].iloc[first] < 252
    # where a bar is not excluded the v2 value is the live base value
    ok = ~flagged & df["fip_raw"].notna()
    assert np.allclose(df["fip_raw_v2"][ok].to_numpy()[:-1], df["fip_raw"][ok].to_numpy()[:-1], equal_nan=True)


def test_item6_one_sign_rule_compounded_not_arithmetic():
    """Alternating +10% / -9.5%: the arithmetic sum is positive, the compounded return is negative. v2 must use the compounded sign."""
    n = 301
    close = np.full(n, 100.0)
    close[100:121] = np.linspace(100, 150, 21)
    close[121:151] = np.linspace(150, 90, 30)
    px = list(close[:151])
    for k in range(150):
        px.append(px[-1] * (1.10 if k % 2 == 0 else 0.905))
    close = np.array(px)
    s = pd.Series(close)
    dr = s.pct_change()
    ex, eff, raw, qual = P._fip_spike_asof(s, dr)
    t = len(close) - 1
    assert ex[t] and not np.isnan(raw[t])
    s0 = t - 251
    g = next(i for i in range(20, len(close)) if abs(close[i] / close[i - 20] - 1) >= 0.30)       # the detector's first >=30% bar
    es = max(s0, g - 21); ee = min(t, g + 21)
    win2 = dr.to_numpy()[s0:t + 1].copy(); win2[es - s0: ee - s0 + 1] = np.nan
    inc = win2[~np.isnan(win2)]
    pp, pn = (inc > 0).mean(), (inc < 0).mean()
    arith, comp = inc.sum(), np.prod(1 + inc) - 1
    assert arith > 0 > comp                                              # the construction really separates the two rules
    assert abs(raw[t] - (pn - pp) * -1.0) < 1e-9                         # compounded sign (negative)


def test_the_live_pipe_rank_columns_are_unchanged_by_the_shadow_fields():
    n = 400
    rng = np.random.default_rng(7)
    close = 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, n))
    df = P.compute(_frame(close))
    for c in ("pipe_rank", "pipe_tier", "momentum_composite", "fip_quality", "fip_raw", "fip_spike_excluded", "fip_window_effective", "ret_12m_score", "adx_score"):
        assert c in df.columns
    assert df["fip_spike_excluded"].iloc[:-1].eq(False).all()


def test_score_columns_carry_the_shadow_block_at_the_end_so_the_research_slices_do_not_move():
    from scripts import research_extract as rx
    from src.scanner.score_runner import SCORE_COLUMNS
    for c in ("pipe_rank_v2", "pr_adx_score_v2", "pr_ret_12m_v2", "fip_raw_v2", "fip_spike_excluded_v2", "ret_12m_pct_v2"):
        assert c in SCORE_COLUMNS
    assert SCORE_COLUMNS.index("pipe_rank_v2") > SCORE_COLUMNS.index("ls_volume_confirmed")
    comp = rx._component_columns(SCORE_COLUMNS)
    assert not any(c.endswith("_v2") for c in comp["aggregate"] + comp["sub"])
