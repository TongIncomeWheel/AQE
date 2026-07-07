# AQE Backlog — 2026-07-07

**Mode:** planning. Nothing here is being executed yet — this is the agreed worklist,
structured from the PM's 7 inputs into the 3 categories.

---

## ⭐ The insight that reshapes items 1, 3, 4, 5, 6

**AQE already computes structural brackets — the alerts and Pricer just don't use them.**

The daily export already carries, per ticker (DSG-18 / Charter v2.3 work):
- **`optimal_stop`** = the *tightest structural support* that passes the 3 gates (ATR floor ≥1.0,
  R:R-TP2 ≥2.0, risk% ≤ regime ceiling). Candidates are **swing lows, MA cluster (MA20/50),
  fib_618/786, MA20/50/100/200** — i.e. exactly "last support / MA / Fib" (item 4).
- **`structural_targets`** = *structural resistance* nearest-first: prior pivot highs, the prior
  swing high, and **fib extensions (1.272/1.618/2.0/2.618)** (item 5). It's already β-adjusted
  (the DSL stop uses 30-day β) and ATR-gated.

**But** the **alert engine** and the **email** still show the *mechanical* ladder
(`dsl_tp_1r/2r/3r` = entry + 1/2/3 × R) — that's item 3's complaint. And the labelling is messy
enough (item 6) that AIC can't tell the structural levels from the mechanical ones.

➡️ **So items 3/4/5 are mostly "surface + wire the structural brackets we already have," not
"build them." The build that remains is calibration (is `optimal_stop` really the *closest* valid
support? is the ATR-relative labelling right?) + pointing the alerts/Pricer at them + a clean
data pass.** This is the thread that ties the whole backlog together.

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

---

## 2 · Bracket & Charting Methodology

**2.1 — Alert TP must be structural, not mechanical** *(input #3)*
- Today the alert/email shows `2×ATR / 2×SL` mechanical TP. Replace with the **structural target**
  (nearest `structural_targets` resistance / fib) — which the export already carries.

**2.2 — SL = closest structural support** *(input #4)*
- Rule: SL = nearest structural support, β(30d)- and ATR-aware; candidates = **last support / MA /
  Fib**. → this *is* `optimal_stop`'s definition. Task = verify it picks the **closest** valid
  support (not just the tightest-passing) and that its risk is sane relative to ATR.

**2.3 — TP = closest structural resistance** *(input #5)*
- Rule: TP = nearest structural resistance, β/ATR-aware; candidates = **support/MA/Fib**; soft
  secondary = **TPx + ATR**, but **Fibs preferred**. → this *is* `structural_targets`. Task = confirm
  nearest-first ordering + fib preference; expose the "TP + ATR" soft variant if wanted.

**2.4 — Merge Pricer into Chart & Trade Entry; drop sizing** *(input #7)*
- Combine the Pricer page into the (already-merged) Charts + Trade Entry page. **Remove position
  sizing** — AIC sizes, AQE just shows levels. Reduces surface + the slow pull (ties to 1.2).

*(Cross-ref: 2.1/2.2/2.3 all resolve to "use `optimal_stop` + `structural_targets` everywhere —
export, alerts, chart — and retire the mechanical `dsl_tp_*` from what AIC reads.")*

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
1.1 Audit alerts (universe + triggers + what a "bracket" is)   ← foundation, defines truth
        │
        ├─► 2.2 SL = optimal_stop (verify "closest" + ATR sanity)
        ├─► 2.3 TP = structural_targets (verify nearest-first + fib)
        │        │
        │        └─► 2.1 Wire structural bracket into alerts (retire mechanical TP)
        │
        └─► 3.1/3.3 Clean + ATR-label the levels  ──► 3.2 readiness/conviction clarity
                                                   └─► 3.4 GICS + thematic direction per ticker
1.2 Pricer/chart pull perf ──► 2.4 merge Pricer+Chart, drop sizing
```

**Proposed order:** **1.1 (audit)** → **2.2/2.3 (lock the structural SL/TP definition)** →
**2.1 + 3.1/3.3 (wire it in + clean feed)** → **3.2/3.4 (labels + sector/thematic direction)** →
**1.2 + 2.4 (chart perf + merge, in parallel)**.

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
2. **`optimal_stop` = "closest valid support"** (item 4) vs the current "tightest valid"? They can
   differ. → PM to confirm "closest."
3. ~~Alert universe?~~ **RESOLVED — held + longlist + elder + Signal Radar; drop the broad
   `_alert_pool`.**
4. Chart pull (1.2) — **per-ticker on-demand** default + cache the monitored set?
5. ~~Backtest simulator?~~ **RESOLVED — retire it.**
6. ~~Un-bracketable names?~~ **RESOLVED — show "no valid bracket."**
