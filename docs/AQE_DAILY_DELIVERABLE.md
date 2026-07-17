# AQE Daily Deliverable — What Gets Shipped, Every Day

**Purpose:** the technical description of what AQE produces each trading day, how it
gets there, and who reads it. For the math behind any individual field, see
`AQE_FIELD_GLOSSARY.md`. For a running list of what changed recently, see the weekly
changelog (`AQE_CHANGELOG_*.md`).

---

## 1. What AQE is

A production daily scanner for ~600+ US equities. Every trading night it pulls fresh
price data, runs five proprietary engines plus a Stage-1 screen and two composite
scores, grades sector rotation, reads the macro tape, and produces one self-describing
JSON — the single artifact the PM/AIC committee reads to run the book. AQE computes
data and levels. **It does not decide, size, or gate a trade** — that judgment stays
with the committee.

---

## 2. The daily pipeline (`src/pipeline/daily_orchestrator.py`)

Runs on two independent schedules that never overlap, sharing state via Drive so the
second never contradicts the first:

| Trigger | When (SGT) | What |
|---|---|---|
| In-app scheduler (HF Space) | 08:30, Tue–Sat | Primary run |
| GitHub Actions backstop | 09:30, Tue–Sat | Runs only if the Space hasn't already run today (catches a sleeping/restarted container) |
| Universe options theta scan | 05:30, Tue–Sat | Separate job, ~1h after US close — never contends with the 08:30 run |
| Weekly MA proximity scan | Daily now (was weekly) | Decoupled from the pipeline's critical path |

**Steps, in order:**
1. **PTJ pull** — the day's held-positions journal from Drive (dated `aegis_trade_journal_YYYY-MM-DD_PTJ.json`; the separate `ARCHIVE_master.json` running summary is explicitly excluded from selection).
2. **Incremental price pull** — daily bars for the fixed, manually-curated universe (+ GICS sector ETFs, thematic-basket constituents, and every currently-held ticker, even ones outside the curated universe).
3. **Earnings calendar refresh.**
4. **Score-cache refresh** — keeps `scores_daily.parquet` current with the panel.
5. **Pipeline Rank screen** — Stage-1 filter over the full universe (`pipe_rank ≥ 60` advances); held names are force-added regardless of rank so Health can always be computed for an open position.
6. **Full scoring** — Flow/Energy/Structure/MP/Elder/BQ/K39 + SC_MOMENTUM/SC_POSITION composites for every advancing + held ticker.
7. **SRM sector grading** — 11 GICS sectors + RRG + macro overlay + 35 thematic baskets.
8. **Regime detection** — VIX bucket + Hurst exponent (SPY).
9. **PTRS + disposition** per candidate.
10. **Recipe screens** — longlist, near-miss watchlist, Precision Edge.
11. **Output + Drive export** — the JSON described below, published and schema-validated before it ships.
12. **Daily-persist snapshot** — zips the day's parquets/outputs to Drive so a container restart restores state in seconds instead of a full re-pull.

---

## 3. The artifact: `aqe_daily_export.json`

One file, overwritten each run (no date-stamped clutter), written to `output/`
locally and to a single pinned Drive folder. This is the file the committee reads.

### Top-level shape (current, ~24 keys)

| Key | What it is |
|---|---|
| `date`, `exported_at`, `market` | Run identity — SGT timestamp, since the desk is Singapore-based reading a US close-of-day scan |
| `regime` | VIX bucket + Hurst regime (TRENDING/MEAN_REVERT/RANDOM) + plain-English implication |
| `intermarket` | Raw COB numbers only (UUP/TLT/HYG, SPY-IWM spread) — **no assessment**, the committee interprets |
| `srm` | All 11 GICS sectors graded (DEPLOY→AVOID) + RRG quadrant/direction + macro headwind + combined entry gate |
| `srm_signals` | The same grades bucketed into deploy/hold/turning/watch/avoid/blocked ETF lists |
| `macro_weather` | TLT/UUP/HYG/IWM/GLD/CPER/USO direction reads + the copper/gold reflation tell |
| `thematic_baskets` | 35 thematic baskets (Mag7, AI Infra, Semiconductors, …), each graded and capped at its parent GICS sector — context only, never adds scan names |
| `daily_list` | **Part 2 of the AIC read** — every scored ticker, full field set (see §4) |
| `lens_ranking` | **Part 1 of the AIC read** (new, see §5) — every scored name ordered by lens agreement |
| `held_positions` | The PM's actual open book (from PTJ) merged with AQE's current engine read on each name |
| `held_book` | Portfolio Hedge Layer — beta-adjusted book exposure, gap-loss scenarios, sector weights |
| `held_positions_status` | `live` / `cache_fallback` / `unknown` — was this run's held-book read a genuine fresh pull? |
| `signal_radar`, `_radar_pool` | Detection-rate tags (runner/premove) across the full scored universe |
| `summary` | Headline counts — daily/longlist/elder/ledger/held, + `data_quality.flagged_count` |
| `data_quality` | Records with a null core field despite being scored — visible, never silent |
| `field_schema`, `field_schema_enums`, `field_glossary` | The export is **self-describing**: every field's role/unit/side + a prose one-liner, shipped in the same file |
| `regime_stop_pct_ceiling`, `spy_roc_20d`, `sector_map_version`, `sector_map_gaps` | Supporting context/versioning |

### `daily_list` — what's on every row

