"""Position Tracker — daily trade management intelligence.

Reads open_positions.json, updates each position with:
  - Current DSL tier and trailing stop level
  - Flow-based TP warning (flow < 65 in Tier 1)
  - Daily R-multiple, P&L dollars, and hold duration
  - Target levels (+1R, +2R, +3R) and BE trigger

Usage:
    python -m src.pipeline.position_tracker            # update all positions
    python -m src.pipeline.position_tracker add AAPL    # add new position
    python -m src.pipeline.position_tracker close AAPL  # mark position closed

Called automatically by run_daily.bat after the pipeline.
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
POSITIONS_PATH = DATA_DIR / "open_positions.json"
CLOSED_PATH = DATA_DIR / "closed_positions.json"

CAPITAL = 70_000
RISK_PCT = 0.03
RISK_DOLLARS = CAPITAL * RISK_PCT  # $2,100


def load_positions() -> list[dict]:
    """Load open positions from JSON."""
    if POSITIONS_PATH.exists():
        with open(POSITIONS_PATH) as f:
            return json.load(f)
    return []


def save_positions(positions: list[dict]) -> None:
    """Save open positions to JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(POSITIONS_PATH, "w") as f:
        json.dump(positions, f, indent=2)


def load_closed() -> list[dict]:
    """Load closed position history."""
    if CLOSED_PATH.exists():
        with open(CLOSED_PATH) as f:
            return json.load(f)
    return []


def save_closed(closed: list[dict]) -> None:
    """Save closed position history."""
    with open(CLOSED_PATH, "w") as f:
        json.dump(closed, f, indent=2)


def add_position(
    ticker: str,
    entry_price: float,
    entry_date: str,
    atr14: float,
    shares: int | None = None,
    initial_stop: float | None = None,
) -> dict:
    """Create a new position record.

    If shares not given, sizes to 3% of $70K capital.
    If initial_stop not given, uses entry - 2*ATR (simplified DSL).
    """
    if initial_stop is None:
        initial_stop = round(entry_price - 2.0 * atr14, 2)

    risk_per_share = entry_price - initial_stop
    if risk_per_share <= 0:
        risk_per_share = atr14  # fallback

    if shares is None:
        shares = int(RISK_DOLLARS / risk_per_share) if risk_per_share > 0 else 0

    position = {
        "ticker": ticker,
        "entry_price": round(entry_price, 2),
        "entry_date": entry_date,
        "shares": shares,
        "atr14_at_entry": round(atr14, 4),
        "risk_per_share": round(risk_per_share, 4),
        "initial_stop": round(initial_stop, 2),
        "current_stop": round(initial_stop, 2),
        "current_tier": 1,
        "peak_r": 0.0,
        "be_triggered": False,
        "current_r": 0.0,
        "current_flow": 0,
        "tp_warning": False,
        "days_held": 0,
        "target_1r": round(entry_price + risk_per_share, 2),
        "target_2r": round(entry_price + 2 * risk_per_share, 2),
        "target_3r": round(entry_price + 3 * risk_per_share, 2),
        "be_trigger": round(entry_price + 0.5 * risk_per_share, 2),
        "last_updated": str(date.today()),
    }

    positions = load_positions()

    # Check for duplicate
    existing = [p for p in positions if p["ticker"] == ticker]
    if existing:
        print(f"[pos] WARNING: {ticker} already has an open position. Not adding duplicate.")
        return existing[0]

    positions.append(position)
    save_positions(positions)
    print(f"[pos] Added {ticker}: entry ${entry_price:.2f}, stop ${initial_stop:.2f}, "
          f"{shares} shares, risk ${risk_per_share * shares:.0f}")
    return position


def close_position(ticker: str, exit_price: float | None = None, reason: str = "manual") -> dict | None:
    """Close a position and move it to closed history."""
    positions = load_positions()
    pos = None
    remaining = []
    for p in positions:
        if p["ticker"] == ticker:
            pos = p
        else:
            remaining.append(p)

    if pos is None:
        print(f"[pos] {ticker} not found in open positions.")
        return None

    pos["exit_date"] = str(date.today())
    pos["exit_price"] = round(exit_price, 2) if exit_price else pos.get("last_close", 0)
    pos["exit_reason"] = reason
    entry = pos["entry_price"]
    risk = pos["risk_per_share"]
    if risk > 0 and pos["exit_price"] > 0:
        pos["final_r"] = round((pos["exit_price"] - entry) / risk, 3)
    else:
        pos["final_r"] = 0.0

    save_positions(remaining)

    closed = load_closed()
    closed.append(pos)
    save_closed(closed)

    print(f"[pos] Closed {ticker} at ${pos['exit_price']:.2f} | R={pos['final_r']:+.2f} | Reason: {reason}")
    return pos


