"""QS daily run — one function the orchestrator calls, one dict it returns.

Assembles the whole QS layer for a run date:

  load frozen config -> build the 5 missing fields -> resolve today's regime
  cell -> pick today's ELIGIBLE set -> score -> store memory -> return rows

Kept out of `daily_orchestrator` so the pipeline gains one call rather than
sixty lines, and so the whole layer is testable without running a pipeline.

DEGRADES, NEVER RAISES. QS is an addition to a working real-money pipeline;
a QS failure must not take down the export that Longlist, Elder and the held
book all ride on. Every entry point returns a status dict, and `status` is
carried into the export so a silent QS outage is impossible to mistake for
"no names qualified today" — the distinction the PM has to be able to make.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

from src.data.paths import DATA_DIR, OUTPUT_DIR, PANEL_DAILY, PROJECT_ROOT, SCORES_DAILY
from src.engines import qs_engine as E
from src.engines import qs_fields as F
from src.engines import qs_spec as S

# The frozen book/calibration are CODE-adjacent, not runtime state: they ship
# with the repo and are baked into the Docker image at <project>/data/qs.
# Resolving them from DATA_DIR alone breaks on any deploy that redirects it —
# a Hugging Face Space with persistent storage sets AQE_DATA_DIR=/data, where
# no config was ever written, so QS would fail to load on every single run.
#
# Order: DATA_DIR first (so an operator CAN drop a newer freeze into
# persistent storage without a rebuild), then the shipped copy.
def _config_path(name: str):
    override = DATA_DIR / "qs" / name
    if override.exists():
        return override
    return PROJECT_ROOT / "data" / "qs" / name


QS_CONFIG_DIR = PROJECT_ROOT / "data" / "qs"
RECIPE_BOOK_PATH = _config_path("recipe_book.json")
CALIBRATION_PATH = _config_path("calibration.json")

# Standalone daily artifact. AQE's convention is a stable filename overwritten
# each run (so the Drive folder never clutters), and the immutable per-day
# record lives in aqe.db's qs_daily_hits trail, which is the real audit trail
# and is snapshotted. The run date is carried INSIDE the file.
QS_DAILY_JSON = OUTPUT_DIR / "qs_daily.json"

# QS's own daily eligibility rule, ON TOP of universe membership: today's
# volume must exceed the ticker's OWN 10-day average (handover §2.1). About
# 40% of names pass on any given day. This is the population the frozen
# probabilities were measured on, so it is not optional — scoring a wider set
# would leave the quoted odds describing a different population.
VOLUME_LOOKBACK = 10


def load_config() -> tuple[dict, dict]:
    """The two frozen artifacts. Read-only — never fitted at runtime."""
    with open(RECIPE_BOOK_PATH) as f:
        book = json.load(f)
    with open(CALIBRATION_PATH) as f:
        cal = json.load(f)
    return book, cal


def write_daily_json(result: dict) -> str | None:
    """Write the standalone QS artifact alongside the main export.

    Same numbers as the export's qs blocks — one computation, two surfaces, so
    they cannot drift. Returns the path, or None if the run failed (a failed
    run must not overwrite yesterday's good file with an empty one).
    """
    if not result.get("ok"):
        return None
    try:
        rows = sorted(
            (r for r in result["rows"].values() if r.get("emitted")),
            key=lambda r: (r.get("rank") or 10 ** 6))
        doc = {
            "date": result.get("date"),
            "engine": "QS",
            "status": result.get("status"),
            "versions": result.get("versions", {}),
            "outcome_def": "touch +2*ATR14 within 20 sessions",
            "market": result.get("market", {}),
            "counts": {
                "eligible": result.get("eligible_count"),
                "scored": result.get("scored_count"),
                "emitted": result.get("emitted_count"),
            },
            "persist_ready": result.get("persist_ready"),
            "ideas": rows,
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(QS_DAILY_JSON, "w") as f:
            json.dump(doc, f, indent=1, default=str)
        return str(QS_DAILY_JSON)
    except Exception:  # noqa: BLE001 — an artifact write never breaks the run
        return None


def eligible_tickers(panel: pd.DataFrame, as_of) -> list[str]:
    """Names whose volume today beats their own 10-day average.

    A name with no volume history is EXCLUDED rather than assumed eligible:
    the rule is a positive test, and admitting an unmeasurable name would put
    it in the cross-section that defines everyone else's percentiles.
    """
    p = panel.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    p = p[p["date"] <= pd.Timestamp(as_of)].sort_values(["ticker", "date"])
    out = []
    for tk, g in p.groupby("ticker", sort=False):
        v = g["volume"].to_numpy(dtype=float)
        if len(v) < VOLUME_LOOKBACK + 1 or g["date"].iloc[-1] != pd.Timestamp(as_of):
            continue
        avg10 = float(np.nanmean(v[-(VOLUME_LOOKBACK + 1):-1]))
        if np.isfinite(avg10) and avg10 > 0 and float(v[-1]) > avg10:
            out.append(str(tk))
    return out


def resolve_regime(book: dict, regime_row: pd.Series | None) -> dict:
    """Today's regime cell -> the book entry the conviction edge is measured against."""
    cell = "unclassified"
    if regime_row is not None and regime_row.get("regime_cell"):
        cell = str(regime_row["regime_cell"])
    entry = (book.get("regimes") or {}).get(cell) or {}
    return {
        "cell": cell,
        "desc": entry.get("desc", "Not enough history to classify"),
        "stance": entry.get("stance", "NEUTRAL"),
        "base_rate_test": entry.get("base_rate_test"),
        "trend_200": (None if regime_row is None
                      else _f(regime_row.get("trend_200"))),
        "vol_60": None if regime_row is None else _f(regime_row.get("vol_60")),
    }


def _f(v):
    try:
        f = float(v)
        return None if not np.isfinite(f) else round(f, 4)
    except (TypeError, ValueError):
        return None


def market_block(regime: dict) -> dict:
    """The MARKET row — plain English first, numbers after, code as a footnote.

    `colour` grades the weather from the recipe book's OWN measured base rate,
    not from invented thresholds: GREEN >= 0.60, AMBER >= 0.50, RED below,
    GREY when the regime was never measured. It is a WARNING — `gates_list` is
    False, so nothing here filters a single name. AQE presents; the PM decides.
    """
    base = regime.get("base_rate_test")
    colour = S.regime_colour(base)
    return {
        "description": regime["desc"],
        "avg_stock_hits_target": base,
        "action": S.STANCE_ACTION.get(regime["stance"], "Normal selectivity."),
        "regime_code": f"{regime['cell']} / {regime['stance']}",
        "stance": regime["stance"],
        "colour": colour,
        "vs_all_market_base": (None if base is None
                               else round(base - S.DEFAULT_CELL_BASE_RATE, 3)),
        "gates_list": S.REGIME_GATES_THE_LIST,
        "trend_200": regime.get("trend_200"),
        "vol_60": regime.get("vol_60"),
        "base_rate_measured": base is not None,
    }


def run(as_of: date | None = None, sector_map: dict[str, str] | None = None,
        store: bool = True) -> dict:
    """The whole QS layer for one day.

    Returns {ok, status, market, rows, eligible_count, scored_count, ...}.
    `rows` are keyed by ticker for the export merge. On any failure returns
    ok=False with a reason — never raises into the pipeline.
    """
    try:
        if not PANEL_DAILY.exists() or not SCORES_DAILY.exists():
            return _fail("panel or scores parquet missing — run the pipeline first")
        book, cal = load_config()

        panel = pd.read_parquet(PANEL_DAILY,
                                columns=["date", "ticker", "close", "volume"])
        panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
        scores = pd.read_parquet(SCORES_DAILY)
        scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()

        asof = (pd.Timestamp(as_of).normalize() if as_of
                else min(panel["date"].max(), scores["date"].max()))

        # --- the 5 fields AQE lacks, plus the regime series -----------------
        per, regime_df = F.compute_all(panel, sector_map=sector_map)

        from src.data import qs_store
        if store:
            qs_store.upsert_regime_series(regime_df.reset_index().rename(
                columns={"index": "date"}))

        reg_row = regime_df.loc[asof] if asof in regime_df.index else None
        regime = resolve_regime(book, reg_row)

        # --- today's eligible set ------------------------------------------
        elig = eligible_tickers(panel, asof)
        if not elig:
            return _fail(f"no ticker cleared the volume rule on {asof.date()}",
                         market=market_block(regime), regime=regime)

        day = scores[scores["date"] == asof].copy()
        if day.empty:
            return _fail(f"no scores for {asof.date()}",
                         market=market_block(regime), regime=regime)

        today_fields = per[per["date"] == asof]
        day = day.merge(today_fields.drop(columns=["date"]), on="ticker", how="left")

        elig_set = set(elig)
        eligible_day = day[day["ticker"].isin(elig_set)].copy()
        other_day = day[~day["ticker"].isin(elig_set)].copy()
        if eligible_day.empty:
            return _fail(f"no scored ticker is QS-eligible on {asof.date()}",
                         market=market_block(regime), regime=regime)

        persist_map = qs_store.get_qs_persist(asof)

        # The eligible frame IS the calibration population — percentiles must
        # be taken across it and nothing else.
        rows = E.run_qs(eligible_day, book, cal, regime,
                        persist_map=persist_map, eligible=True)

        # Names outside today's eligible set still get a read, scored against
        # the eligible cohort WITHOUT joining it, so the reference distribution
        # stays exactly the measured population. Flagged extrapolated.
        if not other_day.empty:
            rows += _score_off_cohort(other_day, eligible_day, book, cal,
                                      regime, persist_map)

        if store:
            qs_store.upsert_daily_hits(pd.DataFrame([{
                "date": asof, "ticker": r["ticker"],
                "recipe_hits": r["engine"]["recipe_hits"],
                "lens_total": r["engine"]["lens_total"],
                "eligible": r["eligible"],
            } for r in rows]))

        emitted = [r for r in rows if r["emitted"]]
        return {
            "ok": True, "status": "live", "date": str(asof.date()),
            "market": market_block(regime), "regime": regime,
            "rows": {r["ticker"]: r for r in rows},
            "eligible_count": len(eligible_day), "scored_count": len(rows),
            "emitted_count": len(emitted),
            "persist_ready": qs_store.store_status().get("persist_ready", False),
            "versions": {"recipe_book": book.get("generated"),
                         "calibration": cal.get("version")},
        }
    except Exception as exc:  # noqa: BLE001 — QS must never break the pipeline
        return _fail(f"{type(exc).__name__}: {exc}")


def _score_off_cohort(other: pd.DataFrame, cohort: pd.DataFrame, book: dict,
                      cal: dict, regime: dict, persist_map: dict) -> list[dict]:
    """Score non-eligible names against the eligible cohort's distribution.

    Their raw values are placed onto the cohort's curve WITHOUT being added to
    it, so every eligible name's percentile is untouched and the reference
    distribution stays the population the calibration was measured on.

    The resulting probability is a read-across, not a measured analogue — the
    name sat outside the population by construction — so every row comes back
    `eligible=False` and `odds.extrapolated=True`, and none of them are
    emitted onto the QS list.
    """
    scored = E.score_lenses(pd.concat([cohort, other], ignore_index=True))
    tail = scored.iloc[len(cohort):].copy()
    rows = E.run_qs(tail, book, cal, regime, persist_map=persist_map,
                    eligible=False)
    for r in rows:
        r["emitted"] = False
        r["rank"] = None
        r["not_listed_reason"] = (
            "not QS-eligible today (volume did not beat its own 10-day "
            "average) — scored against the eligible cohort as a read-across, "
            "never listed")
    return rows


def score_adhoc(record: dict, as_of=None) -> dict:
    """QS read for ONE ad-hoc ticker, scored against today's eligible cohort.

    `record` is an ad-hoc score result (src/scanner/adhoc.py) carrying the raw
    subcomponent values under the names score_runner persists.

    The ticker is placed onto the cohort's percentile curve WITHOUT joining it,
    so no universe name's lens score moves and the reference distribution stays
    the population the calibration was measured on. The result is therefore a
    READ-ACROSS: an ad-hoc name is outside the measured population by
    construction (it need not even be in the universe), so `eligible` is False
    and `odds.extrapolated` is True. Read it as "what the table says for a
    profile like this", never as a measured probability for this name.

    Returns {ok, qs, market, coverage, ...}. `coverage` is not decoration:
    `cond_mask` treats a MISSING field as a failed condition, so any recipe
    field the ad-hoc path could not compute silently costs hits, which can drop
    the name a whole band and understate its probability. The caller must
    surface that rather than presenting a confident-looking number.
    """
    try:
        tk = record.get("ticker")
        if not tk:
            return {"ok": False, "reason": "no ticker in record"}
        if not PANEL_DAILY.exists() or not SCORES_DAILY.exists():
            return {"ok": False, "reason": "panel/scores parquet missing — "
                                           "run the daily pipeline first"}
        book, cal = load_config()

        panel = pd.read_parquet(PANEL_DAILY,
                                columns=["date", "ticker", "close", "volume"])
        panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
        scores = pd.read_parquet(SCORES_DAILY)
        scores["date"] = pd.to_datetime(scores["date"]).dt.normalize()
        asof = (pd.Timestamp(as_of).normalize() if as_of
                else min(panel["date"].max(), scores["date"].max()))

        _, regime_df = F.compute_all(panel)
        reg_row = regime_df.loc[asof] if asof in regime_df.index else None
        regime = resolve_regime(book, reg_row)

        elig = set(eligible_tickers(panel, asof))
        cohort = scores[(scores["date"] == asof)
                        & (scores["ticker"].isin(elig))].copy()
        if cohort.empty:
            return {"ok": False, "reason": f"no eligible cohort on {asof.date()}",
                    "market": market_block(regime)}

        # rs_consist for the cohort feeds the LEADERSHIP lens; without it that
        # lens would score the ad-hoc name on 2 of 3 components.
        ew = F.build_ew_index(panel)
        rs = F.compute_rs_consist(panel, ew)
        rs_today = rs[rs["date"] == asof][["ticker", "rs_consist"]]
        cohort = cohort.merge(rs_today, on="ticker", how="left")

        row = {c: record.get(c) for c in cohort.columns if c in record}
        row["ticker"] = tk
        row["date"] = asof
        if record.get("rs_consist") is not None:
            row["rs_consist"] = record["rs_consist"]
        one = pd.DataFrame([row])

        # Which recipe/veto inputs did the ad-hoc path actually produce?
        needed = sorted({c["field"] for r in book["recipes"] for c in r["conditions"]}
                        | {c["field"] for v in book["vetoes"] for c in v["conditions"]})
        missing = [f for f in needed
                   if f not in one.columns or pd.isna(one[f].iloc[0])]

        stacked = E.score_lenses(pd.concat([cohort, one], ignore_index=True))
        tail = stacked.iloc[[-1]].copy()

        from src.data import qs_store
        persist = qs_store.get_qs_persist(asof)
        rows = E.run_qs(tail, book, cal, regime,
                        persist_map={tk: persist.get(tk, 0)}, eligible=False)
        if not rows:
            return {"ok": False, "reason": "engine returned no row",
                    "market": market_block(regime)}
        qs = rows[0]
        qs["emitted"] = False
        qs["rank"] = None
        return {
            "ok": True, "qs": qs, "market": market_block(regime),
            "regime": regime, "date": str(asof.date()),
            "cohort_size": len(cohort),
            "coverage": {
                "recipe_inputs_required": len(needed),
                "recipe_inputs_missing": missing,
                "complete": not missing,
            },
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def _fail(reason: str, market: dict | None = None,
          regime: dict | None = None) -> dict:
    """A LOUD empty. `status` distinguishes a QS outage from a quiet market."""
    return {"ok": False, "status": "error", "reason": reason,
            "market": market or {}, "regime": regime or {}, "rows": {},
            "eligible_count": 0, "scored_count": 0, "emitted_count": 0,
            "persist_ready": False}