Roughly 60 fields per ticker, grouped:
- **Identity + rank**: ticker, rank, source, PE flag, sector.
- **Composite scores**: `sc_momentum`, `ptrs`, `pipe_rank`, and the five engine reads (Flow/Energy/Structure/MP/Elder) plus BQ/K39 where relevant, with per-engine **gate breakdown** (which specific floor a name is failing, not just pass/fail).
- **`subcomponents`** — the ~46 nightly sub-scores behind the six engine reads (squeeze, MFI/CMF, ADX, RS-vs-SPY, base quality, MA stack…), so the committee sees *why* an engine scored what it did.
- **THE BRACKET** — one nested object: the operative stop (tightest structural level passing all 3 charter gates), the target ladder, R:R, volume-validated levels. This is the single source of truth for stop/targets; mechanical DSL/TP fields are retired.
- **DETECT layer** — `structure_shift` (BOS/CHoCH), `div_state` (price/oscillator divergence), `pin_bar_state`/`inside_bar`, `choch_state` + kNN instance-based confidence, `mp_accel` (momentum acceleration). Data only, never a gate.
- **`lens`, `lens_positive`, `lens_warnings`** — the new reading aid (§5).
- **Signal Radar tags** — `runner_setup`/`premove_setup` + conviction, detection-rate labels, never sizing.
- **Sector/thematic context** — GICS gate, sector trend state, RRG quadrant/direction, primary thematic basket.
- **Risk context** — beta (30d/60d/252d), realised vol, RS-vs-SPY on down days, ATR/malformed-bracket caution flags.

### `held_positions` — the same suite, plus the trade itself

Every currently-open position (from the PM's PTJ, IBKR + Tiger) carries the trade
(entry/qty/SL/TP/unrealised) **and** the identical engine read described above —
including for tickers that have dropped out of (or never were in) the curated
universe; AQE sources their bars specifically because they're held. Options/hedge
legs (covered calls, put spreads) ride along with their raw trade data but are
excluded from the equity-scoring fields and from the `data_quality` guard — an
option can't have an SC_MOMENTUM score, and flagging that as a "gap" would be noise.

Additionally carries `hl_score`/`hl_state` — **Health**, the HOLD decision (trend
integrity of an open position), shown nowhere else.

---

## 4. The three-stage decision framework

AQE's fields answer three distinct questions, deliberately kept separate:

1. **DETECT** — is a move brewing? (Signal Radar tags — detection, not entry.)
2. **ENTER** — is it time to buy, and where? (the bracket + live alert engine.)
3. **HOLD** — should an open position stay on? (Health, held-only.)

AQE supplies data and levels at every stage. It makes no decision at any of them.

---

## 5. Lens consensus (shipped 2026-07-17)

The newest addition: `lens_ranking` (new, top-level) orders every scored name by how
many of 6 lenses — leadership, coil, insti_money, structure, resistance, sector —
read `strong`. Every `daily_list` row gains `lens`/`lens_positive`/`lens_warnings` to
match. **Unweighted, zero fitted parameters** (four attempts to fit weights all
failed pre-launch) — it's a reading aid for where to start looking, not a ranking
model, and it never cuts, caps, filters, or eliminates a name. `extension` is
deliberately excluded from the count — the voices disagree on what it means, so AQE
prints the raw numbers and makes no call, the same treatment now also applied to the
`structure` lens (reads `structure_shift` alone, PM ruling 2026-07-17: *"you do not
decide, you present"*).

---

## 6. Data-integrity guarantees

Three layers, each catching a different failure mode:

1. **Schema key guard** (`_REQUIRED_FIELDS`) — blocks the entire export if a required
   field is structurally missing from a record. Catches code bugs (schema drift).
2. **Value-level `data_quality` guard** — flags (never blocks) any `daily_list` or
   `held_positions` STK record where a core engine field (`sc_momentum`, `flow`,
   `energy`, `structure`, `mp`, `elder`, `entry`, `atr_14d`, `bracket`) came back
   null despite the ticker having gone through full scoring. Catches data gaps
   (thin history, an FMP gap) that the key guard can't see. Never blocks — a single
   thin-history ticker must not take down the whole nightly feed — but it's surfaced
   loudly: the pipeline log, the export JSON, and a Scanner UI warning banner.
3. **PTJ fetch-status tracking** (`held_positions_status`) — a failed live Drive
   fetch of the day's trade journal preserves the last-known-good cache instead of
   silently rendering an empty (indistinguishable-from-flat) held book, and stamps
   whether this run's read was actually live.

---

## 7. Who reads it

- **The PM/AIC committee** — the Drive JSON directly, or via the Scanner UI's
  "exactly what AIC receives" panel (verbatim render of the export).
- **Scanner UI** (`src/ui/1_Scanner.py`) — Streamlit multi-page app: regime, SRM,
  Thematic Rotation, the combined Signals table (longlist ∪ watchlist, slider-
  filterable), Elder list, held positions + hedge layer.
- **Live alert engine** — polls FMP every 15 min for the monitored set (every
  export ticker + held positions), emails on three bounded level events (buy-price
  hit, fresh breakout, approaching-stop). Freshness-gated against a stale export.
- **Pricer page** — a pure bracket calculator for any typed-in ticker (universe or
  not), same engine suite as the export.
- **Intraday plan / options income-wheel chat skills** — separate, recommend-only
  layers that read the export's structural levels but place no orders.

---

*This document describes the deliverable's shape and intent. For per-field formulas
see `AQE_FIELD_GLOSSARY.md`; for what changed and why, see the weekly changelog.*
