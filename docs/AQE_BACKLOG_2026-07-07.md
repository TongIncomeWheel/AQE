# AQE Backlog — 2026-07-07

**Mode:** planning. Nothing here is being executed yet — this is the agreed worklist,
structured from the PM's 7 inputs into the 3 categories.

---

## ⭐ The spine — one Bracketing Engine everything references

**The root cause of items 3/4/5/6 is that brackets are computed in several places with different
logic: `levels.py` (structural `optimal_stop`/`structural_targets`), `dsl.py` (mechanical DSL),
the alert engine (re-derives a buy-zone from `dsl_stop`+1.5·`dsl_risk`), the Pricer (its own),
the intraday `bracket.py` (its own). That divergence IS the "unclean data / messed-up columns."**

**The clean design (PM ruling): a single Bracketing Engine — one source of truth for every
stop/target, referenced by the export, alerts, Pricer, charts, and signal ledger, with one shared
schema (same data, same tables). See §2.0.** The good news: the structural logic already exists in
`levels.py` (closest support / resistance via swing lows, MA, Fib) — the work is to consolidate it
into the engine, delete the mechanical DSL, and make everyone read the engine's output.

➡️ **This is the thread that ties the whole backlog together: build the engine (2.0) → the export,
alerts, chart, and ledger all reference it → the feed is automatically clean because there's only
one bracket definition.**

---

## 1 · Data pull

