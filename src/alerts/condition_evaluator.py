"""AQE handoff D123/R21 (2026-10-02) §5 — the pure condition evaluator.

`evaluate_word()` reads ONE word entry (the shape PMA sends: {"w", "level"
or "x", "plain", ...}) against a live-data context and returns "TRUE",
"FALSE", "NOT_YET" or "UNKNOWN_WORD" — never a guess. `NOT_YET` means the
data this word needs isn't ready yet (e.g. before the second hourly
candle); callers must never treat it as FALSE (§5, §9).

`evaluate_conditions()` reads one PMA row's whole `conditions` block (§2's
JSON shape) and returns buy_met/lit/wrong_lit/chased/exit_warn/exit_hit —
everything engine.py needs to drive the state machine in condition_
state.py. Returns None when the row carries no `conditions` at all — the
handoff's own back-compat rule (§9): "a levels file without conditions
behaves exactly as today."

An UNKNOWN_WORD (or any word not in condition_spec.CONDITION_WORDS) can
never complete an ALL-true rule — "skip it" (§2) is read here as "treat it
as never satisfiable", the conservative direction: AQE never fires an
alert on a condition it doesn't understand, it just never confirms one
either.
"""

from __future__ import annotations

from . import condition_spec as S


def _n(v) -> float | None:
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def entry_level(entry: dict) -> float | None:
    """The price level a word is judged against. PMA ships two shapes
    (seen in the real pma_levels.json, 2026-10-03): the SHARED block's
    words carry `level: 32.01`, while every per-seat word and the chase
    line carry `levels: [28.18]`. Reading only `level` left every seat
    word with a price -- and every chase line -- at NOT_YET forever, so
    the analysts count and CHASED silently under-fired in production."""
    if not isinstance(entry, dict):
        return None
    lv = _n(entry.get("level"))
    if lv is not None:
        return lv
    levels = entry.get("levels")
    if isinstance(levels, list) and levels:
        return _n(levels[0])
    return None


