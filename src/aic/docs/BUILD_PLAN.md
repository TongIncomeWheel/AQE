# AIC POC — Build Plan (Session 1)

**Source spec:** `C:\Users\ashtz\Downloads\AEGIS_POC_BUILD_SPEC_v2.md` (v2.0, ~3,266 lines, 12 voices, 6 protocols, 20 screens)
**Session window:** 5 hours autonomous (PM returns for UAT)
**Authoring constraint:** Spec says AQE is FROZEN — no modifications to `src/scanner/`, `src/engines/`, `src/analyzer/`, `src/data/`, `src/ui/`, `src/pipeline/`, `src/backtest/`, `src/calibration/`. All new code lives under `src/aic/`.

---

## 1. Spec assessment

The spec defines a **complete trading-committee system** on top of AQE: 12 LLM voices (8 Deliberation + 4 Risk & Structure, all `claude-opus-4-6`), an Alfred orchestrator (`claude-sonnet-4-6`), six automated protocols (A–F), a 9am SGT scheduler, Telegram/Drive/IBKR integrations, and a 20-screen web UI. Realistic build is multi-week; the 5-hour window can only deliver high-quality foundations. The UI (Section 14) is a separate frontend build entirely.

**Spec status flag** (worth re-noting): the spec itself says *"Status: DRAFT — Awaiting PM + UX Specialist + Investment Specialist diligence review"* and *"If Claude Code identifies a conflict between this spec and AQE's existing code: STOP. Surface the conflict to PM. Do not resolve autonomously."* I'm proceeding because you instructed me to, but conflicts (below) are surfaced here rather than resolved silently.

---

## 2. Structural conflicts surfaced

### 2.1 Directory layout — spec assumes top-level dirs, project uses `src/`

Spec specifies:
```
EXISTING (frozen):          NEW (extension):
aqe/, srm/, dor/            alfred/, committee/, protocols/, scheduler/, delivery/, ui_extension/
```

Actual project has the AQE code under `src/scanner/`, `src/engines/`, `src/analyzer/`, `src/data/`, `src/pipeline/`, `src/ui/` — not under `aqe/`.

**Decision:** All new code goes under **`src/aic/`** (Aegis Investment Committee), mirroring the spec's intended structure as sub-packages:

```
src/aic/
├── config/        # credentials.py + template (spec section: Credentials)
├── charter/       # Charter v1.8.2 embed (cached system context)
├── prompts/       # voice prompt template + speed-learning summaries
├── alfred/        # orchestrator (PTRS gate, regime, universe cap, LLM client)
├── committee/     # 8-voice Deliberation Cell + 4-voice Risk Cell + literature loader
├── protocols/     # A–F automation entry points
├── state/         # SQLite session state
├── data/          # AQE export reader + DSG-13 extender
├── scheduler/     # 9am SGT runner (schedule library)
├── delivery/      # Telegram client (stub, no credentials in spec)
└── docs/          # BUILD_PLAN.md, STATUS.md
```

This honours *"DO NOT modify any existing AQE Python engine files"* and *"This build is an EXTENSION, not a replacement"* while fitting the project's actual `src/` layout. Nothing under `src/scanner/`, `src/engines/`, etc. is touched.

### 2.2 AQE engine file naming — spec names don't match reality

Spec lists `flow_engine.py`, `energy_engine.py`, `structure_engine.py`, etc. Actual files are `src/engines/flow.py`, `src/engines/energy.py`, `src/engines/structure.py`. The frozen-files mandate applies to the actual files (under `src/engines/`); the spec's filenames are not authoritative for what to *preserve*. Names map cleanly.

### 2.3 AQE export schema — Appendix B uses different field names than the current export

The current `aqe_daily_export.json` (built by `src/data/drive_sync.py`) has structured `top_picks`, `longlist`, `watchlist`, `srm`, etc. — recently extended with Fibonacci, R/R, Elder-5d, beta_30d/60d, SRM trend (your last few sessions).

Spec Appendix B shows a different top-level shape: `export_date`, `export_time`, `regime`, `srm` (with `gics_deploy`/`gics_hold`/...), `top_picks` (flat fields including `dsg07_flag`, `bd_count`, `bd_mode`, `atr_comp_ratio`, `rs_vs_spy`, `nr7`, `nr4`), plus the DSG-13 additive fields (`sector_corr`, `breakout_stop`, `gics_sector`, `sma_distance_pct`, `held`).

