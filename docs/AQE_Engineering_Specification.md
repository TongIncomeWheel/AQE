# AEGIS QUANT ENGINE (AQE) — ENGINEERING SPECIFICATION
## v0.1 Draft | 18 May 2026

**Objective:** Strip TradingView dependency. Compute all Aegis indicators locally from FMP OHLCV data. Produce a daily scored shortlist for committee deliberation. TradingView retained ONLY as PM illustrative/charting tool — zero computational authority.

**Architecture:** Python application, daily batch execution. FMP via MCP for data. Local computation of all engines. Output: scored candidates → committee → PM decision.

**Charter Authority:** AIC v1.8. Indicator Spec: Aegis Design Committee Specification v1.0.

---

# 1 — SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                    AEGIS QUANT ENGINE (AQE)                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────────┐     ┌────────────┐  │
│  │  DATA LAYER  │────▶│  COMPUTE LAYER   │────▶│  OUTPUT    │  │
│  │              │     │                  │     │  LAYER     │  │
│  │  FMP MCP     │     │  Engine modules  │     │            │  │
│  │  (Starter)   │     │  per Design Spec │     │  JSON      │  │
│  │              │     │                  │     │  Dashboard │  │
│  │  • Universe  │     │  • Flow v1.3     │     │  Shortlist │  │
│  │  • OHLCV     │     │  • Energy v1.3.1 │     │  CSV       │  │
│  │  • Earnings  │     │  • Structure 1.5 │     │  Drive     │  │
│  │  • Quotes    │     │  • MP v1.2       │     │            │  │
│  │  • SRM ETFs  │     │  • Elder v1      │     │            │  │
│  │              │     │  • BQ            │     │            │  │
│  └──────────────┘     │  • Pipeline Rank │     └────────────┘  │
│                       │  • DSL v1.4      │                     │
│                       │  • SRM v3.0      │                     │
│                       │  • PTRS (CM)     │                     │
│                       └──────────────────┘                     │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    ORCHESTRATOR                           │  │
│  │  Daily schedule → Universe refresh → Bar pull → Compute  │  │
│  │  → Score → Rank → Filter → SRM overlay → PTRS → Output  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    STATE STORE                            │  │
│  │  SQLite: universe cache, daily bars, computed scores,     │  │
│  │  persistent counters (base days, trend bars, latches)     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

        │                                          │
        ▼                                          ▼
  ┌───────────┐                           ┌──────────────────┐
  │  ALFRED   │  ← Shortlist JSON         │  TRADINGVIEW     │
  │  (Claude) │  ← Committee input        │  (PM Only)       │
  │           │                           │  Illustrative    │
  │  Qualit-  │                           │  charting,       │
  │  ative    │                           │  visual confirm  │
  │  deliber- │                           │  No computation  │
  │  ation    │                           │  authority       │
  └───────────┘                           └──────────────────┘
```

---

# 2 — DATA LAYER

## 2.1 Universe Generation

**Source:** `FMP:search → search-company-screener`

**Filters (daily refresh or weekly, PM configurable):**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `exchange` | NASDAQ, NYSE | US equities only |
| `marketCapMoreThan` | 1,000,000,000 | >$1B mcap (liquid names) |
| `priceMoreThan` | 5.00 | Avoid penny stocks |
| `isActivelyTrading` | true | Exclude halted/delisted |
| `isEtf` | false | Equities only |
| `isFund` | false | No mutual funds |
| `volumeMoreThan` | 500,000 | Minimum daily avg volume |
| `limit` | 5000 | Capture full filtered universe |

**Output:** ~800-1500 tickers. Stored in `universe` table.

**Refresh cadence:** Weekly (Sunday). Universe changes slowly. Saves API calls.

**FMP Starter plan constraint:** Rate limits apply. Universe pull = 1 API call (screener endpoint returns paginated results). Budget-friendly.

## 2.2 Historical OHLCV Pull

**Source:** `FMP:chart → historical-price-eod-full`

**Per ticker:** 252 trading days (1 year lookback). Fields: date, open, high, low, close, adjClose, volume.

**SPY co-pull:** Always. Required by Structure (RS), MP (relative), Elder reference.

**Rate limit strategy (FMP Starter = ~300 calls/day on Starter, varies by plan):**

| Phase | Tickers | Calls | Strategy |
|-------|---------|-------|----------|
| Universe OHLCV (initial) | ~1000 | ~1000 | Batch over 3-4 days at first load |
| Daily incremental | ~1000 | ~1000 | Pull only latest bar (append to local DB) |
| Shortlist deep pull | ~50 | ~50 | Full 252-bar refresh for scored candidates |

**CRITICAL OPTIMISATION:** After initial seed, only pull the LATEST bar daily via `from_date=yesterday`. Append to local SQLite. Full 252-bar re-pull only for: (a) new tickers entering universe, (b) weekly integrity check on top-50 ranked names.

```python
# Incremental daily pull
for ticker in universe:
    bars = fmp_chart(symbol=ticker, 
                     endpoint="historical-price-eod-full",
                     from_date=last_pull_date,
                     to_date=today)
    db.append_bars(ticker, bars)
