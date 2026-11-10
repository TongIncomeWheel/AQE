"""Stage at TICKER level, plus the two canon tests the committee's voices attach
to it, and the canon's market-top count.

  stamp_rows()        every daily_list / held row gains flat columns
                      (stage, stage_candidate, trend_template, stage2_confirmed …)
                      and one `stage_detail` block — the same classify() output
                      Stage Weather breadth counts, so row and breadth agree.
  trend_template()    Minervini C3, eight criteria, all-or-nothing. Reads the
                      row's OWN ma_50/150/200, entry, high/low_52w, rs_rank_pct,
                      so the checklist shows exactly the numbers the row shows.
                      Only the 200-day slope is computed here (the row has no
                      history).
  stage2_confirmed()  Minervini C2: Stage 2 AND ≥25% off the 52-week low.
  distribution_days() O'Neil C2 on SPY/QQQ: down closes on rising volume, last
                      25 sessions, ≥4 = the canon's top signal.

Readings only. A missing input is NA with the reason — never a silent FAIL,
never a PASS by omission.
"""

from __future__ import annotations

import math

import pandas as pd

from . import spec as S

PASS, FAIL, NA = "PASS", "FAIL", "NA"


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _cmp(ok: bool | None):
    return NA if ok is None else (PASS if ok else FAIL)


def ma200_slope(daily: pd.DataFrame, tickers) -> dict:
    """{ticker: {"ma200": x, "ma200_month_ago": y}} from the daily panel."""
    out = {}
    lb = S.IMPL_TT_MA200_RISING_SESSIONS
    sub = daily[daily["ticker"].isin(set(tickers))]
    for tk, g in sub.groupby("ticker"):
        c = g.sort_values("date")["close"].astype(float)
        if len(c) < 200 + lb:
            continue
        ma = c.rolling(200).mean()
        out[tk] = {"ma200": _num(ma.iat[-1]), "ma200_month_ago": _num(ma.iat[-1 - lb])}
    return out


def trend_template(row: dict, slope: dict | None) -> dict:
    p, m50, m150, m200 = (_num(row.get(k)) for k in ("entry", "ma_50", "ma_150", "ma_200"))
    hi, lo, rs = _num(row.get("high_52w")), _num(row.get("low_52w")), _num(row.get("rs_rank_pct"))
    # criterion 3 compares the panel's 200-day average with ITSELF a month ago (one source, both ends)
    m200_now, m200_ago = _num((slope or {}).get("ma200")), _num((slope or {}).get("ma200_month_ago"))

    def both(a, b, c):
        return None if None in (a, b, c) else (a > b and a > c)

    checks = [
        (1, "price above the 150-day and 200-day averages", both(p, m150, m200)),
        (2, "150-day average above the 200-day average", None if None in (m150, m200) else m150 > m200),
        (3, "200-day average rising for at least one month",
         None if None in (m200_now, m200_ago) else m200_now > m200_ago),
        (4, "50-day average above the 150-day and 200-day averages", both(m50, m150, m200)),
        (5, "price above the 50-day average", None if None in (p, m50) else p > m50),
        (6, f"price at least {S.CANON_TT_ABOVE_LOW_PCT:.0f}% above the 52-week low",
         None if None in (p, lo) or lo <= 0 else p >= lo * (1 + S.CANON_TT_ABOVE_LOW_PCT / 100)),
        (7, f"price within {S.CANON_TT_WITHIN_HIGH_PCT:.0f}% of the 52-week high",
         None if None in (p, hi) or hi <= 0 else p >= hi * (1 - S.CANON_TT_WITHIN_HIGH_PCT / 100)),
        (8, f"relative strength rank at least {S.CANON_TT_RS_MIN:.0f}",
         None if rs is None else rs >= S.CANON_TT_RS_MIN),
    ]
    res = [{"n": n, "rule": rule, "result": _cmp(ok)} for n, rule, ok in checks]
    met = sum(1 for r in res if r["result"] == PASS)
    if any(r["result"] == FAIL for r in res):
        verdict = FAIL                      # all-or-nothing: one fail is a fail
    elif any(r["result"] == NA for r in res):
        verdict = NA                        # can't confirm: never a pass by omission
    else:
        verdict = PASS
    return {"result": verdict, "met": met, "of": 8, "checks": res,
            "missing": [r["n"] for r in res if r["result"] == NA],
            "rs_basis": S.TT_RS_BASIS, "source": "Minervini C3 (aegis/canon/minervini)"}


