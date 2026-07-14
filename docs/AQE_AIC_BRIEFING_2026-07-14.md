# AQE → AIC Briefing — Enriched Feed (2026-07-14)

**Audience:** the AI Investment Committee (AIC). **Purpose:** a complete reference
of what changed tonight, every field now on the feed, the exact formula behind
each, and the weighting between subcomponents — so the committee can assess its
own protocols/charter against what AQE now actually measures, and deliberate any
changes to how it reads the feed.

**Status:** code-complete, on `main`, full suite green (223/223). New fields
populate from the **next full pipeline run** (they read `scores_daily.parquet`,
which is rebuilt every run) — until then they carry documented nulls.

---

## Part 1 — What changed tonight (plain summary)

Seven builds, in three categories:

| # | What | Category |
|---|---|---|
| 1 | `subcomponents` block — 46 sub-scores across 6 engines | **Surfaced** (existing data, made visible) |
| 4 | Volume-validated pivots (`vol_ratio`/`vol_validated`) on bracket levels | **Enriched** (existing engine, new dimension) |
| 5 | `structure_shift` (BOS/CHoCH direction flag) | **Enriched** (new field, existing swing data) |
| 3 | `mp_accel` — momentum's own rate of change | **Enriched** (existing engine, new derivative) |
| 2 | Divergence engine (price vs. 5 oscillators) | **New engine** |
| 6 | Pin bar / inside bar pattern detector | **New engine** |
| 7 | Smart-Money kNN (CHoCH + instance-based learning) | **New engine** |

