# AEGIS DESIGN COMMITTEE — SYSTEM SPECIFICATION
## For Backtesting Engine & FMP-Based Python Screener

**Document Version:** 1.0
**Charter Authority:** AIC Charter v1.8 (Effective 9 May 2026)
**Indicator Stack:** Scoring v1.6.0 | Structure v1.5.0 | Energy v1.3.1 | Flow v1.3 | MP v1.2 | Elder v1 | DSL v1.4 | Pipeline Rank v1.0
**Data Source:** FMP via MCP (historical EOD), replacing Massive.com (deprecated for SRM v3.0)
**Purpose:** Complete specification of indicators, scoring logic, gates, qualification pipeline, and process — sufficient to implement a standalone Python backtester + FMP screener, reducing TradingView to PM illustrative tool only.

---

# PART 1 — ARCHITECTURE OVERVIEW

## Design Philosophy

The Aegis system is a **multi-engine quantitative scoring framework** that produces two parallel composite scores for every equity candidate. Each engine measures a distinct dimension of stock quality. Engines are **independent** — no engine references another engine's output. The composites are **weighted sums** of normalised engine scores. Qualification requires both the composite score AND independent gate checks to pass.

The system operates in two stages:

**Stage 1: Screener (Pipeline Rank v1.0)** — Filters the US equity universe (~8,000 names) down to 10-15 candidates using a simplified momentum+path-quality composite. Zero external data dependencies beyond daily OHLCV. Designed for batch processing.

**Stage 2: Chart Analysis (Scoring v1.6.0)** — Full 5-engine scoring suite applied to individual candidates. Requires benchmark data (SPY), weekly bars, and multiple timeframe calculations. Produces SC_MOMENTUM and SC_POSITION composites.

**Post-Scoring: PTRS (Pre-Trade Readiness Score)** — Adds macro context (sector health, regime alignment, VIX level) to the engine score. Determines position sizing. Computed by Alfred (orchestration layer), NOT by the indicator.

```
Universe (~8,000)
    │
    ▼
  [Pipeline Rank v1.0] — FMP daily OHLCV batch
    │  Filter: PIPE_RANK ≥ 60
    ▼
  Shortlist (10-15 names)
    │
    ▼
  [Scoring v1.6.0] — per-ticker chart analysis
    │  SC_MOMENTUM composite + Elder gate
    │  SC_POSITION composite + K39 gate
    ▼
  Engine-Qualified Candidates
    │
    ▼
  [PTRS = Engine Score + Context Modifier]
    │  CM = SH + RA + RL
    ▼
  Disposition: FULL / HALF / QUARTER / REJECT
    │
    ▼
  [Committee Deliberation] → PM Decision
```

## Data Requirements Summary

| Data Item | Source | Bars Needed | Used By |
|-----------|--------|-------------|---------|
| Candidate daily OHLCV | FMP `historical-price-eod-full` | 252 (1yr) | All engines |
| SPY daily OHLCV | FMP `historical-price-eod-full` | 252 | Structure (RS), MP (relative), Elder |
| Candidate weekly OHLCV | FMP `historical-price-eod-full` (aggregate) | 52 | Structure (weekly trend), K39 gate |
| VIX daily close | FMP `quote` (^VIX) | 30 | DSL (regime display), PTRS (RL) |
| Sector ETF daily close | FMP `historical-price-eod-light` | 30 | SRM, PTRS (SH) |

---

# PART 2 — ENGINE SPECIFICATIONS

## Engine 1: FLOW v1.3

**Question answered:** "Is institutional money flowing into this stock?"

**Raw max: 38.0 points → normalised to 0-100 scale**

`flow_100 = min(max(raw / 38.0 × 100, 0), 100)`

### Component 1A: Institutional Flow (17.0 pts max)

**Sub-component: MFI + CMF fusion (11.0 pts)**

Money Flow Index (10-period):
```python
# Accumulate positive and negative money flow over 10 bars
mu = sum(volume[i] * hlc3[i] for i in range(10) if hlc3[i] > hlc3[i+1])
ml = sum(volume[i] * hlc3[i] for i in range(10) if hlc3[i] <= hlc3[i+1])
mfi = 100 - (100 / (1 + mu / ml)) if ml != 0 else 50
```

Chaikin Money Flow (10-period):
```python
cmf_vol = sum(((close[i]-low[i]) - (high[i]-close[i])) / (high[i]-low[i]) * volume[i]
           for i in range(10) if high[i] != low[i])
cmf_sum = sum(volume[i] for i in range(10) if high[i] != low[i])
cmf = cmf_vol / cmf_sum if cmf_sum != 0 else 0
```

Scoring table:

| MFI | CMF | Score |
|-----|-----|-------|
| >55 | >0.05 | 11.0 |
| >48 | >0.02 | 8.0 |
| >42 | >0.00 | 5.0 |
| >38 or CMF>-0.05 | — | 2.5 |
| else | else | 0.0 |

**Sub-component: Heikin-Ashi quality (6.0 pts)**

Count of last 10 bars where HA body < 0.5 × ATR(20):
```python
ha_close = (open[i] + high[i] + low[i] + close[i]) / 4
ha_open = (open[i+1] + close[i+1]) / 2  # simplified; i==0 uses (open+close)/2
ha_count = count where abs(ha_close - ha_open) < atr20 * 0.5
```

| HA Count | Score |
|----------|-------|
| ≥5 | 6.0 |
| ≥3 | 4.0 |
| ≥2 | 2.0 |
| <2 | 0.0 |

`institutional_flow = min(mfi_cmf_score + ha_score, 17.0)`

### Component 1B: Accumulation (7.5 pts max)

Uses Accumulation/Distribution line with linear regression slope comparison:
```python
ad_line = cumsum(((2*close - low - high) / (high - low)) * volume)
# Handle edge case: if close==high and close==low, contribution = 0
slope_short = linreg_slope(ad_line, 10)  # 10-bar slope
slope_long = linreg_slope(ad_line, 20)   # 20-bar slope
```

