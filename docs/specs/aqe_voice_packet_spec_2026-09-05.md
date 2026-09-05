# AQE VOICE PACKET SPEC — what each seat needs, what to add, what to drop
Date 2026-09-05 · For Claude Code working on TongIncomeWheel/AQE · Source of truth for `contracts/voice_menus.json` and `emit_packets.py`

## 0 · Rules
- A packet is ONE seat's columns, ALL rows. Nothing else. Rows shuffled. No other seat's columns.
- `null` is written as the literal token `null`, never blank.
- **Bracket fields ride along for information only. No seat may reject on `bracket.valid`, `bracket.rr*` or `bracket.risk_pct` — PM ruling R1. The three cards that still say so (oneil R6, raschke R6, wyckoff R6/step5) get that line deleted.**
- Chart-pattern fields (`pattern*`) are OUT of every packet — PM 2026-09-05.
- `qs_market` must never appear in any packet (R3, asserted at build).

## 1 · Today's inventory
AQE serves **289** distinct fields per row. The 11 voting seats read **68**. The rest are computed and never read.

## 2 · Fields to ADD to AQE (18)
| field | type | definition | who needs it |
|---|---|---|---|
| `high_52w` | float | highest close, trailing 252 sessions | minervini C3-crit7, oneil, livermore, thorp R2 |
| `low_52w` | float | lowest close, trailing 252 sessions | minervini C3-crit3 (>=30% above) |
| `pct_from_52w_high` | float | (close/high_52w - 1)*100 | minervini (within 25%), oneil, DOOR 4 |
| `ret_6m` | float | total return %, 126 sessions | rs_rank_pct input; momentum window |
| `ret_12m` | float | total return %, 252 sessions | oneil L (12-month RS) |
| `rs_rank_pct` | float | percentile of ret_6m across the scored universe, 0-100 | minervini RS>=70, oneil RS>=80, DOOR 4 |
| `ma_150` | float | 150-day SMA | minervini Trend Template crit 2, 5 |
| `ma_40` | float | 40-day SMA | seow canon instrument |
| `cci_20` | float | Commodity Channel Index, 20 | seow canon instrument |
| `pivot_high` | float | last completed base top: structure_shift_ref when shift=BULLISH_BOS else last_pivot_high.price | oneil C17, minervini C5, livermore C5 — replaces the dead entry-vs-bracket.price test |
| `pct_from_pivot` | float | (close/pivot_high - 1)*100 | oneil: 0-5 buy, 5-10 late, >10 reject |
| `extension_atr_20` | float | (close - ma_20)/atr_14d | extension in volatility units, all technical seats |
| `elder_hi7_streak` | int | consecutive trailing bars with elder>=7 (from elder_5d and history) | DOOR 2 (PM: >=3) |
| `next_earnings_date` | date | FMP earnings calendar (the connector serves it; current 404 is a fetch-path bug) | weis catalyst rule, rogers catalyst test, every card's event window |
| `days_to_earnings` | int | business days to next_earnings_date | same |
| `stack_state` | enum | ALIGNED|REPAIRING|ROLLING|INVERTED from ma20/50/100/200 order | weis hard rule 5, detect-lens |
| `signal_hit_rate_20d` | float | per (elder_pattern x structure_shift) cell: share of names in that cell over trailing 60 sessions that closed higher 20 sessions later | thorp step 1 — measured edge |
| `signal_n` | int | sample size behind signal_hit_rate_20d | thorp step 1 |

## 3 · Already computed — SURFACE onto menus (11)
`elder_context.volume.up_bar_vol_ratio`, `elder_context.volume.vol_trend_5d`, `elder_context.exhaustion_check.exhaustion_flag`, `pipe_rank`, `vwap_14d_position`, `last_pivot_high.price`, `structure_shift_ref`, `fib_618`, `on_longlist`, `on_elder`, `on_qs`

## 4 · RETIRE from every card and menu (6)
- `rvol (-> day_vol)`
- `knn_significant (-> knn_threshold_clear)`
- `energy.squeeze_score (-> squeeze_breakout_state)`
- `bq.bq_base_dur (-> elder_context.vcp.base_range_pct)`
- `bq.bq_range_tight (-> elder_context.vcp.vcp_tightness_pct)`
- `ptrs (RETIRED 2026-08-13, alias of sc_momentum)`