**Trigger:** these were built after cross-referencing 22 open-source TradingView
community strategies against AQE's engine suite (full mapping in
`docs/AQE_TV_STRATEGY_ANALYSIS.md`). ~15 of the 22 turned out to already be
inside AQE's nightly computation, just never exported — that's build #1. Two
gaps had no AQE analog at all and needed real new engines — builds #6 and #7.
The rest (#2, #3, #4, #5) are small, targeted enrichments.

**Nothing here changes a gate, a screen, sizing, or list membership.** Every
field below is **context for the AIC's deliberation** — AQE still makes no
decisions.

---

## Part 2 — The composite formulas (unchanged tonight, restated for reference)

### SC_MOMENTUM (breakout pipeline, uncapped)
```
SC_MOMENTUM = Flow×0.30 + Energy×0.30 + Structure×0.20 + MP×0.20
```
Qualification gate (`sc_m_gates`, does NOT cap the score): Elder≥6.5 AND Flow≥60
AND Energy≥60 AND Structure≥55 AND MP≥55. Per-engine breakdown in
`sc_m_gate_detail` (shipped last session).

### SC_POSITION (base-building pipeline, uncapped)
```
SC_POSITION = Flow×0.10 + Energy×0.30 + Structure×0.20 + MP×0.05 + BQ×0.35
```
Qualification gate (`sc_p_gates`): Flow≥40 AND Energy≥60 AND Structure≥65 AND
MP≥40 AND BQ≥60 AND K39. Per-engine breakdown in `sc_p_gate_detail`.

### PTRS — a feed-accuracy bug found and fixed while writing this briefing
```
PTRS = SC_MOMENTUM        (verbatim — the Sector-Health adjustment is DROPPED)
```
Rationale (PM ruling, this session): sector health is now a committee-level
read via `srm` + RRG (qualitative), not a per-ticker score penalty — avoids
double-counting the sector context. **This is what the export has actually
computed since that ruling** (`compute_ptrs(sc_momentum, 0.0)` — SH hardcoded
to zero).

**What was wrong:** the AIC-facing `field_glossary` entry for `ptrs` still
described the OLD formula ("Engine score + sector health") — the glossary text
itself, not just an internal module docstring, was stale versus what the field
actually contains. **Fixed in this session** (glossary now states the correct
formula + rationale). `src/analyzer/ptrs.py`'s own module docstring and
`compute_ptrs_batch()` still describe/implement the legacy `+SH` formula and are
used elsewhere (e.g. Math Lab backtesting) — that's a separate, lower-stakes
inconsistency (not AIC-facing) the committee may still want ruled on for
internal consistency, but the feed itself is now correct.

### Longlist membership (unrelated to PTRS)
```
on_longlist = (raw SC_MOMENTUM ≥ 65) AND (PTRS ≥ 60) AND (Elder ≥ 7)
```
Single source of truth (`src/longlist_screen.py`) — same thresholds the alert
engine fires on and the Scanner sliders default to.

---

## Part 3 — The 6 scoring engines: internal weighting (the "subcomponents")

This is the part that was previously invisible to the AIC. Every number below
is now on the feed under each record's `subcomponents` block.

### Flow (max 38 raw → scaled ×100/38)
```
flow_raw = flow_score + accum_score + volume_score + skew_score + ext_score
flow_100 = clip(flow_raw / 38 × 100, 0, 100)
```
| Sub-score | Max pts | What it measures |
|---|---|---|
| `flow_score` | 17 | MFI + CMF + Heikin-Ashi candle quality (accumulation core) |
| `accum_score` | 7.5 | A/D line rolling-sum linear regression, short vs long |
| `volume_score` | 7.5 | Volume trend + spike |
| `skew_score` | 3.5 | Up/down volume ratio over 10 bars |
| `ext_score` | −8 to +5 | Extension penalty (how far price has run) |

### Energy (max 59.5 raw → scaled ×100/59.5)
```
energy_raw = vp_position_score + price_action_score + squeeze_score + exhaustion_score + atr_score
energy_100 = clip(energy_raw / 59.5 × 100, 0, 100)
```
| Sub-score | What it measures |
|---|---|
| `vp_position_score` | Volume-profile range-position proxy (where price sits in its recent range) |
| `price_action_score` | Candle/price-action quality |
| `squeeze_score` | **The TTM/Bollinger-Keltner squeeze read** — BB inside KC = compression |
| `exhaustion_score` | Overextension/exhaustion read |
| `atr_score` | ATR-based volatility contribution |

### Structure (max 95 raw → scaled ×100/95)
```
structure_raw = rs_spy_score + rs_accel_score + base_score + ms_pos_score + resist_score + wk_score + earn_score
structure_100 = clip(structure_raw / 95 × 100, 0, 100)
```
| Sub-score | What it measures |
|---|---|
| `rs_spy_score` | Relative strength vs SPY |
| `rs_accel_score` | RS acceleration (is outperformance speeding up?) |
| `base_score` | Base/consolidation quality |
| `ms_pos_score` | Market-structure position (higher-highs/higher-lows read) |
| `resist_score` | Overhead resistance proximity |
| `wk_score` | **Weekly trend — the HTF (higher-timeframe) bias** |
| `earn_score` | Earnings-date proximity (≤5d→0, ≤10d→4, ≤20d→7, >20d/unknown→10) |

### MP — Momentum Persistence (0–100 direct, no rescale)
```
mp_score = clip(abs_mom_score + adx_score + rel_mom_score + trend_score, 0, 100)
```
| Sub-score | Max pts | What it measures |
|---|---|---|
| `abs_mom_score` | 30 | Absolute momentum (20d ROC z-scored vs its own 50d history) |
| `mp_adx_score` (`adx_score`) | 25 | Wilder ADX trend strength, DI+/DI− bullish-gated |
| `rel_mom_score` | 25 | Relative momentum — excess return vs SPY over 20d |
| `trend_score` | 20 | MA-stack alignment (price/EMA20/SMA50, rising or not) |

**State** (`mp_state`): `BUILDING` (rising, score<75) / `STRONG` (rising, ≥75) /
`FADING` (not rising) — a 3-bar delta on `mp_score`. **This is the field that
flickers on a plateau** — see `mp_accel` in Part 4, built specifically to give
the AIC a second, more stable read alongside it.

### BQ — Base Quality (0–100 direct, feeds SC_POSITION only)
```
bq_100 = bq_range_tight + bq_vol_dry + bq_base_dur + bq_ema_conv
```
| Sub-score | Max pts | What it measures |
|---|---|---|
| `bq_range_tight` | 30 | ATR(5)/ATR(20) ratio — is the range tightening? |
| `bq_vol_dry` | 25 | SMA(vol,5)/SMA(vol,20) — is volume drying up (classic base behavior)? |
| `bq_base_dur` | 20 | Base duration (3-mode, with a decay latch) |
| `bq_ema_conv` | 25 | EMA spread normalised by ATR(20) — is price coiling? |

### Pipeline Rank (Stage-1 universe screen, not part of SC_MOMENTUM/POSITION)
```
pipe_rank = momentum_composite × 0.70 + fip_quality × 0.30
```
`momentum_composite` (5 sub-parts, 0-100): 12-month return (skip 1mo), ADX trend
strength, RSI momentum zone, volume confirmation, MA structure — sub-scores
`pr_ret_12m`, `pr_adx_score`, `pr_rsi_score`, `pr_vol_score`, `pr_ma_score`.
`fip_quality` = Fraction-of-Informed-Pricing (step-scored) with the DSG-20 prior-
spike exclusion. Filter: `pipe_rank ≥ 60` advances to full scoring.

### Elder Impulse (0–10)
```
elder_score = state_score{0,2,4} + slope_score{0,1,2,3} + hist_score{0,1,2,3}
```
Impulse colour (green/blue/red) + 3-bar EMA(13) slope + MACD(12,26,9) histogram
trend. Elder ≥ 7 required for longlist; Elder ≥ 8 = the standalone elder_list
(the "event-driven super-runner" catcher).

### K39 (weekly gate, feeds SC_POSITION's `sc_p_gates` only)
```
k39_gate = (stochastic(weekly_close/high/low, 39) > 50) AND (weekly_OBV > SMA(weekly_OBV, 30))
```

---

## Part 4 — The new/enriched fields (formulas, exact)

### `subcomponents` (Build #1 — surfaced, no new compute)
Nested object per record: `{flow: {...}, energy: {...}, structure: {...}, mp:
{...}, bq: {...}, pipe: {...}}` — the exact sub-scores tabulated in Part 3,
pulled straight from `scores_daily.parquet`. **Readiness sub-scores are
intentionally excluded** (standing ruling: Readiness overlapped Signal Radar's
DETECT layer and is hidden from the feed). **Health sub-scores stay
held-only/dropped** (standing ruling).

### `structure_shift` / `structure_shift_ref` (Build #5)
```
if entry > confirmed_swing_high:  BULLISH_BOS  (ref = the broken swing high)
elif entry < confirmed_swing_low: BEARISH_CHOCH (ref = the broken anchor low)
else:                              RANGE
```
Computed from the SAME confirmed swing pivots the bracket engine already uses
(non-repainting). "BOS" = break of structure (continuation); "CHoCH" = change
of character (the up-structure failed).

### `vol_ratio` / `vol_validated` on bracket levels (Build #4)
For every DATED level in `bracket.targets[]` and the operative stop
(`bracket.stop_date` → `bracket.stop_vol_ratio`/`stop_vol_validated`):
```
vol_ratio = volume_on_pivot_bar / SMA(volume, 20)_as_of_that_date
vol_validated = vol_ratio >= 1.2
```
A level defended on ≥1.2× average volume reads as a stronger level (the
BigBeluga "High Volume Pivot" rule). **The 3 bracket gates (ATR≥1.0, RR≥2.0,
regime ceiling) are unchanged** — this is an additional read, not a new gate.

### `mp_accel` / `mp_accel_state` (Build #3)
```
mp_accel = SMA(diff(roc_zscore, 5), 3)          # 2nd derivative of MP momentum
mp_accel_state = "ACCELERATING" if mp_accel > 0.10
                 "DECELERATING" if mp_accel < -0.10
                 else "FLAT"
```
`roc_zscore` is MP's existing momentum-level input. This is its **rate of
change** — flags whether momentum is inflecting BEFORE `mp_state`'s 3-bar delta
flips. Directly answers the "mp_state flickered on a plateau" problem the
committee raised on WFC: read `mp_accel_state` alongside `mp_state`, not
instead of it.

### Divergence — `div_state`, `div_bull_count`, `div_bear_count`, `div_oscs`, `div_date` (Build #2)
Regular price-vs-oscillator divergence, tested independently on **5 oscillators**
AQE already computes: RSI(14), MFI(14), CMF(20), MACD line (EMA12−EMA26), OBV.
```
Confirmed pivot = strict extreme of a [i-5, i+5] window (needs 5 bars printed
                  after it — non-repainting)
BULLISH (per oscillator): price makes a LOWER pivot low AND the oscillator
                          makes a HIGHER low at the same two pivots
BEARISH: mirror on pivot highs
```
Freshness gate: only counts if the newer pivot is within ~10 bars of today.
`div_state` = BULLISH (bull_count>0, bear_count=0) / BEARISH (mirror) / MIXED
(both) / NONE. `div_oscs` lists which oscillators fired (e.g. `"rsi,mfi,-obv"`
— bearish names prefixed `-`).

### Pin bar / inside bar — `pin_bar_state`, `pin_bar_date`, `pin_bar_level`, `inside_bar`, `pib_pattern` (Build #6)
Pure candlestick geometry on the LAST closed bar:
```
range = high - low
lower_wick = min(open,close) - low ;  upper_wick = high - max(open,close)
body = |close - open|

BULLISH_PIN: lower_wick >= 0.66×range AND body <= 0.40×range AND upper_wick <= 0.40×range
BEARISH_PIN: mirror (long upper wick)
```
Filtered: the pin bar's range must be **≥2× the immediately prior bar's range**
(rejects "pin bars" that are just noise inside an already-tiny range).
`inside_bar` = last bar's high/low fully inside the prior bar's high/low.
`pib_pattern` = the bar BEFORE last was a pin bar AND the last bar is an inside
bar relative to it (the named "P.I.B." combo — rejection, then a pause).
`pin_bar_level` = the pin bar's rejection extreme (low for bullish = candidate
support; high for bearish = candidate resistance).