def update_all_positions(panel: pd.DataFrame | None = None, scores: pd.DataFrame | None = None) -> list[dict]:
    """Update every open position with current price data and DSL levels.

    Parameters
    ----------
    panel : daily price panel (must have ticker, date, open, high, low, close)
    scores : daily scores (must have ticker, date, flow_100)

    If not provided, loads from parquet files.
    """
    from src.data.panel_builder import PANEL_DAILY
    from src.scanner.score_runner import SCORES_DAILY

    positions = load_positions()
    if not positions:
        return []

    if panel is None:
        if not PANEL_DAILY.exists():
            print("[pos] No panel data available.")
            return positions
        panel = pd.read_parquet(PANEL_DAILY)
        panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()

    if scores is None:
        if SCORES_DAILY.exists():
            scores = pd.read_parquet(SCORES_DAILY)
            scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()

    today = date.today()
    updated = []

    for pos in positions:
        ticker = pos["ticker"]
        entry_price = pos["entry_price"]
        risk = pos["risk_per_share"]
        atr14 = pos["atr14_at_entry"]
        entry_date = pd.Timestamp(pos["entry_date"])

        # Get price bars since entry
        tkr_panel = panel[panel["ticker"] == ticker].sort_values("date")
        if tkr_panel.empty:
            updated.append(pos)
            continue

        bars_since_entry = tkr_panel[tkr_panel["date"] > entry_date]
        if bars_since_entry.empty:
            # Same-day entry, no bars yet
            pos["days_held"] = 0
            pos["last_updated"] = str(today)
            updated.append(pos)
            continue

        # Walk DSL logic forward to compute current tier + stop
        trail_stop = pos["initial_stop"]
        highest_tier = 1
        be_triggered = False
        peak_r = 0.0

        for _, bar in bars_since_entry.iterrows():
            bar_high = float(bar["high"])
            bar_low = float(bar["low"])
            bar_close = float(bar["close"])

            # Update R-multiple
            current_r = (bar_close - entry_price) / risk if risk > 0 else 0
            high_r = (bar_high - entry_price) / risk if risk > 0 else 0
            peak_r = max(peak_r, high_r)

            # Breakeven trigger at +0.5R
            if not be_triggered and high_r >= 0.5:
                be_triggered = True

            # Tier upgrades (lock, never demote)
            if current_r >= 4.0 and highest_tier < 4:
                highest_tier = 4
            elif current_r >= 2.0 and highest_tier < 3:
                highest_tier = 3
            elif current_r >= 1.0 and highest_tier < 2:
                highest_tier = 2

            # Trail computation per tier
            if highest_tier == 1:
                new_trail = bar_low - 1.0 * atr14
                if be_triggered:
                    new_trail = max(new_trail, entry_price)
            elif highest_tier == 2:
                new_trail = bar_low - 1.5 * atr14
                new_trail = max(new_trail, entry_price)
            elif highest_tier == 3:
                new_trail = bar_low - 2.0 * atr14
                new_trail = max(new_trail, entry_price + 1.5 * risk)
            else:  # T4
                trail_a = bar_low - 2.5 * atr14
                trail_b = (entry_price + 2.0 * risk) - 1.0 * atr14
                new_trail = max(trail_a, trail_b)
                new_trail = max(new_trail, entry_price + 3.0 * risk)

            trail_stop = max(trail_stop, new_trail)

        # Latest bar data
        last_bar = bars_since_entry.iloc[-1]
        last_close = float(last_bar["close"])
        last_r = (last_close - entry_price) / risk if risk > 0 else 0
        days_held = len(bars_since_entry)

        # Get current flow from scores
        current_flow = 0
        tp_warning = False
        if scores is not None:
            tkr_scores = scores[(scores["ticker"] == ticker)].sort_values("date")
            if not tkr_scores.empty and "flow_100" in tkr_scores.columns:
                current_flow = float(tkr_scores["flow_100"].iloc[-1])
                # TP warning: flow < 65 while in Tier 1, profitable
                if highest_tier <= 1 and last_r >= 0.2 and current_flow < 65:
                    tp_warning = True

        # Check if stopped out
        stopped_out = last_bar["low"] <= trail_stop
        gap_stop = last_bar["open"] <= trail_stop

        # Update position record
        pos["current_stop"] = round(trail_stop, 2)
        pos["current_tier"] = highest_tier
        pos["peak_r"] = round(peak_r, 3)
        pos["be_triggered"] = be_triggered
        pos["current_r"] = round(last_r, 3)
        pos["current_flow"] = round(current_flow, 1)
        pos["tp_warning"] = tp_warning
        pos["days_held"] = days_held
        pos["last_close"] = round(last_close, 2)
        pos["last_updated"] = str(today)
        pos["pnl_dollars"] = round((last_close - entry_price) * pos["shares"], 2)

        # Generate alerts
        alerts = []
        if stopped_out:
            alerts.append("STOPPED OUT — trail stop hit")
        if gap_stop:
            alerts.append("GAP STOP — opened below stop")
        if tp_warning:
            alerts.append(f"TP WARNING — flow={current_flow:.0f} < 65, consider exit")
        if be_triggered and highest_tier == 1 and last_r < 0.3:
            alerts.append("BE ZONE — stop at breakeven, small profit")
        if highest_tier >= 3:
            alerts.append(f"RUNNER — Tier {highest_tier}, let it ride")
        pos["alerts"] = alerts

        updated.append(pos)

    save_positions(updated)
    return updated