def evaluate_word(entry: dict, ctx: dict) -> str:
    """One word, one verdict. `ctx` keys used: price, day_high, day_low,
    open, last_hourly_close, hourly_closes (list, oldest first), vwap
    ({"vwap", "provisional"}), vol_x ({"so_far"}), rs_today, atr,
    is_final_cycle, cob (dict of already-judged COB words)."""
    w = entry.get("w")
    if not w:
        return "UNKNOWN_WORD"
    if S.is_cob_word(w):
        # §5: PMA already judged these at the close. Report as given.
        cob = ctx.get("cob") or {}
        if w not in cob:
            return "NOT_YET"
        return "TRUE" if cob[w] else "FALSE"
    if w not in S.CONDITION_WORDS:
        return "UNKNOWN_WORD"

    level = entry_level(entry)
    x = _n(entry.get("x"))
    price = ctx.get("price")
    is_final = bool(ctx.get("is_final_cycle"))

    if w == "close_above" or w == "close_below":
        if not is_final or price is None or level is None:
            return "NOT_YET"
        ok = price > level if w == "close_above" else price < level
        return "TRUE" if ok else "FALSE"

    if w == "h1_close_above" or w == "h1_close_below":
        h1 = ctx.get("last_hourly_close")
        if h1 is None or level is None:
            return "NOT_YET"
        ok = h1 > level if w == "h1_close_above" else h1 < level
        # PM 2026-10-06: "at times the spot is below the entry but still it
        # flags out as entry." The last COMPLETED hourly candle can sit
        # above the line while price has since slipped back under it. An
        # entry condition is only live while spot is still at or above the
        # line, so a faded breakout reads NOT MET (and, if it was MET, the
        # state machine reports it BACK UNDER THE LEVEL). The mirror word
        # (an exit/invalidation line) is left alone: it judges the close.
        if w == "h1_close_above" and ok and price is not None and price < level:
            ok = False
        return "TRUE" if ok else "FALSE"

    if w == "trade_above" or w == "trade_below":
        if level is None:
            return "NOT_YET"
        if w == "trade_above":
            dh = ctx.get("day_high")
            if dh is None:
                return "NOT_YET"
            return "TRUE" if dh >= level else "FALSE"
        dl = ctx.get("day_low")
        if dl is None:
            return "NOT_YET"
        return "TRUE" if dl <= level else "FALSE"

    if w == "reclaim":
        dl, h1 = ctx.get("day_low"), ctx.get("last_hourly_close")
        if level is None or dl is None or h1 is None:
            return "NOT_YET"
        return "TRUE" if (dl < level and h1 > level) else "FALSE"

    if w == "reject":
        dh, h1 = ctx.get("day_high"), ctx.get("last_hourly_close")
        if level is None or dh is None or h1 is None:
            return "NOT_YET"
        return "TRUE" if (dh > level and h1 < level) else "FALSE"

    if w == "in_zone":
        # Literal §5: "abs(price-L) <= 0.25*ATR, OR day_low <= L+0.25*ATR".
        # The day_low leg only meaningfully gates a level AT OR BELOW the
        # day's low (did price dip down near a support) -- for L well
        # ABOVE the low it is trivially true (any L above the low clears
        # "day_low <= L+buffer"), so this word is really built for support
        # tests, not resistance ones. Transcribed as given, not re-derived.
        atr, dl = ctx.get("atr"), ctx.get("day_low")
        if level is None or price is None or not atr:
            return "NOT_YET"
        near_price = abs(price - level) <= 0.25 * atr
        near_low = dl is not None and dl <= level + 0.25 * atr
        return "TRUE" if (near_price or near_low) else "FALSE"

    if w == "vol_x_ge" or w == "vol_x_le":
        so_far = (ctx.get("vol_x") or {}).get("so_far")
        if so_far is None or x is None:
            return "NOT_YET"
        ok = so_far >= x if w == "vol_x_ge" else so_far <= x
        return "TRUE" if ok else "FALSE"

    if w == "above_vwap_s":
        vwap_info = ctx.get("vwap") or {}
        h1 = ctx.get("last_hourly_close")
        if vwap_info.get("provisional") or vwap_info.get("vwap") is None or h1 is None:
            return "NOT_YET"
        return "TRUE" if h1 > vwap_info["vwap"] else "FALSE"

    if w == "below_vwap_s":
        n = int(x) if x else 1
        vwap_info = ctx.get("vwap") or {}
        closes = ctx.get("hourly_closes") or []
        if vwap_info.get("provisional") or vwap_info.get("vwap") is None:
            return "NOT_YET"
        if len(closes) < n:
            return "NOT_YET"
        last_n = closes[-n:]
        return "TRUE" if all(c < vwap_info["vwap"] for c in last_n) else "FALSE"

    if w == "rs_today_gt_spy":
        rs = ctx.get("rs_today")
        if rs is None:
            return "NOT_YET"
        return "TRUE" if rs > 0 else "FALSE"

    if w == "fade_atr_ge":
        dh, atr = ctx.get("day_high"), ctx.get("atr")
        if dh is None or price is None or not atr or x is None:
            return "NOT_YET"
        return "TRUE" if (dh - price) / atr >= x else "FALSE"

    if w == "clv_ge" or w == "clv_le":
        if not is_final:
            return "NOT_YET"
        dh, dl = ctx.get("day_high"), ctx.get("day_low")
        if price is None or dh is None or dl is None or dh == dl or x is None:
            return "NOT_YET"
        clv = (price - dl) / (dh - dl)
        ok = clv >= x if w == "clv_ge" else clv <= x
        return "TRUE" if ok else "FALSE"

    if w == "red_bar":
        if not is_final:
            return "NOT_YET"
        op = ctx.get("open")
        if price is None or op is None:
            return "NOT_YET"
        return "TRUE" if price < op else "FALSE"

    return "UNKNOWN_WORD"  # pragma: no cover — every CONDITION_WORDS member is handled above


def _word_results(entries: list[dict] | None, ctx: dict) -> list[tuple[dict, str]]:
    return [(e, evaluate_word(e, ctx)) for e in (entries or [])]


def _all_true(results: list[tuple[dict, str]]) -> bool:
    return bool(results) and all(r == "TRUE" for _, r in results)


def _any_true(results: list[tuple[dict, str]]) -> bool:
    return any(r == "TRUE" for _, r in results)


