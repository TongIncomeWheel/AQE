# AQE component review - evidence table (2026-11-19)

Evidence for the expert review only. No recipe is proposed and nothing is tuned. Full table: `tables/component_review_table.csv` (79 rows = 10 aggregates + 69 sub-scores, 62 columns). Scripts: `scripts/component_stats.py`, `component_meta.py`, `component_table.py`, `component_md.py`.

## Data and definitions

- Panel: `scripts/_panel.parquet` (from the 2026-11-19 extract), 2021-03-15 to 2026-11-18, PIT tradeability filter close>=$5 and 20d dollar volume>=$10M, 1,928,693 rows, ~1,424 signal dates. Universe and sector map are NOT point-in-time (today's screen applied backwards: survivorship).
- Target: forward excess return vs the equal-weight mean of names scored that date, close to close, h = 5/10/20 sessions (`fwd{h}_vs_ew`).
- Rank-IC: per-date Pearson of centred cross-sectional ranks (= Spearman), averaged over dates; t = Newey-West with lag h. "Neutral" = both the feature rank and the target rank residualised per date on vol rank, log dollar-volume rank and GICS-sector dummies (lib.neutralise).
- Years: 2021 (from 15 Mar) to 2026 (to 18 Nov, partial). `years_pos_*` = years with mean IC > 0, out of `years_with_data_*`. Per-year NW t computed for 36 cells (6 years x 3 horizons x raw/neutral).
- Variance shares: share of each feature's per-date cross-sectional rank variance explained by (a) vol rank alone, (b) log dollar-volume rank alone, (c) sector dummies alone, (d) all three; pooled over all dates.
- Redundancy: mean over 200 randomly sampled dates (seed 20261119) of the per-date Spearman matrix over the 79 columns. Tight cluster = complete linkage on 1-|rho| cut at 0.2, so every pair inside has |rho|>=0.8. `chain_group` = connected components of the |rho|>=0.8 graph (shows chaining). Negative rho counts (an inverted copy is still a copy).
- Categorical labels are coded ordinally for ranking (mp_state FADING<BUILDING<STRONG, impulse RED<NEUTRAL<GREEN, rd_state, hl_state, mp_accel_state, pipe_tier D<C<B<A); bd_mode is NOT ordinal (see NEEDS_REVIEW).

## Flag rules (fixed before looking at the result)

- DUPLICATE: nearest twin |rho| >= 0.80.
- VOL_PROXY / LIQUIDITY_PROXY / SECTOR_PROXY: variance share explained by vol alone / dollar volume alone / sector alone > 50%.
- DEAD: no full-sample |NW t| >= 2 in any of the 6 tests (raw and neutral, 5/10/20d) AND no single year-cell with |t| >= 3 (a stricter per-year bar because 36 cells are tested).
- SIGN_FLIPS: some year significantly positive (t>=2) and another significantly negative (t<=-2) on the same horizon and mode, OR (not DEAD and at its best test fewer than 5 of 6 years share the full-sample sign).
- CONSTANT_OR_DISCRETE: <= 5 distinct values, or one value on >= 80% of rows.
- NEEDS_REVIEW: a data-validity problem (see flag_note).
- `primary_flag` = first of NEEDS_REVIEW > DUPLICATE > VOL/SECTOR/LIQUIDITY_PROXY > DEAD > SIGN_FLIPS > CONSTANT_OR_DISCRETE; `all_flags` lists every flag; NONE = no rule fired.

## Flag counts (79 rows)

| flag | rows carrying it (all_flags) | rows where it is primary |
|---|---|---|
| DUPLICATE | 44 | 43 |
| VOL_PROXY | 1 | 1 |
| SECTOR_PROXY | 0 | 0 |
| LIQUIDITY_PROXY | 0 | 0 |
| SIGN_FLIPS | 8 | 5 |
| DEAD | 67 | 23 |
| CONSTANT_OR_DISCRETE | 23 | 0 |
| NEEDS_REVIEW | 3 | 3 |
| NONE | 4 | 4 |

## Headline facts

- No component (earn_score excluded, see NEEDS_REVIEW) clears |NW t| >= 2 at 10d or 20d after neutralisation (max |t| 1.76 at 10d, 1.96 at 20d). The largest full-sample |t| anywhere: rd_close_str neutral 5d t=2.67; bq_ema_conv raw 5d t=2.43; rd_vol_surge neutral 5d t=2.32; ext_score raw 5d t=1.98; bq_100 raw 10d t=1.98; rd_compression raw 10d t=1.93. All are 5-10 day effects with |IC| of 0.012 or less.
- All 10 aggregates carry DEAD: max |neutral IC| over 5/10/20d is 0.011 (k39_value 20d), max full-sample |t| 1.98.
- Volatility/sector/liquidity explain little of most components (median all-three share 13%); the one >50% proxy is base_days (vol alone 60%: longer bases = lower-vol names). Dollar volume explains <2% of every column.
- en_pos50 and ms_p50 are the same number (rho 1.000), as the glossary already notes. en_trend_bars vs hl_trend_bars rho 0.984 (EMA20 vs EMA21 run counts).
- earn_score varies across names on only 15 dates (2026-10-29 onward); before that it is the constant 10.0 default, so it cannot be evaluated here.

## (b) Five most redundant clusters (by size, then mean |rho|)

1. vp_position_score / en_pos50 / ms_pos_score / ms_p50 / trend_score: 5 columns, mean |rho| 0.89, min 0.83.
2. mp_100 / rel_mom_score / excess_return: 3 columns, mean |rho| 0.94, min 0.92.
3. rs_accel_score / rs_accel / rd_rs_bonus: 3 columns, mean |rho| 0.93, min 0.90.
4. volume_score / bq_vol_dry / pr_vol_score: 3 columns, mean |rho| 0.90, min 0.86 (contains inverted pairs).
5. en_trend_bars / hl_trend / hl_trend_bars: 3 columns, mean |rho| 0.87, min 0.81.

Other tight pairs: abs_mom_score/roc_zscore 0.94; rs_spy_score/rs_vs_spy 0.94; skew_score/hl_vol_updn 0.93; bq_range_tight/hl_atr_spike 0.87; hl_score/hl_state 0.87; mp_adx_score/pr_adx_score 0.87; momentum_composite/pr_ma_score 0.87; elder_score/impulse_state 0.86; mp_accel/mp_accel_state 0.84; bq_base_dur/bq_base_days 0.84; mfi/hl_flow 0.82; structure_100/wk_score 0.81.

Chaining: following |rho|>=0.8 links, G01 (24 cols) connects 24 columns (range position, 20d relative momentum, trend age, MA stack, Health), so these groups are not independent of each other either.

## (a) Blast radius: composites and gates that read a flagged row

Each line: the composite/gate, then every flagged row it depends on directly or through its parents ([primary flag]). Removing a row changes every item it reaches; the per-row chain is in the `blast_radius` column.

- **sc_momentum** (36): flow_100[DEAD], energy_100[DUPLICATE], structure_100[DUPLICATE], mp_100[DUPLICATE], flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD], vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD]
- **sc_position** (41): flow_100[DEAD], energy_100[DUPLICATE], structure_100[DUPLICATE], mp_100[DUPLICATE], bq_100[DEAD], flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD], vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD], bq_range_tight[DUPLICATE], bq_vol_dry[DUPLICATE], bq_base_dur[DUPLICATE], bq_base_days[DUPLICATE]
- **sc_m_gates** (38): flow_100[DEAD], energy_100[DUPLICATE], structure_100[DUPLICATE], mp_100[DUPLICATE], elder_score[DUPLICATE], impulse_state[DUPLICATE], flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD], vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD]
- **sc_p_gates** (43): flow_100[DEAD], energy_100[DUPLICATE], structure_100[DUPLICATE], mp_100[DUPLICATE], bq_100[DEAD], k39_value[DEAD], k39_gate[DEAD], flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD], vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD], bq_range_tight[DUPLICATE], bq_vol_dry[DUPLICATE], bq_base_dur[DUPLICATE], bq_base_days[DUPLICATE]
- **Longlist gate** (38): flow_100[DEAD], energy_100[DUPLICATE], structure_100[DUPLICATE], mp_100[DUPLICATE], elder_score[DUPLICATE], impulse_state[DUPLICATE], flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD], vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD]
- **Watchlist gate** (36): flow_100[DEAD], energy_100[DUPLICATE], structure_100[DUPLICATE], mp_100[DUPLICATE], flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD], vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD]
- **Elder list** (2): elder_score[DUPLICATE], impulse_state[DUPLICATE]
- **Precision Edge** (38): flow_100[DEAD], energy_100[DUPLICATE], structure_100[DUPLICATE], mp_100[DUPLICATE], k39_value[DEAD], flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD], vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD], pr_rsi_score[DEAD]
- **shortlist gate** (36): flow_100[DEAD], energy_100[DUPLICATE], structure_100[DUPLICATE], mp_100[DUPLICATE], flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD], vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD]
- **Pipeline Rank screen** (6): momentum_composite[DUPLICATE], pr_ret_12m[SIGN_FLIPS], pr_adx_score[DUPLICATE], pr_rsi_score[DEAD], pr_vol_score[DUPLICATE], pr_ma_score[DUPLICATE]
- **pipe_rank** (6): momentum_composite[DUPLICATE], pr_ret_12m[SIGN_FLIPS], pr_adx_score[DUPLICATE], pr_rsi_score[DEAD], pr_vol_score[DUPLICATE], pr_ma_score[DUPLICATE]
- **flow_100** (7): flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD]
- **energy_100** (6): vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE]
- **structure_100** (11): rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE]
- **mp_100** (8): abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD]
- **bq_100** (4): bq_range_tight[DUPLICATE], bq_vol_dry[DUPLICATE], bq_base_dur[DUPLICATE], bq_base_days[DUPLICATE]
- **elder_score** (1): impulse_state[DUPLICATE]
- **k39_gate** (1): k39_value[DEAD]
- **rd_score** (7): rd_compression[DEAD], rd_trigger[DEAD], rd_pos_mod[DEAD], rd_rs_bonus[DUPLICATE], rd_inside_bars[SIGN_FLIPS], rd_range_exp[DEAD], rd_vol_surge[SIGN_FLIPS]
- **hl_score** (8): hl_trend[DUPLICATE], hl_flow[DUPLICATE], hl_rs[DEAD], hl_risk[DEAD], hl_higher_lows[DEAD], hl_trend_bars[DUPLICATE], hl_vol_updn[DUPLICATE], hl_atr_spike[DUPLICATE]
- **held_positions export** (10): hl_score[DUPLICATE], hl_state[DUPLICATE], hl_trend[DUPLICATE], hl_flow[DUPLICATE], hl_rs[DEAD], hl_risk[DEAD], hl_higher_lows[DEAD], hl_trend_bars[DUPLICATE], hl_vol_updn[DUPLICATE], hl_atr_spike[DUPLICATE]
- **QS lens_total / calibration** (23): structure_100[DUPLICATE], elder_score[DUPLICATE], impulse_state[DUPLICATE], accum_score[SIGN_FLIPS], mfi[DUPLICATE], cmf[DEAD], en_pos50[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], rel_mom_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], bq_range_tight[DUPLICATE]
- **QS recipes** (32): k39_value[DEAD], impulse_state[DUPLICATE], skew_score[DUPLICATE], vp_position_score[DUPLICATE], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], base_days[VOL_PROXY], ms_p50[DUPLICATE], abs_mom_score[DUPLICATE], rel_mom_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], bq_range_tight[DUPLICATE], bq_base_dur[DUPLICATE], bq_base_days[DUPLICATE], pr_ret_12m[SIGN_FLIPS], pr_ma_score[DUPLICATE], rd_compression[DEAD], rd_pos_mod[DEAD], rd_inside_bars[SIGN_FLIPS], hl_score[DUPLICATE], hl_trend[DUPLICATE], hl_flow[DUPLICATE], hl_rs[DEAD], hl_risk[DEAD], hl_higher_lows[DEAD], hl_trend_bars[DUPLICATE], hl_vol_updn[DUPLICATE], hl_atr_spike[DUPLICATE]
- **QS vetoes** (12): volume_score[DUPLICATE], exhaustion_score[DEAD], en_trend_bars[DUPLICATE], earn_score[NEEDS_REVIEW], rs_accel[DUPLICATE], excess_return[DUPLICATE], momentum_composite[DUPLICATE], pr_ret_12m[SIGN_FLIPS], pr_adx_score[DUPLICATE], pr_rsi_score[DEAD], pr_vol_score[DUPLICATE], pr_ma_score[DUPLICATE]
- **QS why-text** (8): roc_zscore[DUPLICATE], mp_accel[DUPLICATE], momentum_composite[DUPLICATE], pr_ret_12m[SIGN_FLIPS], pr_adx_score[DUPLICATE], pr_rsi_score[DEAD], pr_vol_score[DUPLICATE], pr_ma_score[DUPLICATE]
- **Signal Radar** (52): flow_100[DEAD], energy_100[DUPLICATE], structure_100[DUPLICATE], mp_100[DUPLICATE], elder_score[DUPLICATE], bq_100[DEAD], k39_value[DEAD], impulse_state[DUPLICATE], flow_score[DEAD], accum_score[SIGN_FLIPS], volume_score[DUPLICATE], skew_score[DUPLICATE], ext_score[DEAD], mfi[DUPLICATE], cmf[DEAD], vp_position_score[DUPLICATE], price_action_score[DEAD], exhaustion_score[DEAD], atr_score[DEAD], en_pos50[DUPLICATE], en_trend_bars[DUPLICATE], rs_spy_score[DUPLICATE], rs_accel_score[DUPLICATE], base_score[DEAD], ms_pos_score[DUPLICATE], resist_score[DUPLICATE], wk_score[DUPLICATE], earn_score[NEEDS_REVIEW], base_days[VOL_PROXY], ms_p50[DUPLICATE], rs_vs_spy[DUPLICATE], rs_accel[DUPLICATE], abs_mom_score[DUPLICATE], mp_adx_score[DUPLICATE], rel_mom_score[DUPLICATE], trend_score[DUPLICATE], roc_zscore[DUPLICATE], excess_return[DUPLICATE], adx_val[SIGN_FLIPS], di_bullish[DEAD], bq_range_tight[DUPLICATE], bq_vol_dry[DUPLICATE], bq_base_dur[DUPLICATE], bq_base_days[DUPLICATE], momentum_composite[DUPLICATE], pr_ret_12m[SIGN_FLIPS], pr_adx_score[DUPLICATE], pr_rsi_score[DEAD], pr_vol_score[DUPLICATE], pr_ma_score[DUPLICATE], rd_compression[DEAD], rd_inside_bars[SIGN_FLIPS]
- **lens_consensus** (9): accum_score[SIGN_FLIPS], resist_score[DUPLICATE], momentum_composite[DUPLICATE], pipe_tier[NEEDS_REVIEW], pr_ret_12m[SIGN_FLIPS], pr_adx_score[DUPLICATE], pr_rsi_score[DEAD], pr_vol_score[DUPLICATE], pr_ma_score[DUPLICATE]
- **signal_ledger** (19): rd_score[DEAD], rd_state[DEAD], rd_compression[DEAD], rd_trigger[DEAD], rd_pos_mod[DEAD], rd_rs_bonus[DUPLICATE], rd_inside_bars[SIGN_FLIPS], rd_range_exp[DEAD], rd_vol_surge[SIGN_FLIPS], hl_score[DUPLICATE], hl_state[DUPLICATE], hl_trend[DUPLICATE], hl_flow[DUPLICATE], hl_rs[DEAD], hl_risk[DEAD], hl_higher_lows[DEAD], hl_trend_bars[DUPLICATE], hl_vol_updn[DUPLICATE], hl_atr_spike[DUPLICATE]