def format_position_report(positions: list[dict]) -> str:
    """Plain-text position report for dashboard output."""
    if not positions:
        return "[pos] No open positions."

    lines = []
    lines.append("=" * 90)
    lines.append("  OPEN POSITIONS — DAILY TRADE MANAGEMENT")
    lines.append("=" * 90)
    lines.append(
        f"  {'Ticker':<6} {'Entry':>8} {'Stop':>8} {'Tier':>4} {'R':>7} "
        f"{'P&L$':>8} {'Flow':>5} {'Days':>4}  Alerts"
    )
    lines.append("-" * 90)

    total_pnl = 0
    for p in positions:
        pnl = p.get("pnl_dollars", 0)
        total_pnl += pnl
        alerts_str = " | ".join(p.get("alerts", []))
        lines.append(
            f"  {p['ticker']:<6} ${p['entry_price']:>7.2f} ${p['current_stop']:>7.2f} "
            f"T{p['current_tier']:>2} {p['current_r']:>+6.2f}R "
            f"${pnl:>+7.0f} {p.get('current_flow', 0):>5.0f} {p['days_held']:>4}"
            f"  {alerts_str}"
        )

    lines.append("-" * 90)
    lines.append(f"  Total open P&L: ${total_pnl:>+,.0f} across {len(positions)} positions")
    lines.append("  Stop = DSL v2.0 tiered trail | Flow < 65 in T1 = TP warning")
    lines.append("=" * 90)
    return "\n".join(lines)


def _add_from_shortlist(ticker: str) -> dict | None:
    """Add position using entry data from today's shortlist."""
    shortlist_path = PROJECT_ROOT / "output" / "shortlist.json"
    if not shortlist_path.exists():
        print(f"[pos] No shortlist found. Run run_daily.bat first.")
        return None

    with open(shortlist_path) as f:
        sl = json.load(f)

    # Search recipe_matches and candidates
    found = None
    for rm in sl.get("recipe_matches", []):
        if rm["ticker"] == ticker:
            found = rm
            break
    if not found:
        for c in sl.get("candidates", []):
            if c["ticker"] == ticker:
                found = c
                break
    if not found:
        print(f"[pos] {ticker} not found in today's shortlist.")
        return None

    levels = found.get("levels", {})
    entry = levels.get("entry", found.get("close", 0))
    atr14 = found.get("atr14", found.get("diagnostics", {}).get("atr14", 0))
    stop = levels.get("stop", 0)
    shares = levels.get("shares", 0)

    if entry <= 0 or atr14 <= 0:
        print(f"[pos] Cannot compute levels for {ticker}. Missing price/ATR data.")
        return None

    return add_position(
        ticker=ticker,
        entry_price=entry,
        entry_date=str(date.today()),
        atr14=atr14,
        shares=shares,
        initial_stop=stop if stop > 0 else None,
    )


def main():
    """CLI entry point."""
    args = sys.argv[1:]

    if not args or args[0] == "update":
        # Default: update all positions
        positions = update_all_positions()
        if positions:
            print(format_position_report(positions))
        else:
            print("[pos] No open positions to update.")

    elif args[0] == "add":
        if len(args) < 2:
            print("Usage: python -m src.pipeline.position_tracker add TICKER [entry_price] [atr14]")
            return
        ticker = args[1].upper()
        if len(args) >= 4:
            # Manual entry: add TICKER entry_price atr14
            entry = float(args[2])
            atr14 = float(args[3])
            shares = int(args[4]) if len(args) >= 5 else None
            add_position(ticker, entry, str(date.today()), atr14, shares)
        else:
            # From shortlist
            _add_from_shortlist(ticker)

    elif args[0] == "close":
        if len(args) < 2:
            print("Usage: python -m src.pipeline.position_tracker close TICKER [exit_price]")
            return
        ticker = args[1].upper()
        exit_price = float(args[2]) if len(args) >= 3 else None
        close_position(ticker, exit_price)

    elif args[0] == "list":
        positions = load_positions()
        if positions:
            print(format_position_report(positions))
        else:
            print("[pos] No open positions.")

    else:
        print("Unknown command. Use: update | add | close | list")


if __name__ == "__main__":
    main()
