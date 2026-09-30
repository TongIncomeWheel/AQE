"""VALEN Selection — the VIV handbook's Part 2, "Neighbourhood · selection"
(pieces 04, 05, 07). Piece 06 ("the earnings staircase" — fundamentals
growth) is explicitly NOT built here: AQE has never pulled income-statement
or estimates data from FMP, and inventing that engine mid-flight on this
change was judged riskier than shipping the three pieces that already have
real data behind them. See docs/AQE_VALEN_DASHBOARD_PROPOSAL.md follow-ups.

Every function below reads fields AQE's own engines already stamp onto
`daily_list`/`held_positions` in the finished daily export — no new
scoring, no new FMP calls. Pure functions of already-loaded lists (plain
dicts, the same shape `daily_list` rows already have), so this stays
independently unit-testable without pandas or file access — same
discipline as groups.py's compute layer.

Piece 04 (relative strength): `rs_rank_pct` is already a cross-sectional
percentile rank of 6-month return across that day's whole scored universe
— literally an RS-rank in the O'Neil/Minervini sense. `rs_leadership`
(LEADER/IN-LINE/LAGGARD) is measured only on SPY's DOWN days — "is this
stock still working when it's hard to."

Piece 05 (the funnel): AQE's own charter is "ONE list, membership as
columns" — the funnel is already implicit in `on_longlist`/`on_elder`/
`on_qs`/`held`, this just counts survivors at each stage in the
handbook's own narrowing order.

Piece 07 (the no-buy list): a per-candidate red-flag checklist over
fields that already exist — never a new veto engine, and never anything
that blocks a name from AQE's own longlist/Elder/QS lenses (those keep
their own independent thresholds); this is a separate, additive read.
"""

from __future__ import annotations

from . import spec as S


def relative_strength_leaders(daily_list: list[dict], top_n: int = 15) -> list[dict]:
    """Piece 04 — ranked by `rs_rank_pct` (the RS-rank), richest signal first."""
    ranked = sorted(
        (r for r in daily_list if r.get("rs_rank_pct") is not None),
        key=lambda r: r["rs_rank_pct"], reverse=True,
    )[:top_n]
    return [
        {
            "ticker": r.get("ticker"),
            "rs_rank_pct": r.get("rs_rank_pct"),
            "rs_leadership": r.get("rs_leadership"),
            "pipe_rank": r.get("pipe_rank"),
            "in_theme": bool(r.get("thematic_grade") in ("DEPLOY", "HOLD", "TURNING")),
        }
        for r in ranked
    ]


def funnel_counts(daily_list: list[dict], edge_tickers: set[str] | None = None) -> list[dict]:
    """Piece 05 — survivors at each of the handbook's narrowing stages, in
    the fixed order the handbook itself uses. `edge_tickers` (Precision
    Edge's own ticker set) is optional since that flag isn't currently
    merged onto daily_list rows the way on_longlist/on_elder/on_qs are —
    an absent value reads honestly as "not tracked this run," never zero.
    """
    n = len(daily_list)
    longlist = [r for r in daily_list if r.get("on_longlist")]
    both = [r for r in longlist if r.get("on_elder")]
    qs = [r for r in daily_list if r.get("on_qs")]
    held = [r for r in daily_list if r.get("held")]

    stages = [
        {"stage": "Scored universe", "count": n},
        {"stage": "On longlist", "count": len(longlist)},
        {"stage": "On longlist AND Elder", "count": len(both)},
        {"stage": "QS-scored (third lens)", "count": len(qs)},
    ]
    if edge_tickers is not None:
        edge_n = sum(1 for r in daily_list if r.get("ticker") in edge_tickers)
        stages.append({"stage": "Precision Edge", "count": edge_n})
    else:
        stages.append({"stage": "Precision Edge", "count": None,
                       "reason": "not tracked this run"})
    stages.append({"stage": "Held", "count": len(held)})
    return stages


def no_buy_flags(row: dict, market_stance_word: str | None = None) -> list[dict]:
    """Piece 07's per-candidate checklist. Every flag reads an existing
    field; nothing here is computed fresh. Returns the flags that TRIPPED
    only — an empty list means a clean read, not "not evaluated."""
    flags = []

    price = (row.get("bracket") or {}).get("price")
    ma200 = row.get("ma_200")
    if price is not None and ma200 is not None and price < ma200:
        flags.append({"flag": "below_200d", "label": "Below the 200-day line"})

    ext20 = row.get("extension_atr_20")
    if ext20 is not None and ext20 >= S.PER_STOCK_ATR_MULT_LAUNCHPAD_BELOW:
        flags.append({
            "flag": "stretched",
            "label": f"{ext20:.1f} ATR extended (20-day basis)",
        })

    dte = row.get("days_to_earnings")
    if dte is not None and dte <= S.NO_BUY_EARNINGS_WITHIN_SESSIONS:
        flags.append({"flag": "earnings_soon",
                      "label": f"Earnings in {dte} session(s)"})

    if row.get("sector_trend_state") == "Declining — Avoid":
        flags.append({"flag": "sector_weak", "label": "Sector: Declining — Avoid"})

    if row.get("thematic_grade") == "AVOID":
        flags.append({"flag": "theme_weak", "label": "Theme graded AVOID"})

    if market_stance_word == "RISK_OFF":
        flags.append({"flag": "market_red", "label": "Market check is RISK OFF"})

    return flags


def no_buy_list(daily_list: list[dict], market_stance_word: str | None = None,
                only_candidates: bool = True) -> list[dict]:
    """Every scored candidate (or the whole universe if `only_candidates` is
    False) carrying 1+ no-buy flags, worst first."""
    rows = daily_list
    if only_candidates:
        rows = [r for r in daily_list
               if r.get("on_longlist") or r.get("on_elder") or r.get("on_qs")]
    out = []
    for r in rows:
        flags = no_buy_flags(r, market_stance_word)
        if flags:
            out.append({"ticker": r.get("ticker"), "flags": flags})
    return sorted(out, key=lambda x: -len(x["flags"]))
