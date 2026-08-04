"""AEGIS IDEA SCANNER — the production scan-and-score sheet (Phase 1: entries).

Assembles every validated layer from the research programme:

  1. REGIME    numerical market cell -> plain English + stance. T3V1 stands the
               book down; T2V2 is the measured sweet spot.
  2. RANKING   slow leadership: rs_consist (holdout-validated) + Clenow
               adj_slope. This orders the list.
  3. RECIPES   combo hits against the frozen recipe book (quiet-strength
               family: structure HIGH x momentum QUIET x compression).
               More hits = stronger profile. Measured: >=3 hits ~ 65% one-way
               +2ATR rate vs 55% base.
  4. VETOES    strike-out flags (fading laggard, volume-without-quality,
               jumpy path, earnings inside hold, exhaustion footprint).
  5. LEVELS    entry reference, +2ATR objective (the success yardstick),
               -2ATR adversity marker, ATR%.

The sheet DECIDES NOTHING. It ranks, scores, flags and explains; the PM
deliberates. Phase 2 (exit / scale-out / partial-TP scanning) is next.

  python daily_scan.py                     latest common date
  python daily_scan.py --date 2026-07-24   specific date
  python daily_scan.py --top 25            rows to print
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "quant"))

import book_factors as BF
import ledger as LG
import regime as RG
import verifier as V

ROOT = os.path.dirname(os.path.abspath(__file__))


def cond_mask(df: pd.DataFrame, c: dict) -> pd.Series:
    f = c["field"]
    if f not in df.columns:
        return pd.Series(False, index=df.index)
    s = df[f]
    if c["op"] == "eq":
        return s.astype(str) == c["value"]
    if c["op"] == "le":
        return s <= c["value"]
    if c["op"] == "gt":
        return s > c["value"]
    return s.between(c["lo"], c["hi"], inclusive="right")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()

    book = json.load(open(os.path.join(ROOT, "recipe_book.json")))
    cfg = LG.get_config(LG.connect())
    panel = V.build_panel(cfg["data_path"])
    st = RG.macro_state(panel)
    sc = pd.read_parquet(os.path.join(ROOT, "scores_daily.parquet"))
    sc["date"] = pd.to_datetime(sc["date"])

    dates = pd.to_datetime(panel["dates"])
    asof = pd.Timestamp(a.date) if a.date else min(dates.max(), sc.date.max())
    di = int(np.where(dates == asof)[0][0])
    cell = st["cell"][di]
    reg = book["regimes"].get(cell, {})
    day = sc[sc.date == asof].copy()

    # ---- ranking: rs_consist (vs EW universe) and Clenow adj_slope ---------
    cl, vol = panel["close"], panel["volume"]
    with np.errstate(all="ignore"):
        rets = np.full_like(cl, np.nan)
        rets[1:] = cl[1:] / cl[:-1] - 1.0
        el = panel.get("eligible")
        idx_ret = np.nan_to_num(np.nanmean(
            np.where(el, rets, np.nan) if el is not None else rets, axis=1))
        beat = (rets > idx_ret[:, None]).astype(float)
        rs = pd.DataFrame(beat).rolling(126, min_periods=126).mean().to_numpy()
    tcol = panel["tcol"]
    day["rs_consist"] = [rs[di, tcol[t]] if t in tcol else np.nan
                         for t in day.ticker]
    day["rs_rank"] = day.rs_consist.rank(pct=True)
    bfp = os.path.join(ROOT, "book_factors.parquet")
    if os.path.exists(bfp):
        bf = pd.read_parquet(bfp)
        bf["date"] = pd.to_datetime(bf["date"])
        day = day.merge(bf[bf.date == asof][["ticker", "adj_slope", "r2_90"]],
                        on="ticker", how="left")

    # ---- sector-relative fields (raw OHLCV + universe sector map) ----------
    # Needed by the sector_relative_qs recipe family (book v2). ret20 and
    # rank_in_sector are derived exactly as in the research panel
    # (longlist_lab): 20d %-change, then pct-rank within (date, sector).
    import sqlite3 as _sq
    r20 = np.full_like(cl, np.nan)
    r20[20:] = (cl[20:] / cl[:-20] - 1.0) * 100
    day["ret20"] = [r20[di, tcol[t]] if t in tcol else np.nan for t in day.ticker]
    try:
        _uc = _sq.connect("file:" + os.path.join(ROOT, "universe.db") + "?mode=ro",
                          uri=True)
        smap = dict(_uc.execute(
            "SELECT symbol, sector FROM constituents").fetchall())
        _uc.close()
    except Exception:
        smap = {}
    day["sector"] = day.ticker.map(smap)
    day["rank_in_sector"] = (day.groupby("sector")["ret20"]
                             .rank(pct=True))

    # ---- awareness notes (PM: context, not signal) --------------------------
    # Evaluated and shown as commentary only. Never counted in recipe_hits,
    # conviction, ranking or probability.
    aw_flags = []
    for r in book.get("awareness_notes", {}).get("patterns", []):
        m = np.ones(len(day), dtype=bool)
        for c in r["conditions"]:
            m &= cond_mask(day, c).to_numpy()
        aw_flags.append((r.get("plain", r["name"]), m))
    day["awareness"] = [
        "; ".join(p for p, m in aw_flags if m[i]) for i in range(len(day))]

    # ---- recipes and vetoes -------------------------------------------------
    # recipe_hits counts EVERY entry in book["recipes"] (40), not unique
    # condition-sets (32 -- 8 are exact duplicates by design tradeoff, see
    # book["recipe_hits_rule"]). Do not dedupe: calibration.json's hit bands
    # were built against this exact count.
    hits = np.zeros(len(day), dtype=int)
    for r in book["recipes"]:
        m = np.ones(len(day), dtype=bool)
        for c in r["conditions"]:
            m &= cond_mask(day, c).to_numpy()
        hits += m
    day["recipe_hits"] = hits

    # ---- QS PERSISTENCE ----------------------------------------------------
    # How many of the prior 5 sessions ALSO qualified as QS. Measured to be an
    # independent conviction dimension: inside identical hits x lens buckets it
    # still adds +0.06..+0.16 to the hit rate, in train AND test. A name that
    # has quietly held the profile for days is worth more than one that arrived
    # this morning.
    PERSIST_WINDOW = 5
    prior_dates = [x for x in np.sort(sc.date.unique()) if x < asof][-PERSIST_WINDOW:]
    hist = sc[sc.date.isin(prior_dates)].copy()
    hh = np.zeros(len(hist), dtype=int)
    for r in book["recipes"]:
        m = np.ones(len(hist), dtype=bool)
        for c in r["conditions"]:
            m &= cond_mask(hist, c).to_numpy()
        hh += m
    hist["qs_day"] = (hh >= 3).astype(int)
    day["qs_persist"] = (day.ticker.map(hist.groupby("ticker").qs_day.sum())
                         .fillna(0).astype(int))

    # ---- TWO SIGNAL TYPES --------------------------------------------------
    # EARLY = QS profile present, momentum still asleep -> get on the list.
    # READY = QS held for days AND momentum now waking   -> act.
    # Measured (test window): EARLY 64.8%, READY 69.4%, READY+ (also QS today)
    # 73.1%, vs 54.8% base. Momentum awake with NO QS history = 54.7% on
    # 177k samples -- indistinguishable from a dart, which is the whole point.
    awake = ((day.get("abs_mom_score", 0) > 0) | (day.get("rel_mom_score", 0) > 0)
             | (day.get("impulse_state", "").astype(str) == "GREEN"))
    day["mom_awake"] = awake
    day["qs_state"] = np.where(
        (day.qs_persist >= 3) & awake, "READY",
        np.where((day.recipe_hits >= 3) & ~awake, "EARLY", ""))
    # plain English, printed next to the tag -- nobody should have to decode
    # "READY" from a glossary while reading a card.
    STATE_DESC = {
        "EARLY": "quietly strong, hasn't started moving yet",
        "READY": "was quietly strong all week, now starting to move",
        "": "",
    }
    day["state_desc"] = day.qs_state.map(STATE_DESC).fillna("")

    veto_flags = []
    for _, row in day.iterrows():
        flags = []
        for vt in book["vetoes"]:
            if all(cond_mask(day.loc[[row.name]], c).iloc[0]
                   for c in vt["conditions"]):
                flags.append(vt["name"])
        veto_flags.append("; ".join(flags))
    day["vetoes"] = veto_flags

    # ---- levels -------------------------------------------------------------
    atr = panel["atr"]
    day["atr14_live"] = [atr[di, tcol[t]] if t in tcol else np.nan
                         for t in day.ticker]
    day["ref_close"] = [cl[di, tcol[t]] if t in tcol else np.nan
                        for t in day.ticker]
    day["obj_2atr"] = day.ref_close + 2 * day.atr14_live
    day["adverse_2atr"] = day.ref_close - 2 * day.atr14_live
    day["atr_pct"] = day.atr14_live / day.ref_close * 100

    # ---- plain-English rationale per name ----------------------------------
    PHRASE = {
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

    def rationale_for(row_idx):
        phrases = []
        for r in book["recipes"]:
            ok = all(cond_mask(day.loc[[row_idx]], c).iloc[0]
                     for c in r["conditions"])
            if not ok:
                continue
            for c in r["conditions"]:
                f = c["field"]
                band = ("HI" if c["op"] == "gt" else
                        "LO" if c["op"] == "le" else "MID")
                p = PHRASE.get((f, band))
                if p and p not in phrases:
                    phrases.append(p)
        return ", ".join(phrases[:4])

    # ---- output -------------------------------------------------------------
    stance = reg.get("stance", "NEUTRAL")
    print(f"\n{'=' * 86}")
    print(f"AEGIS IDEA SCAN — {asof.date()}   (Phase 1: entries)")
    print(f"{'=' * 86}")
    ACTION = {
        "PRESS": "Good conditions. Act on strong ideas.",
        "PRESS_EXPECT_WHIPSAW": "Conditions work, but expect violent swings.",
        "NEUTRAL": "Ordinary conditions. Normal selectivity.",
        "DEFENSIVE": "Poor conditions. Only the very best ideas.",
        "STAND_DOWN": "No edge in this market. Manage open positions only.",
    }
    br = reg.get("base_rate_test")
    print(f"THE MARKET TODAY: {reg.get('desc', 'unclassified')}")
    if br:
        print(f"  In this kind of market the average stock reaches its target "
              f"{br:.0%} of the time.")
    print(f"  {ACTION.get(stance, 'Normal selectivity.')}")
    print(f"  (regime code {cell} / {stance} - for the record)")
    print()

    # ---- LENS SCORECARDS ----------------------------------------------------
    # Each lens = a question about the stock, scored 0-10 from today's
    # cross-sectional percentiles, ORIENTED to the validated winning profile
    # (structure HIGH, coil TIGHT, momentum QUIET, leadership PRESENT, risk CLEAR).
    LENSES = {
        "STRUCTURE":  {"q": "where does it sit in its own range?",
                       "flds": [("en_pos50", +1), ("ms_pos_score", +1),
                                ("structure_100", +1)]},
        "COIL":       {"q": "is it compressed / ready?",
                       "flds": [("bq_range_tight", +1), ("bq_ema_conv", +1),
                                ("squeeze_score", +1)]},
        "MOMENTUM":   {"q": "is momentum still QUIET (good) or spent?",
                       "flds": [("roc_zscore", -1), ("abs_mom_score", -1),
                                ("rel_mom_score", -1)]},
        "FLOW":       {"q": "is money quietly arriving?",
                       "flds": [("accum_score", +1), ("cmf", +1),
                                ("mfi", +1)]},
        "LEADERSHIP": {"q": "does it beat the market persistently?",
                       "flds": [("rs_consist", +1), ("rs_vs_spy", +1),
                                ("elder_score", +1)]},
    }
    for lens, spec in LENSES.items():
        parts = []
        for f, sign in spec["flds"]:
            if f in day.columns:
                p = day[f].rank(pct=True)
                parts.append(p if sign > 0 else 1 - p)
        day["L_" + lens] = (pd.concat(parts, axis=1).mean(axis=1) * 10).round(1) \
            if parts else np.nan
    lens_cols = ["L_" + k for k in LENSES]
    day["lens_total"] = day[lens_cols].mean(axis=1).round(1)

    def word(v):
        return ("***" if v >= 7.5 else " **" if v >= 6 else "  *" if v >= 5 else "   ")

    # ---- calibrated probability from historical analogues -------------------
    calp, cal3 = {}, {}
    cal_path = os.path.join(ROOT, "calibration.json")
    if os.path.exists(cal_path):
        _c = json.load(open(cal_path))
        calp, cal3 = _c["buckets"], _c.get("buckets_persist", {})

    def est_p(hits, lens_total, persist=0):
        hb = "0" if hits == 0 else "1-2" if hits <= 2 else "3-7" if hits <= 7 else "8+"
        lb = ("<5" if lens_total < 5 else "5-6" if lens_total < 6
              else "6-7" if lens_total < 7 else "7+")
        pb = "0-1" if persist <= 1 else "2-3" if persist <= 3 else "4-5"
        # persistence-aware bucket preferred; fall back to the 2-D table when
        # that cell is too thin to be trusted.
        b = cal3.get(f"{hb}|{lb}|{pb}") or calp.get(f"{hb}|{lb}")
        return ((b["p_train"], b.get("p_test"), b["n_train"],
                 b.get("days_median"), b.get("mae_atr_median")) if b
                else (None, None, None, None, None))

    # Scored on the WHOLE universe, once. The printed sheet, the CSV, the JSON
    # and the TradingView export are all views of `day` -- there is no second
    # calculation anywhere, so they cannot disagree.
    pn = [est_p(int(h), lt, int(pz)) for h, lt, pz
          in zip(day.recipe_hits, day.lens_total, day.qs_persist)]
    day["est_p"] = [x[0] if x[0] else np.nan for x in pn]
    day["est_p_test"] = [x[1] if x[1] else np.nan for x in pn]
    day["n_analogues"] = [x[2] if x[2] else 0 for x in pn]
    day["days_median"] = [x[3] if x[3] else np.nan for x in pn]
    day["mae_atr_median"] = [x[4] if x[4] else np.nan for x in pn]
    day["signal"] = day.recipe_hits.map(
        lambda h: "STRONG" if h >= 8 else "GOOD" if h >= 3
        else "WATCH" if h >= 1 else "NONE")
    day.loc[day.vetoes != "", "signal"] = "SKIP"
    stance_ok = stance not in ("STAND_DOWN", "DEFENSIVE")
    day["high_probability"] = (
        stance_ok & (day.recipe_hits >= 3) & (day.est_p >= 0.60)
        & (day.n_analogues >= 300) & (day.vetoes == "")
        & (day.L_STRUCTURE >= 6) & (day.L_MOMENTUM >= 6))

    # ---- CONVICTION 1-5 ----------------------------------------------------
    # One number the PM can act on. Built from the two things that actually
    # decide quality: the calibrated probability, and how much that beats the
    # market it is sitting in. Regime is folded in HERE (as a subtraction),
    # never multiplied into the signal -- a good market must not flatter a
    # mediocre name. A veto forces 0.
    cell_base = reg.get("base_rate_test") or 0.548
    # Band on the ROUNDED probability -- the card shows "60%", so a name
    # displaying 60% must score as 60%, not as the 0.596 behind it.
    p_disp = day.est_p.round(2)
    edge = p_disp - cell_base
    conv = np.select(
        [(p_disp >= 0.65) & (edge >= 0.15),
         (p_disp >= 0.60) & (edge >= 0.10),
         (p_disp >= 0.55) & (edge >= 0.05),
         edge > 0],
        [5, 4, 3, 2], default=1)
    day["conviction"] = np.where(day.vetoes != "", 0, conv)
    day["conviction_word"] = day.conviction.map(
        {0: "vetoed", 1: "none", 2: "low", 3: "moderate", 4: "high",
         5: "very high"})
    day["market_base"] = cell_base

    # QS-50 ranking rule (spec STEP 7): drop no-hit and vetoed names, then
    # recipe_hits DESC -> est_P DESC -> lens_total DESC, cut at 50.
    pool = day[(day.recipe_hits >= 1) & (day.vetoes == "")].sort_values(
        ["recipe_hits", "est_p", "lens_total"], ascending=False)
    day["qs_rank"] = np.nan
    sel = pool.index[:50]
    day.loc[sel, "qs_rank"] = np.arange(1, len(sel) + 1)

    # PM rule: "if there's no edge I don't want to see it." Conviction < 2
    # (at or below the market's own base rate) is noise and never printed.
    sheet = (day[(day.recipe_hits >= 2) & ((day.conviction >= 2) | (day.conviction == 0))].copy()
             if stance != "STAND_DOWN" else day.iloc[:0])
    sheet = sheet.sort_values(["recipe_hits", "est_p", "lens_total"], ascending=False)

    print()
    for _, r in sheet.head(a.top).iterrows():
        if not np.isfinite(r.ref_close):
            continue
        p = r.est_p if np.isfinite(r.est_p) else None
        n = int(r.n_analogues)
        ptxt = f"   est P(+2ATR/20d): {p:.0%} ({n:,} analogues)" if p else ""
        move = (r.obj_2atr / r.ref_close - 1) * 100
        pt = r.est_p_test if np.isfinite(r.est_p_test) else None
        print(f"{'-' * 86}")
        print(f"{r.ticker:<6} {r.signal}")
        print(f"  CONVICTION  {int(r.conviction)}/5 {r.conviction_word}"
              + (f"        {p:.0%} vs {r.market_base:.0%} for the average "
                 f"stock today" if p else ""))
        if r.qs_state:
            print(f"  STATE       {r.state_desc.capitalize()}")
        if r.awareness:
            print(f"  NOTE        {r.awareness}")
        print(f"  TRADE       now {r.ref_close:.2f}  ->  target {r.obj_2atr:.2f} "
              f"(+{move:.1f}%)")
        if np.isfinite(r.days_median):
            print(f"              usually takes about {r.days_median:.0f} trading "
                  f"days")
        if np.isfinite(r.mae_atr_median):
            drop = abs(r.mae_atr_median) * r.atr_pct
            print(f"              typically dips up to {drop:.1f}% along the way; "
                  f"give up below {r.adverse_2atr:.2f}")
        if r.vetoes:
            print(f"       !! VETO: {r.vetoes}")
        print(f"       STRUCTURE  {r.L_STRUCTURE:>4}/10 {word(r.L_STRUCTURE)} "
              f"| range pos {r.en_pos50:.0f}/100, structure {r.structure_100:.0f}, "
              f"base {int(r.base_days) if np.isfinite(r.base_days) else '-'}d")
        print(f"       COIL       {r.L_COIL:>4}/10 {word(r.L_COIL)} "
              f"| range tight {r.bq_range_tight:.0f}/30, MA conv {r.bq_ema_conv:.0f}/25, "
              f"squeeze {r.squeeze_score:.1f}/12.5")
        print(f"       MOMENTUM   {r.L_MOMENTUM:>4}/10 {word(r.L_MOMENTUM)} "
              f"| roc-z {r.roc_zscore:+.2f}, abs {r.abs_mom_score:.0f}/30, "
              f"rel {r.rel_mom_score:.0f}/25   (HIGH score = still QUIET = good)")
        print(f"       FLOW       {r.L_FLOW:>4}/10 {word(r.L_FLOW)} "
              f"| accum {r.accum_score:.1f}/7.5, CMF {r.cmf:+.2f}, MFI {r.mfi:.0f}")
        print(f"       LEADERSHIP {r.L_LEADERSHIP:>4}/10 {word(r.L_LEADERSHIP)} "
              f"| beats mkt {r.rs_consist*100 if np.isfinite(r.rs_consist) else float('nan'):.0f}% "
              f"of days, vs SPY {r.rs_vs_spy:+.1f}, elder {r.elder_score:.0f}/10")
    print(f"{'-' * 86}")
    out = os.path.join(ROOT, f"scan_{asof.date()}.csv")
    keep = (["ticker", "signal", "recipe_hits", "lens_total"] + lens_cols +
            ["ref_close", "obj_2atr", "adverse_2atr", "atr_pct", "vetoes"])
    sheet[[c for c in keep if c in sheet.columns]].to_csv(out, index=False)

    # ---- JSON contract (QS_ENGINE.md Part 5) -------------------------------
    # Everything downstream -- the AQE screen, the TradingView export, the
    # journal -- renders THIS file. Nothing recomputes.
    COMPONENTS = ["en_pos50", "ms_pos_score", "structure_100", "base_days",
                  "bq_range_tight", "bq_ema_conv", "squeeze_score",
                  "roc_zscore", "abs_mom_score", "rel_mom_score",
                  "accum_score", "cmf", "mfi",
                  "rs_consist", "rs_vs_spy", "elder_score"]

    def jnum(v, nd=4):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return None if not np.isfinite(f) else round(f, nd)

    rows = []
    for _, r in day.sort_values("qs_rank", na_position="last").iterrows():
        ranked = np.isfinite(r.qs_rank)
        rows.append({
            "rank": int(r.qs_rank) if ranked else None,
            "ticker": r.ticker,
            "signal": r.signal,
            "high_probability": bool(r.high_probability),
            "recipe_hits": int(r.recipe_hits),
            "est_p": jnum(r.est_p, 3),
            "est_p_test": jnum(r.est_p_test, 3),
            "n_analogues": int(r.n_analogues),
            "qs_persist": int(r.qs_persist),
            "conviction": int(r.conviction),
            "conviction_word": str(r.conviction_word),
            "market_base_rate": float(r.market_base),
            "qs_state": str(r.qs_state),
            "qs_state_desc": str(r.state_desc),
            "awareness_notes": str(r.awareness),
            "days_to_target_median": (None if not np.isfinite(r.days_median)
                                      else float(r.days_median)),
            "expected_dip_atr": (None if not np.isfinite(r.mae_atr_median)
                                 else float(r.mae_atr_median)),
            "lens": {"structure": jnum(r.L_STRUCTURE, 1),
                     "coil": jnum(r.L_COIL, 1),
                     "momentum_quiet": jnum(r.L_MOMENTUM, 1),
                     "flow": jnum(r.L_FLOW, 1),
                     "leadership": jnum(r.L_LEADERSHIP, 1),
                     "total": jnum(r.lens_total, 1)},
            "components": {c: jnum(r.get(c)) for c in COMPONENTS
                           if c in day.columns},
            "levels": {"ref_close": jnum(r.ref_close, 2),
                       "obj_2atr": jnum(r.obj_2atr, 2),
                       "adverse_2atr": jnum(r.adverse_2atr, 2),
                       "atr_pct": jnum(r.atr_pct, 2)},
            "vetoes": [v.strip() for v in str(r.vetoes).split(";") if v.strip()],
            "why": rationale_for(r.name) if ranked else "",
        })

    doc = {
        "date": str(asof.date()),
        "engine": "QS",
        "version": f"recipe_book@{book.get('built', 'n/a')}",
        "outcome_def": "touch +2*ATR14 within 20 sessions, entry next open",
        "regime": {"cell": cell, "description": reg.get("desc"),
                   "stance": stance, "cell_base_rate": reg.get("base_rate_test")},
        "universe": {"scanned": int(len(day)),
                     "with_hits": int((day.recipe_hits >= 1).sum()),
                     "high_probability": int(day.high_probability.sum())},
        "rows": rows,
    }
    jout = os.path.join(ROOT, f"qs_daily_{asof.date()}.json")
    json.dump(doc, open(jout, "w"), indent=1)

    print(f"legend: lens 0-10 = today's cross-sectional percentile, oriented to the "
          f"winning profile\nsaved -> {out}\nsaved -> {jout}")

    # ---- transport the SAME numbers to TradingView -------------------------
    import export_pine as EP
    import parity_check as PC
    print("TradingView export:")
    EP.generate(jout)
    PC.check(jout, verbose=False)


if __name__ == "__main__":
    main()
