"""VALEN Dashboard — nightly orchestration. Same wrapped-addition pattern as
src/macro/crown/daily.py::run_crown(): this is an addition to a working
real-money pipeline and must never take the export down with it.

Market trend (SPY/QQQ), extension (VIX/VIX3M + index ATR-multiple-from-
50-day), whole-market breadth (real, from ma_panel.parquet — see
breadth.py), and the Neighbourhood (groups + rotation — see groups.py) are
all computed for real. `stance.status` is only DEGRADED when
`ensure_ma_panel()` cannot get the breadth panel by any path (this
checkout's local disk, then the Daily Persist snapshot on Drive) — an
honest absence, never a fabricated read. The curated-panel % above 20-day
stays as labelled CONTEXT alongside the real whole-market instruments,
never confused with T2108 — see extension.py.

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

from src.data.paths import DATA_DIR, OUTPUT_DIR, PANEL_DAILY, PANEL_WEEKLY
from src.macro.crown import cboe

from . import breadth as breadth_mod
from . import card, explain, extension, groups as groups_mod, spec, stance, trend

LOCAL_PATH = OUTPUT_DIR / "valen_dashboard.json"
PUBLISHED_PATH = OUTPUT_DIR / "aqe_valen_dashboard.json"
MA_PANEL_PATH = DATA_DIR / "ma_panel.parquet"


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

    # Whole-market breadth (piece 01's four instruments), computed for real
    # from the ~2000-ticker ma_panel the HF Space's in-app scheduler already
    # pulls daily — restoring it from the Daily Persist snapshot first if
    # this run's checkout doesn't have it locally. See breadth.py module
    # docstring for why the restore step is necessary (GitHub Actions runs
    # in a separate, ephemeral checkout from the HF Space that builds it).
    try:
        ma_panel = breadth_mod.ensure_ma_panel(MA_PANEL_PATH)
    except Exception:  # noqa: BLE001
        ma_panel = None
    breadth = breadth_mod.compute_breadth(ma_panel)

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
