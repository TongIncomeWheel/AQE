# AQE — Bracketing Engine Migration: Executive Summary

**For:** PM + Chief Programmer · **Date:** 2026-07-07 · **Status:** code-complete, full test
suite green (154/154), **pending UAT on HuggingFace**.

---

## 1. What changed (and why)

**The problem.** Stops and take-profits were computed in *five different places* with *different
logic* — the export (`levels.py` + `drive_sync`), the alert engine, the signal ledger, the Pricer,
and the intraday layer — and they leaned on a **mechanical DSL/TP ladder** (`dsl_stop`,
`dsl_tp_1r/2r/3r` = entry + N×R, `optimal_stop`, `coil_entry`, `max_chase`, …). This was the "unclean
data / messed-up columns" the AIC couldn't reliably read, and the alerts showed a *mechanical* 2×ATR
TP that had nothing to do with real structure.

**The fix (PM ruling).** One **Bracketing Engine** is now the single source of truth. Every
consumer — export, alerts, signal ledger, Pricer, charts, intraday, and the backtest simulator —
references the *same* structural bracket. Mechanical DSL/TP is **retired everywhere**.

| Area | Before | After |
|---|---|---|
| **Bracket logic** | 5 implementations, mechanical | 1 engine (`src/engines/bracket_engine.py`), structural |
| **Stop** | `dsl_stop` = 5-day-low − ½ATR, clamped | **tightest valid structural support** (swing/MA/fib passing 3 gates) |
| **Targets** | `dsl_tp_1r/2r/3r` = entry + N×R (mechanical) | **structural resistance / MA / fib**, nearest-first |
| **R:R** | vs mechanical TP2 | vs the **structural TP2**, re-priced against the current price |
| **Price basis** | close only | **FMP EOD close** (daily) or **FMP 15-min** (live pull), stamped |
| **Un-bracketable** | mechanical fallback (noise) | **"no valid bracket"** — no fallback |
| **Position sizing** | AQE computed `shares` | **removed — AIC sizes** |

**Also shipped this session (data-pull reliability, Phase 1):**
- **MA scanner decoupled** from the daily pipeline → runs **weekly, standalone**, with a **persisted
  panel** (fixes the 40-min feed timeout — it was re-pulling ~2000 tickers every run).
- **Alert universe narrowed** to the daily list + Signal Radar (dropped the broad SC≥50 pool).
- **Pipeline timeout** raised 2400→3300 s + honest "partial" status + per-step timing.

---

## 2. Scaffolding — how the change was managed

A high-blast-radius change (18 files) on a real-money system, executed to keep it reversible and
observable at every step:

1. **Frozen backlog first.** Every decision (retire mechanical, tightest-valid stop, price source,
   alert universe, MA cadence, drop sizing) was written down and PM-ruled *before* code —
   `docs/AQE_BACKLOG_2026-07-07.md`.
2. **Engine-first, additive.** Built + unit-tested the engine in isolation (10 tests) **before**
   wiring any consumer — nothing could break while the foundation was proven.
3. **Risk-ordered chunks, one commit each.** export → alerts → ledger → intraday → UI → simulator →
   sizing. Each chunk was verified and committed separately (WIP-tagged), so the work is
   **recycle-safe** and each step is a clean diff.
4. **Fix-forward, no compatibility shims.** Mechanical fields were *deleted*, not shadowed — the
   known breakage points were fixed as they surfaced (no "data over data").
5. **Schema/glossary kept in lockstep.** The machine-readable `field_schema` + prose `field_glossary`
   were updated together, with a test that enforces they never drift.
6. **Backtest = live.** The simulator wasn't deleted; it was **re-pointed at the same engine**, so
   backtests and the live feed can never diverge.

---

## 3. What was tested (and what wasn't)

**Automated — full suite green: 154/154 tests.**
- **Engine (10 unit tests):** tightest-valid stop selection, nearest-first targets, un-bracketable
  cases (no resistance / no gate-passing support), regime-ceiling tightening, price-source
  re-pricing, de-dup, "no mechanical dsl_stop candidate."
- **Export contract:** record carries the `bracket`; every retired field is absent from records,
  schema, glossary, and the required-fields validator; schema↔glossary lockstep holds.
- **Alerts:** buy-zone / breakout / near-stop fire off the bracket; "no valid bracket" degradation.
- **Signal ledger:** records + reconciles from the bracket (7 tests).
- **Intraday (20 tests):** operative stop, entry zones, plan, Pricer — all on the bracket; sizing
  removed.
- **Backtest simulator (4 tests):** runs on the structural stop.
- **Per-chunk gates:** syntax + import + targeted functional checks before every commit.

**Not covered by the automated suite (→ verify in UAT):**
- **UI rendering.** Streamlit isn't installed in the build container, so the Scanner / Charts /
  Pricer pages are **syntax- and import-verified only**. Confirm the tables + chart overlays show
  the bracket in UAT.
- **The real export build.** No test builds the full export (it needs the live parquets). The
  first HF pipeline run is the true end-to-end check — diff a couple of records to confirm
  `bracket` is populated and the old fields are gone.