### Smart-Money kNN — `choch_state`, `choch_date`, `knn_prob`, `knn_significant`, `knn_neighbors_used`, `knn_tp1/2/3` (Build #7)
**Step 1 — CHoCH detection** (change of character, non-repainting, confirmed
5-bar pivots): a BULLISH CHoCH fires when close breaks above the last confirmed
swing high while trend was flat/down; BEARISH mirrors on the swing low.

**Step 2 — feature vector per CHoCH event** (3 features):
```
vol_delta    = mean(volume × (2×buy_frac − 1)) / mean(volume)     over the interval
               where buy_frac = (close−low)/(high−low) per bar
displacement = |close_now − close_at_prior_event| / ATR(14)
velocity     = displacement / bars_elapsed
```

**Step 3 — self-labeling**: an event is "resolved" once 20 bars have printed
after it. `outcome = 1` if the move's max-favorable-excursion beat its
max-adverse-excursion in the CHoCH's direction, else `0`.

**Step 4 — the kNN query**: the LATEST CHoCH event is compared (Euclidean
distance, 3-feature space) against every past, RESOLVED, SAME-DIRECTION CHoCH
event on the **same ticker's own history** (window: 500 bars). Takes the **5
nearest** (or fewer if history is thin).
```
knn_prob = mean(outcome) over the 5 nearest historical analogs
knn_significant = knn_prob >= 0.60  OR  knn_prob <= 0.40
tp1 = current_close ± mean(neighbors' favorable_run) × 0.5   (signed by direction)
tp2 = current_close ± median(neighbors' favorable_run)
tp3 = current_close ± p75(neighbors' favorable_run)
```

