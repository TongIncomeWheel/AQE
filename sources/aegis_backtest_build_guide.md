# AEGIS BACKTESTING SYSTEM — LOCAL BUILD GUIDE

**Purpose:** Get the backtesting application running on your PC so it persists, evolves, and produces evidence before we touch any more indicators.

**Without this, every design decision is assumption-based. With it, we test before we build.**

---

## WHAT YOU HAVE RIGHT NOW

Download `aegis_backtest_v2.zip` from this session's outputs. It contains:

```
aegis_backtest_v2/
├── README.md              # Full documentation
├── requirements.txt       # Python dependencies
├── data_pipeline.py       # Pulls OHLCV from Massive.com API
├── backtest_runner.py     # Strategy engine + walk-forward runner
├── data/
│   └── panel_daily.parquet   # 49 tickers, 61K bars, May 2021–May 2026
└── output/
    ├── backtest_results.json
    ├── equity_curves.csv
    ├── strategy_comparison.json
    └── walk_forward_results.json
```

---

## STEP 1: SET UP YOUR PC (one-time, 10 minutes)

**Requirements:** Python 3.10+ installed. If not, download from python.org.

```bash
# Create a folder
mkdir ~/aegis-backtest
cd ~/aegis-backtest

# Unzip the download into this folder
unzip aegis_backtest_v2.zip
cd aegis_backtest_v2

# Create virtual environment (keeps it clean)
python -m venv venv

# Activate it
# Mac/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Verify it works:**
```bash
python -c "import vectorbt; import pandas; print('Ready')"
```

---

## STEP 2: RUN THE BASELINE (5 minutes)

The data panel is already in the zip. No API calls needed.

```bash
python backtest_runner.py
```

This runs walk-forward analysis on the standard 12-month momentum strategy and prints:
- In-sample metrics (Oct 2021 – Dec 2023)
- Out-of-sample metrics (Jan 2024 – May 2026)
- Sharpe decay (overfit check)
- Results saved to `output/results.json`

**What the baseline tells you:** The maximum alpha available to a momentum trader on this universe with zero intelligence — just buy the top 10 and hold for a month. This is the ceiling. Everything Aegis does should improve on this, or we're adding friction.

---

## STEP 3: WHAT NEEDS TO BE BUILT NEXT (priority order)

### 3A. ADD STOP LOSSES (most critical)

The baseline has no stops. Aegis lives and dies by stops. Without this, the comparison is meaningless.

**What to build:** After entry, check each day if price hits the stop. If yes, exit that position at the stop price. Stop = entry − 2×ATR(14) at entry date (matching DSL v1.4 Tier 1).

**Why it matters:** The baseline holds for a full month regardless. A stock that drops 15% intramonth and recovers is a "win" in the baseline but a stopped-out loss in Aegis. Adding stops will lower the baseline return and raise the loss count — making the comparison to live Aegis fair.

### 3B. ADD RISK-BUDGET SIZING

The baseline uses 10% equal weight per position. Aegis uses 3% risk-budget sizing.

**What to build:** Position size = (Capital × 3%) / (Entry − Stop). This produces LARGER positions on tight-stop stocks and SMALLER positions on wide-stop stocks. Total exposure will exceed 100% of capital (matches real Aegis leverage via IBKR margin).

### 3C. SOURCE ACTUAL VIX DATA

The current regime filter uses a proxy (SPY realised volatility). It's inaccurate — lags actual VIX by days.

**What to build:** Pull historical VIX daily closes from a free source (CBOE website CSV, or Yahoo Finance `^VIX`). Merge into the panel. Use actual VIX levels for regime classification: GREEN <18, YELLOW 18-25, ORANGE 25-30, RED >30 (no entries).

### 3D. TV SCORE PARITY VALIDATION

Before plugging Aegis scores into the backtest, we need to confirm the Python engine matches TradingView.

**What to do:**
1. Open TradingView, apply Scoring v1.8 to 5 tickers (NVDA, XOM, JPM, COST, VRT)
2. For each ticker, note SC_MOMENTUM on the last 10 Mondays (50 data points total)
3. Build a Python scoring engine that replicates the calculation
4. Compare: if mean absolute error > 5 points, fix the Python engine
5. If MAE < 5 points, proceed to Aegis-scored backtesting

### 3E. AEGIS-SCORED BACKTEST

Once parity is validated, replace the simple 12M momentum signal with actual Aegis SC_MOMENTUM scores. This answers the question: **does the scoring system select better stocks than raw momentum?**

---

## STEP 4: REFRESH THE DATA (when needed)

The panel covers May 2021 – May 2026. To extend it:

```bash
python data_pipeline.py
```

This calls Massive.com API (key is in the code, read-only). Rate-limited to ~5 calls/min. Takes ~10 minutes for 49 tickers. Appends new bars to the existing parquet.

**API key:** `tgdgC4ZRwp950XfcE3pIqLA2Yz40XkKq`

---

## STEP 5: PERSIST WITH GIT (recommended)

```bash
cd ~/aegis-backtest
git init
git add .
git commit -m "Initial: baseline momentum backtest infrastructure"
```

Push to a private GitHub repo. Every session, Alfred can reference this codebase and produce diffs. Code evolves, nothing lost between sessions.

---

## WHAT THIS SYSTEM ANSWERS WHEN COMPLETE

| Question | Test | Status |
|---|---|---|
| Does momentum alpha exist on this universe? | Baseline walk-forward | DONE — yes, Sharpe 1.47 |
| Does regime filtering improve risk-adjusted returns? | Baseline + VIX filter | DONE (directional) — needs real VIX |
| Does Aegis scoring select better than raw momentum? | Aegis-scored vs baseline | BLOCKED on TV score parity (Step 3D) |
| Are stops helping or hurting? | Baseline + stops vs baseline without | BLOCKED on Step 3A |
| Is the sizing formula correct? | Risk-budget vs equal-weight | BLOCKED on Step 3B |
| Does FIP path quality improve selection? | Top 10 by momentum vs top 10 by momentum+FIP | BLOCKED on Step 3A+3B first |
| Should the committee exist? | Aegis-scored+committee vs Aegis-scored alone | BLOCKED on everything above |

**The last question is the one from the §11 calibration schedule — CIC value-add evaluation, overdue from trade #40. The backtest infrastructure is how we answer it with data instead of opinion.**

---

## WHAT NOT TO DO

- Do NOT run the Python scoring engine from the May 7 session. It is unvalidated and unreliable.
- Do NOT draw conclusions from the +337% baseline about what Aegis "should" be doing. The implementation rules are completely different.
- Do NOT change indicators based on backtest results until the backtest matches Aegis implementation (stops + sizing + regime).
- Do NOT expand the universe beyond 49 tickers until the core engine is validated. Breadth adds noise before the fundamentals are right.

---

*Filed by: Alfred (Scrum Master) | 9 May 2026*
*This document is the build specification. The zip file is the starting code. Everything else is pontification.*
