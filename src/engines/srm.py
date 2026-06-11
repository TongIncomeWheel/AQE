"""SRM v3.0 — Sector Rotation Monitor.

Grades each GICS sector based on breadth and momentum of its ETF.
Uses the sector ETF directly (not constituents) for the simplified
backtester implementation.

Grades: DEPLOY / HOLD / TURNING / WATCH / AVOID

For PTRS integration, the grade maps to SH (Sector Health) values:
    DEPLOY  → +3
    HOLD    → 0
    TURNING → -3
    WATCH   → -5
    AVOID   → -8
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


GICS_ETFS = ["XLK", "XLV", "XLF", "XLE", "XLI", "XLY", "XLP", "XLRE", "XLU", "XLC", "XLB"]

TICKER_TO_SECTOR = {
    "AAPL": "XLK", "MSFT": "XLK", "NVDA": "XLK", "AVGO": "XLK", "AMD": "XLK",
    "CRWD": "XLK", "PLTR": "XLK", "ANET": "XLK", "NOW": "XLK",
    "AMZN": "XLY", "TSLA": "XLY", "COST": "XLY", "HD": "XLY", "NKE": "XLY",
    "BKNG": "XLY", "ABNB": "XLY",
    "GOOGL": "XLC", "META": "XLC", "NFLX": "XLC", "DIS": "XLC", "SPOT": "XLC",
    "JPM": "XLF", "V": "XLF", "MA": "XLF", "GS": "XLF", "BLK": "XLF",
    "AXP": "XLF", "COIN": "XLF",
    "UNH": "XLV", "LLY": "XLV", "JNJ": "XLV", "ABBV": "XLV", "MRK": "XLV",
    "ISRG": "XLV", "TMO": "XLV",
    "XOM": "XLE", "CVX": "XLE", "COP": "XLE", "SLB": "XLE", "OXY": "XLE",
    "CAT": "XLI", "GE": "XLI", "RTX": "XLI", "HON": "XLI", "DE": "XLI",
    "VRT": "XLI", "UBER": "XLI",
    "PG": "XLP", "KO": "XLP", "PEP": "XLP", "WMT": "XLP", "PM": "XLP",
    "NEE": "XLU", "SO": "XLU", "DUK": "XLU", "CEG": "XLU", "VST": "XLU",
    "AMT": "XLRE", "PLD": "XLRE", "CCI": "XLRE",
    "FCX": "XLB", "LIN": "XLB", "NEM": "XLB",
}

GRADE_TO_SH = {
    "DEPLOY": 3,
    "HOLD": 0,
    "TURNING": -3,
    "WATCH": -5,
    "AVOID": -8,
}

# Best -> worst ordering for grade comparisons (lower = better).
GRADE_ORDER = {"DEPLOY": 0, "HOLD": 1, "TURNING": 2, "WATCH": 3, "AVOID": 4}

# ── Thematic baskets (Thematic Basket Map v2.0, PM-approved 11 Jun 2026) ──────
# A basket is a CONTEXT LAYER ONLY: it annotates names AQE already scored and
# grades a sector from its constituents' equal-weight price index (capped at the
# parent-GICS grade). It does NOT add names to the scan universe — constituents
# are pulled into the panel for grading (like the GICS ETFs) but are never
# screened. A basket's parent GICS may differ from a constituent's own GICS
# (e.g. ANET is XLK but AI_Infrastructure's parent is XLRE).
#
# Constituent lists below are the GRADING lists (the v2.0 tables, verbatim).
# Counts: Infra 13, Space 10, AI 12, Semi 15, Cyber 13, Defense 13, Crypto 12.
THEMATIC_BASKETS: dict[str, dict] = {
    "Infra_Power":       {"parent_gics_etf": "XLI",
                          "constituents": ["VRT", "ETN", "PWR", "HUBB", "EMR", "GNRC", "JBL",
                                           "GEV", "POWL", "NVT", "ATKR", "VST", "CEG"]},
    "Space_eVTOL":       {"parent_gics_etf": "XLI",
                          "constituents": ["RKLB", "ASTS", "JOBY", "LUNR", "RDW",
                                           "ACHR", "PL", "VOYG", "KTOS", "AVAV"]},
    "AI_Infrastructure": {"parent_gics_etf": "XLRE",
                          "constituents": ["EQIX", "DLR", "AMT", "SMCI", "APLD", "ANET",
                                           "NBIS", "IREN", "CORZ", "CCI", "WULF", "SBAC"]},
    "Semiconductors":    {"parent_gics_etf": "XLK",
                          "constituents": ["NVDA", "AMD", "AVGO", "CRDO", "AMAT", "KLAC",
                                           "LRCX", "MRVL", "MU", "QCOM", "TXN", "ADI",
                                           "NXPI", "MCHP", "ARM"]},
    "Cybersecurity":     {"parent_gics_etf": "XLK",
                          "constituents": ["FTNT", "CRWD", "PANW", "ZS", "OKTA", "S",
                                           "CYBR", "TENB", "VRNS", "NET", "RBRK", "QLYS",
                                           "RPD"]},
    "Defense_Tech":      {"parent_gics_etf": "XLI",
                          "constituents": ["LMT", "RTX", "GD", "NOC", "LHX", "PLTR", "AXON",
                                           "TDG", "HII", "LDOS", "BAH", "CW", "HEI"]},
    "Crypto_Digital":    {"parent_gics_etf": "XLF",
                          "constituents": ["MSTR", "HOOD", "COIN", "MARA", "RIOT", "CLSK",
                                           "BTDR", "HUT", "CIFR", "IREN", "CORZ", "WULF"]},
}

# Annotation-only dual memberships (v2.0 Dual-Basket Summary). A ticker here is
# TAGGED with the extra basket for committee context, but is NOT in that basket's
# grading table (so it does not move that basket's grade). KTOS/AVAV grade in
# Space_eVTOL but are surfaced as Defense_Tech too. IREN/CORZ/WULF need no entry:
# they appear in BOTH the AI_Infrastructure and Crypto_Digital grading tables, so
# the constituent-derived map already tags them with both.
EXTRA_THEMATIC_TAGS: dict[str, list[str]] = {
    "KTOS": ["Defense_Tech"],
    "AVAV": ["Defense_Tech"],
}

# Reverse lookup. A ticker may belong to MULTIPLE baskets (v2.0 dual-listing).
# TICKER_TO_THEMATICS holds the full ordered list (primary = first declared);
# TICKER_TO_THEMATIC keeps the primary basket for single-value callers.
TICKER_TO_THEMATICS: dict[str, list[str]] = {}
for _bname, _binfo in THEMATIC_BASKETS.items():
    for _tk in _binfo["constituents"]:
        _lst = TICKER_TO_THEMATICS.setdefault(_tk, [])
        if _bname not in _lst:
            _lst.append(_bname)
for _tk, _extra in EXTRA_THEMATIC_TAGS.items():
    _lst = TICKER_TO_THEMATICS.setdefault(_tk, [])
    for _b in _extra:
        if _b not in _lst:
            _lst.append(_b)
TICKER_TO_THEMATIC: dict[str, str] = {_tk: _bs[0] for _tk, _bs in TICKER_TO_THEMATICS.items()}

# Union of all GRADING constituents — pulled into the panel for grading but never
# screened (panel_builder adds them; scoring/screening exclude any not already in
# the scan universe). Annotation-only duals (KTOS/AVAV) are already constituents
# of their grading basket, so this set is complete.
BASKET_CONSTITUENTS: set[str] = {
    _c for _b in THEMATIC_BASKETS.values() for _c in _b["constituents"]
}

# Action-state labels: each encodes the market condition AND the implied posture
# for a momentum book, so Alfred/committee read a directive, not a raw signal.
# Derived from the two signals SRM already computes — price vs 20D SMA (trend
# direction) and divergence = roc5 − roc20 (momentum accelerating vs decelerating).
TREND_STATE = {
    (True, True):   "Momentum Building — Add",
    (True, False):  "Momentum Fading — Hold, Don't Add",
    (False, True):  "Recovering From Weakness — Watch for Entry",
    (False, False): "Declining — Avoid",
}


def _trend_state(above_sma20: bool, divergence: float) -> str:
    """Map (trend direction, momentum slope) to a directive action-state label."""
    return TREND_STATE[(bool(above_sma20), divergence > 0.0)]



def grade_sector_etf(etf_daily: pd.DataFrame) -> dict:
    """Grade a single sector ETF's daily bars. Returns latest grade + metrics."""
    if etf_daily.empty or len(etf_daily) < 25:
        return {"grade": "WATCH", "roc20": 0.0, "roc5": 0.0, "above_sma20": False,
                "sh": -5, "trend_state": _trend_state(False, 0.0)}

    close = etf_daily["close"].astype(float)
    sma20 = U.sma(close, 20)

    latest = close.iloc[-1]
    roc20 = (latest - close.iloc[-21]) / close.iloc[-21] * 100.0 if len(close) >= 21 else 0.0
    roc5 = (latest - close.iloc[-6]) / close.iloc[-6] * 100.0 if len(close) >= 6 else 0.0
    above_sma20 = bool(latest > sma20.iloc[-1]) if sma20.notna().iloc[-1] else False

    divergence = roc5 - roc20  # positive = 5d momentum recovering vs 20d trend

    # Canonical SRM grading — must match live /SRM output exactly.
    # Evaluate top-to-bottom, first match wins.
    if above_sma20 and roc20 > 5.0:
        grade = "DEPLOY"
    elif above_sma20 and roc20 > 0.0:
        grade = "HOLD"
    elif not above_sma20 and divergence > 0.0:
        grade = "TURNING"
    elif above_sma20 and roc20 <= 0.0:
        grade = "WATCH"
    else:
        grade = "AVOID"

    return {
        "grade": grade,
        "roc20": round(roc20, 2),
        "roc5": round(roc5, 2),
        "divergence": round(divergence, 2),
        "above_sma20": above_sma20,
        "sh": GRADE_TO_SH[grade],
        "trend_state": _trend_state(above_sma20, divergence),
    }