| Condition | Score |
|-----------|-------|
| slope_long ≠ 0 AND slope_short > slope_long × 1.1 | 7.5 |
| slope_long ≠ 0 AND slope_short > slope_long | 5.5 |
| slope_long ≠ 0 AND slope_short > slope_long × 0.85 | 3.0 |
| slope_short > 0 | 1.5 |
| else | 0.0 |

### Component 1C: Volume Trend (7.5 pts max)

```python
vol_5 = sma(volume, 5)
vol_20 = sma(volume, 20)
vol_trend_ratio = vol_5 / vol_20
spike = volume / vol_20
```

Volume trend base:

| vol_trend_ratio | Base Score |
|-----------------|------------|
| >1.2 | 5.5 |
| >1.05 | 4.0 |
| >0.9 | 2.0 |
| ≤0.9 | 0.0 |

Spike bonus: +2.0 if spike > 2.0, +1.0 if spike > 1.5, else 0.

`volume_trend = min(base + spike_bonus, 7.5)`

### Component 1D: Volume Skew (3.5 pts max)

```python
up_vol = sum(volume[i] for i in range(10) if close[i] > close[i+1])
down_vol = sum(volume[i] for i in range(10) if close[i] <= close[i+1])
up_down_ratio = up_vol / down_vol if down_vol != 0 else 1.0
```

| Ratio | Score |
|-------|-------|
| >1.5 | 3.5 |
| >1.2 | 2.5 |
| ≥0.8 | 1.5 |
| <0.8 | 0.0 |

### Component 1E: Extension Modifier (+5 to -8 pts)

```python
hi20 = highest(high, 20)
hi20_prior = highest(high[1], 20)
is_new_high = high >= hi20_prior
lo20 = lowest(low, 20)
range_20 = hi20 - lo20
pct_position = (close - lo20) / range_20 * 100 if range_20 != 0 else 50
ema20 = ema(close, 20)
dev_from_ema = (close - ema20) / ema20 * 100
close_ratio = (close - low) / (high - low) if (high - low) != 0 else 0.5
vol_ratio = volume / vol_20
range_5 = highest(high, 5) - lowest(low, 5)
avg_tr_range = sma(true_range, 20) * 5
is_contracted = range_5 / avg_tr_range < 0.6
```

| Condition | Score |
|-----------|-------|
| is_new_high AND vol_ratio > 1.5 AND close_ratio > 0.6 | +5.0 |
| pct_position > 85 AND vol_ratio > 1.2 AND close_ratio > 0.5 | +3.0 |
| dev_from_ema > 12 AND vol_ratio > 2.0 AND close_ratio < 0.4 | -8.0 |
| dev_from_ema > 8 AND NOT is_contracted AND close_ratio < 0.4 | -5.0 |
| pct_position < 25 | +3.0 |
| else | 0.0 |

**Final Flow:** `flow_raw = max(min(institutional + accumulation + volume_trend + skew + extension, 38), 0)`

---

## Engine 2: ENERGY v1.3.1

**Question answered:** "Is this stock coiled and ready to move?"

**Raw max: 59.5 points → normalised to 0-100**

`energy_100 = min(max(raw / 59.5 × 100, 0), 100)`

### Component 2A: Range Position / VP Proxy (17.5 pts max)

**CRITICAL NOTE:** Energy uses a 50-bar range-position PROXY, not a true volume profile array. This was standardised in DSG-05 to ensure ONE calculation, ONE number across standalone and overlay versions.

```python
hi50 = highest(high, 50)
lo50 = lowest(low, 50)
rng50 = hi50 - lo50
pos50 = (close - lo50) / rng50 * 100 if rng50 != 0 else 50
```

Range position scoring:

| pos50 | Base Score |
|-------|-----------|
| ≥90 | 15.0 |
| ≥75 | 17.0 ← sweet spot (near top but not overextended) |
| ≥60 | 12.0 |
| ≥45 | 8.0 |
| ≥30 | 5.0 |
| <30 | 3.0 |

LVN bonus (tight at top):
```python
r5_total = highest(high, 5) - lowest(low, 5)
tight_at_top = pos50 > 75 and r5_total < atr20 * 2.0
lvn_bonus = 1.5 if tight_at_top else 0.0
```

`vp_score = min(base + lvn_bonus, 17.5)`

### Component 2B: Price Action (12.5 pts max, with depth modifier)

**Higher-lows structure (5.0 pts):**
```python
hl_count = sum(1 for i in range(1,5) if low[i-1] > low[i])
structure = {4: 5.0, 3: 4.0, 2: 3.0, 1: 1.5}.get(hl_count, 0.0)
```

**Tightness (4.5 pts):**
```python
range_5d = highest(high, 5) - lowest(low, 5)
range_20d = highest(high, 20) - lowest(low, 20)
compression = range_5d / range_20d if range_20d != 0 else 1.0

tightness_base = {
    compression < 0.3: 4.5,
    compression < 0.5: 3.5,
    compression < 0.7: 2.0,
    compression < 0.9: 1.0,
}.get(True, 0.0)  # pseudocode: first matching condition

trending_up = close > ema(close, 20) and close > close[5]
tightness = min(tightness_base + 1.5, 4.5) if trending_up else tightness_base
```

**Pullback from recent high (3.0 pts):**
```python
recent_high = highest(high, 20)
pullback_pct = (recent_high - close) / recent_high * 100

pullback = {
    pullback_pct < 5: 3.0,
    pullback_pct < 10: 2.5,
    pullback_pct < 15: 2.0,
    pullback_pct < 25: 1.0,
}.get(True, 0.0)
```

**Depth modifier:** If pos50 < 30 → multiply PA raw by 0.5. If pos50 < 45 → multiply by 0.7. Else 1.0.

