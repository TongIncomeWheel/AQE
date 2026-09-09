# AQE — what to deliver (2026-09-09, PM: Ash)

RULE: ADDITIVE ONLY. No existing key in `aegis/output/aqe_daily_export.json` is renamed, removed or re-valued. New keys only.

## 1. Test first
`tests/test_export_additive.py`: for every key in yesterday's export, the new export has the same key with the same value. Green before any edit. Stays green after every edit.

## 2. Add these keys to every `daily_list` row (src/data/drive_sync.py, beside `_new_engine_fields` at ~L1725 / ~L2146)

| key | definition | for |
|---|---|---|
| `bar_open`, `bar_high`, `bar_low`, `bar_close` | last completed daily bar, USD | seow |
| `prior_bar_high`, `prior_bar_low` | the bar before it | seow |
| `ma_20_slope_5d_pct` | (ma_20 / ma_20[-5] − 1) × 100 | seow |
| `ret_63d` | close / close[-63] − 1, pct | seow |
| `pct_run_10d` | close / close[-10] − 1, pct | seow |
| `base_low_20d` | min low of last 20 bars | seow |
| `days_since_swing_high` | sessions since `last_pivot_high.date` | seow |
| `bar_range_5d` | list of high−low for last 5 bars, oldest→newest | seow, raschke |
| `hi_20d`, `lo_20d`, `hi_50d`, `lo_50d`, `pos_in_50d_range_pct` | rolling extremes; `energy.py#L40-L45` already computes hi50/lo50/en_pos50 — expose those | raschke, wyckoff |
| `nr4_flag`, `nr7_flag`, `hv_ratio_6_100` | narrowest range of 4/7; 6d vs 100d historical vol | raschke |
| `adx_14` | Wilder ADX(14) — `mp.py` already computes it inside MP | raschke |
| `stoch_k_14`, `stoch_d_3` | fast %K(14), %D(3) | raschke |
| `rvol_20d` | day_vol / elder_context.volume.avg_vol_20d | oneil |
| `gap_risk_flag` | days_to_earnings not null and ≤ 10 | thorp |
| `cohort_hit_rate_20d`, `cohort_n` | copies of `signal_hit_rate_20d` / `signal_n` (old keys stay) | thorp |

Top level: `spy_ret_63d`; `hitrate_window = {"lookback_sessions":60,"horizon_sessions":20}`.

## 3. Fill the DETECT hole (fills nulls only)
Rows entering `daily_list` via the shortlist merge (`drive_sync.py#L2192-L2202`) never get `_new_engine_fields()`. Today SLDE, VLO, PBR, LITE, CNH, FLR, BE, ASX, KDP, XLF have null vwap_14d / div_* / choch_* / subcomponents / sc_m_gates / mp_accel / knn_* / pin_bar_* / inside_bar / squeeze_*. Call `_new_engine_fields()` on that path.

## 4. Declare silent defaults (new key)
`data_quality.macro = {vix_source: "fmp"|"default", intermarket_cache_date, srm_cache_date}`. VIX 18.0/GREEN on a failed quote and FLAT/0.0 directions on a gap must be visible.

## 5. Voice packets (src/pipeline/voice_packets.py)
- Slice from `aegis/contracts/voice_menus.json` **as shipped in aegis-core 1.14.0** (the v6 menus: identity block + only the fields each seat's canon reads). Copy that file into the repo.
- Copy `aegis/contracts/glossary.lock.json` from aegis-core 1.14.0 into the repo. Each packet starts with one `# NOTE <field>: <direction> | blank = <meaning>` line per served field, rendered from it (same as `pma_pipeline.py packets` does).
- `packet_stamp.json` adds `glossary_sha256` beside `menus_sha256`. `verify()` fails on mismatch.
- Every new key in §2 gets a glossary entry (definition, formula, engine line, units, direction, null_means) before it is served.

## 6. Later, separate PRs (new keys, new names)
- `vcp_detail.{contraction_count, depths_pct[], halving_ok, final_contraction_vol_ratio, pivot_price}` — minervini.
- `turning_point.{range_high, range_low, event, event_date, recovered}` — wyckoff.
- `volume_profile.{vpoc, value_area_high, value_area_low}` — wyckoff. (`vp_position_score` is NOT a volume profile; do not alias.)
- `regime.trend`, `regime.implication` — druckenmiller.
- `event_flag` + FMP earnings window beyond +90d on all rows — detect-lens.

## 7. Do NOT touch (needs PM ruling; changes populated values)
`gics_gate` (reads grade only, never `entry_gate`) · `candle_w` (in-progress week) · `atr_caution` / `malformed_bracket` (retired DSL stop) · `in_ledger` (radar flag, not nomination ledger) · dictionary text for `elder_5d` order and `sc_momentum` weights.

## Done =
§1 green · §2 keys present on 120/120 rows (null only where the engine has < N bars) · §3 rows no longer null · §4 key present · §5 packets contain only menu fields, stamp carries both shas · every new key in the glossary.

Reference material (not instructions): `aegis/handoff/voice_contract_v6/` on this branch; full bundle in the PM's Cowork chat (`aqe_data_contract_v6_2026-09-09.tar.gz`).