def grade_all_sectors(panel_daily: pd.DataFrame, trend_days: int = 0) -> dict[str, dict]:
    """Grade all GICS sector ETFs present in the panel. Returns {ETF: grade_dict}.

    When trend_days > 0, each ETF's dict also carries `sh_trend` and
    `grade_trend` -- the SRM reading for each of the last `trend_days` trading
    sessions, oldest -> newest -- so consumers see a trend rather than a
    one-day snapshot. Each historical reading is graded only on bars up to
    that day (no look-ahead); the newest trend entry equals the current grade.
    """
    results = {}
    for etf in GICS_ETFS:
        etf_data = (
            panel_daily.loc[panel_daily["ticker"] == etf]
            .sort_values("date").reset_index(drop=True)
        )
        info = grade_sector_etf(etf_data)
        if trend_days > 0 and len(etf_data) >= 25:
            sh_trend: list[float] = []
            grade_trend: list[str] = []
            n = len(etf_data)
            for k in range(max(25, n - trend_days + 1), n + 1):
                g = grade_sector_etf(etf_data.iloc[:k])
                sh_trend.append(g["sh"])
                grade_trend.append(g["grade"])
            info = {**info, "sh_trend": sh_trend, "grade_trend": grade_trend}
        results[etf] = info
    return results


