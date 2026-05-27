# AEGIS QUANT ENGINE (AQE) — CONSOLIDATED BUILD BRIEF
## For Claude Code Implementation | v1.0 | 18 May 2026

**This is the single authoritative build document.** It consolidates 5 prior specifications into one actionable brief. Claude Code implements from THIS document. Prior specs are reference material for formula details.

**Reference documents (read for detail, not for instruction):**
1. `Aegis_Design_Committee_Specification.md` — Every indicator formula
2. `AQE_Engineering_Specification.md` — Architecture and data pipeline
3. `AQE_Backtest_Calibration_Specification.md` — Confidence layer design
4. `AQE_Red_Team_Review.md` — 15 findings, all incorporated below
5. `AQE_Advisory_Voice_Briefs.md` — Technique sources (López de Prado, Pardo, Chan)

---

# WHAT WE'RE BUILDING

A Python application that:
1. Pulls daily OHLCV from FMP for ~1000 US equities
2. Computes 5 proprietary scoring engines locally (replacing TradingView)
3. Produces a ranked shortlist of 10-15 candidates daily
4. Overlays sector rotation and macro regime context
5. Feeds structured output to Claude (Alfred) for committee deliberation
6. Accumulates an outcome database that becomes a backtesting confidence layer
7. Runs walk-forward calibration to improve parameters over time

**Single user. Single operator. ~$70K capital base. IBKR execution.**

---

# TECH STACK

```
Python 3.11+
numpy, pandas          — computation
scipy                  — optimisation, statistics
SQLite                 — state store (single file, zero config)
FMP MCP                — market data (Starter plan, ~250 calls/day)
Google Drive API       — output sync
```

No web framework. No UI. No server. CLI application that runs daily via cron or manual trigger. Output is JSON + text dashboard pushed to Drive. Claude (Alfred) consumes the output.

---

# PROJECT STRUCTURE

```
aqe/
├── main.py                     # CLI entry point + daily orchestrator
├── config.py                   # All thresholds, weights, constants
├── data/
│   ├── fmp.py                  # FMP MCP client wrapper
│   ├── universe.py             # Universe generation + refresh
│   ├── bars.py                 # OHLCV pull, incremental append, weekly aggregation
│   ├── earnings.py             # Earnings calendar from FMP
│   └── db.py                   # SQLite abstraction layer
├── engines/
│   ├── ta.py                   # Common TA functions (ema, sma, atr, rsi, macd, dmi, etc.)
│   ├── flow.py                 # Flow v1.3 (5 components, raw max 38)
│   ├── energy.py               # Energy v1.3.1 (5 components, raw max 59.5)
│   ├── structure.py            # Structure v1.5.0 (7 components + 3-mode BD, raw max 95)
│   ├── mp.py                   # Momentum Persistence v1.2 (4 components, 0-100)
│   ├── elder.py                # Elder Impulse Score v1 (3 components, 0-10)
│   ├── bq.py                   # Base Quality (4 sub-components, 0-100) + K39 gate
│   ├── pipeline_rank.py        # Stage 1 screener: momentum(70%) + FIP(30%)
│   ├── dsl.py                  # Dynamic Stop Loss v1.4 (initial stop + DSG-10 trail)
│   └── scorer.py               # Composites (SC_M, SC_P), gates, diagnostics
├── context/
│   ├── srm.py                  # Sector Rotation Monitor v3.0
│   ├── regime.py               # VIX regime + Hurst exponent
│   └── ptrs.py                 # PTRS = Engine Score + CM(SH+RA+RL)
├── backtest/
│   ├── engine.py               # Event-loop backtester
│   ├── labels.py               # Triple barrier + trail-based outcome labelling
│   ├── costs.py                # Transaction cost model (slippage + commission)
│   ├── portfolio.py            # Position sizing (charter disposition + quarter-Kelly ceiling)
│   ├── confidence.py           # Backtest Confidence layer (profile matching → BC score)
│   └── analytics.py            # Performance metrics + Monte Carlo
├── calibration/
│   ├── walkforward.py          # Walk-forward analysis (rolling + anchored)
│   ├── grid_search.py          # Coarse grid optimisation (NOT continuous)
│   ├── stability.py            # Parameter stability analysis (Pardo CV metric)
│   ├── validation.py           # DSR, PBO, WFER, purged CV
│   └── report.py               # Calibration report generator
├── output/
│   ├── shortlist.py            # Daily shortlist JSON
│   ├── dashboard.py            # Text dashboard
│   └── drive.py                # Google Drive sync
└── tests/
    ├── test_ta.py              # TA function unit tests
    ├── test_engines.py         # Engine output tests (vs TV reference values)
    ├── test_scorer.py          # Composite + gate tests
    ├── test_backtest.py        # Backtest engine tests
    └── fixtures/               # Reference OHLCV CSVs for validation
```