**Decision:** I do **not** restructure the existing export to match Appendix B (that would violate *"DO NOT alter the existing AQE daily export JSON structure"*). The AIC layer adapts to whatever the existing export emits — see `src/aic/data/aqe_reader.py`. The only AQE-side change permitted by the spec is **additive** DSG-13 fields, which I implement as a *post-processor* (`src/aic/data/dsg13_extender.py`) that reads the existing export, computes the 5 DSG-13 fields per entry, and writes them back to the same JSON file. Existing AQE Python code is not modified.

### 2.4 Voice prompt files — `prompts/{voice}_system.md` vs. templated builder

Spec calls for `prompts/{voice}_system.md` files plus a literature loader. I implement both: voice configs in Python (`voice_config.py`) drive a templated prompt builder (`prompt_builder.py`), and the builder serialises full prompts to markdown on demand. This keeps the 12 voices DRY (single source of truth for the Appendix C template) while still emitting the `.md` files the spec expects.

### 2.5 Charter v1.8.2 source text — referenced but not embedded

The spec references *"Charter v1.8.2 embedded as cached context block"* in Alfred's system prompt and in voice prompts, but the actual Charter document is not in the spec or in this repo. I assemble a `charter_v1_8_2.md` from the gate sequence, PTRS formula, regime tiers, protocol descriptions, and §3A/§3B governance rules that ARE explicit in the spec. **Anything not derivable from the spec is marked as `<<<CHARTER_GAP — PM TO POPULATE>>>`** — flagged for you to fill in.

---

## 3. Scope for this 5-hour session

### Delivered (this session)

| Layer | Module | What |
|---|---|---|
| Config | `config/credentials.py` + template | All required fields blank with `CredentialsMissingError` startup guard. Added to `.gitignore`. |
| Charter | `charter/charter_v1_8_2.md` | Spec-derivable charter content; gaps flagged. |
| Voice prompts | `prompts/voice_config.py`, `prompts/speed_learning.py`, `prompts/prompt_builder.py` | 12 voice configs + speed-learning defaults extracted from spec §5 + §6 + Appendix C template. Emits `prompts/{voice}_system.md` files. |
| Alfred | `alfred/orchestrator.py` | Real Python: PTRS gate (≥65 binary), regime classifier (VIX → GREEN/YELLOW/ORANGE/RED), CM computation (SH+RA+RL), universe cap (≤10), all 8 gates per Charter §9. |
| Alfred | `alfred/llm_client.py` | Anthropic SDK wrapper: model routing (Opus 4.6 for voices, Sonnet 4.6 for Alfred), prompt caching (`cache_control: ephemeral`), cost tracking per spec §13, 529 retry with backoff. |
| Committee | `committee/deliberation_cell.py` | Sequential 8-voice runner; vote tally (5/8 threshold); avg conviction; 8/8 ↔ Steenbarger Inversion trigger; cost logging. |
| Committee | `committee/risk_cell.py` | Sequential 4-voice runner; sizing vote tally (3/4 majority for FULL/HALF/QUARTER); Elder hard-block check (combined stop-out >5%). |
| Committee | `committee/literature_loader.py` | Per spec section "Literature Upload Holding Area" — parses spec slots, falls back to defaults. |
| Data bridge | `data/aqe_reader.py` | Reads existing `output/aqe_daily_export.json`. Adapts to actual schema (not spec Appendix B). |
| Data bridge | `data/dsg13_extender.py` | Computes `sector_corr`, `breakout_stop`, `gics_sector`, `sma_distance_pct`, `held` and appends to existing export entries — additive only. |
| State | `state/db.py` | SQLite schema per spec §12 (sessions, position_state, pipeline_state, cost_log). |
| Protocols | `protocols/protocol_a_premarket.py` … `protocol_f_emergency.py` | Skeleton entry points that compose the orchestrator + cells. External-integration steps stubbed where credentials/services aren't yet wired. |
| Scheduler | `scheduler/runner.py` | Real `schedule` library wiring at 09:00/21:30/04:00/04:30 SGT with trading-day guard. **Not started** by default — entry point only. |
| Docs | `docs/BUILD_PLAN.md` (this file), `docs/STATUS.md` (written at session end) | Decisions + UAT pointers. |

