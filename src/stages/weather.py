"""Stage Weather — the four-stage cycle read for the market, the 11 GICS
sectors, and every single name on the panel (as breadth).

Three questions, in the order a PM asks them:
  1. MARKET   — which stage are SPY and QQQ in? (the weather)
  2. SECTORS  — which of the 11 GICS sectors are in Stage 2 and gaining on
                SPY, which are topping or declining? (where the wind blows)
  3. BREADTH  — what share of single names is in each stage, and is the
                Stage 2 share growing or shrinking vs 4 weeks ago? (is the
                index call broad or carried by a few)

Reads the SAME panel_weekly.parquet every other engine reads, so a close
here can never disagree with the export. No new data pull, no FMP call.

Standalone by design (same rule as Crown, 2026-08-09): reads nothing from
VALEN / Crown / SRM and feeds nothing to them, so overlap with those layers
stays measurable. AQE makes no decisions: a stage is a READING, never a gate,
never a size.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from . import spec as S
from . import ticker as T
from .classify import classify


def _load(panel_weekly_path) -> pd.DataFrame:
    cols = ["date", "ticker", "high", "low", "close", "volume"]
    df = pd.read_parquet(panel_weekly_path)
    df = df[[c for c in cols if c in df.columns]]
    return df.assign(date=pd.to_datetime(df["date"]))


def _load_daily(panel_daily_path) -> pd.DataFrame | None:
    try:
        df = pd.read_parquet(panel_daily_path)
        df = df[[c for c in ("date", "ticker", "close", "volume") if c in df.columns]]
        return df.assign(date=pd.to_datetime(df["date"]))
    except Exception:  # noqa: BLE001
        return None


def last_completed_session(panel_daily_path) -> pd.Timestamp | None:
    """Latest daily close on the panel — any weekly bar dated after it is the
    still-forming week."""
    d = _load_daily(panel_daily_path)
    return None if d is None or d.empty else pd.Timestamp(d["date"].max())


def _public(row: dict) -> dict:
    return {k: v for k, v in row.items() if not k.startswith("_")}


def _shares(stages: list[int]) -> dict:
    n = len(stages)
    c = Counter(stages)
    return {"n": n, **{f"stage_{s}": c.get(s, 0) for s in S.STAGES},
            **{f"stage_{s}_pct": round(100.0 * c.get(s, 0) / n, 1) if n else None for s in S.STAGES}}


def _direction(now, then) -> str | None:
    if now is None or then is None:
        return None
    d = now - then
    if d > S.IMPL_BREADTH_STEADY_PTS:
        return "RISING"
    if d < -S.IMPL_BREADTH_STEADY_PTS:
        return "FALLING"
    return "STEADY"


def _breadth(rows: dict[str, dict]) -> dict:
    """Stage shares now, 1 week and 4 weeks ago, all from the same stage series."""
    ok = {t: r for t, r in rows.items() if r.get("status") == "OK"}
    na = sorted(t for t, r in rows.items() if r.get("status") != "OK")
    if not ok:
        return {"status": "UNAVAILABLE", "reason": "no single name had enough weekly history",
                "population": S.POPULATION_PANEL, "n_na": len(na)}

    def at(k):
        out = []
        for r in ok.values():
            ser = r["_series"].dropna()
            if len(ser) > k:
                out.append(int(ser.iat[-1 - k]))
        return out

    now, wk1, wk4 = _shares(at(0)), _shares(at(1)), _shares(at(S.IMPL_BREADTH_LOOKBACK_WEEKS))
    return {
        "status": "OK",
        "population": S.POPULATION_PANEL,   # never "the whole market": AQE's curated panel only
        "now": now, "one_week_ago": wk1, "four_weeks_ago": wk4,
        "stage_2_direction": _direction(now["stage_2_pct"], wk4["stage_2_pct"]),
        "stage_4_direction": _direction(now["stage_4_pct"], wk4["stage_4_pct"]),
        "n_na": len(na),
    }


def _market_read(market: dict, breadth: dict) -> dict:
    """Categorical, never a score: the index stage, and whether breadth agrees."""
    spy = market.get(S.BENCHMARK) or {}
    if spy.get("status") != "OK":
        return {"status": "UNAVAILABLE", "reason": spy.get("reason", "SPY not on the weekly panel")}
    st = spy["stage"]
    s2 = breadth.get("stage_2_direction")
    s4 = breadth.get("stage_4_direction")
    if breadth.get("status") != "OK":
        agree = "UNTESTED"
    elif st == 2 and (s2 == "FALLING" or s4 == "RISING"):
        agree = "NARROWING"        # index advancing on fewer names
    elif st == 2:
        agree = "CONFIRMS"
    elif st in (3, 4) and (s2 == "RISING" or s4 == "FALLING"):
        agree = "IMPROVING_UNDERNEATH"
    elif st in (3, 4):
        agree = "CONFIRMS"
    elif st == 1 and s2 == "RISING":
        agree = "IMPROVING_UNDERNEATH"
    else:
        agree = "CONFIRMS"
    warning = spy.get("candidate") != st or (spy.get("candidate_forming") not in (None, st))
    return {"status": "OK", "stage": st, "stage_name": spy["stage_name"],
            "cycle_name": spy["cycle_name"], "since": spy["since"],
            "weeks_in_stage": spy["weeks_in_stage"], "breadth_agreement": agree,
            "change_in_progress": bool(warning)}


def compute(panel_weekly_path, panel_daily_path, sector_etfs, held: list[str] | None = None,
            daily_list: list[str] | None = None, extra: list[str] | None = None) -> dict:
    """Full Stage Weather read. Never raises on a missing ticker; a name that
    can't be read is NA with its reason, never dropped silently."""
    df = _load(panel_weekly_path)
    daily = _load_daily(panel_daily_path)
    cutoff = None if daily is None or daily.empty else pd.Timestamp(daily["date"].max())
    by = {t: g for t, g in df.groupby("ticker")}
    bench = by.get(S.BENCHMARK)
    bench_c = None
    if bench is not None:
        b = bench.sort_values("date")
        if cutoff is not None:
            b = b[b["date"] <= cutoff]
        bench_c = b.set_index("date")["close"].astype(float)

    def read(t):
        g = by.get(t)
        if g is None:
            return {"status": "NA", "reason": "not on the weekly panel"}
        return classify(g, bench_c, cutoff)

    market = {t: read(t) for t in S.MARKET_SYMBOLS}
    for t in S.DD_INDEXES:     # O'Neil C2: the canon's market-top count, beside the stage
        if t in market:
            one = None if daily is None else daily[daily["ticker"] == t]
            market[t]["distribution_days"] = T.distribution_days(one)
    sectors = {t: read(t) for t in sector_etfs}
    non_single = set(S.MARKET_SYMBOLS) | set(sector_etfs)
    singles = {t: read(t) for t in by if t not in non_single}
    breadth = _breadth(singles)
    extra_reads: dict = {}

    def transitions(names):
        out = []
        for t in sorted(names):
            r = singles.get(t) or {}
            if r.get("status") != "OK":
                continue
            changing = r["candidate"] != r["stage"] or r.get("candidate_forming") not in (None, r["stage"])
            if r["confirmed_this_week"] or changing:
                out.append({"ticker": t, "stage": r["stage"], "previous_stage": r["previous_stage"],
                            "transition": r["transition"] if r["confirmed_this_week"] else None,
                            "candidate": r["candidate"], "candidate_forming": r.get("candidate_forming"),
                            "weeks_in_stage": r["weeks_in_stage"]})
        return out

    for t in extra or []:      # names asked for by the export that aren't single names on the panel
        if t not in singles and t not in sectors and t not in market:
            singles_extra = read(t)
            singles_extra.pop("_series", None)
            extra_reads.setdefault(t, singles_extra)
    held = sorted(set(held or []))
    dl = sorted(set(daily_list or []))
    held_rows = {t: _public(singles.get(t) or read(t)) for t in held}
    sector_rows = {t: _public(r) for t, r in sectors.items()}

    return {
        "as_of_session": cutoff.date().isoformat() if cutoff is not None else None,
        "market": {t: _public(r) for t, r in market.items()},
        "market_read": _market_read(market, breadth),
        "sectors": sector_rows,
        "sector_groups": {
            f"stage_{s}": sorted(t for t, r in sector_rows.items() if r.get("stage") == s)
            for s in S.STAGES},
        "breadth": breadth,
        "held": held_rows,
        "daily_list_changes": transitions(dl),
        "held_changes": transitions(held),
        "all_confirmed_this_week": [
            {"ticker": t, "transition": r["transition"], "stage": r["stage"]}
            for t, r in sorted(singles.items())
            if r.get("status") == "OK" and r["confirmed_this_week"]],
        # private: full reads + daily panel for the export's row stamp (stripped before any write)
        "_reads": {**extra_reads, **singles, **sectors, **market},
        "_daily": daily,
        "by_ticker": {t: {k: r.get(k) for k in ("status", "stage", "candidate", "candidate_forming",
                                                "weeks_in_stage", "transition", "rs_mansfield", "reason")}
                      for t, r in sorted(singles.items())},
    }