`price_action = (structure + tightness + pullback) × depth_modifier`

### Component 2C: Squeeze Detection (12.5 pts max)

Bollinger Bands inside Keltner Channels = squeeze condition.

```python
bb_mid = sma(close, 20)
bb_std = 2.0 * stdev(close, 20)
bb_upper = bb_mid + bb_std
bb_lower = bb_mid - bb_std
bb_width = (bb_upper - bb_lower) / bb_mid * 100

# Bandwidth percentile over 50 bars
bw_low = lowest(bb_width, 50)
bw_high = highest(bb_width, 50)
bw_pctl = (bb_width - bw_low) / (bw_high - bw_low) * 100

kc_range = atr(20)
kc_upper = bb_mid + kc_range * 1.5
kc_lower = bb_mid - kc_range * 1.5
in_squeeze = bb_lower > kc_lower and bb_upper < kc_upper
```

| Condition | Score |
|-----------|-------|
| in_squeeze AND bw_pctl < 20 | 12.5 |
| in_squeeze AND bw_pctl < 35 | 10.0 |
| in_squeeze AND bw_pctl < 50 | 7.5 |
| in_squeeze | 5.0 |
| bw_pctl < 30 (no squeeze) | 8.5 |
| bw_pctl < 50 | 4.0 |
| else | 0.0 |

### Component 2D: Exhaustion (10.0 pts max, with trend-duration gate)

**Trend maturity gate:** Deductions are SUPPRESSED if the stock has been above EMA(20) for fewer than `exh_trend_min` bars (default: 15). Early-trend volume is confirmation, not exhaustion.

```python
# Trend duration counter (persistent)
if close > ema(close, 20):
    trend_bars += 1
else:
    trend_bars = 0
trend_mature = trend_bars >= 15
```

**Deductions (applied only if trend_mature):**

Climactic volume penalty:
```python
vol_ratio = volume / sma(volume, 20)
gain_pct = (close - close[1]) / close[1] * 100
climactic = -4.0 if (vol_ratio > 3.0 and gain_pct < 2) else \
            -2.5 if (vol_ratio > 2.5 and gain_pct < 3) else 0.0
```

Divergence penalty:
```python
mfi14 = mfi(close, 14)
mfi_prev_high = highest(mfi14, 5)[1]  # exclude current bar
price_new_high = high == highest(high, 10)
mfi_lower = mfi14 < mfi_prev_high
macd_line = ema(close, 12) - ema(close, 26)
macd_prev_high = highest(macd_line, 5)[1]
macd_lower = macd_line < macd_prev_high

divergence = -3.0 if (price_new_high and mfi_lower) else \
             -2.0 if (price_new_high and macd_lower) else 0.0
```

Wide-spread penalty:
```python
bar_range_ratio = (high - low) / atr(20)
follow_through = 1.0 if (bar_range_ratio > 2.0 and close[1] < close and high[1] < high) else 0.0
wide_spread = -3.0 if (bar_range_ratio > 2.0 and vol_ratio > 2.0 and follow_through == 0) else \
              -1.5 if (bar_range_ratio > 1.5 and vol_ratio > 1.5) else 0.0
```

`exhaustion = max(10.0 + climactic + divergence + wide_spread, 0.0) if trend_mature else 10.0`

### Component 2E: ATR Expansion (7.0 pts max)

```python
atr_5d = sma(atr(20), 5)
atr_20d = sma(atr(20), 20)
expansion_pct = (atr_5d - atr_20d) / atr_20d * 100
```

| Expansion % | Score |
|-------------|-------|
| 20-80% | 7.0 ← Goldilocks: expanding but not exploding |
| >150% | 2.0 |
| >80% | 4.0 |
| ≥15% | 5.5 |
| ≥10% | 4.0 |
| ≥0% | 1.0 |
| ≥-10% | 0.5 |
| <-10% | 0.0 |

**Final Energy:** `energy_raw = vp + price_action + squeeze + exhaustion + atr_expansion`

---

## Engine 3: STRUCTURE v1.5.0

**Question answered:** "Is this stock in a position of structural strength?"

**Raw max: 95.0 points → normalised to 0-100**

`structure_100 = min(max(raw / 95.0 × 100, 0), 100)`

### Component 3A: Relative Strength vs SPY (15 pts)

```python
lookback = 60  # bars
stock_perf = (close - close[60]) / close[60] * 100
spy_perf = (spy_close - spy_close[60]) / spy_close[60] * 100
rs_vs_spy = stock_perf - spy_perf
```

| RS vs SPY | Score |
|-----------|-------|
| >10% | 15.0 |
| >5% | 12.0 |
| >2% | 10.0 |
| >0% | 6.0 |
| >-3% | 3.0 |
| ≤-3% | 0.0 |

### Component 3B: RS Acceleration (15 pts)

```python
rs_short = (close - close[20]) / close[20] * 100 - \
           (spy_close - spy_close[20]) / spy_close[20] * 100
rs_accel = rs_short - rs_vs_spy  # positive = accelerating
```

| RS Accel | Score |
|----------|-------|
| >5 | 15.0 |
| >2 | 12.0 |
| >0 | 9.0 |
| >-2 | 6.0 |
| >-5 | 3.0 |
| ≤-5 | 0.0 |

### Component 3C: Base Duration — 3-Mode System (15 pts)

**This is the core structural innovation of the Aegis system.** Three distinct consolidation patterns are detected. ANY mode qualifying counts as a base day.

**Mode 1: VCP/Flat Base (original)**
```python
range_10 = highest(high, 10) - lowest(low, 10)
range_pct = range_10 / close * 100
mode1 = range_pct <= 15.0  # 10-bar range ≤ 15% of price
```

