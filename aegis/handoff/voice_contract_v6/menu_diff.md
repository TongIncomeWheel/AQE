# Menu diff — voice_menus.json (1.13.0) -> v6 generated

## detect-lens: 25 -> 49  (removed 17, added 41)
removed (no canon rule reads them): bracket.atr_fallback_stop, bracket.invalid_reason, bracket.risk_pct, bracket.stop, bracket.valid, day_vol, elder_context.exhaustion_check.exhaustion_flag, elder_context.vwap_5d.position, elder_context.vwap_5d.slope_5d, lens, ma_100, ma_200, ma_50, pct_from_52w_high, stack_state, structure_shift, vwap_14d_position
added (canon rule reads them, never served): choch_date, choch_state, days_to_earnings, div_bear_count, div_bull_count, div_date, div_oscs, div_state, elder, energy, entry, flow, held, inside_bar, knn_neighbors_used, knn_prob, knn_threshold_clear, knn_tp1, knn_tp2, knn_tp3, lens.coil, lens.insti_money, lens.leadership, lens.resistance, lens.sector, lens.structure, mover_subtype, mp, pib_pattern, pin_bar_date, pin_bar_level, pin_bar_state, premove_conviction_label, runner_conviction_label, sc_momentum, source, structure, subcomponents.energy.atr_score, subcomponents.energy.en_pos50, subcomponents.energy.exhaustion_score, subcomponents.flow.ext_score

## druckenmiller: 7 -> 51  (removed 6, added 50)
removed (no canon rule reads them): beta_30d, gics_sector_name, sc_momentum, sector_trend_state, thematic_basket, thematic_grade
added (canon rule reads them, never served): atr_14d, bracket.invalid_reason, bracket.risk_pct, bracket.rr, bracket.rr_tp1, bracket.stop, bracket.stop_type, bracket.targets, bracket.valid, days_to_earnings, entry, held, intermarket.hyg.hyg_tlt_spread, intermarket.hyg.roc20, intermarket.spy_iwm.iwm_roc20, intermarket.spy_iwm.spread, intermarket.spy_iwm.spy_roc20, intermarket.tlt.above_sma20, intermarket.tlt.roc20, intermarket.tlt.roc5, intermarket.uup.roc20, intermarket.uup.roc5, macro_weather.copper_gold_direction, macro_weather.copper_gold_roc20, macro_weather.cper_direction, macro_weather.gld_direction, macro_weather.hyg_direction, macro_weather.iwm_direction, macro_weather.regime_description, macro_weather.tlt_direction, macro_weather.uso_direction, macro_weather.uup_direction, regime.level, regime.vix, regime_stop_pct_ceiling, source, spy_roc_20d, srm[].entry_gate, srm[].grade, srm[].macro_headwind_flag, srm[].macro_headwind_score, srm[].rrg_direction, srm[].rrg_quadrant, srm[].rrg_rs_momentum, srm[].rrg_rs_ratio, srm[].sector, srm[].trend_state, thematic_baskets.*.grade, thematic_baskets.*.rrg_direction, thematic_baskets.*.rrg_quadrant

## elder-lens: 18 -> 24  (removed 7, added 13)
removed (no canon rule reads them): elder, elder_context.volume.up_bar_vol_ratio, elder_context.vwap_5d.position, elder_context.vwap_5d.slope_5d, elder_hi7_streak, mp, vwap_14d_position
added (canon rule reads them, never served): atr_14d, bracket.invalid_reason, bracket.risk_pct, bracket.rr, bracket.rr_tp1, bracket.stop, bracket.stop_type, bracket.targets, bracket.valid, days_to_earnings, held, malformed_bracket, source

## livermore: 29 -> 24  (removed 10, added 5)
removed (no canon rule reads them): bracket.atr_fallback_stop, elder_context.vwap_5d.position, elder_context.vwap_5d.slope_5d, high_52w, next_earnings_date, pct_from_52w_high, pct_from_pivot, pivot_high, rs_rank_pct, vwap_14d_position
added (canon rule reads them, never served): bracket.rr, bracket.rr_tp1, bracket.targets, days_to_earnings, source

## lynch: 11 -> 16  (removed 2, added 7)
removed (no canon rule reads them): bracket.atr_fallback_stop, bracket.invalid_reason
added (canon rule reads them, never served): atr_14d, days_to_earnings, entry, ma_200, ma_50, source, structure

## minervini: 45 -> 30  (removed 21, added 6)
removed (no canon rule reads them): bracket.atr_fallback_stop, div_bear_count, div_state, elder_context.vcp.base_range_pct, elder_context.vcp.current_range_pct_5d, elder_context.vcp.vcp_label, elder_context.vcp.vcp_tightness_pct, elder_pattern, high_52w, low_52w, ma_150, mp_accel_state, next_earnings_date, pct_from_52w_high, pct_from_pivot, pivot_high, rs_down_day_20d, rs_rank_pct, squeeze_breakout_state, squeeze_breakout_volume_confirmed, was_squeezed
added (canon rule reads them, never served): atr_14d, bracket.rr, bracket.rr_tp1, bracket.targets, days_to_earnings, source