---

# CONFIG.PY — ALL CONSTANTS IN ONE PLACE

```python
"""
AQE Configuration — Single source of truth for all parameters.
Charter authority: AIC v1.8.
Every value here is a calibration candidate (see calibration/ modules).
"""

# ── UNIVERSE FILTERS ──────────────────────────────────
UNIVERSE_MIN_MCAP = 1_000_000_000    # $1B
UNIVERSE_MIN_PRICE = 5.00
UNIVERSE_MIN_VOLUME = 500_000
UNIVERSE_EXCHANGES = ["NASDAQ", "NYSE"]
UNIVERSE_REFRESH_DAY = "Sunday"

# ── ENGINE WEIGHTS (SC_MOMENTUM) ──────────────────────
SC_M_WEIGHTS = {
    "flow": 0.30,
    "energy": 0.30,
    "structure": 0.20,
    "mp": 0.20,
}

# ── ENGINE WEIGHTS (SC_POSITION) ──────────────────────
SC_P_WEIGHTS = {
    "flow": 0.10,
    "energy": 0.30,
    "structure": 0.20,
    "mp": 0.05,
    "bq": 0.35,
}

# ── MOMENTUM GATES ────────────────────────────────────
GATES_MOMENTUM = {
    "elder": 6.5,
    "flow": 60.0,
    "energy": 60.0,
    "structure": 55.0,
    "mp": 55.0,
}

# ── POSITION GATES ────────────────────────────────────
GATES_POSITION = {
    "flow": 40.0,
    "energy": 60.0,
    "structure": 65.0,
    "mp": 40.0,
    "bq": 60.0,
    "k39": True,  # K39 > 50 AND OBV confirmed
}

# ── COMPOSITE THRESHOLDS ──────────────────────────────
SC_STRONG = 65.0
SC_QUALIFIED = 55.0
GATE_CAP = 49.0  # Score capped here when any gate fails

# ── PTRS CONTEXT MODIFIER ─────────────────────────────
# SH (Sector Health)
SH_STRONG = 3      # sector ETF >2% above SMA20
SH_ABOVE = 0
SH_BELOW = -5
SH_WEAK = -8       # sector ETF >5% below SMA20

# RA (Regime Alignment)
RA_ALIGNED = 5
RA_NEUTRAL = 0
RA_MISALIGNED = -10

# RL (Regime Level — VIX based)
RL_GREEN = 2        # VIX < 18
RL_YELLOW = -3      # VIX 18-25
RL_ORANGE = -5      # VIX 25-30
# VIX > 30 = RED = HARD STOP, no entries

# ── DISPOSITION BANDS ─────────────────────────────────
DISPOSITION = [
    (60, "FULL", 1.0),
    (50, "HALF", 0.5),
    (45, "QUARTER", 0.25),
    (0, "REJECT", 0.0),
]

# ── VIX REGIME THRESHOLDS ─────────────────────────────
VIX_GREEN = 18.0
VIX_YELLOW = 25.0
VIX_ORANGE = 30.0

# ── DSL v1.4 (Dynamic Stop Loss) ─────────────────────
DSL_TACTICAL = {
    "struct_lookback": 5,
    "struct_buffer_atr": 0.5,
    "max_stop_mult": 2.0,
    "min_stop_mult": 0.75,
}
DSL_CORE = {
    "struct_lookback": 5,
    "struct_buffer_atr": 0.75,  # 0.5 × 1.5
    "max_stop_mult": 3.0,
    "min_stop_mult": 1.0,
}

# ── DSG-10 TRAIL TIERS ────────────────────────────────
TRAIL_TIERS = {
    1: {"r_threshold": 0.0, "atr_mult": 1.0, "anchor": "session_low", "timeframe": "daily"},
    2: {"r_threshold": 1.0, "atr_mult": 1.5, "anchor": "session_low", "timeframe": "daily"},
    3: {"r_threshold": 2.0, "atr_mult": 2.0, "anchor": "weekly_low",  "timeframe": "weekly"},
    4: {"r_threshold": 4.0, "atr_mult": 2.5, "anchor": "weekly_low",  "timeframe": "weekly"},
}

# ── R-FLOORS (minimum trail by tier) ─────────────────
R_FLOORS = {2: 0.0, 3: 1.5, 4: 3.0}  # entry + N × risk_per_share

# ── PIPELINE RANK THRESHOLDS ──────────────────────────
PIPE_RANK_CUTOFF = 60       # minimum for Stage 2
PIPE_RANK_A_TIER = 75
STAGE2_MAX_CANDIDATES = 50  # max tickers for full scoring

# ── BACKTEST PARAMETERS ───────────────────────────────
# Transaction costs (Chan EC-2)
SLIPPAGE_PCT = 0.0010           # 10bps per side
COMMISSION_PER_SHARE = 0.005    # IBKR tiered

# Survivorship bias haircut (Chan EC-1)
SURVIVORSHIP_HAIRCUT_ANNUAL = 0.02  # 2% applied to backtest returns

# Triple barrier (López de Prado MLP-4)
BARRIER_UPPER_R = 3.0           # take profit at +3R
BARRIER_LOWER_R = 1.0           # stop at -1R
BARRIER_MAX_BARS = 25           # max holding period (vertical barrier)

# Position sizing
RISK_PER_TRADE_PCT = 0.01      # 1% of capital per full position
KELLY_FRACTION = 0.25           # quarter Kelly (Chan EC-3)
MAX_POSITIONS = 6
MAX_SECTOR_EXPOSURE = 0.35      # DSG-09

# ── CALIBRATION PARAMETERS ────────────────────────────
# Walk-forward (Pardo)
WF_TRAIN_MONTHS = 12
WF_TEST_MONTHS = 3
WF_STEP_MONTHS = 1
WFER_MINIMUM = 0.30            # reject if below (Pardo RP-1)

# Grid search (Pardo RP-2)
WEIGHT_GRID = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
GATE_GRID = [40, 45, 50, 55, 60, 65, 70]

# Sample minimums (Pardo RP-3)
MIN_IS_TRADES = 50              # in-sample minimum
MIN_OOS_TRADES = 30             # out-of-sample minimum
MIN_BC_SAMPLES = 20             # confidence layer minimum per tier

# Stability (Pardo)
PARAM_STABILITY_CV_MAX = 0.30  # CV > this = UNSTABLE, keep current

# Overfitting detection (López de Prado MLP-1, MLP-2)
DSR_MINIMUM = 1.0              # reject improvements below this
PBO_MAXIMUM = 0.40             # confidence layer overfitting threshold
CSCV_PARTITIONS = 16           # for PBO computation

# Embargo (López de Prado MLP-3)
EMBARGO_PCT = 0.01             # 1% of dataset as post-test buffer
PURGE_WINDOW_BARS = 40         # forward outcome window to purge

# Monte Carlo (Pardo RP-5)
MONTE_CARLO_ITERATIONS = 2000
```