**Mode 2: Staircase Consolidation (DSG-04)**
```python
sma50 = sma(close, 50)
uptrend = close > sma50 and sma50 > sma50[5]  # SMA50 rising
hi10 = highest(high, 10)
pullback_depth = (hi10 - close) / hi10 * 100
shallow_pb = 1.5 <= pullback_depth <= 8.0
stair_hl = sum(1 for i in range(1, 6) if low[i-1] > low[i])
has_staircase = stair_hl >= 2
mode2 = uptrend and shallow_pb and has_staircase
```

**Mode 3: Smooth Trend (DSG-06)**
```python
ema20 = ema(close, 20)
ema20_rising = ema20 > ema20[3]
near_ema20 = abs(close - ema20) <= atr(20) * 1.0
mode3 = ema20_rising and near_ema20 and close > sma50
```

**Combined detection:**
```python
in_base = mode1 or mode2 or mode3

# Mode diagnostic (for export/display)
mode_count = int(mode1) + int(mode2) + int(mode3)
bd_mode = 4 if mode_count >= 2 else (3 if mode3 else (2 if mode2 else (1 if mode1 else 0)))
# 0=none, 1=VCP, 2=staircase, 3=smooth, 4=multi
```

**Accumulation counter (persistent state):**
```python
if in_base:
    raw_base_count += 1
else:
    raw_base_count = 0
```

**Breakout detection (DSG-02 latch):**
```python
# Consolidation high from accumulated base
prev_len = max(raw_base_count_prev, 1)
cap_len = min(prev_len, 60)
cons_high = max(high[i] for i in range(1, cap_len + 1))

breakout = (close > cons_high and
            not in_base and
            raw_base_count_prev >= 3 and
            volume > sma(volume, 20))

# Latch mechanism
if breakout:
    latched_bd = raw_base_count_prev
    bars_since_bo = 0
else:
    bars_since_bo += 1

# Reported value with 10-bar decay
base_days = latched_bd if bars_since_bo <= 10 else raw_base_count
```

**Base duration scoring:**

| Base Days | Raw Score |
|-----------|-----------|
| <3 | 0.0 |
| 3-4 | 3.0 |
| 5-6 | 6.0 |
| 7-9 | 10.0 |
| 10-25 | 15.0 ← sweet spot |
| 26-30 | 12.0 |
| 31-35 | 8.0 |
| >35 | 5.0 |

**Higher-lows quality multiplier:**
```python
hl_lookback = min(base_days, 10)
hl_count = sum(1 for i in range(1, hl_lookback+1) if low[i] > low[i+1])
quality_mult = 1.0 if hl_count >= 4 else (0.8 if hl_count >= 2 else 0.6)
base_score = min(raw_score * quality_mult, 15.0)
```

### Component 3D: Range Position (15 pts, 50-bar)

```python
h50 = highest(high, 50)
l50 = lowest(low, 50)
r50 = h50 - l50
p50 = (close - l50) / r50 * 100 if r50 != 0 else 50
```

| Range Position | Score |
|----------------|-------|
| ≥95% | 15.0 |
| ≥85% | 13.0 |
| ≥75% | 10.0 |
| ≥60% | 7.0 |
| ≥45% | 4.0 |
| <45% | 0.0 |

### Component 3E: Resistance Clearance (10 pts)

```python
nearest_resist = highest(high, 50)
dist_to_resist = (nearest_resist - close) / close * 100
```

| Distance to Resistance | Score |
|------------------------|-------|
| ≤0% (above) | 7.0 |
| ≤3% | 10.0 ← approaching from below, best entry zone |
| ≤8% | 5.0 |
| ≤15% | 3.0 |
| >15% | 0.0 |

### Component 3F: Weekly Trend (15 pts)

**Requires weekly timeframe data.**
```python
wk_sma10 = sma(weekly_close, 10)  # use bar [1] to avoid lookahead
wk_sma10_prev = wk_sma10[1]       # previous week
wk_rising = wk_sma10 > wk_sma10_prev
```

| Condition | Score |
|-----------|-------|
| weekly_close > wk_sma10 AND wk_rising | 15.0 |
| weekly_close > wk_sma10 | 10.0 |
| weekly_close > wk_sma10 × 0.97 | 5.0 |
| weekly_close > wk_sma10 × 0.93 | 2.0 |
| else | 0.0 |

**Backtester note:** If weekly data unavailable, use 7.5 (midpoint) as fallback.

### Component 3G: Earnings Proximity (10 pts)

```python
days_to_earnings = (next_earnings_date - current_date).days
```

| Days to Earnings | Score |
|------------------|-------|
| ≤5 | 0.0 (EARNINGS WARNING flag) |
| ≤10 | 4.0 |
| ≤20 | 7.0 |
| >20 or unknown | 10.0 |

### Diagnostics (not scored, exported for committee)

- **NR7/NR4 contraction:** daily range ≤ lowest daily range over 7 (or 4) bars. Collin Seow pattern — NR7 inside a base = coiled spring.
- **ATR compression ratio:** `atr(5) / atr(20)`. <0.7 = consolidating. Raschke reference.
- **Pullback diagnostic:** scored 0-12 based on depth + structure.
- **Pivot diagnostic:** weekly pivots (PP, R1, R2, S1) — scored 0-8.
- **ATR risk:** `atr(20) / close * 100`. <3.5% = low risk.

---

## Engine 4: MOMENTUM PERSISTENCE (MP) v1.2

**Question answered:** "Is this momentum likely to persist?"

**Raw max: 100.0 (already on 0-100 scale, no normalisation needed)**

### Component 4A: Absolute Momentum (30 pts)

```python
roc = rate_of_change(close, 20)
roc_mean = sma(roc, 50)
roc_stdev = stdev(roc, 50)
z_score = (roc - roc_mean) / roc_stdev if roc_stdev != 0 else 0
```

| Z-Score | Score |
|---------|-------|
| ≥2.0 | 30.0 |
| ≥1.5 | 26.0 |
| ≥1.0 | 22.0 |
| ≥0.5 | 16.0 |
| ≥0.0 | 10.0 |
| ≥-0.5 | 5.0 |
| <-0.5 | 0.0 |