**Outcome:** the entire live path AIC and the PM touch — export JSON, alert emails, Scanner tables,
chart overlays, intraday plans — now reads one structural bracket. Suite green, work committed to
GitHub `main`. **Do not `push_both` to HF until UAT** of the UI is done.

---

## 4. Glossary — data points, methodology, what ships to AIC

### The `bracket` object (per ticker, on every export record)

```jsonc
"bracket": {
  "price":         100.00,        // reference price the R:R is measured against
  "price_source":  "eod_close",   // eod_close (daily run) | live_15min (live pull)
  "stop":          96.00,         // operative STOP (below price) — the tightest valid support
  "stop_type":     "ma50",        // what the stop sits on: swing_low_1/2/3 | ma20/50/100/200 | ma_cluster | fib_618/786
  "stop_atr_dist": 2.00,          // risk in ATRs (read this, not raw USD)
  "risk":          4.00,          // = price − stop  (1R, the structural risk unit)
  "risk_pct":      4.00,          // risk as % of price
  "targets": [                    // structural resistance ABOVE price, nearest-first
    {"type": "resistance", "price": 108.0, "r": 2.0, "atr_dist": 4.0},
    {"type": "fib_1618",   "price": 116.0, "r": 4.0, "atr_dist": 8.0}
  ],
  "rr":            3.0,           // R:R to the structural TP2 (headline reward:risk)
  "valid":         true,          // false → "no valid bracket" (do not trade / show flagged)
  "invalid_reason": null          // why, when valid=false
}
```

### Field-by-field

| Field | Meaning | How it's calculated |
|---|---|---|
| `price` / `price_source` | The price R:R is measured against | FMP **EOD close** on the nightly run; FMP **15-min quote** on a live Pricer/chart pull. Structural levels are fixed from bars; only this reference re-prices. |
| `stop` | The operative protective stop | **Tightest valid structural support**: of all candidate supports below price that pass the 3 gates, the one **closest to price** (smallest risk). |
| `stop_type` | Which structural level the stop is | `swing_low_1/2/3` (last confirmed pivot lows), `ma20/50/100/200`, `ma_cluster` (MA20+MA50 confluence within 1×ATR), `fib_618/786` retracements. **No mechanical `dsl_stop`.** |
| `stop_atr_dist` | Risk expressed in ATRs | `risk / ATR(14)` — the ATR-relative read the AIC uses instead of raw USD. |
| `risk` | 1R in USD | `price − stop` (the **structural** risk unit — everything R is measured off this). |
| `targets[]` | Take-profit levels | Structural resistance above price, **nearest-first**: prior confirmed pivot highs, the prior swing high, and fib measured-move extensions (1.272/1.618/2.0/2.618). Near-equal levels (within ½ATR) collapse; resistance wins de-dup ties. |
| `targets[].r` | Reward of that target in R | `(target − price) / risk`. |
| `rr` | Headline reward:risk | R:R to the **2nd** structural target (TP2). |
| `valid` / `invalid_reason` | Is there a tradeable bracket? | `false` when no support passes the gates, or no resistance exists above price. **No mechanical fallback** — the feed shows "no valid bracket". |

### The 3 gates (Charter §4.2) — a stop candidate is *valid* only if all pass

1. **ATR floor:** `stop_atr_dist ≥ 1.0` (the stop is ≥ 1×ATR away — not noise).
2. **R:R gate:** `rr ≥ 2.0` (at least 2:1 to the structural TP2).
3. **Regime ceiling:** `risk_pct ≤` GREEN 12% / YELLOW 8% / ORANGE 6% / RED 4%.

### Methodology in one line
> **Structural levels are fixed from the daily bars; the bracket re-prices against the current FMP
> price. The stop is the closest support that still gives a real (gated) trade; the targets are the
> real resistance above. R = price − stop. No mechanical R-multiples anywhere.**

### What ships to AIC (the daily export JSON)
- Per record (longlist / elder_list / held): the `bracket` object above, plus `entry`, `atr_14d`,
  the flat fib ladder, MAs, GICS + thematic tags, Signal-Radar detection tags, readiness/health.
- Top-level: `field_schema` (machine-readable role/unit/side per field) + `field_glossary` (this
  prose) so the AIC reads a stop as a stop and a target as a target — structurally, never by guessing.
- **Retired from the feed:** `dsl_stop`, `dsl_risk`, `dsl_tp_1r/2r/3r`, `dsl_rr_pct`,
  `dsl_atr_ratio`, `optimal_stop`, `structural_levels`, `structural_targets`, `coil_entry`,
  `max_chase_tp2/3`, `rr_tp2/3_at_coil`, and all position sizing (`shares`, `dsl_shares`).

---

*Full derivation + per-decision rationale: `docs/AQE_BACKLOG_2026-07-07.md`. Engine:
`src/engines/bracket_engine.py`. Commits: the Phase-2a…2f series on `main` (each chunk a separate,
reviewable diff).*