**Read this honestly:** `knn_prob` is a real k-nearest-neighbors classifier —
not a black box, not deep learning, no external model file, provably
deterministic (same bars always produce the same output). But it is a **simple**
model: 3 hand-picked features, learning only from the ticker's OWN past CHoCH
events (often a small sample). Treat `knn_prob`/`knn_tp1-3` as one more context
signal for deliberation, explicitly **not** a probability of profit, and never
a substitute for `bracket` (the structural stop/target engine) — `knn_tp1-3`
are statistical projections from historical analogs, `bracket.targets` are
real structural levels.

---

## Part 5 — What stays hidden, and why (for the AIC's own charter review)

| Hidden field | Why | Standing ruling |
|---|---|---|
| Readiness (`rd_*`) | Overlapped Signal Radar's DETECT layer; state was ambiguous | This session (prior) |
| Health sub-scores (`hl_trend/flow/rs/risk/...`) | Composite+state (`hl_score`/`hl_state`) is enough; held-positions only | This session (prior) |
| `setup_state`, `breakout_*` | Competing DETECT signal vs Signal Radar | This session (prior) |
| `on_longlist` (old meaning) | Was a stale recipe-match set, not real membership — retired, field renamed to mean actual longlist membership | This session (prior) |

**The standing decision framework** (unchanged, now with one more layer):
```
DETECT  → Signal Radar (runner_setup/premove_setup) + Divergence + Pin Bar/CHoCH (NEW)
ENTER   → bracket (stop/targets) + the live alert engine
HOLD    → Health (hl_score/hl_state, held_positions only)
```
The AIC's job at this briefing: decide whether the **new DETECT-layer signals**
(divergence, pin bar/P.I.B., CHoCH+kNN) should be read as peers to Signal Radar,
subordinate context to it, or whether any should be suppressed the same way
Readiness/setup_state were — that overlap question is exactly what surfaced
Readiness as noise last time, and these three are new candidates for the same
scrutiny.

