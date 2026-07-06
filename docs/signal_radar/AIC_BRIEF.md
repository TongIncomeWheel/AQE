# Signal Radar — AIC Briefing

**Status:** LIVE in the AQE pipeline (additive, deployed 2026-07-06).
**Audience:** AI Investment Committee — read this before using the tags.
**One-line:** a data-driven pre-market radar that answers two questions AQE's
scoring engines were never built to answer — *what's about to run* and *what will
keep running* — delivered as tags AIC reads, never as automatic gates or sizing.

---

## 0. The single most important sentence

**Every number this system reports is a DETECTION RATE — how often tagged names
historically went on to touch +X% (price path only, entry at the next open, no stop).
It is NOT a win rate, NOT risk-adjusted alpha, and NOT a probability of profit on a
bracketed trade.** Read every figure below through that lens. No tag informs sizing
until its forward paper-track shows PASS.

---

## 1. What AIC can expect — the two radars

| Radar | Field | Plain meaning | Answers |
|---|---|---|---|
| **Continuation** | `runner_setup` | Already moving, has another leg: short young base + strong 5-day thrust + clear overhead | "What will keep running?" |
| **Pre-move** | `premove_setup` | Quiet *now* but coiled: very young base + squeeze on + sitting well below the recent high | "What's about to run?" |

These are **descriptive detection layers built from 6 years of daily data** (M14–M18
research program), frozen and validated out-of-sample. They do not replace SC_MOM,
PTRS, Elder, or any engine — they sit alongside them as context, exactly like the
`on_longlist` and `pe` flags AIC already reads.

### The proof (held-out, out-of-sample — the honest numbers)

**`runner_setup`** — the binary rule (`base_days ≤ 15 AND ret_5d > 14.5% AND
resist_score ≤ 8.5`):
- **50.6% of tagged names touched +20% within a month**, vs **~16%** of the untagged
  pond — held-out era, reproduces the study's 52.4%.

**`premove_setup`** — the M18 rule (`base_days ≤ 7.5 AND squeeze_score > 4.5 AND
dist_20dhigh ≤ −16.2%`, applied only to quiet names):
- **49.4% launched +20% within a month, vs 10% of untagged quiet names — ~5×**,
  proven on 2,249 held-out cases, holds in every market regime.
- **Lead time is the point:** the launch came a **median 12 trading days after the
  tag**; only 6.5% popped within 3 days. This *sees the move coming* — it is a
  pre-move radar, not a same-day confirmation.

---

## 2. The SCALE — how to read each tag (no guesswork)

### `runner_conviction` — integer scale 0–4

Counts how many of the four continuation "fingerprint" legs are in their favourable
tercile (each leg is a data-derived cut, frozen from the pond):

| Leg | Condition | Reads as |
|---|---|---|
| 1 | `base_days` in bottom tercile | short base |
| 2 | `ret_5d` in top tercile | strong 5-day thrust |
| 3 | `resist_score` in bottom tercile | clear overhead |
| 4 | `dist_20dhigh` in bottom tercile | room below the 20-day high |

**Delivered as WORD + NUMBER together** — `conviction_label`, e.g. **`HIGH (3/4)`**.
The bare number means nothing on its own to a reader; the word gives it meaning, and
the word is **anchored to the historical detection ladder** (not a judgement call):

```
 conviction_label      legs   historical +20%/20d detection
 MINIMAL (0/4)          0            below base
 LOW (1/4)              1               ~4.5%
 MODERATE (2/4)         2              ~12.6%
 HIGH (3/4)             3              ~27.2%
 MAX (4/4)              4              ~43.4%       (pond base ≈ 16%)
```

Reading: **higher conviction = materially higher historical detection.** A `MAX (4/4)`
runner touched +20% within a month ~43% of the time historically; a `LOW (1/4)` name,
~5%. The label is a *strength-of-signal dial*, not a probability of a winning trade.
The raw integer (`runner_conviction`) is still delivered alongside for sorting/machine
use — but the label is the human read.

### `premove_conviction` — integer scale 0–4

