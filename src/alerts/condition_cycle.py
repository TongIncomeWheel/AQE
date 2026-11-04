"""AQE handoff D123/R21 (2026-10-02) — orchestration for one cycle's worth
of condition-watching work. This is the impure glue (network + file I/O)
between the pure pieces (live_measures.py, condition_evaluator.py,
condition_state.py, condition_ledger.py) and engine.py's own cycle loop.

Runs for EVERY PMA row carrying a `conditions` block, every cycle, in both
shadow and live mode — only the EMAIL side is gated by config.
PMA_CONDITIONS_LIVE (handoff §7). Never raises: one name's fetch failure
must not block the other ~49.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from . import condition_data as CD
from . import config as _cfg
from . import condition_evaluator as CE
from . import condition_ledger as CL
from . import condition_state as CS
from . import live_measures as LM

_ET = ZoneInfo("America/New_York")
from .pma_levels import MK_ENTRY_STATES as PMA_MK_ENTRY_STATES  # noqa: E402


def rows_with_conditions(pma_doc: dict | None) -> list[dict]:
    """Rows of the LATEST committee run that carry a `conditions` block
    (carried-forward rows from older runs are not watched -- PM 2026-10-12)."""
    if not pma_doc:
        return []
    from . import pma_levels as PMA
    return [r for r in (pma_doc.get("rows") or [])
            if r.get("conditions") and PMA.is_latest_run_row(pma_doc, r)]


def _last_weekday_before(d):
    from datetime import timedelta
    x = d - timedelta(days=1)
    while x.weekday() >= 5:
        x -= timedelta(days=1)
    return x


def data_meta(pma_doc: dict | None, pma_stale_doc: dict | None, export: dict | None,
              now_et: datetime) -> dict:
    """Which data this cycle is running on, for the digest header: the PMA run
    and session, the AQE export date and the close it covers, and whether the
    export is current (covers at least the last completed session). A stale
    export means AQE-default names are skipped; a PMA file for another session
    means no committee rows."""
    from datetime import date
    from . import condition_data as CD
    meta: dict = {"pma_run": None, "pma_session": None, "pma_missing": None,
                  "aqe_date": None, "aqe_covers": None, "aqe_current": None}
    if pma_doc:
        meta["pma_run"], meta["pma_session"] = pma_doc.get("run_date"), pma_doc.get("session")
    else:
        meta["pma_missing"] = (pma_stale_doc or {}).get("session") or "none"
    raw = str((export or {}).get("date") or "")[:10]
    if raw:
        meta["aqe_date"] = raw
        try:
            d = date.fromisoformat(raw)
            meta["aqe_covers"] = _last_weekday_before(d).isoformat()
            meta["aqe_current"] = (meta["aqe_covers"]
                                   >= CD._prior_session(now_et.date()).isoformat())
        except ValueError:
            meta["aqe_current"] = None
    return meta


def run_condition_cycle(pma_doc: dict | None, quotes: dict, now_et: datetime,
                        run_date: str, export: dict | None = None,
                        held_events: list[dict] | None = None,
                        meta: dict | None = None) -> dict:
    """Returns a summary dict for the caller's own cycle summary. Mutates
    and persists condition_state.json; appends one ledger line per row
    with `conditions`, every cycle, regardless of whether anything fired.

    Rows = PMA rows carrying `conditions` + AQE-default rows synthesized
    from `export` (committee rows that arrived without conditions, and
    Longlist/Elder names outside the book -- condition_defaults.py)."""
    summary = {"enabled": False, "rows": 0, "fired": {}, "errors": 0, "defaults": 0}
    rows = rows_with_conditions(pma_doc)
    try:
        from . import condition_defaults as DEF
        # AQE-default names come from the export; a stale export (older than
        # the last completed close) must not seed them (PM 2026-10-12).
        defaults = ([] if (meta or {}).get("aqe_current") is False
                    else DEF.synthesize_rows(export, pma_doc))
    except Exception:  # noqa: BLE001 -- defaults must never take the committee rows down
        defaults = []
    rows = rows + defaults
    try:
        rows = DEF.apply_deal_pinned(rows, export)            # R44: no buy trigger for a pending-takeover target
    except Exception:  # noqa: BLE001
        pass
    # PM 2026-11-04: stamp the export's M&A flag on every row (committee rows come from pma_levels, which has none) so every
    # alert card carries it. A missing export or ticker leaves the row unstamped (no claim either way).
    try:
        _byt = {r.get("ticker"): r for r in ((export or {}).get("daily_list") or []) + ((export or {}).get("held_positions") or [])}
        rows = [dict(r, **{k: _byt[r["ticker"]][k] for k in ("ma_status", "ma_note") if k in _byt.get(r.get("ticker"), {})})
                if r.get("ticker") in _byt else r for r in rows]
    except Exception:  # noqa: BLE001
        pass
    # Conductor/PM 2026-11-05: a name on the committee book or in the alert universe that LEFT the AQE list today (it failed both list gates) is
    # flagged on its card; the card says it is still watched here but AQE's own scores no longer list it. No claim when the export has no churn block.
    try:
        from src.data.list_churn import leavers_by_ticker as _leavers
        _left = _leavers(export)
        if _left:
            rows = [dict(r, left_list=_left[r["ticker"]]) if r.get("ticker") in _left else r for r in rows]
    except Exception:  # noqa: BLE001
        pass
    summary["defaults"] = len(defaults)
    held_events = held_events or []
    mk = (meta or {}).get("market_kill") or {}
    market_broken, just_broke = bool(mk.get("broken")), bool(mk.get("just_broke"))
    if not rows:
        # No condition rows, but held-position events still go out -- in the
        # same single mail (PM 2026-10-06).
        email = None
        if held_events or just_broke:
            summary["held_events"] = [e.get("ticker") for e in held_events]
            email = _maybe_email_digest([], now_et, held_events, meta)
        summary["_notice"] = _notice_inputs([], held_events, meta, email)
        return summary
    summary["enabled"] = True
    summary["rows"] = len(rows)
    # Restore the day's ledger from Drive first (a rebuilt container starts with
    # an empty disk), publish after the loop. Loud on failure.
    summary["ledger_sync"] = CL.sync_with_drive(run_date)

    today = now_et.date()
    tickers = [r.get("ticker") for r in rows if r.get("ticker")]

    try:
        from src.data.fmp_client import FMPClient
        client = FMPClient()
    except Exception:  # noqa: BLE001
        summary["errors"] += 1
        summary["_notice"] = _notice_inputs([], held_events, meta, None)
        return summary

    profiles = CD.ensure_volume_profiles(client, tickers, today)
    # Daily history for the live Elder read -- cached once per day, panel
    # fast path only when fresh (see condition_data.ensure_daily_history).
    try:
        histories = CD.ensure_daily_history(client, tickers, today)
    except Exception:  # noqa: BLE001 -- a card line, never the cycle
        histories = {}

    seeds = CD.load_cached_seeds(today.isoformat())   # EMA warm-up, built with the profiles

    spy_bars_today = CD.fetch_today_bars(client, "SPY", today)
    spy_quote = quotes.get("SPY")

    state = CS.load_condition_state()
    any_fired = False
    # One email per CYCLE, not per ticker (PM 2026-10-03: "I don't want
    # individual ticker based alerts. The alerts should run every 15mins").
    # Every row that changed state this cycle becomes one card in a single
    # digest sent after the loop.
    cards: list[tuple] = []

    for row in rows:
        ticker = row.get("ticker")
        quote = quotes.get(ticker)
        if not ticker or not quote:
            continue
        try:
            today_bars = CD.fetch_today_bars(client, ticker, today)
            profile = profiles.get(ticker) or {}
            vol_x = LM.vol_x(today_bars, profile)
            candles = LM.hourly(today_bars)
            vwap_info = LM.session_vwap(candles)
            rs = LM.rs_today(quote, spy_quote) if spy_quote else None

            live = {
                "price": _num(quote.get("price")),
                "day_high": _num(quote.get("day_high")),
                "day_low": _num(quote.get("day_low")),
                "open": _num(quote.get("open")),
                "last_hourly_close": candles[-1]["close"] if candles else None,
                "hourly_closes": [c["close"] for c in candles],
                "vwap": vwap_info,
                "vol_x": vol_x,
                "opening_range": LM.opening_range(today_bars),
                "rs_today": rs,
                "atr": _num(row.get("atr_14d")),
                "cob": {},  # see live_measures.py / module notes: COB word
                           # resolution needs a PMA-side field mapping not
                           # yet specified; every elder_*/ma_above/
                           # choch_bearish/age_ge word reads NOT_YET until
                           # that mapping exists, never guessed.
            }

            # Live Elder (provisional, PM ask 2026-10-04) -- display + ledger
            # only; never evaluates a PMA COB word (handoff §5).
            try:
                import pandas as _pd
                from . import live_elder as LE
                hist = histories.get(ticker) or []
                live["elder"] = LE.elder_live(_pd.DataFrame(hist) if hist else None,
                                              live["price"], today)
            except Exception:  # noqa: BLE001
                live["elder"] = {"elder_live": None, "impulse_live": None,
                                 "elder_prev": None, "impulse_prev": None}

            # EMA8 / EMA20 figures (PM 2026-10-06) -- display only, never an
            # input to evaluate_conditions.
            try:
                from . import live_ema as LEMA
                live["ema"] = LEMA.build(seeds.get(ticker), today_bars,
                                         histories.get(ticker), live["price"])
            except Exception:  # noqa: BLE001
                live["ema"] = {"m15": None, "daily": None}

            # Same-day U&R verdict on the DAILY reference levels (PM
            # 2026-10-07). Reads the cached daily history + today's low and
            # spot; never an input to buy_met.
            try:
                from . import live_unr as LU
                day_low = live["day_low"]
                if day_low is None:
                    lows = [b.get("low") for b in today_bars if b.get("low") is not None]
                    day_low = min(lows) if lows else None
                live["unr"] = LU.evaluate(histories.get(ticker), live["price"], day_low,
                                          vol_x=(vol_x or {}).get("so_far"), today=today)
            except Exception:  # noqa: BLE001
                live["unr"] = {"status": "UNKNOWN", "armed": [], "levels": [],
                               "stop": None, "volume": {}, "reason": "error"}
            # Valen's entry trigger: a 15-min candle closing above VWAP.
            try:
                live["vwap_trigger"] = LM.vwap_trigger(today_bars)
            except Exception:  # noqa: BLE001
                live["vwap_trigger"] = {"state": "NOT_READY"}

            eval_result = CE.evaluate_conditions(row, live, now_et)
            if eval_result is None:
                continue
            eval_result["unr_armed"] = (_cfg.CONDITION_UNR_ENABLED and live["unr"]["status"] == "ARMED")
            eval_result["unr_trigger"] = (eval_result["unr_armed"]
                                          and live["vwap_trigger"].get("state") == "TRIGGERED")
            eval_result["unr_spot"] = live["price"]
            eval_result["unr_stop"] = live["unr"].get("stop")

            is_held = row.get("class") == "HELD"
            fired_states = CS.advance(state, run_date, ticker, eval_result, is_held=is_held)
            if fired_states:
                any_fired = True
                summary["fired"][ticker] = fired_states

            # §8.1: the old linear-clock figure, logged alongside vol_x for
            # a two-week side-by-side comparison -- never retrofitted into
            # the currently-live trigger path's own vol_pace.
            try:
                from . import intraday as legacy_intraday
                legacy_pace = legacy_intraday.measures(
                    quote, live["atr"], now_et).get("vol_pace")
            except Exception:  # noqa: BLE001
                legacy_pace = None

            # R40: market condition broken -> no new entry states for names the PM
            # does not hold. Ledgered, not dropped; stops/exits/failures still go.
            suppressed = ([x for x in fired_states if x in PMA_MK_ENTRY_STATES]
                          if (market_broken and not is_held) else [])
            line = CL.build_ledger_line(
                ticker, eval_result, fired_states, vol_x=vol_x,
                session_vwap=vwap_info, rs_today=rs, legacy_vol_pace=legacy_pace,
                elder_live=live.get("elder"),
                now=now_et.astimezone(ZoneInfo("Asia/Singapore")))
            if suppressed:
                line["suppressed_by_market_kill"] = suppressed
                summary["suppressed"] = summary.get("suppressed", 0) + len(suppressed)
            CL.append_line(run_date, line)

            # Two states stay in the ledger (PMA's scorecard reads it) but
            # are NOT cards of their own (PM 2026-10-03): ANALYST_OUT
            # ("analyst fail is nonsense ... it wouldn't be published") shows
            # as a ✗ on that seat inside whichever card the name next earns;
            # EXIT_LINE_WARN is a name the PM does NOT hold crossing an exit
            # line ("why would I care about an exit I don't own?") -- only a
            # HELD position's exit line is worth an email.
            card_states = [s for s in fired_states
                           if s not in ("ANALYST_OUT", "EXIT_LINE_WARN") and s not in suppressed]
            if card_states:
                cards.append((ticker, row, eval_result, card_states, live))
        except Exception:  # noqa: BLE001 — one name's failure never blocks the rest
            summary["errors"] += 1
            continue

    if any_fired:
        CS.save_condition_state(state)
    summary["ledger_sync_end"] = CL.sync_with_drive(run_date)
    if cards:
        summary["cards"] = [c[0] for c in cards]
    if held_events:
        summary["held_events"] = [e.get("ticker") for e in held_events]
    email = None
    if cards or held_events or just_broke:
        email = _maybe_email_digest(cards, now_et, held_events, meta)
    summary["_notice"] = _notice_inputs(cards, held_events, meta, email)

    return summary


def _notice_inputs(cards: list[tuple], held_events: list[dict] | None, meta: dict | None,
                   email: dict | None) -> dict:
    """What src/alerts/notice.py needs to write the cockpit notice from the SAME
    cards the email rendered. Split full cards / one-line U&R rows exactly as
    build_condition_digest does."""
    from . import config as C
    compact = (C.CONDITION_CARD_STYLE or "compact") != "full"
    setup_rows = [c for c in cards if compact and c[3] == ["UNR_ARMED"]]
    full = [c for c in cards if c not in setup_rows]
    return {"cards": full, "setup_rows": setup_rows, "held_events": list(held_events or []),
            "meta": meta, "email": email}


def _num(v) -> float | None:
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _maybe_email_digest(cards: list[tuple], now_et: datetime,
                        held_events: list[dict] | None = None,
                        meta: dict | None = None) -> None:
    """§7: "In shadow, nothing in §6 is emailed." The config flag is the
    ONLY gate — everything above (evaluation, state, ledger) runs
    identically in both modes. `cards` = [(ticker, row, eval_result,
    fired_states, live), ...] for this cycle; one send for all of them."""
    from . import config as C
    if not C.PMA_CONDITIONS_LIVE:
        return {"ok": None, "reason": "shadow mode"}
    try:
        from .emailer import send_condition_digest, build_condition_digest
        res = dict(send_condition_digest(cards, now_et, held_events, meta) or {})
        if "subject" not in res:
            try:
                res["subject"] = build_condition_digest(cards, now_et, held_events, meta)[0]
            except Exception:  # noqa: BLE001
                pass
        return res
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
