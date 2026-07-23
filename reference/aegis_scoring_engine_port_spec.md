# AEGIS SCORING ENGINE — PYTHON PORT SPECIFICATION
# Target environment: Claude Code (local PC)
# Zero shortcuts. Line-by-line. Validated bar-by-bar.

---

## OBJECTIVE

Port all five Aegis scoring engines from Pine Script v6 to Python.
The Python output must match TradingView output to within ±0.5 points
on the composite SC_MOMENTUM score, on every bar, for every ticker tested.

If a bar diverges by more than 0.5 points, find the line and fix it.
Do not move to the next engine until the current one validates.

---

## SOURCE FILES (Pine Script — copy these to your local project)

These are the canonical Pine indicators. Every line of Python must
trace back to a specific line in these files.

1. `Flow_v1_3.pine` — Flow score (0-100)
2. `Energy_v1_3_1.pine` — Energy score (0-100)
3. `Structure_v1_5_0.pine` — Structure score (0-100)
4. `Momentum_Persistence_v1_2.pine` — MP score (0-100)
5. `Elder_Impulse_Score.pine` — Elder score (0-10)
6. `Scoring_v1_8_Overlay.pine` — Composite (reads from above five, computes SC_MOMENTUM and SC_POSITION)

All files are in the Claude project knowledge. Download them first.

---

## DATA SOURCE

Massive.com API (formerly Polygon.io). Read-only.

**API key:** tgdgC4ZRwp950XfcE3pIqLA2Yz40XkKq

**Daily bars endpoint:**
```
GET https://api.massive.com/v2/aggs/ticker/{TICKER}/range/1/day/{FROM}/{TO}?adjusted=true&sort=asc&limit=5000&apiKey={KEY}
```

Returns: timestamp, open, high, low, close, volume.

**Weekly bars endpoint (for Structure weekly trend):**
```
GET https://api.massive.com/v2/aggs/ticker/{TICKER}/range/1/week/{FROM}/{TO}?adjusted=true&sort=asc&limit=5000&apiKey={KEY}
```

Pull at least 300 daily bars per ticker (need 252 for lookbacks + 50 warmup buffer).

---

## PROJECT STRUCTURE

```
aegis-scoring-engine/
├── README.md
├── requirements.txt          # pandas, numpy, requests, pyarrow, pytest
├── src/
│   ├── data_pull.py          # Massive.com API → parquet
│   ├── flow.py               # Flow v1.3 — line-by-line port
│   ├── energy.py             # Energy v1.3.1 — line-by-line port
│   ├── structure.py          # Structure v1.5.0 — line-by-line port
│   ├── mp.py                 # Momentum Persistence v1.2 — line-by-line port
│   ├── elder.py              # Elder Impulse Score v1 — line-by-line port
│   ├── scoring.py            # Composite — reads from above five
│   └── utils.py              # Shared: wilder_rma, heikin_ashi, etc.
├── validation/
│   ├── tv_exports/           # CSV files exported from TradingView
│   │   ├── NVDA_scores.csv   # Date, Flow, Energy, Structure, MP, Elder, SC_MOM
│   │   ├── XOM_scores.csv
│   │   ├── JPM_scores.csv
│   │   ├── COST_scores.csv
│   │   └── VRT_scores.csv
│   ├── validate_flow.py      # Compare Python Flow vs TV Flow, bar-by-bar
│   ├── validate_energy.py
│   ├── validate_structure.py
│   ├── validate_mp.py
│   ├── validate_elder.py
│   └── validate_composite.py # Final SC_MOMENTUM comparison
├── backtest/
│   ├── signal_scanner.py     # Scan universe: where did SC_MOM >= 55 + Elder >= 6.5?
│   ├── outcome_tracker.py    # For each signal: what happened next? (5d, 10d, 21d returns)
│   ├── accuracy_report.py    # Win rate, avg win, avg loss by score band
│   └── universe.py           # Ticker list + data management
├── data/
│   ├── daily/                # Per-ticker parquet files
│   └── weekly/               # Per-ticker weekly bars
└── output/
    └── accuracy_results.json
```

---

## BUILD ORDER — DO NOT SKIP STEPS

### STEP 1: Shared utilities (utils.py)

Port these Pine built-in functions to Python. Every engine uses them.

