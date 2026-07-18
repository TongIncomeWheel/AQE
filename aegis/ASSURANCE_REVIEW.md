# AEGIS — DEVELOPMENT ASSURANCE REVIEW
**Epics → user stories → tasks, mapped to what exists and where it lives.**
v4.6 · 18 Jul 2026 · Status legend: ✅ built & verified here · 🟡 built, needs live/deploy verification · ⬜ pending (open task)
Taxonomy code = Epic (E#) · User Story (US-#.#) · Task (T-#.#.#). The SAME codes are used in the component map (§2) and artifact map (§3). Repo paths are inside github.com/TongIncomeWheel/AQE — kernel under `aegis/`, engine at repo root (`src/`, `run_daily.bat`, `output/`).

---

## §1 EPICS & USER STORIES (taxonomy: PM journey × functional capability)

### Journey axis
Sunday → Premarket → Approve → Sleep (market) → Wake (accounting + learning) — with four cross-cutting capabilities beneath every stage: Governance/Config · Execution Boundary · Data/Memory · Portability.

### E1 — GOVERNANCE & CONFIGURATION (cross-cutting)
*As the PM I want law, numbers and rulings in exactly one place each, changeable by me in one line, so tweaks never breed spaghetti again.*
- US-1.1 Read all law in one sitting → T-1.1.1 constitution (2pp, orchestration-only) ✅ · T-1.1.2 command registry ✅
- US-1.2 Every number once → T-1.2.1 rulebook.yaml (law) ✅ · T-1.2.2 parameters.yaml (tunables) ✅ · T-1.2.3 build-time value inlining into skills ✅
- US-1.3 One-line tweaks, always logged → T-1.3.1 set_param tool (validate/refuse/log/commit) ✅ self-tested
- US-1.4 Rulings traceable → T-1.4.1 decisions_log D-1…D-10 + D-7a ✅ · T-1.4.2 rule review_by dates ✅ (review sweep in weekly skill)

### E2 — UNIVERSE & DATA INTAKE (Premarket stage)
*As the PM I want a fresh tradable universe and a feed I can trust blindly, because everything downstream reads it verbatim.*
- US-2.1 Daily open-screen universe (D-3) → T-2.1.1 universe_screen.py (FMP screener + EMA/vol cuts) 🟡 (compiles; needs one live run with FMP key on PC)
- US-2.2 Feed trusted before anyone reads it → T-2.2.1 aqe_export.schema.json generated from live feed ✅ · T-2.2.2 tripwires.py (enum death, bracket band, glossary drift, held-vs-journal, staleness) ✅ ran clean on 18 Jul export
- US-2.3 → moved to E3 by D-11: event filter runs post-nomination pre-deliberation on nominated names only ✅
- US-2.4 The engine itself → AQE repo root, untouched (run_daily.bat → output/aqe_daily_export.json) ✅ existing

### E3 — COMMITTEE & DELIBERATION (Premarket stage)
*As the PM I want ten genuinely independent nominators whose grounds I can read and whose results are measured.*
- US-3.1 Voices pinned to their literature → T-3.1.1 9 canon-enriched voice cards ✅ · T-3.1.2 shared engine (one machinery) ✅ · T-3.1.3 reserves bench ✅
- US-3.2 Detect lens as 10th seat (D-5) → T-3.2.1 detect_lens card (lens/radar fields only, orthogonal) ✅
- US-3.3 Isolation before consensus → T-3.3.1 anti-anchoring law ✅ · T-3.3.2 swarm spawn instruction in premarket step 6 ✅ (🟡 first live swarm run pending)
- US-3.4 Structured outputs → T-3.4.1 nomination.schema.json ✅ · T-3.4.2 tally + deliberate-2+ rule (D-2) ✅
- US-3.5 Deliberation discipline → bear case, unanimity challenge, macro-after-nominations ✅ (law + premarket steps 8–9)

### E4 — DAILY PLANNING & APPROVAL (Premarket → Approve stages)
*As the PM I want one actionable plan by 16:00 that I can approve from my phone by 21:00.*
- US-4.1 One orchestrated pass → T-4.1.1 premarket skill (11 steps) ✅
- US-4.2 The plan as a contract → T-4.2.1 plan.schema.json (held actions, tiered ideas, triggers, watch table, approval token, preauthorised flags) ✅
- US-4.3 Phone commands → /pm /plan /approve (+except) ✅ registry; 🟡 wire-up proven only at first live run
- US-4.4 Weather not gates (D-4) → SRM/macro placement after nominations ✅
- ✅ T-4.5.1 hedge assessment wired into premarket step 5 (PM confirmed 18 Jul; BL-007 SHIPPED)

### E5 — EXECUTION & ORDER LIFECYCLE (Sleep stage; Execution-Boundary capability)
*As the PM I want exactly one order-capable agent, previews by default, autonomy only when I lend it.*
- US-5.1 Sole order path → T-5.1.1 staging-gatekeeper skill, 7-check framework ✅ · T-5.1.2 orchestrators stripped of staging ability ✅
- US-5.2 Autopilot I control (D-7/D-7a) → T-5.2.1 autopilot.py /arm /disarm /ap, fixed 05:30 SGT expiry ✅ cycle-tested · T-5.2.2 caps in parameters ✅ · T-5.2.3 kill-conditions disarm-first ✅ (skill text)
- US-5.3 Real-money mechanics → T-5.3.1 sizing.py two-step + post_fill_check ✅ · T-5.3.2 bracket-verbatim law ✅ · T-5.3.3 post-fill protocol owned by gatekeeper ✅
- 🟡 T-5.4.1 Tiger confirm-call wiring — connector proven live (account summary pulled 18 Jul); the gatekeeper's exact place→confirm call sequence exercised only at first armed session (deliberately last)

### E6 — MARKET WATCH (Sleep stage)
*As the PM I want code, not tokens, watching prices while I sleep.*
- US-6.1 Code watches, agents wake → T-6.1.1 market_hours skill ✅ · AQE alert engine (src/alerts, src/intraday) ✅ existing
- ⬜ T-6.2.1 **OPEN: alert-universe loader** — small script writing approved plan triggers into the alert engine's watch config (glue between plan.json and src/alerts)
- US-6.3 MISSED-BY-DESIGN recorded with price path (evidence for Phase-2 case) ✅ (skill text)

### E7 — JOURNAL & ACCOUNTING (Wake stage)
*As the PM I want a book of record built from broker truth every day without my involvement.*
- US-7.1 Daily journal process → T-7.1.1 post_market skill (broker pull → merge vs gatekeeper records → dynCap roll → SL audit → validated write) ✅ · T-7.1.2 journal.schema.json ✅ · full narrative CONTEXT Part 6B ✅
- US-7.2 Metrics + completeness audit → T-7.2.1 post_market steps 2–3 ✅
- US-7.3 Clean naming forever → journal law + T-8.2.1 migration below ✅ law
- 🟡 T-7.4.1 first live multibroker reconcile on PC (IBKR read-only server untested against a real gateway)

### E8 — MEMORY, DATA & HYGIENE (Data/Memory capability)
*As the PM I want four tidy shelves, outcome memory, and growth that stays flat.*
- US-8.1 Four shelves → T-8.1.1 data/ tree + README (sod/intraday/eod/persistent/archive) ✅ · T-8.1.2 GitHub daily archive commit (D-9) ✅ law/process (🟡 first commit at deploy)
- US-8.2 Legacy cleaned once → T-8.2.1 migrate_legacy.py (newest journal = seed; rest archived with manifest) ✅ built ⬜ not yet run against your Drive
- US-8.3 Flat growth → T-8.3.1 janitor.py (rollups + monthly zips after retention.raw_days) ✅
- US-8.4 Outcome memory → T-8.4.1 nomination_ledger.py (record/track/report, 15-day windows, per-voice hit rates) ✅ · ⬜ T-8.4.2 **OPEN: daily price-feed job** for ledger tracking (small FMP pull writing prices.json)

### E9 — ASSURANCE & LEARNING (Wake stage; the anti-spaghetti engine)
*As the PM I want the system to audit itself, measure itself, and change only through a managed pipeline.*
- US-9.1 Self-audit → T-9.1.1 auditor skill ✅
- US-9.2 Outcomes measured → T-9.2.1 performance_scorer skill (miss taxonomy) ✅
- US-9.3 Managed change (D-8) → T-9.3.1 development skill (capture→approve→branch→shadow→ship→remember) ✅ · T-9.3.2 backlog.schema.json (retirement mandatory) ✅
- US-9.4 Evidence before votes → T-9.4.1 measure_proposal.py (panel + volatility-tercile control) ✅
- ⬜ T-9.5.1 **OPEN: morning-summary push assembly** — the 10:00 single push that stitches journal/audit/review/backlog (content exists; the assembler+push step needs its glue at deploy)

### E10 — DEPLOYMENT & PORTABILITY (cross-cutting)
*As the PM I want the same kernel deployable into a new Claude project and a Kimi harness, with security I understand.*
- US-10.1 Generated adapters → T-10.1.1 build_claude.py ✅ runs · T-10.1.2 build_kimi.py ✅ runs (21 skills emitted)
- US-10.2 Deploy instructions → T-10.2.1 DEPLOY.md (3 paths + acceptance checklist) ✅
- US-10.3 Market access → Tiger connector ✅ proven live · FMP ✅ proven live · Alpaca client ✅ (hardcode PM-ruled) · T-10.3.4 IBKR read-only MCP 🟡 built, untested against a gateway
- US-10.4 Security → T-10.4.1 private-repo + fine-grained PAT procedure ✅ documented · T-10.4.2 env.example ✅ · local-hybrid topology (D-9) ✅
- ⬜ T-10.5.1 **OPEN: push kernel to AQE repo as branch** (needs your PAT) · ⬜ T-10.5.2 Task Scheduler entries (needs OS confirm) · ⬜ T-10.5.3 shadow week + parity diffs · ⬜ T-10.5.4 Tiger URL line for Kimi (only if/when Kimi deploys)

### E11 — WEEKLY & REPORTING (Sunday stage)
*As the PM I want a weekly stepping-back view of book, system and universe churn.*
- US-11.1 Weekly process → T-11.1.1 weekly skill (CS Weekly ingest, posture memory, WTD/MTD/YTD, churn report, rule-review sweep) ✅ · CS sample in drop folder ✅

---

## §2 COMPONENT MAP (taxonomy → what was developed → where in the AQE repo)

| Code | Component (type) | Repo location (github.com/TongIncomeWheel/AQE) | Status |
|---|---|---|---|
| E1 | constitution · rulebook · parameters · decisions_log · commands (governance docs) | `aegis/charter/*` | ✅ |
| E1 | set_param (utility tool) | `aegis/tools/set_param.py` | ✅ |
| E2 | universe screen (data tool) | `aegis/tools/universe_screen.py` | 🟡 |
| E2 | feed contract + tripwires (assurance tools) | `aegis/contracts/aqe_export.schema.json` · `aegis/tools/tripwires.py` | ✅ |
| E2 | AQE engine (data plane, pre-existing) | repo root: `src/engines` `src/analyzer` `src/scanner` `src/pipeline` `run_daily.bat` → `output/aqe_daily_export.json` | ✅ existing |
| E3 | 10 voice skills + shared engine + reserves (judgment skills) | `aegis/skills/voice-*` `aegis/skills/voice-common` | ✅ |
| E3 | nomination contract | `aegis/contracts/nomination.schema.json` | ✅ |
| E4 | premarket process (orchestration skill) | `aegis/skills/premarket/SKILL.md` | ✅ |
| E4 | plan contract | `aegis/contracts/plan.schema.json` | ✅ |
| E5 | staging gatekeeper (boundary skill) | `aegis/skills/staging-gatekeeper/SKILL.md` | ✅ |
| E5 | autopilot switch (utility tool) | `aegis/tools/autopilot.py` (+state in `data/persistent/`) | ✅ |
| E5 | sizing + pricers (calculators) | `aegis/tools/calculators/{sizing,bs_price,hedge_engine,alpaca_client}.py` | ✅ |
| E6 | market-hours process (orchestration skill) | `aegis/skills/market_hours/SKILL.md` | ✅ |
| E6 | alert engine (data plane, pre-existing) | repo root: `src/alerts` `src/intraday` | ✅ existing |
| E7 | post-market process (orchestration skill) + journal contract | `aegis/skills/post_market/SKILL.md` · `aegis/contracts/journal.schema.json` | ✅ |
| E8 | shelves + janitor + migration + ledger (data/utility tools) | `aegis/data/README.md` · `aegis/tools/{janitor,migrate_legacy,nomination_ledger}.py` · `aegis/contracts/ledger.schema.json` | ✅ (migration not yet run) |
| E9 | auditor · scorer · learning · development (assurance skills) + backlog contract + panel tool | `aegis/skills/{auditor,performance_scorer,learning_agent,development}` · `aegis/contracts/backlog.schema.json` · `aegis/tools/measure_proposal.py` | ✅ |
| E10 | packagers (build tools) + generated adapters | `aegis/packaging/{build_claude,build_kimi}.py` → `aegis/dist/*` (generated, git-ignored) | ✅ |
| E10 | IBKR MCP (connectivity tool) | `aegis/tools/mcp/ibkr_mcp/server.py` | 🟡 |
| E10 | endpoints + env template (config) | `aegis/config/{endpoints.json,env.example}` | ✅ (values pending) |
| E11 | weekly process (orchestration skill) + CS drop folder | `aegis/skills/weekly/SKILL.md` · `aegis/data/persistent/cs_weekly/` | ✅ |

## §3 ARTIFACT MAP (what the system produces daily, taxonomy-matched)

| Code | Artifact | Producer | Location | Contract |
|---|---|---|---|---|
| E2 | universe_DATE.json | universe screen | `data/sod/DATE/` | criteria embedded |
| E2 | aqe_daily_export.json (+ tripwire verdict) | AQE engine / tripwires | `output/` → fetched to `data/sod/DATE/` | aqe_export.schema |
| E3 | 10 × nomination files | voice skills | `data/sod/DATE/nominations/` | nomination.schema |
| E3/E4 | committee_DATE.json · plan_DATE.json | deliberation / premarket | `data/sod/DATE/` | plan.schema |
| E5 | staging previews / refusals · post-fill records | gatekeeper ONLY | `data/intraday/DATE/staging/` | preview spec in skill |
| E5 | autopilot state + log | /arm /disarm | `data/persistent/autopilot*.json(l)` | in tool |
| E6 | alert fires · wake log | alert engine / MH orchestrator | `data/intraday/DATE/` | — |
| E7 | aegis_journal_DATE.json · metrics · audit | post-market | `data/eod/DATE/` | journal.schema |
| E8 | ledger.jsonl · rollups · monthly zips · legacy archive+manifest | ledger / janitor / migration | `data/persistent/` · `data/archive/` | ledger.schema |
| E9 | review report · backlog.jsonl · shadow diffs | D&R / development | `data/eod/DATE/` · `data/persistent/backlog.jsonl` | backlog.schema |
| E10 | generated Claude plugin · Kimi pack | packagers | `aegis/dist/` (regenerated, never edited) | — |
| E11 | weekly report · posture memory · churn report | weekly | `data/persistent/` + Drive/GitHub archive | — |

## §4 ASSURANCE VERDICT — the open list (also seeded into backlog.jsonl)

Seven ⬜ items stand between "built" and "live", in order: **(1)** push kernel to the repo (needs PAT) · **(2)** run legacy migration · **(3)** alert-universe loader glue (E6) · **(4)** ledger price-feed job (E8) · **(5)** morning-summary assembler (E9) · **(6)** scheduler entries (needs OS confirm) · **(8)** shadow week with parity diffs, ending in the DEPLOY.md acceptance checklist. Deliberately last: first armed Tiger confirm-call, only after the shadow week passes.