## 5 · Per-seat packet — current columns, gaps, and the change
Legend: ✓ served · ∅ null on >50% of rows · ✗ not in AQE · **+** add · **−** drop from this packet

### elder-lens  — PULLBACK
_Buys the moment Elder's red 'no-buy' bar gives way (a <=6 -> >=7 transition in elder_5d) inside a still-rising trend, i.e. the dip that has just stopped being forbidden._

| column | status | note |
|---|---|---|
| `elder` | ✓ |  |
| `elder_5d` | ✓ |  |
| `elder_pattern` | ✓ |  |
| `mp_state` | ✓ |  |
| `mp` | ✓ |  |
| `elder_hi7_streak` | **+** | add |
| `ma_20` | **+** | add |
| `ma_50` | **+** | add |
| `entry` | **+** | add |
| `structure_shift` | **+** | add |
| `choch_state` | **+** | add |
| `pin_bar_state` | **+** | add |
| `pin_bar_level` | **+** | add |
| `elder_context.volume.up_bar_vol_ratio` | **+** | add |

Card steps that cannot run today: impulse_state per-bar colour (R1) — elder.py computes and discards it; no export field; two-bar colour transition (R2); signed Force Index + 2-bar EMA (R3) and 13-bar EMA (R4) — no field; fitted price channel upper/lower wall (R5) — no field

### livermore  — BREAKOUT_AT_PIVOT
_Buys a name in a confirmed uptrend making a fresh new high after a normal pullback, with a predetermined danger-signal and max loss (the Pivotal Point method)._

| column | status | note |
|---|---|---|
| `rank` | ✓ |  |
| `held` | ✓ |  |
| `gics_sector` | ✓ |  |
| `gics_sector_name` | ✓ |  |
| `sector_trend_state` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `sma_distance_pct` | ✓ |  |
| `atr_14d` | ✓ |  |
| `day_vol` | ✓ |  |
| `mp_state` | ✓ |  |
| `mp_accel_state` | ✓ |  |
| `entry` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.stop_type` | ∅ | null 73% |
| `bracket.valid` | ✓ |  |
| `bracket.risk_pct` | ∅ | null 73% |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `high_52w` | **+** | add |
| `pct_from_52w_high` | **+** | add |
| `pivot_high` | **+** | add |
| `pct_from_pivot` | **+** | add |
| `rs_rank_pct` | **+** | add |
| `next_earnings_date` | **+** | add |

Card steps that cannot run today: order-fill difficulty as a strength signal (C-cite #101) — no field; day_vol is a ratio; test orders / probing (C-cite #103/104) — not applicable; relative-move parameter driving mp_state transitions (engine ask rank 1) — not exported; two-name Key Price group pairing (R8) — no field

### minervini  — BREAKOUT_AT_PIVOT
_Buys a confirmed Stage-2 leader as it clears the pivot of a volatility-contraction base on expanding volume, with a tight pre-fixed stop (SEPA / Trend Template)._

| column | status | note |
|---|---|---|
| `rank` | ✓ |  |
| `held` | ✓ |  |
| `gics_sector` | ✓ |  |
| `gics_sector_name` | ✓ |  |
| `sector_trend_state` | ✓ |  |
| `ma_20` | ✓ |  |
| `ma_50` | ✓ |  |
| `ma_100` | ✓ |  |
| `ma_200` | ✓ |  |
| `sma_distance_pct` | ✓ |  |
| `rs_leadership` | ✓ |  |
| `rs_spy_20d` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `day_vol` | ✓ |  |
| `flow` | ✓ |  |
| `energy` | ✓ |  |
| `entry` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.stop_type` | ∅ | null 73% |
| `bracket.valid` | ✓ |  |
| `bracket.risk_pct` | ∅ | null 73% |
| `squeeze_breakout_state` | ✓ |  |
| `was_squeezed` | ✓ |  |
| `squeeze_breakout_volume_confirmed` | ✓ |  |
| `elder_context.vcp.base_range_pct` | ✓ |  |
| `elder_context.vcp.vcp_tightness_pct` | ✓ |  |
| `elder_pattern` | ✓ |  |
| `mp_accel_state` | ✓ |  |
| `rs_down_day_20d` | ✓ |  |
| `div_state` | ✓ |  |
| `div_bear_count` | ✓ |  |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `high_52w` | **+** | add |
| `low_52w` | **+** | add |
| `pct_from_52w_high` | **+** | add |
| `ma_150` | **+** | add |
| `rs_rank_pct` | **+** | add |
| `pivot_high` | **+** | add |
| `pct_from_pivot` | **+** | add |
| `next_earnings_date` | **+** | add |

