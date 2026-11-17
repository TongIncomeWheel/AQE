"""VALEN theme layer (PM 2026-11-17, Valen DAY-2..5): which baskets are bullish, since when, where the money is moving, and which names sit inside them.

Pure over the daily panel (date, ticker, open, high, low, close, volume); AQE's own 35 thematic baskets (src.engines.srm.THEMATIC_BASKETS), never Valen's 96.
Every formula below is MINE, disclosed in `definitions` inside the block, because Valen's own are unpublished. Readings only: nothing here gates, ranks a trade or sizes.

  basket index   equal-weight, each name rebased to its first value in the window, mean across names (the same construction srm.py and groups.py use).
  bullish        the basket index closes above its EMA9, EMA21 and SMA50 (the three averages Valen's chart trades off; the 200 is context). Q5 default.
  sessions_on    consecutive sessions the flag has held (negative = sessions it has been off).
  share_above    share of the basket's names closing above their OWN 9/21/50/200 averages.
  up_share       share of the basket's names higher over 1 day / 1 week / 1 month / 3 months.
  rs_1m          0-100 percentile rank (steps of 5) of the basket's 21-session return vs the other baskets; thrust = the same on 5 sessions. Q4 default.
  days_rs_80     of the last 60 sessions, how many the basket's 21-session RS rank sat at 80 or above.
  reclaimed/lost the basket index crossed back above / fell under an average at today's close (EMA9, EMA21, SMA50, SMA200).
  leading        bullish AND rs_1m >= 80 (Valen's "80+" notion).
  atr_pct/atrx   mean absolute daily move of the index over 14 sessions as a % of price, and today's move in those units (index-level proxy; the basket has no real high/low).
  dryup          per name: of the last 10 sessions, how many traded 45% / 60% under the 50-day average volume (Valen's volume-suite marks).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines.srm import THEMATIC_BASKETS

BULLISH_AVERAGES = ("ema9", "ema21", "sma50")
LEADING_RS_MIN = 80
RS_WINDOW, THRUST_WINDOW, RS_HISTORY = 21, 5, 60
DRYUP_WINDOW, DRYUP_45, DRYUP_60 = 10, 0.45, 0.60
MIN_NAMES = 3
HORIZONS = (("1d", 1), ("1w", 5), ("1m", 21), ("3m", 63))

DEFINITIONS = {
    "basket": "AQE's own thematic baskets, equal-weight index (each name rebased to its first value, mean across names)",
    "bullish": "index closes above its EMA9, EMA21 and SMA50 (the 200-day is context only); AQE's own rule, Valen's is unpublished",
    "sessions_on": "consecutive sessions the bullish flag has held; negative = sessions it has been off",
    "rs_1m": "percentile rank 0-100 (steps of 5) of the 21-session return across the baskets; thrust = the same on 5 sessions; AQE's own formula, Valen's is unpublished",
    "days_rs_80": "of the last 60 sessions, sessions with rs_1m at 80 or above",
    "leading": "bullish AND rs_1m >= 80",
    "atrx": "today's index move divided by its 14-session mean absolute daily move (index-level proxy, no true high/low)",
    "dryup": "of the last 10 sessions, how many traded 45% / 60% under the 50-day average volume",
}


def _step5(rank_pct: pd.Series) -> pd.Series:
    return (rank_pct * 100 / 5).round() * 5


def _index(piv: pd.DataFrame, names: list[str]) -> pd.Series:
    sub = piv[[t for t in names if t in piv.columns]].dropna(how="all")
    if sub.shape[1] < MIN_NAMES or len(sub) < 60:
        return pd.Series(dtype=float)
    base = sub.bfill().iloc[0]
    return sub.divide(base.where(base != 0)).mean(axis=1, skipna=True).dropna()


def _averages(s: pd.Series) -> dict:
    return {"ema9": s.ewm(span=9, adjust=False).mean(), "ema21": s.ewm(span=21, adjust=False).mean(),
            "sma50": s.rolling(50).mean(), "sma200": s.rolling(200).mean()}


def _runs(flag: pd.Series) -> int:
    """consecutive sessions the last value has held; negative when that value is False."""
    f = flag.dropna().astype(bool)
    if f.empty:
        return 0
    last, n = bool(f.iloc[-1]), 0
    for v in f.iloc[::-1]:
        if bool(v) != last:
            break
        n += 1
    return n if last else -n


def compute_theme_block(panel: pd.DataFrame) -> dict:
    """{status, as_of, summary, baskets: [...], reclaimed, lost, definitions}. Never raises: a failure is status UNAVAILABLE with the reason."""
    try:
        p = panel[["date", "ticker", "close"]].copy()
        p["date"] = pd.to_datetime(p["date"])
        piv = p.pivot_table(index="date", columns="ticker", values="close").sort_index()
        if piv.empty:
            return {"status": "UNAVAILABLE", "reason": "empty panel", "baskets": []}
        as_of = piv.index[-1]
        spy = piv["SPY"] if "SPY" in piv.columns else None
        idx = {}
        for name, info in THEMATIC_BASKETS.items():
            s = _index(piv, info.get("constituents") or [])
            if not s.empty:
                idx[name] = s
        if len(idx) < 3:
            return {"status": "UNAVAILABLE", "reason": f"only {len(idx)} baskets had usable data", "baskets": []}
        frame = pd.DataFrame(idx).sort_index()
        # rolling RS ranks across baskets, per session
        rs21 = _step5(frame.pct_change(RS_WINDOW).rank(axis=1, pct=True))
        rs5 = _step5(frame.pct_change(THRUST_WINDOW).rank(axis=1, pct=True))
        rows, reclaimed, lost = [], {k: [] for k in ("ema9", "ema21", "sma50", "sma200")}, {k: [] for k in ("ema9", "ema21", "sma50", "sma200")}
        for name, s in idx.items():
            av = _averages(s)
            above = {k: (s > v) for k, v in av.items()}
            bull = above["ema9"] & above["ema21"] & above["sma50"]
            bull = bull.where(av["sma50"].notna())
            last = lambda ser: ser.iloc[-1] if len(ser) else np.nan  # noqa: E731
            for k in av:
                if len(s) >= 2 and pd.notna(av[k].iloc[-2]) and pd.notna(av[k].iloc[-1]):
                    if bool(above[k].iloc[-1]) and not bool(above[k].iloc[-2]):
                        reclaimed[k].append(name)
                    elif not bool(above[k].iloc[-1]) and bool(above[k].iloc[-2]):
                        lost[k].append(name)
            names = [t for t in (THEMATIC_BASKETS[name].get("constituents") or []) if t in piv.columns]
            cl = piv[names].dropna(how="all")
            share_above = {}
            for k, fn in (("ema9", lambda x: x.ewm(span=9, adjust=False).mean()), ("ema21", lambda x: x.ewm(span=21, adjust=False).mean()),
                          ("sma50", lambda x: x.rolling(50).mean()), ("sma200", lambda x: x.rolling(200).mean())):
                ma = cl.apply(fn)
                ok = ma.iloc[-1].notna() & cl.iloc[-1].notna()
                share_above[k] = round(float((cl.iloc[-1][ok] > ma.iloc[-1][ok]).mean() * 100), 1) if ok.any() else None
            up_share, ret = {}, {}
            for lab, n in HORIZONS:
                if len(cl) > n:
                    chg = (cl.iloc[-1] / cl.iloc[-1 - n] - 1).dropna()
                    up_share[lab] = round(float((chg > 0).mean() * 100), 1) if len(chg) else None
                ret[lab] = round(float((s.iloc[-1] / s.iloc[-1 - n] - 1) * 100), 2) if len(s) > n else None
            d = s.pct_change().abs().tail(14).mean()
            move = (s.iloc[-1] / s.iloc[-2] - 1) if len(s) > 1 else np.nan
            rs_hist = rs21[name].tail(RS_HISTORY)
            rows.append({
                "name": name, "display_name": name.replace("_", " "), "parent_gics": THEMATIC_BASKETS[name].get("parent_gics_etf"),
                "n_names": len(names), "bullish": bool(bull.iloc[-1]) if pd.notna(bull.iloc[-1]) else None,
                "sessions_on": _runs(bull), "above": {k: bool(v.iloc[-1]) for k, v in above.items() if pd.notna(av[k].iloc[-1])},
                "share_above": share_above, "up_share": up_share, "ret_pct": ret,
                "atr_pct": round(float(d * 100), 2) if pd.notna(d) else None,
                "atrx": round(float(move / d), 2) if pd.notna(d) and d else None,
                "rs_1m": None if pd.isna(rs21[name].iloc[-1]) else int(rs21[name].iloc[-1]),
                "thrust": None if pd.isna(rs5[name].iloc[-1]) else int(rs5[name].iloc[-1]),
                "days_rs_80": int((rs_hist >= LEADING_RS_MIN).sum()),
            })
        for r in rows:
            r["leading"] = bool(r["bullish"] and (r["rs_1m"] or 0) >= LEADING_RS_MIN)
        rows.sort(key=lambda r: (not r["bullish"], -(r["rs_1m"] or 0), r["name"]))
        n = len(rows)
        pct = lambda f: round(100 * sum(1 for r in rows if f(r)) / n)  # noqa: E731
        summary = {
            "baskets": n, "bullish": sum(1 for r in rows if r["bullish"]), "bullish_pct": pct(lambda r: r["bullish"]),
            "leading": sum(1 for r in rows if r["leading"]),
            "above_pct": {k: pct(lambda r, k=k: r["above"].get(k)) for k in ("ema9", "ema21", "sma50", "sma200")},
            "up_today_pct": pct(lambda r: (r["ret_pct"].get("1d") or 0) > 0), "up_1w_pct": pct(lambda r: (r["ret_pct"].get("1w") or 0) > 0),
            "up_1m_pct": pct(lambda r: (r["ret_pct"].get("1m") or 0) > 0), "up_3m_pct": pct(lambda r: (r["ret_pct"].get("3m") or 0) > 0),
        }
        return {"status": "OK", "reason": None, "as_of": str(as_of.date()), "summary": summary, "baskets": rows,
                "reclaimed_today": reclaimed, "lost_today": lost, "definitions": DEFINITIONS}
    except Exception as exc:  # noqa: BLE001
        return {"status": "UNAVAILABLE", "reason": f"{type(exc).__name__}: {exc}", "baskets": []}


def membership(block: dict | None) -> dict[str, list[dict]]:
    """{ticker: [{name, bullish, sessions_on, rs_1m, leading}]} for every constituent of every basket in the block."""
    out: dict[str, list[dict]] = {}
    if not block or block.get("status") != "OK":
        return out
    for b in block["baskets"]:
        for t in THEMATIC_BASKETS[b["name"]].get("constituents") or []:
            out.setdefault(t, []).append({"name": b["name"], "bullish": b["bullish"], "sessions_on": b["sessions_on"],
                                          "rs_1m": b["rs_1m"], "leading": b["leading"]})
    return out


def theme_fields(ticker: str, member: dict[str, list[dict]], block_ok: bool) -> dict:
    """The row's theme columns. No block = both None (not read), never an empty list that reads like 'in no theme'."""
    if not block_ok:
        return {"themes": None, "in_leading_theme": None}
    ts = member.get(ticker, [])
    return {"themes": ts, "in_leading_theme": bool(any(t["leading"] for t in ts))}


