# AEGIS — SYSTEM CONTEXT DOCUMENT
**The load-first file. Any harness, agent or human reads THIS before anything else.**
v4.6 · 19 Jul 2026 · Plain English. Companion files: `charter/constitution.md` (law) · `charter/rulebook.yaml` (doctrine) · `charter/parameters.yaml` (numbers) · `charter/decisions_log.md` (rulings D-1…D-31, newest first).

**How you interact — grounded in Claude Cowork (D-31):** Aegis lives in ONE Cowork **workspace** — a persistent file store that syncs across your devices, not a chat. The workspace IS the memory. Three things touch it: (1) **scheduled tasks** run remotely with your app closed — premarket, market-hours watch, post-market, weekly — each its own session reading/writing the workspace files (managed from the mobile "Scheduled" sidebar); (2) **your cockpit** is the Cowork chat in that same workspace, on phone or desk — you type commands (`charter/commands.md`), and the session reads today's files and answers; (3) **pushes** reach your phone when input is needed (4pm plan, 10am summary, money/safety pages). A FRESH chat reconstitutes fully: it loads this file + charter from the project, then reads today's shelf from the workspace — so `/status`, `/plan`, `/ap` are correct even in a brand-new window (they read files, never chat memory). Precise SGT timing uses the scheduled-task tool (cron). Kimi runs the same pattern in parallel, read-only until you confirm migration; only one deployment is ever armed for live orders.

---

# PART 1 — WHAT AEGIS IS, IN ONE PARAGRAPH

Aegis runs one PM's US equity momentum book. A deterministic engine (AQE, in this repo) computes all analytics nightly. Ten isolated agent "voices" nominate candidates independently each day; consensus is counted, not negotiated. An orchestrator assembles an Executive Action Plan by 16:00 SGT; the PM approves by 21:00 and personally stages any orders; code — not AI — watches prices while the PM sleeps; assurance agents audit, measure outcomes, and propose improvements that must retire something to add something. **Default mode: no agent can submit an order; the PM can lend bounded autonomy to exactly one agent via the autopilot switch (Part 7.3).** The whole system is files in this repo plus a data directory: any AI harness (Claude, Kimi) is an interchangeable engine that receives a generated install.

---

# PART 2 — WHAT WAS RETAINED FROM THE CURRENT SYSTEM

Nothing of proven value was discarded. Three fates: **kept as-is**, **kept but relocated/reformed**, **retired by your explicit ruling**.

## 2.1 Kept as-is (the trading substance)

| From | What survives | Where it now lives |
|---|---|---|
| AQE engine & repo | Every calculation: 6 scoring engines, 46 subcomponents, Elder, DETECT engines, brackets, lens block, alert engine, persistent layer | Untouched in this repo — the kernel folders merge alongside |
| Charter (all versions) | Execution boundary · read-verbatim / fabrication-is-gravest-breach · event filter (M&A / activist / >15% single-catalyst — word for word) · anti-anchoring (voices see no tags, no ordering) · mandatory bear case · unanimity challenge (Thorp/Pardo/Steenbarger rotation) · staleness rule (older than T-1 → flag + PM acknowledge) · USD-only · breach classes | rulebook.yaml (law) |
| Charter numbers | dynCap method (prior + realised on closed only) · 1R = 1.5% dynCap · 2R at ≥5 conviction / 0.5R runner-hedge-catalyst · two-step sizing (R then vol-cap, both mandatory) · VIX bands GREEN/YELLOW/ORANGE/RED with RED = no entries · stop ceilings 12/8/6% · ATR multiples 1.5/2.0/2.5 with Elder adjustment and [1.0, 3.5] clamp · beta 1.8 soft / 2.0 hard · VaR 16/20% · leverage 2.5/3.0× · combined stop risk 5% max · bracket gates ATR≥1.0, R:R≥2.0, risk ≤ regime ceiling | parameters.yaml (yours to tune) |
| Execution discipline (Lessons Log, paid for in real breaches) | LIMIT entries / MARKET exits · stop staged only AFTER fill, at actual fill price · post-fill actual-risk check with $50 tolerance · portfolio metrics line after every fill · committee-before-brackets (was "Gate 0") · never assert a missing stop without a broker pull | rulebook.yaml + the Staging Gatekeeper checklist (Part 4) |
| The 9 voices + reserves | Lynch, O'Neil, Wyckoff, Raschke, Steenbarger, Thorp, Seow, Minervini, Druckenmiller active; DeMark, Pardo, Elder, Dalio, Murphy on the bench; Druckenmiller's macro brief always delivered; Lynch/Steenbarger overlap check | skills/voice-* (now with distilled canon pinned in text) |
| Bracket doctrine | AQE bracket object read verbatim, never recomputed by an agent; live-spot distance overlay | rulebook.yaml + market-hours skill |
| Hedge maths | hedge_engine.py + the Black-Scholes pricer (now ONE copy, not three) | tools/calculators/ |
| Journal substance | Multibroker reconcile as execution truth · dynCap roll · SL audit (live vs reference, MATCH/MISMATCH/MISSING) | post_market skill + journal contract |
| SRM substance | Sector grades, trend_state always shown with grade, thematic RRG | AQE feed srm block; role changed by D-4 (below) |

