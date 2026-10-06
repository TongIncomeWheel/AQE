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
from . import condition_evaluator as CE
from . import condition_ledger as CL
from . import condition_state as CS
from . import live_measures as LM

_ET = ZoneInfo("America/New_York")


def rows_with_conditions(pma_doc: dict | None) -> list[dict]:
    if not pma_doc:
        return []
    return [r for r in (pma_doc.get("rows") or []) if r.get("conditions")]


def run_condition_cycle(pma_doc: dict | None, quotes: dict, now_et: datetime,
                        run_date: str, export: dict | None = None,
                        held_events: list[dict] | None = None) -> dict:
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
        defaults = DEF.synthesize_rows(export, pma_doc)
    except Exception:  # noqa: BLE001 -- defaults must never take the committee rows down
        defaults = []
    rows = rows + defaults
    summary["defaults"] = len(defaults)
    held_events = held_events or []
    if not rows:
        # No condition rows, but held-position events still go out -- in the
        # same single mail (PM 2026-10-06).
        if held_events:
            summary["held_events"] = [e.get("ticker") for e in held_events]
            _maybe_email_digest([], now_et, held_events)
        return summary
    summary["enabled"] = True
    summary["rows"] = len(rows)

    today = now_et.date()
    tickers = [r.get("ticker") for r in rows if r.get("ticker")]

    try:
        from src.data.fmp_client import FMPClient
        client = FMPClient()
    except Exception:  # noqa: BLE001
        summary["errors"] += 1
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

            eval_result = CE.evaluate_conditions(row, live, now_et)
            if eval_result is None:
                continue

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

            line = CL.build_ledger_line(
                ticker, eval_result, fired_states, vol_x=vol_x,
                session_vwap=vwap_info, rs_today=rs, legacy_vol_pace=legacy_pace,
                elder_live=live.get("elder"),
                now=now_et.astimezone(ZoneInfo("Asia/Singapore")))
            CL.append_line(run_date, line)

            # Two states stay in the ledger (PMA's scorecard reads it) but
            # are NOT cards of their own (PM 2026-10-03): ANALYST_OUT
            # ("analyst fail is nonsense ... it wouldn't be published") shows
            # as a ✗ on that seat inside whichever card the name next earns;
            # EXIT_LINE_WARN is a name the PM does NOT hold crossing an exit
            # line ("why would I care about an exit I don't own?") -- only a
            # HELD position's exit line is worth an email.
            card_states = [s for s in fired_states
                           if s not in ("ANALYST_OUT", "EXIT_LINE_WARN")]
            if card_states:
                cards.append((ticker, row, eval_result, card_states, live))
        except Exception:  # noqa: BLE001 — one name's failure never blocks the rest
            summary["errors"] += 1
            continue

    if any_fired:
        CS.save_condition_state(state)
    if cards:
        summary["cards"] = [c[0] for c in cards]
    if held_events:
        summary["held_events"] = [e.get("ticker") for e in held_events]
    if cards or held_events:
        _maybe_email_digest(cards, now_et, held_events)

    return summary


def _num(v) -> float | None:
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _maybe_email_digest(cards: list[tuple], now_et: datetime,
                        held_events: list[dict] | None = None) -> None:
    """§7: "In shadow, nothing in §6 is emailed." The config flag is the
    ONLY gate — everything above (evaluation, state, ledger) runs
    identically in both modes. `cards` = [(ticker, row, eval_result,
    fired_states, live), ...] for this cycle; one send for all of them."""
    from . import config as C
    if not C.PMA_CONDITIONS_LIVE:
        return
    try:
        from .emailer import send_condition_digest
        send_condition_digest(cards, now_et, held_events)
    except Exception:  # noqa: BLE001
        pass