def stage2_confirmed(stage: int | None, row: dict) -> dict:
    p, lo = _num(row.get("entry")), _num(row.get("low_52w"))
    rally = None if None in (p, lo) or lo <= 0 else round((p / lo - 1) * 100, 1)
    if stage is None or rally is None:
        val = None
    else:
        val = stage == 2 and rally >= S.CANON_STAGE2_MIN_RALLY_OFF_LOW_PCT
    return {"value": val, "rally_off_52w_low_pct": rally,
            "min_pct": S.CANON_STAGE2_MIN_RALLY_OFF_LOW_PCT, "source": "Minervini C2 (aegis/canon/minervini)"}


def distribution_days(daily_one: pd.DataFrame) -> dict:
    """O'Neil C2 for one index: down closes on volume heavier than the prior
    session, inside the last CANON_DD_WINDOW_SESSIONS sessions."""
    if daily_one is None or daily_one.empty or "volume" not in daily_one:
        return {"status": NA, "reason": "no daily bars with volume"}
    g = daily_one.sort_values("date")
    c, v = g["close"].astype(float), g["volume"].astype(float)
    dd = (c < c.shift(1)) & (v > v.shift(1))
    w = S.CANON_DD_WINDOW_SESSIONS
    if len(g) < w + 1:
        return {"status": NA, "reason": f"{len(g)} sessions < {w + 1} needed"}
    win = dd.tail(w)
    dates = [pd.Timestamp(d).date().isoformat() for d in g["date"].tail(w)[win.values]]
    n = int(win.sum())
    return {"status": "OK", "count": n, "window_sessions": w, "canon_threshold": S.CANON_DD_COUNT,
            "at_or_above_threshold": n >= S.CANON_DD_COUNT, "dates": dates,
            "note": "any down close on heavier volume counts (the canon sets no minimum decline); stall days are "
                    "not counted (the canon gives no number for 'negligible progress')",
            "source": "O'Neil C2 (aegis/canon/oneil)"}


_DETAIL_KEYS = ("stage", "stage_name", "cycle_name", "since", "weeks_in_stage", "previous_stage",
                "transition", "confirmed_this_week", "seeded", "candidate", "candidate_forming",
                "as_of_week", "ma30w", "ma30w_slope_pct_4w", "pct_from_ma30w", "range_pos_52w",
                "rs_mansfield", "rs_rising", "updown_volume_ratio", "status", "reason")


def stamp_rows(rows: list[dict], reads: dict[str, dict], slopes: dict, sector_stage: dict,
               market_stage: int | None) -> dict:
    """Stamp flat columns + `stage_detail` on every row. `reads` = classify()
    output by ticker. Returns counts for the status block."""
    n_ok = n_na = 0
    for r in rows:
        tk = r.get("ticker")
        rd = reads.get(tk) or {"status": NA, "reason": "not on the weekly panel"}
        ok = rd.get("status") == "OK"
        st = rd.get("stage") if ok else None
        tt = trend_template(r, slopes.get(tk))
        s2 = stage2_confirmed(st, r)
        sec = r.get("gics_sector")
        r["stage"] = st
        r["stage_name"] = rd.get("stage_name") if ok else None
        # the latest read: the forming week if there is one, else the last completed week
        r["stage_candidate"] = ((rd.get("candidate_forming") or rd.get("candidate")) if ok else None)
        r["stage_weeks"] = rd.get("weeks_in_stage") if ok else None
        r["stage_transition"] = rd.get("transition") if ok and rd.get("confirmed_this_week") else None
        r["trend_template"] = tt["result"]
        r["trend_template_met"] = tt["met"]
        r["stage2_confirmed"] = s2["value"]
        r["stage_detail"] = {
            **{k: rd.get(k) for k in _DETAIL_KEYS if k in rd},
            "sector_etf": sec, "sector_stage": sector_stage.get(sec),
            "market_stage": market_stage,
            "trend_template": tt, "stage2_confirmed": s2,
        }
        n_ok += ok
        n_na += not ok
    return {"stamped": len(rows), "read": n_ok, "na": n_na}