### Deferred (NOT in this session — explicit)

| What | Why deferred | What you'd need |
|---|---|---|
| **The 20-screen UI (Section 14)** | Multi-day frontend build. React + SSE streaming + responsive mobile. | Separate session, ideally a UX engineer or your direction on Streamlit-vs-React. The spec assumes a full SPA. |
| **Real Telegram delivery** | No bot token / chat ID in spec; spec says PM populates tomorrow. | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. |
| **Google Drive PTJ write** | No service-account key. | `GOOGLE_SA_KEY_PATH`, `GOOGLE_DRIVE_FOLDER_ID`. |
| **IBKR Flex reconciliation** | No proxy URL / token. | `IBKR_FLEX_PROXY_URL`, `IBKR_FLEX_TOKEN`. |
| **End-to-end LLM run** | No `ANTHROPIC_API_KEY`. Also: 12 Opus 4.6 calls per deliberation is real money — should be PM-controlled. | `ANTHROPIC_API_KEY` + your green light on first cost. |
| **Charter v1.8.2 full text** | Not in spec — only the parts that flow through gates/PTRS/regime are derivable. | The actual charter PDF or markdown. |
| **Design Cell (§7)** | 6 voices, Sonnet 4.6 — secondary to Deliberation/Risk. Not on the daily critical path. | Lower priority than the deliberation flow. |
| **The `print-trade-journal` SKILL.md reference** | Spec Appendix A points at it. | Either repo path or content. |

---

## 4. How to UAT (when you return)

1. **Read this BUILD_PLAN** and **`src/aic/docs/STATUS.md`** (the latter is the precise "done / pending" list).
2. **Spot-check the voice prompts**: run `python -m src.aic.prompts.prompt_builder` — it emits all 12 system prompts to `src/aic/prompts/_compiled/{voice}_system.md`. Read a couple to confirm the literature + mandate + governance read correctly.
3. **Confirm conflicts (Section 2 above)**: especially the `src/aic/` layout choice and the AQE-export-via-post-processor pattern. Override if you prefer different.
4. **Decide credentials**: fill `src/aic/config/credentials.py` when you want to run an end-to-end LLM deliberation. Until then, the orchestrator code is exercisable as Python logic (gates, PTRS, regime, vote tally) without API calls.
5. **Inspect AQE-side DSG-13 extender**: `python -m src.aic.data.dsg13_extender` enriches the existing `output/aqe_daily_export.json`. Confirm the added fields are sensible before running on real export.
6. **Run the unit-level smoke tests** in the bottom of `STATUS.md`. They exercise PTRS, regime, gate, vote tally, sizing tally — no LLM calls.

---

## 5. Key risks worth flagging

- **API cost shape**: 12 voices × Opus 4.6 × per-deliberation × multiple candidates/day. The spec's caching strategy is correct (literature blocks cached; 90% cost reduction after first call), but the first cold session of the day is still 12 full Opus prompts. Budget visibility is in `state/db.py` `cost_log` and the planned cost-tracking in Settings (S16) — but until the UI is built, watch the SQLite table.
- **The Inversion Mandate UX is half the value**: Steenbarger's 8/8 counter-argument with the scroll-to-bottom proceed gate is a key control. In this session it's wired as `committee/deliberation_cell.py:trigger_inversion()` — the *back-end* is there, but the scroll-to-bottom enforcement is a UI thing and is deferred with the rest of Section 14.
- **AQE schema drift**: I've adapted the AIC reader to your actual export shape (not spec Appendix B). If you later rewrite AQE export to match the spec, the reader needs updating — flagged in `data/aqe_reader.py`.
- **Charter v1.8.2 gaps**: marked inline with `<<<CHARTER_GAP — PM TO POPULATE>>>`. Voice prompts and Alfred reference the charter; until those gaps are filled, behaviour at the edges (e.g. specific protocol-level enforcement clauses not derivable from the spec) is best-effort.

---

*Generated 26 May 2026 by Claude Code build session. Read alongside `STATUS.md` (written at session end).*