## 2.2 Kept but relocated or reformed

| Old form | New form | Why |
|---|---|---|
| Charter prose v3.0 (700+ lines, §-soup, Bindings A–R) | Constitution (2pp law) + rulebook (doctrine) + parameters (numbers) + skills (procedure) | Your instruction: charter = orchestration only; procedure = skills |
| 5 plugin skills (premarket, brackets, SRM, hedge, PTJ) | 20 kernel skills, generated into any harness | Same sequences, harness-neutral, values compiled in at build |
| DPRS 16-check self-scoring + peer-scored voice cards | Auditor skill (completeness/fabrication checks kept) + Nomination Ledger (outcome scoring) | Kept the audit substance, dropped the ceremony; voices now scored by results, not peer opinion |
| Lessons Log (25 lessons) | Every lesson that had become a rule IS now law/parameters (traced above); the log as a ritual is retired; future lessons flow through Design & Review → backlog → rule/code change | Law 10: learning without debt |
| Drive as access path (hardcoded file IDs) | Drive as replication only; data/ shelves are the access path; IDs in one config file | Killed the fragility class |
| PTJ naming chaos (~40 files, 5 conventions) | One canonical journal name + dated immutables + one-time migration script with manifest | Book-of-record integrity |

## 2.3 Retired by your explicit ruling (each traceable in decisions_log.md)

Fixed 605-name curated universe → **daily open screen** (D-3) · "lens may never enter the tally" → **Detect lens = 10th nominator** (D-5) · Sector "Allowed" hard gate → **weather, never a gate** (D-4) · "all ideas deliberated" → **nominate 10, deliberate 2+** (D-2) · unresolved overnight approval conflict → **Phase 1 pre-authorised brackets** (D-1) · β60d gate → **β30d gate** (D-6, final). Also retired: the three graveyard premarket skills, the dead dsl_* field vocabulary, duplicated pricers, the Drive-MCP dependency.

**Hedge assessment:** wired into Premarket step 5 (held-book review) — PM confirmed 18 Jul. Coverage matrix every day; candidate structures only when coverage is short; hedge orders route through the gatekeeper like everything order-shaped.

---

# PART 3 — ARCHITECTURE: THE FULL MAP

## 3.1 The three planes (who is allowed to think about what)