def _cap_grade(thematic: str, parent: str | None) -> str:
    """Clamp a thematic grade so it can't be BETTER than its parent GICS grade."""
    if not parent or parent not in GRADE_ORDER or thematic not in GRADE_ORDER:
        return thematic
    # Higher order = worse. If thematic is better (lower order) than parent,
    # clamp it down to the parent grade.
    return thematic if GRADE_ORDER[thematic] >= GRADE_ORDER[parent] else parent


def grade_thematic_baskets(panel_daily: pd.DataFrame, sector_grades: dict,
                           min_constituents: int = 2) -> dict[str, dict]:
    """Grade each thematic basket from its constituents' equal-weight price index.

    Reuses grade_sector_etf on a normalized equal-weight index of the
    constituents present in the panel, then CAPS the result at the parent-GICS
    grade. Degrades gracefully: a basket with fewer than min_constituents bars
    present (e.g. constituents not yet in the universe) grades NO_DATA.

    Returns {basket: {grade, raw_grade, parent_gics, parent_grade, roc20, roc5,
    above_sma20, coverage, constituents_used, rrg_rs_ratio, rrg_rs_momentum,
    rrg_quadrant, rrg_direction}}. Pure panel math — 0 FMP calls. RRG is the
    basket's equal-weight index vs SPY (same method as the GICS sector RRG).
    """
    out: dict[str, dict] = {}
    try:
        piv = panel_daily.pivot_table(index="date", columns="ticker", values="close").sort_index()
    except Exception:  # noqa: BLE001
        piv = None

    for name, info in THEMATIC_BASKETS.items():
        parent = info["parent_gics_etf"]
        cons = info["constituents"]
        parent_grade = (sector_grades.get(parent) or {}).get("grade")
        present = [t for t in cons if piv is not None and t in piv.columns]

        sub = piv[present].tail(80) if present else None
        if sub is None or sub.shape[1] < min_constituents or len(sub) < 25:
            out[name] = {
                "grade": "NO_DATA", "raw_grade": "NO_DATA",
                "parent_gics": parent, "parent_grade": parent_grade,
                "roc20": None, "roc5": None, "above_sma20": None,
                "coverage": f"{len(present)}/{len(cons)}",
                "constituents_used": present,
                **_rrg_no_data(),
            }
            continue

        # Equal-weight index: rebase each constituent to its first valid value,
        # then average across columns (skipna so staggered listings don't break it).
        base = sub.bfill().iloc[0]
        norm = sub.divide(base.where(base != 0))
        idx = norm.mean(axis=1, skipna=True).dropna()
        basket_df = pd.DataFrame({"date": idx.index, "close": idx.to_numpy()})

        g = grade_sector_etf(basket_df)
        capped = _cap_grade(g["grade"], parent_grade)

        # RRG: the basket index vs SPY, aligned on the index's own dates.
        rrg = _rrg_no_data()
        try:
            if piv is not None and "SPY" in piv.columns:
                spy_aligned = piv["SPY"].reindex(idx.index).to_numpy(dtype=float)
                if not np.isnan(spy_aligned).any():
                    rrg = compute_rrg(idx.to_numpy(dtype=float), spy_aligned)
        except Exception:  # noqa: BLE001
            rrg = _rrg_no_data()

        out[name] = {
            "grade": capped,
            "raw_grade": g["grade"],
            "parent_gics": parent,
            "parent_grade": parent_grade,
            "roc20": g.get("roc20"), "roc5": g.get("roc5"),
            "above_sma20": g.get("above_sma20"),
            "coverage": f"{len(present)}/{len(cons)}",
            "constituents_used": present,
            **rrg,
        }
    return out