Card steps that cannot run today: earnings growth / quarterly EPS acceleration / sales growth (C1 el.2, C12) — no field; six-category maturation sort (C13, C20) — no field; institutional sponsorship / fund ownership — no field; ma_150 (Trend Template criteria 1,2,4) — AQE has 20/50/100/200 only

### oneil  — BREAKOUT_AT_PIVOT
_Buys the #1-3 market leader breaking out of a sound, measurable base on >=+40% volume, within 5% of the pivot, with a 7-8% stop (CAN SLIM)._

| column | status | note |
|---|---|---|
| `sc_momentum` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `energy` | ✓ |  |
| `flow` | ✓ |  |
| `lens` | ✓ | dict — flatten to lens.* or drop; menu lists the parent |
| `day_vol` | ✓ |  |
| `rs_spy_20d` | ✓ |  |
| `rs_leadership` | ✓ |  |
| `rank` | ✓ |  |
| `gics_sector` | ✓ |  |
| `gics_sector_name` | ✓ |  |
| `sector_trend_state` | ✓ |  |
| `sma_distance_pct` | ✓ |  |
| `ma_50` | ✓ |  |
| `ma_200` | ✓ |  |
| `entry` | ✓ |  |
| `atr_14d` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.rr` | ∅ | null 73% |
| `bracket.price` | ✓ |  |
| `bracket.risk_pct` | ∅ | null 73% |
| `bracket.valid` | ✓ |  |
| `bracket.targets` | ✓ |  |
| `bracket.atr_fallback_stop` | ✓ |  |
| `held` | ✓ |  |
| `elder_context.vcp.base_range_pct` | ✓ |  |
| `elder_context.vcp.vcp_tightness_pct` | ✓ |  |
| `elder_pattern` | ✓ |  |
| `mp_accel_state` | ✓ |  |
| `rs_down_day_20d` | ✓ |  |
| `div_state` | ✓ |  |
| `div_bear_count` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `high_52w` | **+** | add |
| `pct_from_52w_high` | **+** | add |
| `ret_12m` | **+** | add |
| `rs_rank_pct` | **+** | add |
| `pivot_high` | **+** | add |
| `pct_from_pivot` | **+** | add |
| `next_earnings_date` | **+** | add |
| bracket.valid as a gate (keep the field, delete the reject rule) | **−** | drop |

Card steps that cannot run today: C current earnings (C4, C5) — no field; A annual earnings / ROE / cash flow (C6) — no field; S supply/demand: absolute share volume, buybacks, insider % (C8) — no field; I institutional sponsor count (C11) — no field

### raschke  — REVERSAL
_Buys one of four mechanical short-term setup families — failed test of a prior extreme (Turtle Soup), first pullback in a strong trend (Holy Grail/Anti), exhaustion climax, or range-contraction breakout (NR4/NR7) — with a swing-extreme stop._

| column | status | note |
|---|---|---|
| `rank` | ✓ |  |
| `held` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `sma_distance_pct` | ✓ |  |
| `atr_14d` | ✓ |  |
| `atr_caution` | ✓ |  |
| `day_vol` | ✓ |  |
| `mp_state` | ✓ |  |
| `mp_accel_state` | ✓ |  |
| `lens` | ✓ | dict — flatten to lens.* or drop; menu lists the parent |
| `entry` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.stop_type` | ∅ | null 73% |
| `bracket.valid` | ✓ |  |
| `bracket.risk_pct` | ∅ | null 73% |
| `squeeze_breakout_state` | ✓ |  |
| `was_squeezed` | ✓ |  |
| `squeeze_breakout_volume_confirmed` | ✓ |  |
| `elder_pattern` | ✓ |  |
| `div_state` | ✓ |  |
| `div_bear_count` | ✓ |  |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `extension_atr_20` | **+** | add |
| `pivot_high` | **+** | add |
| `next_earnings_date` | **+** | add |
| bracket.valid as a gate (keep the field, delete the reject rule) | **−** | drop |