```
DATA PLANE — deterministic code, no model, no opinions
  AQE engine (nightly) · universe screen · calculators (sizing, BS, hedge) ·
  tripwires · ledger tracking · janitor · alert engine (intraday polling)
        │  produces files, validated by contracts/
        ▼
CONTROL PLANE — orchestrators: sequence, gates, assembly. No analysis, no thresholds of their own.
  5 process orchestrators (Weekly / Premarket / Market-Hours / Post-Market / Design&Review)
  + the Staging Gatekeeper (sole owner of order-shaped work)
        │  invokes skills, passes files, enforces RB: keys
        ▼
JUDGMENT PLANE — model reasoning, the only place AI opinions exist
  10 voice skills (isolated) · deliberation session · macro brief · assurance review
```

## 3.2 Agent taxonomy (your four types, as deployed)

| Type | Members | May | May never |
|---|---|---|---|
| Voices | 9 investors + Detect lens | Read own data menu, nominate, argue in deliberation | See each other pre-tally, compute scores, stage anything |
| Orchestration | 5 process conductors | Sequence skills, enforce gates, assemble artifacts | Hold opinions, contain thresholds, produce order previews |
| Data & utility | catalog tools, calculators, MCPs | Compute, fetch, validate, archive | Interpret, decide |
| Assurance | auditor, performance scorer, learning agent | Audit, measure, propose (with retirement) | Change anything directly |
| (Boundary) | **Staging Gatekeeper** | Emit previews after 7 checks; own post-fill protocol | Submit/amend/cancel; stage unrequested; skip a check |

## 3.3 Tool & data linkage map (what connects to what)

```
                        ┌────────────── GitHub (this repo) ──────────────┐
                        │ law · parameters · skills · calculators ·      │
                        │ contracts · AQE engine source                  │
                        └──────┬─────────────────────────────────────────┘
                               │ build_claude.py / build_kimi.py generate installs
        ┌──────────────────────┴───────────────────────┐
   Claude harness                                 Kimi Code CLI harness
   (plugin + subagents)                           (Agent Skills + swarm + mcp.json)
        │            both speak MCP to the same services            │
        └──────┬───────────┬──────────────┬──────────────┬─────────┘
             Tiger MCP   Alpaca MCP     IBKR MCP        FMP
             (REUSED,    (REUSED,       (NEW, read-     (bars, screener,
             cloud: spot, cloud: Greeks  only, local     quotes)
             positions,   15-min delay)  gateway)
             staging p/c)
        ┌──────────────────────────────────────────────┐
        │ data/ shelves (local, rclone-synced to Drive)│
        │ sod/ · intraday/ · eod/ · persistent/ · archive/ │
        └──────────────────────────────────────────────┘
```

## 3.4 Standing vs triggered orchestration

**Standing (clock-driven, SGT):** Sunday → Weekly · weekdays ~13:00 → Premarket build (plan out 16:00) · 21:00 → approval deadline + pre-staging · 21:30–04:00 → Market-Hours watch (code polls, not AI) · 04:00 → Post-Market · then Design & Review · 10:00 → morning summary push · nightly → janitor.

**Triggered (event-driven):** alert fires → Market-Hours orchestrator wakes → (optionally) Gatekeeper request · tripwire block → process HALTS, PM paged · PM plain-English parameter change → set_param → log + commit · CS Weekly PDF lands → Weekly step 1 consumes · backlog item approved → coding agent ticket · fill observed → Gatekeeper post-fill protocol.

## 3.5 The three loops (how it improves without debt)

