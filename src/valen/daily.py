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

`history` (piece 01, added 2026-10-01): the same trend/extension/breadth
reads, recomputed as of 5 and 21 trading sessions back, so a reader can
see the weather TURNING, not just today's snapshot — see history.py
module docstring for why this needs no new storage. GEX is excluded from
history; a gamma read is a snapshot of today's options open interest with
no panel to recompute against.

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
from . import card, execution, explain, extension, gex as gex_mod, groups as groups_mod
from . import crown_cockpit as crown_cockpit_mod
from . import history as history_mod
from . import house, management, selection, spec, stance, trend

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

    # GEX Traffic Light — a Weather companion instrument. Crown Macro
    # (Step 6f) has already run by the time VALEN's own Step 6i runs, so
    # its gamma read is already on disk; no new data pull here. Degrades to
    # UNAVAILABLE (never a fabricated GREEN/calm reading) if Crown hasn't
    # run this session or its own gamma fetch failed — see gex.py.
    try:
        from src.macro.crown.daily import load_crown
        crown = load_crown()
    except Exception:  # noqa: BLE001
        crown = None
    try:
        gex_reading = gex_mod.compute_gex_reading((crown or {}).get("gamma"))
    except Exception as exc:  # noqa: BLE001
        gex_reading = {"status": "UNAVAILABLE", "ticker": spec.GEX_TICKER, "reason": str(exc)}

    # Macro cockpit (piece 01) — five more Crown readings given a VALEN
    # gauge/LED/tag face, the same read-only pattern GEX already
    # established (see crown_cockpit.py module docstring). Still no new
    # data pull: the SAME `crown` read above. A PM ask (2026-10-02), "how
    # Crown and VALEN can be combined... more cockpit illustration within
    # VALEN's structure" — answered "all 5."
    try:
        crown_cockpit = crown_cockpit_mod.compute_crown_cockpit(crown)
    except Exception as exc:  # noqa: BLE001
        reason = str(exc)
        crown_cockpit = {k: {"status": "UNAVAILABLE", "reason": reason} for k in
                        ("breadth_range", "cta_crowding", "dispersion",
                         "divergence", "cot")}

    st = stance.compute_stance(t, ext, breadth)
    pe = explain.explain(t, ext, st, gr)

    # Turning-point history (piece 01): was the weather different 5
    # sessions (~1wk) or 21 sessions (~1mo) ago? Every input here is a pure
    # recompute off the SAME panels already read above, truncated — see
    # history.py module docstring for why this needs no new storage and
    # has no cold-start gap. GEX is excluded on purpose (no panel to
    # truncate for a point-in-time options read); never faked.
    history: dict = {}
    for key, n in history_mod.SESSIONS_AGO.items():
        try:
            t_h = trend.compute_market_trend_as_of(PANEL_DAILY, PANEL_WEEKLY, n)
            idx_h = {sym: extension.index_atr_multiple_as_of(idx_df[idx_df["ticker"] == sym], n)
                    for sym in spec.TREND_SYMBOLS}
            vv_h = extension.vix_vix3m_as_of(frames.get("vix"), frames.get("vix3m"), n)
            ext_h = {"index_atr": idx_h, "vix_vix3m": vv_h}
            breadth_h = breadth_mod.compute_breadth_as_of(ma_panel, n)
            st_h = stance.compute_stance(t_h, ext_h, breadth_h)
            t2108_h = breadth_h.get("pct_above_40d") or {}
            history[key] = {
                "sessions_ago": n,
                "stance": st_h.get("stance"), "stance_status": st_h.get("status"),
                "regime": t_h.get("regime"),
                "vix_vix3m": vv_h.get("ratio"),
                "t2108": t2108_h.get("value") if t2108_h.get("status") == "OK" else None,
                "spy_atr_mult": (idx_h.get("SPY") or {}).get("atr_multiple_from_50d"),
            }
        except Exception as exc:  # noqa: BLE001
            history[key] = {"sessions_ago": n, "stance_status": "UNAVAILABLE", "reason": str(exc)}

    artifact = {
        "date": _today_sgt(),
        "exported_at": datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M:%S SGT"),
        "basis": "eod",
        "trend": t,
        "extension": ext,
        "breadth": breadth,
        "curated_panel_context": curated_context,
        "groups": gr,
        "gex": gex_reading,
        "crown_cockpit": crown_cockpit,
        "stance": st,
        "history": history,
        "plain_english": pe,
        "status": st.get("status", "UNAVAILABLE"),
    }
    return artifact


