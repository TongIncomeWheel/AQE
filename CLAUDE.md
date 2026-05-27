# AQE — Aegis Quant Engine

## What this is

Production daily scanner for US equities. Scores 600+ tickers nightly through 5 proprietary engines (Flow, Energy, Structure, MP, Elder Impulse), composites (SC_MOMENTUM, SC_POSITION), Pipeline Rank, and PTRS. Outputs a ranked shortlist, longlist, and watchlist with backtested DSL stops and take-profit levels. An LLM committee ("Aegis Committee") consumes the export JSON for downstream analysis.

**This is NOT a portfolio backtester.** It is a signal-accuracy and scoring system for real-money deployment.

## Critical user constraints — NEVER violate

- **No terminal interaction.** Everything is double-click `.bat` or in-app Streamlit buttons. The user does not use terminals.
- **Risk per trade is ALWAYS 3%.** $70K capital base. Risk budget = $2,100 per FULL trade. No Kelly, no quarter-Kelly, no academic sizing.
- **MAX_POSITIONS = 6** in `src/backtest/sizing.py`.
- **FMP API key** is in `.env` which is `.gitignored`. NEVER commit `.env` or expose the key.
- **Pine is the spec, Python is the implementation, FMP is the data.** No TradingView dependency.
- **No fancy visuals.** Plain tables, matplotlib, CSV/JSON/PNG output. Streamlit UI.
- **FIP is informational, NOT a filter gate.** Spike movers are the best trades.
- **Elder Impulse >= 7 required** for entries. Grid is [7, 8, 9], no 0 option.
- **"A higher win rate is better than a low win rate but bigger R."**
- **SIGNAL_MAX_AGE = 2 trading days.** Stale picks have no edge.
- **User is in Singapore (SGT, UTC+8).** Data is US markets close-of-day scans. All timestamps use `ZoneInfo("Asia/Singapore")`.
- **Do NOT cap lists at 25.** When asked for a list, show the full list.
- **Watchlist is simple:** show tickers with SC_MOM score above the slider threshold.

## Architecture