```

**Weekly bar aggregation:** Computed locally from daily bars. No separate FMP call.

```python
def aggregate_weekly(daily_bars):
    """Group daily bars into Monday-Friday weeks."""
    weeks = group_by_iso_week(daily_bars)
    return [{
        "date": week[-1]["date"],  # Friday close
        "open": week[0]["open"],
        "high": max(b["high"] for b in week),
        "low": min(b["low"] for b in week),
        "close": week[-1]["close"],
        "volume": sum(b["volume"] for b in week)
    } for week in weeks]
```

## 2.3 Earnings Calendar

**Source:** `FMP:calendar → earnings-company`

**Pull:** Per ticker, returns next earnings date.

**Cadence:** Weekly refresh for universe. Daily check for shortlist names.

**Structure engine needs:** `days_to_earnings = (next_earnings_date - today).days`

## 2.4 Live Quotes (Session Use)

**Source:** `FMP:quote → batch-quote`

**When:** During market hours for portfolio positions and active candidates. Up to 100 tickers per batch call.

## 2.5 SRM Sector Data

**Source:** `FMP:chart → historical-price-eod-light` (close + volume only, lower token cost)

**Tickers:** 11 GICS ETFs + constituent tickers per thematic basket (~100 tickers total).

**Cadence:** Daily (part of the daily batch).

---

# 3 — STATE STORE (SQLite)

## Schema

```sql
-- Universe registry
CREATE TABLE universe (
    ticker TEXT PRIMARY KEY,
    name TEXT,
    sector TEXT,
    industry TEXT,
    market_cap REAL,
    exchange TEXT,
    last_refreshed DATE
);

-- Daily OHLCV bars (append-only, the core asset)
CREATE TABLE daily_bars (
    ticker TEXT,
    date DATE,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    adj_close REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, date)
);

-- Weekly bars (computed from daily, refreshed weekly)
CREATE TABLE weekly_bars (
    ticker TEXT,
    week_end DATE,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, week_end)
);

-- Persistent state counters (engines need bar-over-bar state)
CREATE TABLE engine_state (
    ticker TEXT PRIMARY KEY,
    -- Structure BD state
    raw_base_count INTEGER DEFAULT 0,
    latched_bd INTEGER DEFAULT 0,
    bars_since_bo INTEGER DEFAULT 999,
    -- Energy exhaustion state
    trend_bars INTEGER DEFAULT 0,
    -- BQ state
    bq_raw_base INTEGER DEFAULT 0,
    bq_latched_bd INTEGER DEFAULT 0,
    bq_bars_since_bo INTEGER DEFAULT 999,
    -- Last computed date
    last_computed DATE
);

-- Computed scores (daily output)
CREATE TABLE scores (
    ticker TEXT,
    date DATE,
    flow_100 REAL,
    energy_100 REAL,
    structure_100 REAL,
    mp_100 REAL,
    mp_state INTEGER,
    elder_score REAL,
    bq_100 REAL,
    sc_momentum REAL,
    sc_position REAL,
    sc_m_gates BOOLEAN,
    sc_p_gates BOOLEAN,
    dual_qual BOOLEAN,
    bd_count INTEGER,
    bd_mode INTEGER,
    atr_comp_ratio REAL,
    dsg07_flag BOOLEAN,
    k39_val REAL,
    k39_gate BOOLEAN,
    rs_vs_spy REAL,
    rs_accel REAL,
    excess_return REAL,
    fip REAL,
    pipe_rank REAL,
    nr7 BOOLEAN,
    nr4 BOOLEAN,
    earn_days INTEGER,
    sl_initial_tact REAL,
    sl_initial_core REAL,
    PRIMARY KEY (ticker, date)
);

-- Earnings calendar
CREATE TABLE earnings (
    ticker TEXT PRIMARY KEY,
    next_earnings_date DATE,
    last_refreshed DATE
);

-- SRM sector scores
CREATE TABLE srm_scores (
    sector TEXT,
    date DATE,
    grade TEXT,
    breadth_pct REAL,
    avg_roc20 REAL,
    avg_roc5 REAL,
    divergence REAL,
    PRIMARY KEY (sector, date)
);

