# AQE Research Panel — Sub-Session Briefing

## Context

You are a sub-session of a main AQE development session. AQE (Aegis Quant Engine)
is a production daily scanner for US equities that scores 600+ tickers nightly
through 9 proprietary engines, composites them into two headline scores
(SC_MOMENTUM and SC_POSITION), and outputs a ranked longlist of trade candidates.

The system runs daily, but until now we had NO backward-looking performance data.
We recently built a **Signal Ledger** — a historical backfill that replayed the
entire AQE scoring engine on every ticker x every trading day for ~5.5 years, then
computed forward returns and target-hit flags for each row. The result is
`research_panel.parquet`.

## Your Task

Analyze `research_panel.parquet` to find which combination of AQE sub-component
scores best separates high-forward-return, high-TP-hit-rate rows from the rest.
The current production filter (SC_MOM >= 65 & Elder >= 7) barely outperforms the
unfiltered universe — we need to find what actually works.

## File Location

```
C:\Users\ashtz\Claude\Projects\AQE Pull\Backtest Engine\data\research_panel.parquet
```

Load with: `pd.read_parquet(path)`

A ready-made analysis script also exists in the repo at:
```
scripts/research_analysis.py
```
You can run it (`python -m scripts.research_analysis data\research_panel.parquet`)
or adapt/extend it. It covers 8 analysis sections (correlations, RF importance,
clustering, Lasso, interactions, cross-method agreement). Install deps first:
`pip install scikit-learn scipy pyarrow`

## Dataset Schema

- **791,421 rows** — 602 tickers x every trading day from 2020-10-23 to 2026-07-02
- No pre-filtering applied — this is the FULL scored universe, not just signals
  that passed a threshold

### Key columns

**Identifiers**: `date`, `ticker`, `close`, `atr14`

**Aggregate engine scores (0-100 scale)**:
- `flow_100` — Flow engine (accumulation, volume, skew, extension, MFI, CMF)
- `energy_100` — Energy engine (VP position, price action, squeeze, exhaustion)
- `structure_100` — Structure engine (RS vs SPY, base detection, market structure)
- `mp_100` — Momentum/Phase engine (absolute + relative momentum, ADX, trend)
- `elder_score` — Elder Impulse (7-9 scale, 7+ = entry-eligible)
- `bq_100` — Base Quality (range tightness, volume dry-up, EMA convergence)
- `k39_value` — K39 gate (weekly confirmation)

**Composites**:
- `sc_momentum` / `sc_momentum_raw` — SC_MOM composite: Flow(30%) + Energy(30%) + Structure(20%) + MP(20%)
- `sc_position` / `sc_position_raw` — SC_POS composite: Flow(10%) + Energy(30%) + Structure(20%) + MP(5%) + BQ(35%)
- `pipe_rank` / `fip_quality` — Pipeline Rank (12-mo return, ADX, RSI, vol, MA alignment)

**Readiness score** (0-100, "is this name about to move?"):
- `rd_score`, `rd_state` (READY/WATCH/NEUTRAL/NOT_READY)
- `rd_compression` (0-60), `rd_trigger` (0-25), `rd_pos_mod` (-15 to 0), `rd_rs_bonus` (0-15)
- `rd_inside_bars`, `rd_range_exp`, `rd_vol_surge`, `rd_close_str`

**Health score** (0-100, "should I stay in this position?"):
- `hl_score`, `hl_state` (HOLD_ADD/HOLD/TIGHTEN/EXIT)
- `hl_trend` (0-35), `hl_flow` (0-25), `hl_rs` (0-20), `hl_risk` (-20 to 0)
- `hl_higher_lows`, `hl_trend_bars`, `hl_vol_updn`, `hl_atr_spike`

**Flow sub-components**: `flow_score`, `accum_score`, `volume_score`, `skew_score`,
`ext_score`, `mfi`, `cmf`, `ha_quality_count`

**Energy sub-components**: `vp_position_score`, `price_action_score`, `squeeze_score`,
`exhaustion_score`, `atr_score`, `en_pos50`, `en_trend_bars`

**Structure sub-components**: `rs_spy_score`, `rs_accel_score`, `base_score`,
`ms_pos_score`, `resist_score`, `wk_score`, `earn_score`, `base_days`, `bd_mode`,
`ms_p50`, `rs_vs_spy`, `rs_accel`

**MP sub-components**: `abs_mom_score`, `mp_adx_score`, `rel_mom_score`, `trend_score`,
`roc_zscore`, `excess_return`, `adx_val`, `di_bullish`

**BQ sub-components**: `bq_range_tight`, `bq_vol_dry`, `bq_base_dur`, `bq_ema_conv`,
`bq_base_days`

**Pipeline Rank sub-components**: `momentum_composite`, `pipe_tier`, `pr_ret_12m`,
`pr_adx_score`, `pr_rsi_score`, `pr_vol_score`, `pr_ma_score`

**Forward-looking outcomes** (the target variables):
- `ret_t5`, `ret_t10`, `ret_t20` — % forward returns at 5/10/20 trading days
- `tp1_hit` — binary: did price reach +1R (1x risk) within 20 days?
- `tp2_hit` — binary: did price reach +2R within 20 days?
- `sl_hit` — binary: did price hit 1.5×ATR stop within 20 days?

