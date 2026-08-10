# AQE — Aegis Quant Engine

## What this is

Production daily scanner for US equities. Scores 600+ tickers nightly through 5 proprietary engines (Flow, Energy, Structure, MP, Elder Impulse) plus Base Quality/K39, composites (SC_MOMENTUM, SC_POSITION), Pipeline Rank, and PTRS. Outputs one self-describing export JSON (`aqe_daily_export.json`) — `daily_list` (every scored ticker, full field set) + `lens_ranking` (the same names ordered by lens agreement) + `held_positions` (the PM's live book) — with structural stop/target brackets, a DETECT layer (divergence/pin-bar/CHoCH+kNN/structure-shift), sector rotation, and a portfolio hedge view.

**This is NOT a portfolio backtester.** It is a signal-accuracy and scoring system for real-money deployment.

**Full technical reference (every field, every formula, cited to source):** `docs/AQE_TECHNICAL_REFERENCE.md`. **Recent changes:** `docs/AQE_CHANGELOG_*.md`. This file (CLAUDE.md) stays a short operating manual — constraints + architecture map only; the deep math lives in the reference doc so it doesn't drift out of sync here.

## Critical user constraints — NEVER violate

- **No terminal interaction.** Everything is double-click `.bat` or in-app Streamlit buttons. The user does not use terminals.
- **Risk per trade is ALWAYS 3%.** $70K capital base. Risk budget = $2,100 per FULL trade. No Kelly, no quarter-Kelly, no academic sizing.
- **MAX_POSITIONS = 6** in `src/research/backtest/sizing.py`.
- **FMP API key** is in `.env` which is `.gitignored`. NEVER commit `.env` or expose the key. Cloud copy lives in HF Space secrets + the GitHub Actions repo secret (both named `FMP_API_KEY` — update both when it rotates).
- **Pine is the spec, Python is the implementation, FMP is the data.** No TradingView dependency.
- **No fancy visuals.** Plain tables, matplotlib, CSV/JSON/PNG output. Streamlit UI.
- **FIP is informational, NOT a filter gate.** Spike movers are the best trades.
- **Elder Impulse >= 7 required** for longlist entries; Elder >= 8 for the standalone `elder_list`.
- **"A higher win rate is better than a low win rate but bigger R."**
- **SIGNAL_MAX_AGE = 2 trading days.** Stale picks have no edge.
- **User is in Singapore (SGT, UTC+8).** Data is US markets close-of-day scans. All timestamps use `ZoneInfo("Asia/Singapore")`.
- **Do NOT cap lists at 25.** When asked for a list, show the full list.
- **AQE makes no decisions, no sizing.** It exports data + computed levels only — scores, brackets, gates as booleans/breakdowns. Sizing, disposition, and the final trade call are the PM/AIC's, not AQE's.
- **A failed data fetch must be LOUD, never silently empty.** (Real-money incidents this session: a failed PTJ Drive fetch and a wrong-file pick both rendered as an empty/null held book with no warning. Fixed via `held_positions_status` + the `data_quality` guard — see reference doc §I.6. Don't reintroduce a silent-empty path.)

## Architecture

Full per-module math and the complete export field list: `docs/AQE_TECHNICAL_REFERENCE.md`. This section is a navigation map only.

### Data layer (`src/data/`)
- `fmp_client.py` — FMP REST client. `panel_builder.py` — builds `panel_daily.parquet`/`panel_weekly.parquet`/`spy_daily.parquet` for the universe + GICS ETFs + thematic-basket constituents + every currently-held ticker (even outside the curated universe).
- `drive_sync.py` — builds + exports `aqe_daily_export.json` (local `output/` + the pinned Drive folder via REST, no local `G:` mount). Owns the schema guards (`_REQUIRED_FIELDS` key check, `_compute_data_quality` value check) and the field_schema/field_glossary self-description.
- `ptj.py` — reads the daily held-positions journal (PTJ) from a dedicated Drive folder. Picks the latest REAL journal by the **date encoded in the filename** (`aegis_trade_journal_YYYY-MM-DD_PTJ.json`), not raw Drive `modifiedTime` alone — a separate `ARCHIVE_master.json` running summary in the same folder is explicitly excluded. `held_positions_status` (`live`/`cache_fallback`/`unknown`) tells readers whether this run's fetch was genuinely fresh.
- `persist.py` — Daily Persist: zips runtime state (parquets/sector_map/active_recipe/`aqe.db`/outputs) into `aqe_state_snapshot.zip` on Drive so a container restart restores the last run in seconds. Powers the Scanner's Local-PC fallback (download/upload the zip) when Drive OAuth is broken.
- `sector_mapper.py` — GICS sector map, round-trips a rich RAG file via a dedicated Drive subfolder. `universe.py` — **the universe is NEVER a fixed list.** It is a dynamic FMP screen rebuilt daily at 06:00 SGT by `build_universe()` and synced to a Drive subfolder. THE rule, shared by every list (Longlist/Elder/QS): **mcap ≥ $2B · 10-day avg volume ≥ 1.5M · US primary listing (NASDAQ/NYSE)**. Size + liquidity + listing only — no trend filter (the old `price > SMA20/SMA50` conditions were removed 2026-08-04: membership is an eligibility test, not a screening opinion, and they deleted the pulled-back names QS exists to find). Each list applies its own trend view via its own thresholds.
- `held_book.py` (`src/analyzer/`) — Portfolio Hedge Layer: beta-adjusted book exposure, gap-loss scenarios, GICS sector weights, from `held_positions`. Carries both β30d and β60d bases side by side (no gate call on which is "correct").

### Cloud uptime + daily auto-run (HF Space)
- `src/ui/keepalive.py` — pings the Space's own URL so HF doesn't sleep (paired with an external UptimeRobot monitor).
- `src/ui/daily_job.py` — in-app scheduler: full pipeline at **08:30 SGT Tue–Sat**, universe CSP theta scan at **05:30 SGT**. Writes an `aqe_last_run.json` marker (local + Drive) for the Scanner status bar.
- GitHub Actions backstops (`.github/workflows/daily-run.yml`, `alerts.yml`) re-run the pipeline/alerts if the Space didn't already, sharing Drive-side dedup state so nothing double-fires.
- `earnings.py` — FMP earnings calendar. `db.py` — SQLite state store.

### Live alerts (`src/alerts/` + `src/ui/pages/3_Charts_and_Trade_Entry.py`)
Polls FMP every ~15 min for the monitored set (every export ticker + held positions). Emails on **3 bounded level events only** (hit-buy-price, fresh breakout, approaching-stop — TP/Fib/MA/RVol alerts were removed as noise). Freshness-gated against a stale export (`MAX_EXPORT_AGE_DAYS`). No AI inside — each alert carries a paste-to-AIC prompt; the PM runs the committee decision externally. Primary emailer = in-app HF thread via Resend HTTPS; GitHub Actions cron is the backstop, sharing Drive dedup state so the two never double-email.

### QS — Quiet Strength (`src/engines/qs_*.py`)
The third lens, alongside Longlist and Elder — **not a separate list.** Finds names that are structurally strong *while momentum is still asleep*, and gives each a calibrated probability of touching **+2×ATR14 within 20 sessions**, read from a frozen table of historical look-alikes.
- **Frozen config, never fitted at runtime**: `data/qs/recipe_book.json` (40 recipes, 5 vetoes, 10 regimes) + `data/qs/calibration.json` (35 3-D + 16 2-D buckets). Re-freeze annually; recipe/veto/regime edits are PM sign-off only. Reference implementation archived at `docs/qs_daily_scan_reference.py`.
- `qs_spec.py` — every frozen constant, transcribed from source with line cites. **The band asymmetry is not a typo**: hits/persist bands are right-inclusive, the lens band uses strict `<`, so `lens_total == 6.0` is `"6-7"`. `recipe_hits` counts **all 40** entries including 8 duplicate pairs — de-duplicating to 32 drops names a whole band and understates every probability.
- `qs_fields.py` — the 5 inputs AQE lacked: `ret20`, `rs_consist` (vs the **equal-weight universe**, not SPY — a breadth question), `rank_in_sector`, `trend_200`, `vol_60`. Regime terciles are expanding + shifted one day (causal); a full-series fit would leak the future into every historical row.
- `qs_engine.py` — lenses → recipes → vetoes → calibration → conviction 0-5 → levels → why.
- `qs_store.py` — memory in `aqe.db` (already in the Daily Persist snapshot): `recipe_hits` trail + regime series. `qs_persist` counts prior **stored sessions**, not calendar days.
- `qs_daily.py` — one call for the orchestrator. **Degrades loudly**: `qs_status` distinguishes an outage from a quiet market.
- `qs_card.py` — renders committee cards **from the export alone** (a test forbids it importing pandas or opening a file), so every card claim is reconstructible from the daily JSON.
- **`qs.objective` (±2×ATR14) is the yardstick the probability was measured against. `bracket` is the tradeable structural set. Never merge them** — conflating them makes `qs.odds.p` read as the odds of hitting structural TP2, which it is not.
- Backfill: `scripts/qs_backfill.bat` (~15 sessions — a floor for persistence, not a research rebuild).

### Nick Crown Macro Layer (`src/macro/crown/`)
Implementation of Crown Institutional Process **kernel v1.4** — positioning, breadth and regime *before* price. **Built STANDALONE by PM directive (2026-08-09): it reads nothing from SRM / Macro Weather / Thematic RRG and feeds nothing to them.** Merge + de-dup is a later decision; keeping them apart is what makes the overlap measurable.
- Hierarchy, in order: **Heartbeat (RSP/SPY) → if confidence < 0.40 STOP → CTA + COT + Gamma → VIX/dispersion → divergence → expression FAMILY + size multiplier.** The gate is the point: a market you can't read stops the process, it doesn't just size down.
- Outputs a **family** (one of 5) + a **multiplier on the PM's own risk budget**. Never a ticker, never a position — AQE still makes no decisions and no sizing.
- **COT comes straight from cftc.gov**, not FMP (which gates it at Premium). Annual archives backfill history; `data/crown_cot.parquet` rides in Daily Persist because that file *is* the percentile window.
- **CTA is replicated, not bought** (Moskowitz-Ooi-Pedersen + Faber, vol-normalised). Our positioning estimate won't match Goldman's; the **flip levels** — "CTAs turn seller of ES below X" — are arithmetic and will be close. That's the column worth reading.
- **The volatility complex comes from cboe.com direct** (VIX/VIXEQ/DSPX/COR1M/VIX3M/VIX9D, free, no key) — same lesson as COT: FMP gates them above Starter, Cboe *computes* them and publishes the history. The realised-dispersion proxy survives only as a last resort, still labelled `basis` + caveat + banner. DSPX and implied correlation cross-check the spread; disagreement lands in `degraded`.
- **Dispersion is level AND direction.** §2.4 gives both framings and they disagree in practice (2026-08-07: 98th-percentile spread that had *fallen* 9.2pts in 20 sessions). `band` + `direction` → `state` (`ELEVATED_RISING` vs `ELEVATED_EASING`); `hidden_stress` needs both, because buying downside into an unwinding spread buys the end of the move.
- **A gamma map without open interest is UNAVAILABLE, never a flat map** — a zeroed profile reads as "dealers are neutral", a completely different claim. Dealer-side is a stated *assumption*, not data.
- **RSI divergence ships in two forms.** Pivot form (strict, 120d lookback, higher high on lower RSI high) AND a 5d/20d **slope readout** — "SPY up, RSI down" — with both series returned for charting. The readout is a *readout first*: measured on trending random walks, the 20d window alone fires on **14.1%** of days (a bounded oscillator drifting off its plateau is what a healthy trend looks like), 5d alone 2.5%, **both agreeing 0.6%**. So both horizons always show, a single window reads `MIXED` and is never acted on, and only agreement warns. Breadth mirrors this: the regime label plus `heartbeat_ma_divergence` (index up while RSP/SPY rolls toward its own 20MA), which fires on the **ratio's own move** — the gap to the MA is self-damping since the average chases the ratio.
- **Divergence reads everything**, not one series: RSI as a matrix (SPY/QQQ/RSP + 18 CTA markets), intermarket non-confirmation from copper/oil/breadth/**dollar (inverted)**/**VIX**/**dispersion**, and a positioning sweep across all 16 COT contracts. Still only §2.5's three types — the additions are all type-2 non-confirmations. `coverage` proves a skipped check never reads as a passed one.
- **Freshness is per-source, and stale-but-present is treated as a failure.** Every leg carries `as_of` + `days_stale`; the run reports its `oldest_leg` because that is how current the read actually is. (2026-08-10 incident: `heartbeat_bars` preferred the local panel guarded by a LENGTH check, so a panel that stopped in June — thousands of rows — displaced the live fetch and the Heartbeat read June while everything else read August. The guard is now recency; a stale local file loses to the network.)
- **CTA symbols verified against FMP's `commodities-list`**: ags are cent-quoted `USX` (`ZCUSX`/`ZSUSX`/`KEUSX` — there is no `ZWUSD`), and **`ZNUSD` is ACCESS DENIED on Starter**. Every market carries an ETF fallback (ZN→IEF, ZB→TLT, ZT→SHY, CL→USO, DX→UUP…) and is **proxied + labelled, never dropped** — `flip_risk` is extremes ÷ n_markets, so a shrinking denominator silently re-rates everything.
- **`explain.py` writes the regime in plain English** — headline / why / so-what / what-would-change-it — generated from the finished dict every run and shipped as `plain_english` in the artifact, so the committee and the page read the same words. Tests forbid raw jargon (`percentile`, `dispersion`, `gex`, `vixeq`, `heartbeat`) reaching the output.
- Page: 🫀 Crown Macro. Daily: step 6f (gamma off, wrapped like QS). Full doc: `docs/AQE_CROWN_MACRO_LAYER.md`.

### Macro scenarios (`src/macro/scenarios.py`) — the FIRST MERGE POINT
Macro Weather's 7 instruments (TLT/UUP/HYG/IWM/GLD/CPER/USO) read **together with** Crown (dispersion, implied correlation, CTA bias, breadth) → 7 ranked scenarios: REFLATION, GROWTH_SCARE, INFLATION_SHOCK, DISINFLATION_GOLDILOCKS, LIQUIDITY_STRESS, DISPERSION_REGIME, DOLLAR_SQUEEZE.
- **Lives OUTSIDE `crown/` on purpose.** Crown stays standalone (a test forbids an SRM import inside it); this module reads both *finished outputs*. A merge point is a named place where two readings meet, not a dependency buried in one.
- **A score is the SHARE OF CONDITIONS MET, never a probability** — nothing fitted, nothing backtested, no base rate. The evidence + **falsifier** lists carry the value; the number only ranks.
- Guards: a scenario under 60% coverage **cannot lead** (else it wins on the data we're missing); two close scenarios report as **contested**, not a call; an unavailable input is skipped, never counted against.
- Reuses `srm.compute_macro_weather` rather than reimplementing direction scores, so this and the sector headwind can never disagree about whether copper is rising. Daily: step 6g → `output/macro_scenarios.json`.

### Engines (`src/engines/`)
Flow / Energy / Structure / MP / Elder / BQ / K39 / Pipeline Rank / SC_MOMENTUM+SC_POSITION composites — full formulas in the reference doc §Part II.1-3. `bracket_engine.py` is **the** stop/target source of truth (structural, 3-charter-gates validated; mechanical DSL/TP fields are retired from the export). `srm.py` — sector grading + RRG + macro overlay + 35 thematic baskets (context layer, never adds scan names). DETECT layer (`divergence.py`, `pin_bar.py`, `smart_money_knn.py`, `signal_radar.py`) and `lens_consensus.py` (the unweighted lens-agreement reading aid) are data-only — never gates, never sizing.

### Daily pipeline (`src/pipeline/daily_orchestrator.py`)
PTJ pull -> incremental price pull -> earnings refresh -> score-cache refresh -> Pipeline Rank screen -> full scoring -> SRM grading -> regime detection -> PTRS + disposition -> recipe screens (longlist/watchlist/Precision Edge) -> **QS engine** -> output JSON + Drive export -> daily-persist snapshot.

### ONE list, membership as columns
`daily_list` is the single list every surface reads. Longlist / Elder / QS / ledger / held are **flags on it** (`on_longlist`, `on_elder`, `on_qs`, `in_ledger`, `held`), never parallel lists — the committee reads membership in one row instead of cross-referencing three. Every row carries the identical AQE block (bracket, ATR, fibs, MAs, beta, vol, DETECT, sector) from the same `_v21_record_fields()` call, so levels cannot disagree between lists, **plus** its full `qs` block if QS scored it — including names QS did not emit, so a Longlist-only name still shows its QS read. An *absent* `qs` key means QS could not evaluate the name; that is not the same as a poor QS score.

### Scanner UI (`src/ui/1_Scanner.py`)
Streamlit multi-page app: regime, SRM, Thematic Rotation, Detect Lens Ranking, the combined Signals table (`daily_list`, slider-filterable on SC_MOM/PTRS/Elder/MP-state), Elder list, held positions + hedge layer, a `data_quality` warning banner when any record has a null core field. `shared.table_with_copy()` — every data table gets a filter box + one-click TSV copy for pasting into AIC chat.

### Active recipe thresholds
Longlist: SC >= 75, Flow >= 80, Energy >= 64, Structure >= 60, MP >= 60, Elder >= 7, Phase = ANY. Stored in `data/active_recipe.json` (`longlist` + `precision` sections). Full watchlist/Precision-Edge thresholds: reference doc §Part I §14.

### Sizing chain
PTRS disposition (ticker quality) x Regime max_new_size (VIX macro) = final position size.
- FULL = 3% risk ($2100), HALF = 1.5% ($1050), QUARTER = 0.75% ($525)
- Shares = risk_budget / bracket.risk (1R)

### Intraday Momentum & Bracket / Options scanner
Two separate, recommend-only layers that don't touch the AQE equity export and place no orders: `src/intraday/` (execution-prep — intraday-anchored stops/entry timing, driven by the Pricer page) and `src/options/` (IBKR-fed CSP/spread calculator for the income wheel, plus an Alpaca-fed universe theta sweep). Both documented in full in `docs/skills/*/SKILL.md` (the chat-skill specs that drive their headless CLI paths).

## Key file paths
- Data: `data/panel_daily.parquet`, `data/scores_daily.parquet` (in `data/`, NOT `output/`)
- Output: `output/shortlist.json`, `output/aqe_daily_export.json`
- Drive destination: pinned Google Drive folder via REST (`gdrive_uploader.DEFAULT_FOLDER_ID`)
- UI launcher: `run_app.bat`
- Pipeline: `python -m src.pipeline.daily_orchestrator` (or in-app button)

---

## Deploy targets + iteration workflow (Claude operating manual)

### Git remotes
On the user's local PC:
- `origin` -> `https://github.com/TongIncomeWheel/AQE.git` (private GitHub, source of truth)
- `hf`     -> `https://huggingface.co/spaces/AQE-Aegis/aqe` (HuggingFace Space, Docker SDK, auto-redeploys on push)

Both auths are persisted on the PC (Git Credential Manager for GitHub; `huggingface_hub` login cache for HF) — either remote can be pushed to directly, no interactive prompt.

**In a cloud/remote Claude Code session** (no `hf` remote configured): push to `origin main` only. A GitHub Actions workflow (`.github/workflows/deploy-hf.yml`) auto-mirrors every push to the HF Space and triggers its rebuild — this is the cloud-session equivalent of running `push_both`.

### Standard iteration loop
1. Edit code (any file under `src/`, `streamlit_app.py`, `Dockerfile`, etc.).
2. Run a smoke test that matches the change:
   - Streamlit UI changes -> `python -c "from streamlit.testing.v1 import AppTest; print(AppTest.from_file('streamlit_app.py').run(timeout=60).exception)"`
   - Engine math changes -> targeted import + scalar check, or the relevant `tests/test_*.py`
3. `git add` only the touched files (NEVER `git add .` without a staging audit — AQE has real-money JSON that could leak).
4. `git commit -m "..."` — conventional message describing intent.
5. **Local PC**: `python -m scripts.push_both` (or `push_both.bat`) — pushes `origin` then `hf`. **Remote session**: `git push origin <branch>:main` (fetch/rebase or cherry-pick onto current `origin/main` first if it moved — check before assuming a fast-forward).
6. Run the full test suite (`pytest -q`) before any push to `main` — this is a real-money production system; don't push red tests.
7. Surface to the user: what changed, and the GitHub/HF links for UAT.

### What lives where after each push
- **GitHub** = full source of truth, including this file and the committed export JSON backup.
- **HuggingFace** = Docker image built from the same source; runtime parquets live in the container's `/data` (ephemeral) or `AQE_DATA_DIR` (if persistent storage is enabled) — a container restart loses local state unless Daily Persist restores it from Drive.

### Credential security posture
- `.env` is gitignored; the local FMP key never leaves the PC via git.
- `AQE_APP_PASSWORD` (HF secret) password-gates the whole app at the front door on the public Space (`require_login()` in `src/ui/shared.py`); UI-only, does not block the scheduled pipeline's Drive writes.
- HF access tokens: rotate at <https://huggingface.co/settings/tokens> if ever leaked.

### Reference scripts
- `push_both.bat` / `scripts/push_both.py` — dual-push helper (local PC).
- `push_aqe.bat` / `scripts/push_to_cloud.py` — legacy single-push (origin only).