Counts how many of the four M18 launcher-fingerprint legs are present (`base_days`,
`dist_20dhigh`, `bq_base_dur`, `bq_base_days` — all "younger base / more room" tells).
Same reading: higher = stronger historical launch detection. The rule itself (any
premove_setup) detected **49.4% vs 10% base**; conviction refines within that.

### `mover_subtype` — categorical (NOT a scale)

Which behavioural family the runner best matches, by z-score profile:

| Subtype | Character | Note |
|---|---|---|
| `squeeze` | coiled / compression release | **most robust** across the R-based re-tests — the durable winner signature |
| `tight_base` | quiet tight consolidation | steady |
| `trend` | established trend continuation | secondary |
| `explosive` | already igniting hard | strongest on raw %, but the least durable once measured against real risk — treat with most caution |

Use subtype as *context on the kind of move*, not as a ranking. When two runners tie
on conviction, `squeeze` is the historically sturdier profile.

---

## 3. How it's delivered — where AIC reads it

### A. The standalone `signal_radar` block (scan this first, daily)

One concise top-level block in `aqe_daily_export.json` — the full radar over the
entire scored universe, both lists ranked by conviction:

```jsonc
"summary": { "longlist_count": 22, "elder_count": 6,
             "runner_count": 8, "premove_count": 3 },

"signal_radar": {
  "scan_date": "2026-07-06",
  "n_scored": 512,
  "runner_setup": [
    { "ticker": "APP", "conviction": 4, "conviction_label": "MAX (4/4)",
      "subtype": "squeeze", "sc_momentum": 88, "elder": 9, "ret_5d": 21.3,
      "on_longlist": true, "on_elder": true }
  ],
  "premove_setup": [
    { "ticker": "SNDK", "conviction": 3, "conviction_label": "HIGH (3/4)",
      "sc_momentum": 41, "elder": 5, "dist_20dhigh": -18.4,
      "on_longlist": false, "on_elder": false }
  ],
  "note": "DETECTION tags only — not entry signals, not sizing…"
}
```

The `on_longlist` / `on_elder` flags tell AIC at a glance whether a radar name is
already an actionable AQE candidate (full DSL bracket present elsewhere in the export)
or a fresh watch-ahead name that appears **only** here.

### B. Inline tags on every longlist / elder record

The same five fields (`runner_setup`, `runner_conviction`, `mover_subtype`,
`premove_setup`, `premove_conviction`) ride on each longlist and elder-list record, so
when AIC is already looking at a candidate it sees the radar read in context.

### C. Schema-tagged so it can't be misread

Each field carries `role: "signal"` in the export's `field_schema`, and a
`field_glossary` line stating plainly it is a **detection tag, not a gate, not sizing**.
AIC keys off the schema, not the field name.

### Why a pre-move name won't be on the longlist — and that's correct

Pre-move names are *quiet by definition* (flat, low momentum), so they don't pass the
longlist's Elder ≥ 7 / SC_MOM > 64 gates. They live in the `signal_radar` block only.
When one starts to move, it graduates onto the longlist/elder with a full DSL bracket —
the natural hand-off from "watch" to "actionable."

---

## 4. How it's suggested to be used — pre-market flow

1. **Open the `signal_radar` block first.** Two short lists, ranked by conviction.
2. **Runners** (`runner_setup`): the continuation watch. Cross-check `on_longlist` —
   most will already be AQE candidates with brackets. Higher conviction + `squeeze`
   subtype = the sturdiest continuation read. These are potentially *today/near-term*.
3. **Pre-movers** (`premove_setup`): the watch-ahead list. These are quiet coils that
   historically led the move by **~12 trading days** — do **not** expect an immediate
   pop. Put them on the radar, revisit as they tighten; act when they trigger and
   graduate onto the longlist with a bracket.
4. **Read conviction as a dial, not a verdict.** Conviction 4 ≠ "buy"; it means the
   historical detection was highest. Entry, bracket, and size remain 100% AIC's live
   discretion.
5. **Do not size off any tag yet.** The forward paper-track (below) is the gate.

### Early-move safety net — how a pre-move name reaches the live alert

