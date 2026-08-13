# AQE canonical taxonomy vs 14-voice data requirements

**Cross-reference — dedup, delta, conflicts, new-since-analysis, unused capacity.**

Sources. AQE: `docs/AQE_DATA_TAXONOMY.csv` @ `6316471` (272 field rows). Voices: `aegis/canon/<voice>/canon.lock.yaml` `recognisers[].fields` @ main, 14 voices. Prior mapping: `aegis/design/voice_data_map.md` (229 rows) and `/root/aqe_data_requirements.md`. Baseline export for the "new" test: `aegis/output/aqe_daily_export.json`, dated 2026-07-28. Compiled 2026-08-13 SGT.

---

## 1. HEADLINE

| Measure | Count |
|---|---|
| Voice requirements on record (voice_data_map rows) | 229 across 14 voices — 459 field references, 216 unique field names |
| Taxonomy field rows | 272 — **219 ship**, 50 marked NOT EXPORTED, 3 schema-vocabulary only |
| Requirements the taxonomy satisfies (exact field, alias, or scoped equivalent) | **~148** of 229 |
| Genuine gaps after searching the whole taxonomy by meaning | **34 distinct data points** (section 3) |
| My earlier "missing / build / buy / won't-build" calls that were **wrong or over-stated** | **14 of the 29 items** outside Section 1 — 18 dedup rows below |

---

## 2. DEDUP — I said missing, AQE actually has it

