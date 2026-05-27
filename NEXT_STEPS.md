# Aegis Backtest Engine — Morning Status

A four-person design committee reviewed the v1 build (quant trader, UX designer, software architect, Pine-port specialist). The 23 findings they returned were prioritized and worked through overnight. The full 80-ticker, 6-year cache is pre-built; the app launches to a fully populated analyzer.

## To launch

**Double-click `run_app.bat`.** That's it.

The browser opens to `http://localhost:8501`. The data is already cached, so the headline metrics card renders on the first scan.

If you ever want to refresh:
- **Inside the app**: sidebar → "Refresh data" expander → "Rebuild prices" or "Rebuild scores".
- **Or** double-click `build_panel.bat` / `build_scores.bat` from the project folder.

## What the committee changed

### Quant trader — path-dependence was being hidden
- **Win-rate (paper)** and **win-rate (realised)** are now separate. Paper counts a signal as a win if close > entry at the horizon, even if a 2×ATR stop was hit on day 3 and never came back. Realised counts ONLY signals that booked positive R-multiples under the actual stop rule. The gap between them is the "paper-but-stopped" mirage rate, shown explicitly.
- **Gap-through-stop** is detected and the fill is at the open, not the stop price. If a signal gaps down to −2.5R, it shows as −2.5R, not −1R.
- **Conservative vs optimistic R** — when both stop and target are touched on the same bar (intraday ambiguity), we report both numbers so you can see the spread.
- **Random-entry baseline** — for every recipe, we draw matched random entries from the same months and run them through the same outcome math. If your recipe's expectancy is +0.30R but the null cohort is +0.25R, the edge is 0.05R, not 0.30R.
- **SPY same-window baseline** — average SPY forward return over the same windows. Quick sanity for "did the recipe beat just holding SPY?"
- **Wilson 95% CIs** on every rate; **bootstrap 95% CI** on expectancy. The headline tooltip shows the interval.

### UX — the app's reason for existing was missing
- **Compare-against-baseline-recipe** is now wired. Pick a saved recipe in the "Compare against" dropdown and the metrics card shows your recipe alongside the baseline with Δ-vs-baseline deltas on every headline number. This is what answers "does adding Flow ≥ 70 actually sharpen SC_MOM ≥ 75 alone?"
- **Plain-English labels** with tooltips on every slider. "SC_MOMENTUM ≥" → "Momentum composite ≥". "MP states" → "Posture phase: Building / Strong / Fading". A glossary expander at the top of the main pane explains each engine in two sentences.
- **3 headline metrics + collapsed detail.** The top of the page shows Signal count, 21d expectancy (R), 21d realised win rate, and 21d stop-out rate. The 18-number detail grid (per window × per metric) lives in an expander for when you want it.
- **Signal drill-down.** Pick any row in the signal table and you see the engine-contribution bars (Flow / Energy / Structure / Posture / Elder), plus a 90-day price chart with the stop and target lines and a Momentum-composite line chart below it, both annotated with the signal date.
- **Empty-cache onboarding.** If you ever wipe the cache, the app shows a two-step setup pane with "Build prices" and "Build scores" buttons that run the panel/score builders with live progress. You never see a terminal.
- **Empty-result message** now distinguishes "no cross-ups at this threshold" from "cross-ups exist but engine filters eliminated them."
- **Save-recipe overwrite** requires an explicit checkbox if the name already exists. No silent overwrites.

### Software architect — five P0 correctness bugs
- **Signal detector NaN handling.** `s < threshold` returned False for NaN warmup bars, breaking the cooldown counter. Fixed: NaN bars break the run-length, never trigger a cross-up.
- **Score-runner perf.** Replaced `panel.loc[panel["ticker"]==ticker]` (O(rows) per ticker, 80×) with a single `groupby` (O(rows) total). Same fix in `outcome_tracker`.
- **align_spy / align_to_dates dedup.** Both helpers now `drop_duplicates("date", keep="last")` before `set_index` so a corrupted parquet can't crash the engines.
- **FMP error payload.** `{"Error Message": "..."}` responses (returned with HTTP 200) now raise instead of silently skipping the ticker. The 401/403 case has a friendlier "fix your .env" message.
- **Streamlit cache mtime keying.** `load_panel` / `load_scores` are now cached on file mtime; rebuilding while the app is open auto-invalidates.

### Pine-port specialist — engines audited clean
Every engine math-reviewed line-by-line. **No P0 divergences**. The only non-trivial systematic gap is the v1-scope earnings score in Structure (hardcoded to 10.0; FMP earnings-calendar pull is Phase 2). That can inflate Structure raw by up to 10 points within 20 days of an earnings event.

### FMP endpoint migration (caught during real-data validation)
The legacy `/api/v3/historical-price-full/` endpoint stopped accepting keys created after Aug 2025 — your key got the "Legacy Endpoint" error. The client now uses `/stable/historical-price-eod/full` which is the documented replacement and returns split + dividend adjusted OHLC directly.