-- Index for fast retrieval
CREATE INDEX idx_bars_ticker_date ON daily_bars(ticker, date DESC);
CREATE INDEX idx_scores_date ON scores(date DESC);
CREATE INDEX idx_scores_rank ON scores(date, pipe_rank DESC);
```

**Why SQLite:** Single-file, zero-config, handles millions of rows. A year of daily bars for 1000 tickers = ~252,000 rows. Trivial for SQLite. No server needed. Portable. Backs up by copying one file.

---

# 4 — COMPUTE LAYER

## 4.1 Module Architecture

```
aegis_quant_engine/
├── main.py                    # Orchestrator / CLI
├── config.py                  # Thresholds, weights, FMP keys
├── data/
│   ├── fmp_client.py          # FMP MCP wrapper
│   ├── universe.py            # Universe generation + refresh
│   ├── bars.py                # OHLCV pull, incremental append
│   ├── earnings.py            # Earnings calendar
│   └── db.py                  # SQLite abstraction
├── engines/
│   ├── common.py              # Shared TA functions (ema, sma, atr, rsi, etc.)
│   ├── flow.py                # Engine 1: Flow v1.3
│   ├── energy.py              # Engine 2: Energy v1.3.1
│   ├── structure.py           # Engine 3: Structure v1.5.0
│   ├── mp.py                  # Engine 4: Momentum Persistence v1.2
│   ├── elder.py               # Engine 5: Elder Impulse Score v1
│   ├── bq.py                  # Base Quality sub-engine
│   ├── pipeline_rank.py       # Stage 1: Pipeline Rank v1.0
│   ├── dsl.py                 # Dynamic Stop Loss v1.4
│   └── scorer.py              # Composites: SC_MOMENTUM, SC_POSITION
├── context/
│   ├── srm.py                 # Sector Rotation Monitor v3.0
│   ├── ptrs.py                # PTRS = Engine Score + CM
│   └── regime.py              # VIX regime classification
├── output/
│   ├── shortlist.py           # Filter, rank, format shortlist
│   ├── dashboard.py           # Summary dashboard
│   ├── drive_sync.py          # Push to Google Drive
│   └── csv_export.py          # CSV for external consumption
├── backtest/
│   ├── engine.py              # Event-loop backtester (Phase 2)
│   ├── portfolio.py           # Position sizing, beta, VaR
│   └── analytics.py           # Performance metrics
└── tests/
    ├── test_common.py
    ├── test_flow.py
    ├── test_energy.py
    ├── test_structure.py
    ├── test_mp.py
    ├── test_elder.py
    └── fixtures/               # Reference OHLCV data for validation
```

## 4.2 Common TA Library (`engines/common.py`)

Every indicator in the Aegis stack reduces to these base functions:

```python
import numpy as np
from typing import Optional

def sma(data: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    result = np.full_like(data, np.nan)
    for i in range(period - 1, len(data)):
        result[i] = np.mean(data[i - period + 1 : i + 1])
    return result

def ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average (standard k = 2/(period+1))."""
    result = np.full_like(data, np.nan)
    k = 2.0 / (period + 1)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = data[i] * k + result[i - 1] * (1 - k)
    return result

def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
        period: int = 14) -> np.ndarray:
    """Average True Range (Wilder smoothing)."""
    tr = np.maximum(
        high - low,
        np.maximum(
            np.abs(high - np.roll(close, 1)),
            np.abs(low - np.roll(close, 1))
        )
    )
    tr[0] = high[0] - low[0]
    return wilder_smooth(tr, period)

def wilder_smooth(data: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothing method (used by ATR, RSI, ADX)."""
    result = np.full_like(data, np.nan)
    result[period - 1] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = (result[i - 1] * (period - 1) + data[i]) / period
    return result

def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """RSI (Wilder method)."""
    delta = np.diff(close, prepend=close[0])
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    avg_gain = wilder_smooth(gains, period)
    avg_loss = wilder_smooth(losses, period)
    rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100.0)
    return 100.0 - (100.0 / (1.0 + rs))

