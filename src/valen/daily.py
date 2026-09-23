"""VALEN Dashboard — nightly orchestration. Same wrapped-addition pattern as
src/macro/crown/daily.py::run_crown(): this is an addition to a working
real-money pipeline and must never take the export down with it.

Phase 1 scope (docs/AQE_VALEN_DASHBOARD_PROPOSAL.md): market trend (SPY/QQQ),
extension (VIX/VIX3M + index ATR-multiple-from-50-day), and the stance read —
which stays DEGRADED (no one-word stance) until Phase 2 wires in a
market-wide breadth population. The curated-panel % above 20-day is
computed and shown as labelled CONTEXT, never as T2108 — see extension.py.

Writes two local files, same split as the other four macro artifacts:
  output/valen_dashboard.json      full detail, runtime-local
  output/aqe_valen_dashboard.json  plain-English first, published copy

Drive/GitHub publish is NOT wired in this pass — see proposal §7 phasing.
The daily orchestrator step below is local-file-only; publishing alongside
aqe_crown_macro.json is a fast-follow once the page itself is confirmed
useful.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from src.data.paths import OUTPUT_DIR, PANEL_DAILY, PANEL_WEEKLY
from src.macro.crown import cboe

from . import card, explain, extension, groups as groups_mod, spec, stance, trend

LOCAL_PATH = OUTPUT_DIR / "valen_dashboard.json"
PUBLISHED_PATH = OUTPUT_DIR / "aqe_valen_dashboard.json"


def _today_sgt() -> str:
    return datetime.now(ZoneInfo("Asia/Singapore")).date().isoformat()


def run_valen() -> dict:
    """Builds the full VALEN artifact from the same panel every other AQE
    engine reads. Never raises — returns a `status` of OK/DEGRADED/
    UNAVAILABLE and the reason, same vocabulary as crown/daily.py."""
    t = trend.compute_market_trend(PANEL_DAILY, PANEL_WEEKLY)

    try:
        idx_df = pd.read_parquet(
            PANEL_DAILY, columns=["date", "ticker", "open", "high", "low", "close"])
        idx_df = idx_df[idx_df["ticker"].isin(spec.TREND_SYMBOLS)]
    except Exception:  # noqa: BLE001
        idx_df = pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close"])

    idx = {sym: extension.index_atr_multiple(idx_df[idx_df["ticker"] == sym])
           for sym in spec.TREND_SYMBOLS}

    try:
        frames = cboe.series_frames()
    except Exception:  # noqa: BLE001
        frames = {}
    vv = extension.vix_vix3m(frames.get("vix"), frames.get("vix3m"))

    ext = {"index_atr": idx, "vix_vix3m": vv}

    # Curated-panel breadth CONTEXT (real, labelled) — never confused with
    # the whole-market instruments the stance rules actually need.
    curated_context = None
    try:
        full_panel = pd.read_parquet(PANEL_DAILY, columns=["date", "ticker", "close"])
        curated_context = extension.breadth_pct_above_20d(
            full_panel, spec.POPULATION_CURATED)
    except Exception:  # noqa: BLE001
        curated_context = None

    breadth_reason = ("whole-market breadth not yet wired — needs "
                      "src/scanner/ma_scanner.py widened to a full-tape "
                      "population (proposal §2.2, §9.1)")
    breadth = {k: extension.whole_market_breadth_unavailable(breadth_reason)
               for k in ("pct_above_40d", "monthly_risers",
                        "five_day_count", "daily_count_green")}

    # The Neighbourhood (pieces 02/03) — where the money is going, and
    # whether a group is leading from its highs or just bouncing off its
    # lows. Reuses AQE's 35 thematic baskets; see groups.py module docstring.
    try:
        full_panel_ohlc = pd.read_parquet(
            PANEL_DAILY, columns=["date", "ticker", "open", "high", "low", "close", "volume"])
        gr = groups_mod.compute_groups(full_panel_ohlc)
    except Exception as exc:  # noqa: BLE001
        gr = {"status": "UNAVAILABLE", "reason": str(exc), "groups": [],
              "theme_leaders": {}, "rotation": []}

    st = stance.compute_stance(t, ext, breadth)
    pe = explain.explain(t, ext, st, gr)

    artifact = {
        "date": _today_sgt(),
        "exported_at": datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M:%S SGT"),
        "basis": "eod",
        "trend": t,
        "extension": ext,
        "breadth": breadth,
        "curated_panel_context": curated_context,
        "groups": gr,
        "stance": st,
        "plain_english": pe,
        "status": st.get("status", "UNAVAILABLE"),
    }
    return artifact


def write_artifacts(artifact: dict) -> dict:
    """Local write only — see module docstring on Drive publish scope."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_PATH.write_text(json.dumps(artifact, indent=2, default=str), encoding="utf-8")

    published = {
        "date": artifact["date"], "exported_at": artifact["exported_at"],
        "basis": artifact["basis"], "status": artifact["status"],
        "read_me_first": artifact["plain_english"],
        "stance": card.stance_banner(artifact),
        "trend": card.trend_rows(artifact),
        "regime": card.regime_word(artifact),
        "extension": card.extension_rows(artifact),
        "breadth": card.breadth_rows(artifact),
        "neighbourhood": card.neighbourhood_lines(artifact),
        "theme_leaders": card.theme_leaders_table(artifact),
        "rotation": card.rotation_table(artifact),
    }
    PUBLISHED_PATH.write_text(json.dumps(published, indent=2, default=str), encoding="utf-8")
    return {"local": str(LOCAL_PATH), "published": str(PUBLISHED_PATH)}


def load_valen() -> dict | None:
    """The last written VALEN read, for the UI to render without re-running —
    same pattern as crown/daily.py::load_crown()."""
    if not LOCAL_PATH.exists():
        return None
    try:
        return json.loads(LOCAL_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
