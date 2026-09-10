# AQE follow-up — D-116 (2026-09-10, PM: Ash)

RULE STAYS: ADDITIVE ONLY. Same as AQE_INSTRUCTIONS.md.

## 1. ADX — push for the full spec, not the partial
`adx_14` is live and raschke's canon now reads it (D-116, locked). Two gaps, both wanted:
- **AND-RISING**: Holy Grail (C7) gates on ADX > 30 **and rising**. You ship one snapshot value, no history. Add `adx_14_prior` (yesterday's value) or a short list like `bar_range_5d`'s pattern — either lets us test the rising clause instead of level-only.
- **+DI/-DI pair**: ADX Gapper (C8) needs a 12-period ADX with a 28-period +DI/-DI pair for directional confirmation. You ship the ADX composite only. Add `plus_di_28` / `minus_di_28` (or whatever period pair `mp.py` already computes internally, if it computes DI at all alongside ADX — check before building new).

## 2. Stochastic — closer to spec if it costs nothing extra
`stoch_k_14`/`stoch_d_3` are live. Canon (C6, The Anti) specifies 7-period %K / 10-period %D; you ship 14/3. If cheap, add `stoch_k_7`/`stoch_d_10` alongside the existing pair (additive, keep both) so raschke can drop the declared-proxy language. Not urgent if it's real engine work — 14/3 stays usable as a stated proxy either way.

## 3. Glossary — document what you said you shipped
Two keys from your own §2/§4 work are missing from `aegis/contracts/glossary.lock.json`:
- `hitrate_window` (top-level, spec was `{lookback_sessions:60, horizon_sessions:20}`) — confirm it's actually on the export and add the glossary entry.
- `data_quality.macro.{vix_source, intermarket_cache_date, srm_cache_date}` — same: confirm live, document.

Separately: your glossary is genuinely good where it's real (~500 fields — indicators, bracket, elder/mp/qs engines — real formulas, real engine citations) but 64% of the 1502 entries (mostly `thematic_baskets.*`/`srm.py`, ~950 fields) are auto-generated stubs — `"See engine source — <name>"`, empty formula, `direction: n/a`, boilerplate `known_traps`. That's fine for fields nobody reads, but don't let it read as uniformly authoritative. We pulled the 29 genuinely-documented fields we needed into the plugin's own 445-field glossary (confidence-tagged by source) rather than importing the stub population. If you want ONE glossary going forward instead of two, the fix is on your side: bring the stub fields up to the same bar (real formula, real line cite, real direction) — once that's true we drop the plugin copy and read yours directly at runtime instead of maintaining a parallel file.

## 4. The 1502 count is real but inflated — one cheap fix
Checked it field-by-field. 910 of the 1502 keys (61%) are `thematic_baskets.<BASKET_NAME>.<subfield>` — the identical 26-field schema stamped out 35 times, once per basket name, instead of documented once generically like you already did for `srm[].*` (20 keys, array notation, no names spliced in — that one's done right). Collapse `thematic_baskets.*` to the same `thematic_baskets[].*`-style generic pattern `srm[]` already uses: 26 entries instead of 910, zero loss of information, and the real distinct-concept count in this file goes from "1502" to something close to the ~464 it actually is. Cheap, no engine work, just a documentation-generator fix.

## Done =
§1: `adx_14_prior` (or equivalent) + a +DI/-DI pair on every row, glossaried. §2: 7/10-period stochastic pair added (or explicitly declined with a reason). §3: `hitrate_window` + `data_quality.macro.*` confirmed live and glossary-documented, or confirmed NOT live and the AQE_INSTRUCTIONS.md §2/§4 claim corrected. §4: `thematic_baskets.*` collapsed to one generic schema entry, field count drops from 1502 to ~618 (464 real concepts + the 26-entry thematic schema replacing 910 keys, roughly).
