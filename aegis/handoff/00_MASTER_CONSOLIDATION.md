# AEGIS — MASTER CONSOLIDATION
**Baseline handoff document · 21 Jul 2026 · kernel repo `TongIncomeWheel/AQE`, subdir `aegis/`**

This is the single-source consolidation of what Aegis IS: the PM's requirement, the build, the
agentic design, the orchestration map, the skills, and the process. It is written to be read by a
human OR by any harness (Claude, Kimi, a self-hosted runtime) that will run the system. Companion
documents in this folder: `01_ORCHESTRATION_IMPLEMENTATION.md` (the how), `02_RUNTIME_INFRA_REQUIREMENTS.md`
(the sourcing spec — the key doc), `03_LONGLIST_ALERT_UNIVERSE.md` (the stock-selection recipe),
`04_COWORK_NATIVE_GUIDE.md` (running it on Cowork today), `PLATFORM_SWITCH.md` (moving harness).

---

## 1. THE REQUIREMENT (what the PM actually wants)

**The fund.** Aegis is one PM's **US-equity momentum book** — one of three strategies (Aegis,
Income Wheel, Protégé9) sharing co-mingled capital across two brokers (Tiger, IBKR). Only the
Aegis-tagged sub-book is governed here; dynCap and every risk gate apply to the Aegis book alone,
never co-mingled broker totals (D-17).

**The machine the PM is buying.** An **autonomous agentic system** that, every trading day:
1. Screens the US market to a daily universe.
2. Runs an independent **11-voice swarm** that nominates candidates in isolation (no anchoring).
3. Tallies consensus, filters events, and has a **committee** deliberate the survivors into an
   Executive Action Plan with a mandatory bear case on every idea.
4. Presents the plan for **PM approval by 21:00 SGT** (human-in-the-loop; silence never trades).
5. Watches the held book and a mechanically-screened **alert universe** intraday, paging only on
   what is worth acting on.
6. Journals the day, marks the book, audits itself, and proposes improvements that must **retire
   something to add something** (no unmanaged change — the anti-spaghetti law).

**The non-negotiables the PM has stated repeatedly:**
- **Momentum-first.** The voices were chosen as momentum traders; the system's only job is to not
  distort them. Extension above a moving average is strength, not a flaw; risk lives in the
  bracket, not in a gate (D-52, D-63).
- **Weather, never a gate.** Sector rotation / concentration / macro inform sizing tone; they do
  NOT remove a name from consideration. The PM decides (D-4, reaffirmed 21 Jul).
- **Read, never invent.** Fabrication is the gravest breach. Voices read AQE data; they never make
  up numbers. A declared data gap is sourced by the Chief, not guessed (D-53, D-55).
- **One order path.** No agent may place an order except the staging-gatekeeper, and only under an
  armed, dated, auto-expiring autopilot switch; default is PREVIEW-only, PM stages personally (D-1, D-7).
- **Anti-spaghetti.** When a need arises, COMPLETE or CORRECT an existing structure, or build one
  genuinely new agent/skill — never overlayer prose/flags/shims. Every change names what it retires (D-8).
- **Self-healing is first-class.** The agents must classify failures, retry within bounds, reseed data,
  source declared gaps, verify the world independently, and escalate with the exact manual fix — never
  fabricate around a failure, and never self-heal a hard gate. This agent-level self-heal doctrine (the
  D-45 exception ladder + D-40/D-55/D-64/D-69/D-70/D-72) is a KEY capability that any runtime must
  preserve, and the runtime itself must add process-level recovery (restart/resume, re-fire a missed
  loop, deliver the escalation). Captured in full as a rated requirement in
  `02_RUNTIME_INFRA_REQUIREMENTS.md §2.6`.
- **The PM must be able to SEE and STEER.** An agentic system that does work the PM cannot observe,
  interrogate, or approve in one coherent place is only half-built. (This is the open gap — see §7
  and `02_RUNTIME_INFRA_REQUIREMENTS.md`.)

---

## 2. THE BUILD (what exists today)