## Glossary gaps

26 rows have no glossary row under the extract's name; their description was read from source (cited in the `source` column): k39_value, ha_quality_count, bd_mode, mp_adx_score, pr_ret_12m, pr_rsi_score, pr_vol_score, pr_ma_score, rd_score, rd_state, rd_compression, rd_trigger, rd_pos_mod, rd_rs_bonus, rd_inside_bars, rd_range_exp, rd_vol_surge, rd_close_str, hl_trend, hl_flow, hl_rs, hl_risk, hl_higher_lows, hl_trend_bars, hl_vol_updn, hl_atr_spike.
The 7 engine totals are documented in the glossary under short names (flow, energy, structure, mp, elder, bq) rather than the extract name; k39_value has no row at all. Readiness (rd_*) and the hl_ sub-scores/diagnostics are absent from the glossary entirely (both are stripped from the export, drive_sync.py:3186-3188). pr_ret_12m: glossary (as ret_12m_score) says the 12-month return skips the latest month; the code (pipeline_rank.py:95) is close/close[231]-1, which does not skip it.

## Rows with no flag

ha_quality_count (best raw 5d, t=1.58), squeeze_score (best raw 5d, t=1.72), bq_ema_conv (best raw 5d, t=2.43), rd_close_str (best neutral 5d, t=2.67).

## Caveats

- Survivorship (today's universe applied backwards) and a current sector map bias the level of IC; they do not obviously bias the redundancy or exposure columns.
- 2026 is a partial year (Jan to 18 Nov; 20d targets end ~20 sessions earlier).
- Step scores with few levels produce many tied ranks; rank-IC still works but resolution is low (see n_distinct_values).
- The research panel is the scores_daily history as stored; nothing was recomputed.