1. **Daily trading loop:** AQE → screen → nominate → tally → deliberate → plan → approve → watch → journal → ledger. (The journal's held list feeds the next AQE run — the loop closes.)
2. **Learning loop:** outcomes (ledger + runners) → performance scorer classifies every miss (NOT-IN-UNIVERSE / NOMINATED-NOT-DELIBERATED / DELIBERATED-NOT-ADVANCED / ADVANCED-NOT-ACTIONED / MISSED-BY-DESIGN) → learning agent drafts backlog items that must name a retirement → PM morning approval → code or rule change → committed.
3. **Parameter loop:** PM says it → set_param validates → decisions_log entry → commit → next build inlines the new value everywhere. One utterance, full traceability, zero drift.

---

# PART 4 — THE STAGING PROCEDURE (real money, real levels)

## 4.1 Principle
Exactly one agent — the **Staging Gatekeeper** — can turn an idea into an order preview. Everyone else can only *request*. Seven checks, all must pass, refusals are logged outcomes, and in Phase 1 a passing preview still ends at **your hands in the broker app**. The boundary is code and structure, not a promise.

## 4.2 The seven checks (each cites its rule)
1. **Consensus** — today's committee file shows ADVANCE for the ticker, with conviction and recorded dissent (HOLD-FOR-CONDITIONS passes only with its condition evidenced true).
2. **Event-clean** — not EVENT-DRIVEN (M&A / activist / single-catalyst).
3. **Bracket** — AQE bracket object valid (ATR ≥ 1.0 · R:R ≥ 2.0 · risk% ≤ regime ceiling), verbatim; or a PM override recorded in today's plan.
4. **Size** — from `sizing.py`, both steps, R-multiple matching the conviction tier.
5. **Portfolio gates AFTER the add** — β30d, VaR, leverage, combined stop risk all still pass at post-add values.
6. **PM approval** — ticker on today's plan with status APPROVED; overnight names carry the pre-authorised flag.
7. **Mechanics** — LIMIT entry, MARKET exit path, stop planned post-fill.

## 4.3 Worked example — a real evening
dynCap $72,574.37 → 1R = $1,088.62 (1.5%). Regime YELLOW (stop ceiling 8%, vol-cap 1.5%).

**16:00** — plan carries CLOV: committee ADVANCE 6/9 (dissent: Steenbarger, crowding note recorded), trigger "break of $4.20", AQE bracket: stop 3.86 (fib_618, ATR-distance 1.4), TP1 4.55, TP2 4.95, R:R to TP2 = 2.03 ✓, risk 8.5%→ within… no: risk% = (4.22−3.86)/4.22 = **8.5% — exceeds the 8% YELLOW ceiling → bracket INVALID**. Gatekeeper **REFUSES at check 3**, refusal logged: "risk 8.5% > ceiling 8.0 (YELLOW)". The name stays on the watch table. *That refusal is the system working.*

**Next day** — CLOV consolidates; new AQE bracket: entry ref 4.30, stop 3.98 (new higher structure), risk 7.4% ✓, TP2 4.95 → R:R = (4.95−4.30)/(0.32) = 2.03 ✓. Committee position stands. You approve; pre-authorised = true.
- Check 4, sizing: shares_R = floor(1088.62 / 0.32) = **3,401**. Vol-cap: vol_30d 0.55 → daily vol/share = 4.30 × 0.55/√252 = $0.149; cap$ = 1.5% × 72,574 = $1,088.6 → shares_vol = 7,306. Final = min = **3,401 shares** (~$14,624 position, capped by R).
- Check 5: post-add β30d 0.29 ✓, combined stop risk 3.1% + 1.5% = 4.6% < 5% ✓, leverage ✓, VaR ✓.
- Checks 1,2,6,7 ✓ → **preview emitted**: `BUY 3401 CLOV LMT 4.30 · stop plan 3.98 (post-fill) · TP1 4.55 / TP2 4.95 · 1.0R = $1,088 · checks 7×PASS`.

**21:00** — you stage it yourself in the broker as a conditional order. **02:47** — CLOV breaks 4.30; your staged order fills at **4.31**. Gatekeeper post-fill: actual risk = 3401 × (4.31−3.98) = **$1,122** vs budget $1,088 → delta **+$34 < $50 tolerance**, no flag (at +$50+ it would instruct a quantity trim). Emits the metrics line (exposure, leverage, β, combined stop 4.7%, sector weights) and the stop instruction: **"Stage stop: SELL 3401 CLOV STP 3.98 — at actual fill basis."** You staged the stop with the bracket at 21:00, so this is a verification, not a wake-up. **10:00** — the fire, the fill, the delta and the metrics are the first lines of your morning summary.

## 4.4 The execution data trail (audit by construction)
Every step writes a file: plan with your approval token (`sod/`) → gatekeeper request, preview or refusal (`intraday/DATE/staging/`) → alert fire log (`intraday/`) → broker fill via MCP pull → post-fill record (`intraday/`) → journal (`eod/`) → ledger update (`persistent/`). Real money never moves without a written chain: *who asked → what was checked → what you approved → what filled → what it actually risked.*

---

# PART 5 — THE DATA & EXECUTION DATA LAYER (full map)

## 5.1 The four shelves and every artifact

| Shelf | Artifact | Written by | Read by | Contract |
|---|---|---|---|---|
| sod/DATE/ | universe.json | universe_screen.py | all voices | criteria embedded |
| | aqe_working_read.json | Premarket step 3 (post-tripwire) | voices (via data menus), deliberation | aqe_export.schema |
| | nominations/×10 | each voice skill | tally, ledger | nomination.schema |
| | committee.json | deliberation | Gatekeeper check 1, plan | committee artifact |
| | plan.json (+approval token) | Premarket step 10 / PM 21:00 | Gatekeeper check 6, Market-Hours | plan.schema |
| intraday/DATE/ | alert fires, wake log | alert engine / MH orchestrator | Design & Review | — |
| | staging/ previews + refusals | **Gatekeeper only** | PM, auditor | preview spec |
| | fills + post-fill records | Gatekeeper post-fill | journal | — |
| eod/DATE/ | aegis_journal_DATE.json | Post-Market step 1 | next AQE run (held list), everything | journal.schema |
| | metrics, audit, review | Post-Market/D&R | morning summary | — |
| persistent/ | ledger.jsonl | nomination_ledger.py | scorer, voices (own memory) | ledger.schema |
| | pipeline tracking, posture memory, voice memories, cs_weekly/, journal_seed, rollups/ | various | various | — |
| archive/ | monthly zips + legacy_* | janitor / migration | humans, if ever | manifest.csv |

## 5.2 Lifecycle & growth control
Dated folders immutable at day close → after `retention.raw_days` (30, tunable) the janitor writes a per-day rollup summary into `persistent/rollups/` (kept forever) and zips the raw day into `archive/SHELF-YYYY-MM.zip` → raw folder removed. Ledger rows close at 15 days into per-voice statistics. Drive holds a synced replica of everything; GitHub holds law and code. Nothing is ever deleted — archived with manifests.

## 5.3 Memory, by kind
**Working memory** = today's sod/ + intraday/ files (what a session loads). **Episodic memory** = eod/ days + rollups (what happened). **Outcome memory** = the ledger (what worked, per voice). **Doctrine memory** = charter + decisions log (what we ruled and why). **Posture memory** = the weekly file (how we stand this week). A fresh session reconstructs full context from: CONTEXT.md → constitution → parameters → today's shelf. No conversation history required — that is what makes the system portable and restart-proof.

---

# PART 6 — SETUP CHECKLIST (what the architect must stand up)

1. Merge kernel folders into the AQE repo (github.com/TongIncomeWheel/AQE) as `aegis/`.
2. Fill `config/endpoints.json`: Tiger MCP URL, Alpaca MCP URL (reused cloud services), FMP key env, IBKR gateway choice.
3. Run `tools/migrate_legacy.py` once against the synced Drive journal folder.
4. Set up rclone Drive sync for `data/`.
5. `python3 packaging/build_claude.py` and/or `build_kimi.py` → install the generated package into the harness.
6. Schedule the standing clock (harness scheduled tasks or cron): premarket build, post-market, design & review, weekly, janitor.
7. Intake: Charter v3.0 export → reconcile D-6 → flip `rulebook meta.ratified: true`.
8. Shadow week: new system runs alongside the current routine; daily diff review; cut over when the diff is boring.


---

# PART 6B — THE DAY IN FOUR LENSES (what is actually happening, when)

## The swarm, drawn (how voice independence is real, not claimed)

```
                       ORCHESTRATOR (premarket, step 5)
                       reads: universe file · agents/voice-*.md · per-voice ledger reports
      ┌───────┬───────┬───────┬───────┬───┴───┬───────┬───────┬───────┬───────┬────────┐
      ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼
   [lynch] [oneil] [wyckoff][raschke][steen][thorp] [seow] [minervini][druck][detect]
   each = ONE fresh subagent · ONE compiled agent file (identity+canon+data menu+process
   +own memory+output contract+forbidden) · NO tools · NO session · NO sight of the others
      │       │       │       │       │       │       │       │       │       │
      └── nomination.json ×10 (schema-validated on receipt) ──────────────────┘
                       ▼
        TALLY (count votes; stamp prices) → EVENT FILTER (nominated names only, D-11)
        → deliberation set (2+ votes / lens top tier) → single-context deliberation
```
Consistency guarantee: all ten agent files are COMPILED from one template (shared engine) + one
card each by `packaging/build_claude.py` — the machinery cannot drift between voices, only the
methodology cards differ, and those are the files you read and correct.

## Premarket lens (13:00–21:00 SGT — the thinking window)
The AQE engine has already run (08:30). From 13:00 the Premarket orchestrator: verifies journal freshness → builds the day's universe from the screen → validates the export through tripwires → sends the identical universe to ten isolated voices → collects ten nomination files → tallies (2+ votes or lens top tier = deliberation set) → runs the blocking event filter on the nominated names only (D-11) → macro/SRM weather → deliberation with mandatory bear case → assembles the Executive Action Plan (held actions + new ideas with triggers, brackets, sizes + ranked watch table). Plan on your phone by 16:00. You `/approve` (or edit) by 21:00; approved triggers load into the AQE alert universe; you optionally `/arm`. **State at end of lens:** sod/ shelf complete; alerts armed; autopilot armed or not.

## Market lens (21:30–04:00 SGT — the acting window, you asleep)
Code polls; agents sleep until a trigger fires. On fire: the Market-Hours orchestrator wakes, re-validates the plan entry against live spot, and routes any order-shaped need as a REQUEST to the Staging Gatekeeper. Gatekeeper runs its seven checks → preview (and, ONLY if `/arm` is active and caps allow, executes Tiger's place-preview→confirm itself). Fills observed via broker pull start the post-fill protocol: actual-risk vs budget ($50 tolerance), metrics line, stop verification at actual fill basis. Every wake writes one line; every staging action writes a record. **State at end of lens:** intraday/ shelf holds fires, previews/refusals, fills, post-fill records; autopilot has expired (05:30) or been disarmed.

## Post-market lens (04:00–10:00 SGT — the accounting window)
**The daily trade journal process, end to end:** (1) pull fills, positions, balances from Tiger (default broker; IBKR if in use) — the broker pull is execution truth, conversation memory never is; (2) merge with the gatekeeper's intraday fill records — any mismatch is surfaced, never silently resolved; (3) roll dynCap: prior + realised P&L on CLOSED trades only, recompute 1R; (4) write per-position rows — entry, qty, live mark, reference SL vs the broker's actual staged stop with a MATCH / MISMATCH / MISSING audit per position; (5) close out finished trades with realised R multiples; (6) write `aegis_journal_DATE.json` to eod/, schema-validated — if it doesn't validate, the process did not happen; (7) update the pipeline and mark ledger rows `actioned`; (8) the journal's held list becomes tomorrow's AQE held-enrichment input — the loop closes; (9) the daily GitHub archive commit snapshots data/. Then portfolio metrics, the completeness audit, Design & Review (runners vs nominations, misses classified, backlog items with mandatory retirements), and the janitor. **10:00: one morning summary** — fires, fills, deltas, journal state, audit result, learning asks.

## Weekly lens (Sunday — the stepping-back window)
CS Weekly PDF read from its drop folder into the week's posture memory → held book + regime reviewed → WTD/MTD/YTD book performance AND system performance (per-voice ledger hit rates, audit trends, gatekeeper refusal patterns) → universe churn report (who entered/left the screen — the evidence file if you ever revisit the $2bn floor) → rulebook keys past their review date surfaced for keep/amend/retire. One report, one push.

---

# PART 7 — TOPOLOGY, SECURITY & AUTHENTICATION (local-hybrid, D-9)

## 7.1 Where things run
**The PM's PC is the server**, on 24/7: the harness (Claude Code or Kimi CLI), the AQE nightly job, the alert engine, the IBKR gateway (if used), the data/ shelves, the schedulers. **If the PC is down, the process stops** — deliberately fail-safe; the book is protected by broker-side stops, not by the system being up. **Private GitHub** is the resilience layer: law + skills + code (live, every change a commit) and a **once-daily archive commit** of data/ (post-market step). Drive becomes an optional second mirror, not an access path.

## 7.2 Authentication, service by service (secrets NEVER enter the repo)
| Service | How auth works | Where the secret lives |
|---|---|---|
| Private GitHub | The PC authenticates with an SSH deploy key or a fine-grained PAT scoped to ONE repo, contents read/write only. A working session (me) gets the PAT via environment/secret at session start — used, never stored, never committed. | PC keychain / .env (git-ignored) |
| Tiger MCP (cloud) | Your existing Cloud Run service. Recommended: require an auth header (API key) or Cloud Run IAM (ID-token); the harness sends it from env. Order placement stays two-step: place-preview → confirm. | .env on PC + Cloud Run secret |
| Alpaca MCP (cloud) | Same pattern as Tiger. Read-only market data. | .env + Cloud Run secret |
| IBKR | Client Portal Gateway runs ON the PC; you log in interactively; sessions kept alive locally; localhost-only, nothing exposed to the internet. | Gateway session on PC |
| FMP | API key in env (FMP_API_KEY). | .env |
| Harness | Claude/Kimi subscription login on the PC. | Vendor keychain |
| Drive mirror (optional) | rclone OAuth token created once on the PC. | rclone.conf on PC |
Rules: one `.env` file on the PC (git-ignored, template committed as `config/env.example`) · every credential is least-privilege · rotating any key touches exactly one place · the repo going public by accident leaks zero secrets.

## 7.3 The autopilot switch (D-7) — how autonomy actually works
Default is PREVIEW, always. You arm autopilot in plain English (`/arm`) → `tools/autopilot.py` writes a dated, reasoned, auto-expiring state (fixed expiry: next 05:30 SGT — past US close in any season, no timezone math (D-7a)) and logs it. While armed and inside the window: the Staging Gatekeeper — the only order-capable agent — may execute Tiger's place-preview → confirm two-step, but only for tickers on your APPROVED plan with the preauthorised flag, only within caps (max 1.0R/order, max 3/session, both tunable). Any kill condition — tripwire block, gate breach, broker error, window end — disarms FIRST, then notifies you. Disarmed/expired/absent state all mean OFF. You can disarm any time with one line. Autonomy is therefore something you *lend* the system for a bounded window, never something it has.

## 7.4 The development loop (D-8) — how the system changes without decaying
Findings (from Design & Review, a breach, or your idea) → backlog items that MUST name what they retire → your one-tap morning approval → built on a git branch by a coding agent → verified (compile, contracts, tripwires, both packagings) and shadow-run for a day with the diff shown to you → merged, versioned, changelogged → re-measured 15 sessions later: did the promised effect appear? No edit happens outside this pipeline except your own parameter tweaks, which self-log. This loop is the direct answer to how the old system became spaghetti: change without memory. Now change IS memory.

*End of context document. If this file and the charter disagree, the charter wins and this file gets fixed.*
