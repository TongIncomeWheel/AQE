"""Macro scenario reads — the FIRST MERGE POINT between Crown and Macro Weather.

Macro Weather has been capturing TLT / UUP / HYG / IWM / GLD / CPER / USO daily
for a long time and using them for one thing: a per-sector headwind score. The
raw cross-asset state — the thing those seven instruments actually describe — was
never assembled into a reading. This module does that, and folds in what Crown
now holds (dispersion, implied correlation, CTA sector bias, the breadth regime)
so the story is told by every series we have rather than by the ETFs alone.

**Why this lives OUTSIDE `crown/`.** The PM directive is that Crown is built
standalone and merged with SRM / Macro Weather / Thematic RRG later, so the
overlap stays measurable. Importing SRM into a Crown module would quietly
pre-empt that decision — and a test forbids it. So Crown stays pure, and this
module reads *both* finished outputs. That is what a merge point is: a named
place where two independent readings meet, not a dependency buried in one of
them.

**A score here is the share of a scenario's conditions currently met. It is NOT
a probability.** Nothing was fitted, nothing was backtested, no base rate was
measured. It says "seven of nine things this story needs are true right now",
which is a genuinely different and weaker claim than "70% likely" — and the
whole value is in the evidence and falsifier lists, not the number.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

# Conditions are (source, key, expected, weight). `expected` means:
#   macro      "up" / "down"      — sign of that instrument's direction score
#   vol        a literal value the reading must equal / satisfy
#   cta        "up" / "down"      — sign of that sector's trend bias
#   heartbeat  a regime name
SCENARIOS: dict[str, dict] = {
    "REFLATION": {
        "story": "Growth accelerating and yields rising with it. Cyclicals and "
                 "small caps lead; duration is the funding source.",
        "conditions": [
            ("macro", "CPER", "up", 1.0),
            ("macro", "COPPER_GOLD", "up", 1.5),
            ("macro", "HYG", "up", 1.0),
            ("macro", "IWM", "up", 1.0),
            ("macro", "TLT", "down", 1.0),
            ("cta", "energy", "up", 0.5),
            ("cta", "rates", "down", 0.5),
        ],
        "expression": "Cyclicals, financials, small caps, energy. Short duration.",
    },
    "GROWTH_SCARE": {
        "story": "Growth decelerating. Credit widens, small caps break, and "
                 "duration bids as a hedge rather than as a rate call.",
        "conditions": [
            ("macro", "CPER", "down", 1.0),
            ("macro", "COPPER_GOLD", "down", 1.5),
            ("macro", "HYG", "down", 1.5),
            ("macro", "IWM", "down", 1.0),
            ("macro", "TLT", "up", 1.0),
            ("cta", "rates", "up", 0.5),
        ],
        "expression": "Defensives, quality, long duration. Fade cyclical strength.",
    },
    "INFLATION_SHOCK": {
        "story": "Commodity-led repricing. Rates and the dollar rise together, "
                 "which is the combination that hurts everything at once.",
        "conditions": [
            ("macro", "USO", "up", 1.5),
            ("macro", "GLD", "up", 1.0),
            ("macro", "TLT", "down", 1.5),
            ("macro", "UUP", "up", 1.0),
            ("cta", "energy", "up", 1.0),
        ],
        "expression": "Real assets, energy, short duration. Multiple compression risk.",
    },
    "DISINFLATION_GOLDILOCKS": {
        "story": "Yields fall without credit breaking. The benign version of "
                 "lower rates — the one where breadth improves rather than hides.",
        "conditions": [
            ("macro", "TLT", "up", 1.5),
            ("macro", "HYG", "up", 1.5),
            ("macro", "IWM", "up", 1.0),
            ("macro", "USO", "down", 1.0),
            ("heartbeat", "regime", "broadening", 1.0),
        ],
        "expression": "Long duration equity, small caps, breadth trades.",
    },
    "LIQUIDITY_STRESS": {
        "story": "Flight to quality. The dollar and gold bid together while "
                 "credit gives way, and CORRELATION rises — everything trades "
                 "as one thing, which is what makes it a liquidity event rather "
                 "than a rotation.",
        "conditions": [
            ("macro", "UUP", "up", 1.5),
            ("macro", "GLD", "up", 1.0),
            ("macro", "HYG", "down", 2.0),
            ("macro", "TLT", "up", 1.0),
            ("vol", "correlation_rising", True, 1.5),
            ("vol", "dispersion_band", "CALM", 1.0),
        ],
        "expression": "Cut gross. Defined-risk downside. Cash is a position.",
    },
    "DISPERSION_REGIME": {
        "story": "A stock-picker's tape. Implied correlation collapses and "
                 "single-stock vol pulls away from a calm index — the index "
                 "tells you almost nothing about what the average name is doing.",
        "conditions": [
            ("vol", "correlation_low", True, 2.0),
            ("vol", "dispersion_elevated", True, 2.0),
            ("vol", "vix_low", True, 1.0),
            ("cta", "spread", "wide", 1.0),
        ],
        "expression": "Single-name selection over index exposure. Pairs. "
                      "Sell index vol / own single-stock vol.",
    },
    "DOLLAR_SQUEEZE": {
        "story": "The dollar is the whole story and it is draining everything "
                 "else — commodities, credit and non-US risk together.",
        "conditions": [
            ("macro", "UUP", "up", 2.0),
            ("macro", "CPER", "down", 1.0),
            ("macro", "GLD", "down", 1.0),
            ("macro", "HYG", "down", 1.0),
            ("cta", "fx", "up", 1.0),
        ],
        "expression": "US large-cap domestic over international and commodities.",
    },
}

# Two scenarios within this of each other is a contested tape, not a call.
CONTESTED_MARGIN = 0.12
LEADING_MIN_SCORE = 0.50        # below this, nothing is really leading
# A score computed from two of seven conditions is not comparable to one
# computed from seven of seven, and ranking them together lets a scenario lead
# on the strength of the data we happen to be MISSING. Anything below this is
# reported with its evidence but cannot lead.
MIN_COVERAGE_TO_LEAD = 0.60
CORRELATION_LOW_PCTL = 0.25
VIX_LOW = 15.0
CTA_SPREAD_WIDE = 0.60          # max sector bias minus min, in signal units


# ── condition evaluation ──────────────────────────────────────────────────

def _macro_condition(weather: dict, inst: str, expected: str):
    """(met, strength, detail). None when the instrument is unavailable."""
    w = (weather or {}).get(inst)
    if not w:
        return None, 0.0, f"{inst}: unavailable"
    score = float(w.get("score", 0))
    if score == 0:
        return False, 0.0, f"{inst} flat (roc5 {w.get('roc5')}%, roc20 {w.get('roc20')}%)"
    up = score > 0
    met = up if expected == "up" else (not up)
    return (met, abs(score) / 2.0,
            f"{inst} {'up' if up else 'down'} "
            f"(roc5 {w.get('roc5')}%, roc20 {w.get('roc20')}%)")


def _vol_condition(vol: dict, key: str, expected):
    disp = (vol or {}).get("dispersion") or {}
    corr = (vol or {}).get("corroboration") or {}

    if key == "correlation_low":
        p = corr.get("correlation_percentile")
        if p is None:
            return None, 0.0, "implied correlation: unavailable"
        met = (p <= CORRELATION_LOW_PCTL) == bool(expected)
        return met, 1.0, f"implied correlation {corr.get('implied_correlation')} ({p:.0%} pctl)"

    if key == "correlation_rising":
        p = corr.get("correlation_percentile")
        if p is None:
            return None, 0.0, "implied correlation: unavailable"
        # High correlation percentile is the liquidity-event tell.
        met = (p >= 0.60) == bool(expected)
        return met, 1.0, f"implied correlation at {p:.0%} pctl"

    if key == "dispersion_elevated":
        band = disp.get("band")
        if band in (None, "UNKNOWN"):
            return None, 0.0, "dispersion: unavailable"
        met = (band == "ELEVATED") == bool(expected)
        return met, 1.0, f"dispersion {band} (spread {disp.get('spread')})"

    if key == "dispersion_band":
        band = disp.get("band")
        if band in (None, "UNKNOWN"):
            return None, 0.0, "dispersion: unavailable"
        return band == expected, 1.0, f"dispersion {band}"

    if key == "vix_low":
        v = (vol or {}).get("vix")
        if v is None:
            return None, 0.0, "VIX: unavailable"
        met = (float(v) < VIX_LOW) == bool(expected)
        return met, 1.0, f"VIX {v}"

    return None, 0.0, f"vol.{key}: unknown condition"


def _cta_condition(cta: dict, key: str, expected):
    bias = (cta or {}).get("sector_bias") or {}
    if key == "spread":
        if len(bias) < 2:
            return None, 0.0, "CTA sector bias: unavailable"
        spread = float(max(bias.values()) - min(bias.values()))
        met = (spread >= CTA_SPREAD_WIDE) == (expected == "wide")
        return met, 1.0, f"CTA sector spread {spread:.2f}"
    v = bias.get(key)
    if v is None:
        return None, 0.0, f"CTA {key}: unavailable"
    up = float(v) > 0
    met = up if expected == "up" else (not up)
    return met, min(abs(float(v)), 1.0), f"CTA {key} bias {float(v):+.2f}"


def _heartbeat_condition(hb: dict, key: str, expected):
    val = (hb or {}).get(key)
    if val is None:
        return None, 0.0, f"heartbeat {key}: unavailable"
    return val == expected, 1.0, f"heartbeat {key} = {val}"


def evaluate(name: str, weather: dict, vol: dict, cta: dict, hb: dict) -> dict:
    """Score one scenario and show every condition, met or not."""
    spec = SCENARIOS[name]
    met, unmet, missing = [], [], []
    got, total = 0.0, 0.0

    for source, key, expected, weight in spec["conditions"]:
        if source == "macro":
            ok, strength, detail = _macro_condition(weather, key, expected)
        elif source == "vol":
            ok, strength, detail = _vol_condition(vol, key, expected)
        elif source == "cta":
            ok, strength, detail = _cta_condition(cta, key, expected)
        else:
            ok, strength, detail = _heartbeat_condition(hb, key, expected)

        if ok is None:
            missing.append(detail)
            continue
        total += weight
        if ok:
            got += weight * max(strength, 0.5)   # met-but-weak still counts, at half
            met.append(detail)
        else:
            unmet.append(detail)

    n_defined = len(spec["conditions"])
    return {
        "scenario": name,
        "score": round(got / total, 4) if total > 0 else None,
        "coverage": round((n_defined - len(missing)) / n_defined, 4),
        "story": spec["story"],
        "expression": spec["expression"],
        "evidence": met,
        # The falsifier list. What is NOT true is what would have to change for
        # this story to become the read, and it is the more useful column.
        "missing_conditions": unmet,
        "unavailable": missing,
    }


def analyse(weather: dict | None, crown: dict | None) -> dict:
    """Rank every scenario against the current cross-asset state."""
    crown = crown or {}
    vol = crown.get("volatility") or {}
    cta = crown.get("cta") or {}
    hb = crown.get("heartbeat") or {}

    if not weather and not vol:
        return {"status": "UNAVAILABLE", "scenarios": [], "leading": None,
                "reason": "neither macro weather nor a Crown read is available"}

    ranked = [evaluate(n, weather or {}, vol, cta, hb) for n in SCENARIOS]
    ranked = [r for r in ranked if r["score"] is not None]
    ranked.sort(key=lambda r: -r["score"])

    if not ranked:
        return {"status": "UNAVAILABLE", "scenarios": [], "leading": None,
                "reason": "no scenario had a single evaluable condition"}

    for r in ranked:
        r["can_lead"] = bool(r["coverage"] >= MIN_COVERAGE_TO_LEAD)
        if not r["can_lead"]:
            r["caveat"] = (f"only {r['coverage']:.0%} of this scenario's conditions "
                           "could be evaluated — reported, but not eligible to lead")

    eligible = [r for r in ranked if r["can_lead"]]
    top = eligible[0] if eligible else None
    second = eligible[1] if len(eligible) > 1 else None
    contested = bool(top and second and (top["score"] - second["score"]) < CONTESTED_MARGIN)
    leading = (top["scenario"] if top and top["score"] >= LEADING_MIN_SCORE else None)

    if top is None:
        reading = ("No scenario had enough of its inputs available to be ranked — "
                   "this is a data gap, not a quiet tape.")
    elif leading is None:
        reading = ("No scenario has a majority of its conditions met — the tape "
                   "is not currently expressing a clean macro story.")
    elif contested:
        reading = (f"{top['scenario']} leads but {second['scenario']} is within "
                   f"{CONTESTED_MARGIN:.0%}. Two stories fit the same tape; treat "
                   "the overlap as the honest read, not the winner.")
    else:
        reading = f"{top['scenario']} is the cleanest fit to the current cross-asset state."

    return {
        "status": "OK",
        "scenarios": ranked,
        "leading": leading,
        "leading_score": top["score"] if top else None,
        "runner_up": second["scenario"] if second else None,
        "contested": contested,
        "reading": reading,
        "note": ("A score is the SHARE OF CONDITIONS MET, not a probability. "
                 "Nothing here was fitted or backtested and no base rate was "
                 "measured. The evidence and the missing-conditions lists carry "
                 "the value; the number only ranks them."),
        "merge_point": ("Macro Weather (TLT/UUP/HYG/IWM/GLD/CPER/USO) + the Crown "
                        "layer (dispersion, implied correlation, CTA bias, "
                        "breadth). Crown itself stays standalone."),
    }


# ── data ──────────────────────────────────────────────────────────────────

def fetch_weather(client=None, lookback_days: int = 120) -> tuple[dict, list[str]]:
    """Macro Weather from the same seven instruments SRM already reads.

    Returns (weather, missing). Calls `srm.compute_macro_weather` rather than
    reimplementing the direction score, so this module and the sector headwind
    can never disagree about whether copper is rising.
    """
    from src.engines.srm import MACRO_INSTRUMENTS, compute_macro_weather

    try:
        from src.data.fmp_client import FMPClient
        c = client or FMPClient()
    except Exception:
        return {}, list(MACRO_INSTRUMENTS)

    to_d = date.today()
    from_d = to_d - timedelta(days=lookback_days)
    closes, missing = {}, []
    for inst in MACRO_INSTRUMENTS:
        try:
            bars = c.get_daily_bars(inst, from_date=from_d, to_date=to_d)
        except Exception:
            bars = None
        if bars is not None and len(bars):
            closes[inst] = bars["close"].astype(float).to_numpy()
        else:
            missing.append(inst)
    if not closes:
        return {}, missing
    return compute_macro_weather(closes), missing


def run_scenarios(client=None, crown: dict | None = None,
                  write: bool = True) -> dict:
    """Fetch what is needed and produce the scenario read."""
    import json
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from src.data.paths import OUTPUT_DIR
    from src.macro.crown.daily import load_crown

    weather, missing = fetch_weather(client)
    crown = crown if crown is not None else (load_crown() or {})
    out = analyse(weather, crown)
    out["weather"] = weather
    out["weather_missing"] = missing
    out["generated_at"] = datetime.now(ZoneInfo("Asia/Singapore")).isoformat(
        timespec="seconds")
    if missing:
        out.setdefault("degraded", []).append(
            "macro instruments unavailable: " + ", ".join(missing))
    if not crown:
        out.setdefault("degraded", []).append(
            "no Crown read — dispersion, correlation, CTA and breadth conditions "
            "were skipped, not failed")

    if write:
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            (OUTPUT_DIR / "macro_scenarios.json").write_text(
                json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            print(f"[scenarios] could not write artifact: {exc}", flush=True)
    return out


def load_scenarios() -> dict | None:
    """The last written scenario read, for the UI to render without re-running."""
    import json

    from src.data.paths import OUTPUT_DIR

    p = OUTPUT_DIR / "macro_scenarios.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