Card steps that cannot run today: ADX / +DI/-DI (Holy Grail C7, ADX Gapper C8) — no field; %K/%D stochastic (the Anti, C6) — no field; rolling 20-day high/low (Turtle Soup C3, 80-20 C4) — no field; per-bar range history for NR4/NR7 / 6d-100d HV ratio (C12, C13) — no field

### seow  — PULLBACK
_Buys a graded pullback to a rising 20MA inside a 20>40MA uptrend when CCI < -100, via a buy-stop above the prior day's high, with stop/size/time-limit fixed first._

| column | status | note |
|---|---|---|
| `ma_20` | ✓ |  |
| `ma_50` | ✓ |  |
| `ma_100` | ✓ |  |
| `ma_200` | ✓ |  |
| `sma_distance_pct` | ✓ |  |
| `mp_state` | ✓ |  |
| `sector_trend_state` | ✓ |  |
| `entry` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `atr_caution` | ✓ |  |
| `bracket.valid` | ✓ |  |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `ma_40` | **+** | add |
| `cci_20` | **+** | add |
| `extension_atr_20` | **+** | add |

Card steps that cannot run today: ma_40 (40-period SMA) — no field; card forbids substituting ma_50; CCI / cci20 — no field; sma20 5-day slope — no field; 63-day stock vs index / industry-group % change (R8) — no field

### thorp  — NEUTRAL
_Buys only a measurable, evidenced mispricing, sized from the named worst case (overnight gap through the stop), ranked on volatility before horizon — never a chart shape._

