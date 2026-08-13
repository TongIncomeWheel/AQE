# AQE Data Taxonomy

**Every data point AQE computes and every place it lands.**

Generated 2026-08-13 11:27 SGT by `scripts/build_data_taxonomy.py`. Do not hand-edit —
regenerate it. Each row records where its definition came from, so a field
known only from a sample file is visibly weaker evidence than one carried by
the export's own glossary.

**146 distinct fields** across 17 groups.

---

## 1 · Where the data lands

One destination: **`aegis/output/`** in this repository. One copy of each file, overwritten in place, no dated filenames.

| Artifact | What it carries |
|---|---|
| `aqe_daily_export.json` | The committee's read — every block in section 2. |
| `aqe_crown_macro.json` | Crown macro reading copy: plain English first, series stripped. |
| `crown_macro.json` | Crown runtime record, with the chart series. |
| `macro_scenarios.json` | The Crown x Macro Weather merge point — 7 ranked scenarios. |
| `qs_daily.json` | Quiet Strength standalone artifact. |
| `shortlist.json` | The pre-export shortlist. |
| `held_positions.json` | The PM's live book as read from the journal. |
| `aqe_sector_map.json` | GICS sector map, rich form. |
| `options_scan.json` | Universe CSP theta sweep. |
| `aqe_last_run.json` | Run marker the status bar reads. |

The heavy runtime state (`panel_daily`, `ma_panel`, `scores_daily`, `aqe.db`)
is **not** in this folder. It rides in a GitHub release asset on the
`state-snapshot` tag, because a daily binary of that size committed to the
repo would grow git history permanently. See `docs/AQE_GITHUB_AS_STORE.md`.

---

## 2 · Export structure — the 25 top-level blocks

| Block | What it is |
|---|---|
| `date` | Scan date, US market close. |
| `exported_at` | When this file was written (SGT). |
| `market` | One-line market descriptor. |
| `regime` | VIX bucket + Hurst regime detection, and the size ceiling it implies. |
| `intermarket` | Cross-asset context read. |
| `srm` | Sector Rotation Model — one row per GICS sector, graded. |
| `srm_signals` | Sector-level signals derived from the SRM grid. |
| `macro_weather` | The 7-instrument cross-asset direction read (TLT/UUP/HYG/IWM/GLD/CPER/USO). |
| `regime_stop_pct_ceiling` | Regime-implied ceiling on stop width, in percent. |
| `spy_roc_20d` | SPY 20-day rate of change — the benchmark move. |
| `thematic_baskets` | The 35 thematic baskets with grades and RRG position. |
| `sector_map_version` | Version stamp of the GICS sector map in force. |
| `sector_map_gaps` | Tickers the sector map could not classify. Empty is the goal. |
| `field_schema` | The export describing its own field types. |
| `field_schema_enums` | Every permitted value for each categorical field. |
| `field_glossary` | The export describing what each field means. |
| `held_positions_status` | live / cache_fallback / unknown — whether this run's PTJ fetch was genuinely fresh. |
| `held_positions` | The PM's live book, as read from the trade journal. |
| `held_book` | Portfolio hedge layer — beta-adjusted exposure, gap scenarios, sector weights. |
| `daily_list` | THE list. Every scored ticker with the full field set. Membership of Longlist / Elder / QS / ledger is a flag on the row, never a separate list. |
| `lens_ranking` | The same names ordered by how many lenses agree. A reading order, not a verdict. |
| `summary` | Counts and headline figures for the run. |
| `signal_radar` | Radar tag totals across the scored universe. |
| `data_quality` | Records carrying a null core field despite being scored. The loud-failure guard. |
| `_radar_pool` | Internal radar pool sample. Diagnostic, not a read. |

### The one-list rule

`daily_list` is the single list every surface reads. Longlist, Elder, QS,
ledger and held are **flags on the row** (`on_longlist`, `on_elder`, `on_qs`,
`in_ledger`, `held`), never parallel lists. Every row carries the identical
AQE block from the same builder, so levels cannot disagree between lists.

An **absent** `qs` key means QS could not evaluate that name. That is not the
same as a poor QS score, and the two must not be read alike.

---

## 3 · Every field, by group