---

# BUILD ORDER (PHASED)

## PHASE 1: DATA FOUNDATION (Build first)

**Goal:** Can pull data, store it, retrieve it. TA functions verified.

### 1a. `data/db.py` — SQLite abstraction

Tables: `universe`, `daily_bars`, `weekly_bars`, `engine_state`, `scores`, `earnings`, `srm_scores`. Schema exactly as in AQE Engineering Spec Section 3. Include indexes.

### 1b. `data/fmp.py` — FMP MCP wrapper

Wraps FMP tool calls. Handles rate limiting (sleep between calls). Key methods:
- `pull_universe()` → `FMP:search → search-company-screener`
- `pull_bars(ticker, from_date, to_date)` → `FMP:chart → historical-price-eod-full`
- `pull_bars_light(ticker, from_date, to_date)` → `FMP:chart → historical-price-eod-light`
- `pull_earnings(ticker)` → `FMP:calendar → earnings-company`
- `pull_quote(ticker)` → `FMP:quote → quote`
- `pull_batch_quotes(tickers)` → `FMP:quote → batch-quote`
- `pull_vix()` → `FMP:quote → quote` for ^VIX

### 1c. `data/bars.py` — Bar management

- `seed_bars(ticker, lookback=252)` — initial full history load
- `incremental_pull(ticker, last_date)` — pull only new bars, append to DB
- `aggregate_weekly(daily_bars)` — compute weekly OHLCV from daily (Mon-Fri grouping)