def evaluate_conditions(row: dict, live: dict, now_et) -> dict | None:
    """One PMA row, one cycle. `live` carries price/day_high/day_low/open/
    last_hourly_close/hourly_closes/vwap/vol_x/rs_today/atr/cob (see
    evaluate_word()'s own docstring for the exact keys). Returns None when
    the row has no `conditions` block at all (back-compat, §9)."""
    conditions = row.get("conditions")
    if not conditions:
        return None

    is_final = (now_et.hour * 60 + now_et.minute) >= S.FINAL_CYCLE_HOUR_MIN
    ctx = dict(live)
    ctx["is_final_cycle"] = is_final

    shared = conditions.get("shared") or {}
    no_shared_buy = bool(shared.get("no_shared_buy"))
    shared_buy = _word_results(shared.get("buy"), ctx)
    shared_confirm = _word_results(shared.get("confirm"), ctx)

    analysts = conditions.get("analysts") or []
    counting = [a for a in analysts if a.get("counts", True)]
    lit: list[str] = []
    wrong_lit: list[str] = []
    analyst_detail: dict[str, dict] = {}
    for a in analysts:
        seat = a.get("seat")
        buy_r = _word_results(a.get("buy"), ctx)
        confirm_r = _word_results(a.get("confirm"), ctx)
        wrong_r = _word_results(a.get("wrong"), ctx)
        analyst_detail[seat] = {"buy": buy_r, "confirm": confirm_r, "wrong": wrong_r,
                                "counts": a.get("counts", True)}
        if not a.get("counts", True):
            continue  # advisory supporter (R14) -- shown elsewhere, never counted
        if _any_true(wrong_r):
            wrong_lit.append(seat)
        elif _all_true(buy_r) and _all_true(confirm_r):
            lit.append(seat)

    if no_shared_buy:
        buy_met = bool(counting) and len(lit) > len(counting) / 2.0
    else:
        buy_met = _all_true(shared_buy) and _all_true(shared_confirm)

    chase_entry = shared.get("chase")
    chased = bool(chase_entry) and evaluate_word(chase_entry, ctx) == "TRUE"

    # §5: exit_hit is a DAILY close below an exits[] level; an hourly close
    # below it is only a WARN (exit_warn here), never the full exit_hit.
    exits = conditions.get("exits") or []
    h1 = ctx.get("last_hourly_close")
    price = ctx.get("price")
    exit_warn = None
    if h1 is not None:
        crossed = [e for e in exits if _n(e.get("value")) is not None and h1 < _n(e.get("value"))]
        if crossed:
            exit_warn = max(crossed, key=lambda e: _n(e.get("value")))
    exit_hit = None
    if is_final and price is not None:
        crossed = [e for e in exits if _n(e.get("value")) is not None and price < _n(e.get("value"))]
        if crossed:
            exit_hit = max(crossed, key=lambda e: _n(e.get("value")))

    # §2: "If a word is not in it, AQE logs UNKNOWN_WORD and skips it; it
    # never guesses." Collected across every word list on the row so a
    # new/typo'd word surfaces in the ledger even on a cycle where it
    # wasn't the deciding factor for anything.
    all_results = (shared_buy + shared_confirm
                  + [r for a in analyst_detail.values()
                     for bucket in (a["buy"], a["confirm"], a["wrong"]) for r in bucket])
    unknown_words = sorted({e.get("w") for e, r in all_results if r == "UNKNOWN_WORD"})

    return {
        "buy_met": buy_met, "lit": lit, "wrong_lit": wrong_lit, "chased": chased,
        "exit_warn": exit_warn, "exit_hit": exit_hit,
        "n_counting": len(counting), "n_lit": len(lit),
        "analyst_detail": analyst_detail,
        "no_shared_buy": no_shared_buy,
        "unknown_words": unknown_words,
        # Per-word (entry, TRUE/FALSE/NOT_YET/UNKNOWN_WORD) detail for the
        # SHARED buy/confirm block -- computed above to reach buy_met, but
        # previously discarded. The condition-state email (handoff §6)
        # needs the per-word verdict, not just the all-true aggregate, to
        # show which specific line is met/not-met/still-watching rather
        # than only the combined yes/no.
        "shared_buy_detail": shared_buy,
        "shared_confirm_detail": shared_confirm,
    }
