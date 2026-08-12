# S0 — PREFLIGHT · INJECT the voices, then verify the data · NOTHING RUNS UNTIL THIS PASSES

**PM instruction 2026-08-12: "insert procedure to inject voices as step 0 of running PMA."**
This is stronger than a check, and the distinction matters. Over one build session, seats
present at the start were absent later; `canon/detect-lens/canon.lock.yaml` and
`canon/livermore/canon.lock.yaml` vanished from the working checkout mid-run and both seats ran
card-only without anyone noticing. **Loaded voices expire out of runtime.** So S0 does not ask
whether they are there — it puts them there, every run, from the source of record.

---

## PART A — VOICE INJECTION

### A1 · Resolve the roster
The roster is **`canon/` on GitHub `main`**, not whatever happens to be in the container.
Enumerate the seats and their declared kind (`nominator` · `challenge` · `weather`). The
remote is authoritative because local disk is disposable — it has been wiped five times in one
build, and every artifact that survived did so because it was pushed.

### A2 · Materialise each seat — fetch, never assume
For every seat, pull from GitHub `main` into the run's working set:

| Component | Path | Missing means |
|---|---|---|
| Method card | `skills/voice-<v>/SKILL.md` | seat is `UNAVAILABLE` |
| Canon lock | `canon/<v>/canon.lock.yaml` | seat is `UNGROUNDED` |
| Spot-check | `canon/<v>/spotcheck.json` | grounding is `UNVERIFIED` |

Fetch unconditionally. Do not test-then-fetch: a stale local copy is worse than no copy, because
it looks correct. **This step is the self-heal** — the failure that produced card-only seats
becomes impossible when the canon is pulled fresh every run.

### A3 · Verify what was injected
Per seat: `counts.principles` and `counts.recognisers` match the arrays · `pm_signed` present ·
canon `voice` key matches the directory · card and canon agree on seat kind.

Record a **grounding tier** for every seat, because the sample run showed four distinct states
and only one of them is fully sound:

| Tier | Meaning | Observed 2026-08-12 |
|---|---|---|
| `SIGNED` | lock present, PM-signed, spot-checked | **raschke only** |
| `LOCKED_UNSIGNED` | lock present, no PM signature | most seats |
| `PENDING` | principles exist, no lock | steenbarger, livermore |
| `CARD_ONLY` | no canon at all | **detect-lens** |

### A4 · Bind into the run
Write `data/pma/<date>/voice_roster.json` — `expected[]` · `injected[]` · `grounding_tier{}` ·
`unavailable[]` · `canon_versions{}` · `fetched_from` (commit SHA of `main`) · `quorum_met`.

**Every downstream packet carries its seat's tier**, and every nomination inherits it. A
`CARD_ONLY` seat's picks are tagged as such through the tally, the deliberation and onto the CIO
page. A degraded seat is never silently counted as a full one.

**Gate:** fewer than 8 nominating seats injected → **STAND DOWN**.

---

## PART B — DATA FRESHNESS CROSS-CHECK

Two files, two timestamps, and — the point — **the gap between them**.

| | AQE daily export | Nick Crown macro |
|---|---|---|
| Timestamp | `date` | `generated_at` |
| Also read | — | `how_current.oldest_source_days_behind` |

**Three tests, all recorded:** absolute age of each file in *trading* days · the gap between
them · Crown's own internal age.

### Trading-day calendar (PM ruling)
Monday reading Saturday's file is a **0-trading-day** gap and is normal — a weekend is not
staleness. Weekday rule now. **Midweek trading holidays are deliberately NOT handled** — PM
ruling, backlogged. A holiday will read as one spurious stale day; a known small false positive
beats a hidden wrong-calendar bug.

### Thresholds

| Condition | Verdict | Behaviour |
|---|---|---|
| Both ≤1 trading day old, gap ≤1 | **FRESH** | proceed silently |
| Either 2–3 old, or gap 2–3 | **STALE** | proceed; banner on the report; declared in every packet |
| Either >3 old, or gap >3 | **BLOCKED** | needs explicit `--ack`, recorded **verbatim**, reprinted in Sections 1 and 5 |
| Crown `oldest_source_days_behind` >3 | **DEGRADED-INPUT** | flag regardless of the file's own stamp |

**The relative gap is the one that bit us.** Two individually-acceptable files can still be 11
trading days apart, and a frame built from both halves is then internally inconsistent. The gap
is a first-class test.

`data/pma/<date>/freshness_check.json`: `run_date` · `export{date, trading_days_old}` ·
`crown{generated_at, trading_days_old, oldest_source_days_behind}` · `gap_trading_days` ·
`verdict` · `ack_text` · `weekend_adjusted` · `holiday_calendar: "NOT_IMPLEMENTED (backlog)"`.

---

## The gate

```
voice_roster.quorum_met == false           → STAND DOWN
freshness.verdict == BLOCKED and no --ack  → STAND DOWN
otherwise → proceed, carrying both records into every packet and into Sections 1 and 5
```

Both artifacts are written **and pushed** before any voice spawns. Preflight evidence that lives
only on local disk will be gone by the time anyone asks for it.
