"""VALEN card renderer — from the artifact alone.

No data libraries, no file access, no engine imports. Renders ONLY from the
dict this module is handed (the same `valen` block that ships in the export
JSON), so every claim the card makes is reconstructible from that one file —
the same rule tests/test_qs_card.py enforces on qs_card.py. Streamlit pages
call these functions; they do not compute anything themselves either.
"""

from __future__ import annotations


def stance_banner(valen: dict) -> dict:
    stance = (valen.get("stance") or {})
    word = stance.get("stance") or "—"
    return {
        "word": word.replace("_", " "),
        "status": stance.get("status", "UNAVAILABLE"),
        "reason": stance.get("reason"),
    }


def headline(valen: dict) -> str:
    return (valen.get("plain_english") or {}).get("headline") or "No read available."


def trend_rows(valen: dict) -> list[dict]:
    trend = valen.get("trend") or {}
    rows = (trend.get("rows") or {})
    out = []
    for sym in ("SPY", "QQQ"):
        r = rows.get(sym) or {}
        out.append({
            "symbol": sym,
            "last_price": r.get("last_price"),
            "daily_buy_signal": r.get("daily_buy_signal"),
            "weekly_buy_signal": r.get("weekly_buy_signal"),
            "above_rising_5d": r.get("above_rising_5d"),
            "basis": r.get("basis", "unavailable"),
        })
    return out


def regime_word(valen: dict) -> str:
    return (valen.get("trend") or {}).get("regime") or "UNKNOWN"


def extension_rows(valen: dict) -> list[dict]:
    ext = valen.get("extension") or {}
    idx = ext.get("index_atr") or {}
    rows = []
    for sym in ("SPY", "QQQ"):
        r = idx.get(sym) or {}
        rows.append({"label": f"{sym} ATRs above 50-day",
                     "value": r.get("atr_multiple_from_50d"),
                     "flag": r.get("stretched")})
    vv = ext.get("vix_vix3m") or {}
    rows.append({"label": "VIX / VIX3M", "value": vv.get("ratio"),
                 "flag": vv.get("uncertainty")})
    return rows


def breadth_rows(valen: dict) -> list[dict]:
    """Every row is either a real reading or the honest UNAVAILABLE shape —
    never silently dropped, so a reader can tell "not computed" from "zero"."""
    breadth = valen.get("breadth") or {}
    labels = {
        "pct_above_40d": "Stocks above their 40-day line",
        "monthly_risers": "Monthly big risers (25%+)",
        "five_day_count": "5-day up/down 4% count",
        "daily_count_green": "Today's count green",
    }
    out = []
    for key, label in labels.items():
        row = breadth.get(key) or {"status": "UNAVAILABLE", "reason": "not computed"}
        out.append({"label": label, "status": row.get("status"),
                    "value": row.get("value"), "reason": row.get("reason")})
    return out


def watch_for_lines(valen: dict) -> list[str]:
    return (valen.get("plain_english") or {}).get("watch_for") or []


def caveats(valen: dict) -> list[str]:
    return (valen.get("plain_english") or {}).get("caveats") or []


def freshness(valen: dict) -> dict:
    return {"as_of": (valen.get("plain_english") or {}).get("as_of"),
            "basis": valen.get("basis", "eod")}