| What the voice needs | Voice(s) | AQE field (exact dotted path) | What it actually is | My earlier call was wrong because… |
|---|---|---|---|---|
| Intraday tape / VWAP | livermore, raschke, detect-lens | `elder.elder_context` → `.vwap_5d`, `.hourly_bars_used`, `.volume`; plus `vwap_14d_position`, `vwap_14d_position.vwap_14d` | 5-day hourly VWAP read behind the elder pattern, plus a rolling 14-session VWAP and the close's position against it. Both ship on `daily_list` | I put "intraday tape — VWAP" in Section 4 WON'T BUILD. AQE already carries an hourly VWAP read per row, and added a daily rolling VWAP since. Only time & sales / L2 is truly out |
| VCP contraction sequence | minervini | `elder.elder_context` → `.vcp`; supporting: `energy.squeeze_score`, `price_action_score.compression_ratio`, `bq.bq_range_tight` | A VCP read already sits inside `elder_context`, shipped per row. The contraction mechanics (5-bar/20-bar range ratio, ATR5/ATR20) are computed | Section 2 said "not computed". It is computed and a VCP flag ships; only the *countable sequence with per-contraction depth* is absent |
| Weekly trend direction | elder-lens, seow | `structure.wk_score` (`subcomponents.structure`); `candle_w`, `candle_w.candle_w_dir`, `pattern_w`, `pattern_w.pattern_w_dir`, `pattern_w.pattern_w_stage` | Weekly close vs weekly SMA10, banded 0–15; plus a weekly candle read with direction and a weekly chart-pattern sweep with direction and lifecycle stage | Section 2 asked to build `weekly_trend_dir`. AQE has had `wk_score` all along and has since added two more weekly reads |
| Elder impulse colour | elder-lens | `elder_state_score.impulse_state`; `elder.elder_state_score`, `elder.elder_slope_score`, `elder.elder_hist_score`, `elder.elder_5d`, `elder.elder_pattern` | EMA13 direction combined with MACD-histogram direction — green / red / blue. The exact impulse colour | Section 2 said build `impulse_colour`. It is computed inside the Elder engine — marked NOT EXPORTED, so this is an export decision, not engineering |
| Stochastic | seow, raschke | `sc_position.k39_gate` — formula `stoch(weekly,39)>50 AND obv_weekly>sma(obv_weekly,30)` | A weekly stochastic and an OBV confirmation, mapped to daily as-of with no look-ahead | Section 2 said build `stoch_k`/`stoch_d`. AQE computes a stochastic and an OBV read already — NOT EXPORTED, and on a weekly-39 setting, not daily 14/3 |
| Wyckoff range boundary | wyckoff | `fib_swing_low`, `fib_swing_low.fib_swing_high`; `structure_shift.last_pivot_high`, `structure_shift.structure_shift_ref` | Low and high of the auto-detected current swing, plus the confirmed pivot the structure read is measured against | Section 2 asked to build `range_high`/`range_low`. The swing envelope already ships per row |
| Wyckoff penetration + recovery event | wyckoff | `pin_bar_state`, `pin_bar_state.pin_bar_level`, `pin_bar_state.pin_bar_date`; `choch_state`, `choch_state.choch_date`; `structure_shift`; `squeeze_breakout_state`, `.squeeze_breakout_volume_confirmed`; `candle_d`, `candle_d.candle_d_dir` | Rejection-candle geometry with the exact level rejected and the date; the change-of-character direction; the close vs the confirmed pivot; a squeeze breakout with volume confirmation; full candlestick geometry | Section 2 said "not in AQE". Every mechanical component of a spring, upthrust, secondary test and shakeout ships. Only the Wyckoff *naming layer* on top is missing |
| Breadth | druckenmiller | `thematic_grade.breadth_pct` | Fraction of a basket's constituents above their **own** 20-day SMA, per basket, 35 baskets | Section 2 said build in-house breadth. Basket-level breadth already ships. Exchange-wide breadth (advance/decline, new highs/lows) really is absent — that part of the call stands |
| Days to earnings | detect-lens, minervini, oneil | `structure.earn_score` (`subcomponents.structure`) — `days<=5→0.0, days<=10→4.0, days<=20→7.0, days>20 or NA→10.0` | A proximity band to the next earnings date, 0–10 | Section 2 asked to build `days_to_earnings` for minervini and oneil. The band already answers "how close is earnings" for all three; only the integer day count is missing |
| Recent volume vs its own average | 8 voices — livermore, minervini, oneil, raschke, rogers, wyckoff, elder-lens, thorp | `day_vol`; duplicates in `volume_score.vtr`, `bq_vol_dry.vd_ratio`, `momentum_composite.vol_score` | Today's volume over its own 20-day prior average. The 5/20 average-volume ratio is computed independently in four places | The voice_data_map called `day_vol` a "phantom menu entry" that populates 0/162. It is the real field — `rvol` was renamed to `day_vol` on 2026-08-05. Absolute average daily volume in shares/dollars is still absent |
| Open R / unrealised on a held name | seow, steenbarger | `held.unreal_usd`, `held.live_px`, `held.held_sl`, `held.held_tp1`, `held.held_tp2`, `bracket.risk_pct`, `bracket.rr` — all `held_positions only` | Unrealised P&L, the current mark, and the broker-journal stop and targets, all on the held record | Section 2 said build `open_r`. Every input ships on `held_positions`. Caveat: `held.unreal_usd` is flagged NOT YET WIRED — it reads a journal field renamed in the 2026-07-28 restructure |
| Measured edge / forward probability per signal | thorp, steenbarger | `qs.qs.odds.p`, `qs.odds.p.qs.odds.extrapolated`, `qs.qs.engine.recipe_hits`, `qs.qs.engine.qs_persist`, `qs.qs.unevaluable_vetoes`, `qs_market`, `qs_status`, `on_qs` — `qs{} block` | A calibrated probability of touching the ±2×ATR14 objective within 20 sessions, read from a frozen historical look-alike table; how many of 40 frozen recipes matched; prior stored sessions; which vetoes could not be evaluated | Section 2 asked to build `signal_stats{}`. The QS block is exactly this and it is live — it postdates my 2026-07-28 baseline |
| Support levels and targets | seow | `fib_swing_low.fib_236/.fib_382/.fib_500/.fib_618/.fib_786`; `structure_shift.last_pivot_high`; `bracket.targets`; `atr_quarter_stop` | A five-level Fibonacci retracement support ladder off the detected swing, the confirmed pivot high, the bracket's target ladder, and a volatility stop offered beside it | I listed only `fib_swing_low` as provided for seow. The whole support/target ladder ships |
| 20-day moving average and its stack | seow, elder-lens | `ma_20`, `ma_20.ma_50`, `ma_20.ma_100`, `ma_20.ma_200`, `sma_distance_pct`, `mp.trend_score` | Absolute 20/50/100/200-day SMAs, the close's distance from the 50-day, and a moving-average stacking score | Section 2 bundled `sma20` into "extra MAs to build". `ma_20` and the full stack ship. Only SMA(40) and the 20-day slope are absent |
| Institutional money read | lynch, minervini, oneil | `sc_momentum.flow`, `flow.accum_score`, `accum_score.ad_short`, `accum_score.ad_long`, `flow.skew_score`, `flow_score.mfi`, `flow_score.cmf`, `lens.insti_money` | Money flow as institutional accumulation vs distribution: A/D line short-vs-long regression slope, up-vs-down volume skew, MFI(14), CMF(20), and a dedicated lens read | Section 3 said buy institutional ownership. The *behavioural* institutional read ships. The holdings register (13F %, holder count, insider net) is genuinely absent — see conflicts |
| Chart pattern / base geometry | oneil, minervini, wyckoff | `pattern`, `pattern.pattern_fit`, `.pattern_stage`, `.pattern_trigger`, `.pattern_invalidation`, `.pattern_direction`, `.pattern_days`, `.pattern_start`, `.pattern_alt` | A 126-bar (~6 month) chart-pattern detector with geometric fit quality, lifecycle stage, the confirming breakout price, the invalidation price, and every alternative that also matched | Never in my mapping at all. This is the base/cup-with-handle read O'Neil and Minervini were assumed to lack. New since 2026-07-28 |
| Reward:risk / expected gain in R | thorp, oneil, steenbarger | `bracket.rr`, `bracket.rr_tp1`, `bracket.rr_tp2`, `bracket.rr_tp3`, `bracket.risk_pct`, `bracket.stop_atr_dist`, `atr_quarter_stop.atr_quarter_risk_pct` | The bracket's reward:risk at each target rung, the percent of capital at risk, and the stop's distance in ATR | Section 2 implied `expected_gain_r` needed building. It ships as `bracket.rr*` on every row where `bracket.valid` is true |
| Universe pass counts and run statistics | thorp | `summary`, `data_quality`, `rank`, `pipe_rank`, `pipe_rank.pipe_tier`, `signal_radar` | Run counts, records carrying a null core field, position in the sorted list, the pre-screen rank and its tier label, radar tag totals | Section 2 asked to build `universe_stats{}`. The run-level counts already ship as `summary` + `data_quality`; only forward-return dispersion and base rate are absent |