### Component 4B: Trend Persistence — ADX (25 pts)

```python
di_plus, di_minus, adx = dmi(14, 14)
di_bullish = di_plus > di_minus
```

| ADX | DI+ Leading | Score |
|-----|-------------|-------|
| ≥40 | Yes | 25.0 |
| ≥30 | Yes | 22.0 |
| ≥25 | Yes | 18.0 |
| ≥20 | Yes | 12.0 |
| any | No | 0.0 |

### Component 4C: Relative Momentum (25 pts)

```python
stock_roc = rate_of_change(close, 20)
spy_roc = rate_of_change(spy_close, 20)
excess_return = stock_roc - spy_roc
```

| Excess Return | Score |
|---------------|-------|
| ≥15% | 25.0 |
| ≥10% | 22.0 |
| ≥5% | 18.0 |
| ≥2% | 13.0 |
| ≥0% | 8.0 |
| ≥-3% | 3.0 |
| <-3% | 0.0 |

### Component 4D: Trend Structure (20 pts)

```python
ma50 = sma(close, 50)
ma20 = ema(close, 20)
ma50_rising = ma50 > ma50[5]
ma20_rising = ma20 > ma20[3]
above_50 = close > ma50
above_20 = close > ma20
```

| Condition | Score |
|-----------|-------|
| above_20 AND above_50 AND ma20_rising AND ma50_rising | 20.0 |
| above_20 AND above_50 AND ma50_rising | 16.0 |
| above_50 AND ma50_rising | 12.0 |
| above_50 | 8.0 |
| above_20 (only) | 5.0 |
| else | 0.0 |

### MP State Machine (for bar colouring and committee)

```python
mp_rising = mp_score > mp_score[3]  # 3-bar rate of change
mp_state = 1 if (mp_rising and mp_score < 75) else \
           2 if (mp_rising and mp_score >= 75) else 3
# 1 = BUILDING (green) — entry zone
# 2 = STRONG (yellow) — hold, trail stops
# 3 = FADING (red) — no new entry
```

---

## Engine 5: ELDER IMPULSE SCORE v1

**Question answered:** "Is the current bar bullish, bearish, or neutral?"

**Used as: SC_MOMENTUM gate (≥ 6.5 required). NOT a composite weight.**

**Scale: 0-10**

### Component 5A: Impulse State (0-4 pts)

```python
ema13 = ema(close, 13)
macd_line, signal, hist = macd(close, 12, 26, 9)

impulse_green = ema13 > ema13[1] and hist > hist[1]
impulse_red = ema13 < ema13[1] and hist < hist[1]

state_score = 4.0 if impulse_green else (2.0 if not impulse_red else 0.0)
```

### Component 5B: EMA Slope (0-3 pts)

```python
slope = (ema13 - ema13[3]) / ema13 * 100
slope_score = 3.0 if slope > 1.0 else (2.0 if slope > 0.3 else (1.0 if slope > 0 else 0.0))
```

### Component 5C: Histogram Momentum (0-3 pts)

```python
hist_accel = hist - hist[1]
hist_score = 3.0 if (hist > 0 and hist_accel > 0) else \
             2.0 if hist > 0 else \
             1.0 if hist_accel > 0 else 0.0
```

`elder_score = state_score + slope_score + hist_score`

---

# PART 3 — COMPOSITE SCORING & QUALIFICATION

## SC_MOMENTUM (Breakout Pipeline, 1-2 week holding)

**Weights:** Flow 30% | Energy 30% | Structure 20% | MP 20%

```python
sc_m_raw = (flow_100 * 0.30) + (energy_100 * 0.30) + \
           (structure_100 * 0.20) + (mp_100 * 0.20)
```

### Momentum Gates (ALL must pass)

| Gate | Threshold |
|------|-----------|
| Elder Score | ≥ 6.5 |
| Flow | ≥ 60 |
| Energy | ≥ 60 |
| Structure | ≥ 55 |
| MP | ≥ 55 |

```python
elder_passes = elder_score >= 6.5
engines_pass = (flow_100 >= 60 and energy_100 >= 60 and
                structure_100 >= 55 and mp_100 >= 55)
all_gates = elder_passes and engines_pass

sc_momentum = sc_m_raw if all_gates else min(sc_m_raw, 49.0)
```

**Key design:** If ANY gate fails, the composite is hard-capped at 49.0 regardless of raw score. This prevents a stock with one severely deficient dimension from qualifying.

## SC_POSITION (Base-Building Pipeline, 3-6 week holding)

**Weights:** Flow 10% | Energy 30% | Structure 20% | MP 5% | Base Quality 35%

```python
sc_p_raw = (flow_100 * 0.10) + (energy_100 * 0.30) + \
           (structure_100 * 0.20) + (mp_100 * 0.05) + (bq_100 * 0.35)
```

### Base Quality (BQ) Sub-Engine

**BQ raw max: 100.0 (already normalised)**

**BQ1: Range Tightness (30 pts)**
```python
atr5 = atr(5)
atr20 = atr(20)
rt_ratio = atr5 / atr20
```

| RT Ratio | Score |
|----------|-------|
| <0.5 | 30.0 |
| <0.6 | 25.0 |
| <0.7 | 20.0 |
| <0.8 | 14.0 |
| <0.9 | 8.0 |
| <1.0 | 4.0 |
| ≥1.0 | 0.0 |

**BQ2: Volume Dry-Up (25 pts)**
```python
v5 = sma(volume, 5)
v20 = sma(volume, 20)
vd_ratio = v5 / v20
```

| VD Ratio | Score |
|----------|-------|
| <0.5 | 25.0 |
| <0.65 | 20.0 |
| <0.8 | 15.0 |
| <0.95 | 10.0 |
| <1.1 | 5.0 |
| ≥1.1 | 0.0 |

