"""VALEN plain English — rule-based, no LLM, same discipline as
src/macro/crown/explain.py (deterministic template-filling, jargon-tested).

Produces the card's prose from the finished trend/extension/stance dicts.
Never opens a file, never calls a network, never imports pandas — a pure
function of its arguments, same as crown/explain.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

_STANCE_WORDS = {
    "RISK_ON": "RISK ON",
    "NEUTRAL": "NEUTRAL",
    "RISK_OFF": "RISK OFF",
}


def _trend_sentence(trend: dict) -> str | None:
    spy = (trend.get("rows") or {}).get("SPY") or {}
    regime = trend.get("regime")
    if regime is None or spy.get("last_price") is None:
        return None
    if regime == "UPTREND":
        return (f"SPY is above its 10- and 20-day lines, above a rising "
                f"5-day line, and the weekly test agrees — the index is in "
                f"an uptrend.")
    if regime == "DOWNTREND":
        return ("SPY is below its short-term lines on both the daily and "
                "weekly charts — the index is in a downtrend.")
    return ("SPY's daily, weekly and 5-day trend checks disagree with each "
            "other — that is chop, and chop is where breakouts get sold.")


def _extension_sentence(extension: dict) -> str | None:
    bits = []
    for sym in ("SPY", "QQQ"):
        row = (extension.get("index_atr") or {}).get(sym) or {}
        mult = row.get("atr_multiple_from_50d")
        if mult is not None:
            word = "stretched" if row.get("stretched") else "not stretched"
            bits.append(f"{sym} sits {mult} ATRs above its 50-day line ({word})")
    vv = extension.get("vix_vix3m") or {}
    if vv.get("ratio") is not None:
        if vv.get("uncertainty"):
            bits.append(f"VIX/VIX3M is {vv['ratio']:.2f}, above 1.00 — the "
                        f"options market is pricing near-term uncertainty")
        elif vv.get("calm"):
            bits.append(f"VIX/VIX3M is {vv['ratio']:.2f}, below 0.82 — calm")
        else:
            bits.append(f"VIX/VIX3M is {vv['ratio']:.2f} — neither calm nor "
                        f"stressed")
    if not bits:
        return None
    return " ".join((b[0].upper() + b[1:] + ".") if not b.endswith(".") else b
                     for b in bits)


def _watch_for_lines(watch_for: list[dict]) -> list[str]:
    out = []
    for row in watch_for:
        now = row.get("now")
        level = row.get("level")
        if now is None or level is None:
            continue
        verb = "clears" if row.get("direction") == "to_positive" else "falls under"
        out.append(f"{row['what']} {verb} {level} (now {now})")
    return out


def explain(trend: dict, extension: dict, stance: dict) -> dict:
    """Returns {headline, because, so_what, watch_for, caveats, as_of, note}
    — same key set as crown/explain.py's plain_english, for one shared
    rendering idiom across the two macro pages."""
    because = [s for s in (_trend_sentence(trend), _extension_sentence(extension)) if s]

    stance_word = _STANCE_WORDS.get(stance.get("stance"))
    caveats: list[str] = []
    if stance.get("status") == "DEGRADED":
        caveats.append(
            "The one-word stance is not shown: it depends on whole-market "
            "breadth (how many stocks are above their 40-day line, how many "
            "moved 25%+ this month) that AQE does not yet compute across the "
            "full market — " + (stance.get("reason") or ""))

    if stance_word:
        headline = f"Stance: {stance_word}. " + (because[0] if because else "")
    elif because:
        headline = because[0]
    else:
        headline = "Not enough data to read the market yet."

    so_what = None
    if stance.get("status") == "OK":
        so_what = {
            "RISK_ON": "Breadth confirms the trend — conditions favour the full playbook.",
            "NEUTRAL": "Mixed signals — half size, best setups only, take profit sooner.",
            "RISK_OFF": "Breadth is against the tape — build the watchlist, do not push new entries.",
        }.get(stance.get("stance"))

    return {
        "headline": headline,
        "because": because,
        "so_what": so_what,
        "watch_for": _watch_for_lines(stance.get("watch_for") or []),
        "caveats": caveats,
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "Rule-based reading, not a prediction — see docs/AQE_VALEN_DASHBOARD_PROPOSAL.md.",
    }
