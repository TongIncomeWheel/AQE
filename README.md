---
title: AQE Scanner
emoji: 📈
colorFrom: yellow
colorTo: blue
sdk: streamlit
sdk_version: 1.57.0
app_file: streamlit_app.py
pinned: false
short_description: Aegis Quant Engine — daily US equity scanner
---

# Aegis Backtest Engine

Local Streamlit app that answers two empirical questions over the user's tradeable universe and 5+ years of FMP daily bars:

1. Does **Scoring v1.8 SC_MOMENTUM ≥ 75** actually predict winners better than chance?
2. Conditional on SC_MOM ≥ 75, which combinations of the 5 underlying engines (Flow, Energy, Structure, MP, Elder) sharpen win rate and expectancy?

This is a **signal-accuracy lab**, not a portfolio backtester. No position sizing, no equity curve, no transaction costs. For every (ticker, date) where a filter recipe matches, the engine logs forward 5/10/21-day returns plus 2×ATR-stop / 2:1-target outcomes.

## First-time setup

1. Install Python 3.11+ from python.org. Make sure "Add Python to PATH" is checked.
2. Double-click `setup.bat`. This installs the Python dependencies.
3. Double-click `build_panel.bat`. Pulls daily bars for the universe from FMP. Takes ~1 minute.
4. Double-click `build_scores.bat`. Runs all engines across the panel. Takes ~5 minutes.
5. Double-click `run_app.bat`. Opens the analyzer in your browser.

## Daily use

After first setup, only `run_app.bat` is needed. Run `build_panel.bat` + `build_scores.bat` whenever you want fresh data.

## Folder layout

| Folder | Purpose |
|---|---|
| `src/data/` | FMP client, panel builder, universe loader |
| `src/engines/` | Ported Pine engines (Flow, Energy, Structure, MP, Elder, Scoring) |
| `src/scanner/` | Score runner, signal detector, outcome tracker |
| `src/analyzer/` | Recipe filter + metrics for the UI |
| `src/ui/` | Streamlit app |
| `data/` | Parquet caches (gitignored) |
| `output/` | Exported signal CSVs and saved recipes |
| `sources/` | Original Pine source files (reference during the port) |
| `docs/plans/` | Design doc |

## Key design notes

- **Pine is the spec, Python is the implementation, FMP is the data.** No TradingView dependency.
- **Wilder RMA** = `series.ewm(alpha=1/n, adjust=False).mean()` — NOT EMA, NOT SMA. Used in ATR, RSI, ADX.
- **Pine `ta.macd` signal line** = EMA(9), not SMA(9). (Exception: DSL v1.4 uses SMA — match the source.)
- **Stateful `var` Pine variables** (e.g., `en_trend_bars`, `ms_latched_bd`) must be implemented as bar-by-bar loops in Python.
- **Earnings score in Structure** is hardcoded to 10.0 in v1 (FMP earnings calendar deferred to Phase 2).
- **SC_POSITION** is out of v1 scope — only SC_MOMENTUM is computed.

See [docs/plans/2026-05-15-aegis-backtest-engine-design.md](docs/plans/2026-05-15-aegis-backtest-engine-design.md) for the full design.