**BQ3: Base Duration (20 pts)** — Uses same 3-mode + DSG-02 latch system as Structure BD, but with 60-bar pivot and 8% band.

```python
pivot = highest(high, 60)
band = pivot * 0.08
in_band = (pivot - close) <= band  # within 8% of 60-bar high
# 3-mode extension: staircase and smooth trend within band also count
in_band_ext = in_band or (mode2 and in_band) or (mode3 and in_band)
```

Same accumulation/latch/decay as Structure BD. Scoring:

| BQ Base Days | Score |
|--------------|-------|
| 10-25 | 20.0 |
| 7-9 | 14.0 |
| 25-35 | 14.0 |
| 5-6 | 8.0 |
| >35 | 8.0 |
| 3-4 | 4.0 |
| <3 | 0.0 |

**BQ4: EMA Convergence (25 pts)**
```python
e8 = ema(close, 8)
e13 = ema(close, 13)
e21 = ema(close, 21)
spread = max(e8, e13, e21) - min(e8, e13, e21)
norm_spread = spread / atr20
```

| Normalised Spread | Score |
|--------------------|-------|
| <0.5 | 25.0 |
| <0.8 | 20.0 |
| <1.2 | 15.0 |
| <1.8 | 10.0 |
| <2.5 | 5.0 |
| ≥2.5 | 0.0 |

### Position Gates (ALL must pass)

| Gate | Threshold |
|------|-----------|
| K39 Weekly Stochastic | >50 AND OBV > OBV SMA(30) |
| Flow | ≥ 40 |
| Energy | ≥ 60 |
| Structure | ≥ 65 |
| MP | ≥ 40 |
| BQ | ≥ 60 |

**NO Elder gate for SC_POSITION** — base-building stocks may have neutral impulse.

```python
# K39 gate (weekly timeframe)
k39 = stochastic(weekly_close, weekly_high, weekly_low, 39)
obv_weekly = obv(weekly)
obv_sma30 = sma(obv_weekly, 30)
k39_gate = (k39 > 50) and (obv_weekly > obv_sma30)

engines_pass_p = (flow_100 >= 40 and energy_100 >= 60 and
                  structure_100 >= 65 and mp_100 >= 40 and bq_100 >= 60)
all_gates_p = engines_pass_p and k39_gate

sc_position = sc_p_raw if all_gates_p else min(sc_p_raw, 49.0)
```

### Dual Qualification

`dual_qual = sc_momentum >= 55 and sc_position >= 55`

A dual-qualified stock satisfies BOTH pipelines simultaneously. DRS (Dual Reference Score) is the reference case.

---

# PART 4 — PTRS & CONTEXT MODIFIER (v1.8)

## PTRS Computation (Alfred, NOT indicator)

`PTRS = Engine Score + Context Modifier`

Engine Score = SC_MOMENTUM (for breakout pipeline) or SC_POSITION (for base pipeline).

## Context Modifier (v1.8): CM = SH + RA + RL

**Three components only.** BR (Base Readiness) was removed in v1.8 to eliminate double-taxation with Structure BD.

### SH: Sector Health

Based on the sector ETF's position relative to its 20-day SMA.

| Condition | SH Value |
|-----------|----------|
| Sector ETF >2% above SMA20 | +3 |
| Above SMA20 | 0 |
| Below SMA20 | -5 |
| Below SMA20 by >5% | -8 |

Under SRM v3.0, SH is the GICS grade for the sector (DEPLOY/HOLD/WATCH/AVOID maps to the scoring tiers).

### RA: Regime Alignment

