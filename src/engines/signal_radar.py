"""Signal Radar -- the %-radar's scans as computable tags (live AQE engine).

Promoted from the M14-M18 research program (2026-07-06). PM mandate: this is a
%-based RADAR for momentum-swing trading with two jobs --
(1) what is ABOUT to run (pre-move), (2) what will KEEP running (continuation).
It is NOT a risk / bracket / sizing engine. Every % figure it emits is a DETECTION
RATE (how often tagged names went on to touch +X% -- price path only), never a
win rate or risk-adjusted alpha.

ADDITIVE ONLY. This engine consumes the scored universe (scores_daily) + the daily
OHLCV panel that already exist; it does not change scoring, gating, DSL, or any
existing export field. Its five tags are appended to the export for AIC context and
logged to the paper-track (signal_ledger) -- they never gate, filter, or size.

Tags:
  runner_setup      Job 2 (continuation). Verbatim M15 rule, OOS-validated:
                    base_days <= 15 AND ret_5d > 14.5% AND resist_score <= 8.5
                    (short young base + strong 5-day thrust + clear overhead).
  mover_subtype     explosive / trend / tight_base / squeeze -- family z-score argmax
                    (M16c method, frozen z-params).
  runner_conviction 0-4: how many of the four M15 interaction legs are in their
                    favourable tercile (short base / strong 5d momentum / clear
                    overhead / room below the 20-day high). Tercile cuts frozen.
  premove_setup     Job 1 (pre-move). M18-confirmed launcher rule. Applies ONLY to
                    names that are QUIET at the scan date (per the M18 pond definition).
  premove_conviction 0-N legs of the M18 launcher fingerprint.

Params (tercile cuts, subtype z-params, premove rule + track bands) are FROZEN in
data/signal_engine_params.json -- fitted once on the v1.8.0 QUAL pond, NEVER re-fit
in production. compute_dynamic_features() reproduces the study matrix to the last
decimal (verified in the research session: 100% conformance, 50.6% OOS detection
vs the study's 52.4%).
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from src.data.paths import DATA_DIR, PANEL_DAILY, SCORES_DAILY

warnings.filterwarnings("ignore", category=FutureWarning)

PARAMS_FILE = DATA_DIR / "signal_engine_params.json"

# ---------------------------------------------------------------------------
# Frozen rule + families (from M15/M16 -- do not re-tune here)
# ---------------------------------------------------------------------------
RUNNER_RULE = {"base_days_max": 15.0, "ret_5d_min": 14.5, "resist_score_max": 8.5}

SUBTYPE_FAMILIES = {
    "explosive": ["ret_3d", "ret_5d", "atr_slope_3d", "atr_slope_5d"],
    "trend": ["mp_100", "adx_val", "k39_value", "pipe_rank"],
    "tight_base": ["bq_vol_dry", "bq_100", "bq_range_tight"],
    "squeeze": ["squeeze_score", "ext_score", "rd_compression", "energy_100"],
}

STATIC_COLS = ["base_days", "resist_score", "mp_100", "adx_val", "k39_value",
               "pipe_rank", "bq_vol_dry", "bq_100", "bq_range_tight",
               "squeeze_score", "ext_score", "rd_compression", "energy_100",
               "bq_base_dur", "bq_base_days", "bq_ema_conv",   # M18 fingerprint legs
               "sc_momentum", "elder_score"]

DYNAMIC_COLS = ["ret_3d", "ret_5d", "atr_slope_3d", "atr_slope_5d", "atr5_over_atr20",
                "vol5_over_vol20", "updown_vol_3d", "updown_vol_5d", "obv_accum_5d",
                "close_str_5d", "higher_lows_5d", "up_days_5d", "range_comp_5v20",
                "dist_20dhigh", "trailing20", "pos20"]

# M18 quiet-pond definition (frozen spec): trailing-20d in [-8, +8] AND below the top
# decile of the name's own 20-day range.
QUIET_TRAIL_LO, QUIET_TRAIL_HI, QUIET_POS20_MAX = -8.0, 8.0, 0.90

# The 5 tags this engine appends to the export (additive; never gate/size).
SIGNAL_FIELDS = ["runner_setup", "runner_conviction", "mover_subtype",
                 "premove_setup", "premove_conviction"]


# ---------------------------------------------------------------------------
# Dynamic (3-5 day trajectory) features -- EXACT M14 formulas, single source of truth
# ---------------------------------------------------------------------------
def compute_dynamic_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Add the 3-5 day trajectory features to a daily OHLCV panel.

    panel: columns [date, ticker, open, high, low, close, volume].
    Returns a sorted copy with the DYNAMIC_COLS added. Formulas are verbatim from
    the M14 study source -- so engine == study (verified to <1e-6 max abs diff).
    """
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"])
    p = p.sort_values(["ticker", "date"]).reset_index(drop=True)
    g = p.groupby("ticker")

    pc = g["close"].shift(1)
    tr = pd.concat([p["high"] - p["low"], (p["high"] - pc).abs(),
                    (p["low"] - pc).abs()], axis=1).max(axis=1)
    atr14 = tr.groupby(p["ticker"]).transform(lambda s: s.rolling(14, min_periods=7).mean())
    p["atr_slope_5d"] = atr14.groupby(p["ticker"]).transform(lambda s: s.pct_change(5)) * 100
    p["atr_slope_3d"] = atr14.groupby(p["ticker"]).transform(lambda s: s.pct_change(3)) * 100
    p["atr5_over_atr20"] = (tr.groupby(p["ticker"]).transform(lambda s: s.rolling(5).mean())
                            / tr.groupby(p["ticker"]).transform(lambda s: s.rolling(20).mean()))
    p["vol5_over_vol20"] = (g["volume"].transform(lambda s: s.rolling(5).mean())
                            / g["volume"].transform(lambda s: s.rolling(20).mean()))
    up = (p["close"] > pc).astype(float)
    upvol = p["volume"] * up
    dnvol = p["volume"] * (1 - up)
    p["updown_vol_5d"] = (upvol.groupby(p["ticker"]).transform(lambda s: s.rolling(5).sum())
                          / dnvol.groupby(p["ticker"]).transform(lambda s: s.rolling(5).sum()).replace(0, np.nan))
    p["updown_vol_3d"] = (upvol.groupby(p["ticker"]).transform(lambda s: s.rolling(3).sum())
                          / dnvol.groupby(p["ticker"]).transform(lambda s: s.rolling(3).sum()).replace(0, np.nan))
    obv = (np.sign(p["close"] - pc).fillna(0) * p["volume"]).groupby(p["ticker"]).cumsum()
    vol20 = g["volume"].transform(lambda s: s.rolling(20).mean())
    p["obv_accum_5d"] = obv.groupby(p["ticker"]).transform(lambda s: s.diff(5)) / (vol20 * 5)
    rng = p["high"] - p["low"]
    p["close_str_5d"] = ((p["close"] - p["low"]) / rng.replace(0, np.nan)
                         ).groupby(p["ticker"]).transform(lambda s: s.rolling(5).mean())
    p["higher_lows_5d"] = (p["low"] > g["low"].shift(1)).astype(float).groupby(p["ticker"]).transform(
        lambda s: s.rolling(5).sum())
    p["up_days_5d"] = up.groupby(p["ticker"]).transform(lambda s: s.rolling(5).sum())
    p["range_comp_5v20"] = (rng.groupby(p["ticker"]).transform(lambda s: s.rolling(5).mean())
                            / rng.groupby(p["ticker"]).transform(lambda s: s.rolling(20).mean()))
    p["ret_3d"] = g["close"].transform(lambda s: s.pct_change(3)) * 100
    p["ret_5d"] = g["close"].transform(lambda s: s.pct_change(5)) * 100
    hi20 = g["high"].transform(lambda s: s.rolling(20).max())
    lo20 = g["low"].transform(lambda s: s.rolling(20).min())
    p["dist_20dhigh"] = (p["close"] / hi20 - 1) * 100
    p["trailing20"] = g["close"].transform(lambda s: s.pct_change(20)) * 100
    p["pos20"] = (p["close"] - lo20) / (hi20 - lo20).replace(0, np.nan)
    return p