---

## Part 6 — Questions for AIC deliberation

1. **PTRS** (Part 2): the AIC-facing glossary bug is fixed. Remaining, lower-
   stakes: should `src/analyzer/ptrs.py`'s legacy `+SH` formula (still used by
   Math Lab backtesting) be updated to match production, or is a divergence
   between live-feed PTRS and backtest PTRS intentional?
2. **New DETECT-layer signals**: do divergence / pin-bar / CHoCH+kNN get treated
   like Signal Radar (a first-class detect layer) or as secondary context?
3. **`knn_prob` interpretation**: agree on how the committee should weight a
   kNN read built on a small, ticker-own-history sample — a strong prior, a
   tie-breaker, or informational only until it earns a forward track record
   (the way Signal Radar's detection-rate stats accrued over time)?
4. **`mp_accel` vs `mp_state`**: should `mp_accel_state` become the primary
   momentum-direction read (since it's less prone to the plateau-flicker
   problem), with `mp_state` demoted to secondary?
5. **Subcomponent depth**: now that ~46 subcomponents are visible, does the
   committee want ALL of them in its working read, or should AQE pre-filter to
   a smaller "high-signal" subset to avoid analysis paralysis?

---

*Source: `docs/AQE_TV_STRATEGY_ANALYSIS.md` (the originating strategy-mapping
analysis). Engines: `src/engines/{flow,energy,structure,mp,bq,pipeline_rank,
elder,k39,divergence,pin_bar,smart_money_knn}.py`. Export assembly:
`src/data/drive_sync.py` (`_subcomponents`, `_new_engine_fields`,
`field_glossary`, `field_schema`).*
