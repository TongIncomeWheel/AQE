"""One table of every macro leg: as_of vs expected, with a REASON CODE (conductor + PM 2026-11-04).

The PM must be able to tell 'stale because we are slow' from 'stale because the publisher is':
  CURRENT            the leg carries the expected session
  PUBLISHER_CADENCE  the publisher releases on a fixed cadence and this IS its latest release (CFTC COT: weekly, Friday)
  PUBLISHER_LAG      the publisher has not posted the expected session yet (Cboe posts VIX/VIXEQ ~21:11 ET, DSPX ~21:41 ET)
  OUR_BUDGET         we could have had it and did not (the whole-market panel refresh ran out of time / budget)
  SOURCE_DOWN        the source could not be reached or returned nothing
Nothing here changes a reading; it only says why a date is what it is.
"""
from __future__ import annotations

from datetime import date, timedelta

CURRENT, CADENCE, LAG, BUDGET, DOWN = "CURRENT", "PUBLISHER_CADENCE", "PUBLISHER_LAG", "OUR_BUDGET", "SOURCE_DOWN"
BLOCKING = {BUDGET, DOWN}          # reasons the committee gate FAILs on; LAG and CADENCE are a labelled WARN at most


def next_cot_release(today: date) -> str:
    """CFTC publishes the Tuesday report on Friday afternoon ET: the next Friday strictly after `today`'s last release."""
    d = today + timedelta(days=1)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d.isoformat()


def _row(leg, as_of, expected, reason, detail=""):
    return {"leg": leg, "as_of": as_of, "expected": expected, "reason": reason, "detail": detail}


def build_legs(expected: str, today: date, *, breadth: dict | None = None, vol_series: dict | None = None,
               cot_as_of: str | None = None, heartbeat_asof: str | None = None, cboe_ok: bool = True) -> list[dict]:
    rows = []
    fr = (breadth or {}).get("freshness") or {}
    if not fr:
        rows.append(_row("breadth_whole_market", None, expected, DOWN, "no whole-market panel by any path"))
    elif not fr.get("stale"):
        rows.append(_row("breadth_whole_market", fr.get("as_of"), expected, CURRENT, f"{fr.get('current')}/{fr.get('total')} tickers current"))
    else:
        rows.append(_row("breadth_whole_market", fr.get("as_of"), expected, BUDGET, fr.get("reason") or ""))
    rows.append(_row("heartbeat_rsp_spy", heartbeat_asof, expected, CURRENT if (heartbeat_asof or "") >= expected else DOWN,
                     "FMP daily bars"))
    names = {"vix": ("vix_level", "FMP ^VIX fills the level when Cboe is behind"),
             "vixeq": ("dispersion_vixeq", "Cboe posts ~21:11 ET (10:11 SGT)"),
             "dspx": ("dspx", "Cboe posts ~21:41 ET (10:41 SGT)"),
             "vix3m": ("vix3m", "Cboe posts ~17:31 ET (06:31 SGT)"),
             "vix9d": ("vix9d", "Cboe posts ~17:31 ET (06:31 SGT)"),
             "cor1m": ("implied_correlation_cor1m", "Cboe posts ~17:31 ET (06:31 SGT)")}
    for k, (leg, note) in names.items():
        a = (vol_series or {}).get(k)
        if a and a >= expected:
            rows.append(_row(leg, a, expected, CURRENT, ""))
        elif k == "vix" and not a:
            rows.append(_row(leg, a, expected, DOWN, "no VIX series from Cboe or FMP"))
        else:
            rows.append(_row(leg, a, expected, LAG if cboe_ok and a else DOWN, note if cboe_ok and a else "Cboe unreachable or empty"))
    if cot_as_of:
        age = (today - date.fromisoformat(cot_as_of)).days
        rows.append(_row("positioning_cot", cot_as_of, expected, CADENCE if age <= 13 else DOWN,
                         f"latest published weekly CFTC release; next release {next_cot_release(today)}" if age <= 13
                         else f"{age} days old: the weekly release is missing"))
    else:
        rows.append(_row("positioning_cot", None, expected, DOWN, "no COT history"))
    return rows


def blocking(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["reason"] in BLOCKING]


def one_line(rows: list[dict]) -> str:
    return " | ".join(f"{r['leg']} {r['as_of']} {r['reason']}" for r in rows)


def freshness_line(expected: str, rows: list[dict]) -> str:
    """The one-line FRESHNESS header the desk proposed (PM 2026-11-04): printed on every card page and summary."""
    short = {"breadth_whole_market": "breadth", "vix_level": "VIX", "dispersion_vixeq": "dispersion", "dspx": "DSPX",
             "vix3m": "VIX3M", "vix9d": "VIX9D", "implied_correlation_cor1m": "COR1M", "positioning_cot": "COT",
             "heartbeat_rsp_spy": "heartbeat"}
    parts = []
    for r in rows:
        label = short.get(r["leg"], r["leg"])
        tag = "" if r["reason"] == CURRENT else f" [{r['reason']}]"
        extra = " (latest published; next release " + r["detail"].split("next release ")[-1] + ")" if r["leg"] == "positioning_cot" and "next release" in (r.get("detail") or "") else ""
        parts.append(f"{label} {r['as_of']}{tag}{extra}")
    return f"FRESHNESS | expected {expected} | " + " | ".join(parts)