```
aegis/
  CONTEXT.md          load-first: what Aegis is, the interaction model, session bootstrap
  charter/
    constitution.md   the law (2pp): 10 laws incl. execution boundary, read-never-invent, learning-with-debt
    rulebook.yaml     doctrine: every operational rule (event filter, anti-anchoring, staleness, breach classes)
    parameters.yaml   the numbers the PM tunes (dynCap method, 1R, gates, VIX bands, alert_universe thresholds)
    decisions_log.md  D-1 .. D-77, newest first — every ruling that changed law/rulebook, and what it retired
    commands.md       the PM's command registry (/status /ops /plan /ap /cockpit /recover ...)
  skills/             the PROCESS — one folder per skill (see §5)
  tools/              deterministic data-plane code (no model): screeners, calculators, ledgers, self-heal, audits
  contracts/          JSON schemas every artifact validates against (nomination, committee, plan, journal, ...)
  desks/              desk-scoped skill material (risk/exits, etc.)
  data/               the workspace shelf — SOD (sod/DATE), EOD (eod/DATE), alerts, journal, persistent state
  packaging/          build_claude.py — compiles the kernel into a Claude/Cowork plugin (agents/*.md pinned)
  orchestration/      physical home of the process skills (BL-033)
```

**The AQE engine** (this same repo) is the deterministic analytics layer: 6 scoring engines, ~46
subcomponents, Elder, DETECT lenses, brackets, the alert engine, the persistent historical store.
It runs nightly and writes `aqe_daily_export.json` to a Google Drive folder named "AQE" — the
canonical feed the kernel pulls each premarket (D-66).

**Connectors (MCP):** FMP (market data / news), Tiger + IBKR (broker positions/orders, read + the
gated order path), Google Drive (the AQE feed + the PTJ book of record). All ride OAuth; the only
local secret is a GitHub PAT for the autonomous git push (D-48/D-49).

---

## 3. THE AGENTIC DESIGN (three planes, who may think about what)

```
DATA PLANE — deterministic code, no model, no opinions
   AQE engine · universe screen · calculators (sizing, ATR/trailing-stop, VaR, hedge, Black-Scholes)
   · alert_universe casting mat · ledgers (dynCap, nomination) · audits · self-heal · notify
        │  (produces validated data artifacts on the shelf)
        ▼
JUDGMENT PLANE — pinned to the judgment model tier (opus), spawned ISOLATED, this is where analysis happens
   11 VOICES (nominate in isolation): lynch · oneil · wyckoff · raschke · steenbarger · thorp ·
        seow · minervini · druckenmiller · detect-lens · elder-lens
   COMMITTEE-DESK (deliberates the tallied survivors → verdicts + mandatory bear case + dissent)
   ENGINEERING BENCH (5 seats: technical · indicator · data · process · governance-chair) — the learning loop
        │  (produces nominations, verdicts, improvement proposals)
        ▼
CONTROL PLANE — the cheap/economy tier; sequences, validates contracts, calls tools; NEVER analyses
   THE CHIEF / ORCHESTRATOR — runs the process skills, adopts a DESK per phase (Research→Risk→Execution→Operations→Engineering)
   STAGING-GATEKEEPER — the ONLY order-capable agent (isolated, armed-switch-gated)
```

**Why isolation matters.** Each voice is a FRESH context with no session, no other voices, no
tally — it sees only its own methodology card + the universe file + its own rolling memory. This
is the anti-anchoring guarantee: consensus is *counted*, never negotiated (D-5, D-16).

**Desk model (D-26/D-32).** There is one Chief; it *adopts* a desk identity per phase rather than
spawning standing desk agents. Premarket: Research (universe→swarm→deliberation) → Risk (sizing,
gates) → Execution (staging requests). Post-market: Operations (journal, book of record) →
Engineering & Change (scorer, audit, assurance).

---

## 4. THE ORCHESTRATION MAP (the five loops)

| Loop | SGT window | Trigger | What it does | Output |
|---|---|---|---|---|
| **Premarket** | plan ready 16:00, approve by 21:00 | cron 10:00 wkdays | universe → 11-voice swarm → tally → event filter → committee deliberation → sized plan | Executive Action Plan (DRAFT→approved) |
| **Market-hours** | 21:30–04:00 | in-session /loop, armed by the 21:25 liveness cron | sweep the mechanical alert universe; held-book risk stream; 3-lens pod on survivors; page only on actionable CONFIRM | pages + intraday reconciliation |
| **Post-market** | 05:05 | cron (DST-proofed, D-74) | reconcile fills → journal + PTJ to Drive → metrics → archive ledger → scorecard → audits → git push | journal, PTJ, scorecard, flow audit |
| **Design & Review** | 08:00 | cron (Tue–Sat) | grade the day's processes; learning agent proposes improvements to the STEER file | change proposals for PM |
| **Weekly** | Sun 06:00 | cron | parameter/criteria review, AQE contract review, historical-store maintenance, hygiene janitor | weekly report + proposals |

