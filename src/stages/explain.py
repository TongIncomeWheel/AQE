"""Stage Weather in plain English — rule-based, no LLM, no pandas, no files.

Same shape as src/valen/explain.py and src/macro/crown/explain.py:
headline / because / so_what / watch_for / caveats. Pure function of the
finished artifact, so the page, the committee and the published file read
the same words.

`so_what` states what each stage has historically meant for a long book
(Weinstein's doctrine, quoted as doctrine). It never sizes, never names a
trade: AQE makes no decisions.
"""

from __future__ import annotations

from . import spec as S

_DOCTRINE = {
    1: ("Stage 1 is a waiting room: selling has dried up but buyers have not taken over. "
        "Doctrine: watch for breakouts from bases; new long exposure is early."),
    2: ("Stage 2 is the only stage in which the long-only playbook is designed to work. "
        "Doctrine: buy breakouts and pullbacks that hold the 30-week average."),
    3: ("Stage 3 is distribution: the advance has stalled and stronger hands are selling into strength. "
        "Doctrine: protect gains, tighten stops, stop adding."),
    4: ("Stage 4 is a decline: rallies fail under a falling average. "
        "Doctrine: no new longs; treat rallies as exits."),
}

_AGREE = {
    "CONFIRMS": "the single names agree with the index",
    "NARROWING": "fewer single names are advancing than four weeks ago, so the index is being carried by a narrower group",
    "IMPROVING_UNDERNEATH": "more single names are turning up than four weeks ago, ahead of the index",
    "UNTESTED": "the single-name breadth read is unavailable this run",
}


def _stage_word(s):
    return f"Stage {s} ({S.STAGE_NAME[s]})"


def _position(row: dict) -> str:
    """This week's facts, stated separately from the confirmed stage so the two
    can never be read as one claim (a confirmed Stage 2 can sit under its average
    for a week: that is the warning, not a contradiction)."""
    pct, slope = row.get("pct_from_ma30w"), row.get("ma30w_slope_pct_4w")
    if pct is None or slope is None:
        return ""
    side = "above" if pct >= 0 else "below"
    trend = "risen" if slope > 0 else "fallen"
    return (f"The last completed week closed {abs(pct)}% {side} the 30-week average "
            f"({row.get('ma30w')}), and that average has {trend} {abs(slope)}% over four weeks.")


def _pending(row: dict) -> str:
    st, c, f = row.get("stage"), row.get("candidate"), row.get("candidate_forming")
    bits = []
    if c is not None and c != st:
        bits.append(f"last week's close read {_stage_word(c)}, unconfirmed; one more completed "
                    f"week there confirms the change")
    if f is not None and f != c:
        bits.append(f"the week still forming reads {_stage_word(f)}")
    elif f is not None and f != st and c == st:
        bits.append(f"the week still forming reads {_stage_word(f)}; nothing confirms until it closes")
    return ("; ".join(bits) + ".") if bits else "no change pending."


def build(art: dict) -> dict:
    mr = art.get("market_read") or {}
    caveats = []
    if mr.get("status") != "OK":
        return {"headline": "Stage Weather unavailable: " + str(mr.get("reason") or "SPY could not be read"),
                "because": [], "so_what": None, "watch_for": [], "caveats": caveats,
                "as_of": art.get("as_of_session")}

    st = mr["stage"]
    headline = (f"The market is in {_stage_word(st)}: the {S.CYCLE_NAME[st].lower()} phase of the cycle, "
                f"{mr['weeks_in_stage']} weeks in.")
    if mr.get("change_in_progress"):
        headline += " A change of stage is in progress but not yet confirmed."

    because = []
    spy = (art.get("market") or {}).get("SPY") or {}
    because.append(f"Stage {st} means {S.STAGE_PLAIN[st]}. " + _position(spy))
    qqq = (art.get("market") or {}).get("QQQ") or {}
    if qqq.get("status") == "OK":
        same = "agrees" if qqq["stage"] == st else "disagrees"
        because.append(f"QQQ is in {_stage_word(qqq['stage'])}, which {same} with SPY.")
    b = art.get("breadth") or {}
    if b.get("status") == "OK":
        now, then = b["now"], b["four_weeks_ago"]
        because.append(
            f"Of {now['n']} single names on AQE's panel, {now['stage_2_pct']}% are in Stage 2 "
            f"(four weeks ago {then['stage_2_pct']}%) and {now['stage_4_pct']}% are in Stage 4 "
            f"(four weeks ago {then['stage_4_pct']}%): {_AGREE[mr['breadth_agreement']]}.")
    else:
        caveats.append("Single-name breadth unavailable: " + str(b.get("reason")))
    sg = art.get("sector_groups") or {}
    if any(sg.values()):
        parts = [f"{_stage_word(s)}: {', '.join(sg[f'stage_{s}'])}" for s in S.STAGES if sg.get(f"stage_{s}")]
        because.append("Sectors: " + "; ".join(parts) + ".")

    watch = []
    if mr.get("change_in_progress"):
        watch.append("SPY: " + _pending(spy))
    pct = spy.get("pct_from_ma30w") or 0
    if st == 2 and pct >= 0:
        watch.append(f"A weekly close below the 30-week average (about {spy.get('ma30w')}) is the first sign of a top.")
    elif st == 4 and pct < 0:
        watch.append(f"A weekly close back above the 30-week average (about {spy.get('ma30w')}) with the average flattening starts a base.")
    elif st in (1, 3):
        watch.append(f"Which way SPY leaves the range around {spy.get('ma30w')} decides the next stage.")
    for r in art.get("held_changes") or []:
        if r.get("transition"):
            watch.append(f"Held {r['ticker']}: moved from Stage {r['previous_stage']} to "
                         f"{_stage_word(r['stage'])} this week.")
        else:
            watch.append(f"Held {r['ticker']} ({_stage_word(r['stage'])}): " + _pending(r))

    if art.get("population_note"):
        caveats.append(art["population_note"])
    return {"headline": headline, "because": because, "so_what": _DOCTRINE[st],
            "watch_for": watch, "caveats": caveats, "as_of": art.get("as_of_session")}