**1.1 — Audit the AQE alert pull** *(from input #1)*
- **Current universe:** `held_positions` → `longlist` → `elder_list` → `_alert_pool` (broad, raw
  SC_MOM ≥ 50, ~100+ names) → `_radar_pool` (Signal-Radar). Quotes = 15-min-delayed FMP
  `/stable/quote`, one fetch per cycle for the whole set.
- **🔒 PM ruling — narrow the universe to the daily AQE list + signal ledger:**
  **`held_positions` + `longlist` + `elder_list` + `_radar_pool` (Signal Radar). DROP `_alert_pool`**
  (the broad SC≥50 pool — that's the noise). Alerts should fire only on names AQE actually surfaces
  that day.
  - *Note:* `_alert_pool` was originally added because the tight list rarely tripped the narrow
    bands — so expect **fewer alerts**. The Signal-Radar names (esp. pre-move coils) now backfill
    that, which is the point: relevant > frequent.
- **What triggers an alert (current):** 3 bounded events — **Hit buy price** (candle traded
  *through* `dsl_stop + 1.5·dsl_risk`), **fresh Breakout** (2–8% over entry), **Approaching stop**.
  Radar names fire only on the two upside events.
  - → the trigger levels get re-based onto the structural bracket (item 2.1 / the DSL-retirement).

**1.2 — Pricer / Chart pull is too slow** *(from input #2)*
- Problem: pulling 15-min data on every chart request takes ~10 min → unusable.
- Options on the table (PM open to ideas):
  - **(a) Persistence layer** — the alert poller already fetches quotes every 15 min; cache them
    (Drive/local) so the chart reads the cache instead of re-pulling.
  - **(b) Per-ticker on-demand pull** — don't pull the universe; pull just the one ticker being
    charted (fast, seconds).
  - Likely answer: **(b) for the chart the PM is looking at** + **(a) cache** for the monitored set.
- Shares the "per-ticker vs universe pull" question with 1.1.
- **Feed cadence — stay 15-min delayed (recommendation, PM-aligned).** Real-time live is *not*
  recommended for AQE's feed/alerts: the signals are EOD/swing, so 15-min granularity is plenty to
  see a level cross; live is noisier and would trip more false level-crosses (the PM's own concern).
  Live's real benefit is *execution precision* — and that belongs at the **broker (IBKR) at order
  time**, not in AQE's scanning feed. Net: 15-min FMP is the right call; no data upgrade needed.

---

## 2 · Bracket & Charting Methodology

### 🔒 2.0 — THE BRACKETING ENGINE (architectural spine, PM ruling)

**The clean design: one bracketing engine is the single source of truth for every stop/target in
AQE. Everything references the same output — same data, same tables, no re-derivation anywhere.**

- **New module** (e.g. `src/engines/bracket_engine.py`) computes the canonical bracket for a ticker
  from daily bars + β(30d) + ATR + regime, and emits ONE bracket object/table:
  `{ price, price_source, stop, stop_type, stop_atr_dist, risk, targets[ {price, type, r, ...} ],
    rr, valid, invalid_reason }`.
- **🔒 Price source = FMP, always (PM ruling).** Structural levels (stop/targets) are FIXED from the
  bars; **R:R and distances are computed against the passed-in price**:
  - **Daily run** → `price = FMP close-of-day` → the EOD snapshot as the name enters the watchlist.
  - **Live pull** (chart / bracket / entry) → `price = FMP 15-min-delayed quote`.
  - Fixes today's inconsistency (alert fires on live price but shows EOD R:R). Same engine, price
    passed in, R:R recomputed. `price_source` stamped so AIC knows which it's reading.
  - **Stay 15-min delayed** (not real-time live) — see the feed-cadence note in §1.2.
- **Every consumer calls it — none compute their own bracket:**
  - the **Drive export** stamps the bracket per record (replaces the scattered `optimal_stop` /
    `structural_targets` / `dsl_*` assembly),
  - the **alert engine** triggers off the bracket (buy-zone / breakout / near-stop derived from it),
  - the **Pricer** + **Charts/Trade-Entry** display it,
  - the **signal ledger / paper-track** scores outcomes against it.
- **One schema, referenced everywhere** — the bracket's field set + glossary are defined once by the
  engine; the export schema, the UI tables, and the alert email all read that same definition. No
  per-consumer column remixing (that's the "unclean data" in item 6).
- This makes the DSL retirement trivial: there is simply **nothing else computing a bracket** — the
  mechanical `dsl_*` construct is deleted, not replaced piecemeal.
- The engine **owns the SL/TP rule** (below) — so "closest vs tightest" is decided *once, in one
  place*, not re-litigated per consumer.

**Absorbs inputs #3/#4/#5** — these are no longer separate tasks, they are the engine's definition:

- **Stop rule (input #4) — 🔒 RESOLVED = TIGHTEST VALID:** SL = among the structural candidates
  (last support / MA / Fib) that PASS the 3 gates, take the one **closest to entry** (highest price
  = smallest risk). This *is* the current `optimal_stop` logic — no change. "Tightest valid" is how
  you get a well-defined "closest support": the gates are the tie-breaker that stops a too-near
  level from being picked. β(30d)/ATR-aware via the gates.
- **Target rule (input #5):** TP = **closest structural resistance** above entry, β/ATR-aware;
  candidates = pivot high / MA / Fib; **Fibs preferred**; soft secondary = **TPx + ATR**.
- **Alert levels (input #3):** the alert's buy/TP/stop all read the engine's bracket — mechanical
  `2×ATR / 2×SL` is gone.
- **Un-bracketable:** when no candidate passes the gates → `valid=false`, `invalid_reason` set; the
  feed shows **"no valid bracket"** (no fallback).

**2.4 — Merge Pricer into Chart & Trade Entry; drop sizing** *(input #7)*
- Combine the Pricer page into the (already-merged) Charts + Trade Entry page. **Remove position
  sizing** — AIC sizes, AQE just shows levels. Both then render the **same bracket-engine output**
  (ties to 1.2 + 2.0).

---

## 3 · Clean / simplified data feed to AIC

**3.1 — DSL levels are odd / badly labelled / not ATR-relative** *(input #6)*
- Raw `dsl_stop`/`dsl_tp_*` are absolute USD with confusing names. Make every level **ATR-relative
  and clearly labelled** (or drop the mechanical ones in favour of the structural bracket).

**3.2 — Readiness + conviction not understood by AIC** *(input #6)*
- The signal-ledger readiness (`rd_*`) and radar conviction reach AIC as bare scores. We added
  `conviction_label` ("HIGH (3/4)"); do the same clarity pass for readiness/health, or cut what
  AIC doesn't use.

**3.3 — Too much unclean data / messed-up columns** *(input #6)*
- A field-pruning pass: keep only what AIC reads; remove/rename the rest. (Continues the earlier
  removal of rr_tp1/2/3, rr_est, disposition, bare `stop`.)

**3.4 — Add per-ticker GICS + Thematic *direction* for the day** *(input #6)*
- Each watchlist ticker should carry its **GICS direction** and **Thematic direction** for the day —
  we already compute these (SRM `trend_state` / RRG direction, thematic-basket RRG). Task = surface
  them cleanly per record, not just in the top-level SRM block.

---

## Dependencies & suggested sequence

```
2.0 BRACKETING ENGINE  ← the spine: one engine, one schema, one output
     (owns SL=closest support, TP=closest resistance, valid/invalid)
        │
        ├─► export stamps the engine's bracket   ──► retire mechanical dsl_* (fix-forward)
        ├─► alerts trigger off the engine's bracket (1.1 universe already narrowed)
        ├─► Pricer + Charts render the engine's bracket ──► 2.4 merge + drop sizing
        ├─► signal ledger scores outcomes vs the engine's bracket
        └─► feed is clean by construction (3.1/3.3) ──► 3.2 readiness/conviction labels
                                                     └─► 3.4 GICS + thematic direction per ticker
1.2 Pricer/chart pull perf (per-ticker + cache) — parallel, feeds 2.4
```

**Proposed order:** **2.0 build the engine** (owns the SL/TP rule) → **repoint export + alerts +
ledger at it, delete mechanical DSL** → **feed clean-up falls out (3.1/3.3)** → **3.2/3.4 (labels +
sector/thematic direction)** → **1.2 + 2.4 (chart perf + merge, parallel)**.

## 🔒 PM DECISION — retire mechanical DSL + TP across the WHOLE AQE

**Ruling (2026-07-07):** the mechanical stop/target ladder is "nonsense and noise." Retire it
**everywhere it is AIC-facing or drives a live decision.** The **structural bracket becomes THE
bracket**: operative stop = `optimal_stop` (closest structural support), targets =
`structural_targets` (structural resistance / MA / fib). R (risk unit) = `entry − optimal_stop`.

**Fields to retire from the export / alerts / chart:** `dsl_stop`, `dsl_risk`, `dsl_tp_1r/2r/3r`,
`dsl_rr_pct`, `dsl_atr_ratio` (as the operative levels), plus the derived mechanical helpers
`coil_entry`, `max_chase_tp2/tp3`, `rr_tp2_at_coil`/`rr_tp3_at_coil`. Rename the survivors to plain
structural terms (stop / risk / targets) — no "DSL" vocabulary in the AIC feed.

**Approach (PM ruling):** **remove altogether — clean removal, fix-forward.** No careful re-base,
no compatibility shims. "Slapping data over data is stupid." We rip out the mechanical fields and
the DSL construct, then fix whatever breaks *as it surfaces* — no layering to preserve dead vocab.

### Known breakage points (fix-forward, not pre-emptive re-base)
These read the mechanical fields and WILL break on removal — we fix each at the structural bracket
when it surfaces (listed so we know where to look, not to gate the removal):
- **Alert triggers** — `BUY_ZONE` = `dsl_stop + 1.5·dsl_risk`; the email R:R line → `optimal_stop`
  + `structural_targets`.
- **Signal ledger / paper-track** — TP/SL-hit uses `dsl_stop`/`dsl_tp_1r/2r` → structural
  stop/targets.
- **`structural_targets[].r_optimal`** — currently falls back to `dsl_risk` → structural risk only.
- **Schema validator `_REQUIRED_FIELDS`** — lists the `dsl_*` fields → drop them from the required
  set (else the export self-blocks).
- **`_FIELD_SCHEMA` / `_FIELD_GLOSSARY`** — drop the mechanical entries (lockstep test).
- **Scanner / Pricer / Charts UI** — any column reading `dsl_*` → structural.

### 🔒 Backtest DSL simulator — RETIRE (PM ruling)
`src/scanner/dsl.py` R-tier trailing + flow-TP simulator is retired too. The backtest ruler goes
structural along with everything else.

### 🔒 Un-bracketable names — SHOW "no valid bracket" (PM ruling)
When no structural candidate passes the 3 gates (`optimal_stop_exists = false`), the name stays in
the feed but is **flagged "no valid bracket"** — no stop/target shown, no mechanical fallback. The
proper fallback logic is the separate **bracketing-engine refinement**.

## Remaining open questions for the PM
1. ~~Retire mechanical TP?~~ **RESOLVED — remove mechanical DSL *and* TP altogether, whole-AQE.**
2. ~~Engine stop rule?~~ **RESOLVED — TIGHTEST VALID** (= closest structural support that passes the
   gates; the current `optimal_stop` logic, unchanged).
3. ~~Alert universe?~~ **RESOLVED — held + longlist + elder + Signal Radar; drop the broad
   `_alert_pool`.**
4. Chart pull (1.2) — **per-ticker on-demand** default + cache the monitored set?
5. ~~Backtest simulator?~~ **RESOLVED — retire it.**
6. ~~Un-bracketable names?~~ **RESOLVED — show "no valid bracket."**