def forward_touch_frame(panel: pd.DataFrame, horizons: tuple[int, ...] = (10, 20)) -> pd.DataFrame:
    """Forward outcome per (ticker, date): entry at NEXT bar's open, then the max
    favourable move (%) within each horizon. Price path only -- no stop, no R.

    Returns [ticker, date, entry_open, fwdmax_pct_10d, fwdmax_pct_20d].
    Touch flags derive by comparison, e.g. touched +20%/20d == fwdmax_pct_20d >= 20.
    """
    p = panel.sort_values(["ticker", "date"]).reset_index(drop=True)
    out = []
    for tk, grp in p.groupby("ticker"):
        o = grp["open"].to_numpy(float)
        h = grp["high"].to_numpy(float)
        d = grp["date"].to_numpy()
        n = len(grp)
        rows = np.full((n, len(horizons)), np.nan)
        eo = np.full(n, np.nan)
        for i in range(n - 1):
            e = o[i + 1]
            if not (e > 0):
                continue
            eo[i] = e
            for j, hz in enumerate(horizons):
                j1 = min(i + 1 + hz, n)
                if i + 1 < j1 and (j1 - (i + 1)) >= hz:      # full window only
                    rows[i, j] = (h[i + 1:j1].max() / e - 1) * 100
        rec = pd.DataFrame({"ticker": tk, "date": d, "entry_open": eo})
        for j, hz in enumerate(horizons):
            rec[f"fwdmax_pct_{hz}d"] = rows[:, j]
        out.append(rec)
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------------------
# Params -- frozen JSON, loaded and never re-fit in production
# ---------------------------------------------------------------------------
def load_params() -> dict | None:
    if PARAMS_FILE.exists():
        with open(PARAMS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    return None


# ---------------------------------------------------------------------------
# Tag computation
# ---------------------------------------------------------------------------
def compute_signals(scores: pd.DataFrame, panel: pd.DataFrame,
                    dates=None, params: dict | None = None,
                    panel_has_dynamics: bool = False) -> pd.DataFrame:
    """Compute all tags for the given scores rows.

    scores: [date, ticker] + STATIC_COLS (from scores_daily live).
    panel : daily OHLCV (full history needed for the trajectory features).
    dates : optional subset of dates to tag (default: every scores date).
    """
    if params is None:
        params = load_params()
    if params is None:
        raise RuntimeError("no frozen params -- data/signal_engine_params.json missing")

    s = scores.copy()
    s["date"] = pd.to_datetime(s["date"])
    if dates is not None:
        dates = pd.to_datetime(pd.Index(dates))
        s = s[s["date"].isin(dates)]
    dyn = panel if panel_has_dynamics else compute_dynamic_features(panel)
    m = s.merge(dyn[["ticker", "date"] + DYNAMIC_COLS], on=["ticker", "date"], how="left")

    # ---- Job 2: runner_setup (verbatim M15 rule) ----
    r = RUNNER_RULE
    m["runner_setup"] = ((m["base_days"] <= r["base_days_max"])
                         & (m["ret_5d"] > r["ret_5d_min"])
                         & (m["resist_score"] <= r["resist_score_max"]))

    # ---- runner_conviction: 0-4 interaction legs ----
    c = params["conviction_cuts"]
    m["runner_conviction"] = ((m["base_days"] <= c["base_days_lo"]).astype(int)
                              + (m["ret_5d"] >= c["ret_5d_hi"]).astype(int)
                              + (m["resist_score"] <= c["resist_score_lo"]).astype(int)
                              + (m["dist_20dhigh"] <= c["dist_20dhigh_lo"]).astype(int))

    # ---- mover_subtype: family z-score argmax ----
    zp = params["subtype_z"]
    fam_scores = {}
    for fam, feats in SUBTYPE_FAMILIES.items():
        zs = []
        for f in feats:
            mu, sd = zp[f]["mean"], zp[f]["std"]
            zs.append((pd.to_numeric(m[f], errors="coerce") - mu) / (sd if sd else 1.0))
        fam_scores[fam] = pd.concat(zs, axis=1).mean(axis=1)
    fam_df = pd.DataFrame(fam_scores)
    m["mover_subtype"] = fam_df.idxmax(axis=1)
    m.loc[fam_df.isna().all(axis=1), "mover_subtype"] = None

    # ---- quiet flag + Job 1: premove_setup (M18-confirmed rule) ----
    m["is_quiet"] = ((m["trailing20"] >= QUIET_TRAIL_LO) & (m["trailing20"] <= QUIET_TRAIL_HI)
                     & (m["pos20"] < QUIET_POS20_MAX))
    pm = params.get("premove_rule")
    if pm:
        cond = m["is_quiet"].copy()
        for leg in pm["legs"]:
            f, op, thr = leg["feature"], leg["op"], leg["value"]
            if f not in m.columns:                 # a rule leg the input can't serve
                raise RuntimeError(f"premove rule needs column '{f}' -- add it to the scores input")
            v = pd.to_numeric(m[f], errors="coerce")
            cond &= (v <= thr) if op == "<=" else (v > thr)
        m["premove_setup"] = cond
        pc_cuts = params.get("premove_conviction_cuts") or {}
        conv = pd.Series(0, index=m.index)
        for f, cut in pc_cuts.items():
            if f not in m.columns:                 # conviction legs degrade gracefully
                continue
            v = pd.to_numeric(m[f], errors="coerce")
            conv += ((v <= cut["value"]) if cut["direction"] == "low" else (v >= cut["value"])).astype(int)
        m["premove_conviction"] = conv.where(m["is_quiet"], 0)
    else:
        m["premove_setup"] = False
        m["premove_conviction"] = 0

    # QUAL context (informational)
    if {"sc_momentum", "elder_score"} <= set(m.columns):
        m["on_qual"] = (m["sc_momentum"] >= 75) & (m["elder_score"] >= 6.5)

    keep = ["ticker", "date", "runner_setup", "runner_conviction", "mover_subtype",
            "premove_setup", "premove_conviction", "is_quiet", "on_qual",
            "base_days", "ret_5d", "ret_3d", "resist_score", "dist_20dhigh",
            "trailing20", "pos20", "sc_momentum", "elder_score"]
    return m[[k for k in keep if k in m.columns]]


# ---------------------------------------------------------------------------
# Live helpers -- consumed by drive_sync (export lookup) + signal_ledger (paper-track)
# ---------------------------------------------------------------------------
def _clean(v):
    """JSON-safe scalar: NaN/NaT -> None; numpy -> python."""
    if v is None:
        return None
    try:
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


def signal_lookup(scores_path=None, panel_path=None, asof=None) -> dict[str, dict]:
    """Build a per-ticker signal-tag dict for the latest scored date.

    Returns {ticker: {runner_setup, runner_conviction, mover_subtype,
                      premove_setup, premove_conviction}} -- exactly the 5 fields the
    export stamps onto each record. Read-only; raises only if params/data missing
    (caller wraps in try/except so a failure degrades to no tags).
    """
    scores_path = scores_path or SCORES_DAILY
    panel_path = panel_path or PANEL_DAILY
    scores = pd.read_parquet(scores_path)
    scores["date"] = pd.to_datetime(scores["date"])
    have = [c for c in STATIC_COLS if c in scores.columns]
    missing = [c for c in STATIC_COLS if c not in scores.columns]
    if missing:
        raise RuntimeError(f"scores_daily missing signal columns: {missing}")
    panel = pd.read_parquet(panel_path, columns=["date", "ticker", "open", "high",
                                                 "low", "close", "volume"])
    when = pd.to_datetime(asof) if asof else scores["date"].max()
    tags = compute_signals(scores[["date", "ticker"] + have], panel, dates=[when])

    out: dict[str, dict] = {}
    for _, row in tags.iterrows():
        out[row["ticker"]] = {
            "runner_setup": _clean(row.get("runner_setup")),
            "runner_conviction": _clean(row.get("runner_conviction")),
            "mover_subtype": _clean(row.get("mover_subtype")),
            "premove_setup": _clean(row.get("premove_setup")),
            "premove_conviction": _clean(row.get("premove_conviction")),
        }
    return out


def scan_latest(asof=None) -> dict:
    """On-demand manual scan (the run_signal_scan.bat fallback). Returns today's
    runner + pre-mover names. No side effects beyond reading the parquets."""
    lk = signal_lookup(asof=asof)
    runners = sorted(
        [{"ticker": t, **v} for t, v in lk.items() if v.get("runner_setup")],
        key=lambda x: -(x.get("runner_conviction") or 0),
    )
    premovers = sorted(
        [{"ticker": t, "premove_conviction": v.get("premove_conviction")}
         for t, v in lk.items() if v.get("premove_setup")],
        key=lambda x: -(x.get("premove_conviction") or 0),
    )
    return {"n_scored": len(lk), "runner_setup": runners, "premove_setup": premovers,
            "note": "DETECTION tags only -- not gates, not sizing. PM decides entry/bracket/size live."}