def run_playbook(export: dict, valen_artifact: dict | None = None) -> dict:
    """Pieces 04-20 (Parts 2-4's read-only half, Parts 5-6's facts) —
    everything that needs the FINISHED scored export (`daily_list`/
    `held_positions`), unlike Part 1 Weather which only needs raw price
    panels and so runs earlier (Step 6i). This runs as its own later
    pipeline step, after Step 8 has written aqe_daily_export.json — the
    exact same "read-only door" reason src/macro/pack.py's Step 8a-1
    already established. Never raises; each section degrades to an empty
    list on its own failure so one broken piece can't blank the rest.

    `valen_artifact` is Part 1's own already-written artifact (for the
    no-buy list's "market check red" flag, read from its `stance` block);
    None is fine — that one flag just never fires.
    """
    daily_list = export.get("daily_list") or []
    held_positions = export.get("held_positions") or []
    stance_word = ((valen_artifact or {}).get("stance") or {}).get("stance")

    try:
        rs_leaders = selection.relative_strength_leaders(daily_list)
    except Exception:  # noqa: BLE001
        rs_leaders = []
    try:
        funnel = selection.funnel_counts(daily_list)
    except Exception:  # noqa: BLE001
        funnel = []
    try:
        no_buy = selection.no_buy_list(daily_list, market_stance_word=stance_word)
    except Exception:  # noqa: BLE001
        no_buy = []

    try:
        setups = house.house_setups(daily_list, held_positions)
    except Exception:  # noqa: BLE001
        setups = []
    setups_status = export.get("setups_status") or {
        "status": "not_run",
        "reason": "this export predates measured setups (no setups_status)"}

    try:
        entries = execution.entry_candidates(daily_list)
    except Exception:  # noqa: BLE001
        entries = []
    try:
        breaches = execution.stop_breaches(held_positions)
    except Exception:  # noqa: BLE001
        breaches = []

    try:
        held_facts = management.held_book_facts(held_positions)
    except Exception:  # noqa: BLE001
        held_facts = []
    try:
        from src.data import trade_history
        streak = trade_history.load_streak()
    except Exception as exc:  # noqa: BLE001
        streak = {"status": "UNAVAILABLE", "reason": str(exc)}

    return {
        "selection": {"relative_strength": rs_leaders, "funnel": funnel,
                     "no_buy_list": no_buy},
        "house": {"setups": setups, "status": setups_status},
        "execution": {"entries": entries, "stop_breaches": breaches},
        "management": {"held_facts": held_facts, "streak": streak},
    }


def run_valen_full() -> dict:
    """Part 1 rebuilt fresh PLUS Parts 2-6 re-attached from today's export.

    The page's "Run VALEN read" button used to call run_valen() alone and
    write the result over valen_dashboard.json -- which silently deleted
    Step 8a-1b's selection/house/execution/management sections, so Part 3
    read "No setup pattern flagged today" when nothing had been computed
    at all (PM caught it 2026-10-05). Now the button re-runs both halves.
    If the export is missing or the playbook fails, the artifact carries a
    `playbook_status` saying so, and the page shows that instead of an
    empty list."""
    from src.data.paths import EXPORT_JSON
    art = run_valen()
    if not EXPORT_JSON.exists():
        art["playbook_status"] = {"status": "UNAVAILABLE",
                                  "reason": "no daily export on disk to read"}
        return art
    try:
        export = json.loads(EXPORT_JSON.read_text(encoding="utf-8"))
        art.update(run_playbook(export, art))
        art["playbook_status"] = {"status": "OK"}
    except Exception as exc:  # noqa: BLE001 -- Part 1 still renders
        art["playbook_status"] = {"status": "UNAVAILABLE",
                                  "reason": f"playbook failed: {exc}"}
    return art


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
        "gex": card.gex_block(artifact),
        "crown_cockpit": card.crown_cockpit_block(artifact),
        "history": card.history_rows(artifact),
        "neighbourhood": card.neighbourhood_lines(artifact),
        "theme_leaders": card.theme_leaders_table(artifact),
        "rotation": card.rotation_table(artifact),
        "selection": card.selection_block(artifact),
        "house": card.house_block(artifact),
        "execution": card.execution_block(artifact),
        "management": card.management_block(artifact),
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