```python
def wilder_rma(series, period):
    """
    Pine: ta.rma(x, length)
    Wilder's smoothing = EMA with alpha = 1/length
    pandas: series.ewm(alpha=1/period, adjust=False).mean()
    """

def ema(series, period):
    """
    Pine: ta.ema(x, length)
    pandas: series.ewm(span=period, adjust=False).mean()
    """

def sma(series, period):
    """
    Pine: ta.sma(x, length)
    pandas: series.rolling(period).mean()
    """

def true_range(high, low, prev_close):
    """
    Pine: ta.tr
    max(high - low, abs(high - prev_close), abs(low - prev_close))
    """

def atr(high, low, close, period=14):
    """
    Pine: ta.atr(14)
    wilder_rma(true_range, period)
    NOTE: Pine uses RMA (Wilder's), NOT SMA. This is the #1 divergence source.
    """

def rsi(close, period=14):
    """
    Pine: ta.rsi(close, 14)
    Uses Wilder's smoothing on gains and losses separately.
    NOT simple average. This matters.
    """

def macd(close, fast=12, slow=26, signal=9):
    """
    Pine: ta.macd(close, 12, 26, 9)
    Returns: macd_line, signal_line, histogram
    Signal line is EMA(9) of MACD, NOT SMA(9).
    May 7 session got this wrong — used SMA. Fix it.
    """

def linreg(series, length, offset=0):
    """
    Pine: ta.linreg(x, length, offset)
    Linear regression value at current bar.
    Use numpy.polyfit in a rolling window.
    """

def heikin_ashi(open, high, low, close):
    """
    Pine: Heikin Ashi candle calculation
    HA_close = (O + H + L + C) / 4
    HA_open = (prev_HA_open + prev_HA_close) / 2  [recursive]
    HA_high = max(H, HA_open, HA_close)
    HA_low = min(L, HA_open, HA_close)
    NOTE: HA_open is stateful — depends on previous bar. Must iterate, not vectorise.
    """

def stdev(series, period):
    """
    Pine: ta.stdev(x, length)
    pandas: series.rolling(period).std(ddof=0)
    NOTE: Pine uses population stdev (ddof=0), not sample stdev (ddof=1).
    """
```

**CRITICAL Pine/Python divergence points:**
- `ta.rma()` = Wilder's EMA (alpha=1/n). NOT the same as SMA or standard EMA.
- `ta.macd()` signal line = EMA, not SMA.
- `ta.stdev()` = population (ddof=0), not sample (ddof=1).
- `ta.linreg()` = value of regression line at current bar, not slope.
- Heikin Ashi open is recursive — must loop bar-by-bar.
- `var float x = na` in Pine = stateful variable that persists across bars. In Python, track it in a loop column or use iterative calculation.

### STEP 2: Port Flow v1.3 (flow.py)

Open `Flow_v1_3.pine`. Port every calculation line by line.

Flow v1.3 components (from the Pine source):
1. **MFI+CMF+HA composite** (Flow quality) — MFI(14), CMF(20), Heikin Ashi body/wick quality over 10 bars
2. **Accumulation** — OBV slope via linreg
3. **Volume Trend** — volume SMA ratio
4. **Volume Skew** — up-volume vs down-volume ratio
5. **Extension** — price distance from EMA

Each component produces a sub-score. They combine into Flow (0-100).

Read every line of the Pine. Reproduce every line in Python. Comment each Python line with the corresponding Pine line number.

### STEP 3: Port Energy v1.3.1 (energy.py)

Energy v1.3.1 components:
1. **VP Proxy** — volume-price trend (DSG-05 fix applied)
2. **Price Action** — candle body strength, momentum bars
3. **Squeeze** — Bollinger Band width vs Keltner Channel (TTM Squeeze proxy)
4. **Exhaustion** — stateful counter: bars above EMA20 (`en_trend_bars`). This is the one May 7 session skipped entirely. DO NOT SKIP.

The exhaustion component uses `var int en_trend_bars = 0` — a stateful counter that increments each bar price is above EMA20 and resets when price crosses below. This MUST be implemented as a bar-by-bar loop, not vectorised.

### STEP 4: Port Structure v1.5.0 (structure.py)