---

## 3. DELTA — genuinely not in AQE

Confirmed absent after searching all 272 taxonomy rows by meaning.

| Data point | Voice(s) | Proposed field name | Where it would live | Build or Source |
|---|---|---|---|---|
| 52-week high / low and % distance from each | thorp, minervini, oneil | `high_52w`, `low_52w`, `pct_from_52w_high`, `pct_from_52w_low` | `daily_list` | Build |
| Last eleven monthly highs / lows | thorp | `monthly_high_11`, `monthly_low_11` | `daily_list` | Build |
| Implied volatility and IV rank | thorp | `iv_30d`, `iv_rank` | `daily_list` | Source — Alpaca (charter's only Greeks source) |
| Bid / ask spread | thorp, livermore | `bid`, `ask`, `bid_ask_spread`, `spread_bps` | `daily_list` | Source — IBKR (no NBBO in FMP) |
| Absolute average daily volume and dollar liquidity | thorp, livermore | `avg_daily_volume`, `dollar_volume_20d` | `daily_list` | Build (the ratio exists; the absolute does not) |
| Company fundamentals — EPS/sales growth, margins, P/E, PEG, yield, debt, market cap | lynch, minervini, oneil, rogers, druckenmiller | `fundamentals{}` | `daily_list` (weekly refresh) | Source — FMP `statements/*`, `company/*` |
| Institutional and insider ownership register | lynch, minervini, oneil | `inst_ownership_pct`, `inst_holders`, `insider_net_90d` | `daily_list` | Source — FMP `form13F` + insider trades |
| Exchange-wide breadth — TICK, TRIN, A/D line, new highs vs lows | druckenmiller, raschke, oneil | `tick`, `trin`, `nyse_ad_line`, `nh_nl_net` | top-level block | Source — IBKR |
| Policy rate, 2s10s curve, central-bank balance sheet | druckenmiller | `policy_rate`, `curve_2s10s`, `cb_balance_sheet` | top-level block | Source — FMP `economics/*` + FRED `WALCL` |
| Positioning and sentiment — COT, put/call, short interest | druckenmiller, crown | `cot_positioning{}` | top-level block | Source — FMP `commitmentOfTraders` |
| Commodity prices and sector capex | rogers, druckenmiller | `commodity_prices{}`, `sector_capex{}` | top-level block | Source — FMP `commodity` + cash-flow statements |
| Crown macro artifact ingestion — `readings.breadth.*`, `.volatility.*`, `.positioning.*`, `.divergence.*`, `status`, `limits` | crown (all 12 requirements) | route `aqe_crown_macro.json` | top-level block | Build — the file is published daily; nothing ingests it, and no taxonomy row covers it |
| Raw per-bar OHLC history | raschke, seow | `bars_20d[]` | `daily_list` | Build |
| Force Index — 2-bar and 13-bar EMAs | elder-lens | `force_index_2`, `force_index_13` | `daily_list` | Build |
| Fitted regression price channel | elder-lens | `channel_upper`, `channel_lower` | `daily_list` | Build |
| Days held on an open position | seow, steenbarger | `days_held` | `held_positions` | Build — `trade_date` ships on the record but has no taxonomy row |
| High since entry | seow | `high_since_entry` | `held_positions` | Build |
| Realised exit prices vs planned levels | steenbarger, thorp | `exit_actual`, `exit_vs_planned_r` | `held_positions` | Build — join the trade journal's fills onto the bracket |
| CCI(20) | seow | `cci_20` | `daily_list` | Build |
| SMA(40) and the 20-day slope of SMA(20) | seow | `ma_40`, `ma_20_slope` | `daily_list` | Build |
| Daily stochastic %K/%D (14,3) | seow, raschke | `stoch_k`, `stoch_d` | `daily_list` | Build — only a weekly-39 stochastic exists, unexported |
| 63-day stock / index / industry-group returns | seow, oneil | `ret_63d`, `index_ret_63d`, `industry_group_ret_63d` | `daily_list` | Build |
| Tick size | seow | `tick_size` | `daily_list` | Source — broker contract detail |
| Days since the last swing high | seow | `days_since_swing_high` | `daily_list` | Build — the pivot ships, its age does not |
| 10-day percentage run | seow | `pct_run_10d` | `daily_list` | Build |
| Integer day count to next earnings | detect-lens, minervini, oneil | `days_to_earnings` | `daily_list` | Build — the band exists, the number does not |
| Countable VCP contraction sequence with per-contraction depth | minervini | `vcp_contractions[]`, `vcp_count` | `daily_list` | Build |
| Wyckoff turning-point label — spring / upthrust / secondary test / shakeout | wyckoff | `turning_point_type`, `penetration_event` | `daily_list` | Build — a naming layer over fields that already ship |
| Wyckoff wave triad — wave length, cumulative wave volume, wave duration | wyckoff | `wave_read{}` | `daily_list` | Build |
| Per-ticker gap-risk flag | thorp | `gap_risk_flag` | `daily_list` | Build — `held_book` carries gap scenarios at portfolio level only |
| Expected holding days and monitoring interval | thorp | `expected_hold_days`, `monitoring_interval` | `daily_list` | Build |
| Backtest trade count, sample window, rules generated, edge vs trailing median | thorp, steenbarger | `backtest_trade_count`, `sample_start`, `sample_end`, `rules_generated_count`, `signal_edge_trailing_median` | `daily_list` | Build |
| Portfolio value, per-trade risk %, position size % | seow, thorp | `portfolio_value`, `risk_pct`, `position_size_pct` | Aegis-side, not AQE | Build — sizing plane, Charter §4.5 |
| Committee nomination count per name | rogers | `nomination_count` | Aegis-side, not AQE | Build — tally output, Charter §3.7 |
| Country macro — sovereign debt, currency regime, savings rate, demographics, rule of law | rogers | — | — | Won't build — country research, not a stock scanner |
| Named 12–36 month catalyst | rogers | — | — | Won't build — human judgement |
| Order-fill difficulty as size scales | livermore | — | — | Won't build — needs live order-book simulation |
| Intraday time & sales / L2 print sequence | livermore, detect-lens | — | — | Won't build — AQE is end-of-day; VWAP part is already served (section 2) |

---

## 4. CONFLICTS

| Concept | AQE's name & definition | What the voice's canon assumes | The conflict | Suggested resolution |
|---|---|---|---|---|
| Volume participation | `day_vol` — today's volume over its own 20-day prior average. Renamed from `rvol` on 2026-08-05; ships `daily_list` | `rvol` (oneil). `day_vol` (livermore, minervini, raschke, rogers, wyckoff) | oneil's canon still names the retired `rvol`. The 2026-07-28 export carries `rvol` and no `day_vol`; the taxonomy carries `day_vol` and no `rvol`. voice_data_map wrongly labelled `day_vol` a "phantom menu entry" | Update oneil's canon to `day_vol`. Nothing else to fix — it resolves when AQE next runs |
| Volume-profile location | `energy.vp_position_score` — "range-position **proxy** for volume-profile location. The true VP array (POC/VAH/VAL) is diagnostic only in Pine and is not computed here" | wyckoff reads it as a volume-profile location (Wyckoff 2.0 / Villahermosa) | It is a 50-bar high/low range position, not a volume profile. No POC, VAH or VAL exists anywhere in AQE | Rename the voice's requirement to "range position", or record volume profile as permanently unserved in wyckoff's canon |
| Earnings proximity | `structure.earn_score` — 0–10, where **higher means further away**: `days<=5→0.0, days<=10→4.0, days<=20→7.0, days>20 or NA→10.0` | detect-lens, minervini, oneil want "how close is earnings" | Sign is inverted against intuition, and a **missing earnings date scores 10** — identical to a name three weeks clear. A voice cannot distinguish "safe" from "unknown" | Ship the integer `days_to_earnings` alongside, with an explicit null for unknown |
| Weekly trend | `structure.wk_score` — weekly close vs weekly SMA10, banded 0–15, **7.5 when no weekly data is available** | elder-lens, seow read it as a weekly trend strength | The no-data value sits inside the live scoring range and is indistinguishable from a genuine mid reading | Emit a separate `wk_data_available` boolean, or move the no-data value out of band |
| Institutional money | `sc_momentum.flow` — "money flow: institutional accumulation vs distribution", built from MFI/CMF, A/D regression slope and up/down volume skew | lynch, minervini, oneil canons assume an ownership register — % held, holder count, insider activity | A price/volume behavioural inference is being read as a holdings fact | Keep `flow` as the behavioural read; source 13F separately (section 3). Do not let one stand in for the other |
| Statistical significance | `knn_prob.knn_significant` — "clears 0.60/0.40. Charter Amendment v2.8: at k=5 this is a **PLAIN THRESHOLD CHECK, not a significance test**" | detect-lens reads `knn_significant` as an inferential result | The field name asserts significance the computation does not deliver — 3-of-5 neighbours agreeing | Rename to `knn_threshold_clear`, or have detect-lens cite the amendment inline whenever it reads the field |
| Probability target vs tradeable target | `qs.qs.objective` — the ±2×ATR14 level the odds were measured against. "The yardstick, not the tradeable bracket. **Never merge with `bracket.targets`**" | thorp's `target` / `expected_gain_r` naturally merge a probability with a target price | Merging the QS odds with the bracket's targets would attribute a calibrated probability to a level it was never measured against | Keep them separate in thorp's packet; label the QS objective explicitly as a yardstick |
| PTRS vs SC_MOMENTUM | `sc_momentum` is the momentum composite; `ptrs` = SC_MOMENTUM with SH hard-coded to 0 in live code | detect-lens reads `ptrs` and `sc_momentum` as two distinct inputs | They are the same number. `CLAUDE.md` still documents `PTRS = SC_MOMENTUM + SH` | Fix the doc to match the code; detect-lens should read one field, not two |
| 12-month return | `momentum_composite.ret_12m_score` — a **banded 0–20 score** on the 12-month return skipping the most recent month. Ships as `pr_ret_12m` in `subcomponents.pipe`, not under its taxonomy name | thorp / minervini would read a 12-month return | It is a score, not a return, and the shipped key differs from the taxonomy's field name | Read it as a score only. Note the alias in the field menu |
| Weekly stochastic + OBV | `sc_position.k39_gate` — `stoch(weekly,39)>50 AND obv_weekly>sma(obv_weekly,30)`. **NOT EXPORTED** | seow and raschke assume a daily stochastic (14,3) | Computed but unreachable, and on a different timeframe and period than either voice's canon | Export `k39_gate` for what it is; build a daily 14/3 stochastic separately if seow's canon requires it |
| Base-quality engine | `sc_position` and its whole `bq` tree — `bq_range_tight`, `bq_vol_dry`, `bq_base_dur`, `bq_ema_conv`. **NOT EXPORTED** ("confirmed never exported: computed into scores_daily, absent from all 162 records"). The `bq.*` sub-scores do appear under `subcomponents.bq` | minervini's base-building read, and any 3–6 week hold thesis | The composite is computed on every name and thrown away, while its own children ship | Export `sc_position` and `bq`, or record them as deliberately internal |
| Squeeze internals | `squeeze_score.bwp` (bandwidth 50-bar percentile) and `squeeze_score.sq` (BB inside KC). Both **NOT EXPORTED**; only the rolled-up `energy.squeeze_score` ships | wyckoff needs the squeeze state and the bandwidth percentile separately | A voice reading only the 0–12.5 roll-up cannot tell a tight squeeze from a mid-range bandwidth | Export `bwp` and `sq` — or use the new `was_squeezed` / `squeeze_breakout_state`, which do ship |
| Overhead supply | `resist_score.dist_to_resist` — distance from close to the 50-bar high. **NOT EXPORTED**; only `structure.resist_score` (0–10) ships | wyckoff and oneil want the actual distance to overhead resistance | The number is computed, only the band ships | Export `dist_to_resist` |
| Path quality | `pipe_rank.fip_quality` and `fip_quality.fip_raw`. **NOT EXPORTED**; only `fip_spike_excluded` and `fip_window_effective` ship | thorp's path-quality / smoothness read | The two housekeeping flags ship and the score they describe does not | Export `fip_quality` |
| Held-position trend integrity | `hl_score`, `hl_score.hl_state` — `held_positions only` | seow and steenbarger read trend integrity per candidate | A held-only field cannot inform an entry decision on a name not yet owned | Either compute `hl_score` for all `daily_list` rows, or restrict the voices' recognisers to held names |
| Broker stop / targets / mark | `held.live_px`, `held.held_sl`, `held.held_tp1`, `held.held_tp2`, `held.unreal_usd` — all `held_positions only` | seow's `current_stop`, `stop`, `target`; thorp's `entry_price` | Not available per-ticker on `daily_list`. Also `held.live_px` is "the SAME FMP close every other field is scored against, **not** a separate live quote" — voices treating it as a live mark are wrong | Read `bracket.stop`/`bracket.targets` for unheld names; treat `live_px` as an EOD close. Broker stop truth is Charter §0.5 |
| Unrealised P&L | `held.unreal_usd` — flagged **NOT YET WIRED**: "reads a journal field the 2026-07-28 journal restructure renamed" | steenbarger and seow read open P&L | The field exists and is broken | Repoint it at the renamed journal field before any voice consumes it |
| Basket breadth | `thematic_grade.breadth_pct` and `thematic_grade.parent_capped_grade` — `daily_list[].thematic_baskets[]`, **nested per-basket** | druckenmiller wants a single per-name or market-wide breadth read | Only reachable by iterating a name's baskets; there is no scalar breadth on the row | Project a per-ticker `breadth_pct` for the name's primary basket, or source exchange-wide breadth (section 3) |
| Sector detail | `grade`, `grade.grade_path`, `grade.grade_trend`, `grade.sh_value`, `etf`, `sector`, `gics_gate.entry_gate_reason` — `srm[] block only (not projected per-ticker)` | druckenmiller reads `srm[].*` directly (correct); wyckoff and oneil read per-ticker sector state | Per-ticker consumers get only `grade.gics_gate`, `grade.sector_trend_state`, `sector_rrg_quadrant` — not the grade path or trend | Fine as-is for druckenmiller. Others must join through `gics_sector`, or accept the projected subset |
| Days-held input | `trade_date` ships on every `held_positions` record in the live export but has **no row in the 272-row taxonomy** | seow's `days_held` | The only input to days-held is undocumented, so it can be renamed or dropped without anyone noticing | Add a taxonomy row for `held.trade_date` before building `days_held` on top of it |
| ATR period | `atr_14d` — 14-day ATR, absolute price | thorp names `atr_14`; seow names `atr20` | thorp is a naming mismatch only. seow assumes a 20-period ATR that does not exist — `atr_14d` is the only ATR on the row | Alias `atr_14` → `atr_14d`. Correct seow's canon to 14, or build ATR20 |
| Realised volatility | `vol_30d_ann` — annualised realised volatility, 30-session daily log returns | thorp names `realised_vol_30d` | Naming mismatch only | Alias in the field menu |
| Beta | `beta_30d` and `beta_30d.beta_252d` — "a separate inline computation, **not the same code path**" (`scanner/betas.py` vs inline) | The β30d gate, Charter §4.5 | Two betas from two code paths on one row; a voice picking the wrong one sizes differently | Keep `beta_30d` as the sizing input per §4.5; label `beta_252d` context-only |
| Range position, computed twice | `vp_position_score.en_pos50` and `ms_pos_score.ms_p50` — "IDENTICAL formula, independently implemented" | detect-lens reads `subcomponents.energy.en_pos50`; wyckoff reads `structure` | Two fields, one meaning, two code paths that can drift | Collapse to one, or document the duplication in the field glossary |
| Extension lens | `lens.extension` — present in the `lens` dict but "extension never counted" in `lens_positive` / `lens_warnings` | detect-lens R5 is written around it being null | Consistent with the standing PM ruling — no defect, but the field is live in the dict and empty in the counts | Leave as-is. Already documented |
| Retired blocks | `srm_signals` and `_radar_pool` are top-level keys in the 2026-07-28 export; both are **absent from the taxonomy** (`srm_signals` retired at `6316471`) | Any consumer reading the 2026-07-28 file | A voice built against the stale export may read a block that no longer exists | Do not read `srm_signals` or `_radar_pool`. Re-run AQE and rebuild menus against the new export |

---

## 5. NEW SINCE MY ANALYSIS

42 taxonomy fields that ship but are absent from `aegis/output/aqe_daily_export.json` @ 2026-07-28.

| AQE field | What it is | Which voice it would serve | Was it in my missing list? |
|---|---|---|---|
| `qs` | Quiet Strength read for the name; an absent key means QS could not evaluate it, not a poor score | thorp, steenbarger | No |
| `qs.qs.state` (`qs{}`) | QS's own regime read at scoring time | thorp, druckenmiller | No |
| `qs.qs.objective` (`qs{}`) | The ±2×ATR14 level the odds were measured against — a yardstick, not a bracket | thorp | No |
| `qs.qs.odds.p` (`qs{}`) | Calibrated probability of touching the objective within 20 sessions, from a frozen look-alike table | thorp | Yes — as `signal_stats{}`, called "needs building" |
| `qs.odds.p.qs.odds.extrapolated` (`qs{}`) | The probability was extrapolated from neighbouring buckets, not read directly | thorp | Yes — same item |
| `qs.qs.engine.recipe_hits` (`qs{}`) | How many of the 40 frozen recipes the name matches | thorp, detect-lens | No |
| `qs.qs.engine.qs_persist` (`qs{}`) | Prior stored sessions the name has scored — not calendar days | steenbarger, seow | Partly — I asked for `days_held`; this is not it |
| `qs.qs.unevaluable_vetoes` (`qs{}`) | Which of the 5 frozen vetoes could not be evaluated | thorp | No |
| `qs_market` (`qs{}`) | The regime terciles QS's lenses were scored against on this run | thorp, druckenmiller | No |
| `qs_status` (`qs{}`) | OK / DEGRADED / UNAVAILABLE — separates a QS outage from a quiet market | thorp | No |
| `on_qs` | Quiet Strength emitted a read for this name | thorp | Yes — as universe membership, Section 1 |
| `pattern` | Chart-pattern detector over a 126-bar (~6 month) window | oneil, minervini, wyckoff | No |
| `pattern.pattern_fit` | Geometric match quality, 0–1; PATTERN_MIN_FIT=0.50 is the floor for a real match | oneil, minervini | No |
| `pattern.pattern_stage` | Where the pattern sits in its own lifecycle | oneil, minervini, wyckoff | No |
| `pattern.pattern_trigger` | The breakout/breakdown price that would confirm the pattern | oneil, livermore | No |
| `pattern.pattern_invalidation` | The price that would invalidate the pattern read | wyckoff, minervini | No |
| `pattern.pattern_direction` | Direction implied by the detected pattern | oneil, wyckoff | No |
| `pattern.pattern_days` | Bars the pattern has been forming | minervini | Partly — related to `base_days` |
| `pattern.pattern_start` | Date the pattern's formation began | minervini | No |
| `pattern.pattern_alt` | Every other detector that also matched, comma-joined | detect-lens | No |
| `pattern_w` | The same 6-detector sweep on weekly bars | oneil, minervini, elder-lens | Yes — as `weekly_trend_dir` |
| `pattern_w.pattern_w_dir` | Direction of the weekly pattern | elder-lens | Yes — same item |
| `pattern_w.pattern_w_stage` | Lifecycle stage of the weekly pattern | oneil | No |
| `pattern_w.pattern_w_trigger` | Weekly breakout/breakdown trigger price | livermore | No |
| `candle_d` | Single/multi-bar candlestick geometry on the last daily bar, 3-bar patterns first down to DOJI | wyckoff, detect-lens, seow | No |
| `candle_d.candle_d_dir` | Direction implied by `candle_d` | wyckoff, detect-lens | No |
| `candle_w` | The same detector on the current weekly bar | elder-lens, seow | Yes — as `weekly_trend_dir` |
| `candle_w.candle_w_dir` | Direction implied by `candle_w` | elder-lens | Yes — same item |
| `candle_w.candle_w_date` | Date of the weekly bar `candle_w` was read from | elder-lens | No |
| `squeeze_breakout_state` | Bollinger-squeeze breakout event on the last closed bar | wyckoff, minervini, livermore | Partly — I asked for squeeze internals via `subcomponents` |
| `squeeze_breakout_state.squeeze_breakout_date` | Date of the breakout, if any | livermore | No |
| `squeeze_breakout_state.squeeze_breakout_volume_confirmed` | Whether breakout-bar volume was above its own 20-bar average | wyckoff, oneil | No |
| `was_squeezed` | Whether the last bar is currently squeezed, independent of a breakout | wyckoff, minervini | No |
| `vwap_14d_position` | Last close vs the rolling 14-session VWAP | raschke, livermore, seow | Yes — I put VWAP in WON'T BUILD |
| `vwap_14d_position.vwap_14d` | The rolling 14-session volume-weighted average price | raschke, seow | Yes — same item |
| `day_vol` | Today's volume over its own 20-day prior average (renamed from `rvol`, 2026-08-05) | 8 voices | Yes — flagged as the rename, Section 5 item 2 |
| `structure_shift.last_pivot_high` | The confirmed pivot high the structure read is measured against, shipped so a consumer need not recompute | wyckoff, seow, elder-lens | Yes — as Wyckoff `range_high` |
| `atr_quarter_stop` | A volatility stop offered beside the structural bracket — not the bracket, not a gate | raschke, thorp | No |
| `atr_quarter_stop.atr_quarter_risk_pct` | That stop's distance as a percent of entry | thorp | No |
| `thematic_grade.breadth_pct` (nested per-basket) | Fraction of basket constituents above their own 20-day SMA | druckenmiller | Yes — as in-house breadth, "needs building" |
| `thematic_grade.parent_capped_grade` (nested per-basket) | What the thematic grade would read if still clamped at the parent GICS grade | druckenmiller, oneil | No |
| `grade.grade_path` (`srm[]` only) | Which of the grade's rules actually fired | druckenmiller | No |

---

## 6. UNUSED CAPACITY

Fields AQE ships that no voice's canon or menu asks for. 25 most substantive; plumbing excluded.

| AQE field | What it is | No voice currently requests it |
|---|---|---|
| `floor` | The weakest of the four core engines — a name is only as strong as its worst leg | Not on any canon or menu. Also missing from the export's own `_FIELD_GLOSSARY` |
| `pattern` + 8 sub-fields | 126-bar chart-pattern detector with fit, stage, trigger, invalidation, direction, age and alternatives | New; no canon references it |
| `candle_d`, `candle_w` (+ direction, date) | Daily and weekly candlestick geometry with implied direction | New; no canon references it |
| `was_squeezed`, `squeeze_breakout_state` (+ date, volume flag) | Current squeeze state and the breakout event with volume confirmation | New; wyckoff would want it |
| `qs` block — `qs.state`, `qs.objective`, `qs.odds.p`, `qs.engine.recipe_hits`, `qs.engine.qs_persist`, `qs.unevaluable_vetoes`, `qs_market`, `qs_status` | The whole Quiet Strength probability engine | New; thorp's requirement was written before it existed |
| `atr_quarter_stop`, `.atr_quarter_risk_pct` | A volatility stop and its risk % offered beside the structural bracket | No canon references it |
| `mp.mp_accel` | Additive momentum acceleration, outside the Pine spec | Voices read `mp_accel_state` (the label) but never the number |
| `pipe_rank`, `pipe_rank.pipe_tier`, `pipe_rank.momentum_composite` | The pre-screen rank that orders the scoring queue, its tier label and the 5×20-point composite behind it | No canon references it |
| `momentum_composite.pr_adx_score`, `.rsi_score`, `.vol_score`, `.ma_score`, `.ret_12m_score` | RSI(14) zone, ADX(14) strength, 5/20 volume band, MA stack, 12-month return band | RSI is nowhere else in the export and no voice asks for it |
| `sc_momentum.sc_momentum_raw` | The same weighted average read before the gates are applied | Only the gated `sc_momentum` is consumed |
| `sc_m_gates.sc_m_gate_detail`, `sc_p_gates.sc_p_gate_detail` | Per-engine pass/fail breakdown behind the gate booleans | On no canon — the "why did it fail" evidence is unread |
| `flow_score.mfi`, `flow_score.cmf` | Money Flow Index(14) and Chaikin Money Flow(20) | wyckoff and detect-lens read `flow` only, never its two named oscillators |
| `flow.accum_score`, `flow.volume_score`, `flow.skew_score`, `flow.flow_score` | A/D regression slope, volume trend + spike, up/down volume skew, MFI/CMF joint band | The whole Flow evidence layer is unread |
| `energy.vp_position_score`, `.price_action_score`, `.squeeze_score` | Range position, higher-lows/tightness/pullback, squeeze state | detect-lens reads only `en_pos50`, `exhaustion_score`, `atr_score` |
| `exhaustion_score.en_trend_bars` | Consecutive bars closing above EMA20 | On no canon |
| `structure.rs_spy_score`, `rs_spy_score.rs_vs_spy`, `structure.rs_accel_score`, `rs_accel_score.rs_accel` | 60-day relative performance vs SPY and its 20-vs-60-day acceleration | oneil and minervini read `rs_leadership`/`rs_spy_20d` but never these |
| `structure.base_score`, `base_score.base_days`, `bq_base_dur.bq_base_days` | Base duration and quality, latched through breakout, decaying after | minervini's base read never touches them |
| `structure.ms_pos_score`, `structure.resist_score`, `structure.wk_score`, `structure.earn_score` | 50-bar range position, overhead clear air, weekly trend, earnings proximity | All four ship in `subcomponents.structure`; none is on a menu |
| `mp.abs_mom_score`, `abs_mom_score.roc_zscore`, `mp.rel_mom_score`, `rel_mom_score.excess_return`, `mp.trend_score`, `adx_score.di_bullish` | The full MP evidence layer — ROC z-score, 20-day excess return, MA stacking, DI direction gate | Only `adx_val` is on a menu (raschke) |
| `bq.bq_range_tight`, `.bq_vol_dry`, `.bq_base_dur`, `.bq_ema_conv` | Range tightness, volume dry-up, base duration, EMA(8/13/21) convergence | Ship under `subcomponents.bq` while their parent `bq` does not. Minervini's VCP read wants all four |
| `fib_swing_low.fib_236/.fib_382/.fib_500/.fib_618/.fib_786`, `.fib_swing_high` | A five-level Fibonacci support ladder and the swing high | seow reads `fib_swing_low` alone; the ladder is unread |
| `hl_score`, `hl_score.hl_state` (`held_positions only`) | Composite trend-integrity read and action band for a held position | On no canon at all — the held-book's own health score is unread |
| `elder.elder_context` | Hourly VWAP / VCP / exhaustion read behind the elder pattern | elder-lens reads `elder_5d` and `elder_pattern` but not the context that produced them |
| `sector_rrg_quadrant`, `.sector_rrg_direction`, `thematic_grade.thematic_rrg_quadrant`, `thematic_rrg_quadrant.thematic_rrg_direction` | RRG quadrant and direction vs SPY, per sector and per basket | druckenmiller reads the `srm[]` copies; the per-ticker projections are unread |
| `fip_quality.fip_spike_excluded`, `.fip_window_effective` | Whether the last bar sits in a spike-exclusion window, and the effective FIP window length | On no canon — and the score they qualify is not exported |
| `beta_30d.beta_252d`, `rs_leadership.rs_down_day_20d` | 252-day beta vs SPY, and 20-day outperformance measured only on SPY's down days | minervini reads `rs_leadership` (the label) but not the number behind it |