def theme_line(row: dict) -> str | None:
    """One plain card line from the row's theme columns (ALT-5); None when the layer was not read."""
    ts = row.get("themes")
    if ts is None:
        return None
    if not ts:
        return "Theme: in none of AQE's themes"
    ts = sorted(ts, key=lambda t: (not t["leading"], not t["bullish"], -(t["rs_1m"] or 0)))
    bits = []
    for t in ts[:3]:
        nm = t["name"].replace("_", " ")
        state = f"bullish {t['sessions_on']} sessions" if t["bullish"] else (f"not bullish, off {abs(t['sessions_on'])} sessions" if t["bullish"] is not None else "not read")
        bits.append(f"{nm} ({state}, 1-month strength {t['rs_1m']})")
    lead = "a leading theme" if row.get("in_leading_theme") else "no leading theme"
    return f"Theme: {lead}: " + "; ".join(bits)


def dryup_counts(panel: pd.DataFrame, tickers: set[str]) -> dict[str, dict]:
    """Per ticker: sessions out of the last 10 with volume 45% / 60% under the 50-day average volume (the average excludes the counted window)."""
    out = {}
    for tk, df in panel[panel["ticker"].isin(tickers)].groupby("ticker", sort=False):
        v = pd.to_numeric(df.sort_values("date")["volume"], errors="coerce")
        if len(v) < 50 + DRYUP_WINDOW:
            out[tk] = {"dryup_45": None, "dryup_60": None, "dryup_window": DRYUP_WINDOW}
            continue
        avg = v.iloc[-(50 + DRYUP_WINDOW):-DRYUP_WINDOW].mean()
        w = v.tail(DRYUP_WINDOW)
        out[tk] = {"dryup_45": int((w <= avg * (1 - DRYUP_45)).sum()), "dryup_60": int((w <= avg * (1 - DRYUP_60)).sum()), "dryup_window": DRYUP_WINDOW}
    return out


def store_flags(block: dict) -> dict:
    """One row per basket per session in aqe.db (the QS-trail pattern) so a timeline can be drawn later. Loud on failure, never raises."""
    if block.get("status") != "OK":
        return {"persisted": 0, "error": block.get("reason")}
    try:
        from src.data import db
        with db.get_conn() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS valen_theme_flags (date TEXT, basket TEXT, bullish INTEGER, sessions_on INTEGER, rs_1m INTEGER, leading INTEGER, PRIMARY KEY (date, basket))")
            conn.executemany("INSERT OR REPLACE INTO valen_theme_flags VALUES (?,?,?,?,?,?)",
                             [(block["as_of"], b["name"], int(bool(b["bullish"])), b["sessions_on"], b["rs_1m"], int(b["leading"])) for b in block["baskets"]])
        return {"persisted": len(block["baskets"]), "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"persisted": 0, "error": f"{type(exc).__name__}: {exc}"}
