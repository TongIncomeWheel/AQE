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
    """The daily export — the MORE RECENT of the local working copy and Drive.

    A "local copy" is not reliably fresh: `output/aqe_daily_export.json` is
    committed to git as a backup record, so a fresh checkout (every GitHub
    Actions run) or a freshly-redeployed HF Space (before that container's own
    pipeline run) can see a LOCAL file that is actually the stale git-committed
    snapshot — while Drive already has the real, current export from whichever
    environment (Space or the GH pipeline backstop) actually ran the pipeline.
    Trusting local-first silently starved the freshness guard and blocked every
    alert for days without ever raising. Fast path: if local already carries
    today's date, skip the Drive round-trip (the common case). Otherwise compare
    `exported_at`/`date` and return whichever export is newer.
    """
    local = None
    try:
        if EXPORT_JSON.exists():
            local = json.loads(EXPORT_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass

    try:
        today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        if local and str(local.get("date") or "")[:10] == today:
            return local
    except Exception:  # noqa: BLE001
        pass

    drive = None
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text("aqe_daily_export.json")
            if txt:
                drive = json.loads(txt)
    except Exception:  # noqa: BLE001
        pass

    if drive is None:
        return local
    if local is None:
        return drive

    def _key(exp: dict) -> str:
        return str(exp.get("exported_at") or exp.get("date") or "")

    return drive if _key(drive) > _key(local) else local


def _lens_count(r: dict) -> int:
    return sum(bool(r.get(k)) for k in ("on_longlist", "on_elder", "on_qs"))


def in_alert_universe(r: dict) -> bool:
    """Strength gate for an UNHELD name (PM ruling 2026-08-04).

    On at least TWO of {Longlist, Elder, QS}, or on QS alone. Multi-lens
    agreement, or the one lens whose whole purpose is finding what the others
    miss — nothing in between.

    The old universe had NO strength gate at all: any monitored name touching a
    level fired, which is why it read as noise. It also still drew from
    `_radar_pool` (retired Signal Radar), so alerts came from a lens no surface
    reads any more.
    """
    n = _lens_count(r)
    if n >= 2:
        return True
    return bool(r.get("on_qs")) and not r.get("on_longlist") and not r.get("on_elder")


def monitored(export: dict) -> list[dict]:
    """Flatten the export into a dedup'd monitor list of {ticker, source, record}.

    Universe = held (always, no strength gate — you own it, conviction is
    irrelevant to risk) + unheld names passing `in_alert_universe`.

    `_radar_pool` is NO LONGER a source: it is Signal Radar, retired.
    """
    held_recs = export.get("held_positions") or []
    held_tickers = {r.get("ticker") for r in held_recs if r.get("ticker")}

    out: list[dict] = []
    for r in held_recs:
        if r.get("ticker"):
            out.append({"ticker": r["ticker"], "source": "held",
                        "is_held": True, "record": r})

    seen = set(held_tickers)
    for _src in ("daily_list",):
        for r in export.get(_src) or []:
            if not in_alert_universe(r):
                continue
            tk = r.get("ticker")
            if not tk or tk in seen:
                continue
            seen.add(tk)
            out.append({"ticker": tk, "source": r.get("source") or _src,
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

    day_hi = _n(quote.get("day_high"))
    day_lo = _n(quote.get("day_low"))
    entry = _n(rec.get("entry"))
    # The structural bracket is the single source of levels (mechanical DSL retired).
    _bracket = rec.get("bracket") or {}
    _b_stop = _n(_bracket.get("stop"))
    _b_risk = _n(_bracket.get("risk"))
    _b_price = _n(_bracket.get("price")) or entry
    # Stop: held names use their live position SL; others use the structural stop.
    stop = _n(rec.get("held_sl")) if is_held else _b_stop
    # Buy-zone trigger = +0.5R above the bracket price (structural risk unit).
    be = (_b_price + 0.5 * _b_risk
          if (_b_price is not None and _b_risk is not None) else None)

    trig: list[dict] = []

    def add(level, label, level_price, note=""):
        trig.append({
            "ticker": ticker, "source": source, "is_held": is_held,
            "level": level, "label": label,
            "level_price": round(level_price, 2) if level_price is not None else None,
            "live_px": round(live, 2), "note": note,
        })

    # Only THREE actionable, non-stale level events are emailed (PM ruling):
    #   Hit-buy / buy-zone, fresh Breakout, Approaching-stop. TP-hit / Fib / MA /
    #   RVol were removed — they fired on names long past the level (stale noise).
    # Every condition is a BOUNDED band, so a name far past a level never fires.

    # --- MOVE: plain +/-2% vs prior close. A NOTIFICATION, not a decision
    # level and not an entry signal (PM ruling 2026-08-04) — "something is
    # happening here", nothing more. Expect it on a third to a half of the
    # universe on an active day; that is the intended cost of a movement tape.
    prev_close = _n(quote.get("prev_close"))
    if prev_close and prev_close > 0:
        chg = (live / prev_close - 1) * 100
        if abs(chg) >= C.MOVE_PCT:
            add("MOVE", f"Moved {chg:+.1f}%", prev_close,
                f"{chg:+.1f}% vs prior close {prev_close:.2f} — movement only, "
                f"no entry claim")

    # --- BOS: closed above the last CONFIRMED pivot high. The structural
    # breakout: price clearing the level that was capping it, rather than a
    # fixed % over an arbitrary reference (the old rule) or a target already
    # reached (TP1). Sourced from the daily read, so it changes once per day.
    _lph = (rec.get("last_pivot_high") or {}).get("price")
    if not is_held and rec.get("structure_shift") == "BULLISH_BOS":
        add("BOS", "Break of structure", _lph,
            f"closed above the last confirmed pivot high"
            + (f" {_lph:.2f}" if _lph else "") + f" (live {live:.2f})")

    # --- AT A DECISION LEVEL: within X% of the stop, TP1 or the pivot high.
    # Deliberately NOT every structural level — within 2% of ANY of the ~15
    # levels a row carries caught 72% of the universe on the 2026-08-04
    # export; restricted to these three it was 2 of 83.
    _tp1 = next((t.get("price") for t in (_bracket.get("targets") or [])
                 if t.get("tp") == "TP1"), None)
    for _lname, _lvl in (("stop", _b_stop), ("TP1", _tp1),
                         ("pivot high", _lph)):
        _lvl = _n(_lvl)
        if _lvl and _lvl > 0 and abs(live / _lvl - 1) * 100 <= C.NEAR_LEVEL_PCT:
            add("AT_LEVEL", f"At {_lname}", _lvl,
                f"{abs(live / _lvl - 1) * 100:.1f}% from {_lname} {_lvl:.2f}")
            break                       # one level event per name per poll

    # --- Approaching stop, measured in R so it means the same on every
    # ticker. A flat 5% band spanned 0.4-3.3 ATRs and 0.4-2.5 R across the
    # universe: the same alert, a different warning on every name.
    #
    # For a HELD name the risk unit is the one actually taken — what was paid
    # minus where the stop sits — not the bracket's structural risk. Held rows
    # frequently carry an INVALID bracket (no structural stop passed the
    # gates), so bracket.risk is None on every held position in the 2026-08-04
    # export; without this they would all silently fall back to the flat %.
    _risk_unit = _b_risk
    if is_held:
        _h_entry = _n(rec.get("entry"))
        _h_sl = _n(rec.get("held_sl"))
        if _h_entry and _h_sl and _h_entry > _h_sl:
            _risk_unit = _h_entry - _h_sl
    if stop is not None and stop > 0 and live > stop:
        if _risk_unit and _risk_unit > 0:
            cushion_r = (live - stop) / _risk_unit
            if cushion_r <= C.NEAR_STOP_R:
                add("NEAR_STOP", f"Approaching stop ({'SL' if is_held else 'DSL'})",
                    stop, f"{cushion_r:.2f}R above stop {stop:.2f} "
                          f"({(live / stop - 1) * 100:.1f}%)")
        elif live <= stop * (1 + C.NEAR_STOP_PCT / 100):
            add("NEAR_STOP", f"Approaching stop ({'SL' if is_held else 'DSL'})",
                stop, f"{(live / stop - 1) * 100:.1f}% above stop {stop:.2f} "
                      f"(no risk unit — % fallback)")

    # --- HELD-ONLY: a veto struck something you own. Risk-side, rare, and the
    # kind of thing that should not wait for a price level to surface it.
    if is_held:
        _vetoes = ((rec.get("qs") or {}).get("vetoes")) or []
        if _vetoes:
            add("VETO_HELD", "Veto fired on a held name", None,
                f"QS veto: {', '.join(_vetoes)}")

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


def _export_age_days(export: dict):
    """Calendar days between the export's scan date and today (None if unknown)."""
    try:
        d = (export.get("date") or "")[:10]
        scan = datetime.strptime(d, "%Y-%m-%d").date()
        return (datetime.now(ZoneInfo("America/New_York")).date() - scan).days
    except Exception:  # noqa: BLE001
        return None


def run_alert_cycle(send_email: bool = True, force: bool = False) -> dict:
    """One poll cycle. Returns a summary dict; never raises.

    force=True bypasses the market-hours gate (used by the UI "Refresh now").
    """
    summary = {"ok": False, "checked": 0, "new_triggers": 0,
               "emailed": False, "reason": None, "triggers": [], "export_date": None}

    if not force and not in_market_window():
        summary["reason"] = "outside US market hours"
        return summary

    export = load_export()
    if not export:
        summary["reason"] = "no export available"
        return summary
    summary["export_date"] = export.get("date")

    # Freshness guard — never blast stale levels (e.g. the pipeline didn't run).
    age = _export_age_days(export)
    if age is not None and age > C.MAX_EXPORT_AGE_DAYS and not force:
        summary["reason"] = (f"export is {age}d old (> {C.MAX_EXPORT_AGE_DAYS}) — "
                             "skipping to avoid stale alerts")
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

    # Log every fired trigger to the rolling history (powers the 36h on-screen feed).
    if fresh:
        try:
            S.append_history(fresh)
        except Exception:  # noqa: BLE001
            pass

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