## oneil: 47 -> 24  (removed 28, added 5)
removed (no canon rule reads them): bracket.atr_fallback_stop, bracket.invalid_reason, bracket.rr, bracket.targets, div_bear_count, div_state, elder_context.vcp.base_range_pct, elder_context.vcp.current_range_pct_5d, elder_context.vcp.vcp_label, elder_context.vcp.vcp_tightness_pct, elder_context.vwap_5d.position, elder_context.vwap_5d.slope_5d, elder_pattern, energy, flow, gics_sector_name, high_52w, lens, mp_accel_state, next_earnings_date, pct_from_52w_high, pct_from_pivot, pivot_high, ret_12m, rs_down_day_20d, rs_rank_pct, rs_spy_20d, vwap_14d_position
added (canon rule reads them, never served): days_to_earnings, lens.coil, lens.sector, lens.structure, source

## raschke: 31 -> 30  (removed 14, added 13)
removed (no canon rule reads them): bracket.atr_fallback_stop, div_bear_count, div_state, elder_context.vwap_5d.position, elder_context.vwap_5d.slope_5d, elder_pattern, extension_atr_20, lens, next_earnings_date, pivot_high, squeeze_breakout_state, squeeze_breakout_volume_confirmed, vwap_14d_position, was_squeezed
added (canon rule reads them, never served): bracket.rr, bracket.rr_tp1, bracket.targets, days_to_earnings, lens.coil, lens.insti_money, lens.leadership, lens.resistance, lens.sector, lens.structure, lens_positive, lens_warnings, source

## rogers: 25 -> 25  (removed 5, added 5)
removed (no canon rule reads them): bracket.atr_fallback_stop, ma_200, next_earnings_date, rs_rank_pct, rs_spy_20d
added (canon rule reads them, never served): atr_14d, bracket.rr, bracket.rr_tp1, bracket.targets, source

## seow: 17 -> 14  (removed 11, added 8)
removed (no canon rule reads them): atr_caution, bracket.atr_fallback_stop, bracket.invalid_reason, bracket.valid, extension_atr_20, ma_100, ma_200, ma_50, mp_state, sector_trend_state, sma_distance_pct
added (canon rule reads them, never served): atr_14d, bracket.risk_pct, bracket.targets, days_to_earnings, fib_swing_low, held, source, srm[].roc20

## steenbarger: 20 -> 18  (removed 10, added 8)
removed (no canon rule reads them): bracket.atr_fallback_stop, day_vol, div_bear_count, div_state, gics_sector_name, lens_warnings, pct_from_52w_high, rs_rank_pct, sc_momentum, structure_shift
added (canon rule reads them, never served): bracket.rr, bracket.rr_tp1, bracket.stop_type, bracket.targets, days_to_earnings, entry, held, source

## thorp: 24 -> 15  (removed 15, added 6)
removed (no canon rule reads them): atr_caution, beta_30d, bracket.atr_fallback_stop, bracket.invalid_reason, bracket.price, bracket.rr_tp1, bracket.rr_tp2, bracket.stop_atr_dist, bracket.valid, day_vol, knn_prob, knn_threshold_clear, sc_m_gate_detail, sc_momentum, sc_p_gate_detail
added (canon rule reads them, never served): days_to_earnings, elder_context.volume.avg_vol_20d, entry, held, low_52w, source

## weis: 44 -> 25  (removed 21, added 2)
removed (no canon rule reads them): atr_caution, bracket.atr_fallback_stop, bracket.invalid_reason, bracket.risk_pct, bracket.stop, bracket.stop_type, bracket.valid, div_bear_count, div_state, elder_context.vcp.current_range_pct_5d, elder_context.vcp.vcp_label, elder_context.volume.up_bar_vol_ratio, elder_context.vwap_5d.position, elder_context.vwap_5d.slope_5d, elder_pattern, energy, flow, next_earnings_date, stack_state, structure, vwap_14d_position
added (canon rule reads them, never served): held, source

## wyckoff: 44 -> 27  (removed 20, added 3)
removed (no canon rule reads them): atr_caution, bracket.atr_fallback_stop, bracket.invalid_reason, bracket.rr, bracket.targets, bracket.valid, elder_context.vcp.base_range_pct, elder_context.vcp.current_range_pct_5d, elder_context.vcp.vcp_label, elder_context.vcp.vcp_tightness_pct, elder_context.volume.up_bar_vol_ratio, elder_context.volume.vol_trend_5d, elder_pattern, extension_atr_20, lens, ma_20, pivot_high, squeeze_breakout_state, squeeze_breakout_volume_confirmed, was_squeezed
added (canon rule reads them, never served): days_to_earnings, held, source
