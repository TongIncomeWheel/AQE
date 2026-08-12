# S0 — PREFLIGHT · voices loaded, data fresh · NOTHING RUNS UNTIL THIS PASSES

**Added 2026-08-12 on PM instruction, from two failures observed in the sample run.** This is
the first stage of `/premarket-analysis`. It is deterministic, cheap, and it is a **gate** —
a failed preflight stands the run down rather than degrading it.

---

## Why this exists

**Failure 1 — voices expire out of runtime.** Over the course of one build session the set of
loaded voice skills changed repeatedly: seats present at the start were absent later, and
`canon/detect-lens/canon.lock.yaml` and `canon/livermore/canon.lock.yaml` vanished from the
working checkout mid-run — both seats ran from card-only grounding and had to declare it.
Nothing detected this. The committee silently ran with degraded seats.

**Failure 2 — staleness was only discovered by the voices.** The 2026-08-12 run put a 15-day-old
export next to a same-day Crown file. All eleven seats independently flagged that the market
frame was internally 15 days apart — the momentum caveat computed off a stale VIX of 18.7 while
live Crown carried 15.28. **The committee caught what the pipeline should have caught.** That is
backwards: it costs eleven agent-runs to discover something one timestamp comparison would have
told us before any of them spawned.

---

## PART A — VOICE ROSTER CHECK

For every seat in the expected roster, confirm three things and record all three:

| Check | Source | Fail means |
|---|---|---|
| **Skill card present** | `plugins/synced/aegis-voices/skills/voice-<v>/SKILL.md` | seat cannot run at all |
| **Canon lock present** | `canon/<v>/canon.lock.yaml` — local, else fetch from GitHub `main` | seat runs **UNGROUNDED** |
| **Canon integrity** | `counts.principles` / `counts.recognisers` match the arrays; `pm_signed` present | seat runs on a corrupt spine |

**Self-heal, in order:** missing canon locally → **fetch from GitHub `main`** (the remote is the
source of record; local disk is disposable and has been wiped five times in one build). Missing
card → the seat is `UNAVAILABLE`.

**Output** `data/pma/<date>/voice_roster.json`:
```
expected[] · loaded[] · ungrounded[{voice, reason, healed_from_github: bool}] ·
unavailable[{voice, reason}] · canon_versions{voice: {principles, recognisers, pm_signed}} ·
quorum_met: bool
```

**Gate:** `loaded >= 8` of the nominating seats, else **STAND DOWN** — no plan. Any seat running
ungrounded is named in the report's Section 5 and its nominations carry a `grounding: CARD_ONLY`
tag through to the CIO page. A degraded seat is never silently counted as a full seat.

---

## PART B — DATA FRESHNESS CROSS-CHECK

Two files, two timestamps, and — this is the point — **the gap between them**.

| Field | AQE daily export | Nick Crown macro |
|---|---|---|
| Timestamp read from | `date` | `generated_at` |
| Also read | — | `how_current.oldest_source_days_behind` |

**Three tests, all must be recorded:**

1. **Absolute age** — how old is each file against the run date, in *trading* days
2. **Relative gap** — how far apart are the two files from each other
3. **Crown's own internal age** — its `oldest_source_days_behind`, because a run stamped today
   built on three-week-old legs is a three-week-old read whatever the stamp says

### Trading-day calendar (PM ruling 2026-08-12)

Age is measured in **trading days, not calendar days.** Monday reading Saturday's file is a
0-trading-day gap and is **normal** — the weekend is not staleness. Implement with a simple
weekday rule now.

**Midweek trading holidays are deliberately NOT handled** — logged to backlog, PM ruling. Until
a market calendar is wired in, a holiday will read as one spurious stale day. Accepting a known
small false-positive beats a hidden wrong-calendar bug.

### Thresholds

| Condition | Verdict | Behaviour |
|---|---|---|
| Both files ≤ 1 trading day old, gap ≤ 1 | **FRESH** | proceed silently |
| Either 2–3 trading days old, or gap 2–3 | **STALE** | proceed, banner on the report, declaration in every voice packet |
| Either > 3 trading days old, or gap > 3 | **BLOCKED** | requires explicit `--ack "<reason>"`, recorded **verbatim** and reprinted in Section 1 and Section 5 |
| Crown `oldest_source_days_behind` > 3 | **DEGRADED-INPUT** | flag regardless of the file's own stamp |

**The relative gap is the one that bit us.** Two individually-acceptable files can still be 15
days apart from each other, and a market frame assembled from both halves is then internally
inconsistent — which is exactly what all eleven seats reported. The gap is a first-class test,
not a derived nicety.

**Output** `data/pma/<date>/freshness_check.json`:
```
run_date · export{date, trading_days_old} · crown{generated_at, trading_days_old, oldest_source_days_behind} ·
gap_trading_days · verdict · ack_text · weekend_adjusted: bool · holiday_calendar: "NOT_IMPLEMENTED (backlog)"
```

---

## The preflight gate

```
voice_roster.quorum_met == false   → STAND DOWN
freshness.verdict == BLOCKED and no --ack → STAND DOWN
otherwise → proceed, carrying both records into every downstream packet and into Sections 1 and 5
```

Both artifacts are written **and pushed** before any voice spawns. Preflight evidence that exists
only on local disk is preflight evidence that will be gone by the time anyone asks.