def get_sector_health(ticker: str, sector_grades: dict[str, dict]) -> int:
    """Return the SH value for a given ticker based on its sector ETF grade."""
    sector_etf = TICKER_TO_SECTOR.get(ticker)
    if sector_etf is None:
        sector_etf = _dynamic_sector_lookup(ticker)
    if sector_etf is None or sector_etf not in sector_grades:
        return 0  # unknown sector → neutral
    return sector_grades[sector_etf]["sh"]


def _dynamic_sector_lookup(ticker: str) -> str | None:
    """Check data/sector_map.json for dynamically-mapped sectors."""
    from pathlib import Path
    import json
    map_path = Path(__file__).resolve().parents[2] / "data" / "sector_map.json"
    if not map_path.exists():
        return None
    try:
        with open(map_path) as f:
            mapping = json.load(f)
        return mapping.get(ticker)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
# DSG-18 — RRG Sector Relative Strength Layer
# ═══════════════════════════════════════════════════════════════════════

RRG_WINDOW = 42          # ~42 trading days for the RS normalisation window
RRG_MOM_PERIOD = 10      # RS-Momentum = 10-bar ROC of the RS line
RRG_DIR_LOOKBACK = 5     # direction compares to 5 bars ago


def compute_rrg(sector_closes: np.ndarray, spy_closes: np.ndarray) -> dict:
    """Compute RS-Ratio and RS-Momentum for a sector ETF vs SPY.

    Both arrays must be sorted ascending by date with matching alignment.
    Uses the tail of each array (last RRG_WINDOW bars).
    """
    n = min(len(sector_closes), len(spy_closes))
    if n < RRG_WINDOW:
        return _rrg_no_data()

    sc = sector_closes[-RRG_WINDOW:].astype(float)
    sp = spy_closes[-RRG_WINDOW:].astype(float)

    if sp[0] == 0 or np.any(sp == 0):
        return _rrg_no_data()

    rs_line = sc / sp
    rs_norm = rs_line / rs_line[0] * 100.0

    rs_ratio = float(rs_norm[-1])

    if len(rs_norm) >= RRG_MOM_PERIOD + 1 and rs_norm[-(RRG_MOM_PERIOD + 1)] != 0:
        rs_momentum = float(
            (rs_norm[-1] / rs_norm[-(RRG_MOM_PERIOD + 1)] - 1) * 100 + 100
        )
    else:
        rs_momentum = 100.0

    quadrant = _rrg_quadrant(rs_ratio, rs_momentum)

    lb = RRG_DIR_LOOKBACK
    if len(rs_norm) >= lb + RRG_MOM_PERIOD + 2:
        ratio_prev = float(rs_norm[-(lb + 1)])
        mom_denom = rs_norm[-(lb + RRG_MOM_PERIOD + 1)]
        if mom_denom != 0:
            mom_prev = float((rs_norm[-(lb + 1)] / mom_denom - 1) * 100 + 100)
        else:
            mom_prev = 100.0
        quad_prev = _rrg_quadrant(ratio_prev, mom_prev)
        direction = _rrg_direction(
            quadrant, quad_prev, rs_ratio, rs_momentum, ratio_prev, mom_prev
        )
    else:
        direction = "STABLE"

    return {
        "rrg_rs_ratio": round(rs_ratio, 2),
        "rrg_rs_momentum": round(rs_momentum, 2),
        "rrg_quadrant": quadrant,
        "rrg_direction": direction,
    }


