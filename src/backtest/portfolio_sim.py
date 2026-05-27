"""Portfolio P&L Simulator — event-loop backtest with real sizing and costs.

Takes scored signals with DSL outcomes and simulates how a $70K account
would perform using AQE's actual rules:
    - 3% risk per FULL trade, scaled by disposition (HALF/QUARTER)
    - Max 6 concurrent positions
    - 35% max sector exposure
    - 10bps slippage + $0.005/share commission (both sides)
    - 2% annual survivorship bias haircut on reported returns
    - Triple barrier labeling alongside DSL trail outcomes

Output: trade log, equity curve, summary statistics, Monte Carlo distribution.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.costs import entry_fill, exit_fill, round_trip_cost, SLIPPAGE_PCT
from src.backtest.sizing import (
    compute_position_size,
    MAX_POSITIONS,
    MAX_SECTOR_EXPOSURE,
    RISK_PER_TRADE_PCT,
)

SURVIVORSHIP_HAIRCUT_ANNUAL = 0.02
BARRIER_UPPER_R = 3.0
BARRIER_LOWER_R = 1.0
BARRIER_MAX_BARS = 25


# ─── Triple Barrier Labeling ───────────────────────────────────────────────

def triple_barrier_label(
    bars_high: np.ndarray,
    bars_low: np.ndarray,
    bars_close: np.ndarray,
    entry_price: float,
    risk_per_share: float,
    upper_mult: float = BARRIER_UPPER_R,
    lower_mult: float = BARRIER_LOWER_R,
    max_bars: int = BARRIER_MAX_BARS,
) -> dict:
    """Label a trade using the triple barrier method (López de Prado MLP-4).

    Three barriers:
        UPPER: entry + upper_mult × risk (profit target)
        LOWER: entry - lower_mult × risk (stop loss)
        VERTICAL: max_bars reached (time expiry)

    Returns: label (+1/-1/0), barrier_hit, bars_to_hit.
    """
    upper = entry_price + (risk_per_share * upper_mult)
    lower = entry_price - (risk_per_share * lower_mult)
    n = min(len(bars_high), max_bars)

    for i in range(n):
        if bars_high[i] >= upper:
            return {"label": 1, "barrier": "UPPER", "bars": i + 1}
        if bars_low[i] <= lower:
            return {"label": -1, "barrier": "LOWER", "bars": i + 1}

    if n > 0:
        final_ret = bars_close[n - 1] - entry_price
        label = 1 if final_ret > 0 else (-1 if final_ret < 0 else 0)
    else:
        label = 0
    return {"label": label, "barrier": "VERTICAL", "bars": n}


# ─── Monte Carlo Permutation ──────────────────────────────────────────────

def monte_carlo_equity(
    trade_pnls: list[float],
    initial_capital: float,
    n_simulations: int = 2000,
) -> dict:
    """Shuffle trade sequence 2000 times, rebuild equity curves.

    Shows the DISTRIBUTION of outcomes from the same trades in random order.
    Answers: "What's the worst drawdown I should expect, given sequencing luck?"
    """
    if not trade_pnls:
        return {
            "median_return_pct": 0.0,
            "p5_return_pct": 0.0,
            "p95_return_pct": 0.0,
            "median_max_dd_pct": 0.0,
            "p95_max_dd_pct": 0.0,
            "risk_of_ruin_pct": 0.0,
            "original_percentile": 50.0,
        }

    pnls = np.array(trade_pnls)
    original_final = float(np.sum(pnls))

    finals = []
    max_dds = []

    for _ in range(n_simulations):
        shuffled = np.random.permutation(pnls)
        equity = np.cumsum(shuffled) + initial_capital
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak
        max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0
        final_ret = float((equity[-1] - initial_capital) / initial_capital)
        finals.append(final_ret)
        max_dds.append(max_dd)

    finals = np.array(finals)
    max_dds = np.array(max_dds)

    original_ret = original_final / initial_capital
    original_pct = float(np.mean(finals <= original_ret) * 100)

    return {
        "median_return_pct": round(float(np.median(finals)) * 100, 2),
        "p5_return_pct": round(float(np.percentile(finals, 5)) * 100, 2),
        "p95_return_pct": round(float(np.percentile(finals, 95)) * 100, 2),
        "median_max_dd_pct": round(float(np.median(max_dds)) * 100, 2),
        "p95_max_dd_pct": round(float(np.percentile(max_dds, 95)) * 100, 2),
        "risk_of_ruin_pct": round(float(np.mean(max_dds > 0.25)) * 100, 2),
        "original_percentile": round(original_pct, 1),
    }


# ─── Portfolio Simulator ──────────────────────────────────────────────────

def simulate_portfolio(
    signals: pd.DataFrame,
    panel_daily: pd.DataFrame,
    initial_capital: float = 70_000.0,
    max_positions: int = MAX_POSITIONS,
    risk_pct: float = RISK_PER_TRADE_PCT,
    max_sector_pct: float = MAX_SECTOR_EXPOSURE,
) -> dict:
    """Run event-loop portfolio simulation.

    signals must have: date, ticker, sc_momentum, atr14_at_entry (or atr14),
                       ptrs_disposition (or defaults to FULL).
    panel_daily: full OHLCV data.

    Returns dict with:
        trades: list of closed trade dicts
        equity_curve: DataFrame (date, equity, drawdown)
        summary: performance metrics
        monte_carlo: distribution stats
    """
    from src.engines.srm import TICKER_TO_SECTOR

    if signals.empty:
        return _empty_result(initial_capital)

    sig = signals.copy()
    sig["date"] = pd.to_datetime(sig["date"]).dt.normalize()
    sig = sig.sort_values("date").reset_index(drop=True)

    panel = panel_daily.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    panel_groups = {t: g.reset_index(drop=True) for t, g in panel.groupby("ticker", sort=False)}

    equity = initial_capital
    active_positions: list[dict] = []  # tracks (ticker, sector, entry_idx, exit_idx, position_value)
    closed_trades: list[dict] = []
    equity_history: list[dict] = []

    for _, row in sig.iterrows():
        ticker = row["ticker"]
        entry_date = row["date"]
        disposition = row.get("ptrs_disposition", "FULL")
        if disposition in ("REJECT", "PARKED") or pd.isna(disposition):
            continue

        bars = panel_groups.get(ticker)
        if bars is None or bars.empty:
            continue
        bars_dates = bars["date"].to_numpy()
        date_to_idx = {d: i for i, d in enumerate(bars_dates)}
        entry_idx = date_to_idx.get(np.datetime64(entry_date, "ns"))
        if entry_idx is None:
            continue

        # Expire positions that have closed by this entry date
        active_positions = [
            p for p in active_positions if p["exit_idx"] > entry_idx or p["ticker"] != ticker
        ]
        # For cross-ticker concurrency, compare by date index in their own bar series
        # Simpler: track exit dates as timestamps and compare
        active_positions = [
            p for p in active_positions if p["exit_date"] > entry_date
        ]

        if len(active_positions) >= max_positions:
            continue

        sector = TICKER_TO_SECTOR.get(ticker, "Unknown")
        sector_exposure = sum(
            p["position_value"] for p in active_positions if p["sector"] == sector
        )
        if equity > 0 and (sector_exposure / equity) >= max_sector_pct:
            continue

        entry_close = float(bars["close"].iloc[entry_idx])
        atr_col = "atr14_at_entry" if "atr14_at_entry" in row.index else "atr14"
        atr14 = float(row.get(atr_col, np.nan))
        if not np.isfinite(atr14) or atr14 <= 0:
            continue

        low_start = max(0, entry_idx - 4)
        recent_lows = bars["low"].iloc[low_start:entry_idx + 1].astype(float).to_numpy()
        struct_low = float(np.nanmin(recent_lows))
        buffered_stop = struct_low - 0.5 * atr14
        raw_distance = entry_close - buffered_stop
        risk_per_share = max(min(raw_distance, atr14 * 2.0), atr14 * 0.75)

        sizing = compute_position_size(
            equity=equity,
            entry_price=entry_close,
            risk_per_share=risk_per_share,
            disposition=disposition,
        )
        shares = sizing["shares"]
        if shares <= 0:
            continue

        fill_price, entry_commission = entry_fill(entry_close, shares)
        position_value = fill_price * shares

        fwd_start = entry_idx + 1
        fwd_end = min(fwd_start + 63, len(bars))
        if fwd_start >= len(bars):
            continue

        fwd_high = bars["high"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_low = bars["low"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_close = bars["close"].iloc[fwd_start:fwd_end].astype(float).to_numpy()
        fwd_open = bars["open"].iloc[fwd_start:fwd_end].astype(float).to_numpy()

        # DSL trail simulation
        from src.scanner.dsl import simulate_dsl_trade
        initial_stop = fill_price - risk_per_share
        dsl_result = simulate_dsl_trade(
            fill_price, atr14, risk_per_share,
            fwd_open, fwd_high, fwd_low, fwd_close,
            initial_stop, max_bars=63,
        )

        exit_price_raw = dsl_result["exit_price"]
        exit_fill_price, exit_commission = exit_fill(exit_price_raw, shares)

        gross_pnl = (exit_fill_price - fill_price) * shares
        total_costs = entry_commission + exit_commission
        net_pnl = gross_pnl - total_costs

        # Triple barrier label
        tb = triple_barrier_label(
            fwd_high, fwd_low, fwd_close,
            fill_price, risk_per_share,
        )

        trade = {
            "ticker": ticker,
            "sector": sector,
            "entry_date": str(entry_date.date()) if hasattr(entry_date, 'date') else str(entry_date)[:10],
            "entry_price": round(fill_price, 2),
            "exit_price": round(exit_fill_price, 2),
            "shares": shares,
            "disposition": disposition,
            "risk_per_share": round(risk_per_share, 2),
            "dollar_risk": round(sizing["dollar_risk"], 2),
            "gross_pnl": round(gross_pnl, 2),
            "costs": round(total_costs, 2),
            "net_pnl": round(net_pnl, 2),
            "r_realized": round(net_pnl / sizing["dollar_risk"], 2) if sizing["dollar_risk"] > 0 else 0.0,
            "exit_type": dsl_result["exit_type"],
            "exit_bar": dsl_result["exit_bar"],
            "peak_tier": dsl_result["peak_tier"],
            "peak_r": round(dsl_result["peak_r"], 2),
            "tb_label": tb["label"],
            "tb_barrier": tb["barrier"],
            "tb_bars": tb["bars"],
            "position_value": round(position_value, 2),
        }
        closed_trades.append(trade)
        equity += net_pnl
        equity_history.append({"date": str(entry_date)[:10], "equity": round(equity, 2)})

        # Track position for concurrency limiting
        exit_bar_count = dsl_result["exit_bar"]
        exit_idx_abs = entry_idx + exit_bar_count
        if exit_idx_abs < len(bars_dates):
            exit_date_ts = pd.Timestamp(bars_dates[exit_idx_abs])
        else:
            exit_date_ts = entry_date + pd.Timedelta(days=exit_bar_count * 2)
        active_positions.append({
            "ticker": ticker,
            "sector": sector,
            "position_value": position_value,
            "exit_idx": exit_idx_abs,
            "exit_date": exit_date_ts,
        })

    summary = _compute_summary(closed_trades, initial_capital, equity)
    mc = monte_carlo_equity(
        [t["net_pnl"] for t in closed_trades],
        initial_capital,
    )

    # Correlated loss stress test — the gap Monte Carlo can't see
    from src.backtest.correlation_stress import run_correlation_stress, stress_to_dict
    stress = run_correlation_stress(
        closed_trades, initial_capital, risk_pct, max_positions,
    )

    return {
        "trades": closed_trades,
        "equity_curve": equity_history,
        "summary": summary,
        "monte_carlo": mc,
        "stress_test": stress_to_dict(stress),
    }


def _compute_summary(trades: list[dict], initial_capital: float, final_equity: float) -> dict:
    if not trades:
        return {"total_trades": 0, "net_return_pct": 0.0}

    pnls = [t["net_pnl"] for t in trades]
    rs = [t["r_realized"] for t in trades]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]
    total_costs = sum(t["costs"] for t in trades)

    gross_return = (final_equity - initial_capital) / initial_capital
    # Approximate annual return (assume ~252 trading days, use trade span)
    if len(trades) >= 2:
        first_date = pd.Timestamp(trades[0]["entry_date"])
        last_date = pd.Timestamp(trades[-1]["entry_date"])
        days_span = max((last_date - first_date).days, 1)
        years = days_span / 365.25
    else:
        years = 1.0

    annual_return = gross_return / years if years > 0 else gross_return
    adjusted_annual = annual_return - SURVIVORSHIP_HAIRCUT_ANNUAL

    # Equity curve for drawdown
    eq = np.array([initial_capital] + [initial_capital + sum(pnls[:i+1]) for i in range(len(pnls))])
    peak = np.maximum.accumulate(eq)
    dd = (peak - eq) / peak
    max_dd = float(np.max(dd))

    # Risk metrics
    ret_arr = np.array(pnls) / initial_capital
    avg_hold = float(np.mean([t["exit_bar"] for t in trades]))

    if len(pnls) > 1 and np.std(ret_arr) > 0:
        sharpe = float(np.mean(ret_arr) / np.std(ret_arr) * np.sqrt(252 / max(avg_hold, 1)))
    else:
        sharpe = 0.0

    downside = ret_arr[ret_arr < 0]
    if len(downside) > 1 and np.std(downside) > 0:
        sortino = float(np.mean(ret_arr) / np.std(downside) * np.sqrt(252 / max(avg_hold, 1)))
    else:
        sortino = sharpe

    calmar = round(annual_return / max_dd, 2) if max_dd > 0 else 0.0

    win_rate = len(winners) / len(trades)
    avg_win = float(np.mean(winners)) if winners else 0.0
    avg_loss = abs(float(np.mean(losers))) if losers else 0.0
    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

    # DSL trail-specific: capture ratio and avg exit tier
    peak_rs = [t["peak_r"] for t in trades if t["peak_r"] > 0]
    exit_rs = [t["r_realized"] for t in trades if t["peak_r"] > 0]
    trail_capture = float(np.mean(np.array(exit_rs) / np.array(peak_rs))) if peak_rs else 0.0

    avg_exit_tier = float(np.mean([t["peak_tier"] for t in trades]))

    return {
        "total_trades": len(trades),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate_pct": round(win_rate * 100, 1),
        "avg_win_dollar": round(avg_win, 2),
        "avg_loss_dollar": round(float(np.mean(losers)), 2) if losers else 0.0,
        "avg_r": round(float(np.mean(rs)), 2),
        "median_r": round(float(np.median(rs)), 2),
        "expectancy_dollar": round(expectancy, 2),
        "total_pnl": round(sum(pnls), 2),
        "total_costs": round(total_costs, 2),
        "cost_drag_pct": round(total_costs / initial_capital * 100, 2),
        "gross_return_pct": round(gross_return * 100, 2),
        "annual_return_pct": round(annual_return * 100, 2),
        "adjusted_annual_pct": round(adjusted_annual * 100, 2),
        "survivorship_haircut_pct": SURVIVORSHIP_HAIRCUT_ANNUAL * 100,
        "max_drawdown_pct": round(max_dd * 100, 2),
        "sharpe_approx": round(sharpe, 2),
        "sortino_approx": round(sortino, 2),
        "calmar": calmar,
        "avg_hold_bars": round(avg_hold, 1),
        "avg_exit_tier": round(avg_exit_tier, 1),
        "trail_capture_ratio": round(trail_capture, 3),
        "peak_tier_distribution": {
            f"T{tier}": sum(1 for t in trades if t["peak_tier"] == tier)
            for tier in [1, 2, 3, 4]
        },
        "final_equity": round(final_equity, 2),
        "initial_capital": initial_capital,
    }


def _empty_result(capital: float) -> dict:
    from src.backtest.correlation_stress import stress_to_dict, _empty_stress
    return {
        "trades": [],
        "equity_curve": [],
        "summary": {"total_trades": 0, "net_return_pct": 0.0, "initial_capital": capital, "final_equity": capital},
        "monte_carlo": monte_carlo_equity([], capital),
        "stress_test": stress_to_dict(_empty_stress()),
    }


# ─── Example Scenario (for display / explanation) ─────────────────────────

def example_100k_scenario() -> str:
    """Generate a plain-English walkthrough of how the system sizes a trade.

    This is a STATIC example for documentation/explanation purposes.
    """
    return """
