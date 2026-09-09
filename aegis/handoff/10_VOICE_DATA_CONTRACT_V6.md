# HANDOFF — Voice Data Contract v6 (for Claude Code on TongIncomeWheel/AQE)

Date 2026-09-09 · From: the PMA conductor session (Cowork) · PM: Ash · Authority: PM instruction 2026-09-09.

## The one rule that governs every edit here

**ADDITIVE ONLY. Nothing the daily pipeline produces today is renamed, removed, re-scaled or re-ordered.** Every existing key in `aegis/output/aqe_daily_export.json` keeps its name, its type and its value. The voices' requirements are NEW keys appended to the same rows and the same file. The voice packets (`aegis/output/voice_packets/`) are the only place that narrows: they carry only what each voice's canon reads. If a change in this document would alter a populated value that exists today, it is out of scope — log it under §5 and stop.

Acceptance test for the whole handoff (write it first, `tests/test_export_additive.py`): load yesterday's export and the new one for the same run date; for every key present in the old file, assert the new file has the same key with an equal value. New keys may appear; nothing else may change.

## 1. Inputs — read these, they are in this bundle
`aegis/handoff/voice_contract_v6/` (this folder, branch `voice-data-contract-v6`). The glossary ships as `glossary.lock.json.gz.b64` (gzip, base64; sha256 of the decoded JSON is in `glossary.sha256`) — decode with `base64 -d glossary.lock.json.gz.b64 | gunzip > glossary.lock.json` and verify the sha before use. `binding/` and `cards/` are GENERATED — regenerate them locally before reading: `pip install pyyaml && cd aegis/handoff/voice_contract_v6 && python3 bind.py && python3 render.py` (reads `../../canon/*/canon.lock.yaml` and `../../contracts/voice_menus.json`; writes `binding/`, `cards/`, `voice_menus.v6.json`, `menu_diff.md`, `aqe_deliverables.json`). The complete pre-rendered bundle (bindings, cards, un-minified glossary) is also attached in the PM's Cowork chat as `aqe_data_contract_v6_2026-09-09.tar.gz`.
- `glossary.lock.json` — 413 export fields, each with the engine line that computes it, formula, units, direction, null meaning, per-name vs cohort, traps. This is the reader's canon; do not edit by hand — regenerate.
- `binding/<voice>.binding.yaml` ×15 — each PM-signed canon rule field → export path + fit (EXACT / PROXY / DERIVABLE / ABSENT / HELD_BOOK / RUNTIME / OUTPUT / MACRO). The alias table in `bind.py` is the only hand-written mapping.
- `cards/<voice>.glossary.md` ×14 — the reading card each seat is served.
- `voice_menus.v6.json` — menus generated from the bindings (`render.py`). Replaces the hand-kept `voice_menus.json` for packet slicing ONLY.
- `aqe_deliverables.json`, `canon_declared_gaps.txt` — the field backlog, by voice and rule id.
- `nomination_v6.schema.json` — the R1 form (conductor side; here for reference so field names agree).
- `AQE_DATA_CONTRACT_v6.md` — the PM document with the findings.

## 2. Edits to make — main file, additive

**2a. `src/data/drive_sync.py` — new per-row keys on `daily_list` rows** (add to the row builder next to the existing `_new_engine_fields` spread at ~L1725 and ~L2146; same source panel the engines already use):

| new key | definition | wanted by |
|---|---|---|
| `bar_open`, `bar_high`, `bar_low`, `bar_close` | last completed daily bar, USD | seow R1/R2/R9 |
| `prior_bar_high`, `prior_bar_low` | the bar before it | seow R2/R3/R5 |
| `ma_20_slope_5d_pct` | (ma_20 / ma_20 five sessions ago − 1) × 100 | seow R1 |
| `ret_63d`, `pct_run_10d` | close / close[−63] − 1 (pct); close / close[−10] − 1 (pct) | seow R7/R8 |
| `hi_20d`, `lo_20d`, `hi_50d`, `lo_50d`, `pos_in_50d_range_pct` | rolling extremes; `energy.py#L40-L45` already computes hi50/lo50/en_pos50 — expose, do not recompute differently | raschke R2, wyckoff R1 |
| `rvol_20d` | day_vol / elder_context.volume.avg_vol_20d | oneil R4 |
| `base_low_20d` | min low of the last 20 bars | seow R3 |
| `days_since_swing_high` | sessions since `last_pivot_high.date` | seow R7 |
| `gap_risk_flag` | days_to_earnings is not null and ≤ 10 | thorp R4 |
| `cohort_hit_rate_20d`, `cohort_n` | **copies** of `signal_hit_rate_20d` / `signal_n` under an honest name. The old keys stay. | thorp R6/R7, all readers |

Top level (beside `spy_roc_20d`): `spy_ret_63d`; `hitrate_window: {"lookback_sessions": 60, "horizon_sessions": 20, "from": "t-79", "to": "t-20"}` (seow R8, thorp R6).