Structure v1.5.0 components:
1. **RS vs SPY** — relative strength percentage (requires SPY data alongside the ticker)
2. **RS Acceleration** — rate of change of RS
3. **Base Days** — 3-mode BD system (VCP/Staircase/Smooth). Uses `var` stateful variables: `ms_latched_bd`, `ms_bars_since_bo`, `ms_decay_counter`. MUST be bar-by-bar loop.
4. **Range 50d** — current price position within 50-day range, plus 52-week range context
5. **Weekly trend** — uses `request.security(tickerid, "W", ...)` for weekly close and MA. In Python, use the weekly bars pulled from Massive.com API. Align dates correctly — weekly bar closes on Friday.
6. **Earnings proximity** — not available from Massive.com. Default to max score (10/10 = >20 days out). Document this limitation.

**BD latch/decay logic is the hardest part.** Read the Pine code character by character. The latch sets when base conditions first trigger. The decay counter starts when base conditions break. BD score decays over N bars after breakout. This is where May 7 diverged the most.

### STEP 5: Port MP v1.2 (mp.py)

Momentum Persistence v1.2 components:
1. **Absolute Momentum** — ROC (rate of change)
2. **ADX Trend** — ADX + directional index. Uses Wilder's RMA, NOT EMA. May 7 got this wrong.
3. **Relative Momentum** — performance vs SPY over lookback period
4. **Trend Structure** — MA alignment (EMA20 > SMA50 > SMA150 etc.)

ADX in Pine uses `ta.rma()` for all smoothing. If you use EMA or SMA instead, the ADX values will be systematically different. This was a known error in the May 7 engine.

### STEP 6: Port Elder v1 (elder.py)

Elder Impulse Score components:
1. **EMA(13) direction** — rising or falling
2. **MACD histogram direction** — rising or falling
3. Score: both rising = GREEN (10), both falling = RED (0), mixed = NEUTRAL (5), with interpolation

Simple engine. Potential divergence: MACD signal line must be EMA(9), not SMA(9).

### STEP 7: Composite (scoring.py)

Reads the five engine outputs and computes:

```python
# SC_MOMENTUM weights (from Scoring v1.8 Pine):
sc_momentum = (
    flow_score * 0.30 +
    energy_score * 0.30 +
    structure_score * 0.20 +
    mp_score * 0.20
)

# v1.8: NO sub-component floor gating. Raw composite flows through.
# Charter gates (checked separately, not in the score):
#   Elder >= 6.5 for SC_MOMENTUM qualification
#   K39 PASS for SC_POSITION qualification
```

**Verify weights match the Pine source.** Read line ~505 of Scoring_v1_8_Overlay.pine.

### STEP 8: Validation

**PM must export TV scores first.** Process:

1. Open TradingView, apply Scoring v1.8 to NVDA daily chart
2. For the most recent 20 trading days, record from the dashboard:
   - Date, SC_MOMENTUM, Flow, Energy, Structure, MP, Elder
3. Save as `validation/tv_exports/NVDA_scores.csv`
4. Repeat for XOM, JPM, COST, VRT (5 tickers × 20 bars = 100 data points)

Then run validation scripts:

```bash
python validation/validate_flow.py        # Compare Flow only
python validation/validate_energy.py      # Compare Energy only
python validation/validate_structure.py   # Compare Structure only
python validation/validate_mp.py          # Compare MP only
python validation/validate_elder.py       # Compare Elder only
python validation/validate_composite.py   # Compare SC_MOMENTUM
```

Each script outputs:
- Mean absolute error (MAE)
- Max error
- Correlation
- Any bars where error > 0.5 points (flagged for investigation)

**Pass criteria:**
- Per-engine MAE < 1.0 point
- Composite SC_MOMENTUM MAE < 0.5 points
- Max error on any single bar < 3.0 points
- Correlation > 0.99

If any engine fails, fix it before proceeding. Do not build the backtest on a broken scoring engine.

### STEP 9: Accuracy Backtest (signal_scanner.py + outcome_tracker.py)

Once scoring validates:

