"""QS engine — scores the eligible universe and produces the daily rows.

The middle of the machine. `qs_fields` supplies the inputs AQE lacked,
`qs_spec` holds the frozen constants, `qs_store` holds the memory, `qs_card`
renders the output. This module is what turns a day's scored universe into QS
readings.

Per name, per night:
  1. LENSES      15 measurements -> 5 cross-sectional 0-10 scores. MOMENTUM is
                 inverted, so quiet momentum scores high.
  2. RECIPES     count how many of the 40 frozen rules the name satisfies.
  3. VETOES      5 strike-out rules; a hit forces conviction 0.
  4. PERSIST     how many of the prior 5 sessions also qualified (from store).
  5. STATE       EARLY / READY / READY+.
  6. PROBABILITY (hits, lens, persist) -> calibration bucket -> p, analogues,
                 typical days, typical dip.
  7. CONVICTION  0-5, from p and how far it beats THIS market's own base rate.
  8. LEVELS      +/-2xATR14 objective — the yardstick p was measured against.
  9. WHY         plain English, from the rules that actually matched.

FIDELITY IS THE WHOLE GAME HERE. Every comparison, rounding step and boundary
below is matched to the reference implementation, because the frozen
calibration was measured through exactly this arithmetic. A deviation does not
raise an error — it returns a plausible number that means something other than
what it claims. The specific traps, each of which bites silently:

  * a missing or NaN field makes a condition FALSE, never True
  * `between` is right-inclusive: lo < x <= hi
  * recipe_hits counts all 40 entries, including the 8 duplicate pairs
  * lens scores round to 1dp BEFORE lens_total averages them, and lens_total
    rounds again
  * the lens band uses strict `<`, so lens_total 6.0 is "6-7", not "5-6"
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.engines import qs_spec as S

# Plain-English phrase per (field, band) — daily_scan.py:206-244, transcribed.
# band: "HI" for a `gt` condition, "LO" for `le`, "MID" for `between`.
PHRASE: dict[tuple[str, str], str] = {
    ("en_pos50", "HI"): "sitting near its highs",
    ("ms_pos_score", "HI"): "sitting near its highs",
    ("vp_position_score", "HI"): "strong position in range",
    ("en_pos50", "LO"): "low in its range",
    ("roc_zscore", "LO"): "momentum still quiet",
    ("abs_mom_score", "LO"): "momentum still quiet",
    ("rel_mom_score", "LO"): "not yet outrunning the market",
    ("excess_return", "LO"): "not yet outrunning the market",
    ("bq_range_tight", "HI"): "range tightening",
    ("bq_ema_conv", "HI"): "MAs converged (coiled)",
    ("bq_ema_conv", "LO"): "MAs fanning out",
    ("squeeze_score", "HI"): "volatility squeeze on",
    ("bq_base_days", "MID"): "base maturing",
    ("bq_base_dur", "MID"): "base maturing",
    ("bq_base_dur", "LO"): "fresh young base",
    ("base_days", "LO"): "fresh young base",
    ("base_days", "MID"): "base maturing",
    ("pr_ma_score", "HI"): "MA stack aligned",
    ("k39_value", "MID"): "weekly not overbought",
    ("fip_quality", "HI"): "smooth price path",
    ("en_trend_bars", "LO"): "trend just starting",
    ("hl_trend_bars", "LO"): "trend just starting",
    ("en_trend_bars", "MID"): "trend establishing",
    ("elder_score", "HI"): "Elder impulse green",
    ("rs_accel_score", "LO"): "RS not yet accelerating",
    ("rs_spy_score", "HI"): "beating SPY",
    ("rs_spy_score", "MID"): "tracking SPY",
    ("structure_100", "HI"): "strong structure",
    ("accum_score", "HI"): "accumulation underneath",
    ("cmf", "LO"): "money flow not yet crowded",
    ("flow_score", "LO"): "flow not yet crowded",
    ("resist_score", "LO"): "room overhead",
    ("mp_accel", "HI"): "momentum starting to build",
    ("energy_100", "HI"): "energy building",
    ("pr_ret_12m", "LO"): "12m return still modest",
    ("momentum_composite", "MID"): "mid-pack momentum",
    ("sc_position", "MID"): "mid-pack position score",
}
MAX_WHY_PHRASES = 4      # daily_scan.py:260


# --------------------------------------------------------------- conditions

def cond_mask(df: pd.DataFrame, c: dict) -> pd.Series:
    """Boolean mask for one recipe/veto condition. daily_scan.py:45-56.

    An ABSENT column yields all-False, and a NaN value compares False. Both
    mean the condition fails, never passes. That is conservative for recipes
    (the rule simply does not fire) but fail-OPEN for vetoes, so callers
    evaluating vetoes should also ask `unevaluable_mask` and surface the gap.
    """
    f = c["field"]
    if f not in df.columns:
        return pd.Series(False, index=df.index)
    s = df[f]
    op = c["op"]
    if op == "eq":
        return s.astype(str) == c["value"]
    if op == "le":
        return s <= c["value"]
    if op == "gt":
        return s > c["value"]
    return s.between(c["lo"], c["hi"], inclusive=S.BETWEEN_INCLUSIVE)


def unevaluable_mask(df: pd.DataFrame, conditions: list[dict]) -> pd.Series:
    """True where a condition could not be evaluated at all (missing/NaN input).

    Distinct from "evaluated and failed". Used only to flag vetoes — it never
    changes an outcome, so conviction stays identical to the reference.
    """
    out = pd.Series(False, index=df.index)
    for c in conditions:
        f = c["field"]
        out = out | (df[f].isna() if f in df.columns
                     else pd.Series(True, index=df.index))
    return out


def count_recipe_hits(df: pd.DataFrame, recipes: list[dict]) -> np.ndarray:
    """recipe_hits — daily_scan.py:137-143.

    Counts EVERY entry in the book (40), NOT unique condition-sets (32). Eight
    are exact duplicates with reordered conditions and are counted twice by
    design; the calibration's hit bands were fitted on this total. Deduping
    would push names down a band and understate every probability.
    """
    hits = np.zeros(len(df), dtype=int)
    for r in recipes:
        m = np.ones(len(df), dtype=bool)
        for c in r["conditions"]:
            m &= cond_mask(df, c).to_numpy()
        hits += m
    return hits


def matched_recipes(df: pd.DataFrame, recipes: list[dict]) -> list[list[int]]:
    """Indices of the recipes each row satisfies — for `why` and audit."""
    masks = []
    for r in recipes:
        m = np.ones(len(df), dtype=bool)
        for c in r["conditions"]:
            m &= cond_mask(df, c).to_numpy()
        masks.append(m)
    if not masks:
        return [[] for _ in range(len(df))]
    stack = np.vstack(masks)
    return [list(np.flatnonzero(stack[:, i])) for i in range(len(df))]


def evaluate_vetoes(df: pd.DataFrame, vetoes: list[dict]
                    ) -> tuple[list[list[str]], list[list[str]]]:
    """(fired, unevaluable) veto names per row.

    Vectorised over rows — the reference loops per row, which is O(rows x
    vetoes x conditions) and far too slow at ~900 names, but the semantics are
    identical: every condition must hold for the veto to fire.
    """
    fired = [[] for _ in range(len(df))]
    ungrad = [[] for _ in range(len(df))]
    for vt in vetoes:
        m = np.ones(len(df), dtype=bool)
        for c in vt["conditions"]:
            m &= cond_mask(df, c).to_numpy()
        u = unevaluable_mask(df, vt["conditions"]).to_numpy()
        for i in np.flatnonzero(m):
            fired[i].append(vt["name"])
        if S.FLAG_UNEVALUABLE_VETOES:
            for i in np.flatnonzero(u & ~m):
                ungrad[i].append(vt["name"])
    return fired, ungrad


def awareness_notes(df: pd.DataFrame, patterns: list[dict]) -> list[str]:
    """Commentary only. Never counted in hits, conviction, ranking or p."""
    flags = []
    for r in patterns:
        m = np.ones(len(df), dtype=bool)
        for c in r["conditions"]:
            m &= cond_mask(df, c).to_numpy()
        flags.append((r.get("plain", r["name"]), m))
    return ["; ".join(p for p, m in flags if m[i]) for i in range(len(df))]


# -------------------------------------------------------------------- lenses

def score_lenses(df: pd.DataFrame) -> pd.DataFrame:
    """Add L_<LENS> columns and lens_total. daily_scan.py:304-313.

    Each component becomes its cross-sectional percentile across the frame
    (which must be TODAY'S ELIGIBLE SET — that population is what the
    calibration was measured on). Sign -1 components are inverted, so a low
    raw value scores high.

    A component missing from the frame is skipped rather than treated as zero,
    and the lens averages whatever remains — matching the reference. That is
    silently degrading, so `lens_components_used` records how many of the 15
    actually contributed.
    """
    out = df.copy()
    used = np.zeros(len(df), dtype=int)
    cols = []
    for lens, flds in S.LENSES.items():
        parts = []
        for f, sign in flds:
            if f in out.columns:
                p = out[f].rank(pct=True)
                parts.append(p if sign > 0 else 1 - p)
                used += out[f].notna().to_numpy().astype(int)
        col = f"L_{lens}"
        out[col] = (pd.concat(parts, axis=1).mean(axis=1) * 10
                    ).round(S.LENS_SCORE_DP) if parts else np.nan
        cols.append(col)
    out["lens_total"] = out[cols].mean(axis=1).round(S.LENS_TOTAL_DP)
    out["lens_components_used"] = used
    return out


# -------------------------------------------------------------- probability

def lookup_probability(hits: int, lens_total: float, persist: int,
                       calibration: dict) -> dict:
    """Calibration bucket -> p and its path stats. daily_scan.py:325-335.

    Prefers the 3-D (hits x lens x persist) cell and falls back to the 2-D
    (hits x lens) table when that cell was too thin to publish. The 2-D table
    carries NO days_median / mae_atr_median, so those come back None and the
    card omits them — the reference does the same, and an omitted number is
    honest where an invented one is not.

    `p` is p_train and `n_analogues` is n_train. p_test is context, shown
    beside p but never used for conviction.
    """
    if lens_total is None or (isinstance(lens_total, float) and np.isnan(lens_total)):
        return {"p": None, "p_test": None, "n_analogues": 0, "bucket": None,
                "bucket_kind": None, "days_median": None, "mae_atr_median": None}
    hb, lb, pb = (S.hits_band(int(hits)), S.lens_band(float(lens_total)),
                  S.persist_band(int(persist)))
    k3, k2 = f"{hb}|{lb}|{pb}", f"{hb}|{lb}"
    b = (calibration.get("buckets_persist") or {}).get(k3)
    key, kind = k3, "3-D"
    if not b:
        b = (calibration.get("buckets") or {}).get(k2)
        key, kind = k2, "2-D fallback"
    if not b:
        return {"p": None, "p_test": None, "n_analogues": 0, "bucket": k3,
                "bucket_kind": "missing", "days_median": None,
                "mae_atr_median": None}
    return {"p": b.get("p_train"), "p_test": b.get("p_test"),
            "n_analogues": b.get("n_train") or 0, "bucket": key,
            "bucket_kind": kind, "days_median": b.get("days_median"),
            "mae_atr_median": b.get("mae_atr_median")}


def why_phrases(recipes: list[dict], matched_idx: list[int]) -> str:
    """Plain English from the rules that actually matched. daily_scan.py:246-260."""
    phrases: list[str] = []
    for i in matched_idx:
        for c in recipes[i]["conditions"]:
            band = ("HI" if c["op"] == "gt" else
                    "LO" if c["op"] == "le" else "MID")
            p = PHRASE.get((c["field"], band))
            if p and p not in phrases:
                phrases.append(p)
    return ", ".join(phrases[:MAX_WHY_PHRASES])


# ----------------------------------------------------------------- the run

def compute_awake(df: pd.DataFrame) -> np.ndarray:
    """abs_mom > 0 OR rel_mom > 0 OR impulse GREEN. daily_scan.py:170-171."""
    z = pd.Series(0.0, index=df.index)
    a = (df["abs_mom_score"] if "abs_mom_score" in df.columns else z) > 0
    r = (df["rel_mom_score"] if "rel_mom_score" in df.columns else z) > 0
    if "impulse_state" in df.columns:
        g = df["impulse_state"].astype(str) == S.AWAKE_IMPULSE_VALUE
    else:
        g = pd.Series(False, index=df.index)
    return (a | r | g).to_numpy()


def run_qs(day: pd.DataFrame, book: dict, calibration: dict,
           regime: dict, persist_map: dict[str, int] | None = None,
           eligible: bool = True) -> list[dict]:
    """Score one day's frame. `day` must already be TODAY'S ELIGIBLE SET.

    `regime` is the recipe-book regime entry for today's cell, plus its code:
    {"cell", "desc", "stance", "base_rate_test"}. A regime with no measured
    base rate falls back to the global test base (daily_scan.py:363) rather
    than leaving conviction undefined.

    Returns one dict per row, ready to nest under `qs` on a daily_list record.
    """
    if day is None or day.empty:
        return []
    persist_map = persist_map or {}
    recipes = book.get("recipes") or []
    day = score_lenses(day)

    hits = count_recipe_hits(day, recipes)
    matched = matched_recipes(day, recipes)
    fired, ungraded = evaluate_vetoes(day, book.get("vetoes") or [])
    aware = awareness_notes(
        day, (book.get("awareness_notes") or {}).get("patterns") or [])
    awake = compute_awake(day)

    cell_base = regime.get("base_rate_test") or S.DEFAULT_CELL_BASE_RATE
    stance = regime.get("stance", "NEUTRAL")

    tickers = day["ticker"].tolist()
    closes = (day["close"] if "close" in day.columns
              else pd.Series(np.nan, index=day.index)).tolist()
    atrs = (day["atr14"] if "atr14" in day.columns
            else pd.Series(np.nan, index=day.index)).tolist()

    rows = []
    for i, tk in enumerate(tickers):
        h = int(hits[i])
        persist = int(persist_map.get(tk, 0))
        lt = day["lens_total"].iloc[i]
        lt = None if pd.isna(lt) else float(lt)
        prob = lookup_probability(h, lt, persist, calibration)

        p_disp = (None if prob["p"] is None
                  else round(float(prob["p"]), S.CONVICTION_P_DP))
        vetoed = bool(fired[i])
        conv = S.conviction(p_disp, cell_base, vetoed)
        state = S.qs_state(h, persist, bool(awake[i]))

        close, atr = closes[i], atrs[i]
        has_lv = pd.notna(close) and pd.notna(atr)
        atr_pct = (atr / close * 100) if has_lv and close else None
        mae = prob["mae_atr_median"]

        lens = {k.lower(): (None if pd.isna(day[f"L_{k}"].iloc[i])
                            else float(day[f"L_{k}"].iloc[i]))
                for k in S.LENSES}
        comps = {f: (None if f not in day.columns or pd.isna(day[f].iloc[i])
                     else float(day[f].iloc[i]) if not isinstance(
                         day[f].iloc[i], str) else day[f].iloc[i])
                 for f in S.CARD_COMPONENTS if f in day.columns}

        high_prob = bool(
            stance not in S.HIGH_PROB_BLOCKED_STANCES
            and h >= S.HIGH_PROB_MIN_HITS
            and (p_disp or 0) >= S.HIGH_PROB_MIN_P
            and prob["n_analogues"] >= S.HIGH_PROB_MIN_ANALOGUES
            and not vetoed
            and (lens.get("structure") or 0) >= S.HIGH_PROB_MIN_LENS
            and (lens.get("momentum") or 0) >= S.HIGH_PROB_MIN_LENS)

        rows.append({
            "ticker": tk,
            "signal": S.signal_label(h, vetoed),
            "conviction": conv, "conviction_word": S.CONVICTION_WORD[conv],
            "high_probability": high_prob,
            "eligible": bool(eligible),
            "state": {"code": state, "plain": S.STATE_DESC.get(state, ""),
                      "test_hit_rate": S.STATE_TEST_RATE.get(state),
                      "awake": bool(awake[i])},
            "odds": {
                "p": p_disp, "p_test": prob["p_test"],
                "n_analogues": prob["n_analogues"],
                "market_avg": round(cell_base, 3),
                "edge": (None if p_disp is None
                         else round(p_disp - cell_base, 3)),
                "bucket": prob["bucket"], "bucket_kind": prob["bucket_kind"],
                "refers_to": calibration.get("outcome",
                                             "touch +2*ATR14 within 20 sessions"),
                "extrapolated": not eligible,
            },
            "objective": ({
                "now": round(float(close), 2),
                "target_2atr": round(float(close + 2 * atr), 2),
                "target_pct": round(float(2 * atr / close * 100), 1),
                "give_up_2atr": round(float(close - 2 * atr), 2),
                "atr_pct": round(float(atr_pct), 2),
            } if has_lv and close else {}),
            "path": ({} if prob["days_median"] is None and mae is None else {
                "usual_days": prob["days_median"],
                "typical_dip_pct": (None if mae is None or atr_pct is None
                                    else round(abs(mae) * atr_pct, 1)),
                "mae_atr_median": mae,
            }),
            "engine": {
                "recipe_hits": h, "qs_persist": persist, "lens_total": lt,
                "lens": lens, "components": comps,
                "lens_components_used": int(day["lens_components_used"].iloc[i]),
                "matched_recipes": [recipes[j]["name"] for j in matched[i]],
            },
            "awareness_notes": aware[i],
            "vetoes": fired[i],
            "unevaluable_vetoes": ungraded[i],
            "why": why_phrases(recipes, matched[i]),
            "versions": {
                "recipe_book": book.get("generated") or book.get("built"),
                "calibration": calibration.get("version"),
            },
        })

    _assign_ranks(rows, stance)
    return rows


def _assign_ranks(rows: list[dict], stance: str) -> None:
    """qs.rank over the emittable pool, and on_qs membership.

    Two separate rules, both from the reference:
      qs_rank  — hits >= 1, no vetoes, sorted by SORT_KEYS, cut at 50 (:381-386)
      emitted  — hits >= 2 AND (conviction >= 2 OR vetoed), empty in
                 STAND_DOWN (:390-391). Vetoed names ARE emitted so the
                 committee sees what was struck; conviction 1 is suppressed
                 because it has no edge over today's own market.
    """
    stand_down = stance == S.STAND_DOWN_STANCE
    pool = [r for r in rows
            if r["engine"]["recipe_hits"] >= S.QS_RANK_MIN_HITS and not r["vetoes"]]
    pool.sort(key=lambda r: (r["engine"]["recipe_hits"], r["odds"]["p"] or 0,
                             r["engine"]["lens_total"] or 0), reverse=True)
    for r in rows:
        r["rank"] = None
    for i, r in enumerate(pool[:S.QS_RANK_TOP_N], 1):
        r["rank"] = i
    for r in rows:
        r["emitted"] = bool(
            not stand_down
            and r["engine"]["recipe_hits"] >= S.SHEET_MIN_HITS
            and (r["conviction"] >= 2 or r["conviction"] == 0))