**Production filter flags**:
- `is_longlist` — True if SC_MOM >= 65 AND Elder >= 7 (current production filter)
- `is_elder_list` — True if Elder >= 8

## Critical Baseline Numbers

The current production longlist filter BARELY beats the unfiltered universe:

| Metric | Full Universe | Longlist (SC_MOM>=65, Elder>=7) |
|--------|-------------|-------------------------------|
| Avg T20 return | ~1.93% | ~1.98% |
| TP1 hit rate | ~64.4% | ~66.0% |

**This means the current composite weights and thresholds are unproven.** Treat them
as a hypothesis to test, not ground truth. The goal is to find what actually works.

## Data Preparation

**Drop rows where `ret_t20` is null** before any analysis — these are the most recent
~20 trading days per ticker where forward returns can't be computed yet.

## Analysis Objectives (in priority order)

### 1. Univariate Feature Screen
For every sub-component score, compute:
- Spearman rank correlation vs `ret_t20` and vs `tp1_hit`
- Quintile spread: mean(top quintile) - mean(bottom quintile) for both targets
- Statistical significance (p-value)

**Deliverable**: Ranked list of all features by TP1 predictive power. Which
sub-components actually predict forward returns? Which are noise?

### 2. Feature Importance (ML)
- Random Forest classifier for `tp1_hit` — feature importances + 5-fold CV AUC
- Random Forest regressor for `ret_t20` — feature importances
- Lasso logistic regression for `tp1_hit` — sparse feature selection

**Deliverable**: Which features survive regularization? RF + Lasso + Spearman
cross-method agreement = the robust signal set.

### 3. Clustering
- K-Means (k=6,8,10) on the sub-component score vectors (standardized)
- For each cluster: N, avg ret_t5/t10/t20, TP1/TP2/SL hit rates, % positive at T20
- Cluster centroids: what features define the best-performing cluster?

**Deliverable**: Do natural clusters in score-space map to differentiated forward
returns? If cluster C3 has 72% TP1 vs 64% baseline, what scores define it?

### 4. Interaction Effects
- 2-way: for top features, split at median, compare all (high, high) quadrants
  vs baseline — which PAIRS produce the biggest TP1 lift?
- 3-way: extend to triples — does adding a third feature improve further?

**Deliverable**: The best 2-feature and 3-feature combinations for TP1 prediction.

### 5. Proposed New Filter
Based on findings from steps 1-4, propose:
- A new longlist filter formula (which features, what thresholds)
- Expected TP1 hit rate and avg T20 return for the new filter
- Comparison table: old filter vs new filter vs full universe
- Sample size (how many rows pass the new filter — must be tradeable, not
  too restrictive: aim for 5-15 names per day on average)

### 6. Walk-Forward Validation (if time permits)
- Split data into train (2020-2024) and test (2025-2026)
- Fit the filter/model on train, evaluate on test
- Does the improvement survive out-of-sample?

## Output Format

Save all CSV outputs to `output/research/` (create if needed). Key files:
- `univariate_correlations.csv`
- `feature_importance.csv`
- `cluster_profiles.csv`
- `interaction_effects.csv`
- `cross_method_agreement.csv`
- `proposed_filter_comparison.csv`

Print a **summary report** to the console with the key findings. Focus on
actionable conclusions:
1. Which features predict TP1 hits? (top 10 with direction)
2. Which features are noise or negatively predictive? (bottom 10)
3. Best 2-3 feature combination and its TP1/T20 numbers
4. Proposed new filter vs current longlist baseline
5. Any surprises (e.g., features that work opposite to expectation)

## What NOT To Do

- Do NOT change any AQE source code — this is a read-only analysis session
- Do NOT commit data files to git (parquet/db files are gitignored)
- Do NOT treat `is_longlist` as a filter to apply — it's a baseline flag to compare against
- Do NOT use the composites (sc_momentum, sc_position) as features in ML models —
  they ARE the current formula; we want to find if a DIFFERENT weighting works better.
  Use only the sub-component scores as predictors
- Do NOT over-optimize on the full dataset without a holdout — report in-sample AND
  out-of-sample numbers separately

## Repo Structure (for reference)

```
C:\Users\ashtz\Claude\Projects\AQE Pull\Backtest Engine\
├── data/
│   ├── research_panel.parquet    ← YOUR INPUT (791K rows)
│   ├── scores_daily.parquet      ← Full score history (all tickers x all dates)
│   ├── panel_daily.parquet       ← Raw OHLCV bars
│   ├── aqe.db                    ← Signal ledger SQLite DB
│   └── ...
├── scripts/
│   └── research_analysis.py      ← Ready-made analysis script (8 sections)
├── output/
│   └── research/                 ← Save outputs here
├── src/
│   ├── engines/                  ← Score computation code (read-only reference)
│   ├── data/signal_ledger.py     ← How the research panel was built
│   └── ...
└── ...
```

## After You're Done

Report back to the main session with:
1. The top findings (which features predict, which don't)
2. A proposed new filter formula with performance numbers
3. Any surprises or concerns about data quality
4. The CSV files in `output/research/` for the main session to review

The main session will then decide whether to modify AQE's production scoring
weights and thresholds based on your findings.