### Data layer (`src/data/`)
- `fmp_client.py` — FMP REST client
- `panel_builder.py` — builds `data/panel_daily.parquet`, `panel_weekly.parquet`, `spy_daily.parquet`
- `scores_daily.parquet` — lives in `data/` (NOT `output/`)
- `drive_sync.py` — exports `aqe_daily_export.json` to `output/` + `G:\My Drive\Trading Strategy\AQE\`
- `sector_mapper.py` — maps tickers to GICS sector ETFs
- `universe.py` — manages the 600+ ticker universe
- `earnings.py` — pulls/stores earnings calendar from FMP
- `db.py` — SQLite state store (7 tables)

### Engines (`src/engines/`)
- `flow.py` — Flow v1.3 (accumulation, volume, skew, extension, MFI, CMF, HA quality)
- `energy.py` — Energy v1.3.1 (VP position, price action, squeeze, exhaustion, ATR)
- `structure.py` — Structure v1.5.0 (RS vs SPY, base detection, market structure, weekly trend, earnings)
- `mp.py` — MP v1.2 (absolute + relative momentum, ADX with Wilder RMA, trend)
- `elder.py` — Elder Impulse engine
- `bq.py` — Base Quality sub-engine
- `k39.py` — K39 gate (weekly confirmation)
- `pipeline_rank.py` — Pipeline Rank v1.0 (12mo return, ADX, RSI, vol, MA alignment)
- `scoring.py` — SC_MOMENTUM + SC_POSITION composites with gate enforcement
- `srm.py` — Sector Rotation Model (GICS ETF grading: DEPLOY/HOLD/TURNING/WATCH/AVOID)

### Scoring composites (`src/engines/scoring.py`)
**SC_MOMENTUM** = Flow(30%) + Energy(30%) + Structure(20%) + MP(20%)
- Gates: Elder >= 6.5, Flow >= 60, Energy >= 60, Structure >= 55, MP >= 55
- If ANY gate fails: composite hard-capped at 49.0 (`GATE_CAP`). Raw score preserved in `sc_momentum_raw`.

**SC_POSITION** = Flow(10%) + Energy(30%) + Structure(20%) + MP(5%) + BQ(35%)
- Gates: Flow >= 40, Energy >= 60, Structure >= 65, MP >= 40, BQ >= 60, K39 gate
- Same 49.0 cap on gate failure.

### PTRS (`src/analyzer/ptrs.py`)
PTRS = SC_MOM + SH (sector health only). No VIX (RL) or Regime Alignment (RA).
- SH range: -8 to +3
- Disposition: >= 60 FULL, 50-59 HALF, 45-49 QUARTER, < 45 REJECT
- Regime handles VIX sizing separately — no double penalty

### DSL v2.0 (`src/scanner/dsl.py`)
Dynamic Stop Loss with R-tiered trailing + flow-based take-profit.
- Initial stop: `lowest(low, 5) - 0.5 * ATR(14)`, clamped to [0.75, 2.0] * ATR
- Tiers: T1(0-0.5R) -> T1b(BE at +0.5R) -> T2(+1R) -> T3(+2R) -> T4(+4R)
- Flow TP: in Tier 1, if flow_100 < 65 and R > 0.2 after 2-bar grace -> exit
- Trail ratchets upward only. Highest tier locks.
- Both Scanner UI tables and Drive export show DSL-based stops (not the naive 2xATR).

### Daily pipeline (`src/pipeline/daily_orchestrator.py`)
Steps: incremental pull -> Pipeline Rank screen -> full scoring (top 50) -> SRM grading -> regime detection -> PTRS + disposition -> recipe match screen -> Precision Edge screen -> output JSON + Drive export -> position tracker update.

### Scanner UI (`src/ui/1_Scanner.py`)
Streamlit multi-page app. Page 1 = Scanner (regime, SRM, Precision Edge, longlist, watchlist).
- Longlist: sorted by Pipeline Rank DESC + Floor DESC. Columns include DSL stop, TP(+2R), R%, QTY, Beta, Why.
- Watchlist: full universe above raw SC_MOM slider. Same DSL columns.
- `_compute_dsl_levels()` — cached helper computing structural stops for all tickers
- `_load_betas()` — cached 60d beta vs SPY
- `_rank_explain()` — 1-liner ranking explanation

### Drive export (`src/data/drive_sync.py`)
JSON export to Google Drive for committee consumption. Contains:
- `top_picks` (PTRS-ranked shortlist), `edge_list` (Precision Edge), `longlist`, `watchlist`
- Every ticker tagged with: `source` (longlist/watchlist), `pe` (bool), `on_longlist` (bool)
- DSL fields: `dsl_stop`, `dsl_risk`, `dsl_tp_2r`, `dsl_shares`, `dsl_rr_pct`
- `beta_60d`, `rank_explain` per ticker
- `exported_at` (SGT timestamp), `market`, `regime`, `srm_deploy`, `srm_avoid`
- Erase-then-write to both `output/` and `G:\My Drive\Trading Strategy\AQE\`

### Active recipe thresholds
Longlist: SC >= 75, Flow >= 80, Energy >= 64, Structure >= 60, MP >= 60, Elder >= 7, Phase = ANY
Stored in `data/active_recipe.json` (dual format: `longlist` + `precision` sections).

### Sizing chain
PTRS disposition (ticker quality) x Regime max_new_size (VIX macro) = final position size.
- FULL = 3% risk ($2100), HALF = 1.5% ($1050), QUARTER = 0.75% ($525)
- Shares = risk_budget / dsl_risk (1R)

### BE Trigger + Trail Ladder
`entry + 0.5 * r_size` triggers breakeven. Trail: BE(+0.5R) -> stop to entry | +1R -> stop to entry | +2R -> stop to +1R | +3R -> stop to +2R (RUNNER)

## Key file paths
- Project root: `C:\Users\ashtz\Backtest Engine`
- Data: `data/panel_daily.parquet`, `data/scores_daily.parquet` (in `data/`, NOT `output/`)
- Output: `output/shortlist.json`, `output/aqe_daily_export.json`
- Drive mount: `G:\My Drive\Trading Strategy\AQE\`
- UI launcher: `run_app.bat`
- Pipeline: `python -m src.pipeline.daily_orchestrator` (or in-app button)