The full step-by-step of each loop lives in its skill (`skills/<loop>/SKILL.md`) — procedure lives
in the skills, never in the charter. The implementation-layer mechanics (bootstrap, self-rearm,
delivery, state) are in `01_ORCHESTRATION_IMPLEMENTATION.md`.

---

## 5. THE SKILLS (the process, one card each)

**Process loops:** premarket · market_hours · post_market · design_review · weekly
**Judgment agents:** committee-desk · voice-common (+ 11 voice cards) · the 5 eng-* bench seats · learning_agent
**Assurance:** auditor · performance_scorer
**Execution:** staging-gatekeeper (sole order path)
**Cockpit / PM surface:** status (/status book card) · ops-status (/ops machine card) · cockpit (/cockpit results delivery, D-76) · recover (/recover /heal /repull /reseed)
**Governance:** development (the capture→approve→branch→verify→ship→remember pipeline — why spaghetti never returns)

**Key deterministic tools (data plane, no model):** universe_screen · alert_universe (casting mat,
D-77) · subscore_board · quality_flags · tripwires · sizing · trailing_stop · var_parametric ·
hedge_engine · dyncap_ledger · archive_ledger · historical_store · nomination_ledger ·
daily_flow_audit · drive_ptj_check · self_heal · notify · git_sync · bootstrap · morning_summary · ops_status.

---

## 6. THE PROCESS (premarket, in one pass — the heart of the day)

0. **Preflight** — check the git token; the plan still writes locally + to Drive regardless.
1. **Freshness** — journal current? AQE export dated today (else flag + PM-acknowledge, D-66).
2. **Universe build** — `universe_screen.py` → the daily universe + near-misses (surfaced, not cut).
3. **AQE pull** — pull the export from Drive with bounded retry (D-70); validate; run tripwires.
4. **Held book FIRST** — exits before entries: recompute trailing stops (mechanical floor), refresh
   dynCap mark-to-market, run the hedge assessment.
5. **THE SWARM** — 11 isolated voice spawns nominate from the taxonomy-complete universe; the swarm
   ALWAYS runs (a portfolio breach caps verdicts, never the analysis — D-65); declared data gaps
   self-heal before tally (D-55).
6. **Tally & tier** — count nominations; stamp price + field values + quality flags; attach the
   data board (D-60).
7. **Event filter** (blocking) — M&A/activist/single-catalyst names marked EVENT-DRIVEN, cannot
   advance (this is the ONLY hard exclusion — it caught PYPL's takeover pop 21 Jul).
8. **Macro & SRM weather + bellwether letters** — context only, never a gate.
9. **Deliberation** — the committee-desk (isolated, opus) turns the survivors into ADVANCE /
   HOLD-FOR-CONDITIONS / PASS verdicts, each with a mandatory bear case + held-book verdicts.
10. **Plan assembly** — sized brackets (a wide stop is sized smaller, never cut); the phone render
    with plain-language "why (data)" anchors.
11. **PM approval by 21:00** — approve/edit/reject; approved names load the intraday alert universe.
12. **Run outcome + self-heal wiring.**

The stock-selection tension the PM refined over 20–21 Jul — momentum-first, concentration as
context, the detection-lane "casting mat" for the alert universe — is captured in full in
`03_LONGLIST_ALERT_UNIVERSE.md`.

---

## 7. WHAT IS TRUE, AND THE ONE OPEN GAP

**What works today (verified):** the analytics engine, the 11-voice swarm, committee deliberation,
sizing, journaling, the self-bootstrap that lets a scheduled session reconstruct its workspace
(D-64), and the git-as-source-of-truth persistence. A scheduled loop genuinely runs end-to-end and
pushes real artifacts — verified by live git commits on 21 Jul (premarket plan; market-hours
liveness wake).

**The open gap (the reason for `02_RUNTIME_INFRA_REQUIREMENTS.md`):** Claude Cowork has **no
persistent, interactive, proactive single entry point.** Verified against Anthropic's own docs:
every scheduled fire spawns a *new* session (no session-binding), artifacts are display-only (a
dashboard cannot take input back), and there is no documented pattern for a durable cockpit. So the
autonomous work runs, but it cannot reliably *surface to and be steered by the PM in one coherent
place* on the current harness. That is a runtime/harness limitation, not a kernel defect — the
kernel is deliberately harness-neutral (D-15) so it can move to a runtime that provides the missing
persistent-agent layer. See `02_RUNTIME_INFRA_REQUIREMENTS.md`.
