# AQE — Aegis Quant Engine

## What this is

Production daily scanner for US equities. Scores 600+ tickers nightly through 5 proprietary engines (Flow, Energy, Structure, MP, Elder Impulse), composites (SC_MOMENTUM, SC_POSITION), Pipeline Rank, and PTRS. Outputs a ranked shortlist, longlist, and watchlist with backtested DSL stops and take-profit levels. The export JSON (`aqe_daily_export.json`) is the downstream read interface for future analysis layers (phase 2).

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
- `drive_sync.py` — exports `aqe_daily_export.json` to `output/` (local working copy) + the pinned Google Drive folder via REST (no local `G:` mount)
- `ptj.py` — reads the daily held-positions journal (PTJ) from a dedicated Drive folder (`GDRIVE_PTJ_FOLDER_ID`, default `15PR74…`), picking the **latest-modified** non-folder file (dedupes runtime duplicates; ignores the `Legacy/` archive subfolder). Extracts `open_positions` → caches `output/held_positions.json`. The export then sets `held=true` on those tickers and adds a top-level `held_positions` array = the trade (entry/qty/SL/TP/unrealised) + AQE's current engine read (scores, MP state, DSL bracket, sector, RS). Surfaced on the Scanner "Held positions" panel + the Charts "Bought @" overlay.
- `sector_mapper.py` — maps tickers to GICS sector ETFs
- `universe.py` — fixed, manually-curated ticker universe (the "fishing net"). Auto-refresh from the FMP screener is DISABLED (it ballooned to ~1800). Source of truth = a single CSV in a **dedicated Drive subfolder** (`UNIVERSE_FOLDER_ID`, override `GDRIVE_UNIVERSE_FOLDER_ID`); `restore_universe_from_drive()` overwrites the local `universe.txt` from it on every pipeline startup. Update via the app's Universe panel (overwrites the canonical `universe.csv`) or by replacing the file in that folder. `get_drive_universe_status()` powers the in-app date/count display.

### Cloud uptime + daily auto-run (HF Space)
- `src/ui/keepalive.py` — in-app daemon pings the Space's own public URL (`KEEPALIVE_MINUTES`, default 90) so HF doesn't sleep. Paired with an external UptimeRobot monitor (every 30 min). Both no-op locally; both work behind the `AQE_APP_PASSWORD` gate (started in `require_login()` before `st.stop()`; HF counts any HTTP hit).
- `src/ui/daily_job.py` — in-app scheduler thread runs the full pipeline at **08:30 SGT, Tue–Sat** (skips Sun/Mon — US markets shut Sat/Sun), exporting to the AQE Drive folder. Writes a `aqe_last_run.json` marker (local + Drive) that drives the Scanner's status bar (last run time / success / push). Needs the container awake (UptimeRobot). HF-only unless `AQE_ENABLE_SCHEDULER=1`.
- `earnings.py` — pulls/stores earnings calendar from FMP
- `db.py` — SQLite state store (7 tables)

