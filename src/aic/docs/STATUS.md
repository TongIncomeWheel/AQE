# AIC POC Build — Session 1 STATUS

> **Read this with [BUILD_PLAN.md](BUILD_PLAN.md).** The plan covers *what I committed to build and the conflicts I surfaced*. This file is the *what's actually on disk now, what's verified, and how to UAT it*.

**Spec:** `C:\Users\ashtz\Downloads\AEGIS_POC_BUILD_SPEC_v2.md` (v2.0)
**AQE preservation:** zero AQE files modified. The only AQE-export change is via `src/aic/data/dsg13_extender.py`, a post-processor that appends DSG-13 additive fields to the existing JSON without touching any `src/scanner`, `src/engines`, `src/analyzer`, `src/data`, `src/pipeline`, or `src/ui` file.

---

## 1. What is on disk

All new code lives under `src/aic/`. The complete file inventory:

```
src/aic/
├── __init__.py                            ← package version / spec / charter pointers
├── config/
│   ├── __init__.py                        ← exports CredentialsMissingError, assert_required, ...
│   ├── credentials.py                     ← BLANK — PM populates (gitignored)
│   ├── credentials_template.py            ← BLANK reference; copy from here on reset
│   └── aic_config.py                      ← startup guard + per-subsystem checks
├── charter/
│   └── charter_v1_8_2.md                  ← spec-derivable charter; gaps flagged inline
├── prompts/
│   ├── __init__.py
│   ├── voice_config.py                    ← 12 voice configs + default speed-learning summaries
│   ├── prompt_builder.py                  ← Appendix C template + cache-control blocks
│   ├── alfred_system.md                   ← Alfred system prompt (Sonnet 4.6)
│   └── _compiled/
│       ├── lynch_system.md                ← 12 compiled prompts emitted by prompt_builder
│       ├── oneil_system.md
│       ├── wyckoff_system.md
│       ├── raschke_system.md
│       ├── steenbarger_system.md
│       ├── thorp_system.md
│       ├── seow_system.md
│       ├── druckenmiller_system.md
│       ├── elder_system.md
│       ├── shannon_system.md
│       ├── dalio_system.md
│       └── murphy_system.md
├── alfred/
│   ├── __init__.py
│   ├── orchestrator.py                    ← PURE PYTHON: PTRS, gate sequence, regime, sector gate,
│   │                                        DSG-11 override, universe cap, combined stop-out
│   └── llm_client.py                      ← Anthropic SDK wrapper (Opus/Sonnet routing, caching, 529 retry)
├── committee/
│   ├── __init__.py
│   ├── deliberation_cell.py               ← 8-voice sequential runner + vote tally + Inversion trigger
│   ├── risk_cell.py                       ← 4-voice sequential sizing vote + Elder hard-block
│   ├── literature_loader.py               ← parses PM-uploaded slots from the spec; falls back to defaults
│   └── vote_parser.py                     ← extracts ANCHOR/ASSESSMENT/VOTE/CONVICTION/CONDITION from voice text
├── data/
│   ├── __init__.py
│   ├── aqe_reader.py                      ← reads aqe_daily_export.json into CandidateBrief
│   └── dsg13_extender.py                  ← additive DSG-13 fields: sector_corr, breakout_stop,
│                                            gics_sector, sma_distance_pct, held
├── state/
│   ├── __init__.py
│   ├── db.py                              ← SQLite schema + CRUD (sessions, pipeline, cost_log,
│   │                                        deliberations, inversions)
│   └── aic.db                             ← initialised; empty (gitignored)
├── protocols/
│   ├── __init__.py
│   ├── protocol_a_premarket.py            ← 09:00 SGT — stop audit, regime, SRM, pipeline×AQE, new names
│   ├── protocol_b_qualification.py        ← gate → PTRS → Deliberation → (Inversion) → Risk Cell — MOST COMPLETE
│   ├── protocol_c_position_mgmt.py        ← DSG-10 trail-tier math (Tier 0–4)
│   ├── protocol_d_close.py                ← 04:00 SGT close brief + PTJ trigger stub
│   ├── protocol_e_weekly.py               ← weekly scorecard via SQLite aggregates
│   └── protocol_f_emergency.py            ← RED regime / stop-out breach / FMP outage / API overloaded alerts
├── scheduler/
│   ├── __init__.py
│   └── runner.py                          ← schedule library wiring + trading-day guard (Mon–Fri + holidays)
├── delivery/
│   ├── __init__.py
│   ├── telegram_client.py                 ← Telegram sendMessage with retry + local fallback log
│   └── brief_formatters.py                ← Telegram-text formatters for S02/S11/S12 (single source)
├── web/                                   ← NEW (session 2) — NiceGUI brief frontend
│   ├── __init__.py
│   ├── theme.py                           ← spec §14.1 design tokens + global CSS
│   ├── components.py                      ← page_header, kpi, mono_table, srm_bands, priority_list, footer
│   ├── brief_data.py                      ← compose_premarket/open/close (single source for web + telegram)
│   ├── views_premarket.py                 ← S02 web view
│   ├── views_open.py                      ← S11 web view
│   ├── views_close.py                     ← S12 web view
│   ├── app.py                             ← NiceGUI entrypoint, route registration, shell
│   └── smoke_test.py                      ← no-server import + compose + format check
└── docs/
    ├── BUILD_PLAN.md                      ← scope, conflicts, decisions
    └── STATUS.md                          ← THIS FILE
```