### 1d. `engines/ta.py` — Common TA library

Implement ALL functions from AQE Engineering Spec Section 4.2:
`sma`, `ema`, `atr` (Wilder), `rsi` (Wilder), `macd`, `dmi` (→ DI+, DI-, ADX), `stochastic`, `linreg_slope`, `highest`, `lowest`, `rate_of_change`, `obv`, `mfi`, `wilder_smooth`, `stdev`, `true_range`

All functions: numpy arrays in, numpy arrays out. Handle NaN edges.

### 1e. `tests/test_ta.py` — Unit tests

Test every TA function against known values. Use a small reference OHLCV dataset (10-20 bars) where expected outputs can be manually computed.

**Phase 1 exit criteria:** `pytest tests/test_ta.py` passes. Can pull SPY bars from FMP, store in SQLite, retrieve, compute EMA/ATR/RSI and verify against TradingView values.

---

## PHASE 2: SCORING ENGINES (Build second)

**Goal:** All 5 engines + BQ + Pipeline Rank produce scores matching TV within tolerance.

### 2a. Engine modules

Build each engine as an independent module following the Design Committee Spec Part 2. Each returns a typed dataclass. Implementation order:

1. `engines/elder.py` — simplest (3 components, no state). Build and test first.
2. `engines/mp.py` — 4 components, no persistent state. State machine for BUILDING/STRONG/FADING.
3. `engines/flow.py` — 5 components. MFI+CMF fusion, HA quality, A/D line, volume trend, extension.
4. `engines/energy.py` — 5 components. VP proxy (NOT real VP array), squeeze detection, exhaustion with trend-duration gate (PERSISTENT STATE: `trend_bars`).
5. `engines/structure.py` — 7 components. 3-mode BD system (PERSISTENT STATE: `raw_base_count`, `latched_bd`, `bars_since_bo`). Most complex — DSG-02 latch + decay.
6. `engines/bq.py` — 4 sub-components + K39 gate (REQUIRES WEEKLY BARS). Persistent state for BQ base days.
7. `engines/pipeline_rank.py` — Momentum composite (70%) + FIP (30%). Uses close+volume ONLY. No benchmark needed. Screener-compatible.

### 2b. `engines/scorer.py` — Composites and gates

Consumes all engine outputs. Computes:
- `SC_MOMENTUM` = weighted sum, gated by Elder + engine floors. Capped at 49.0 if any gate fails.
- `SC_POSITION` = weighted sum with BQ, gated by K39 + engine floors. Capped at 49.0 if any gate fails.
- `dual_qual` = both ≥ 55
- DSG-07 overextension flag
- All diagnostic exports (BD count, BD mode, ATR comp, NR7/NR4, etc.)

### 2c. `engines/dsl.py` — Dynamic Stop Loss

Compute initial stop (tactical + core profiles). DSG-10 trail tiers for backtest engine (persistent state: `trailing_stop`, `highest_tier`, `weekly_mode`, `frozen_risk`).

### 2d. Validation

Select 10 reference tickers spanning score ranges. Pull their TV dashboard values. Run through AQE. Tolerance: ±2 per engine, ±3 on composite. Document any deltas and their causes.

**Phase 2 exit criteria:** 10-ticker cross-validation passes. All engines produce scores within tolerance of TV.

---

## PHASE 3: DAILY PIPELINE (Build third)

**Goal:** End-to-end daily run produces a committee-ready shortlist.