| column | status | note |
|---|---|---|
| `sc_momentum` | ✓ |  |
| `atr_14d` | ✓ |  |
| `day_vol` | ✓ |  |
| `bracket.price` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.valid` | ✓ |  |
| `bracket.risk_pct` | ∅ | null 73% |
| `bracket.stop_atr_dist` | ∅ | null 73% |
| `bracket.rr` | ∅ | null 73% |
| `bracket.rr_tp1` | ∅ | null 73% |
| `bracket.rr_tp2` | ∅ | null 73% |
| `knn_prob` | ✓ |  |
| `knn_threshold_clear` | ✓ |  |
| `sc_m_gate_detail` | ✓ |  |
| `sc_p_gate_detail` | ✓ |  |
| `beta_30d` | ✓ |  |
| `atr_caution` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `signal_hit_rate_20d` | **+** | add |
| `signal_n` | **+** | add |
| `high_52w` | **+** | add |
| `vol_30d_ann` | **+** | add |

Card steps that cannot run today: high_52w / low_52w (canon volatility measure C5, R2) — no field; avg_daily_volume, bid/ask spread (round-trip cost C24, R8) — no field; realised_vol_30d, candidate_set_vol_rank, expected_hold_days (R1) — no field; backtest_trade_count / rules_generated_count / sample window (R6) — no field; no per-signal hit rate is exported

### weis  — REVERSAL
_Buys the failure of weakness — a spring / false breakdown below support that does not follow through — inside an uptrend; explicitly does not buy strength or breakouts._

| column | status | note |
|---|---|---|
| `pin_bar_state` | ✓ |  |
| `choch_state` | ✓ |  |
| `inside_bar` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `energy` | ✓ |  |
| `squeeze_breakout_state` | ✓ |  |
| `was_squeezed` | ✓ |  |
| `squeeze_breakout_volume_confirmed` | ✓ |  |
| `elder_context.vcp.base_range_pct` | ✓ |  |
| `elder_context.vcp.vcp_tightness_pct` | ✓ |  |
| `flow` | ✓ |  |
| `day_vol` | ✓ |  |
| `atr_14d` | ✓ |  |
| `atr_caution` | ✓ |  |
| `sma_distance_pct` | ✓ |  |
| `ma_20` | ✓ |  |
| `ma_50` | ✓ |  |
| `ma_200` | ✓ |  |
| `mp_state` | ✓ |  |
| `mp_accel_state` | ✓ |  |
| `sc_momentum` | ✓ |  |
| `div_state` | ✓ |  |
| `div_bear_count` | ✓ |  |
| `elder_pattern` | ✓ |  |
| `elder_5d` | ✓ |  |
| `sector_trend_state` | ✓ |  |
| `entry` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.stop_type` | ∅ | null 73% |
| `bracket.valid` | ✓ |  |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.risk_pct` | ∅ | null 73% |
| `bracket.invalid_reason` | ✓ |  |
| `stack_state` | **+** | add |
| `next_earnings_date` | **+** | add |
| `days_to_earnings` | **+** | add |
| `elder_context.volume.up_bar_vol_ratio` | **+** | add |

Card steps that cannot run today: close-location value (close-low)/(high-low) — upthrust confirmation (R8/W13) — no field; penetration depth vs violated support (R9/W8) — no field; secondary test (R10/W9) — no field; absorption sequence (R11/W16) — no field

### wyckoff  — REVERSAL
_Buys at the edge of a trading range in measured contraction where effort and result disagree in the buyer's favour, with a structural danger-point stop (Weis's Wyckoff)._

| column | status | note |
|---|---|---|
| `flow` | ✓ |  |
| `energy` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `mp_state` | ✓ |  |
| `mp_accel_state` | ✓ |  |
| `day_vol` | ✓ |  |
| `lens` | ✓ | dict — flatten to lens.* or drop; menu lists the parent |
| `lens.coil` | ✓ |  |
| `lens.structure` | ✓ |  |
| `lens.resistance` | ✓ |  |
| `sma_distance_pct` | ✓ |  |
| `ma_20` | ✓ |  |
| `ma_50` | ✓ |  |
| `ma_200` | ✓ |  |
| `atr_14d` | ✓ |  |
| `atr_caution` | ✓ |  |
| `pin_bar_state` | ✓ |  |
| `choch_state` | ✓ |  |
| `div_state` | ✓ |  |
| `div_bear_count` | ✓ |  |
| `entry` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.stop_type` | ∅ | null 73% |
| `bracket.stop_atr_dist` | ∅ | null 73% |
| `bracket.risk_pct` | ∅ | null 73% |
| `bracket.rr` | ∅ | null 73% |
| `bracket.valid` | ✓ |  |
| `bracket.targets` | ✓ |  |
| `squeeze_breakout_state` | ✓ |  |
| `was_squeezed` | ✓ |  |
| `squeeze_breakout_volume_confirmed` | ✓ |  |
| `elder_context.vcp.base_range_pct` | ✓ |  |
| `elder_context.vcp.vcp_tightness_pct` | ✓ |  |
| `elder_pattern` | ✓ |  |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `elder_context.volume.up_bar_vol_ratio` | **+** | add |
| `elder_context.volume.vol_trend_5d` | **+** | add |
| `pivot_high` | **+** | add |
| `extension_atr_20` | **+** | add |
| bracket.valid as a gate (keep the field, delete the reject rule) | **−** | drop |

Card steps that cannot run today: range_high / range_low / last_penetration event — springs, upthrusts, secondary tests, absorption (C7-C10, C14, C15) — n; wave triad length/volume/duration (C13, C19, C20) — no wave object; two-bar sequences, Crabel NR counts, thrust measurement, distribution sequence (C4, C5, C11, C12, C17) — no bar series i; net up-minus-down volume / FORCE (C16) — not derivable from daily bars

### lynch  — NEUTRAL
_Bottom-up fundamental analysis by business category (PEG, net cash, FCF yield, inventory vs sales) — on AQE data it is 'a question-asker and a discipline, not a nominator'._

| column | status | note |
|---|---|---|
| `gics_sector` | ✓ |  |
| `gics_sector_name` | ✓ |  |
| `sector_trend_state` | ✓ |  |
| `sma_distance_pct` | ✓ |  |
| `ma_20` | ✓ |  |
| `ma_50` | ✓ |  |
| `ma_200` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `rank` | ✓ |  |
| `held` | ✓ |  |
| `rs_leadership` | ✓ |  |
| `rs_spy_20d` | ✓ |  |
| `bracket.valid` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `(fundamentals arrive via the FMP pack at GATHER, not the AQE packet — card must be updated to say so)` | **+** | add |
| ma_20 | **−** | drop |
| ma_50 | **−** | drop |
| ma_200 | **−** | drop |
| structure | **−** | drop |
| structure_shift | **−** | drop |
| rs_leadership | **−** | drop |
| rs_spy_20d  (card marks all six "advisory only / not mine") | **−** | drop |