### Identity and rank — 12 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `entry` | `{'role': 'reference', 'unit': 'usd', 'side': 'at_entry'}` |  | Reference entry = prior close-of-day. The live fill is the IBKR price at bracket time, NOT this value. | export field_schema, export field_glossary, observed in export |
| `held` | `bool` |  | Flag: name is currently held. | agentic glossary, observed in export |
| `held_sl` |  |  | (held_positions only) The trade's OWN stop as tracked by the PM/broker in the Aegis journal — `stop_live_broker` if the broker confirms one, else the journal's `stop_reference`. This is the position's actual working stop, NOT AQE's structural read (that's `bracket.stop`); the two can legitimately disagree — `stop_match` upstream flags it. | export field_glossary |
| `held_tp1` |  |  | (held_positions only) PM ruling 2026-07-29: the Aegis journal's own tp1 is unpopulated on held names, so this is AQE's own computed bracket.targets TP1 price instead of an empty field. Null when the bracket has no valid TP1 (see bracket.valid). | export field_glossary |
| `held_tp2` |  |  | (held_positions only) Same as held_tp1, but bracket.targets TP2. | export field_glossary |
| `in_ledger` | `bool` |  | Flag: name is currently tracked in the nomination ledger. | agentic glossary, observed in export |
| `on_elder` | `bool` |  | Flag: name is on the Elder list. | agentic glossary, observed in export |
| `on_longlist` | `bool` |  | Flag: name is on the longlist. | agentic glossary, observed in export |
| `on_qs` |  |  | TRUE if the name cleared QS's emit rule today (>=2 recipe hits AND conviction >=2, or vetoed-and-shown). Membership flag on the ONE daily_list — Longlist/Elder/QS are lenses on one list, not parallel lists. A name can carry any combination. | export field_glossary |
| `rank` | `int` |  | Overall daily rank of the name in the scored universe. | agentic glossary, observed in export |
| `source` | `str` |  | Data-source tag for the record. | agentic glossary, observed in export |
| `ticker` | `str` |  |  | observed in export |

### Composite scores — 9 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `floor` | `float` |  | UNDOCUMENTED — AQE owner to define (meaning not recoverable from code comments). | agentic glossary, observed in export |
| `pipe_rank` | `float` |  | Momentum-pipeline rank (pipeline_rank.py). | agentic glossary, observed in export |
| `ptrs` | `float` |  | = SC_MOMENTUM verbatim (PM ruling: the Sector-Health adjustment is DROPPED — sector context is read separately and qualitatively via `srm`/RRG, not double-counted into a per-ticker score). Disposition/sizing is the committee's call — AQE exports no sizing. | export field_glossary, observed in export |
| `sc_m_gate_detail` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | Per-engine SC_MOMENTUM gate pass/fail (dict): {flow, energy, structure, mp, elder} each True/False vs the SC_M_GATES threshold — so you read WHICH check a name is failing without recomputing. false = that engine is below its floor. | export field_schema, export field_glossary, observed in export |
| `sc_m_gates` | `{'role': 'signal', 'unit': 'boolean', 'side': 'n/a'}` |  | SC_MOMENTUM qualification gate (bool): True iff EVERY engine floor passes — Flow≥60, Energy≥60, Structure≥55, MP≥55, Elder≥6.5 (Pine SC_M_GATES). It does NOT cap the score (composite is uncapped); it flags whether the momentum read is fully gated. See sc_m_gate_detail for which specific check fails. | export field_schema, export field_glossary, observed in export |
| `sc_momentum` | `float` |  | SC_MOMENTUM composite [0,100], uncapped weighted average of flow/energy/structure/mp/elder (scoring.py v1.8.0); floors not applied to the composite, Elder gate enforced at qualification. | agentic glossary, observed in export |
| `sc_momentum_raw` | `float` |  | The ungated SC_MOMENTUM weighted average (== sc_momentum in v1.8.0). | agentic glossary, observed in export |
| `sc_p_gate_detail` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | Per-engine SC_POSITION gate pass/fail (dict): {flow, energy, structure, mp, bq, k39} each True/False vs the SC_P_GATES threshold (k39 = the weekly confirmation gate; null if unavailable). | export field_schema, export field_glossary, observed in export |
| `sc_p_gates` | `{'role': 'signal', 'unit': 'boolean', 'side': 'n/a'}` |  | SC_POSITION qualification gate (bool): True iff every engine floor passes — Flow≥40, Energy≥60, Structure≥65, MP≥40, BQ≥60 (Pine SC_P_GATES) AND the K39 weekly gate. Does NOT cap the score. See sc_p_gate_detail for the breakdown. | export field_schema, export field_glossary, observed in export |

### The five engines — 13 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `elder` | `float` |  | Elder Impulse score [0,10] (elder.py): state{0,2,4}+slope{0-3}+MACD-histogram{0-3}. | agentic glossary, observed in export |
| `elder_5d` | `list` |  | Elder impulse read over a 5-day context (list of recent impulse states). | agentic glossary, observed in export |
| `elder_context` | `dict` |  | Hourly VWAP/VCP/exhaustion context object behind the elder read (elder_context.py). | agentic glossary, observed in export |
| `elder_pattern` | `str` | `ACCELERATION` · `ACCUMULATION_BASE` · `CORRECTION_REENTRY` · `INTERRUPTED` · `SUSTAINED` | Labelled Elder impulse pattern (see enum). | agentic glossary, enum set, observed in export |
| `energy` | `float` |  | Energy engine [0,100] (energy.py): range-position proxy + price-action + squeeze + exhaustion + ATR. | agentic glossary, observed in export |
| `flow` | `float` |  | Flow engine [0,100] (flow.py): MFI+CMF+Heikin-Ashi quality + A/D linreg + volume trend/spike + up/down skew. | agentic glossary, observed in export |
| `mp` | `float` |  | Momentum Persistence [0,100] (mp.py): abs_mom+ADX+rel_mom+trend. | agentic glossary, observed in export |
| `mp_accel` | `{'role': 'signal', 'unit': 'decimal', 'side': 'n/a'}` |  | Momentum ACCELERATION (2nd derivative): 5-bar change of the MP momentum z-score (roc_zscore), smoothed 3 bars. Positive = momentum itself is building; negative = rolling over. Flags inflection BEFORE the level/mp_state confirms — read alongside mp_state (which is a knife-edge when the score plateaus). Additive diagnostic, not part of the Pine spec. | export field_schema, export field_glossary, observed in export |
| `mp_accel_state` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `ACCELERATING` · `FLAT` · `DECELERATING` | Label for mp_accel with a ±0.10 dead-zone: ACCELERATING / DECELERATING / FLAT. | export field_schema, export field_glossary, enum set, observed in export |
| `mp_state` | `str` | `BUILDING` · `STRONG` · `FADING` | Momentum-persistence phase label (mp.py). | agentic glossary, enum set, observed in export |
| `structure` | `float` |  | Structure engine [0,100] (structure.py): clip((rs_spy+rs_accel+base+ms_pos+resist+wk+earn)/95*100). | agentic glossary, observed in export |
| `structure_shift` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `RANGE` · `BULLISH_BOS` · `ABOVE_STRUCTURE` · `BEARISH_CHOCH` | BOS/CHoCH read vs the CONFIRMED anchors (data only, never a gate): BULLISH_BOS = COB close is above the last CONFIRMED pivot high AND still within 2% of it — a break that JUST HAPPENED; ABOVE_STRUCTURE = above that pivot but further than 2% past it — it broke out earlier and kept running, which is a state, not an event; BEARISH_CHOCH = close broke BELOW the up-swing's anchor low (character chan… | export field_schema, export field_glossary, enum set, observed in export |
| `structure_shift_ref` | `{'role': 'reference', 'unit': 'usd', 'side': 'n/a'}` |  | The level the shift is measured against (USD): the broken confirmed pivot high for BULLISH_BOS/ABOVE_STRUCTURE, the broken swing anchor low for BEARISH_CHOCH; null for RANGE. | export field_schema, export field_glossary, observed in export |

### Structural bracket — 3 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `atr_caution` | `{'role': 'flag', 'unit': 'boolean', 'side': 'n/a'}` |  | True if the structural stop was too tight for the regime (risk% near the regime ceiling). | export field_schema, export field_glossary, observed in export |
| `bracket` | `{'role': 'stop', 'unit': 'usd', 'side': 'below_entry'}` |  | THE bracket — the single source of truth for stop + targets (mechanical DSL/TP is retired). A nested object: {price, price_source (eod_close on the daily run / live_15min on a live pull), stop, stop_type (swing_low/ma/fib that the stop sits on), stop_atr_dist (risk in ATRs — read this, not raw USD), risk (=price−stop, the R unit to size against), risk_pct, targets[{type,tp (TP1/2/3),price,r,atr… | export field_schema, export field_glossary, observed in export |
| `malformed_bracket` | `{'role': 'flag', 'unit': 'boolean', 'side': 'n/a'}` |  | True if the structural stop sits within 0.5% of price (bracket unusable — stop virtually at entry). | export field_schema, export field_glossary, observed in export |

### Levels and moving averages — 16 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `fib_236` | `{'role': 'fib_support', 'unit': 'usd', 'side': 'n/a'}` |  | 23.6% Fibonacci retracement of swing_low->swing_high (USD). | export field_schema, agentic glossary, observed in export |
| `fib_236/382/500/618/786` |  |  | Fib RETRACEMENT supports below the swing high — potential pullback/STOP levels (absolute USD). | export field_glossary |
| `fib_382` | `{'role': 'fib_support', 'unit': 'usd', 'side': 'n/a'}` |  | 38.2% Fibonacci retracement (USD). | export field_schema, agentic glossary, observed in export |
| `fib_500` | `{'role': 'fib_support', 'unit': 'usd', 'side': 'n/a'}` |  | 50% retracement (USD). | export field_schema, agentic glossary, observed in export |
| `fib_618` | `{'role': 'fib_support', 'unit': 'usd', 'side': 'n/a'}` |  | 61.8% Fibonacci retracement (USD). | export field_schema, agentic glossary, observed in export |
| `fib_786` | `{'role': 'fib_support', 'unit': 'usd', 'side': 'n/a'}` |  | 78.6% Fibonacci retracement (USD). | export field_schema, agentic glossary, observed in export |
| `fib_swing_high` | `{'role': 'reference', 'unit': 'usd', 'side': 'n/a'}` |  | Upper anchor (swing high) of the Fibonacci retracement. | export field_schema, agentic glossary, observed in export |
| `fib_swing_low` | `{'role': 'reference', 'unit': 'usd', 'side': 'n/a'}` |  | Lower anchor (swing low) of the Fibonacci retracement. | export field_schema, agentic glossary, observed in export |
| `fib_swing_low/high` |  |  | Anchors of the current detected up-swing (absolute USD). | export field_glossary |
| `last_pivot_high` | `{'role': 'reference', 'unit': 'usd', 'side': 'n/a'}` |  | {price, date} — the MOST RECENT confirmed fractal pivot high, wherever it sits relative to today's close. The ceiling the name last had to clear. This is what structure_shift is measured against, and what the live NEAR_BREAKOUT alert watches price climb into. Shipped from 2026-08-06: it was computed and discarded before, so NEAR_BREAKOUT read a key that was not on any row and could never fire. | export field_schema, export field_glossary |
| `ma_100` | `{'role': 'moving_average', 'unit': 'usd', 'side': 'n/a'}` |  | 100-day simple moving average of close. | export field_schema, agentic glossary, observed in export |
| `ma_20` | `{'role': 'moving_average', 'unit': 'usd', 'side': 'n/a'}` |  | 20-day simple moving average of close. | export field_schema, agentic glossary, observed in export |
| `ma_20/50/100/200` |  |  | Simple moving averages (absolute USD) — dynamic support/resistance. | export field_glossary |
| `ma_200` | `{'role': 'moving_average', 'unit': 'usd', 'side': 'n/a'}` |  | 200-day simple moving average of close. | export field_schema, agentic glossary, observed in export |
| `ma_50` | `{'role': 'moving_average', 'unit': 'usd', 'side': 'n/a'}` |  | 50-day simple moving average of close. | export field_schema, agentic glossary, observed in export |
| `sma_distance_pct` | `float` |  | Percent distance of price from its SMA — extension (large + = extended, ~0 = at support). | agentic glossary, observed in export |

### Volatility and relative strength — 9 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `atr_14d` | `{'role': 'volatility', 'unit': 'usd', 'side': 'n/a'}` |  | 14-day Average True Range in USD (the volatility unit). | export field_schema, export field_glossary, observed in export |
| `beta_252d` | `{'role': 'risk_metric', 'unit': 'ratio', 'side': 'n/a'}` |  | 1-year beta vs SPY (cov/var). | export field_schema, export field_glossary, observed in export |
| `beta_30d` | `float` |  | 30-day beta vs SPY — the portfolio-gate window (D-6). | agentic glossary, observed in export |
| `day_vol` |  |  | (formerly `rvol` — same number, same formula, renamed 2026-08-05) The DAY'S VOLUME MULTIPLE: today's volume divided by this name's own prior 20-day average. 1.0 = a normal day for it, 1.8 = it traded 1.8x its own normal. The only volume-participation field on the row — there is deliberately no second one under another name. Charter docs, archived exports and voice menus written before the renam… | export field_glossary, agentic glossary |
| `rs_down_day_20d` | `{'role': 'signal', 'unit': 'pct', 'side': 'n/a'}` |  | All-weather leadership: stock's avg outperformance vs SPY on SPY DOWN days (last 20 sessions). Positive = beats SPY when market drops = genuine leader (pct). | export field_schema, export field_glossary, observed in export |
| `rs_leadership` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `LEADER` · `IN-LINE` · `LAGGARD` | Classification from rs_down_day_20d: LEADER (>+0.25), IN-LINE, LAGGARD (<−0.25). | export field_schema, export field_glossary, enum set, observed in export |
| `rs_spy_20d` | `float` |  | 20-day relative strength vs SPY (%). | agentic glossary, observed in export |
| `rvol` | `float` |  |  | observed in export |
| `vol_30d_ann` | `{'role': 'volatility', 'unit': 'decimal', 'side': 'n/a'}` |  | 30-day annualised realised volatility (decimal: 0.18 = 18%). This IS the Charter §4.5 operative sizing vol (the charter calls it 'vol_30d'; AQE's field is annualised — same number). Forsizing/VaR, not a target. | export field_schema, export field_glossary, observed in export |

### DETECT layer — 18 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `choch_date` | `{'role': 'reference', 'unit': 'date', 'side': 'n/a'}` |  | Date of the latest CHoCH event (null when choch_state=NONE). | export field_schema, export field_glossary, observed in export |
| `choch_state` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `BULLISH` · `BEARISH` · `NONE` | Change-of-Character (swing-break trend flip), the LATEST detected event: BULLISH = close broke above the last confirmed swing high while the prior trend was flat/down; BEARISH mirrors it (broke below swing low). NONE = no CHoCH detected. Non-repainting (confirmed pivots only). | export field_schema, export field_glossary, enum set, observed in export |
| `div_bear_count` | `{'role': 'signal', 'unit': 'score', 'side': 'n/a'}` |  | How many of the 5 oscillators confirm the bearish divergence (0-5). | export field_schema, export field_glossary, observed in export |
| `div_bull_count` | `{'role': 'signal', 'unit': 'score', 'side': 'n/a'}` |  | How many of the 5 oscillators confirm the bullish divergence (0-5). More confirming oscillators = stronger read. | export field_schema, export field_glossary, observed in export |
| `div_date` | `{'role': 'reference', 'unit': 'date', 'side': 'n/a'}` |  | Date of the confirming (newer) pivot anchoring the divergence. | export field_schema, export field_glossary, observed in export |
| `div_oscs` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | Which oscillators fired, comma-joined — bullish names bare, bearish names prefixed '-' (e.g. 'rsi,mfi,-obv'). Null when none. | export field_schema, export field_glossary, observed in export |
| `div_state` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `BULLISH` · `BEARISH` · `MIXED` · `NONE` | Regular price-vs-oscillator DIVERGENCE at the last close (non-repainting: confirmed pivots only, freshness-gated ~10 bars): BULLISH = price made a lower pivot low while ≥1 oscillator made a higher low (downmove losing internal energy); BEARISH mirror on highs; MIXED = both; NONE. Oscillators tested: RSI, MFI, CMF, MACD, OBV — all AQE-computed. Context only, never a gate. | export field_schema, export field_glossary, enum set, observed in export |
| `inside_bar` | `{'role': 'flag', 'unit': 'boolean', 'side': 'n/a'}` |  | True if the LAST bar's range is fully inside the PRIOR bar's range (high < prev_high AND low > prev_low) — a one-bar consolidation pause. | export field_schema, export field_glossary, observed in export |
| `knn_neighbors_used` | `{'role': 'signal', 'unit': 'score', 'side': 'n/a'}` |  | How many historical analog events the knn_prob is averaged over (0 if none found). | export field_schema, export field_glossary, observed in export |
| `knn_prob` | `{'role': 'signal', 'unit': 'ratio', 'side': 'n/a'}` |  | K-NEAREST-NEIGHBORS directional probability (0-1) for the current CHoCH: the win-rate of the K most similar HISTORICAL CHoCH events on this SAME ticker (matched on 3 features — volume-delta, ATR-normalised displacement, velocity — via Euclidean distance), where 'win' = the move's max favorable excursion exceeded its max adverse excursion within a fixed lookahead. This IS genuine instance-based … | export field_schema, export field_glossary, observed in export |
| `knn_significant` | `{'role': 'flag', 'unit': 'boolean', 'side': 'n/a'}` |  | True iff knn_prob clears a fixed threshold in either direction (≥60% or ≤40% by default). CAVEAT (AIC Charter Amendment v2.8, 2026-07-15 ruling): this is a plain threshold check on a SMALL neighbor count (k=5 by default), NOT a statistical significance test — at k=5, 3-of-5 agreeing clears the 60% bar trivially, including by chance. Carries no p-value or confidence-interval semantics. Read as '… | export field_schema, export field_glossary, observed in export |
| `knn_tp1` | `{'role': 'target', 'unit': 'usd', 'side': 'n/a'}` |  | Nearest kNN-implied target (USD): current price ± half the neighbors' mean favorable excursion, signed by the CHoCH direction. A statistical projection from historical analogs, NOT a structural level — read alongside bracket.targets, never in place of them. | export field_schema, export field_glossary, observed in export |
| `knn_tp2` | `{'role': 'target', 'unit': 'usd', 'side': 'n/a'}` |  | Mid kNN-implied target: current price ± the neighbors' MEDIAN favorable excursion, signed by direction. | export field_schema, export field_glossary, observed in export |
| `knn_tp3` | `{'role': 'target', 'unit': 'usd', 'side': 'n/a'}` |  | Far kNN-implied target: current price ± the neighbors' 75th-percentile favorable excursion, signed by direction. | export field_schema, export field_glossary, observed in export |
| `pib_pattern` | `{'role': 'flag', 'unit': 'boolean', 'side': 'n/a'}` |  | True if the SECOND-TO-LAST bar was a pin bar AND the last bar is an inside bar relative to it — the 'rejection, then pause' combo pattern. Independent of pin_bar_state (which only reads the LAST bar itself). | export field_schema, export field_glossary, observed in export |
| `pin_bar_date` | `{'role': 'reference', 'unit': 'date', 'side': 'n/a'}` |  | Date of the pin bar (null when pin_bar_state=NONE). | export field_schema, export field_glossary, observed in export |
| `pin_bar_level` | `{'role': 'reference', 'unit': 'usd', 'side': 'n/a'}` |  | The pin bar's rejection extreme (USD): the LOW for a bullish pin (a candidate support), the HIGH for a bearish pin (candidate resistance). Null when pin_bar_state=NONE. | export field_schema, export field_glossary, observed in export |
| `pin_bar_state` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `NONE` · `BULLISH_PIN` · `BEARISH_PIN` | Candlestick REJECTION pattern on the LAST closed bar (pure geometry, no lookahead): BULLISH_PIN = long lower wick (≥66% of range) + small body (≤40%) + small upper wick (≤40%) — the market pushed down and got rejected; BEARISH_PIN mirrors it (long upper wick). NONE = no pattern. Filtered so the bar's range must be ≥2× the prior bar's range (rejects 'pin bars' that are just noise inside an alrea… | export field_schema, export field_glossary, enum set, observed in export |

### Signal Radar — 7 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `mover_subtype` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | DETECTION sub-type label (explosive / trend / tight_base / squeeze) — the family whose z-score profile the name matches best (M16c). Context only; not a gate. | export field_schema, export field_glossary, observed in export |
| `premove_conviction` | `{'role': 'signal', 'unit': 'score', 'side': 'n/a'}` |  | DETECTION conviction (0-4): count of M18 launcher-fingerprint legs present. Context only; not a probability of profit. | export field_schema, export field_glossary, observed in export |
| `premove_conviction_label` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | Human-readable pre-move conviction = word + number, e.g. 'HIGH (3/4)' (MINIMAL 0 / LOW 1 / MODERATE 2 / HIGH 3 / MAX 4). Read this, not the bare number. Detection tag, not a win rate, not sizing. | export field_schema, export field_glossary, observed in export |
| `premove_setup` | `{'role': 'signal', 'unit': 'boolean', 'side': 'n/a'}` |  | DETECTION tag (bool): name is QUIET now but coiled to launch — very young base + squeeze on + well below the recent high (M18 rule, applies only to quiet-pond names). Historical launches came a median ~12 trading days after the tag — a pre-move radar, not a same-day trigger. NOT a gate, NOT sizing; % elsewhere = detection rate, not win rate. | export field_schema, export field_glossary, observed in export |
| `runner_conviction` | `{'role': 'signal', 'unit': 'score', 'side': 'n/a'}` |  | DETECTION conviction (0-4): how many of the four M15 legs (short base / strong 5d momentum / clear overhead / room below the 20d high) are in their favourable tercile. Higher = stronger historical detection, not a probability of profit. | export field_schema, export field_glossary, observed in export |
| `runner_conviction_label` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | Human-readable conviction = word + number, e.g. 'HIGH (3/4)'. The word is anchored to the historical +20%/20d detection ladder (MINIMAL 0 / LOW 1 / MODERATE 2 / HIGH 3 / MAX 4 ~= 5/13/27/43% detection). Read this, not the bare number. Still a detection tag, not a win rate, not sizing. | export field_schema, export field_glossary, observed in export |
| `runner_setup` | `{'role': 'signal', 'unit': 'boolean', 'side': 'n/a'}` |  | DETECTION tag (bool): name is already moving with another leg — short young base + strong 5-day thrust + clear overhead (M15 rule). NOT a gate, NOT sizing; the PM decides entry/bracket/size live. Any % reported for this tag elsewhere is a DETECTION RATE (how often tagged names historically touched a level, price-path only) — never a win rate. | export field_schema, export field_glossary, observed in export |

### Chart patterns — 18 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `candle_d` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | CANDLESTICK LENS, DAILY — the shape of the LAST completed daily bar, or null for an ordinary bar. A visual flag like `pattern`: no probability, no gate. Three-bar reads beat two-bar reads beat single-candle reads (widest context wins). Bullish: HAMMER, BULLISH_ENGULFING, PIERCING, BULLISH_HARAMI, MORNING_STAR, THREE_WHITE_SOLDIERS, MARUBOZU_BULL. Bearish: SHOOTING_STAR, BEARISH_ENGULFING, DARK_… | export field_schema, export field_glossary |
| `candle_d_dir` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | BULLISH / BEARISH / NEUTRAL for candle_d. DOJI is NEUTRAL on purpose: open and close level says indecision, and calling that directional would invent a read the bar does not contain. | export field_schema, export field_glossary |
| `candle_w` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | CANDLESTICK LENS, WEEKLY — the same read on the last completed WEEKLY bar, from panel_weekly. Kept as its own column and NEVER merged with candle_d: a weekly engulfing is five sessions of agreement, a daily one is a single session, and collapsing them would destroy the difference that makes the weekly worth reading. Null when the weekly panel is absent — which is a data gap, not an ordinary bar. | export field_schema, export field_glossary |
| `candle_w_date` | `{'role': 'signal', 'unit': 'date', 'side': 'n/a'}` |  | Date of the weekly bar candle_w read — so a stale weekly panel is visible rather than silently reported as this week. | export field_schema, export field_glossary |
| `candle_w_dir` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | BULLISH / BEARISH / NEUTRAL for candle_w. | export field_schema, export field_glossary |
| `pattern` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | CHART-PATTERN LENS — the classic formation this name is currently sitting inside, or null. A VISUAL FLAG (PM ruling 2026-08-06), not a signal: it adds no names, gates nothing, sizes nothing and carries no probability. Either a shape is there or it is not. CUP_HANDLE / DOUBLE_BOTTOM / ASC_TRIANGLE. Built from the CONFIRMED pivot series (the same 11-bar fractals the bracket and structure_shift us… | export field_schema, export field_glossary |
| `pattern_alt` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | Other shapes this same chart also matched, or null. A cup & handle and a double top are the SAME geometry — two highs at a level with a trough between — and differ only in how price resolves, so an ambiguous chart genuinely matches both. Naming the runner-up is more honest than picking one on a tie-break the reader cannot see. NOTE: pattern_fit is only comparable WITHIN a pattern (each shape sc… | export field_schema, export field_glossary |
| `pattern_days` | `{'role': 'signal', 'unit': 'decimal', 'side': 'n/a'}` |  | Days from the start of the formation to today. A textbook cup runs 2-6 months, so this is how you tell a real base from a three-week dip. | export field_schema, export field_glossary |
| `pattern_direction` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | BULLISH or BEARISH. READ THIS BEFORE pattern_trigger: on a bearish shape the trigger is broken DOWNWARD and the invalidation sits ABOVE it, so 'trigger = buy above' is exactly backwards. A lens that only reported bullish shapes would be flattering the chart rather than reading it. | export field_schema, export field_glossary |
| `pattern_fit` | `{'role': 'signal', 'unit': 'score', 'side': 'n/a'}` |  | 0-1, how TEXTBOOK the shape is — cup: depth, rim symmetry, handle size, handle volume; double bottom: how level the two lows are and how real the bounce between them; triangle: how flat the ceiling is, how far the lows have climbed, how many touches. Flat-weighted. NOT a probability and NOT an edge — nothing here says the shape works. It is how closely it matches the textbook drawing, nothing m… | export field_schema, export field_glossary |
| `pattern_invalidation` | `{'role': 'reference', 'unit': 'usd', 'side': 'n/a'}` |  | Below this the shape is gone whatever the fit score says (USD): the handle low (or cup low) for a cup, the lower of the two lows for a double bottom, the LAST rising low for an ascending triangle — the step that would have to fail. | export field_schema, export field_glossary |
| `pattern_stage` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | How far along the shape is. CUP_HANDLE: CUP = both rims formed, no handle yet; HANDLE = the handle low is in and price is drifting under the rim. DOUBLE_BOTTOM: BASE = both lows in, price under the neckline. ASC_TRIANGLE: FORMING = flat ceiling with rising lows under it. TRIGGERED (all three) = price has closed above the trigger level. | export field_schema, export field_glossary |
| `pattern_start` |  |  | Date the formation began (left rim / first low / first ceiling touch). | export field_glossary |
| `pattern_trigger` | `{'role': 'reference', 'unit': 'usd', 'side': 'n/a'}` |  | The level that CONFIRMS the shape (USD): the rim for a cup, the NECKLINE (the peak between the two lows) for a double bottom, the flat ceiling for an ascending triangle. Same kind of object as last_pivot_high. | export field_schema, export field_glossary |
| `pattern_w` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | CHART-PATTERN LENS, WEEKLY — the same nine shapes read off WEEKLY bars. A cup or a head-and-shoulders built from weekly candles is a far bigger claim than the same outline on dailies, so the two are separate columns and never merged. Deliberately LEANER than the daily set: name, direction, stage and the level only. The weekly answers 'is a big base forming?'; the daily carries the actionable de… | export field_schema, export field_glossary |
| `pattern_w_dir` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | BULLISH or BEARISH for pattern_w. Same warning as pattern_direction: on a bearish shape the trigger breaks DOWNWARD. | export field_schema, export field_glossary |
| `pattern_w_stage` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` |  | Stage of the weekly formation — see pattern_stage. | export field_schema, export field_glossary |
| `pattern_w_trigger` | `{'role': 'reference', 'unit': 'usd', 'side': 'n/a'}` |  | The level that would confirm the WEEKLY shape (USD). | export field_schema, export field_glossary |

### Lens consensus — 4 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `lens` | `dict` |  | Per-lens read: strong/ok/warn/-- for leadership, coil, insti_money, structure, resistance, sector. `extension` is ALWAYS null — the voices disagree on what extension means, so AQE prints the numbers (subcomponents.flow.ext_score, energy.en_pos50/exhaustion_score/atr_score) and makes no call. Every verdict comes from a label AQE already computes, or from top/bottom-third position in TODAY's list… | export field_glossary, lens glossary, observed in export |
| `lens_positive` | `int` |  | Count of lenses reading `strong` (0-6). UNWEIGHTED — no weighting was ever earned. Sort on it to tier the read; it is a READING AID, not a prediction, and whether 5-of-6 beats 2-of-6 is untested. Never a gate: nothing is eliminated, every name keeps its full block. | export field_glossary, lens glossary, observed in export |
| `lens_ranking` |  |  | PART 1 of the AIC read — every scored name ordered by how many lenses agree (`positive` desc, then `warnings` asc, then ptrs). A READING ORDER, not a verdict, and not a filter: nothing is eliminated and the count carries no proven edge. The FULL per-name data is Part 2 = `daily_list`, unchanged. | export field_glossary, lens glossary |
| `lens_warnings` | `int` |  | Count of lenses reading `warn` (0-6). | export field_glossary, lens glossary, observed in export |

### Quiet Strength — 10 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `qs` |  |  | The Quiet Strength read (nested). Present on EVERY row QS evaluated, including names it did NOT emit — so a Longlist-only name still shows its QS conviction/probability/lens. ABSENT means QS could not evaluate the name at all (outside the eligible set or no scores), which is NOT the same as a poor QS score. Keys: conviction (0-5) + conviction_word; signal (STRONG/GOOD/WATCH/NONE/SKIP, driven by… | export field_glossary |
| `qs.engine.qs_persist` |  |  | How many of the PRIOR 5 stored sessions the name also qualified as QS (recipe_hits >= 3). An independent conviction dimension: inside identical hits x lens buckets it still adds +0.06..+0.16 to the hit rate. Counted over stored SESSIONS, not calendar days — a market holiday is not a day the name failed. | export field_glossary |
| `qs.engine.recipe_hits` |  |  | How many of the frozen book's 40 recipes the name satisfies. Counts ALL 40 entries, including 8 exact duplicate pairs that are double-counted BY DESIGN — the calibration's hit bands were fitted on this total, so de-duplicating to 32 would drop names a band and understate every probability. | export field_glossary |
| `qs.objective` |  |  | The MECHANICAL yardstick the probability was measured against: target_2atr = close + 2xATR14, give_up_2atr = close - 2xATR14. NOT a trade instruction and NOT the tradeable level set — `bracket` is that (structural, 3-gate validated). The two are different numbers answering different questions; conflating them makes qs.odds.p read as the odds of hitting structural TP2, which it is not. | export field_glossary |
| `qs.odds.extrapolated` |  |  | TRUE when the name sat OUTSIDE today's QS-eligible set (its volume did not beat its own 10-day average). It was still scored, against the eligible cohort's distribution without joining it — so the reference curve stays the measured population — but its probability is a read-across, not a measured analogue. Never emitted. | export field_glossary |
| `qs.odds.p` |  |  | Probability of reaching the QS OBJECTIVE (+2xATR14 within 20 sessions) read from a table of historical look-alikes matched on (recipe_hits band x lens_total band x persistence band). This is p_train, the conservative side; p_test sits beside it as context. NEVER read p without n_analogues behind it, and NEVER read it as the odds of reaching a bracket target — see qs.objective. | export field_glossary |
| `qs.state` |  |  | EARLY = quietly strong, not yet moving. READY = was quietly strong all week, now starting to move. READY+ = READY and STILL qualifying today (the rarer case — most recipes need quiet momentum, so hits normally collapse the moment the move starts). Measured test rates 64.8 / 69.4 / 73.1% vs a 54.8% base. Descriptive: the label feeds nothing, though recipe_hits — which separates READY from READY+… | export field_glossary |
| `qs.unevaluable_vetoes` |  |  | Vetoes that could NOT be evaluated because an input was missing/NaN. The name was not struck (matching the reference, which fails open), but this is recorded so a veto that could not be checked is never mistaken for one that was checked and cleared. | export field_glossary |
| `qs_market` |  |  | The MARKET row, read FIRST because it can cancel the day: plain-English regime description, the base rate the average stock hits its target in this regime, the stance action line, and the regime code as a footnote. STAND_DOWN emits an empty QS list by design. | export field_glossary |
| `qs_status` |  |  | 'live' (QS ran), 'error' (it failed — reason in the pipeline log), or 'not_run'. Distinguishes a QS OUTAGE from a genuinely quiet market. An empty QS list with status='live' means nothing qualified; with status='error' it means nothing was checked. | export field_glossary |

### Sector and thematic — 13 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `gics_gate` | `str` | `PASS` · `WATCH` · `CAUTION` · `BLOCKED` | Sector entry gate PASS/WATCH/CAUTION/BLOCKED (srm.sector_entry_gate: grade+RRG+macro). | agentic glossary, enum set, observed in export |
| `gics_sector` | `str` |  | GICS sector ETF code the name maps to. | agentic glossary, observed in export |
| `gics_sector_name` | `str` |  | GICS sector name. | agentic glossary, observed in export |
| `sector_rrg_direction` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `ENTERING` · `DEEPENING` · `EXITING` | The ticker's sector RRG direction of travel: ENTERING / DEEPENING / EXITING / STABLE. | export field_schema, export field_glossary, enum set, observed in export |
| `sector_rrg_quadrant` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `LEADING` · `WEAKENING` · `LAGGING` · `IMPROVING` | The ticker's sector RRG quadrant vs SPY: LEADING / IMPROVING / WEAKENING / LAGGING. | export field_schema, export field_glossary, enum set, observed in export |
| `sector_trend_state` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `Declining — Avoid` · `Momentum Fading — Hold, Don't Add` · `Recovering From Weakness — Watch for Entry` · `Leading — Deploy` | The ticker's GICS-sector SRM trend-state for the day (e.g. 'Momentum Building — Add' / 'Momentum Fading — Hold' / 'Recovering' / 'Declining'). Context; the gate is gics_gate, unchanged. | export field_schema, export field_glossary, enum set, observed in export |
| `thematic_basket` | `str` |  | Thematic basket the name belongs to (srm thematic layer). | agentic glossary, observed in export |
| `thematic_baskets` | `list` |  | All thematic baskets the name belongs to. Each entry carries grade, grade_path, breadth_pct, parent_capped_grade, parent_gics, parent_grade and RRG. | agentic glossary, observed in export |
| `thematic_grade` | `str` | `DEPLOY` · `HOLD` · `TURNING` · `WATCH` · `AVOID` | The PRIMARY thematic basket's grade — the theme's OWN reading, UNCAPPED since 2026-08-05. It used to be clamped at the parent GICS grade, which with XLK on HOLD made a +13% theme and a flat one read identically; the parent's grade is on the row as thematic_parent_grade, so apply that caution yourself. Each entry in thematic_baskets also carries grade_path (WHICH rule graded it: trend / accelera… | export field_glossary, agentic glossary, enum set, observed in export |
| `thematic_parent_gics` | `str` |  | Parent GICS sector of the thematic basket. | agentic glossary, observed in export |
| `thematic_parent_grade` | `str` | `DEPLOY` · `HOLD` · `TURNING` · `WATCH` · `AVOID` | Grade of the parent GICS sector. | agentic glossary, enum set, observed in export |
| `thematic_rrg_direction` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `ENTERING` · `DEEPENING` · `EXITING` | The ticker's PRIMARY thematic basket's RRG direction (ENTERING / DEEPENING / EXITING / STABLE). | export field_schema, export field_glossary, enum set, observed in export |
| `thematic_rrg_quadrant` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `LEADING` · `WEAKENING` · `LAGGING` · `IMPROVING` | The ticker's PRIMARY thematic basket's RRG quadrant vs SPY (LEADING / IMPROVING / WEAKENING / LAGGING). | export field_schema, export field_glossary, enum set, observed in export |

### Held-position health — 4 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `hl_score` | `{'role': 'signal', 'unit': 'score', 'side': 'n/a'}` |  | Health composite (0-100). Trend integrity of a HELD position — the HOLD decision. HOLD_ADD (75+) / HOLD (50-74) / TIGHTEN (30-49) / EXIT (<30). Shown ONLY on held_positions. | export field_schema, export field_glossary |
| `hl_state` | `{'role': 'signal', 'unit': 'label', 'side': 'n/a'}` | `HOLD` · `TIGHTEN` · `EXIT` | Health state label (held only): HOLD_ADD / HOLD / TIGHTEN / EXIT. | export field_schema, export field_glossary, enum set |
| `live_px` |  |  | (held_positions only) Current mark for a held ticker = the same FMP close every other field on the record is scored against (see cob_price) — not a broker/journal field. PM ruling 2026-07-29: the Aegis journal's own live-price field was retired in its D-84 restructure, so AQE now supplies this from its own data instead of leaving it empty. | export field_glossary |
| `unreal_usd` |  |  | (held_positions only) NOT YET WIRED — currently reads a journal field the Aegis journal's 2026-07-28 restructure retired, so this is always null. PM ruling 2026-07-29: leave as-is for now; the real fix is a proper qty×(live_px−entry) calculation, not a rename. | export field_glossary |

### FIP — 2 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `fip_spike_excluded` | `bool` |  | UNDOCUMENTED — AQE owner to define (FIP spike-exclusion flag; confirm semantics). | agentic glossary, observed in export |
| `fip_window_effective` | `int` |  | UNDOCUMENTED — AQE owner to define (effective FIP window; confirm semantics). | agentic glossary, observed in export |

### Schema vocabulary — 5 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `_convention` |  |  | LONG setups: STOPS are BELOW entry, TARGETS are ABOVE entry. Values are absolute USD prices unless the name ends in _rr/_ratio/_pct/_ann (ratios) or is a list/object. 'rr'/'r' = reward-to-risk in R, where 1R = bracket.risk (= price − bracket.stop, the structural risk unit). | export field_glossary |
| `_decision_framework` |  |  | AQE reads the trade lifecycle in three distinct stages — do NOT conflate them; each answers a different question, so there is no 'picking at random': (1) DETECT — is a move brewing? = Signal Radar (runner_setup = a name already moving with another leg; premove_setup = a pre-move, ~12-day lead). These are DETECTION tags, not entries. (2) ENTER — is it time to buy, and where? = the bracket (stop/… | export field_glossary |
| `role` |  | `entry` · `reference` · `stop` · `target` · `fib_support` · `moving_average` · `risk_metric` · `volatility` · `ratio` · `signal` · `flag` |  | enum set |
| `side` |  | `below_entry` · `above_entry` · `at_entry` · `n/a` |  | enum set |
| `unit` |  | `usd` · `r_multiple` · `ratio` · `pct` · `atr` · `decimal` · `score` · `label` · `boolean` · `date` |  | enum set |

### Engine subcomponents — 1 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `subcomponents` | `{'role': 'signal', 'unit': 'score', 'side': 'n/a'}` |  | The engine SUB-SCORES behind each headline read — nested by engine, so the AIC sees WHY an engine scored what it did (context, never a gate). flow: {flow_score (MFI+CMF+HA core), accum_score, volume_score, skew_score, ext_score (extension penalty), mfi, cmf, ha_quality_count}. energy: {vp_position_score (volume-profile position), price_action_score, squeeze_score (BB/KC squeeze — the TTM-squeez… | export field_schema, export field_glossary, observed in export |

### Retired — documented, no longer emitted — 2 fields

| Field | Type | Values | Meaning | Documented by |
|---|---|---|---|---|
| `atr_quarter_risk_pct` | `{'role': 'risk_metric', 'unit': 'pct', 'side': 'n/a'}` |  | **RETIRED** (companion to atr_quarter_stop, retired with it). The atr_quarter_stop distance as a % of entry — i.e. how much room that stop actually gives. | export field_schema, export field_glossary |
| `atr_quarter_stop` | `{'role': 'stop', 'unit': 'usd', 'side': 'below_entry'}` |  | **RETIRED** (mechanical stop, retired in favour of bracket.stop). A VOLATILITY stop: entry minus 0.25 x ATR14 (the "Nick Crown" level). A REFERENCE beside the bracket, NOT a replacement — bracket.stop stays the structural stop AQE sizes against, and the two answer different questions. This one asks 'how far is a quarter of a normal day?'; the bracket asks 'where is the level that would say I am wrong?'. Read atr_quarter_risk_pct with it: a quarter-ATR is TIGH… | export field_schema, export field_glossary |

---

## 4 · Engine subcomponents

Each engine also exports its own breakdown under `subcomponents`, so a
score can always be taken apart into the parts that made it.

**`subcomponents.flow`** — MFI + CMF + Heikin-Ashi quality (flow_score), A/D linreg (accum_score), volume trend/spike (volume_score), up/down skew (skew_score); diagnostics mfi, cmf, ha_quality_count.

**`subcomponents.energy`** — range-position proxy (vp_position_score), price action, squeeze, exhaustion, ATR; diagnostics en_pos50, en_trend_bars.

**`subcomponents.structure`** — RS-vs-SPY, RS-acceleration, base, market-structure position, resistance, weekly, earnings sub-scores; diagnostics rs_vs_spy, rs_accel, base_days, bd_mode.

**`subcomponents.mp`** — absolute momentum, ADX, relative momentum, trend sub-scores; diagnostics roc_zscore, excess_return, adx_val, di_bullish.

**`subcomponents.bq`** — Base Quality: range tightness (ATR5/ATR20), volume dry-up, base duration, EMA convergence; used by SC_POSITION.

**`subcomponents.pipe`** — Pipeline rank inputs: 12m return, ADX, RSI, volume, MA sub-scores, momentum_composite, pipe_tier.

---

## 5 · The lens set

Six lenses count toward the consensus; `extension` is present and
**always null** by ruling, because the voices disagree on what extension
means, so AQE prints the numbers and makes no call.

Counting lenses: `leadership`, `coil`, `insti_money`, `structure`, `resistance`, `sector`

---

## 6 · Provenance of this run

Static sources: the export's own `field_schema` / `field_glossary`,
the agentic dictionary, the enum sets and the lens glossary — all read
from code at generation time.

Sample file: `aegis/output/aqe_daily_export.json` — 162 records, scan date 2026-07-28. Fields marked *observed in export* and
nothing else are known only from that sample; if it is stale, they are
the rows most likely to be out of date.

