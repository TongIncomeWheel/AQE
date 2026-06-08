"""Live alert engine — evaluate monitored tickers against their key levels.

Pure-data design: every level the engine checks lives on the daily export record
(absolute prices), so the same evaluation runs identically in the in-app thread
and the GitHub Actions backstop, with no dependency on the runtime parquet panel.

A *trigger* is one (ticker, level) crossing. `run_alert_cycle` is the orchestrator:
load export + held → fetch 15-min quotes → evaluate → dedup → email digest → save
state. It never raises; data gaps degrade to "nothing to alert".
"""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.alerts import config as C
from src.alerts import state as S
from src.data.paths import EXPORT_JSON


# ---------------------------------------------------------------------------
# Export loading (local working copy, else Drive)
# ---------------------------------------------------------------------------

def load_export() -> dict | None:
    """The daily export — local copy first, then Drive (for the GH backstop)."""
    try:
        if EXPORT_JSON.exists():
            return json.loads(EXPORT_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text("aqe_daily_export.json")
            if txt:
                return json.loads(txt)
    except Exception:  # noqa: BLE001
        pass
    return None


def monitored(export: dict) -> list[dict]:
    """Flatten the export into a dedup'd monitor list of {ticker, source, record}.

    Held names win (their record carries the live trade context); otherwise the
    richest candidate tier wins (PE > top > longlist > watchlist).
    """
    held_recs = export.get("held_positions") or []
    held_tickers = {r.get("ticker") for r in held_recs if r.get("ticker")}

    out: list[dict] = []
    for r in held_recs:
        if r.get("ticker"):
            out.append({"ticker": r["ticker"], "source": "held",
                        "is_held": True, "record": r})

    seen = set(held_tickers)
    for src, tier in (("PE", "edge_list"), ("top", "top_picks"),
                      ("longlist", "longlist"), ("watchlist", "watchlist")):
        for r in export.get(tier) or []:
            tk = r.get("ticker")
            if not tk or tk in seen:
                continue
            seen.add(tk)
            out.append({"ticker": tk, "source": src,
                        "is_held": False, "record": r})
    return out


# ---------------------------------------------------------------------------
# Per-ticker level evaluation (pure)
# ---------------------------------------------------------------------------

def _n(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def evaluate(ticker: str, source: str, is_held: bool,
             rec: dict, quote: dict) -> list[dict]:
    """Return the list of triggered levels for one ticker given its live quote."""
    live = _n(quote.get("price"))
    if live is None or live <= 0:
        return []

    entry = _n(rec.get("entry"))
    stop = _n(rec.get("held_sl")) if is_held else _n(rec.get("dsl_stop"))
    be = _n(rec.get("dsl_be"))
    tp1 = _n(rec.get("held_tp1")) if is_held else _n(rec.get("dsl_tp_1r"))
    tp2 = _n(rec.get("held_tp2")) if is_held else _n(rec.get("dsl_tp_2r"))
    tp3 = _n(rec.get("dsl_tp_3r"))

    trig: list[dict] = []

    def add(level, label, level_price, note=""):
        trig.append({
            "ticker": ticker, "source": source, "is_held": is_held,
            "level": level, "label": label,
            "level_price": round(level_price, 2) if level_price is not None else None,
            "live_px": round(live, 2), "note": note,
        })

    # --- Entry (candidates only — held names are already in) ---
    if not is_held:
        if stop is not None and be is not None and stop < live <= be:
            add("ENTRY_PULLBACK", "Entry — pullback to buy zone", be,
                f"price in DSL buy zone [{stop:.2f}–{be:.2f}]")
        if entry is not None and live >= entry * (1 + C.BREAKOUT_PCT / 100):
            add("ENTRY_BREAKOUT", "Entry — breakout above trigger",
                entry * (1 + C.BREAKOUT_PCT / 100),
                f"+{C.BREAKOUT_PCT:.0f}% above scan entry {entry:.2f}")

    # --- Approaching stop (within X% above it) ---
    if stop is not None and stop > 0 and stop < live <= stop * (1 + C.NEAR_STOP_PCT / 100):
        cushion = (live / stop - 1) * 100
        add("NEAR_STOP", f"Approaching stop ({'SL' if is_held else 'DSL'})",
            stop, f"{cushion:.1f}% above stop {stop:.2f}")

    # --- Take-profit ladder ---
    for key, label, tp in (("TP1", "TP1 hit", tp1),
                           ("TP2", "TP2 hit", tp2),
                           ("TP3", "TP3 hit", tp3)):
        if tp is not None and live >= tp:
            add(key, label, tp, f"price reached {tp:.2f}")

    # --- RVol spike ---
    vol, avgv = _n(quote.get("volume")), _n(quote.get("avg_volume"))
    if vol is not None and avgv and avgv > 0:
        rv = vol / avgv
        if rv >= C.RVOL_SPIKE:
            add("RVOL", f"RVol spike {rv:.1f}×", None,
                f"volume {vol:,.0f} vs avg {avgv:,.0f}")

    # --- MA support (within tolerance of any MA in the ladder) ---
    for w in C.MA_WINDOWS:
        ma = _n(rec.get(f"ma_{w}"))
        if ma and ma > 0 and abs(live / ma - 1) * 100 <= C.MA_TOL_PCT:
            add(f"MA_{w}", f"At MA{w} support", ma,
                f"{(live / ma - 1) * 100:+.2f}% vs MA{w} {ma:.2f}")

    # --- Fib support (within tolerance of a key retracement) ---
    fib = rec.get("fib") or {}
    retr = (fib.get("retracements") or {}) if isinstance(fib, dict) else {}
    for key in C.FIB_KEYS:
        lvl = _n(retr.get(key))
        if lvl and lvl > 0 and abs(live / lvl - 1) * 100 <= C.FIB_TOL_PCT:
            add(f"FIB_{key}", f"At Fib {key} support", lvl,
                f"{(live / lvl - 1) * 100:+.2f}% vs fib {key} {lvl:.2f}")

    return trig


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def in_market_window() -> bool:
    """True iff the US cash session (padded) is open right now (Mon–Fri)."""
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:  # Sat/Sun
        return False
    mins = now.hour * 60 + now.minute
    return (C.MARKET_OPEN[0] * 60 + C.MARKET_OPEN[1]
            <= mins <= C.MARKET_CLOSE[0] * 60 + C.MARKET_CLOSE[1])


def run_alert_cycle(send_email: bool = True, force: bool = False) -> dict:
    """One poll cycle. Returns a summary dict; never raises.

    force=True bypasses the market-hours gate (used by the UI "Refresh now").
    """
    summary = {"ok": False, "checked": 0, "new_triggers": 0,
               "emailed": False, "reason": None, "triggers": []}

    if not force and not in_market_window():
        summary["reason"] = "outside US market hours"
        return summary

    export = load_export()
    if not export:
        summary["reason"] = "no export available"
        return summary

    mon = monitored(export)
    if not mon:
        summary["reason"] = "no monitored tickers"
        return summary

    tickers = [m["ticker"] for m in mon]
    try:
        from src.data.fmp_client import FMPClient, FMPError
        quotes = FMPClient().get_quotes(tickers)
    except FMPError as exc:
        summary["reason"] = f"quote fetch failed: {exc}"
        return summary
    except Exception as exc:  # noqa: BLE001
        summary["reason"] = f"quote error: {exc}"
        return summary

    summary["checked"] = len(quotes)

    state = S.load_alert_state()
    fresh: list[dict] = []
    for m in mon:
        q = quotes.get(m["ticker"])
        if not q:
            continue
        for t in evaluate(m["ticker"], m["source"], m["is_held"], m["record"], q):
            if not S.is_fired(state, t["ticker"], t["level"]):
                fresh.append(t)
                S.mark_fired(state, t["ticker"], t["level"])

    summary["new_triggers"] = len(fresh)
    summary["triggers"] = fresh

    if fresh and send_email:
        try:
            from src.alerts.emailer import send_digest
            res = send_digest(fresh, export)
            summary["emailed"] = bool(res.get("ok"))
            if not res.get("ok"):
                summary["reason"] = f"email failed: {res.get('reason')}"
        except Exception as exc:  # noqa: BLE001
            summary["reason"] = f"email error: {exc}"

    # Persist dedup state only if we actually recorded new fires (or to roll date)
    S.save_alert_state(state)
    summary["ok"] = True
    return summary