def _rrg_no_data() -> dict:
    return {
        "rrg_rs_ratio": None,
        "rrg_rs_momentum": None,
        "rrg_quadrant": "NO_DATA",
        "rrg_direction": "STABLE",
    }


def _rrg_quadrant(rs_ratio: float, rs_momentum: float) -> str:
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "LEADING"
    if rs_ratio < 100 and rs_momentum >= 100:
        return "IMPROVING"
    if rs_ratio >= 100 and rs_momentum < 100:
        return "WEAKENING"
    return "LAGGING"


def _rrg_direction(q_now: str, q_prev: str,
                   ratio: float, mom: float,
                   ratio_prev: float, mom_prev: float) -> str:
    if q_now != q_prev:
        return "ENTERING"
    dist_now = ((ratio - 100) ** 2 + (mom - 100) ** 2) ** 0.5
    dist_prev = ((ratio_prev - 100) ** 2 + (mom_prev - 100) ** 2) ** 0.5
    if dist_prev == 0:
        return "STABLE"
    if dist_now > dist_prev * 1.02:
        return "DEEPENING"
    if dist_now < dist_prev * 0.98:
        return "EXITING"
    return "STABLE"


def rrg_grade_override(grade: str, quadrant: str) -> str | None:
    """DSG-18 grade override flag based on RRG quadrant."""
    if grade == "AVOID" or quadrant == "NO_DATA":
        return None
    if grade == "DEPLOY":
        if quadrant == "WEAKENING":
            return "HOLD_FLAG"
        if quadrant == "LAGGING":
            return "AVOID_FLAG"
    if grade == "HOLD":
        if quadrant == "LEADING":
            return "WATCH_UP"
        if quadrant == "WEAKENING":
            return "CAUTION"
        if quadrant == "LAGGING":
            return "AVOID_FLAG"
    return None


# ═══════════════════════════════════════════════════════════════════════
# DSG-19 — Risk Weather Macro Overlay
# ═══════════════════════════════════════════════════════════════════════

MACRO_INSTRUMENTS = ["TLT", "UUP", "HYG", "IWM", "GLD", "CPER", "USO"]

# Sensitivity sign per sector: when the instrument RISES, does it help (+1),
# hurt (-1), or not matter (0) for the sector?  Columns are ordered to match
# MACRO_INSTRUMENTS: [TLT, UUP, HYG, IWM, GLD, CPER, USO].
#   GLD  — gold up = risk-off / debasement hedge (helps miners, hurts banks)
#   CPER — copper up = "Dr. Copper" global-growth/reflation (helps cyclicals,
#          hurts defensives via rotation + higher yields)
#   USO  — oil up = energy strength but a consumer/transport cost squeeze
SENSITIVITY = {
    "XLK":  [+1, -1, +1, +1,  0, +1,  0],
    "XLC":  [+1, -1, +1, +1,  0, +1,  0],
    "XLY":  [+1,  0, +1, +1,  0, +1, -1],
    "XLF":  [ 0, +1, +1,  0, -1, +1,  0],
    "XLI":  [ 0,  0, +1, +1,  0, +1, -1],
    "XLB":  [+1, -1, +1, +1, +1, +1, +1],
    "XLE":  [ 0, -1,  0,  0,  0, +1, +1],
    "XLV":  [+1,  0,  0,  0,  0,  0,  0],
    "XLP":  [+1,  0,  0, -1,  0, -1,  0],
    "XLRE": [+1, -1,  0,  0,  0,  0,  0],
    "XLU":  [+1,  0,  0, -1,  0, -1,  0],
}

# Original four stay dominant (0.70); the commodity complex adds 0.30.
# Total stays 1.0 so the TAILWIND/CAUTION/HEADWIND thresholds keep their scale.
MACRO_WEIGHTS = [0.22, 0.15, 0.18, 0.15, 0.10, 0.12, 0.08]


def macro_direction_score(closes: np.ndarray) -> tuple[int, float, float]:
    """Direction score for a macro instrument: -2 (strong down) to +2 (strong up).

    Returns (score, roc5, roc20).
    """
    closes = np.asarray(closes, dtype=float)
    if len(closes) < 21:
        return 0, 0.0, 0.0

    roc5 = (closes[-1] / closes[-6] - 1) * 100 if closes[-6] != 0 else 0.0
    roc20 = (closes[-1] / closes[-21] - 1) * 100 if closes[-21] != 0 else 0.0

    score = 0
    if roc5 > 0:
        score += 1
    elif roc5 < 0:
        score -= 1
    if roc20 > 0:
        score += 1
    elif roc20 < 0:
        score -= 1

    return score, round(float(roc5), 2), round(float(roc20), 2)


