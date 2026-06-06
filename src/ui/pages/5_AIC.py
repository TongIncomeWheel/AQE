"""AIC Committee -- Page 5 of the Streamlit app.

UAT surface for the Aegis Investment Committee POC build. The spec asks for
a 20-screen React SPA (Section 14); this page is the *pragmatic* UAT layer
that matches your existing Streamlit pattern and lets you exercise every
piece of the deterministic core today, without API credentials.

Tabs:
  Overview        what was built, where to read, credential subsystem status.
  Voices          all 12 voice prompts + mandates + speed-learning summaries.
  Gate Tester     interactive 8-gate sequence + PTRS computation -- NO LLM.
  AQE Bridge      what the reader extracts; preview DSG-13 enrichment.
  State           SQLite session state -- pipeline, deliberations, cost log.
  Deliberation    end-to-end qualify_candidate; credential-gated.

Launched via run_app.bat (existing). No terminal interaction.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AIC Committee", page_icon=":scales:", layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login

# Password gate — halts with a sign-in form until authenticated (public Space).
require_login()

import pandas as pd

from src.aic import CHARTER_VERSION, SPEC_VERSION, VERSION
from src.aic.config import is_subsystem_ready
from src.aic.prompts import (
    DELIBERATION_ORDER,
    RISK_STRUCTURE_ORDER,
    VOICES,
    build_voice_prompt,
    get_voice,
)
from src.aic.alfred.orchestrator import (
    RA_FROM_STATUS,
    RL_FROM_LEVEL,
    assess_combined_stopout,
    check_universe_cap,
    classify_regime,
    compute_ptrs,
    run_gate_sequence,
    sector_gate_check,
)
from src.aic.committee.literature_loader import (
    DEFAULT_SPEC_PATH,
    load_literature,
)
from src.aic.state import AICStateDB, DB_PATH

st.title("AIC Committee")
st.caption(
    f"AIC v{VERSION}  ·  Charter {CHARTER_VERSION}  ·  Spec: {SPEC_VERSION}  "
    f"·  AQE preserved (read-only)"
)

# Persistent header showing credential subsystem status -- visible on every tab.
_subsystems = ["anthropic", "fmp", "ibkr_flex", "google_drive", "telegram", "srm_cleanup"]
_status_cols = st.columns(len(_subsystems))
for col, sub in zip(_status_cols, _subsystems):
    ready = is_subsystem_ready(sub)
    label = sub.replace("_", " ").title()
    if ready:
        col.success(f"{label}  ready")
    else:
        col.warning(f"{label}  not set")

tab_overview, tab_voices, tab_gates, tab_bridge, tab_state, tab_delib = st.tabs(
    ["Overview", "Voices (12)", "Gate Tester", "AQE Bridge", "State", "Deliberation"]
)


# ============================================================================
# OVERVIEW
# ============================================================================

with tab_overview:
    st.subheader("Build status")
    st.markdown(
        """
        This page is the **UAT surface** for the AIC POC built per
        `AEGIS_POC_BUILD_SPEC_v2.md`.  All committee code lives under
        `src/aic/`; AQE files (`src/scanner/`, `src/engines/`, `src/analyzer/`,
        `src/data/`, `src/pipeline/`, `src/ui/1-4`) are **frozen** per spec.

        **What is wired and exerciseable now (no credentials):**
        - All 12 voice prompts (Deliberation Cell + Risk & Structure Cell)
        - Alfred orchestrator: PTRS computation, 8-gate sequence, regime
          classifier, DSG-11 sector override, universe cap, combined stop-out
        - AQE bridge reader + DSG-13 additive extender (post-processor)
        - Session-state SQLite (`src/aic/state/aic.db`)
        - All six protocols A-F (Protocol B is fully end-to-end)

        **What waits on credentials in `src/aic/config/credentials.py`:**
        - Real LLM deliberation (Anthropic)
        - Telegram push delivery
        - Google Drive PTJ write
        - IBKR Flex reconciliation
        """
    )

    docs_dir = PROJECT_ROOT / "src" / "aic" / "docs"
    st.markdown(
        f"**Read the docs:**\n"
        f"- [BUILD_PLAN.md](file://{(docs_dir / 'BUILD_PLAN.md').as_posix()})  "
        f"-- scope, conflicts surfaced, decisions and rationale\n"
        f"- [STATUS.md](file://{(docs_dir / 'STATUS.md').as_posix()})  "
        f"-- what is verified, what is deferred, how to UAT"
    )

    st.subheader("Where AQE meets AIC")
    st.markdown(
        """
        The single bridge is the AQE export JSON (`output/aqe_daily_export.json`).
        AQE writes it.  The AIC reader (`src/aic/data/aqe_reader.py`) reads it.
        Zero modification to AQE.  The one allowed addition is the **DSG-13
        post-processor** which appends `sector_corr`, `breakout_stop`,
        `gics_sector`, `sma_distance_pct`, `held` to existing entries.
        """
    )

    st.subheader("Spec deferments visible from here")
    st.markdown(
        """
        - The 20-screen React SPA (spec Section 14) is *not* this Streamlit page.
          This page is the practical UAT layer for the Streamlit project; the
          full SPA is a separate build session.
        - Real LLM calls are credential-gated.  First Anthropic call will spend
          ~12 Opus 4.6 prompts per deliberation (spec §13 estimates ~$2 per).
        - Charter v1.8.2 gaps (`<<<CHARTER_GAP -- PM TO POPULATE>>>`) inline in
          `src/aic/charter/charter_v1_8_2.md`.
        """
    )


# ============================================================================
# VOICES
# ============================================================================

with tab_voices:
    st.subheader("12 Voting Voices")
    st.caption(
        "Deliberation Cell (8 voices, `claude-opus-4-6`) votes on quality.  "
        "Risk & Structure Cell (4 voices, `claude-opus-4-6`) votes on sizing.  "
        "Each voice's system prompt = Appendix C template + the literature "
        "summary below (PM upload override via `literature_loader`)."
    )

    lit = load_literature()
    populated = [k for k, v in lit.items() if v]
    if populated:
        st.info(
            f"Spec literature uploads populated for: {', '.join(populated)}.  "
            f"All other voices use defaults in `prompts/voice_config.py`."
        )
    else:
        st.caption(
            f"No PM literature uploads found in {DEFAULT_SPEC_PATH.name}; "
            "all voices use built-in speed-learning defaults."
        )

    voice_rows = []
    for vid in [*DELIBERATION_ORDER, *RISK_STRUCTURE_ORDER]:
        v = get_voice(vid)
        voice_rows.append({
            "Voice": v.name,
            "Cell": "Deliberation" if v.cell == "deliberation" else "Risk & Structure",
            "Texts": v.texts,
            "Special": v.special_authority or "—",
            "Literature uploaded": "yes" if lit.get(vid) else "default",
        })
    st.dataframe(pd.DataFrame(voice_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    sel = st.selectbox(
        "Inspect a voice's full system prompt",
        options=[*DELIBERATION_ORDER, *RISK_STRUCTURE_ORDER],
        format_func=lambda k: f"{get_voice(k).name}  ({get_voice(k).cell})",
        key="aic_voice_select",
    )
    v = get_voice(sel)
    st.markdown(f"**{v.name}**  ·  {v.title}")
    st.caption(f"Anchor texts: {v.texts}")
    st.markdown(f"**Mandate.**  {v.mandate}")
    if v.special_authority:
        st.warning(f"**Special authority.**  {v.special_authority}")
    st.markdown("**Compiled system prompt** (this is what the LLM receives):")
    st.code(build_voice_prompt(sel, lit.get(sel)), language="markdown")


# ============================================================================
# GATE TESTER
# ============================================================================

with tab_gates:
    st.subheader("Gate sequence + PTRS  ·  pure Python  ·  no LLM call")
    st.caption(
        "Edit the inputs and click *Run gates*.  All 8 gates per Charter §9B "
        "run in order; the first failure short-circuits.  PTRS is computed at "
        "gate 6 using SC_MOMENTUM + (SH + RA + RL)."
    )

    with st.form("aic_gate_form"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            ticker = st.text_input("Ticker", value="ALAB")
            sc_mom = st.number_input("SC_MOMENTUM", 0.0, 100.0, 84.1, step=0.1)
            elder = st.number_input("Elder score", 0.0, 10.0, 8.2, step=0.1)
        with c2:
            flow = st.number_input("Flow_100", 0.0, 100.0, 82.3, step=0.1)
            energy = st.number_input("Energy_100", 0.0, 100.0, 79.1, step=0.1)
            structure = st.number_input("Structure_100", 0.0, 100.0, 88.4, step=0.1)
            mp = st.number_input("MP_100", 0.0, 100.0, 87.2, step=0.1)
        with c3:
            sector_grade = st.selectbox(
                "Sector grade",
                ["DEPLOY", "HOLD", "TURNING", "WATCH", "AVOID"],
                index=0,
            )
            sector_corr = st.number_input(
                "DSG-11 sector_corr (stock vs ETF)", -1.0, 1.0, 0.71, step=0.01,
            )
            rr_to_target = st.number_input("R:R vs committee target", 0.0, 20.0, 3.2, step=0.1)
            sma_dist = st.number_input("SMA20 distance (%)", -100.0, 100.0, 4.2, step=0.1)
        with c4:
            ra_status = st.selectbox(
                "RA status (Dalio voice owns)",
                ["ALIGNED", "NEUTRAL", "MISALIGNED"],
                index=0,
            )
            vix = st.number_input("VIX", 0.0, 100.0, 17.0, step=0.1)
            pipeline_count = st.number_input(
                "Pipeline count (BRACKET + WATCH)", 0, 20, 8, step=1,
            )
            universe_cap = st.number_input("Universe cap", 1, 20, 10, step=1)
        submitted = st.form_submit_button("Run gates", type="primary")

    if submitted:
        result = run_gate_sequence(
            ticker=ticker, sc_momentum=sc_mom, elder_score=elder,
            flow_100=flow, energy_100=energy, structure_100=structure, mp_100=mp,
            sector_grade=sector_grade, sector_corr=sector_corr,
            rr_to_committee_target=rr_to_target, sma_distance_pct=sma_dist,
            ra_status=ra_status, vix=vix,
            pipeline_count=int(pipeline_count), universe_cap=int(universe_cap),
        )

        if result.qualified:
            st.success(
                f"**{ticker}** passes all 8 gates and would advance to "
                "Deliberation Cell."
            )
        else:
            st.error(
                f"**{ticker}** REJECTED at **{result.failed_gate}**.  "
                f"Reason logged.  STOP."
            )

        gate_df = pd.DataFrame([
            {
                "#": i + 1,
                "Gate": g.name,
                "Result": "PASS" if g.passed else "FAIL",
                "Detail": g.detail,
            }
            for i, g in enumerate(result.gates)
        ])
        st.dataframe(gate_df, use_container_width=True, hide_index=True)

        if result.ptrs is not None:
            p = result.ptrs
            cm = p.cm
            kpi = st.columns(6)
            kpi[0].metric("PTRS", f"{p.ptrs:.1f}", "qualified" if p.qualified else "rejected")
            kpi[1].metric("SC_MOMENTUM", f"{p.sc_momentum:.1f}")
            kpi[2].metric("SH", f"{p.sh:+d}")
            kpi[3].metric("RA", f"{p.ra:+d}")
            kpi[4].metric("RL", f"{p.rl:+d}", p.regime)
            kpi[5].metric("CM (SH+RA+RL)", f"{cm:+d}")
            for note in p.notes:
                st.caption(note)

        st.subheader("Side checks")
        cap = check_universe_cap(int(pipeline_count), int(universe_cap))
        st.caption(f"Universe cap  ·  {cap.message}")
        sg = sector_gate_check(sector_grade, sector_corr, ptrs=sc_mom)
        st.caption(
            f"Sector gate (Charter §4B.4)  ·  treatment = `{sg.treatment}`, "
            f"passes = `{sg.passes}`.  {sg.note}"
        )
        regime = classify_regime(vix)
        st.caption(f"Regime classifier  ·  VIX {vix:.2f} -> **{regime}** "
                   f"(RL = {RL_FROM_LEVEL[regime]:+d})")

        st.markdown("---")
        st.markdown("**Combined stop-out (Elder hard-block trigger, Charter §6A).** "
                    "Edit your open positions below and a proposed candidate:")
        col_l, col_r = st.columns(2)
        with col_l:
            ex_text = st.text_area(
                "Existing open positions (one per line: entry,stop,shares)",
                value="100,95,100\n50,48,200",
                height=120,
            )
        with col_r:
            cap_usd = st.number_input("Dynamic capital (USD)", 1.0, 1e9, 70200.0, step=100.0)
            prop_entry = st.number_input("Proposed entry", 0.0, 1e6, 145.0, step=0.1)
            prop_stop = st.number_input("Proposed stop", 0.0, 1e6, 138.5, step=0.1)
            prop_shares = st.number_input("Proposed shares", 0, 100000, 100, step=1)

        positions = []
        for line in ex_text.strip().splitlines():
            try:
                e, s, n = [x.strip() for x in line.split(",")]
                positions.append({"entry": float(e), "stop": float(s), "shares": int(n)})
            except Exception:
                continue
        so = assess_combined_stopout(
            open_positions=positions,
            proposed_entry=prop_entry,
            proposed_stop=prop_stop,
            proposed_shares=int(prop_shares),
            dynamic_capital_usd=cap_usd,
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Existing risk", f"${so.existing_risk_usd:,.0f}")
        c2.metric("Proposed risk", f"${so.proposed_risk_usd:,.0f}")
        c3.metric("Combined", f"${so.combined_usd:,.0f}", f"{so.combined_pct:.2f}%")
        c4.metric("vs 5% cap", "BREACH" if so.breaches_5pct else "OK",
                  delta_color="inverse" if so.breaches_5pct else "normal")
        if so.breaches_5pct:
            st.error(
                "Combined stop-out exceeds 5% of capital -- Elder hard-block "
                "would BLOCK this candidate per Charter §6A regardless of Risk "
                "Cell vote."
            )


# ============================================================================
# AQE BRIDGE
# ============================================================================

with tab_bridge:
    st.subheader("AQE export reader  ·  the only bridge from AQE to AIC")

    export_path = PROJECT_ROOT / "output" / "aqe_daily_export.json"
    if not export_path.exists():
        st.warning(
            f"AQE export not found at `{export_path}`.  Run the daily pipeline "
            "first (see Scanner page sidebar)."
        )
    else:
        try:
            from src.aic.data.aqe_reader import iter_candidates, load_export
        except Exception as e:                              # noqa: BLE001
            st.error(f"AQE reader import failed: {e}")
        else:
            export = load_export(export_path)
            meta_cols = st.columns(5)
            meta_cols[0].metric("Date", str(export.get("date", "—")))
            meta_cols[1].metric("Regime",
                                (export.get("regime") or {}).get("level", "—"))
            meta_cols[2].metric("Longlist",
                                len(export.get("longlist") or []))
            meta_cols[3].metric("Watchlist",
                                len(export.get("watchlist") or []))
            meta_cols[4].metric("DSG-13 enriched",
                                "yes" if export.get("dsg13_enriched") else "no")

            source = st.radio(
                "Section",
                ["longlist", "watchlist", "top_picks", "edge_list"],
                horizontal=True,
            )
            rows = []
            for c in iter_candidates(export, source=source):
                rows.append({
                    "Ticker": c.ticker,
                    "SC_MOM": c.sc_momentum,
                    "Elder": c.elder_score,
                    "PipeRk": c.pipe_rank,
                    "Sector": c.gics_sector or "—",
                    "Grade": c.sector_grade or "—",
                    "sector_corr": c.sector_corr,
                    "sma_dist_%": c.sma_distance_pct,
                    "breakout_stop": c.breakout_stop,
                    "held": c.held,
                    "Beta30/60": (
                        f"{c.beta_30d}/{c.beta_60d}" if c.beta_30d is not None else "—"
                    ),
                    "Elder5d": ",".join(str(int(v)) for v in (c.elder_5d or [])) or "—",
                    "Entry": c.entry,
                    "DSL stop": c.stop,
                    "rr_est": c.rr_est,
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            else:
                st.info(f"No entries in `{source}`.")

            st.markdown("---")
            st.markdown(
                "**DSG-13 enrichment** (`src/aic/data/dsg13_extender.py`) "
                "appends `sector_corr`, `breakout_stop`, `gics_sector`, "
                "`sma_distance_pct`, `held` to every entry.  This is a "
                "post-processor; the existing AQE export-writer in "
                "`src/data/drive_sync.py` is *not* modified."
            )
            if st.button("Run DSG-13 enrichment on the export now", type="primary"):
                with st.spinner("Enriching..."):
                    from src.aic.data.dsg13_extender import enrich_export
                    result = enrich_export(export_path)
                counts = (result.get("dsg13_enriched") or {}).get("counts", {})
                st.success(
                    "DSG-13 enrichment complete.  Entries updated per section: "
                    f"{counts}."
                )


# ============================================================================
# STATE
# ============================================================================

with tab_state:
    st.subheader("Session state  ·  SQLite")
    st.caption(f"DB: `{DB_PATH.relative_to(PROJECT_ROOT)}`")
    db = AICStateDB()

    pipeline = db.list_pipeline()
    st.markdown(f"**Pipeline** ({len(pipeline)} entries)")
    if pipeline:
        st.dataframe(pd.DataFrame(pipeline), use_container_width=True, hide_index=True)
    else:
        st.info("Pipeline is empty.  Entries land here when Protocol B advances "
                "candidates to WATCH or BRACKET.")

    st.markdown("---")
    st.markdown("**Recent deliberations**")
    import sqlite3
    with sqlite3.connect(str(DB_PATH)) as conn:
        rows = conn.execute(
            "SELECT created_at, ticker, decision, approvals, abstentions, "
            "rejections, ROUND(avg_conviction,2), inversion_required, sizing, "
            "ROUND(cost_usd,4) "
            "FROM deliberations ORDER BY created_at DESC LIMIT 25"
        ).fetchall()
        cost_rows = conn.execute(
            "SELECT model, voice, COUNT(*), ROUND(SUM(cost_usd),4), "
            "SUM(input_tokens), SUM(output_tokens), SUM(cache_tokens) "
            "FROM cost_log GROUP BY model, voice ORDER BY 4 DESC"
        ).fetchall()

    if rows:
        st.dataframe(
            pd.DataFrame(
                rows,
                columns=["When", "Ticker", "Decision", "Approve", "Abstain",
                         "Reject", "AvgConv", "Inversion", "Sizing", "Cost ($)"],
            ),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No deliberations recorded yet.")

    st.markdown("---")
    st.markdown("**Cost log (grouped by model + voice)**")
    if cost_rows:
        st.dataframe(
            pd.DataFrame(
                cost_rows,
                columns=["Model", "Voice", "Calls", "Cost ($)",
                         "Input tok", "Output tok", "Cache tok"],
            ),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("No LLM calls logged yet (credentials not populated or no run executed).")


# ============================================================================
# DELIBERATION (credential-gated)
# ============================================================================

with tab_delib:
    st.subheader("Run a deliberation  ·  Protocol B end-to-end")
    if not is_subsystem_ready("anthropic"):
        st.warning(
            "Anthropic API key missing in `src/aic/config/credentials.py`.  "
            "The full deliberation chain (8 voices -> Inversion -> 4 voices) "
            "needs this populated.  The credential safety guard "
            "(`assert_required('anthropic')`) blocks any LLM call until then.  "
            "All other tabs work without credentials."
        )

    st.markdown(
        "When credentials are set, this tab fires `qualify_candidate()` from "
        "`src/aic/protocols/protocol_b_qualification.py` on a candidate of "
        "your choice -- runs the 8 gates, then 8-voice Deliberation, then "
        "Steenbarger Inversion if 8/8 unanimous, then 4-voice Risk Cell, "
        "then prints the full execution brief.  Each voice's cost is logged "
        "to the State tab above."
    )

    st.markdown(
        "**First run estimate**: ~$2 of Anthropic Opus 4.6 spend per "
        "deliberation per spec §13.  Subsequent calls within the cache TTL "
        "benefit from prompt caching (90% reduction on the system prompt "
        "block) -- watch the cache-tokens column on the State tab to confirm."
    )

    # The actual LLM-fire button is intentionally NOT wired here yet.  The
    # safety pattern is: PM populates credentials -> rerun this page -> the
    # warning above clears -> next session wires the button to call
    # qualify_candidate(...).  This avoids any chance of an accidental
    # expensive run during UAT.
    st.info(
        "Live-fire button intentionally deferred until credentials are "
        "populated and a per-session $ ceiling is agreed.  Next session wires "
        "the button to `qualify_candidate(...)` against an AQE longlist entry "
        "of your choosing."
    )