```python
# For every stock in the universe, on every trading day:
for ticker in universe:
    scores = compute_all_scores(ticker_data)
    
    for date in trading_days:
        sc_mom = scores.loc[date, 'sc_momentum']
        elder = scores.loc[date, 'elder']
        
        # Did the system say BUY?
        if sc_mom >= 55 and elder >= 6.5:
            # What happened next?
            entry_price = data.loc[date, 'close']
            
            # Forward returns at various horizons
            ret_5d = (close[date + 5] / entry_price - 1) * 100
            ret_10d = (close[date + 10] / entry_price - 1) * 100
            ret_21d = (close[date + 21] / entry_price - 1) * 100
            
            # Did it hit a 2×ATR stop?
            stop = entry_price - 2 * atr_at_entry
            hit_stop = any(low[date+1 : date+21] < stop)
            
            # Did it reach 2:1 R:R target?
            target = entry_price + 2 * (entry_price - stop)
            hit_target = any(high[date+1 : date+21] > target)
            
            log_signal(date, ticker, sc_mom, elder, entry_price,
                       ret_5d, ret_10d, ret_21d, hit_stop, hit_target)
```

### STEP 10: Accuracy Report (accuracy_report.py)

Group the signals and count:

```
OVERALL ACCURACY (SC_MOM >= 55 + Elder >= 6.5):
  Total signals: XXXX
  Win rate (10d > 0%): XX.X%
  Win rate (21d > 0%): XX.X%
  Avg 10d return: +X.XX%
  Avg 21d return: +X.XX%
  Stop hit rate (2×ATR, 21d): XX.X%
  Target hit rate (2:1 R:R, 21d): XX.X%

BY SCORE BAND:
  SC 55-59: XX signals, XX.X% win rate, avg +X.XX%
  SC 60-64: XX signals, XX.X% win rate, avg +X.XX%
  SC 65-69: XX signals, XX.X% win rate, avg +X.XX%
  SC 70-74: XX signals, XX.X% win rate, avg +X.XX%
  SC 75+:   XX signals, XX.X% win rate, avg +X.XX%

BY COMPONENT:
  High Flow (>70) signals: XX.X% win rate
  Low Flow (<50) signals: XX.X% win rate
  High Energy (>70) + High Flow (>70): XX.X% win rate
  MP FADE signals: XX.X% win rate
  [etc.]
```

**This is the answer.** This tells you whether the indicators work, which score bands are reliable, which components add value, and where the system breaks down.

---

## KNOWN LIMITATIONS (document, don't ignore)

1. **Earnings dates** not available from Massive.com. Structure earnings proximity defaults to max. Signals near earnings will be included that Aegis would have capped to quarter-size.

2. **Survivorship bias** — 49-stock universe selected from current large-caps. Historical delistings/crashes excluded. Overestimates accuracy by an unknown amount.

3. **Look-ahead in weekly alignment** — Pine's `request.security("W", ...)` returns the completed weekly bar. Python weekly resampling must NOT use Friday's daily data until Friday's bar is complete. Align carefully.

4. **Heikin Ashi initialisation** — First HA_open depends on seed value. Pine uses the first available bar. Python must match this or the first ~20 bars of Flow will diverge.

5. **K39 gate** — requires Collin Seow's specific weekly momentum calculation. If not available in the Pine source, document and exclude SC_POSITION from the backtest. SC_MOMENTUM is the primary track.

---

## ENVIRONMENT REQUIREMENTS

```
Python 3.10+
pandas >= 2.0
numpy >= 1.24
requests >= 2.28
pyarrow >= 12.0 (parquet support)
pytest >= 7.0 (validation tests)
```

No vectorbt needed. No backtesting.py needed. This is a scoring engine + signal counter, not a portfolio simulator.

---

## RULES FOR CLAUDE CODE SESSION

1. Read the Pine source file FIRST. Understand every line before writing Python.
2. Comment every Python line with the corresponding Pine line number.
3. Do not approximate. Do not use "close enough." Port exactly.
4. Wilder's RMA, not EMA, not SMA. Check every smoothing function.
5. MACD signal = EMA(9), not SMA(9).
6. Stateful variables (`var` in Pine) = bar-by-bar loop in Python.
7. Validate each engine independently before combining.
8. If validation fails, fix the Python, do not adjust the pass criteria.
9. Do not build the backtest until all five engines pass validation.
10. No fucking shortcuts.

---

*Specification filed by: Alfred (Scrum Master) | 9 May 2026*
*This is the engineering spec. Deviation from it without PM approval is not acceptable.*