╔══════════════════════════════════════════════════════════════════════════╗
║          $70,000 PORTFOLIO — HOW ONE TRADE GETS SIZED                  ║
╠══════════════════════════════════════════════════════════════════════════╣

SCENARIO: NNE scores SC_MOMENTUM = 71.4, PTRS = 74 → Disposition: FULL

Step 1: RISK BUDGET
   Account equity:        $70,000
   Risk per trade:        3% × FULL (1.0×) = $2,100

Step 2: STOP PLACEMENT (DSL v1.4)
   Entry price:           $55.20 (close of signal bar)
   Structural low:        $53.80 (lowest low of last 5 bars)
   Buffered stop:         $53.80 - 0.5 × $1.40 (ATR14) = $53.10
   Raw distance:          $55.20 - $53.10 = $2.10
   Clamped (0.75-2× ATR): $2.10 clamp to [$1.05, $2.80] → $2.10
   Initial stop:          $55.20 - $2.10 = $53.10
   Risk per share (1R):   $2.10

Step 3: POSITION SIZE
   Shares = $2,100 ÷ $2.10 = 1000 shares
   Position value:        1000 × $55.20 = $55,200 (78.9% of equity)

Step 4: TRANSACTION COSTS (entry)
   Slippage (10bps):      $55.20 × 0.10% = $0.055 per share
   Fill price:            $55.26
   Commission:            1000 × $0.005 = $5.00

