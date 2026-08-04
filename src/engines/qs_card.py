"""QS card renderer — rebuilds a committee card from the daily file ALONE.

This module is deliberately blind. It takes a `daily_list` row and the
`qs_market` block and returns text. It opens no parquet, calls no engine,
reads no config, and recomputes nothing. If a number appears on a card it
must therefore already be in the export.

That constraint is the point, not an implementation detail. The QS handover
§4.3 requires "every claim in prose must be reconstructible from the file (no
screen-only numbers)", and the reference implementation says the same:
"Everything downstream -- the AQE screen, the TradingView export, the journal
-- renders THIS file. Nothing recomputes." A renderer that cannot reach
outside its arguments makes that guarantee testable instead of aspirational:
`test_qs_card.py` asserts the module never imports pandas or touches disk.

Consumers: the Scanner UI's per-name expander, the committee memo, and any
on-demand "show me the card for X" request.

TWO LEVEL SETS, NEVER MERGED
---------------------------
`qs.objective` is the +/-2xATR14 yardstick the calibrated probability was
MEASURED against ("touch +2*ATR14 within 20 sessions"). `bracket` is AQE's
structural stop and target ladder — what you would actually trade. They are
different numbers answering different questions. The card prints them in
separate blocks with the probability bound explicitly to the objective, so
"71%" can never be read as the odds of reaching structural TP2.
"""

from __future__ import annotations

RULE = "-" * 78


def _stars(score: float | None) -> str:
    """Emphasis marker for a lens score. Display-only, derived from the score."""
    if score is None:
        return "   "
    if score >= 7.5:
        return "***"
    if score >= 6:
        return " **"
    if score >= 5:
        return "  *"
    return "   "


def _num(v, spec: str = ".2f", dash: str = "--") -> str:
    try:
        return format(float(v), spec)
    except (TypeError, ValueError):
        return dash


def render_market(market: dict) -> str:
    """The market header. It can cancel the day, so it is read first."""
    if not market:
        return "MARKET\n  (no regime block in this export)"
    out = ["MARKET", f"  {market.get('description', 'unclassified')}"]
    avg = market.get("avg_stock_hits_target")
    if avg is not None:
        out.append(f"  In this kind of market the average stock reaches its "
                   f"target {avg:.0%} of the time.")
    if market.get("action"):
        out.append(f"  {market['action']}")
    if market.get("regime_code"):
        out.append(f"  (regime code {market['regime_code']} — for the record)")
    if market.get("stance") == "STAND_DOWN":
        out.append("  STAND DOWN — no actionable list today by design.")
    return "\n".join(out)


def _render_lenses(qs: dict) -> list[str]:
    """Five lens rows, each with its score and the raw components behind it.

    The component values come from `qs.engine.components`, which the export
    carries precisely so this line can be drawn without a data lookup.
    """
    eng = qs.get("engine") or {}
    lens = eng.get("lens") or {}
    c = eng.get("components") or {}
    g = c.get
    rows = [
        ("STRUCTURE", lens.get("structure"),
         f"range pos {_num(g('en_pos50'), '.0f')}/100, "
         f"mkt-struct {_num(g('ms_pos_score'), '.0f')}, "
         f"structure {_num(g('structure_100'), '.0f')}"
         + (f", base {_num(g('base_days'), '.0f')}d"
            if g("base_days") is not None else "")),
        ("COIL", lens.get("coil"),
         f"range tight {_num(g('bq_range_tight'), '.0f')}/30, "
         f"MA conv {_num(g('bq_ema_conv'), '.0f')}/25, "
         f"squeeze {_num(g('squeeze_score'), '.1f')}/12.5"),
        ("MOMENTUM", lens.get("momentum"),
         f"roc-z {_num(g('roc_zscore'), '+.2f')}, "
         f"abs {_num(g('abs_mom_score'), '.0f')}/30, "
         f"rel {_num(g('rel_mom_score'), '.0f')}/25   "
         f"(HIGH = still QUIET = good)"),
        ("FLOW", lens.get("flow"),
         f"accum {_num(g('accum_score'), '.1f')}/7.5, "
         f"CMF {_num(g('cmf'), '+.2f')}, MFI {_num(g('mfi'), '.0f')}"),
        ("LEADERSHIP", lens.get("leadership"),
         f"beats mkt {_num((g('rs_consist') or 0) * 100, '.0f')}% of days, "
         f"vs SPY {_num(g('rs_vs_spy'), '+.1f')}, "
         f"elder {_num(g('elder_score'), '.0f')}/10"),
    ]
    return [f"       {name:<11}{_num(score, '.1f', '--'):>5}/10 {_stars(score)} | {detail}"
            for name, score, detail in rows]