| Alignment | RA Value |
|-----------|----------|
| ALIGNED (stock's sector matches prevailing macro theme) | +5 |
| NEUTRAL | 0 |
| MISALIGNED (rate-sensitive defensive in stagflation, etc.) | -10 |

### RL: Regime Level (VIX-based)

| VIX Level | Regime | RL Value |
|-----------|--------|----------|
| <18 | GREEN | +2 |
| 18-25 | YELLOW | -3 |
| 25-30 | ORANGE | -5 |
| >30 | RED | HARD STOP (no entries) |

**CM Range:** -23 (SH -8, RA -10, RL -5) to +10 (SH +3, RA +5, RL +2)

## Disposition Bands

| PTRS | Size | Conviction Required |
|------|------|---------------------|
| ≥60 | Full (1.0×) | avg ≥ 6.0 |
| 50-59 | Half (0.5×) | avg ≥ 7.0 |
| 45-49 | Quarter (0.25×) | avg ≥ 7.5 |
| <45 | REJECT | — |

**RED regime = no PTRS evaluation.** All candidates parked.

**YELLOW regime:** Quarter-size maximum on new entries (protocol override).

---

# PART 5 — DYNAMIC STOP LOSS (DSL v1.4)

## Initial Stop Computation

**Tactical profile:**
```python
atr14 = atr(14)
struct_low = lowest(low, 5)
buffered_stop = struct_low - (atr14 * 0.5)
raw_distance = entry_price - buffered_stop
clamped = max(min(raw_distance, atr14 * 2.0), atr14 * 0.75)
initial_stop = entry_price - clamped
```

**Core profile:** Wider buffer (1.5×), wider clamps (1.0-3.0 × ATR).

## DSG-10: R-Tiered Trail System

**The trail WIDENS as the position proves itself.** This is the architectural inversion from v1.3 (which tightened).

| Tier | R-Multiple | Trail Formula | Timeframe |
|------|-----------|---------------|-----------|
| T1 (Prove) | 0-1R | Session low − 1.0 × ATR(14) | Daily |
| T2 (Develop) | 1-2R | Session low − 1.5 × ATR(14) | Daily |
| T3 (Winner) | 2-4R | Weekly low − 2.0 × ATR(14) | Weekly |
| T4 (Runner) | 4R+ | max(WeeklyLow − 2.5×ATR, T1Target − 1×ATR) | Weekly |

**Rules:**
1. Trail ratchets upward only (never lowers)
2. Daily → Weekly at T3 is ONE-WAY (never reverts)
3. Highest tier reached LOCKS (pullback doesn't demote)
4. PM may tighten but never widen beyond tier prescription

**R-based minimum floors:**
- T2+: Trail ≥ entry (breakeven)
- T3+: Trail ≥ entry + 1.5R
- T4+: Trail ≥ entry + 3.0R

**Exit signals:**
- Trail exit: close < trailing_stop
- Impulse exit: RED Elder impulse at Tier 1 ONLY (Tier 2+ is immune — position has earned the right to survive impulse shifts)

---

# PART 6 — PIPELINE RANK v1.0 (SCREENER)

**Purpose:** Batch-screen the entire universe. Produces a single sort key.

`PIPELINE_RANK = Momentum_Composite × 0.70 + FIP_Quality × 0.30`

## Momentum Composite (70%, 0-100)

Five sub-components from daily OHLCV only:

1. **12-Month Return (skip 1 month):** `(close / close[231]) - 1` (252 - 21 = 231 bars)
2. **ADX Trend Strength:** ADX(14) value and DI+ vs DI- direction
3. **RSI Momentum Zone:** RSI(14) position (40-70 = constructive)
4. **Volume Confirmation:** Volume trend vs 20-day average
5. **MA Structure:** above 20/50/150/200 EMA, MA stack alignment, SMA50 direction

## FIP Path Quality (30%, 0-100)

```python
lookback = 252
pct_positive = count(daily_return > 0) / lookback
pct_negative = count(daily_return < 0) / lookback
momentum_sign = sign(cumulative_return_252d)

FIP = (pct_negative - pct_positive) * momentum_sign

# Interpretation:
# FIP < -0.10 → SMOOTH (high quality, institutional)
# FIP -0.10 to 0.00 → MODERATE
# FIP > 0.00 → JUMPY (lottery-like, fragile)

# 5-day spike detection:
max_5 = max(abs(daily_return) for last 5 bars)
if max_5 > 0.08:  # >8% single-day move
    apply -30 penalty to FIP quality score
```

## Classifications

| PIPE_RANK | Tier |
|-----------|------|
| ≥75 | A-TIER (prioritise for committee) |
| 60-74 | B-STRONG (standard pipeline) |
| 45-59 | C-WATCH (park on watchlist) |
| <45 | D-SKIP (do not advance) |

**Zero `request.security` calls.** Full screener compatibility.

---

# PART 7 — DSG-07 OVEREXTENSION FLAG

Diagnostic flag (not a gate, not a penalty). Committee visibility only.

```python
dsg07_flag = (sc_momentum > 85 and
              not sl_tight and  # SL is WIDE
              close > (ema20 + atr20 * 2.0))  # price >2× ATR above EMA20
```

When flagged: the stock scores well but is extended — committee should discuss entry timing, partial position, or waiting for a pullback.

---

# PART 8 — SECTOR ROTATION MONITOR (SRM v3.0)

## Architecture

**Dual-layer:** 11 GICS sector ETFs (floor) + 15 thematic baskets (capped by parent).

**Data source:** FMP `historical-price-eod-light` per constituent.

### GICS Floor ETFs

XLK, XLV, XLF, XLE, XLI, XLY, XLP, XLRE, XLU, XLC, XLB

### Thematic Baskets (12 active)

Clean Energy, Solar, Nuclear, Lithium, Copper, Rare Earth, Oil & Gas, Infra/Power, Cyber, Quantum, Space, Semicon — each with 5-10 constituent tickers.

### Per-Constituent Metrics

```python
roc20 = (close_today - close_20d_ago) / close_20d_ago * 100
roc5 = (close_today - close_5d_ago) / close_5d_ago * 100
above_sma20 = close_today > mean(close_last_20d)
```

### Per-Sector Grading

| Grade | Criteria |
|-------|----------|
| DEPLOY | ≥80% breadth + ROC20 >5% |
| HOLD | ≥60% breadth + positive ROC20 |
| TURNING | <60% breadth but Divergence >0 (5D accelerating vs 20D) |
| WATCH | ≥40% breadth or partial signals |
| AVOID | <40% breadth + negative ROC20 |

### Charter Integration

- **§4B.4 Sector Gate:** GICS grade ≥ HOLD required for any entry or add-on
- **§4B.5 Add-On Recheck:** SRM re-run required before any add-on tranche
- **SH in CM = GICS grade** (maps to the +3/0/-5/-8 scoring above)

---

# PART 9 — CHARTER PROCESS (PROTOCOL FLOW)

## Protocol A: Session Open

1. Dual timestamp [ET] / [SGT] + market status
2. Download session state JSON from Google Drive
3. Stop audit — verify all stops match last confirmed levels
4. Regime check — pull VIX, classify GREEN/YELLOW/ORANGE/RED
5. Run SRM (sector scanner)

## Protocol B: Candidate Qualification

| Step | Gate | Description |
|------|------|-------------|
| B1 | Sourcing | Pipeline Rank screener ≥ 60, sort desc. Top 10-15 advance. |
| B2 | Engine Qual | SC_MOMENTUM ≥ 55 AND all engine floors pass AND Elder ≥ 6.5 |
| B3 | PTRS | Alfred computes: Engine Score + CM (SH + RA + RL). Check disposition band. |
| B4 | Portfolio Risk | Weighted portfolio beta (flag if >2.5). Pairwise correlation. Sector exposure. DSG-09 35% single-thesis cap check. |
| B4a | Pre-Entry Beta | Current + projected beta with new position |
| B5 | R:R Check | R:R ≥ 2:1 against committee-designated target |
| B6 | Deliberation | Committee votes 5/8 majority. Steenbarger inversion mandate at 8/8. |

## Protocol C: Position Management

- Trail management per DSG-10 tier system
- Stop audit at every session open
- MP state monitoring (FADING triggers review)
- Add-on protocol: re-run SRM sector check, re-compute beta

## Protocol D: Session Close

1. Reconcile fills / P&L
2. Update journal (Drive JSON + Sheet append)
3. Run SRM (compare vs open)
4. Record session state

## Protocol E: Weekly Scorecard (D1)

- Weighted portfolio beta (flag drift)
- Cumulative P&L and win rate
- Regime trend review
- SRM full scan with quadrant changes

---

# PART 10 — BACKTESTER IMPLEMENTATION NOTES

## Data Pipeline

```python
# Primary: FMP via MCP
# Endpoint: FMP:chart → historical-price-eod-full
# Fields needed: date, open, high, low, close, volume
# Lookback: 252 bars minimum per ticker
# Benchmark: SPY (always co-pulled)

# For weekly bars: aggregate daily into weekly OHLCV
# Week boundary: Monday-Friday (standard US market week)
```

## State Variables (require persistence across bars)

| Variable | Engine | Description |
|----------|--------|-------------|
| `raw_base_count` | Structure | Consecutive base day counter |
| `latched_bd` | Structure | Latched base days at breakout |
| `bars_since_bo` | Structure | Bars since last breakout |
| `trend_bars` | Energy | Consecutive bars above EMA20 |
| `bq_raw_base` | BQ | BQ base day counter |
| `bq_latched_bd` | BQ | BQ latched base days |
| `bq_bars_since_bo` | BQ | BQ bars since breakout |
| `trailing_stop` | DSL | Ratcheting trail stop |
| `highest_tier` | DSL | Highest R-tier reached |
| `weekly_mode` | DSL | Daily→Weekly transition flag |
| `frozen_risk` | DSL | 1R value frozen at entry |

## Known QA Issues

- **QA-01:** SC_POSITION returning 49.0 universally — gated. K39 weekly gate may be failing due to `request.security` returning NA on weekly data in screener context. **Backtester must verify K39 computation on weekly aggregates.**
- **Screener vs chart delta:** TradingView screener loads fewer bars than chart. Indicators with long lookbacks (252-bar FIP, 60-bar RS) may produce different values. **Backtester is the canonical environment — it processes full bar history.**

## Output Schema (per-bar, per-ticker)

```json
{
  "date": "2026-05-12",
  "ticker": "NNE",
  "flow_100": 72.4,
  "energy_100": 68.1,
  "structure_100": 81.3,
  "mp_100": 64.0,
  "mp_state": 1,
  "elder_score": 8.0,
  "bq_100": 55.0,
  "sc_momentum": 71.2,
  "sc_position": 49.0,
  "sc_m_gates": true,
  "sc_p_gates": false,
  "dual_qual": false,
  "bd_count": 12,
  "bd_mode": 2,
  "atr_comp_ratio": 0.65,
  "dsg07_flag": false,
  "k39_val": 48.3,
  "k39_gate": false,
  "sl_initial_tact": 52.10,
  "sl_initial_core": 50.40,
  "sl_tight": true,
  "rs_vs_spy": 8.4,
  "rs_accel": 3.1,
  "excess_return": 6.7,
  "fip": -0.12,
  "pipe_rank": 74.0,
  "nr7": false,
  "nr4": false,
  "earn_days": 45
}
```

---

# APPENDIX A — SCORING CURVE SUMMARY (All Engines)

| Engine | Raw Max | Normaliser | Scale |
|--------|---------|------------|-------|
| Flow | 38.0 | ÷ 38 × 100 | 0-100 |
| Energy | 59.5 | ÷ 59.5 × 100 | 0-100 |
| Structure | 95.0 | ÷ 95 × 100 | 0-100 |
| MP | 100.0 | none | 0-100 |
| Elder | 10.0 | none | 0-10 |
| BQ | 100.0 | none | 0-100 |

# APPENDIX B — COMPOSITE WEIGHT MATRIX

| Engine | SC_MOMENTUM Weight | SC_POSITION Weight |
|--------|--------------------|--------------------|
| Flow | 30% | 10% |
| Energy | 30% | 30% |
| Structure | 20% | 20% |
| MP | 20% | 5% |
| BQ | — | 35% |

# APPENDIX C — GATE MATRIX

| Gate | SC_MOMENTUM | SC_POSITION |
|------|-------------|-------------|
| Elder ≥ 6.5 | YES | NO |
| Flow floor | 60 | 40 |
| Energy floor | 60 | 60 |
| Structure floor | 55 | 65 |
| MP floor | 55 | 40 |
| BQ floor | — | 60 |
| K39 gate | — | >50 + OBV confirmed |

# APPENDIX D — INDICATOR VERSION REGISTRY

| Indicator | Current Version | Supersedes | Key Change |
|-----------|----------------|------------|------------|
| Scoring | v1.6.0 | v1.5.2, v1.5.3, v1.5.4 | 3-mode BD, DSG-07, ATR compression |
| Structure | v1.5.0 | v1.4.2, v1.4.3 | 3-mode BD aligned to Scoring |
| Energy | v1.3.1 | v1.3.0 | DSG-05 VP proxy fix |
| Flow | v1.3 | — | Canonical |
| MP | v1.2 | v1.1 | State-based colouring |
| Elder | v1 | — | Canonical |
| DSL | v1.4 | v1.3 | DSG-10 R-tiered trail (widening) |
| Pipeline Rank | v1.0 | Standalone FIP v1.0 | Combined screener indicator |

**DUPLICATE INDICATOR WARNING:** Before any deployment or review, verify that only ONE version of each indicator is loaded on TradingView. Re-versioning creates duplicates. The version listed here is canonical.

---

*Document generated by Alfred (Scrum Master) | AIC Charter v1.8 authority*
*For backtesting engine development — all formulas verified against Pine source code*