Step 5: TRADE PLAYS OUT (DSL trailing)
   Days 1-5:   T1 trail (bar_low - 1.0×ATR), price drifts up
   Day 6:      Reaches +1R ($57.30) → promotes to T2
   Day 6+:     T2 trail (bar_low - 1.5×ATR), floor = entry ($55.26)
   Day 12:     Reaches +2R ($59.40) → promotes to T3
   Day 12+:    T3 trail (weekly_low - 2.0×ATR), floor = entry + 1.5R ($58.41)
   Day 18:     Pullback. Weekly low triggers T3 trail at $58.50

Step 6: EXIT WITH COSTS
   Exit price (raw):      $58.50
   Slippage (10bps):      $58.50 × 0.10% = $0.059 per share
   Fill price:            $58.44
   Commission:            1000 × $0.005 = $5.00

Step 7: P&L
   Gross P&L:             ($58.44 - $55.26) × 1000 = $3,180.00
   Total costs:           $5.00 + $5.00 + $55.20×0.001×1000 + $58.50×0.001×1000
                        = $5.00 + $5.00 + $55.20 + $58.50 = $123.70
   Net P&L:              $3,180.00 - $123.70 = $3,056.30
   R-multiple:           $3,056.30 ÷ $2,100 = +1.46R
   Return on equity:      +4.37%