**2b. Fill the DETECT hole — fills nulls, changes no populated value.** Rows that enter `daily_list` through the shortlist merge (`drive_sync.py#L2192-L2202`: `top_picks` / `recipe_matches` path) never get `_new_engine_fields()`; today SLDE, VLO, PBR, LITE, CNH, FLR, BE, ASX, KDP, XLF carry null `vwap_14d`, `div_*`, `choch_*`, `subcomponents`, `sc_m_gates`, `mp_accel`, `knn_*`, `pin_bar_*`, `inside_bar`, `squeeze_*`. Call `_new_engine_fields()` on that path too. The additive test passes because every affected value today is null.

**2c. `data_quality` flags, additive.** Add `data_quality.macro: {vix_source: "fmp"|"default", intermarket_cache_date, srm_cache_date}` so a silent default (VIX 18.0/GREEN on a failed quote, FLAT/0.0 directions on a gap, stale intermarket cache) is declared, not hidden. Existing values untouched.

**2d. Glossary and bindings into the repo:** `aegis/contracts/glossary.lock.json` (new file; `field_dictionary.json` and `_FIELD_GLOSSARY` stay as they are), `aegis/canon/<voice>/binding.yaml` (new file per voice, beside `canon.lock.yaml`), `aegis/contracts/voice_menus.v6.json`. Add the new §2a keys to `glossary.lock.json` with their engine line when you write them — an exported key without a glossary entry fails `verify()`.

## 3. Edits to make — voice packets, narrow

`src/pipeline/voice_packets.py`:
- `build()` slices from `voice_menus.v6.json` instead of `voice_menus.json` (`~L87`). A packet carries the identity block (`ticker, entry, source, held, atr_14d, days_to_earnings`) plus the fields the seat's binding marks EXACT or PROXY — nothing else. `lens.extension` is never served (constant null by ruling); `bracket.*` is served as the eight-field core listed in `render.py` `BRACKET_CORE`.
- Every packet starts with `# NOTE` lines rendered from `glossary.lock.json` for each field it carries: `direction` and `null_means` (the current hand-kept `FIELD_NOTES` dict in `pma_pipeline.py` is retired by this).
- `packet_stamp.json` gains `glossary_sha256` and `cards_sha256[voice]` beside `menus_sha256`. `verify()` fails on any mismatch. The conductor's preflight (R7) checks the same three.
- Ship each seat's reading card (`cards/<voice>.glossary.md`) into `aegis/output/voice_packets/cards/` so the conductor can inline it at spawn.

## 4. Tier-3 builds (new keys, new names; separate PRs, after §2–3 are merged)
- `vcp_detail.{contraction_count, depths_pct[], halving_ok, final_contraction_vol_ratio, pivot_price}` — minervini C4/C5/C6. Today's `elder_context.vcp.*` stays exactly as is; the packets serve it to minervini as PROXY with the loss stated.
- `turning_point.{range_high, range_low, event, event_date, recovered}` with event ∈ {SPRING, UPTHRUST, SECONDARY_TEST, SHAKEOUT, NONE} — wyckoff R1.
- `volume_profile.{vpoc, value_area_high, value_area_low, hvn[], lvn[]}` from the daily panel (20/50 bars) — wyckoff R11. Note `energy.py#L40-L61 vp_position_score` is NOT a volume profile; do not alias it.
- `regime.trend`, `regime.implication` — druckenmiller R2/R7; additive keys on the existing `regime` object.
- `event_flag` (earnings within hold horizon / known binary catalyst) — detect-lens R11; widen the FMP calendar window beyond +90 days and stamp all `daily_list` rows, not only longlist/elder.

## 5. Out of scope — needs a PM ruling before anyone touches it
These change populated values and are therefore NOT done under this handoff. Listed so they are not lost:
- `gics_gate` reads `grade` only; `srm[].entry_gate` never reaches rows (`#L1250`, `#L1817`). Rows print PASS where the sector prints WATCH/CAUTION.
- `candle_w` is the in-progress week (W-FRI resample) stamped with a future date.
- `atr_caution` / `malformed_bracket` derive from the retired DSL stop, not `bracket.stop`.
- `in_ledger` means Signal Radar membership, not the nomination ledger.
- `elder_5d` order (oldest→newest) and `sc_momentum` weights (four engines, Elder gate-only) are correct in code; `field_dictionary.json` and `agentic_dictionary.py` describe them wrongly — fix the text, not the values, in a docs-only PR.

## 6. Order of work and done-criteria
1. `tests/test_export_additive.py` written and green on the current export before any change.
2. §2a keys + §2b fill + §2c flags in one PR: additive test green; every new key has a `glossary.lock.json` entry with an engine line; `verify()` passes.
3. §3 packet PR: packets contain only menu fields (test: every column ∈ menu ∪ identity block); stamp carries the three shas; the conductor's `preflight_run.py` fails on a mismatched sha (coordinate with the plugin side — the conductor session will update `aegis-core` to read the v6 stamp).
4. §4 one PR per build.
5. §5 untouched until ruled.

Questions go to the PM, not resolved by assumption. Anything in §5 that "has to move" to make §2–4 work means the design is wrong — stop and say so.