A pre-move name is on "early watch" — but sometimes a coil breaks **earlier** than its
~12-day median. Because pre-movers are quiet (below every list), the live alert engine
would normally never watch them. So the radar names are folded into a dedicated
**`_radar_pool`** the alert engine monitors: each carries its DSL levels, and when one
**breaks out fresh** (or trades through its buy-zone) intraday, it fires a live alert
tagged **`radar-premove` / `radar-runner`** with an **"⚡ running EARLY"** note and its
conviction label — even though it isn't on the longlist yet. (Radar names fire only on
the two *upside* events — buy-zone / breakout — not the approaching-stop event, since
there's no position to protect.) This closes the gap between "on early watch" and
"it moved before we expected."

### What it is NOT

- **Not a gate** — it never filters the longlist or blocks a name.
- **Not sizing** — it never sets or suggests position size.
- **Not a bracket** — DSL / stops / targets are unchanged and unrelated to this.
- **Not a win rate** — detection ≠ profit; a detected move can still be un-tradeable
  or reverse.

---

## 5. The paper-track — the gate to ever trusting these for sizing

Every scan logs its tags to an append-only store; every matured tag is scored against
what price actually did, versus **pass/fail bands written down before the track
started** (pre-registration — no moving the goalposts):

- **`runner_setup` PASS:** forward +20%/20d detection **≥ 35%** AND **≥ 1.5×** the
  concurrent pond base, after **≥ 60 matured tags AND ≥ 92 days**. FAIL if < 25%.
- **`premove_setup`:** bands set from the M18 study (pass floor ~15%, 1.5× base,
  fail < 10%).

Until a tag's track reads **PASS**, it is context only. AIC will see the live
scoreboard (logged / matured / forward detection / verdict) on the Scanner and can
call for it any time. **No tag informs a sizing decision until it passes its own
forward test.**

---

## 6. Data lineage — confirmed, not assumed

The radar consumes only what the nightly pipeline already produces — **zero new
external calls, zero new secrets:**

```
FMP pull (FMP_API_KEY, existing)
   → panel_daily.parquet          (OHLCV — build_panel)
   → scores_daily.parquet         (10 engines: flow/energy/structure/mp/elder/
                                    bq/k39/pipeline_rank/readiness/scoring)
   → Signal Radar                 (16 trajectory features computed from the panel;
                                    18 scoring inputs read from scores_daily — all
                                    present & verified; NO new FMP calls)
   → export signal_radar block + inline tags + paper-track log
```

- All **18 scoring inputs** the radar needs are confirmed present in `scores_daily`.
- The **16 trajectory features** (3–5 day momentum, volume, compression) are computed
  live from the OHLCV panel — reproduce the study matrix to < 1e-6.
- The step is **resilient**: if the radar throws, the pipeline logs a warning and
  exports everything else normally, tags defaulting to `false`/`0`/`null`. It can
  never take down the nightly scan.

---

## 7. The honest caveats (carried on every number)

- All history is **2020–2026** (mostly a rising market) with today's universe applied
  backward — so every detection rate is an **upper bound / best case** until the
  forward tracker confirms it live. That is exactly what the tracker is for.
- The universe is survivorship-tainted; the window is single-regime and in-sample.
- Detection rate is a **price-path** measure (max favourable move from the next open,
  no stop). Whether a detected move is tradeable at acceptable risk is a separate
  bracketing question, handled by AQE's DSL layer — not claimed here.

---

## 8. What AIC feedback would help most

Settled by the PM (not open for debate): conviction is delivered as **word + number
together** (`conviction_label`, e.g. `HIGH (3/4)`) — the word is anchored to the
detection ladder so it carries meaning, the number is kept alongside for machine use.
The radar lands **only** in the daily export/scan protocol AIC already runs (no email
or side channel). Feedback wanted on the read itself:

1. Is the `signal_radar` block the right shape / right fields to scan daily?
2. Any additional context field per name that would sharpen the pre-market read
   without adding noise?
3. For runners that overlap the longlist, is the `on_longlist` / `on_elder` flag enough
   to bridge "detected" → "actionable with a bracket", or is more linkage useful?

*Reference trail (full derivation): `docs/signal_radar/` — M16/M17/M18 synthesis,
BUILD_REPORT, integration brief. The BQ calibration evidence in that folder is a
SEPARATE committee item (a proposed SC_POSITION re-weight) — not part of this radar.*