def compute_macro_headwind(etf: str, macro_scores: dict[str, int]) -> tuple[float, str]:
    """Weighted macro headwind score + flag for a sector ETF.

    macro_scores: {instrument: direction_score} for the MACRO_INSTRUMENTS
    (TLT/UUP/HYG/IWM/GLD/CPER/USO), each in [-2, +2].
    Score range depends on sector sensitivity (roughly -2 to +2).
    Flag: TAILWIND / NEUTRAL / CAUTION / HEADWIND.
    """
    sens = SENSITIVITY.get(etf, [0] * len(MACRO_INSTRUMENTS))
    scores = [macro_scores.get(inst, 0) for inst in MACRO_INSTRUMENTS]
    raw = sum(w * s * se for w, s, se in zip(MACRO_WEIGHTS, scores, sens))
    score = round(raw, 2)

    if score >= 0.5:
        flag = "TAILWIND"
    elif score >= -0.2:
        flag = "NEUTRAL"
    elif score >= -0.5:
        flag = "CAUTION"
    else:
        flag = "HEADWIND"

    return score, flag


def compute_macro_weather(macro_data: dict[str, np.ndarray]) -> dict:
    """Global macro weather summary from instrument close arrays."""
    weather: dict = {}
    for inst in MACRO_INSTRUMENTS:
        closes = macro_data.get(inst)
        if closes is None or len(closes) < 21:
            weather[inst] = {"score": 0, "roc5": 0.0, "roc20": 0.0, "direction": "FLAT"}
            continue
        score, roc5, roc20 = macro_direction_score(closes)
        if roc5 > 0.1:
            direction = "RISING"
        elif roc5 < -0.1:
            direction = "FALLING"
        else:
            direction = "FLAT"
        weather[inst] = {"score": score, "roc5": roc5, "roc20": roc20, "direction": direction}

    # Copper/Gold ratio — the Druckenmiller/Gundlach growth+rates tell.
    # Rising = reflation / risk-on (front-runs higher 10y yields);
    # falling = deflation / risk-off.
    gld = macro_data.get("GLD")
    cper = macro_data.get("CPER")
    if (gld is not None and cper is not None
            and len(gld) >= 21 and len(cper) >= 21):
        n = min(len(gld), len(cper))
        ratio = np.asarray(cper[-n:], dtype=float) / np.where(
            np.asarray(gld[-n:], dtype=float) == 0, np.nan, np.asarray(gld[-n:], dtype=float)
        )
        ratio = ratio[~np.isnan(ratio)]
        if len(ratio) >= 21:
            cg_score, cg_roc5, cg_roc20 = macro_direction_score(ratio)
            if cg_roc5 > 0.1:
                cg_dir = "RISING"
            elif cg_roc5 < -0.1:
                cg_dir = "FALLING"
            else:
                cg_dir = "FLAT"
            weather["COPPER_GOLD"] = {
                "score": cg_score, "roc5": cg_roc5, "roc20": cg_roc20,
                "direction": cg_dir,
            }

    return weather


def _format_macro_weather(weather_raw: dict) -> dict:
    """Format macro weather for the export JSON."""
    from datetime import date as _date

    tlt = weather_raw.get("TLT", {})
    uup = weather_raw.get("UUP", {})
    hyg = weather_raw.get("HYG", {})
    iwm = weather_raw.get("IWM", {})
    gld = weather_raw.get("GLD", {})
    cper = weather_raw.get("CPER", {})
    uso = weather_raw.get("USO", {})
    cg = weather_raw.get("COPPER_GOLD", {})

    parts: list[str] = []
    if tlt.get("direction") == "FALLING":
        parts.append("Rising rates")
    elif tlt.get("direction") == "RISING":
        parts.append("Falling rates")
    if uup.get("direction") == "RISING":
        parts.append("dollar bid")
    elif uup.get("direction") == "FALLING":
        parts.append("dollar weak")
    if hyg.get("direction") == "FALLING":
        parts.append("credit softening")
    elif hyg.get("direction") == "RISING":
        parts.append("credit tightening")
    if iwm.get("direction") == "FALLING":
        parts.append("narrow tape")
    elif iwm.get("direction") == "RISING":
        parts.append("broad tape")
    if gld.get("direction") == "RISING":
        parts.append("gold bid")
    elif gld.get("direction") == "FALLING":
        parts.append("gold soft")
    if cper.get("direction") == "RISING":
        parts.append("copper firm (growth)")
    elif cper.get("direction") == "FALLING":
        parts.append("copper weak (slowing)")
    if uso.get("direction") == "RISING":
        parts.append("oil rising (inflation)")
    elif uso.get("direction") == "FALLING":
        parts.append("oil easing")
    # The headline Druckenmiller tell goes last, as the regime verdict.
    if cg.get("direction") == "RISING":
        parts.append("copper/gold reflation tilt (risk-on)")
    elif cg.get("direction") == "FALLING":
        parts.append("copper/gold deflation tilt (risk-off)")

    desc = ", ".join(parts) + "." if parts else "No strong macro signal."

    return {
        "tlt_direction": tlt.get("direction", "FLAT"),
        "tlt_roc5": tlt.get("roc5", 0.0),
        "uup_direction": uup.get("direction", "FLAT"),
        "uup_roc5": uup.get("roc5", 0.0),
        "hyg_direction": hyg.get("direction", "FLAT"),
        "hyg_roc5": hyg.get("roc5", 0.0),
        "iwm_direction": iwm.get("direction", "FLAT"),
        "iwm_roc5": iwm.get("roc5", 0.0),
        "gld_direction": gld.get("direction", "FLAT"),
        "gld_roc5": gld.get("roc5", 0.0),
        "cper_direction": cper.get("direction", "FLAT"),
        "cper_roc5": cper.get("roc5", 0.0),
        "uso_direction": uso.get("direction", "FLAT"),
        "uso_roc5": uso.get("roc5", 0.0),
        "copper_gold_direction": cg.get("direction", "FLAT"),
        "copper_gold_roc5": cg.get("roc5", 0.0),
        "copper_gold_roc20": cg.get("roc20", 0.0),
        "regime_description": desc,
        "snapshot_date": str(_date.today()),
    }