Step 9: TRIPLE BARRIER CHECK
   Upper barrier (+3R):   $55.26 + 3×$2.10 = $61.56 — NOT hit
   Lower barrier (-1R):   $55.26 - $2.10 = $53.16 — NOT hit
   Vertical (25 bars):    — reached before either price barrier
   Label: VERTICAL, +1 (positive return at time expiry)

╠══════════════════════════════════════════════════════════════════════════╣
║  PORTFOLIO CONSTRAINTS ENFORCED                                        ║
╠══════════════════════════════════════════════════════════════════════════╣

Max 6 positions at once         → $100K ÷ 6 = ~$16.7K avg, but varies by stop width
35% max per sector              → no more than $35K in Nuclear/Copper/etc
VIX > 30 (RED) = NO entries     → all cash, wait
VIX 18-25 (YELLOW) = QUARTER   → max $250 risk per trade (even if PTRS says FULL)

╠══════════════════════════════════════════════════════════════════════════╣
║  SURVIVORSHIP BIAS HAIRCUT                                             ║
╠══════════════════════════════════════════════════════════════════════════╣

All backtest annual returns reduced by 2% before reporting.
If backtest says 15% annual → report as 13% annual.
Reason: our universe only includes stocks that SURVIVED to today.
Companies that went bankrupt or got delisted are invisible in our data.
This makes our backtest look 1-3% better per year than reality.

╚══════════════════════════════════════════════════════════════════════════╝
"""