def _render_bracket(row: dict) -> list[str]:
    """AQE's STRUCTURAL levels — what you'd actually trade.

    Kept visually distinct from the objective block above it. A bracket that
    is invalid says so: the reference position is that a name with no
    structural level has NO tradeable bracket, and inventing a mechanical
    fallback there would be worse than printing nothing.
    """
    br = row.get("bracket") or {}
    if not br:
        return []
    if not br.get("valid", True):
        return [f"  LEVELS      no valid structural bracket"
                f" ({br.get('invalid_reason') or 'no qualifying level'})"]
    out = []
    stop = br.get("stop")
    bits = [f"stop {_num(stop)}"]
    if br.get("stop_type"):
        bits.append(f"on {br['stop_type']}")
    if br.get("risk_pct") is not None:
        bits.append(f"risk {_num(br['risk_pct'], '.1f')}%")
    if br.get("stop_vol_validated"):
        bits.append("vol-confirmed")
    out.append(f"  LEVELS      {', '.join(bits)}   (structural — the tradeable set)")
    for t in (br.get("targets") or [])[:3]:
        rr = f"{_num(t.get('r'), '.1f')}R" if t.get("r") is not None else "--"
        out.append(f"              {t.get('tp', '--'):<4} {_num(t.get('price')):>9}"
                   f"  {rr:>6}  {t.get('type', '')}")
    return out


def render_card(row: dict, market: dict | None = None) -> str:
    """Rebuild one committee card from a daily_list row. Reads nothing else."""
    qs = row.get("qs") or {}
    if not qs:
        return f"{row.get('ticker', '?')} — not scored by QS in this export."

    tk = row.get("ticker", "?")
    vetoes = qs.get("vetoes") or []
    out = [RULE, f"{tk:<6} {qs.get('signal', '')}"
                 + ("   !! VETOED" if vetoes else "")]

    odds = qs.get("odds") or {}
    p, avg = odds.get("p"), odds.get("market_avg")
    tail = (f"        {p:.0%} vs {avg:.0%} for the average stock today"
            if p is not None and avg is not None else "")
    out.append(f"  CONVICTION  {qs.get('conviction', '?')}/5 "
               f"{qs.get('conviction_word', '')}{tail}")

    st = qs.get("state") or {}
    if st.get("code"):
        rate = (f"   [{st['test_hit_rate']:.1%} historically]"
                if st.get("test_hit_rate") else "")
        out.append(f"  STATE       {st['code']} — {st.get('plain', '')}{rate}")

    if qs.get("awareness_notes"):
        out.append(f"  NOTE        {qs['awareness_notes']}")
    if vetoes:
        out.append(f"  VETO        {', '.join(vetoes)}"
                   f"   (struck — shown so the strike is visible)")
    if qs.get("unevaluable_vetoes"):
        out.append(f"  !! DATA GAP  veto(s) could not be evaluated: "
                   f"{', '.join(qs['unevaluable_vetoes'])} — missing input, "
                   f"NOT a pass")

    obj = qs.get("objective") or {}
    if obj:
        out.append(f"  OBJECTIVE   now {_num(obj.get('now'))}  ->  "
                   f"+2ATR {_num(obj.get('target_2atr'))} "
                   f"(+{_num(obj.get('target_pct'), '.1f')}%)"
                   f"   <- what the {('%.0f%%' % (p * 100)) if p is not None else 'odds'} refers to")
        path = qs.get("path") or {}
        if path.get("usual_days") is not None:
            out.append(f"              usually takes about "
                       f"{_num(path['usual_days'], '.0f')} trading days")
        if path.get("typical_dip_pct") is not None:
            out.append(f"              typically dips up to "
                       f"{_num(path['typical_dip_pct'], '.1f')}% along the way; "
                       f"give up below {_num(obj.get('give_up_2atr'))}")
        else:
            out.append(f"              give up below {_num(obj.get('give_up_2atr'))}")
            if odds.get("bucket_kind") and odds["bucket_kind"] != "3-D":
                out.append(f"              (no path stats — {odds['bucket_kind']} "
                           f"cell '{odds.get('bucket')}' carries none)")

    out += _render_bracket(row)

    if qs.get("why"):
        out.append(f"  WHY         {qs['why']}")
    out += _render_lenses(qs)

    eng = qs.get("engine") or {}
    out.append(f"       audit: {eng.get('recipe_hits', '?')} recipe hits · "
               f"persist {eng.get('qs_persist', '?')}/5 · "
               f"lens_total {eng.get('lens_total', '?')} · "
               f"{odds.get('n_analogues', '?')} analogues · "
               f"cell {odds.get('bucket', '?')}")
    return "\n".join(out)


def render_sheet(rows: list[dict], market: dict | None = None,
                 limit: int | None = None) -> str:
    """Market header + every QS-flagged row as a card, in export order."""
    qs_rows = [r for r in rows if r.get("on_qs") and r.get("qs")]
    qs_rows.sort(key=lambda r: (r.get("qs") or {}).get("rank") or 10**6)
    if limit:
        qs_rows = qs_rows[:limit]
    parts = [render_market(market or {}), ""]
    parts += [render_card(r, market) for r in qs_rows]
    parts.append(RULE)
    if not qs_rows:
        parts.append("No QS names cleared the noise rule today.")
    return "\n".join(parts)