# ── §3A.6 Intermarket brief (COB-driven Druckenmiller opener) ───────────

def _intermarket_instrument(closes) -> dict | None:
    """close / roc5 / roc20 / above_sma20 from a COB close array (>=21 bars)."""
    if closes is None:
        return None
    arr = np.asarray(closes, dtype=float)
    if len(arr) < 21:
        return None
    close = float(arr[-1])
    roc5 = (close / arr[-6] - 1) * 100 if arr[-6] != 0 else 0.0
    roc20 = (close / arr[-21] - 1) * 100 if arr[-21] != 0 else 0.0
    sma20 = float(np.mean(arr[-20:]))
    return {
        "close": round(close, 2),
        "roc5": round(float(roc5), 2),
        "roc20": round(float(roc20), 2),
        "above_sma20": bool(close > sma20),
    }


def compute_intermarket(macro_data: dict[str, np.ndarray],
                        spy_closes, as_of: str) -> dict:
    """Build the §3A.6 intermarket brief from COB closes.

    Inputs are the EOD close arrays already fetched for the macro overlay
    (UUP/TLT/HYG/IWM) plus SPY from the panel. 30-bar lookback. No live pull.
    AQE emits raw numbers (close, ROC5, ROC20, above_sma20 + the two spreads);
    it makes NO assessment — Druckenmiller reads these and provides the call.
    """
    _empty = {"close": None, "roc5": 0.0, "roc20": 0.0, "above_sma20": None}
    uup = _intermarket_instrument(macro_data.get("UUP")) or dict(_empty)
    tlt = _intermarket_instrument(macro_data.get("TLT")) or dict(_empty)
    hyg = _intermarket_instrument(macro_data.get("HYG")) or dict(_empty)
    iwm = _intermarket_instrument(macro_data.get("IWM"))
    spy = _intermarket_instrument(spy_closes)

    # Spreads are arithmetic conveniences, not judgments.
    hyg_tlt_spread = (round(hyg["roc5"] - tlt["roc5"], 2)
                      if hyg["close"] is not None and tlt["close"] is not None else 0.0)
    spy_roc20 = spy["roc20"] if spy else 0.0
    iwm_roc20 = iwm["roc20"] if iwm else 0.0
    spy_iwm_spread = round(spy_roc20 - iwm_roc20, 2) if (spy and iwm) else 0.0

    return {
        "as_of": as_of,
        "uup": uup,
        "tlt": tlt,
        "hyg": {**hyg, "hyg_tlt_spread": hyg_tlt_spread},
        "spy_iwm": {
            "spy_roc20": round(float(spy_roc20), 2),
            "iwm_roc20": round(float(iwm_roc20), 2),
            "spread": spy_iwm_spread,
        },
    }


# ── Combined entry gate (DSG-18 + DSG-19) ──────────────────────────