## What the data actually said (full universe, 89 tickers × 6 years)

I ran the full panel before you woke up. SC_MOM ≥ 75 cross-ups with 21d cooldown produced **1,047 signals** across 89 tickers. At the 21-day window:

| Metric | Recipe (SC_MOM ≥ 75) | Random baseline | SPY same window |
|---|---|---|---|
| Signals (N) | 1047 | 1034 | — |
| Win rate (realised) | 50.5% | 50.0% | — |
| Win rate (paper) | 58.9% | — | — |
| Expectancy | **+0.25 R** | **+0.22 R** | — |
| Expectancy 95% CI | +0.17 .. +0.33 R | — | — |
| Hit-stop rate | 42.7% | — | — |
| Avg forward return | — | — | +0.95% |
| **Paper-but-stopped** | **9.6%** | — | — |

**This is the empirical answer to your core question:** SC_MOM ≥ 75, *as a standalone rule on this universe over this period*, is **not meaningfully predictive above random** — the edge vs random is +0.03R per signal, well inside the CI, so consistent with no edge at all. The 0.25R positive expectancy is almost entirely market-beta drift over a bullish 2020–2026 backtest window.

Two things you should know:
1. **The 8.4pp gap between paper (58.9%) and realised (50.5%) win rate is real.** Roughly 1 in 10 "winners" by paper actually got stopped out first then recovered — money you didn't capture. Your discretionary mental model was probably tracking paper, not realised.
2. **Adding Flow ≥ 70 AND Energy ≥ 60 doesn't help** — it cuts N from 1047 to 921 and expectancy stays at +0.25R. Engine combinations need a different approach. Some directions to try in the app:
   - **Filter by Posture phase: STRONG only** (currently includes BUILDING + FADING).
   - **Elder ≥ 7** (the gate the Pine spec uses for "qualified" signals).
   - **Structure ≥ 70** with Elder ≥ 7 — quality + impulse.
   - **Higher SC_MOM threshold** (80, 85) to see if the tail of the distribution is more predictive than the entry zone.

The compare-against-baseline UI is built to make these iterations fast — save "SC_MOM≥75 only" as baseline, then try variants and watch the Δ-expectancy.

**Caveat:** the random baseline is matched on month-of-signal, so it shares the regime drift. The right question isn't "does it beat random globally?" but "does it beat random conditional on being in a chosen filter cohort?" Both numbers move with regime; the *edge* is what you're studying.

## Tests

`run_tests.bat` → 23 tests, all green.

- `test_utils.py` — Wilder RMA, ATR, RSI, MACD signal type, stdev ddof=0, linreg, Heikin Ashi recursion, weekly-asof no-look-ahead.
- `test_engines_smoke.py` — each engine produces [0,100] (or [0,10] for Elder) on synthetic bars with no NaN floods.
- `test_smoke_endtoend.py` — full pipeline; gap-through-stop test; NaN-warmup cooldown test; empty-input handling; random + SPY baselines.

## What's still in scope-shifted territory

- **Earnings score** is hardcoded to 10.0 (the "≥20 days out" max). FMP earnings-calendar pull is Phase 2 — would prevent the up-to-10pt Structure inflation near earnings.
- **SC_POSITION** (BQ engine + K39 weekly stoch) — explicitly out of v1 scope.
- **VP-array math in Energy** — Pine itself uses the range-position proxy for scoring (the array values are diagnostic-only per Pine line 117). We match Pine.
- **Pullback / pivot / ATR-risk diagnostics in Structure** — not in the headline composite. Easy to add as extra columns later.

## File touch list

| Layer | Files changed |
|---|---|
| FMP | `src/data/fmp_client.py` (endpoint migration + error detection + key-rejection message) |
| Data | `src/data/panel_builder.py` (SPY dedup on write) |
| Engines | `src/engines/{flow,mp,energy,structure,elder}.py` (warmup-NaN masks; align-helpers dedup; flow variable rename) |
| Scanner | `src/scanner/{signal_detector,outcome_tracker,score_runner}.py` (NaN handling, gap-stop logic, groupby perf) |
| Analyzer | `src/analyzer/metrics.py` (paper vs realised win rate, Wilson + bootstrap CIs, edge helpers) |
| Analyzer | `src/analyzer/baselines.py` (NEW: random-entry + SPY same-window) |
| UI | `src/ui/streamlit_app.py` (full rewrite — labels, glossary, compare flow, drill-down, refresh expander, onboarding) |
| Tests | `tests/test_{utils,smoke_endtoend}.py` (gap-stop, NaN warmup, baselines, ATR-handcalc fix) |

The committee's 23 numbered findings → 8 task buckets → all closed and verified end-to-end on real FMP data.