### 3a. `context/regime.py`

- VIX regime classification (GREEN/YELLOW/ORANGE/RED)
- Hurst exponent on SPY 60-day returns (TRENDING/RANDOM/MEAN_REVERT) — Chan EC-4

### 3b. `context/srm.py`

SRM v3.0: 11 GICS ETFs + thematic baskets. Grade each sector (DEPLOY/HOLD/TURNING/WATCH/AVOID). Uses `historical-price-eod-light` for efficiency.

### 3c. `context/ptrs.py`

PTRS = Engine Score + CM. CM = SH + RA + RL (v1.8, no BR). Map sector to GICS ETF. Classify disposition (FULL/HALF/QUARTER/REJECT).

### 3d. `main.py` — Orchestrator

Daily pipeline exactly as AQE Engineering Spec Section 5.1:
1. Incremental bar pull
2. Stage 1: Pipeline Rank for full universe (light bars)
3. Stage 2: Full scoring for top-50 (full OHLCV)
4. SRM overlay
5. PTRS computation
6. Output: shortlist JSON + dashboard text + Drive sync

### 3e. `output/` modules

- `shortlist.py` — JSON per AQE Engineering Spec Section 6.1
- `dashboard.py` — text dashboard per Section 6.2
- `drive.py` — upload to Google Drive "Trading Strategy" folder

**Phase 3 exit criteria:** `python main.py --date 2026-05-16` produces a scored shortlist. PM validates against live TV assessment for 5 consecutive sessions.

---

## PHASE 4: BACKTEST ENGINE (Build fourth)

**Goal:** Event-loop backtester that produces outcome-tagged database.

### 4a. `backtest/costs.py` — Transaction cost model

```python
SLIPPAGE_PCT = 0.0010       # 10bps per side
COMMISSION_PER_SHARE = 0.005

def entry_fill(price, shares):
    fill = price * (1 + SLIPPAGE_PCT)
    cost = shares * COMMISSION_PER_SHARE
    return fill, cost

def exit_fill(price, shares):
    fill = price * (1 - SLIPPAGE_PCT)
    cost = shares * COMMISSION_PER_SHARE
    return fill, cost
```

### 4b. `backtest/labels.py` — Dual outcome labelling

**Method 1: Trail-based** — simulate DSG-10 trail, record exit R. This is the primary label for the confidence layer.

**Method 2: Triple barrier (López de Prado)** — upper (+3R), lower (-1R), vertical (25 bars). Label by which barrier hit first. Records both label AND time-to-barrier.

Both methods run on every scored event. Both are stored. Confidence layer uses trail-based. Calibration engine analyses both.

### 4c. `backtest/engine.py` — Event loop

Iterates over trading days. For each day:
1. Score universe (re-uses Phase 2 engine modules)
2. Manage existing positions (DSG-10 trail, exit signals)
3. Evaluate new entries (qualification → sizing → entry with costs)
4. Record daily state (equity curve, positions, scores)

Sizing: charter disposition (FULL/HALF/QUARTER) × 1% risk budget. Apply quarter-Kelly ceiling from confidence layer once it has sufficient data (N ≥ 20).

### 4d. `backtest/portfolio.py` — Portfolio constraints

- Max positions: 6
- Max sector exposure: 35% (DSG-09)
- Weighted portfolio beta check (flag if > 2.5)
- Capacity check: warn if position > 1% of daily dollar volume (Chan EC-5)

### 4e. `backtest/confidence.py` — Backtest Confidence (BC) layer

Profile signature matching (composite band + MP state + regime + SRM grade + BD mode + FIP class). Tiered matching: EXACT → CORE → BROAD. Use tightest tier with N ≥ 20.

BC score (0-100): win_rate (40%) + expectancy (30%) + sample_size (15%) + consistency (15%).

BC modifier on PTRS: `(BC - 50) × 0.15`. Range ±7.5. Cannot resurrect a REJECT.

### 4f. `backtest/analytics.py` — Performance metrics

Standard: total trades, win rate, avg R, median R, expectancy, max drawdown, Sharpe, Sortino, Calmar.

DSG-10 specific: avg tier at exit, % reaching T2/T3/T4, trail capture ratio (exit R / peak R).