Plus surrounding edits in session 2:

- `run_aic_web.bat` — Windows double-click launcher for the brief server (http://localhost:8765).
- `.gitignore` — added `src/aic/state/telegram_alerts.log.jsonl`.
- `src/aic/alfred/orchestrator.py` — `assess_combined_stopout` now tolerates None entry/stop/shares (option rows in PTJ).

Plus surrounding edits:

- `.gitignore` — added `src/aic/config/credentials.py`, `src/aic/state/*.db*`, `src/aic/prompts/_compiled/`.
- `requirements.txt` — added `anthropic>=0.39`, `schedule>=1.2`, `pytz>=2024.1` as **AIC dependencies**. The existing AQE deps are untouched.

---

## 2. What is verified (no LLM credentials needed)

All checks below ran successfully at the end of the session:

| Check | Command | Result |
|---|---|---|
| Compile-clean across all 22 AIC files | `python -m py_compile ...` | ✓ FULL AIC COMPILE OK |
| Voice prompts assemble + write to disk | `python -m src.aic.prompts.prompt_builder` | ✓ 12 files, ~4-5 KB each |
| Regime classifier (VIX → tier) | inline smoke | ✓ 15→GREEN, 22→YELLOW, 28→ORANGE, 35→RED |
| PTRS math (strong case) | inline | ✓ sc_mom 78 + CM 10 → 88.0 qualified |
| PTRS math (weak case) | inline | ✓ sc_mom 55 + CM −8 → 47.0 rejected, gap +18 |
| 8-gate sequence (ALAB scenario) | inline | ✓ all 8 pass, PTRS 94.1 |
| DSG-11 idiosyncratic override (AVOID + corr 0.20 + PTRS 72) | inline | ✓ passes via override |
| Combined stop-out arithmetic | inline | ✓ existing $900 + proposed $650 = $1,550 (2.21%) — below 5% |
| Universe cap check (9/10) | inline | ✓ warning state, not at cap |
| Literature loader against the real spec file | `python -m src.aic.committee.literature_loader` | ✓ 14 slots parsed |
| Vote parser on a synthetic Lynch response | inline | ✓ vote=APPROVE, conviction=8, anchor + condition extracted |
| Session-state SQLite init | `python -m src.aic.state.db` | ✓ DB created, 0 active pipeline names |

---

## 2b. What is verified — session 2 (NiceGUI briefs)

| Check | Command | Result |
|---|---|---|
| Web smoke (composers + formatters + module imports) | `python -m src.aic.web.smoke_test` | ✓ All 7 checks pass — 0 stops case + 7-position case both render |
| NiceGUI app boots | `python -m src.aic.web.app --port 8765` | ✓ Server up |
| HTTP 200 on all 7 routes | `curl /, /brief/{premarket,open,close}, /telegram/{premarket,open,close}` | ✓ All 200 |
| Pre-market data composer hits real export | inline | ✓ 7 stops, 10 new AQE candidates, regime GREEN VIX 16.60 |
| Telegram pre-market text under 40-line cap | smoke | ✓ 34 lines, web link footer present |
| Telegram open text format | smoke | ✓ 14 lines |
| Telegram close text format | smoke | ✓ 15 lines |
| Real ticker data flows to renderers | grep telegram preview | ✓ S/WDC/MKSI/SFM/ADM/TRGP/RKLB present |

---

## 3. What's deferred (explicit)

- **The remaining 17 screens (spec Section 14).** Session 2 built S02/S11/S12 (the three daily briefs the PM reads on mobile). Still deferred: S01 credentials, S03–S07 dashboard tabs, S08 deliberation overlay, S09 inversion modal, S10 risk-cell sizing, S13 PTJ confirmation, S14 rejection flow, S15 Elder hard-block, S16 settings, S17/S18 error states, S19 universe cap banner, S20 RED regime alert.
- **Real LLM calls.** The Anthropic SDK is wired but `ANTHROPIC_API_KEY` is empty. The first deliberation will cost real money (12 Opus 4.6 calls + the literature blocks cached after call 1); ~$2/deliberation per spec estimates.
- **Telegram delivery.** Client is built; `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` empty. Calls are logged to `state/telegram_alerts.log.jsonl` until credentials are populated.
- **Google Drive PTJ write.** No service-account key. PTJ auto-run in `protocol_d_close.py` is a stub.
- **IBKR Flex reconciliation.** No proxy URL / token. Position state is currently fed from existing `data/open_positions.json` only.
- **The Design Cell (spec §7).** Lower priority than the daily critical path.
- **Real-bar back-fill for trail tier (Protocol C).** `compute_trail` is correct; needs the peak-close-since-entry sweep from `panel_daily.parquet` to be invoked per open position.
- **A real NYSE holiday calendar.** Currently a hard-coded list in `scheduler/runner.py` for 2026. Swap for `pandas_market_calendars` when ready.

---

## 4. How to UAT (in order)

### Step 0 — open the brief web UI (NEW, session 2)

Double-click `run_aic_web.bat` at the project root. The NiceGUI server starts on
`http://localhost:8765`. Open it in any browser (mobile-first, but it scales).

```
/                       index — links to all six brief views
/brief/premarket        S02  — pre-market brief (read at 09:00 SGT)
/brief/open             S11  — market-open brief (21:30 SGT)
/brief/close            S12  — market-close brief (04:00 SGT)
/telegram/premarket     S02 raw text preview (what the Telegram bot will push)
/telegram/open          S11 raw text preview
/telegram/close         S12 raw text preview
```

What to UAT:
1. **Pre-market brief** should show the regime badge (GREEN/YELLOW/ORANGE/RED), VIX, capital, the open-positions stop audit, SRM bands, the pipeline × AQE cross-reference, the New-In-AQE candidates, and the priority actions block.
2. **Telegram preview** should be the same data compressed to under 40 lines with the emoji conventions from spec §14.6a (✅ / ⚠️ / 🔴, ▲/━/▼ for SRM grades).
3. **Market-open** + **market-close** briefs render even with zero pipeline state — they degrade gracefully so PM can use the UI before the first scheduler run.

Close the .bat window to stop the server. The Streamlit AQE pages (1_Scanner, 5_AIC, etc.) are unaffected.

### Step 1 — read the two docs
- `src/aic/docs/BUILD_PLAN.md` — the contract for this session: scope, conflicts surfaced, decisions and rationale.
- `src/aic/docs/STATUS.md` (this file) — what's actually on disk.

### Step 2 — read 3 compiled voice prompts
The 12 voice prompts are emitted to `src/aic/prompts/_compiled/`. Skim:
- `lynch_system.md` (a deliberation voice — should anchor on Lynch's Ten-Bagger / PEG framework)
- `steenbarger_system.md` (owns the Inversion Mandate — that special authority is explicit at the top)
- `elder_system.md` (Risk Cell — should anchor on 2% rule + combined stop-out hard-block)

Confirm: each prompt cites the right canonical texts, the right mandate, the right vote schema (APPROVE/REJECT/ABSTAIN for deliberation; FULL/HALF/QUARTER/BLOCK for risk).

### Step 3 — exercise the deterministic logic (no API credentials)
```bash
cd "C:/Users/ashtz/Backtest Engine"
python - <<'EOF'
from src.aic.alfred.orchestrator import (
    run_gate_sequence, compute_ptrs, check_universe_cap,
    sector_gate_check, assess_combined_stopout, classify_regime,
)
# Walk through the 8 gates on a real-ish candidate:
r = run_gate_sequence(
    ticker="ALAB",
    sc_momentum=84.1, elder_score=8.2,
    flow_100=82.3, energy_100=79.1, structure_100=88.4, mp_100=87.2,
    sector_grade="DEPLOY", sector_corr=0.71,
    rr_to_committee_target=3.2, sma_distance_pct=4.2,
    ra_status="ALIGNED", vix=17.0, pipeline_count=8,
)
print("qualified:", r.qualified, " ptrs:", r.ptrs.ptrs)
for g in r.gates: print(" ", "OK" if g.passed else "FAIL", g.name, g.detail)
EOF
```
This is the heart of Alfred. If you change the inputs you can stress-test every gate, including the DSG-11 override and the 5% combined stop-out.

### Step 4 — try the DSG-13 enrichment on your existing AQE export
```bash
python -m src.aic.data.dsg13_extender
```
This reads `output/aqe_daily_export.json`, computes the 5 additive fields for every `top_picks`/`longlist`/`watchlist` entry, and rewrites the same file. After running, look at any longlist entry — it should now have `sector_corr`, `breakout_stop`, `gics_sector`, `sma_distance_pct`, `held` appended. **Existing AQE fields are untouched.**

### Step 5 — populate credentials when ready to wire the LLM
Edit `src/aic/config/credentials.py` (gitignored). The minimum needed for an end-to-end deliberation is `ANTHROPIC_API_KEY`. Then:
```bash
pip install anthropic schedule pytz   # per the updated requirements.txt
python - <<'EOF'
from src.aic.committee.deliberation_cell import run_deliberation_cell
# WARNING: this fires 8 real Opus 4.6 calls — real money.
candidate_brief = {"ticker": "ALAB", "sc_momentum": 84.1, "...": "..."}  # fill in
session_state = {"regime": "GREEN", "vix": 17.0, "open_positions": []}
result = run_deliberation_cell(candidate_brief, session_state)
print(result.decision, result.approvals, "/8", "conviction", result.avg_conviction)
EOF
```
The literature loader will use any text you paste into the spec markdown's `<<<VOICE_LITERATURE_START>>>…<<<VOICE_LITERATURE_END>>>` slots; otherwise it uses the defaults in `voice_config.py`.

### Step 6 — scheduler dry-run (no credentials needed)
```bash
python -m src.aic.scheduler.runner
```
This starts the schedule loop. With no credentials, each handler simply prints when it fires. Use it to confirm the trading-day guard + the four SGT triggers are correct for your timezone.

---

## 5. What needs PM input (charter + decision gaps)

These are flagged for you to populate. The system runs without them, but behaviour at the edges is best-effort until you fill them in.

1. **Charter v1.8.2 full text.** `src/aic/charter/charter_v1_8_2.md` has the gates / PTRS / regime / protocol summaries that are *explicit* in the spec. Sections marked `<<<CHARTER_GAP — PM TO POPULATE>>>` need the real charter document content.
2. **Voice literature uploads.** Each voice has a default speed-learning summary baked in (`voice_config.py`). To use the richer text you have from owned ebooks, paste it into the spec markdown's per-voice upload slots — the literature loader picks them up automatically.
3. **Universe / pipeline cap = 10.** Locked per spec; flagged here for visibility.
4. **First LLM-cost ceiling.** No budget gate is wired. Cost is logged to `state/aic.db cost_log`. Consider setting a per-session ceiling before going live.
5. **Holiday calendar.** `scheduler/runner.py` has a hard-coded 2026 list. Replace with `pandas_market_calendars` when wiring for production.

---

## 6. Decisions made (so you can override)

These are the calls I made without you. Flagged so you can review and adjust:

| Decision | Reason | Where |
|---|---|---|
| New code lives under `src/aic/`, not top-level `alfred/`, `committee/` | Existing project uses `src/` layout. Honours "extension, not replacement". | All new files |
| AQE export extension via **post-processor**, not by editing `drive_sync.py` | Spec mandates AQE files frozen; export schema extended additively. | `src/aic/data/dsg13_extender.py` |
| Voice prompts assembled by Python template, with `.md` files emitted under `_compiled/` | DRY + spec-compatible. `voice_config.py` is the single source of truth. | `prompts/prompt_builder.py` |
| Sizing fallback = `QUARTER` when no 3/4 majority in Risk Cell | Most conservative non-BLOCK option. Spec doesn't specify; flagged here. | `committee/risk_cell.py` |
| Steenbarger Inversion runs automatically when 0/8 or 8/8 unanimous and returns before Risk Cell | Per Charter §3A rule 3. PM still has to acknowledge — UI gate (S09) is deferred. | `protocols/protocol_b_qualification.py` |
| `sma_distance_pct` uses SMA20 (not SMA50) | Aligns with PTRS SH definition in Charter §6. | `data/dsg13_extender.py` |
| `sector_corr` uses 60-day Pearson | Standard window; matches the existing 60-day beta in AQE. | `data/dsg13_extender.py` |
| Telegram failures degrade to local log file rather than raising | Per spec §14.26 reliability rule. | `delivery/telegram_client.py` |

---

## 7. Suggested next session priorities

Sequenced by value-per-hour for the POC:

1. **Wire the first real deliberation.** Populate `ANTHROPIC_API_KEY`, run `protocol_b_qualification.qualify_candidate` end-to-end on one candidate, watch the eight voice outputs land in `state.deliberations`, validate the voice parsers against actual Opus 4.6 text. *Highest learning value per hour.*
2. **Build the prompt-caching test.** Confirm the second voice call reads the cached system block at the discounted rate (`cache_read_input_tokens > 0` on call 2). Without this, cost runs ~10× expected.
3. **Patch the holiday calendar.** Swap the hard-coded list in `scheduler/runner.py` for `pandas_market_calendars`.
4. **Wire Telegram briefs.** Once `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` exist, hook the four scheduler handlers to the delivery client. Test with a manual `python -c "from src.aic.delivery.telegram_client import send_message; send_message('test')"`.
5. **Real protocol-A pull.** Hook in VIX (FMP `^VIX`) + dynamic capital from PTJ + `open_positions.json` so `protocol_a_premarket.run_pre_market` produces a brief from live state. The handler stub in `scheduler/runner.py` shows the wiring points.
6. **Protocol C trail sweep on real positions.** Iterate `open_positions.json`, look up peak close from the AQE panel, call `compute_trail` per row, persist recommendations.
7. **UI.** Frontend build (separate session). 20 screens. Suggest scoping to S03 + S08 + S09 first — those are the daily critical path.

---

*Generated 26 May 2026. Build session 1. Next session: wire the first real deliberation under credentials supervision.*