def sector_entry_gate(grade: str, rrg_quadrant: str,
                      macro_flag: str) -> tuple[str, str]:
    """Combined sector entry gate: grade + RRG + macro.

    Returns (gate, reason) where gate is PASS / WATCH / CAUTION / BLOCKED.
    """
    if grade == "AVOID":
        return "BLOCKED", "AVOID grade"
    if macro_flag == "HEADWIND" and rrg_quadrant == "LAGGING":
        return "BLOCKED", "HEADWIND macro + LAGGING RRG"
    if macro_flag == "HEADWIND":
        return "CAUTION", "Macro headwind"
    if rrg_quadrant in ("LAGGING", "WEAKENING") and macro_flag == "CAUTION":
        return "CAUTION", f"RRG {rrg_quadrant} + macro caution"
    if (grade in ("DEPLOY", "HOLD")
            and rrg_quadrant in ("LEADING", "IMPROVING")
            and macro_flag in ("TAILWIND", "NEUTRAL")):
        return "PASS", "Grade + RRG + macro aligned"
    return "WATCH", f"Grade {grade} / RRG {rrg_quadrant} / Macro {macro_flag}"


# ── Enrichment orchestrator ─────────────────────────────────────────

def enrich_sectors_intermarket(
    sector_grades: dict[str, dict],
    panel: pd.DataFrame,
    macro_data: dict[str, np.ndarray] | None = None,
) -> dict[str, dict]:
    """Add DSG-18 RRG + DSG-19 macro overlay to sector_grades (in-place).

    panel must contain SPY + sector ETF rows with [date, ticker, close].
    macro_data: {instrument: closes_array} for TLT/UUP/HYG/IWM/GLD/CPER/USO
    (optional). GLD/CPER/USO + the copper/gold ratio are the Druckenmiller
    commodity-complex overlay.
    """
    spy_data = panel.loc[panel["ticker"] == "SPY"].sort_values("date")
    if spy_data.empty:
        return sector_grades
    spy_closes = spy_data["close"].astype(float).to_numpy()

    macro_scores: dict[str, int] = {}
    macro_weather_raw: dict = {}
    if macro_data:
        macro_weather_raw = compute_macro_weather(macro_data)
        for inst in MACRO_INSTRUMENTS:
            macro_scores[inst] = macro_weather_raw.get(inst, {}).get("score", 0)

    for etf in GICS_ETFS:
        info = sector_grades.get(etf)
        if info is None:
            continue

        etf_data = panel.loc[panel["ticker"] == etf].sort_values("date")
        if not etf_data.empty:
            etf_closes = etf_data["close"].astype(float).to_numpy()
            rrg = compute_rrg(etf_closes, spy_closes)
        else:
            rrg = _rrg_no_data()

        info.update(rrg)
        info["rrg_grade_override"] = rrg_grade_override(
            info.get("grade", "WATCH"), rrg.get("rrg_quadrant", "NO_DATA")
        )

        if macro_data:
            hw_score, hw_flag = compute_macro_headwind(etf, macro_scores)
            info["macro_headwind_score"] = hw_score
            info["macro_headwind_flag"] = hw_flag
        else:
            info["macro_headwind_score"] = None
            info["macro_headwind_flag"] = "NO_DATA"

        gate, reason = sector_entry_gate(
            info.get("grade", "WATCH"),
            rrg.get("rrg_quadrant", "NO_DATA"),
            info.get("macro_headwind_flag", "NEUTRAL"),
        )
        info["entry_gate"] = gate
        info["entry_gate_reason"] = reason

    sector_grades["_macro_weather"] = _format_macro_weather(macro_weather_raw)
    return sector_grades


def save_intermarket_cache(sector_grades: dict[str, dict], run_date) -> None:
    """Persist enriched SRM + macro weather to a small JSON cache."""
    import json
    from pathlib import Path

    cache_path = Path(__file__).resolve().parents[2] / "data" / "srm_intermarket_cache.json"
    cache: dict = {"date": str(run_date), "macro_weather": {},
                   "intermarket": {}, "sectors": {}}
    mw = sector_grades.get("_macro_weather")
    if mw:
        cache["macro_weather"] = mw
    im = sector_grades.get("_intermarket")
    if im:
        cache["intermarket"] = im
    for etf in GICS_ETFS:
        info = sector_grades.get(etf)
        if info is None:
            continue
        cache["sectors"][etf] = {
            k: v for k, v in info.items()
            if k in (
                "rrg_rs_ratio", "rrg_rs_momentum", "rrg_quadrant",
                "rrg_direction", "rrg_grade_override",
                "macro_headwind_score", "macro_headwind_flag",
                "entry_gate", "entry_gate_reason",
            )
        }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:
        pass


def load_intermarket_cache() -> dict | None:
    """Load the DSG-18/19 cache written by the orchestrator."""
    import json
    from pathlib import Path

    cache_path = Path(__file__).resolve().parents[2] / "data" / "srm_intermarket_cache.json"
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