Card steps that cannot run today: EPS, growth rate, P/E, PEG, dividend yield (C7-C9) — no field; net cash, debt, equity ratio (C10-C12) — no field; operating cash flow, CapEx, FCF yield, market cap (C13, C16) — no field; inventory vs sales two-quarter series (C14) — no field

### detect-lens  — NEUTRAL
_Mechanical seat: ranks the universe by lens_positive (count of 'strong' lenses) and overlays the runner_setup / premove_setup detection tags — no framework, reasons are the fields verbatim._

| column | status | note |
|---|---|---|
| `lens` | ✓ | dict — flatten to lens.* or drop; menu lists the parent |
| `lens_positive` | ✓ |  |
| `lens_warnings` | ✓ |  |
| `runner_setup` | ✓ |  |
| `runner_conviction` | ✓ |  |
| `premove_setup` | ✓ |  |
| `premove_conviction` | ✓ |  |
| `ma_50` | ✓ |  |
| `ma_100` | ✓ |  |
| `ma_200` | ✓ |  |
| `atr_14d` | ✓ |  |
| `day_vol` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.valid` | ✓ |  |
| `bracket.risk_pct` | ∅ | null 73% |
| `sc_momentum` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `energy` | ✓ |  |
| `flow` | ✓ |  |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `stack_state` | **+** | add |
| `elder_context.exhaustion_check.exhaustion_flag` | **+** | add |
| `pct_from_52w_high` | **+** | add |
| sc_momentum | **−** | drop |
| structure | **−** | drop |
| energy | **−** | drop |
| flow  (card header: "never reads composites") | **−** | drop |

Card steps that cannot run today: Clenow regression slope x R-squared ranking (C12) — sc_momentum is a different construct; single-day gap magnitude over lookback (C15 gap filter) — no field; Level 2 depth / print rate / live spread (C6-C11) — no feed; premarket N/A; Weis bar tests C19-C24 mapping to structure/energy/flow — unconfirmed

### rogers  — —

| column | status | note |
|---|---|---|
| `rank` | ✓ |  |
| `held` | ✓ |  |
| `gics_sector` | ✓ |  |
| `gics_sector_name` | ✓ |  |
| `sector_trend_state` | ✓ |  |
| `sma_distance_pct` | ✓ |  |
| `ma_20` | ✓ |  |
| `ma_50` | ✓ |  |
| `ma_200` | ✓ |  |
| `day_vol` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `rs_leadership` | ✓ |  |
| `rs_spy_20d` | ✓ |  |
| `entry` | ✓ |  |
| `bracket.valid` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.stop_type` | ∅ | null 73% |
| `bracket.risk_pct` | ∅ | null 73% |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `next_earnings_date` | **+** | add |
| `days_to_earnings` | **+** | add |
| `rs_rank_pct` | **+** | add |

### steenbarger  — —

| column | status | note |
|---|---|---|
| `gics_sector_name` | ✓ |  |
| `sc_momentum` | ✓ |  |
| `lens_warnings` | ✓ |  |
| `day_vol` | ✓ |  |
| `ma_50` | ✓ |  |
| `ma_100` | ✓ |  |
| `ma_200` | ✓ |  |
| `structure` | ✓ |  |
| `structure_shift` | ✓ |  |
| `atr_14d` | ✓ |  |
| `bracket.stop` | ∅ | null 73% |
| `bracket.valid` | ✓ |  |
| `bracket.risk_pct` | ∅ | null 73% |
| `div_state` | ✓ |  |
| `div_bear_count` | ✓ |  |
| `bracket.atr_fallback_stop` | ✓ |  |
| `bracket.invalid_reason` | ✓ |  |
| `rs_rank_pct` | **+** | add |
| `pct_from_52w_high` | **+** | add |

### druckenmiller  — —

| column | status | note |
|---|---|---|
| `gics_sector_name` | ✓ |  |
| `sc_momentum` | ✓ |  |
| `beta_30d` | ✓ |  |
| `sector_trend_state` | ✓ |  |
| `thematic_basket` | ∅ | null 65% |
| `thematic_grade` | ∅ | null 65% |