def macd(close: np.ndarray, fast: int = 12, slow: int = 26, 
         signal: int = 9):
    """MACD line, signal, histogram."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def dmi(high: np.ndarray, low: np.ndarray, close: np.ndarray, 
        period: int = 14):
    """Directional Movement Index → DI+, DI-, ADX."""
    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    atr_vals = atr(high, low, close, period)
    smooth_plus = wilder_smooth(np.insert(plus_dm, 0, 0), period)
    smooth_minus = wilder_smooth(np.insert(minus_dm, 0, 0), period)
    
    di_plus = np.where(atr_vals != 0, 100 * smooth_plus / atr_vals, 0)
    di_minus = np.where(atr_vals != 0, 100 * smooth_minus / atr_vals, 0)
    
    dx = np.where(
        (di_plus + di_minus) != 0,
        100 * np.abs(di_plus - di_minus) / (di_plus + di_minus),
        0
    )
    adx = wilder_smooth(dx, period)
    return di_plus, di_minus, adx

def stochastic(close: np.ndarray, high: np.ndarray, low: np.ndarray, 
               period: int) -> np.ndarray:
    """Stochastic %K (raw, unsmoothed)."""
    result = np.full_like(close, np.nan)
    for i in range(period - 1, len(close)):
        hh = np.max(high[i - period + 1 : i + 1])
        ll = np.min(low[i - period + 1 : i + 1])
        result[i] = (close[i] - ll) / (hh - ll) * 100 if (hh - ll) != 0 else 50
    return result

def linreg_slope(data: np.ndarray, period: int) -> np.ndarray:
    """Linear regression slope over rolling window."""
    result = np.full_like(data, np.nan)
    x = np.arange(period)
    for i in range(period - 1, len(data)):
        y = data[i - period + 1 : i + 1]
        if np.any(np.isnan(y)):
            continue
        slope = np.polyfit(x, y, 1)[0]
        result[i] = slope
    return result

def highest(data: np.ndarray, period: int) -> np.ndarray:
    """Rolling highest value."""
    result = np.full_like(data, np.nan)
    for i in range(period - 1, len(data)):
        result[i] = np.max(data[i - period + 1 : i + 1])
    return result

def lowest(data: np.ndarray, period: int) -> np.ndarray:
    """Rolling lowest value."""
    result = np.full_like(data, np.nan)
    for i in range(period - 1, len(data)):
        result[i] = np.min(data[i - period + 1 : i + 1])
    return result

def rate_of_change(data: np.ndarray, period: int) -> np.ndarray:
    """ROC = (current - N bars ago) / N bars ago * 100."""
    result = np.full_like(data, np.nan)
    for i in range(period, len(data)):
        if data[i - period] != 0:
            result[i] = (data[i] - data[i - period]) / data[i - period] * 100
    return result

def obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """On-Balance Volume."""
    result = np.zeros_like(close)
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            result[i] = result[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            result[i] = result[i - 1] - volume[i]
        else:
            result[i] = result[i - 1]
    return result

def mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray,
        volume: np.ndarray, period: int = 14) -> np.ndarray:
    """Money Flow Index."""
    tp = (high + low + close) / 3
    mf = tp * volume
    result = np.full_like(close, np.nan)
    for i in range(period, len(close)):
        pos = sum(mf[j] for j in range(i - period + 1, i + 1) if tp[j] > tp[j - 1])
        neg = sum(mf[j] for j in range(i - period + 1, i + 1) if tp[j] <= tp[j - 1])
        result[i] = 100 - (100 / (1 + pos / neg)) if neg != 0 else 100
    return result
```

## 4.3 Engine Module Pattern

Each engine follows the same interface:

```python
# engines/flow.py
import numpy as np
from engines.common import *
from dataclasses import dataclass

@dataclass
class FlowResult:
    """Flow v1.3 output."""
    flow_100: float
    institutional: float
    accumulation: float
    volume_trend: float
    skew: float
    extension: float
    raw: float

def compute_flow(ohlcv: dict, bar_index: int = -1) -> FlowResult:
    """
    Compute Flow v1.3 for a single bar.
    
    ohlcv: dict with keys 'open', 'high', 'low', 'close', 'volume'
           each a numpy array, sorted ascending by date.
    bar_index: which bar to compute for (-1 = latest).
    
    Returns FlowResult with all components.
    """
    o, h, l, c, v = ohlcv['open'], ohlcv['high'], ohlcv['low'], ohlcv['close'], ohlcv['volume']
    i = bar_index if bar_index >= 0 else len(c) - 1
    
    # Component 1A: MFI + CMF + HA
    # ... (implement per Design Spec Part 2, Engine 1)
    
    # Component 1B: Accumulation
    # ...
    
    # Component 1C: Volume Trend
    # ...
    
    # Component 1D: Volume Skew
    # ...
    
    # Component 1E: Extension
    # ...
    
    raw = max(min(institutional + accumulation + vol_trend + skew + ext, 38), 0)
    flow_100 = raw / 38.0 * 100.0
    
    return FlowResult(
        flow_100=flow_100,
        institutional=institutional,
        accumulation=accumulation,
        volume_trend=vol_trend,
        skew=skew,
        extension=ext,
        raw=raw
    )
```

**Every engine module returns a typed dataclass.** The scorer module consumes these.

## 4.4 Scorer Module (`engines/scorer.py`)

```python
@dataclass
class ScoringResult:
    """Complete scoring output for one ticker on one date."""
    # Composites
    sc_momentum: float
    sc_position: float
    sc_m_gates: bool
    sc_p_gates: bool
    dual_qual: bool
    
    # Engine scores
    flow: FlowResult
    energy: EnergyResult
    structure: StructureResult
    mp: MPResult
    elder: ElderResult
    bq: BQResult
    
    # Pipeline Rank
    pipe_rank: float
    fip: float
    
    # Diagnostics
    bd_count: int
    bd_mode: int
    atr_comp_ratio: float
    dsg07_flag: bool
    k39_val: float
    k39_gate: bool
    earn_days: int
    nr7: bool
    nr4: bool
    
    # Stop levels
    sl_initial_tact: float
    sl_initial_core: float

def score_ticker(ticker: str, daily_bars: dict, weekly_bars: dict,
                 spy_bars: dict, state: EngineState,
                 earnings_date: Optional[date] = None) -> ScoringResult:
    """
    Full scoring computation for one ticker.
    
    This is the equivalent of loading Scoring v1.6.0 on a TV chart.
    Computes all 5 engines + BQ + composites + gates.
    Updates persistent state (base day counters, trend bars).
    """
    flow = compute_flow(daily_bars)
    energy = compute_energy(daily_bars)
    structure = compute_structure(daily_bars, spy_bars, weekly_bars, state)
    mp = compute_mp(daily_bars, spy_bars)
    elder = compute_elder(daily_bars)
    bq = compute_bq(daily_bars, weekly_bars, state)
    
    # SC_MOMENTUM composite
    sc_m_raw = (flow.flow_100 * 0.30 + energy.energy_100 * 0.30 +
                structure.structure_100 * 0.20 + mp.mp_100 * 0.20)
    
    elder_passes = elder.elder_score >= 6.5
    engines_m = (flow.flow_100 >= 60 and energy.energy_100 >= 60 and
                 structure.structure_100 >= 55 and mp.mp_100 >= 55)
    sc_m_gates = elder_passes and engines_m
    sc_momentum = sc_m_raw if sc_m_gates else min(sc_m_raw, 49.0)
    
    # SC_POSITION composite
    sc_p_raw = (flow.flow_100 * 0.10 + energy.energy_100 * 0.30 +
                structure.structure_100 * 0.20 + mp.mp_100 * 0.05 +
                bq.bq_100 * 0.35)
    
    engines_p = (flow.flow_100 >= 40 and energy.energy_100 >= 60 and
                 structure.structure_100 >= 65 and mp.mp_100 >= 40 and
                 bq.bq_100 >= 60)
    sc_p_gates = engines_p and bq.k39_gate
    sc_position = sc_p_raw if sc_p_gates else min(sc_p_raw, 49.0)
    
    # ... assemble full ScoringResult
```

---

# 5 — ORCHESTRATOR (DAILY PIPELINE)

## 5.1 Daily Execution Flow

```python
def daily_run(date: date):
    """
    Full daily pipeline. Designed to run post-market close.
    SGT ~6:30 AM (after US 4 PM ET close + 30 min settlement).
    """
    
    # ── PHASE 1: DATA ─────────────────────────────────
    log.info(f"AQE daily run: {date}")
    
    # 1a. Pull latest daily bar for all universe tickers
    universe = db.get_universe()
    new_bars = fmp.pull_incremental_bars(universe, date)
    db.append_bars(new_bars)
    
    # 1b. Pull SPY bar (always)
    spy_bar = fmp.pull_incremental_bars(["SPY"], date)
    db.append_bars(spy_bar)
    
    # 1c. Pull SRM sector ETF bars
    srm_bars = fmp.pull_incremental_bars(SRM_TICKERS, date)
    db.append_bars(srm_bars)
    
    # 1d. Refresh earnings calendar (weekly or if stale)
    if is_weekly_refresh_day(date):
        earnings.refresh_earnings_calendar(universe)
    
    # ── PHASE 2: STAGE 1 SCREENING ───────────────────
    # Compute Pipeline Rank for full universe (fast — daily bars only)
    stage1_scores = {}
    for ticker in universe:
        bars = db.get_bars(ticker, lookback=252)
        if len(bars) < 60:  # minimum viable history
            continue
        pr = compute_pipeline_rank(bars)
        stage1_scores[ticker] = pr
    
    # Filter: PIPE_RANK ≥ 60, sort descending
    shortlist = sorted(
        [(t, s) for t, s in stage1_scores.items() if s.pipe_rank >= 60],
        key=lambda x: x[1].pipe_rank, reverse=True
    )[:50]  # top 50 for Stage 2
    
    # ── PHASE 3: STAGE 2 FULL SCORING ────────────────
    spy_bars = db.get_bars("SPY", lookback=252)
    scored = []
    
    for ticker, pr in shortlist:
        daily = db.get_bars(ticker, lookback=252)
        weekly = aggregate_weekly(daily)
        state = db.get_engine_state(ticker)
        earn_date = db.get_next_earnings(ticker)
        
        result = score_ticker(ticker, daily, weekly, spy_bars, 
                              state, earn_date)
        
        # Persist updated state
        db.save_engine_state(ticker, state)
        db.save_score(ticker, date, result)
        scored.append((ticker, result))
    
    # ── PHASE 4: SRM OVERLAY ─────────────────────────
    srm_results = srm.compute_all_sectors(date)
    db.save_srm(date, srm_results)
    
    # ── PHASE 5: PTRS COMPUTATION ────────────────────
    vix = fmp.get_vix_close(date)
    regime = classify_regime(vix)
    
    ptrs_results = []
    for ticker, result in scored:
        sector_etf = map_ticker_to_gics_etf(ticker)
        sh = compute_sector_health(sector_etf, srm_results)
        ra = compute_regime_alignment(ticker, regime)
        rl = compute_regime_level(vix)
        cm = sh + ra + rl
        
        ptrs = result.sc_momentum + cm  # or sc_position for base pipeline
        disposition = classify_disposition(ptrs, regime)
        
        ptrs_results.append({
            "ticker": ticker,
            "pipe_rank": stage1_scores[ticker].pipe_rank,
            "sc_momentum": result.sc_momentum,
            "sc_position": result.sc_position,
            "ptrs": ptrs,
            "disposition": disposition,
            "cm": cm,
            "sh": sh, "ra": ra, "rl": rl,
            **result.to_dict()
        })
    
    # ── PHASE 6: OUTPUT ──────────────────────────────
    # Filter to committee-ready candidates
    committee_list = [r for r in ptrs_results 
                      if r["disposition"] != "REJECT"
                      and r["sc_m_gates"]]
    
    # Sort by PTRS descending
    committee_list.sort(key=lambda x: x["ptrs"], reverse=True)
    
    # Output
    output.write_shortlist_json(date, committee_list)
    output.write_dashboard(date, committee_list, srm_results, regime)
    output.sync_to_drive(date)
    
    log.info(f"AQE complete: {len(committee_list)} candidates for committee")
```

## 5.2 Execution Schedule

| Time (SGT) | Time (ET) | Action |
|------------|-----------|--------|
| 06:00 | 18:00 (prev) | Cron trigger: `daily_run()` |
| 06:01 | — | Phase 1: Incremental bar pull (~1000 tickers) |
| 06:15 | — | Phase 2: Pipeline Rank screening (~1000 tickers) |
| 06:25 | — | Phase 3: Full scoring (top 50) |
| 06:35 | — | Phase 4-5: SRM + PTRS |
| 06:40 | — | Phase 6: Output → Drive → Alfred notification |
| 08:00 | — | PM reviews shortlist over morning coffee |
| 22:00 | 10:00 | Pre-market: Alfred + PM committee deliberation on candidates |
| 22:30 | 10:30 | Bracket orders placed on IBKR |

**The PM wakes up to a ranked, scored, SRM-overlaid shortlist every morning. Zero TV interaction required until qualitative chart review.**

---

# 6 — OUTPUT LAYER

## 6.1 Shortlist JSON (Primary Output)

```json
{
  "date": "2026-05-16",
  "regime": "YELLOW",
  "vix": 19.2,
  "max_new_size": "QUARTER",
  "candidates": [
    {
      "rank": 1,
      "ticker": "NNE",
      "pipe_rank": 82,
      "sc_momentum": 71.4,
      "sc_position": 49.0,
      "sc_m_gates": true,
      "sc_p_gates": false,
      "ptrs": 74,
      "disposition": "FULL",
      "cm": { "sh": 0, "ra": 5, "rl": -3, "total": 2 },
      "engines": {
        "flow": 68, "energy": 72, "structure": 79, "mp": 64, "elder": 8.0
      },
      "diagnostics": {
        "bd_count": 14, "bd_mode": "STAIR", "atr_comp": 0.62,
        "dsg07": false, "mp_state": "BUILDING", "earn_days": 38,
        "nr7": false, "rs_vs_spy": 12.3, "fip": -0.14
      },
      "stops": { "tact": 52.10, "core": 50.40 },
      "srm_sector": { "name": "Nuclear", "grade": "DEPLOY" }
    }
  ],
  "srm_summary": {
    "DEPLOY": ["Nuclear", "Copper"],
    "HOLD": ["Oil & Gas", "Semicon"],
    "TURNING": ["Infra/Power"],
    "WATCH": ["Cyber"],
    "AVOID": ["Solar", "Lithium"]
  }
}
```

## 6.2 Dashboard (Daily Summary)

Text-based dashboard pushed to Google Drive and formatted for Alfred consumption:

```
═══════════════════════════════════════════════════════════════
AEGIS QUANT ENGINE — DAILY SCORECARD | 16 May 2026
Regime: YELLOW (VIX 19.2) | New Entry Max: QUARTER
═══════════════════════════════════════════════════════════════

SHORTLIST (SC_M qualified, PTRS non-REJECT, sorted by PTRS)
──────────────────────────────────────────────────────────────
#  Ticker  PIPE  SC_M  PTRS  Disp   Flow Enrg Strc  MP  Eldr  BD     SRM
1  NNE      82   71.4   74   FULL    68   72   79   64   8.0  14 STR  DEPLOY
2  TECK     77   66.2   69   FULL    62   70   74   58   7.0   8 VCP  DEPLOY
3  PLUG     74   63.8   61   FULL    70   65   60   60   7.5   0 ---  HOLD
4  SMR      71   59.1   56   HALF    55   62   68   52   6.5  22 VCP  DEPLOY
5  CCJ      69   57.3   54   HALF    58   60   62   49   7.0   5 STR  DEPLOY

GATED (engine score exists but gates failed — monitor)
──────────────────────────────────────────────────────────────
   FSLR     66   49.0*  —    GATED   72   58   55   61  *5.0  0 ---  AVOID
   IONQ     62   49.0*  —    GATED   48*  64   58   70   7.0  0 ---  WATCH

SRM SNAPSHOT
──────────────────────────────────────────────────────────────
DEPLOY:  Nuclear(85% ↑8.2), Copper(72% ↑5.1)
HOLD:    Oil&Gas(65% ↑2.3), Semicon(62% ↑1.8)
TURNING: Infra/Power(45% ↑3.2 accel)
WATCH:   Cyber(42% -1.1)
AVOID:   Solar(28% -6.4), Lithium(30% -4.2)

═══════════════════════════════════════════════════════════════
```

## 6.3 Google Drive Sync

- Shortlist JSON → `Trading Strategy/aqe_shortlist_YYYY-MM-DD.json`
- Dashboard text → `Trading Strategy/aqe_dashboard_YYYY-MM-DD.txt`
- Scores CSV (full 50-ticker detail) → `Trading Strategy/aqe_scores_YYYY-MM-DD.csv`

---

# 7 — VALIDATION STRATEGY

## 7.1 TV Cross-Validation (Phase 1)

Before trusting AQE output, validate against TradingView for reference tickers.

**Method:**
1. Select 10 tickers spanning score ranges (high/mid/low/gated)
2. Load Scoring v1.6.0 on each in TV
3. Record all engine scores from TV dashboard
4. Run same tickers through AQE
5. Compare: tolerance ±2 points per engine, ±3 points on composite

**Known delta sources:**
- TV screener loads fewer bars → long-lookback indicators (252-bar FIP, 60-bar RS) may differ
- Weekly `request.security` in TV uses lookahead_on → weekly bars align to bar boundaries differently
- Earnings date source: TV uses internal earnings DB; AQE uses FMP calendar
- All deltas must be documented and explained. AQE becomes canonical once validated.

## 7.2 Historical Backtest Validation (Phase 2)

Run AQE on historical data for known reference trades:
- **JBL:** +5.66R peak. Verify DSG-10 trail tier transitions.
- **VRT:** +1.72R peak. Verify Structure BD latch + decay.
- **DOW/CLMT:** Should produce BD=0, PTRS reject. Verify gate enforcement.
- **LNTH/VTR/KR:** Should flag MISALIGNED regime. Verify RA = -10.

---

# 8 — RATE LIMIT BUDGET (FMP Starter)

## Daily Operational Budget

| Operation | Tickers | Calls/Day | Notes |
|-----------|---------|-----------|-------|
| Incremental bar pull | ~1000 | ~1000 | 1 call per ticker (latest bar) |
| SPY + sector ETFs | 12 | 12 | Always pulled |
| SRM constituents | ~100 | ~100 | Light endpoint |
| Earnings refresh | ~50 | ~50 | Shortlist only (weekly for full) |
| VIX quote | 1 | 1 | Single quote |
| Batch quotes (session) | ~20 | 5 | Batch endpoint, 20 per call |
| **Daily total** | — | **~1,170** | |

**FMP Starter plan:** 250 API calls/day. **This is a constraint.**

## Mitigation Strategy

| Strategy | Savings | Implementation |
|----------|---------|----------------|
| Universe light endpoint | ~50% tokens | Use `historical-price-eod-light` for Pipeline Rank (close+vol only) |
| Batch quotes | 4× | `batch-quote` handles 100 tickers per call |
| Tiered pull | ~70% | Only pull full OHLCV for top-50 Stage 2 candidates |
| Local weekly aggregation | 100% | Zero FMP calls for weekly bars |
| Cache universe | ~90% | Weekly refresh, not daily |
| Incremental bars | ~90% | Only 1 bar per ticker per day after seed |

**Revised budget with mitigations:**

| Operation | Calls/Day |
|-----------|-----------|
| Top-50 incremental bars (full OHLCV) | 50 |
| Universe light bars (close only) | Split across 4 days (~250/day) |
| SRM light bars | 25 (batch or light) |
| SPY + sector ETFs | 12 |
| Earnings (weekly ÷ 5) | 10 |
| VIX + batch quotes | 5 |
| **Revised daily total** | **~150** ← within Starter |

**Key insight:** The full universe doesn't need full OHLCV daily. Pipeline Rank only needs close + volume (light endpoint). Only the top-50 shortlist candidates need full OHLCV for the 5-engine scoring suite. This drops daily calls from 1,170 to ~150.

**Plan upgrade path:** FMP Professional ($79/mo) raises to 750 calls/day. Removes the tiered-pull constraint entirely. Recommended once AQE is validated.

---

# 9 — IMPLEMENTATION ROADMAP

## Phase 1: Foundation (Weeks 1-2)

| Deliverable | Description |
|-------------|-------------|
| `common.py` | Full TA library with unit tests |
| `db.py` | SQLite schema + CRUD operations |
| `fmp_client.py` | FMP MCP wrapper with rate limiting |
| `universe.py` | Universe generation + caching |
| `bars.py` | Incremental bar pull + append |
| Data seed | Initial 252-bar load for top-200 tickers |

**Exit criteria:** Can pull bars, store, retrieve. TA functions pass unit tests against known values.

## Phase 2: Engine Modules (Weeks 3-5)

| Deliverable | Description |
|-------------|-------------|
| `flow.py` | Flow v1.3 — all 5 components |
| `energy.py` | Energy v1.3.1 — VP proxy + 4 components |
| `structure.py` | Structure v1.5.0 — 3-mode BD + latch + 7 components |
| `mp.py` | MP v1.2 — 4 components + state machine |
| `elder.py` | Elder v1 — 3 components |
| `bq.py` | Base Quality — 4 sub-components + K39 gate |
| `pipeline_rank.py` | Pipeline Rank v1.0 — momentum + FIP |
| `scorer.py` | Composites + gates + diagnostics |

**Exit criteria:** 10-ticker TV cross-validation passes within tolerance (±2 engine, ±3 composite).

## Phase 3: Pipeline Integration (Weeks 6-7)

| Deliverable | Description |
|-------------|-------------|
| `srm.py` | SRM v3.0 dual-layer |
| `ptrs.py` | PTRS = Engine + CM |
| `regime.py` | VIX classification |
| `main.py` | Orchestrator with daily pipeline |
| `shortlist.py` | Output formatting |
| `drive_sync.py` | Google Drive push |

**Exit criteria:** End-to-end daily run produces committee-ready shortlist. PM validates against live TV assessment for 5 consecutive sessions.

## Phase 4: Backtester (Weeks 8-12)

| Deliverable | Description |
|-------------|-------------|
| `backtest/engine.py` | Event-loop backtester |
| `backtest/portfolio.py` | Position sizing, DSL trails, beta |
| `backtest/analytics.py` | Sharpe, Sortino, max DD, win rate, R-distribution |
| Historical validation | Reference trades (JBL, VRT, DOW/CLMT) |
| Parameter sensitivity | Engine weight / gate threshold analysis |

**Exit criteria:** Backtest reproduces known trade outcomes. Performance metrics are stable across parameter perturbation.

## Phase 5: Full Autonomy (Weeks 13+)

| Deliverable | Description |
|-------------|-------------|
| TV decommission | Remove all computational reliance on TV |
| TV retained as | PM visual confirmation tool only |
| AQE dashboard | Daily push to Alfred for committee orchestration |
| Continuous improvement | Engine calibration per Charter §11 schedule |

---

# 10 — WHAT THIS CHANGES FOR THE PROCESS

## Before (TV-dependent)

```
PM manually scans TV screener → eyeballs Pipeline Rank → 
opens individual charts → reads dashboard tables → 
mentally computes PTRS → asks Alfred to run committee → 
Alfred runs committee from PM's verbal inputs
```

**Failure modes:** Human error in reading scores, stale data from screener refresh lag, inconsistent PTRS computation, hours of manual chart review.

## After (AQE-driven)

```
AQE runs automatically at 6 AM SGT →
produces ranked, scored, SRM-overlaid shortlist →
PM reviews shortlist over coffee (10 min) →
PM selects 3-5 candidates for committee →
Alfred runs committee with AQE data as input →
PM confirms bracket orders on IBKR
```

**Gains:**
- **Consistency:** Every ticker scored identically. No dashboard-reading errors. No "forgot to check Elder gate."
- **Speed:** Full universe scored in 30 minutes (automated). Previously: hours of manual TV chart review.
- **Coverage:** Screen 1000+ names daily, not the 30-50 PM can manually review.
- **Audit trail:** Every score, every date, stored in SQLite. Backtestable. Reviewable.
- **Data maximisation:** FMP subscription fully utilised. Currently paying for data we pull ad-hoc.
- **Independence from TV:** No more screener lag, no more request.security limits, no more 4-call tuple hacks.
- **Committee quality:** Alfred receives structured data, not PM's verbal summary of a TV dashboard.

## What Doesn't Change

- **Committee deliberation remains qualitative.** AQE scores the numbers. Humans interpret context.
- **PM retains final decision authority.** AQE is a decision-support tool, not an auto-trader.
- **Charter v1.8 governs.** AQE implements the charter mechanically. Any charter amendment updates AQE.
- **TV available for visual confirmation.** PM can still open a chart to see price action. No computation required.

---

*AQE Engineering Specification v0.1 | 18 May 2026*
*Authored by: Alfred (Scrum Master) on direction of PM*
*Charter authority: AIC v1.8 | Indicator spec: Design Committee v1.0*
