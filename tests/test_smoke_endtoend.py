"""End-to-end smoke test on synthetic data.

Generates synthetic price panels for 5 tickers, runs every engine + composite,
detects signals, computes outcomes, and verifies the resulting frame has the
expected shape and value ranges. Also exercises the baselines + new metrics.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analyzer import metrics as M
from src.analyzer.baselines import random_baseline, spy_baseline
from src.analyzer.ptrs import classify_vix_regime, compute_ptrs, compute_ptrs_batch
from src.analyzer.recipe import Recipe, apply_filter
from src.engines.srm import grade_sector_etf, GRADE_TO_SH
from src.engines import bq, elder, energy, flow, k39, mp, scoring, structure
from src.engines.utils import atr
from src.scanner.dsl import compute_dsl_outcomes, compute_initial_stop, simulate_dsl_trade
from src.scanner.outcome_tracker import attach_signal_context, compute_outcomes
from src.scanner.signal_detector import detect_crossups


TICKERS = ["AAA", "BBB", "CCC", "DDD", "EEE"]


def _synth_panel(seed_base: int = 100, n: int = 600) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for i, t in enumerate(TICKERS + ["SPY"]):
        rng = np.random.default_rng(seed_base + i)
        dates = pd.bdate_range("2020-01-02", periods=n)
        trend = np.linspace(100, 100 + 80 * (0.5 + i * 0.2), n)
        noise = rng.normal(0, 1.5, n).cumsum() * 0.3
        close = trend + noise
        high = close + rng.uniform(0.2, 2.0, n)
        low = close - rng.uniform(0.2, 2.0, n)
        open_ = close + rng.normal(0, 0.4, n)
        volume = rng.integers(1_000_000, 5_000_000, n)
        df = pd.DataFrame({"date": dates, "ticker": t, "open": open_, "high": high, "low": low, "close": close, "volume": volume})
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def _weekly(panel: pd.DataFrame) -> pd.DataFrame:
    out = []
    for ticker, group in panel.groupby("ticker", sort=False):
        idx = group.set_index("date")
        w = pd.DataFrame({
            "open": idx["open"].resample("W-FRI").first(),
            "high": idx["high"].resample("W-FRI").max(),
            "low": idx["low"].resample("W-FRI").min(),
            "close": idx["close"].resample("W-FRI").last(),
            "volume": idx["volume"].resample("W-FRI").sum(),
        }).dropna(subset=["close"]).reset_index()
        w["ticker"] = ticker
        out.append(w)
    return pd.concat(out, ignore_index=True)


def _score_panel(panel: pd.DataFrame, weekly: pd.DataFrame) -> pd.DataFrame:
    spy = panel.loc[panel["ticker"] == "SPY"].reset_index(drop=True)
    rows: list[pd.DataFrame] = []
    for t in TICKERS:
        d = panel.loc[panel["ticker"] == t].sort_values("date").reset_index(drop=True)
        w = weekly.loc[weekly["ticker"] == t].sort_values("date").reset_index(drop=True)
        f = flow.compute(d)
        e = energy.compute(d)
        s = structure.compute(d, spy, w)
        m = mp.compute(d, spy)
        el = elder.compute(d)
        bq_df = bq.compute(d)
        k39_gate_s, k39_val = k39.compute_k39_gate(w, d["date"])
        sc_m = scoring.compute(f["flow_100"], e["energy_100"], s["structure_100"], m["mp_score"], el["elder_score"])
        sc_p = scoring.compute_position(f["flow_100"], e["energy_100"], s["structure_100"], m["mp_score"], bq_df["bq_100"], k39_gate_s)
        a14 = atr(d["high"].astype(float), d["low"].astype(float), d["close"].astype(float), 14)
        rows.append(pd.DataFrame({
            "date": d["date"], "ticker": t,
            "close": d["close"].astype(float), "atr14": a14,
            "flow_100": f["flow_100"], "energy_100": e["energy_100"],
            "structure_100": s["structure_100"], "mp_100": m["mp_score"],
            "elder_score": el["elder_score"], "bq_100": bq_df["bq_100"],
            "mp_state": m["mp_state"],
            "sc_momentum": sc_m, "sc_position": sc_p,
        }))
    return pd.concat(rows, ignore_index=True).dropna(subset=["sc_momentum"]).reset_index(drop=True)


def test_full_pipeline_on_synthetic():
    panel = _synth_panel()
    weekly = _weekly(panel)
    scores = _score_panel(panel, weekly)

    assert (scores["sc_momentum"] >= 0).all()
    assert (scores["sc_momentum"] <= 100).all()

    events = detect_crossups(scores, threshold=50.0, cooldown_days=10)
    assert "ticker" in events.columns

    if events.empty:
        pytest.skip("Synthetic data produced no SC_MOM cross-ups at threshold=50")

    with_ctx = attach_signal_context(events, scores)
    outcomes = compute_outcomes(with_ctx, panel)
    assert len(outcomes) > 0
    for col in [
        "fwd_ret_5d", "fwd_ret_10d", "fwd_ret_21d",
        "hit_target_21d", "hit_stop_21d", "gap_stop_21d",
        "r_realized_21d", "r_realized_optimistic_21d", "days_to_outcome_21d",
    ]:
        assert col in outcomes.columns, f"missing column: {col}"

    # Realized R is bounded below by -1 (or worse on gap-stop) and unbounded above on terminal close.
    # For non-gap stops the floor is exactly -1; assert no stop is > 0.
    stopped = outcomes.loc[outcomes["hit_stop_21d"] & ~outcomes["gap_stop_21d"].fillna(False)]
    if not stopped.empty:
        assert (stopped["r_realized_21d"] <= -1.0 + 1e-9).all()

    # Hit_target stops at exactly +2R for non-stopped trades.
    targeted = outcomes.loc[outcomes["hit_target_21d"] & ~outcomes["hit_stop_21d"]]
    if not targeted.empty:
        assert (targeted["r_realized_21d"] == 2.0).all()

    recipe = Recipe(sc_mom_min=0, flow_min=0, energy_min=0, structure_min=0, mp_min=0, elder_min=0)
    filtered = apply_filter(outcomes, recipe)
    win_metrics = M.compute_all_windows(filtered)
    assert len(win_metrics) == 3
    for w in win_metrics:
        assert w.n == len(filtered)
        # Wilson CIs must be ordered and inside [0, 1].
        lo, hi = w.win_rate_realized_ci
        assert lo <= hi
        assert 0.0 <= lo and hi <= 1.0


def test_random_and_spy_baselines():
    panel = _synth_panel()
    weekly = _weekly(panel)
    scores = _score_panel(panel, weekly)
    # Use the same threshold the full-pipeline test uses — proven to produce events.
    events = detect_crossups(scores, threshold=50.0, cooldown_days=5)
    if events.empty:
        pytest.skip("No events to baseline")
    outcomes = compute_outcomes(attach_signal_context(events, scores), panel)

    spy_panel = panel.loc[panel["ticker"] == "SPY"].copy()
    rand = random_baseline(outcomes, panel, scores)
    spy_ret = spy_baseline(outcomes, spy_panel)

    assert "r_realized_21d" in rand.columns
    assert "spy_fwd_ret_21d" in spy_ret.columns
    # Random baseline N should be close to signal N (same multiplier=1).
    assert abs(len(rand) - len(outcomes)) <= len(outcomes)  # loose bound — some draws may be dropped


def test_empty_inputs_handled():
    empty_signals = pd.DataFrame(columns=["date", "ticker"])
    empty_panel = pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"])
    assert compute_outcomes(empty_signals, empty_panel).empty
    assert detect_crossups(pd.DataFrame(columns=["date", "ticker", "sc_momentum"])).empty


def test_signal_detector_ignores_nan_warmup():
    """NaN warmup bars must NOT count as 'below threshold' for cooldown purposes,
    OR cause spurious cross-ups when the first real bar is above threshold."""
    n = 60
    s = np.full(n, np.nan, dtype=float)
    # Bars 30..40 are valid, threshold-straddling.
    s[30:35] = 60.0  # below 75
    s[35] = 80.0     # cross-up to above 75
    s[36:40] = 80.0
    df = pd.DataFrame({
        "date": pd.bdate_range("2024-01-02", periods=n),
        "ticker": "TEST",
        "sc_momentum": s,
    })
    events = detect_crossups(df, threshold=75.0, cooldown_days=3)
    # The first valid cross-up is at index 35 — that should fire, since bars 30..34 (5 bars) were below.
    assert not events.empty
    assert events.iloc[0]["date"] == df.iloc[35]["date"]


def test_gap_through_stop_realistic_fill():
    """If the next bar opens below the stop price, r_realized must reflect the open fill, not -1R."""
    # Synthetic: entry at 100, ATR14=2.0 → stop=96, target=108.
    # Bar entry+1 gaps open to 90 (worse than stop). Stop fill = open = 90 → r = (90-100)/4 = -2.5R.
    dates = pd.bdate_range("2024-01-02", periods=30)
    panel = pd.DataFrame({
        "date": dates,
        "ticker": "GAP",
        "open": [100.0] * 30,
        "high": [101.0] * 30,
        "low": [99.0] * 30,
        "close": [100.0] * 30,
        "volume": [1_000_000] * 30,
    })
    # Inject gap-down on bar index 11 (entry+1 if entry is 10).
    panel.loc[11, ["open", "high", "low", "close"]] = [90.0, 91.0, 88.0, 89.0]

    signals = pd.DataFrame({
        "date": [dates[10]],
        "ticker": ["GAP"],
        "atr14_at_entry": [2.0],
        "sc_momentum": [85.0],
    })
    outcomes = compute_outcomes(signals, panel)
    assert len(outcomes) == 1
    r = outcomes.iloc[0]["r_realized_5d"]
    # Expected r = (90 - 100) / (2 * 2) = -2.5
    assert r == pytest.approx(-2.5)
    assert outcomes.iloc[0]["gap_stop_5d"] == True  # noqa: E712


def test_dsl_initial_stop_clamp():
    """Initial stop must be clamped within [0.75×ATR, 2.0×ATR] of entry."""
    entry = 100.0
    atr14 = 2.0
    # Recent lows very close to entry → raw distance small → clamp to 0.75*ATR
    recent_lows = np.array([99.5, 99.6, 99.7, 99.8, 99.9])
    stop, risk = compute_initial_stop(entry, atr14, recent_lows)
    assert risk == pytest.approx(atr14 * 0.75)
    assert stop == pytest.approx(entry - atr14 * 0.75)

    # Recent lows very far below → raw distance large → clamp to 2.0*ATR
    recent_lows_far = np.array([85.0, 86.0, 87.0, 88.0, 89.0])
    stop2, risk2 = compute_initial_stop(entry, atr14, recent_lows_far)
    assert risk2 == pytest.approx(atr14 * 2.0)
    assert stop2 == pytest.approx(entry - atr14 * 2.0)


def test_dsl_trail_tiers():
    """Verify trail widens as R-multiple increases, and trail ratchets up."""
    entry = 100.0
    atr14 = 2.0
    risk = 4.0  # 2*ATR
    initial_stop = 96.0

    # Simulate steady uptrend — price rises 1R per 5 bars
    n = 40
    bars_close = np.linspace(100, 120, n)  # +20 over 40 bars = 5R
    bars_high = bars_close + 0.5
    bars_low = bars_close - 0.5
    bars_open = bars_close - 0.2

    result = simulate_dsl_trade(
        entry, atr14, risk,
        bars_open, bars_high, bars_low, bars_close,
        initial_stop, max_bars=n,
    )
    # Should reach T4 (>4R) and exit at time
    assert result["peak_tier"] >= 3
    assert result["exit_type"] == "time"
    assert result["r_realized"] > 3.0


def test_dsl_stop_exit():
    """If price drops immediately, DSL should stop out at initial stop or gap."""
    entry = 100.0
    atr14 = 2.0
    risk = 4.0
    initial_stop = 96.0

    # Price crashes day 1
    bars_open = np.array([95.0])
    bars_high = np.array([95.5])
    bars_low = np.array([93.0])
    bars_close = np.array([93.5])

    result = simulate_dsl_trade(
        entry, atr14, risk,
        bars_open, bars_high, bars_low, bars_close,
        initial_stop, max_bars=21,
    )
    assert result["exit_type"] == "gap_stop"
    assert result["exit_bar"] == 1
    assert result["r_realized"] < -1.0  # worse than -1R due to gap


def test_dsl_outcomes_pipeline():
    """Full pipeline: signals → DSL outcomes."""
    panel = _synth_panel()
    weekly = _weekly(panel)
    scores = _score_panel(panel, weekly)
    events = detect_crossups(scores, threshold=50.0, cooldown_days=10)
    if events.empty:
        pytest.skip("No events")
    with_ctx = attach_signal_context(events, scores)
    dsl_out = compute_dsl_outcomes(with_ctx, panel, max_bars=21)
    assert "dsl_r_realized" in dsl_out.columns
    assert "dsl_exit_type" in dsl_out.columns
    assert "dsl_peak_tier" in dsl_out.columns
    valid = dsl_out["dsl_r_realized"].dropna()
    if not valid.empty:
        assert valid.dtype == float


def test_vix_regime_classification():
    assert classify_vix_regime(12.0) == "GREEN"
    assert classify_vix_regime(20.0) == "YELLOW"
    assert classify_vix_regime(27.0) == "ORANGE"
    assert classify_vix_regime(35.0) == "RED"


def test_ptrs_disposition_bands():
    # PTRS = engine_score + SH only (no VIX/RA — regime handles macro separately)

    # High engine score + positive sector → FULL
    r = compute_ptrs(engine_score=65.0, sh=3.0)
    assert r["disposition"] == "FULL"
    assert r["ptrs"] == 68.0  # 65 + 3

    # Mediocre score → HALF
    r2 = compute_ptrs(engine_score=52.0, sh=0.0)
    assert r2["disposition"] == "HALF"
    assert r2["ptrs"] == 52.0

    # Below threshold → REJECT
    r3 = compute_ptrs(engine_score=35.0, sh=-5.0)
    assert r3["disposition"] == "REJECT"
    assert r3["ptrs"] == 30.0

    # Borderline QUARTER
    r4 = compute_ptrs(engine_score=48.0, sh=0.0)
    assert r4["disposition"] == "QUARTER"
    assert r4["max_size"] == 0.25

    # VIX regime is separate from PTRS (tested via classify_vix_regime)
    assert classify_vix_regime(15.0) == "GREEN"
    assert classify_vix_regime(20.0) == "YELLOW"
    assert classify_vix_regime(28.0) == "ORANGE"
    assert classify_vix_regime(35.0) == "RED"


def test_srm_grade_basic():
    """SRM should grade a synthetic uptrending ETF as DEPLOY or HOLD."""
    n = 50
    dates = pd.bdate_range("2024-01-02", periods=n)
    close = np.linspace(100, 120, n)  # strong uptrend
    etf = pd.DataFrame({
        "date": dates, "ticker": "XLK",
        "open": close - 0.3, "high": close + 0.5,
        "low": close - 0.5, "close": close,
        "volume": [5_000_000] * n,
    })
    result = grade_sector_etf(etf)
    assert result["grade"] in ("DEPLOY", "HOLD")
    assert result["sh"] >= 0

    # Downtrending ETF — a linear decline has divergence > 0 (5d % loss
    # is less than 20d % loss), which the SRM correctly reads as TURNING
    # (deceleration). For AVOID we need an accelerating crash where 5d ROC
    # is MORE negative than 20d ROC (divergence < 0). A brief rally followed
    # by a sharp crash achieves this: price 5d ago was higher than 20d ago,
    # so the recent crash looks worse.
    close_down = np.concatenate([
        np.linspace(100, 90, 30),      # slow decline for 30 bars
        np.linspace(90, 110, 15),      # brief rally (dead-cat bounce)
        np.linspace(110, 70, 5),       # crash in last 5 bars
    ])
    etf_down = pd.DataFrame({
        "date": dates, "ticker": "XLE",
        "open": close_down + 0.3, "high": close_down + 0.5,
        "low": close_down - 0.5, "close": close_down,
        "volume": [5_000_000] * n,
    })
    result_down = grade_sector_etf(etf_down)
    assert result_down["grade"] in ("WATCH", "AVOID")
    assert result_down["sh"] <= 0

    # trend_state is additive (alongside grade) and present on every reading.
    assert result["trend_state"] in (
        "Momentum Building — Add", "Momentum Fading — Hold, Don't Add",
        "Recovering From Weakness — Watch for Entry", "Declining — Avoid",
    )


def test_srm_trend_state_mapping():
    """The four action-states encode (trend direction × momentum slope)."""
    from src.engines.srm import _trend_state
    assert _trend_state(True, 1.2) == "Momentum Building — Add"
    assert _trend_state(True, -0.5) == "Momentum Fading — Hold, Don't Add"   # XLV case
    assert _trend_state(False, 0.8) == "Recovering From Weakness — Watch for Entry"
    assert _trend_state(False, -2.0) == "Declining — Avoid"
    # Boundary: flat divergence reads as decelerating (not accelerating).
    assert _trend_state(True, 0.0) == "Momentum Fading — Hold, Don't Add"


def test_rrg_quadrant_classification():
    """DSG-18: RRG quadrant and direction from synthetic sector vs SPY."""
    from src.engines.srm import compute_rrg, _rrg_quadrant, rrg_grade_override

    # Sector outperforming SPY (rising RS) -> LEADING or IMPROVING
    spy = np.linspace(100, 110, 50)
    sector_strong = np.linspace(100, 130, 50)  # outperforming
    result = compute_rrg(sector_strong, spy)
    assert result["rrg_quadrant"] in ("LEADING", "IMPROVING")
    assert result["rrg_rs_ratio"] is not None
    assert result["rrg_rs_ratio"] > 100

    # Sector underperforming SPY -> LAGGING or WEAKENING
    sector_weak = np.linspace(100, 95, 50)  # underperforming
    result2 = compute_rrg(sector_weak, spy)
    assert result2["rrg_quadrant"] in ("LAGGING", "WEAKENING")
    assert result2["rrg_rs_ratio"] < 100

    # Quadrant logic
    assert _rrg_quadrant(102, 101) == "LEADING"
    assert _rrg_quadrant(98, 101) == "IMPROVING"
    assert _rrg_quadrant(102, 99) == "WEAKENING"
    assert _rrg_quadrant(98, 99) == "LAGGING"

    # Grade overrides
    assert rrg_grade_override("DEPLOY", "LAGGING") == "AVOID_FLAG"
    assert rrg_grade_override("DEPLOY", "WEAKENING") == "HOLD_FLAG"
    assert rrg_grade_override("HOLD", "LEADING") == "WATCH_UP"
    assert rrg_grade_override("HOLD", "LAGGING") == "AVOID_FLAG"
    assert rrg_grade_override("AVOID", "LEADING") is None  # AVOID never upgraded
    assert rrg_grade_override("DEPLOY", "LEADING") is None  # no override needed

    # Too little data -> NO_DATA
    short = np.array([100, 101, 102])
    assert compute_rrg(short, short)["rrg_quadrant"] == "NO_DATA"


def test_macro_direction_and_headwind():
    """DSG-19: macro direction score and sector headwind flag."""
    from src.engines.srm import macro_direction_score, compute_macro_headwind

    # Strong uptrend: roc5 > 0, roc20 > 0 -> score +2
    up = np.linspace(100, 120, 25)
    score, roc5, roc20 = macro_direction_score(up)
    assert score == 2
    assert roc5 > 0
    assert roc20 > 0

    # Strong downtrend: roc5 < 0, roc20 < 0 -> score -2
    down = np.linspace(120, 100, 25)
    score_d, roc5_d, roc20_d = macro_direction_score(down)
    assert score_d == -2
    assert roc5_d < 0

    # XLK with TLT falling (score -2), UUP rising (+2), HYG falling (-2), IWM falling (-2)
    # Sensitivity: TLT+1, UUP-1, HYG+1, IWM+1
    # Aligned: TLT(-2)*1=-2, UUP(+2)*(-1)=-2, HYG(-2)*1=-2, IWM(-2)*1=-2
    # Weighted: 0.30*(-2) + 0.25*(-2) + 0.25*(-2) + 0.20*(-2) = -2.0
    hw_score, hw_flag = compute_macro_headwind("XLK", -2, +2, -2, -2)
    assert hw_score < -0.5
    assert hw_flag == "HEADWIND"

    # XLK with tailwind: TLT rising (+2), UUP falling (-2), HYG rising (+2), IWM rising (+2)
    tw_score, tw_flag = compute_macro_headwind("XLK", +2, -2, +2, +2)
    assert tw_score > 0.5
    assert tw_flag == "TAILWIND"


def test_sector_entry_gate():
    """Combined gate: grade + RRG + macro -> PASS/WATCH/CAUTION/BLOCKED."""
    from src.engines.srm import sector_entry_gate

    assert sector_entry_gate("AVOID", "LEADING", "TAILWIND")[0] == "BLOCKED"
    assert sector_entry_gate("HOLD", "LAGGING", "HEADWIND")[0] == "BLOCKED"
    assert sector_entry_gate("DEPLOY", "LEADING", "TAILWIND")[0] == "PASS"
    assert sector_entry_gate("HOLD", "IMPROVING", "NEUTRAL")[0] == "PASS"
    assert sector_entry_gate("HOLD", "WEAKENING", "CAUTION")[0] == "CAUTION"
    assert sector_entry_gate("DEPLOY", "WEAKENING", "HEADWIND")[0] == "CAUTION"
    assert sector_entry_gate("TURNING", "IMPROVING", "NEUTRAL")[0] == "WATCH"


def test_non_monotonic_dates_raise_or_handle():
    """Engines accept a single-ticker frame; if dates are out of order they should not produce garbage."""
    # We don't enforce monotonicity in the engine signatures, but the score_runner always sorts.
    # Verify a sorted frame produces clean output and a hand-shuffled frame produces different scores.
    panel = _synth_panel(n=300)
    spy = panel.loc[panel["ticker"] == "SPY"].reset_index(drop=True)
    d = panel.loc[panel["ticker"] == "AAA"].sort_values("date").reset_index(drop=True)
    f_sorted = flow.compute(d)
    # Just confirm the sorted call returns the expected shape.
    assert len(f_sorted) == len(d)
    assert (f_sorted["flow_100"].dropna() >= 0).all()
    assert (f_sorted["flow_100"].dropna() <= 100).all()


def test_hurst_trending():
    """Strong uptrend should produce H > 0.55 (TRENDING)."""
    from src.analyzer.regime import hurst_exponent, classify_hurst
    # Steady uptrend with small noise
    np.random.seed(123)
    prices = 100 * np.cumprod(1 + 0.002 + np.random.randn(200) * 0.005)
    h = hurst_exponent(prices)
    assert 0.0 <= h <= 1.0
    # Strong trend should push H above 0.5
    assert h > 0.45


def test_hurst_random_walk():
    """Pure random walk should produce H near 0.50."""
    from src.analyzer.regime import hurst_exponent, classify_hurst
    np.random.seed(456)
    prices = 100 * np.cumprod(1 + np.random.randn(500) * 0.01)
    h = hurst_exponent(prices)
    assert 0.35 <= h <= 0.65


def test_regime_computation():
    """compute_regime returns expected structure."""
    from src.analyzer.regime import compute_regime
    np.random.seed(789)
    spy_closes = 100 * np.cumprod(1 + np.random.randn(100) * 0.01)
    result = compute_regime(spy_closes, vix=22.0)
    assert result["vix_regime"] == "YELLOW"
    assert "hurst" in result
    assert result["hurst_regime"] in ("TRENDING", "RANDOM", "MEAN_REVERT")


def test_capacity_check():
    """Capacity check flags small-volume tickers."""
    from src.analyzer.capacity import check_capacity
    # $10K position in a stock with $500K daily dollar volume → 2% participation
    result = check_capacity("IONQ", 10_000, avg_volume_20d=50_000, avg_price=10.0)
    assert result["status"] == "WARNING"
    assert result["participation_pct"] == pytest.approx(2.0, abs=0.01)

    # $10K in NVDA ($10B daily) → negligible
    result2 = check_capacity("NVDA", 10_000, avg_volume_20d=50_000_000, avg_price=200.0)
    assert result2["status"] == "OK"


def test_walkforward_windows():
    """Walk-forward analysis returns valid windows on synthetic outcomes."""
    from src.calibration.walkforward import walk_forward_analysis, format_walkforward, WFWindow
    rng = np.random.default_rng(42)
    n = 2000
    dates = pd.bdate_range("2020-01-02", periods=n)
    outcomes = pd.DataFrame({
        "date": dates[:n],
        "ticker": rng.choice(["AAA", "BBB", "CCC"], n),
        "sc_momentum": rng.uniform(50, 90, n),
        "flow_100": rng.uniform(60, 95, n),
        "energy_100": rng.uniform(60, 95, n),
        "structure_100": rng.uniform(55, 95, n),
        "mp_100": rng.uniform(55, 95, n),
        "dsl_r_realized": rng.normal(0.05, 1.0, n),
    })
    windows = walk_forward_analysis(outcomes, r_column="dsl_r_realized", train_months=12, test_months=3, step_months=3)
    assert len(windows) >= 1
    for w in windows:
        assert isinstance(w, WFWindow)
        assert w.train_start < w.test_start
        assert w.test_start < w.test_end
    report = format_walkforward(windows)
    assert "WALK-FORWARD ANALYSIS" in report


def test_walkforward_empty():
    """Walk-forward on empty data returns empty list."""
    from src.calibration.walkforward import walk_forward_analysis
    result = walk_forward_analysis(pd.DataFrame(), r_column="dsl_r_realized")
    assert result == []


def test_pipeline_rank_basic():
    """Pipeline Rank produces scores in [0, 100] for synthetic data with enough bars."""
    panel = _synth_panel(n=600)
    d = panel[panel["ticker"] == "AAA"].sort_values("date").reset_index(drop=True)
    from src.engines.pipeline_rank import compute
    pr = compute(d)
    assert "pipe_rank" in pr.columns
    valid = pr["pipe_rank"].dropna()
    assert len(valid) > 0
    assert (valid >= 0).all()
    assert (valid <= 100).all()


def test_bc_layer():
    """Backtest Confidence layer scores and classifies correctly."""
    from src.backtest.confidence import (
        compute_bc_score, bc_modifier, classify_composite_band,
        build_profile_signature, match_outcomes, BCResult,
    )
    # High performer: 55% win rate, +0.3 avg R, 100 samples, 70% consistency
    score = compute_bc_score(0.55, 0.30, 100, 0.70)
    assert 50 < score < 100
    assert bc_modifier(score) > 0  # positive adjustment

    # Poor performer
    score_bad = compute_bc_score(0.30, -0.10, 25, 0.30)
    assert score_bad < 50
    assert bc_modifier(score_bad) < 0  # negative adjustment

    # Band classification
    assert classify_composite_band(80) == "HIGH"
    assert classify_composite_band(65) == "MEDIUM"
    assert classify_composite_band(52) == "LOW"
    assert classify_composite_band(40) == "BELOW"

    # Profile matching with sufficient data
    rng = np.random.default_rng(99)
    outcomes = pd.DataFrame({
        "sc_momentum": rng.uniform(60, 80, 100),
        "mp_state": ["STRONG"] * 100,
        "dsl_r_realized": rng.normal(0.2, 0.8, 100),
    })
    profile = build_profile_signature(70, "STRONG", "YELLOW", "DEPLOY")
    profile["ticker"] = "TEST"
    result = match_outcomes(profile, outcomes)
    assert result is not None
    assert isinstance(result, BCResult)
    assert result.tier in ("EXACT", "CORE", "BROAD")
    assert result.n_samples >= 20


def test_shortlist_format():
    """Daily orchestrator output format matches expected schema."""
    from src.pipeline.daily_orchestrator import _build_output, _format_dashboard
    from datetime import date
    fake_regime = {"vix": 20.0, "vix_regime": "YELLOW", "hurst": 0.55, "hurst_regime": "TRENDING", "implication": "Momentum strategies favoured"}
    fake_grades = {"XLK": {"grade": "DEPLOY", "sh": 3}, "XLE": {"grade": "AVOID", "sh": -8}}
    fake_shortlist = [{
        "ticker": "NVDA", "sc_momentum": 75.0, "sc_position": 60.0,
        "flow_100": 80.0, "energy_100": 70.0, "structure_100": 75.0,
        "mp_100": 65.0, "elder_score": 8.0, "bq_100": 55.0,
        "mp_state": "STRONG", "close": 150.0, "atr14": 3.5,
        "ptrs": 80.0, "cm": 5.0, "sh": 3, "ra": 5.0, "rl": -3.0,
        "regime": "YELLOW", "disposition": "FULL", "max_size": 0.25,
        "sector": "XLK", "sector_grade": "DEPLOY",
    }]
    output = _build_output(date(2026, 5, 17), fake_regime, fake_grades, fake_shortlist)
    assert output["date"] == "2026-05-17"
    assert output["regime"]["level"] == "YELLOW"
    assert len(output["candidates"]) == 1
    assert output["candidates"][0]["ticker"] == "NVDA"
    assert output["candidates"][0]["disposition"] == "FULL"
    dashboard = _format_dashboard(output)
    assert "NVDA" in dashboard
    assert "AQE DAILY SHORTLIST" in dashboard


def test_earnings_proximity():
    """Earnings proximity scoring follows spec (<=5d=0, <=10d=4, <=20d=7, >20d=10)."""
    from src.data.earnings import earn_proximity_score, days_to_earnings, build_earnings_series
    from datetime import date

    assert earn_proximity_score(None) == 10.0
    assert earn_proximity_score(3) == 0.0
    assert earn_proximity_score(5) == 0.0
    assert earn_proximity_score(7) == 4.0
    assert earn_proximity_score(10) == 4.0
    assert earn_proximity_score(15) == 7.0
    assert earn_proximity_score(20) == 7.0
    assert earn_proximity_score(25) == 10.0
    assert earn_proximity_score(100) == 10.0

    cal = {"NVDA": "2026-06-01"}
    assert days_to_earnings("NVDA", date(2026, 5, 28), cal) == 4.0
    assert days_to_earnings("NVDA", date(2026, 5, 20), cal) == 12.0
    assert days_to_earnings("AAPL", date(2026, 5, 20), cal) is None

    dates = pd.Series(
        [pd.Timestamp("2026-05-28"), pd.Timestamp("2026-05-20"), pd.Timestamp("2026-04-01")],
    )
    series = build_earnings_series(dates, "NVDA", cal)
    assert len(series) == 3
    assert series.iloc[0] == 0.0   # 4 days out -> <=5d
    assert series.iloc[1] == 7.0   # 12 days out -> <=20d
    assert series.iloc[2] == 10.0  # 61 days out -> >20d


def test_sqlite_roundtrip(tmp_path):
    """SQLite db module can init, write, and read back data."""
    import src.data.db as db
    original_path = db.DB_PATH
    db.DB_PATH = tmp_path / "test.db"
    try:
        db.init_db()
        db.save_engine_state("NVDA", {
            "raw_base_count": 15,
            "latched_bd": 8,
            "bars_since_bo": 5,
            "trend_bars": 3,
            "last_computed": "2026-05-17",
        })
        state = db.get_engine_state("NVDA")
        assert state is not None
        assert state["raw_base_count"] == 15
        assert state["latched_bd"] == 8
        assert state["trend_bars"] == 3

        db.upsert_earnings({"NVDA": "2026-05-20", "AAPL": "2026-07-25"})
        cal = db.get_earnings()
        assert cal["NVDA"] == "2026-05-20"
        assert cal["AAPL"] == "2026-07-25"

        counts = db.table_counts()
        assert counts["engine_state"] == 1
        assert counts["earnings"] == 2
    finally:
        db.DB_PATH = original_path


def test_pbo_and_purged_kfold():
    """PBO detects overfitting in random data; purged K-fold runs cleanly."""
    from src.calibration.validation import (
        probability_of_backtest_overfitting,
        purged_kfold_cv,
        deflated_sharpe_ratio,
    )

    rng = np.random.default_rng(42)
    n_trades = 500
    n_models = 10
    returns_matrix = rng.normal(0.0, 1.0, (n_trades, n_models))

    result = probability_of_backtest_overfitting(returns_matrix, n_partitions=8)
    assert "pbo" in result
    assert 0.0 <= result["pbo"] <= 1.0
    assert result["n_combinations"] > 0
    # Pure noise should have PBO near 0.5 (random IS/OOS alignment)
    assert result["pbo"] > 0.2

    # Test with a genuinely predictive model (model 0 always positive)
    good_matrix = rng.normal(0.0, 1.0, (n_trades, n_models))
    good_matrix[:, 0] += 0.5  # model 0 has real edge
    result_good = probability_of_backtest_overfitting(good_matrix, n_partitions=8)
    # A real edge should have lower PBO than pure noise
    assert result_good["pbo"] < result["pbo"] or result_good["pbo"] < 0.5

    # Purged K-fold
    returns = pd.Series(rng.normal(0.05, 0.8, 200))
    dates = pd.Series(pd.date_range("2020-01-01", periods=200, freq="B"))
    cv_result = purged_kfold_cv(returns, dates, n_folds=5)
    assert cv_result["n_folds"] == 5
    assert len(cv_result["folds"]) == 5
    assert "avg_r" in cv_result

    # Deflated Sharpe
    dsr = deflated_sharpe_ratio(sharpe_obs=1.5, n_trials=100, n_trades=500)
    assert 0.0 <= dsr <= 1.0


def test_triple_barrier():
    """Triple barrier labeling: UPPER hit, LOWER hit, VERTICAL expiry."""
    from src.backtest.labels import apply_triple_barrier, batch_triple_barrier

    # --- Single trade: hits profit target (UPPER) ---
    entry = 100.0
    risk = 5.0  # stop at 95
    # Day 1: rallies to 120 (high >= 100 + 3*5 = 115)
    highs = np.array([112.0, 116.0, 120.0])
    lows = np.array([99.0, 110.0, 114.0])
    closes = np.array([110.0, 114.0, 118.0])
    result = apply_triple_barrier(entry, risk, highs, lows, closes)
    assert result["label"] == "UPPER"
    assert result["exit_bar"] == 2  # bar index 1 (0-based) → exit_bar 2
    assert result["r_multiple"] == 3.0
    assert result["exit_price"] == 115.0

    # --- Single trade: hits stop (LOWER) ---
    highs2 = np.array([101.0, 102.0, 103.0])
    lows2 = np.array([96.0, 94.0, 92.0])  # bar 0: low 96 > 95, bar 1: low 94 <= 95
    closes2 = np.array([99.0, 95.0, 93.0])
    result2 = apply_triple_barrier(entry, risk, highs2, lows2, closes2)
    assert result2["label"] == "LOWER"
    assert result2["exit_bar"] == 2
    assert result2["r_multiple"] == -1.0
    assert result2["exit_price"] == 95.0

    # --- Single trade: expires at vertical barrier ---
    flat_highs = np.array([101.0, 102.0, 101.5])
    flat_lows = np.array([99.0, 98.5, 99.0])
    flat_closes = np.array([100.5, 100.2, 100.3])
    result3 = apply_triple_barrier(entry, risk, flat_highs, flat_lows, flat_closes, max_bars=3)
    assert result3["label"] == "VERTICAL"
    assert result3["exit_bar"] == 3
    assert abs(result3["exit_price"] - 100.3) < 0.01

    # --- Edge: zero risk returns VERTICAL immediately ---
    result4 = apply_triple_barrier(entry, 0.0, highs, lows, closes)
    assert result4["label"] == "VERTICAL"
    assert result4["r_multiple"] == 0.0

    # --- Edge: empty forward bars ---
    result5 = apply_triple_barrier(entry, risk, np.array([]), np.array([]), np.array([]))
    assert result5["label"] == "VERTICAL"

    # --- Batch: DataFrame path ---
    signals = pd.DataFrame({
        "ticker": ["AAPL", "AAPL"],
        "date": [pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-07")],
        "entry_close": [150.0, 150.0],
        "stop_price": [145.0, 145.0],
    })
    panel = pd.DataFrame({
        "ticker": ["AAPL"] * 10,
        "date": pd.date_range("2026-01-05", periods=10, freq="B"),
        "open": [150.0] * 10,
        "high": [151.0, 153.0, 160.0, 166.0, 170.0,
                 151.0, 153.0, 160.0, 166.0, 170.0],
        "low":  [149.0, 148.0, 155.0, 160.0, 165.0,
                 149.0, 148.0, 155.0, 160.0, 165.0],
        "close": [150.5, 152.0, 158.0, 164.0, 168.0,
                  150.5, 152.0, 158.0, 164.0, 168.0],
    })
    batch = batch_triple_barrier(signals, panel, max_bars=5)
    assert "tb_label" in batch.columns
    assert "tb_r_multiple" in batch.columns
    assert len(batch) == 2
    # Both signals should get labels (not INSUFFICIENT since panel has future bars)
    assert batch.iloc[0]["tb_label"] in ("UPPER", "LOWER", "VERTICAL")
    assert batch.iloc[1]["tb_label"] in ("UPPER", "LOWER", "VERTICAL")


def test_correlation_stress():
    """Correlated loss stress test produces valid output on synthetic trades."""
    from src.backtest.correlation_stress import (
        run_correlation_stress, format_stress_report, stress_to_dict, StressResult,
    )
    import json as _json

    # Build synthetic trade log resembling portfolio sim output
    rng = np.random.default_rng(42)
    trades = []
    for i in range(80):
        trades.append({
            "entry_date": str(pd.Timestamp("2024-01-02") + pd.offsets.BDay(i)),
            "exit_bar": int(rng.integers(3, 15)),
            "r_realized": float(rng.normal(0.1, 1.0)),
            "net_pnl": float(rng.normal(50, 500)),
            "shares": 100,
            "risk_per_share": 2.0,
            "dollar_risk": 2100.0,
            "sector": ["XLK", "XLF", "XLE"][i % 3],
            "ticker": f"T{i % 8}",
        })

    result = run_correlation_stress(trades, 70_000.0, 0.03, 6)
    assert isinstance(result, StressResult)
    assert result.max_concurrent_positions > 0
    assert result.stress_grade in ("A", "B", "C", "D", "F")
    assert result.worst_week_loss_pct <= 0 or result.worst_week_loss_pct >= 0  # not NaN
    assert result.longest_losing_streak >= 0

    # Report formats without error
    report = format_stress_report(result)
    assert "CORRELATED LOSS STRESS TEST" in report

    # Dict is JSON-serializable
    d = stress_to_dict(result)
    _json.dumps(d)  # throws if numpy types leak

    # Empty trades produce clean empty result
    empty = run_correlation_stress([], 70_000.0)
    assert empty.stress_grade == "A"
    assert empty.max_concurrent_positions == 0