Monte Carlo (Pardo RP-5): 2000 permutations of trade sequence. Report median return, p5 drawdown, risk of ruin.

Survivorship bias: apply 2% annual haircut to reported returns (Chan EC-1).

**Phase 4 exit criteria:** Backtest reproduces known trade outcomes (JBL +5.66R peak, DOW/CLMT rejected by gates). Analytics dashboard is complete. Monte Carlo produces credible distribution.

---

## PHASE 5: CALIBRATION ENGINE (Build last)

**Goal:** Walk-forward framework with overfitting protection.

### 5a. `calibration/walkforward.py`

Both modes (Pardo RP-4):
- **Rolling:** 12-month train, 3-month test, 1-month step
- **Anchored:** Fixed start, growing train window, 3-month test, 1-month step

Compute WFER for each window. Reject if avg WFER < 0.30.

### 5b. `calibration/grid_search.py`

Coarse grid (Pardo RP-2): 7 levels per parameter. For 4 engine weights: 7^4 = 2,401 combinations. For weights: must sum to 1.0 (filter valid combos). For gates: independent grid per engine.

### 5c. `calibration/validation.py`

**Deflated Sharpe Ratio (López de Prado MLP-1):** Adjusts observed Sharpe for number of trials. Reject improvements where DSR < 1.0.

**Probability of Backtest Overfitting (López de Prado MLP-2):** CSCV with 16 partitions on the confidence layer's profile matching. If PBO > 0.40, restrict to BROAD tier matching.

**Purged K-Fold CV (López de Prado MLP-3):** Purge training observations whose forward windows overlap test set. Embargo = 1% of dataset after test set. Mandatory for all calibration.

**Walk-Forward Efficiency Ratio (Pardo RP-1):** OOS annual return / IS annual return. Report per window and average.

### 5d. `calibration/stability.py`

Parameter stability (Pardo): compute coefficient of variation of optimal parameter values across all walk-forward windows. CV < 0.15 = STABLE (adopt). CV 0.15-0.30 = ACCEPTABLE (adopt with monitoring). CV > 0.30 = UNSTABLE (keep current value).

### 5e. `calibration/report.py`

Weekly calibration report for PM review. Includes:
- Proposed parameter changes with evidence
- WFER per walk-forward window
- DSR for each proposed improvement
- Parameter stability chart
- PBO for confidence layer
- Recommendation: ADOPT / MONITOR / REJECT per parameter

**Phase 5 exit criteria:** Walk-forward analysis runs on 2-year historical data. WFER > 0.30. PBO < 0.40. At least one calibration cycle produces a recommendation the PM can review.

---

# CRITICAL IMPLEMENTATION RULES

1. **Every engine is independent.** No engine references another engine's output. They all consume raw OHLCV + benchmark data. The scorer module is the only place they combine.

2. **Persistent state variables must be stored in SQLite between daily runs.** The Structure BD counter, Energy trend bars, BQ base days — these accumulate across bars. If state is lost, scores will be wrong until the state re-accumulates (60+ bars).

3. **Weekly bars are computed locally from daily bars.** Zero FMP calls for weekly data. Aggregate Mon-Fri. Handle partial weeks (holidays, short weeks).

4. **Transaction costs are ALWAYS included in backtest results.** No gross-of-costs reporting ever. Chan's finding: 1.4-4.1% annual drag at this capital scale.

5. **No continuous optimisation.** Coarse grid search only (7 levels per parameter). López de Prado + Pardo both insist: finer resolution finds finer noise.

6. **Every calibration improvement must pass DSR ≥ 1.0 AND WFER ≥ 0.30 AND parameter stability CV < 0.30.** All three gates. Fail any one = keep current parameters.

7. **Survivorship bias haircut (2% annual) applied to ALL backtest return figures.** Non-negotiable.

8. **Confidence layer defaults to BC_modifier = 0 when sample_size < 20.** Insufficient data means no adjustment. System defaults to indicator-only scoring.

9. **RED regime (VIX > 30) = hard stop.** No entries, no PTRS evaluation. Backtest engine respects this.