### Live alerts — "Trade Entry Menu" (`src/alerts/` + `src/ui/pages/3_Charts_and_Trade_Entry.py`)
The PM's level-watch + 2-system AIC loop. AQE polls FMP for **15-min-delayed**
quotes every `AQE_ALERT_MINUTES` (default 15, matching FMP Starter's delay) and
emails a digest when a monitored ticker hits a key level. AQE has **no AI inside** —
each alert carries a ready-to-paste "engage AIC via Claude" prompt, so the PM runs
the committee decision externally (data ping → human → AIC).
- Monitored set = every ticker across `top_picks`/`edge_list`/`longlist`/`watchlist`
  + `held_positions` (held names win; else richest tier: PE > top > longlist > watchlist).
- **Only THREE actionable, bounded level events are emailed** (PM ruling — TP-hit /
  Fib / MA / RVol were removed as stale noise): **Hit buy price** — today's
  intraday candle traded THROUGH the buy line (`day_low ≤ dsl_be ≤ day_high`),
  not a proximity-to-buy check; naturally bounded (a name that gapped above and
  held, or never reached it, doesn't fire), **fresh Breakout** (`entry·(1+BREAKOUT_PCT) ≤ live ≤
  entry·(1+BREAKOUT_MAX_PCT)` — bounded so already-extended names never fire), and
  **Approaching-stop** (`stop < live ≤ stop·(1+NEAR_STOP_PCT)`, `held_sl` for held).
  Every condition is a bounded band, so a name far past a level can't re-fire.
- **Freshness guard**: `run_alert_cycle` refuses to email off an export older than
  `MAX_EXPORT_AGE_DAYS` (default 4) — no more blasting stale levels if the pipeline
  didn't run. Export date is shown in the email header.
- `engine.py` — `run_alert_cycle()` (load export → fetch quotes → `evaluate()` per
  ticker → dedup → email → save state); never raises. `config.py` — thresholds via
  `AQE_ALERT_*` env. `state.py` — dedup once-per-(ticker,level)-per-US-trading-day in a
  shared Drive file `aqe_alert_state.json` (both pollers share it; last-writer-wins).
  `emailer.py` — digest via **Resend HTTP** (`RESEND_API_KEY`, works on HF over HTTPS)
  with **Gmail SMTP fallback** (`AQE_SMTP_PASSWORD`, GitHub-only). Layout: **HELD
  section first, then grouped by type (Buy / Breakout / Approaching-stop), ranked by
  SC_MOM within each group**, compact, each row carrying a one-line AIC prompt.
- Export now carries absolute `ma_20/50/100/200` + `fib` on every record (incl. held)
  so alerts are export-driven. `fmp_client.get_quotes()` adds the 15-min quote fetch
  (`/stable/quote`: price, volume, avgVolume, priceAvg50/200).
- **Primary emailer = the in-app HF thread `src/ui/alert_job.py`** (every 15 min,
  sends via Resend HTTPS — reliable cadence, which GitHub's throttled `*/15` cron is
  NOT). HF blocks SMTP but allows HTTPS, so Resend works in-app. The GH Actions cron
  `alerts.yml` (`*/15 13-21 * * 1-5`) stays as a **backstop** sharing the Drive dedup
  state (`aqe_alert_state.json`) so the two never double-email; `scripts/alert_poll.py`
  (`--force` / `--test-email`). Both read `RESEND_API_KEY` then fall back to SMTP.
- **Charts + Trade Entry are ONE page** (`3_Charts_and_Trade_Entry.py`; the old
  separate `3_Charts.py`/`4_Trade_Entry_Menu.py` were merged). Left (majority) = the
  price chart (EOD candles + 20/50/100/200 MAs + live 15-min forming candle/line + DSL
  buy/stop/TP zones + held "Bought @" overlay + AQE numbers); a **free-text ticker
  search** + filtered dropdown drive it. Right rail = the Trade Entry Menu with a
  **Latest ↔ Cards** toggle: *Latest* = chronological 36h feed grouped by SGT day (from
  Drive's `aqe_alert_history.json`, no FMP calls); *Cards* = live triggers grouped into
  the four categories (Entry-pullback / Approaching-stop / Breakout / Key-levels, needs
  a quote refresh). **Every alert is a button — click it to load that ticker's chart**;
  `★ HELD` buttons render red + flashing and sort first. Test email from GitHub:
  **Actions → AQE live alerts → Run workflow → tick `test`**.

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

### Scoring composites (`src/engines/scoring.py`) — v1.8.0
**Parity with TradingView `Scoring v1.8.0`: composites are UNCAPPED.** The raw
weighted average flows straight through (`sc_momentum = sc_m_raw`); sub-component
floors and the Elder/K39 gates are NOT a score cap. They're exported as separate
qualification booleans `sc_m_gates` / `sc_p_gates` (Pine `SC_M_GATES` / `SC_P_GATES`).
The longlist/PE recipe screens enforce engine floors independently downstream, so
list membership is unchanged — only gated *watchlist-tier* names (and their PTRS)
now read their true composite instead of being pinned at 49.

**SC_MOMENTUM** = Flow(30%) + Energy(30%) + Structure(20%) + MP(20%)
- Gate flag (`sc_m_gates`): Elder >= 6.5, Flow >= 60, Energy >= 60, Structure >= 55, MP >= 55

**SC_POSITION** = Flow(10%) + Energy(30%) + Structure(20%) + MP(5%) + BQ(35%)
- Gate flag (`sc_p_gates`): Flow >= 40, Energy >= 60, Structure >= 65, MP >= 40, BQ >= 60, K39 gate

> History: v1.6.0 hard-capped a gate-failing composite at 49.0 (`GATE_CAP`). v1.8.0
> removed that cap to match the canonical chart (AIC-approved, 8 Jun 2026).

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
Steps: incremental pull -> Pipeline Rank screen -> full scoring (top 50) -> SRM grading -> regime detection -> PTRS + disposition -> recipe match screen -> Precision Edge screen -> output JSON + Drive export.

### Scanner UI (`src/ui/1_Scanner.py`)
Streamlit multi-page app. Page 1 = Scanner (regime, SRM, Precision Edge, longlist, watchlist).
- Longlist: sorted by Pipeline Rank DESC + Floor DESC. Columns include DSL stop, TP(+2R), R%, QTY, Beta, Why.
- Watchlist: full universe above raw SC_MOM slider. Same DSL columns.
- `_compute_dsl_levels()` — cached helper computing structural stops for all tickers
- `_load_betas()` — cached 60d beta vs SPY
- `_rank_explain()` — 1-liner ranking explanation

### Drive export (`src/data/drive_sync.py`)
ONE combined JSON for committee consumption — `aqe_daily_export.json` in a single
`AQE/` folder, overwritten every run (no date-stamped clutter). Contains:
- `top_picks` (PTRS-ranked shortlist), `edge_list` (Precision Edge), `longlist`, `watchlist`
- Every ticker tagged with: `source` (longlist/watchlist), `pe` (bool), `on_longlist` (bool)
- DSL fields: `dsl_stop`, `dsl_risk`, `dsl_tp_2r`, `dsl_shares`, `dsl_rr_pct`
- `beta_60d`, `rank_explain` per ticker
- `exported_at` (SGT timestamp), `market`, `regime`
- **SRM is combined in-file** (no separate SRM file): `srm` (canonical sector-grade
  list for downstream readers), plus `srm_gics`/`srm_signals`/`srm_deploy`/`srm_avoid` aliases
- Erase-then-write to `output/` (local working copy) and the pinned Google Drive
  folder via the REST API (folder ID in `gdrive_uploader.DEFAULT_FOLDER_ID`,
  override with `GDRIVE_FOLDER_ID`). Scope is full `drive`. No local `G:` mount.
- **Trade journal is local-only:** `aegis_trade_journal_{date}` is written to `output/`
  and NOT published to Drive. The old `SRM Daily/` and `AEGIS Trade Journal/` Drive
  folders are no longer written.

### AQE v2.1 schema (charter v1.9.2 / Data Schema Spec v1.0)
**Principle: AQE exports DATA + computed LEVELS only — no decisions, no sizing.**
Per-record fields on all four tiers (uniform; `_v21_record_fields` + a normalization
pass in `drive_sync.py`): `gics_sector`, `gics_sector_name`, `gics_gate`
(PASS/BLOCKED/WATCH/CHECK from SRM grade), `sector_corr` + `sector_corr_class`
(60d Pearson vs parent ETF), `rvol` (vol/20d-avg), `rs_spy_20d` (20d ROC − SPY 20d ROC),
`sma_distance_pct` (vs 50D SMA), `rr_tp1/2/3` (R:R to each DSL target from `dsl_be`),
`held` (false — positions decommissioned). Top-level: `spy_roc_20d`,
`sector_map_version`, `sector_map_gaps`. All defensive — failures degrade to null.
- **REMOVED** (PM ruling, "AQE makes no decisions/sizing; no nulls"): `disposition`
  (sizing decision — Alfred decides from `ptrs`), `dsl_shares` (sizing calc),
  `atr_1h` / `breakout_stop` / `daily_range_proxy` (always-null in an EOD system).
- **DSL stop = β-adjusted v2.1** (`compute_initial_stop`): recent 5-session low − 0.5·ATR,
  clamped to [0.75, upper]×ATR, upper = 2.5/2.25/2.0 for β≥2.0/≥1.5/else. Wider room for
  high-β names (charter-updated to stop early stop-outs). Bracket geometry holds
  (`dsl_be−dsl_stop = 1.5·dsl_risk`; `tp_N = be + 0.5/1.5/2.5·dsl_risk`). `dsl_atr_ratio` =
  effective stop width in ATRs (β-capped 2.0–2.5; no more 3.5 pegging).
- **PTRS** = engine score + SH (sector health); Alfred reads `ptrs` verbatim, computes no
  CM/SH/RA/RL. SRM `TURNING` SH = **−3** in AQE (PM "early signal" ruling; charter §4.3 says
  −5 — charter to be amended to −3 to match).
- **Sector RAG map** (`aqe_sector_map.json`, rich §6.2 format) published to a dedicated Drive
  subfolder `SECTOR_MAP_FOLDER_ID` (override `GDRIVE_SECTOR_FOLDER_ID`). Source of truth =
  `data/sector_map.json` (flat {ticker: ETF}); gaps surfaced, filled manually.
- UI: the Scanner page shows a **"AQE export — exactly what AIC receives"** panel rendering
  the verbatim export per tier (parity with the JSON).

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
- Drive destination: pinned Google Drive folder via REST (`gdrive_uploader.DEFAULT_FOLDER_ID`)
- UI launcher: `run_app.bat`
- Pipeline: `python -m src.pipeline.daily_orchestrator` (or in-app button)

---

## Deploy targets + iteration workflow (Claude operating manual)

### Git remotes
- `origin` -> `https://github.com/TongIncomeWheel/AQE.git` (private GitHub, source of truth)
- `hf`     -> `https://huggingface.co/spaces/AQE-Aegis/aqe` (HuggingFace Space, Docker SDK, auto-redeploys on push)

Both auths are persisted on this PC:
- GitHub: Git Credential Manager has cached the token
- HuggingFace: `huggingface_hub.login(token=..., add_to_git_credential=True)` ran once, lives in `~/.cache/huggingface/token` + Credential Manager

Either remote can be pushed to from any bash shell on this PC without an interactive prompt. Claude can do this directly.

### Standard iteration loop
1. Edit code locally (any file under `src/`, `streamlit_app.py`, `Dockerfile`, etc.).
2. Run a smoke test that matches the change:
   - Streamlit UI changes -> `python -c "from streamlit.testing.v1 import AppTest; print(AppTest.from_file('streamlit_app.py').run(timeout=60).exception)"`
   - Engine math changes -> targeted import + scalar check
3. `git add` only the touched files (NEVER `git add .` without a staging audit -- AQE has real-money JSON that could leak).
4. `git commit -m "..."` -- conventional message describing intent.
5. `python -m scripts.push_both` (or double-click `push_both.bat`) -- this pushes to `origin` then `hf`.
6. Surface to the user: GitHub commit URL + HuggingFace Space URL for UAT.

### When NOT to dual-push
- `--no-hf` for changes that don't affect the cloud deploy (e.g. scripts/ helpers, local-only `.bat` files).
- `--no-origin` for HF-only debugging (rare).

### What lives where after each push
- **GitHub** = full source of truth, including DEPLOY.md, CLAUDE.md, and the committed export JSON
- **HuggingFace** = Docker image built from the same source; runtime parquets live in the container's `/data` (ephemeral) or `AQE_DATA_DIR` (if persistent storage is enabled)

### Credential security posture
- `.env` is gitignored. The local FMP key never leaves the PC via git.
- HF secret store holds the cloud copy of `FMP_API_KEY`. Set once in the HF UI; Docker injects it into the container env at start.
- **`AQE_APP_PASSWORD`** (HF secret) password-gates the whole app at the front door on the public Space. When set, every page calls `require_login()` (in `src/ui/shared.py`) and halts with a sign-in form until authenticated; auth is per browser session, shared across pages. Unset locally → app opens with no friction. This gate is UI-only and deliberately does NOT touch the Drive write path, so the scheduled 9am `daily_orchestrator` run writes to Drive unattended.
- HF access tokens live in `~/.cache/huggingface/token` (file-permission protected) and Windows Credential Manager. If a token is ever leaked, rotate at <https://huggingface.co/settings/tokens>.

### Reference scripts
- `push_both.bat` -- dual-push helper
- `push_aqe.bat` -- legacy single-push helper (origin only, for read-only Streamlit Cloud workflow)
- `scripts/push_to_cloud.py` -- the small-file-only refresh helper (used when only the daily JSON changed)
- `scripts/push_both.py` -- the engine behind push_both.bat