10. **Output format is structured JSON.** Claude (Alfred) parses this. No prose in the data output. Prose is Alfred's job.

---

# FMP API BUDGET

**Starter plan: ~250 calls/day. Budget allocation:**

| Operation | Calls | Cadence |
|-----------|-------|---------|
| Top-50 full OHLCV (incremental) | 50 | Daily |
| Universe light bars (split across 4 days) | ~250 | Weekly (62/day) |
| SRM sector ETF + thematic (light) | 25 | Daily |
| SPY + VIX + sector ETFs | 15 | Daily |
| Earnings calendar (shortlist) | 10 | Daily |
| Batch quotes (session use) | 5 | As needed |
| **Daily total** | **~167** | Within budget |

**Rate limit handling:** 1-second delay between calls. Retry with exponential backoff on 429 responses. Log all API calls with timestamps.

---

# VALIDATION REFERENCE TICKERS

Use these 10 tickers for Phase 2 TV cross-validation:

| Ticker | Expected Profile | Why Selected |
|--------|-----------------|--------------|
| NNE | High SC_M, DEPLOY sector | Pipeline candidate |
| TECK | Mid SC_M, STAIR base | Active position |
| ADM | Lower SC_M, different sector | Active position |
| KGS | Runner, high MP | Active position (runner) |
| NVDA | High everything | Benchmark large-cap momentum |
| FSLR | Should be gated (AVOID sector) | Tests SRM gate |
| IONQ | Small-cap, volatile | Tests capacity check |
| XOM | Defensive, possible MISALIGNED | Tests RA modifier |
| SPY | Benchmark (RS=0 by definition) | Sanity check |
| DOW | Known REJECT (BD=0, DOW/CLMT lesson) | Tests gate enforcement |

Record TV dashboard values for all engines. AQE must match within ±2 per engine, ±3 on composite.

---

# DAILY OUTPUT EXAMPLE

```json
{
  "date": "2026-05-16",
  "regime": {"vix": 19.2, "level": "YELLOW", "hurst": 0.58, "trend": "TRENDING"},
  "max_new_size": "QUARTER",
  "candidates": [
    {
      "rank": 1,
      "ticker": "NNE",
      "pipe_rank": 82,
      "sc_momentum": 71.4,
      "sc_m_gates": true,
      "ptrs": 74,
      "ptrs_e": 77.2,
      "disposition": "FULL",
      "bc": {"score": 71, "tier": "CORE", "n": 34, "win_rate": 0.62, "avg_r": 1.8},
      "engines": {"flow": 68, "energy": 72, "structure": 79, "mp": 64, "elder": 8.0},
      "diagnostics": {"bd": 14, "bd_mode": "STAIR", "atr_comp": 0.62, "mp_state": "BUILDING", "fip": -0.14},
      "stops": {"tact": 52.10, "core": 50.40},
      "srm": {"sector": "Nuclear", "grade": "DEPLOY"},
      "kelly_ceiling": 0.018
    }
  ],
  "srm_summary": {"DEPLOY": ["Nuclear", "Copper"], "AVOID": ["Solar", "Lithium"]}
}
```

---

# WHAT SUCCESS LOOKS LIKE

**Week 1-2:** Phase 1 complete. TA library tested. FMP data flowing into SQLite.

**Week 3-5:** Phase 2 complete. All engines produce TV-validated scores. 10-ticker cross-validation documented.

**Week 6-7:** Phase 3 complete. Daily pipeline runs. PM receives scored shortlist every morning. Alfred consumes JSON for committee deliberation.

**Week 8-12:** Phase 4 complete. Backtest on 2 years of data. Outcome database seeded with ~500 tagged events. Confidence layer operational at BROAD tier.

**Week 13+:** Phase 5 initiated. First calibration cycle. Walk-forward results. Parameter stability analysis. System begins self-improving.

**TradingView:** Retained as PM visual confirmation tool. Zero computational authority. All scores come from AQE.

---

*AQE Consolidated Build Brief v1.0 | 18 May 2026*
*Aggregates: Design Committee Spec + Engineering Spec + Backtest Spec + Red Team Review + Voice Briefs*
*Charter authority: AIC v1.8*
*Advisory voices: López de Prado, Pardo, Chan*
