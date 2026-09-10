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

## 5. `voice_menus.json` is not canon-derived — corrects our earlier assumption, and blocks your own stated design

We (PM + Claude) previously described your live `aegis/contracts/voice_menus.json` as "hand-patched." That word was wrong and we're retracting it — but the corrected finding is still a real problem, just a different one, and it's ours to fix as much as yours.

**What we found, checked against your repo directly:**
- Commit `8cb471dd` (2026-09-10T02:57:47Z) — the commit that created `voice_menus.json` — says in its own message that the file was "built from AQE's own live field_glossary/field_schema self-description... the external aegis-core glossary drop... was never reachable from this repo." That's not canon-pipeline output; that's a different, more permissive generation method.
- The toolkit we handed off (`aegis/handoff/voice_contract_v6/bind.py` + `render.py`) is present in your repo unmodified, but **cannot run as-is**: both scripts require `glossary.lock.json` or `glossary.lock.min.json` to exist at `aegis/handoff/voice_contract_v6/` (same directory as the scripts). Neither file exists there now, and `list_commits` on that exact path returns zero results — it has never existed there. Without it, both scripts crash at the first line that loads the glossary, before touching any canon file.
- Consistent with that: raschke's live menu is byte-identical to the pre-v6 (1.13.0-era) baseline (`menu_diff.md` confirms `raschke: 32 -> 32, removed 0, added 0`), and carries four fields (`lens_positive`, `lens_ranking`, `lens_warnings`, and a redundant bare `lens` alongside its own children) that don't trace to any binding our `bind.py`/`ALIAS` logic produces from her canon. That's what a file NOT run through the real pipeline looks like.

**This means your stated design — "AQE calculates the master file, voice packs have a layer 0 filter and carve out what's needed" — is not what's actually running today, whatever the intent.** We agree that's the right design; the pipeline to do it (bind.py -> render.py) exists in your repo and is unchanged from what we shipped. It just has no glossary at the path it needs to actually execute.

**The fix, on your side, is small**: point `render.py`'s and `bind.py`'s glossary loader at your own `aegis/contracts/glossary.lock.json` (1502 fields, or ~618 once §4's collapse lands) instead of the currently-dead `{ROOT}/glossary.lock.json` path — or drop a copy of that file at `aegis/handoff/voice_contract_v6/glossary.lock.json` so the existing loader line finds it unmodified. Either way, once a real glossary is reachable, running `bind.py` then `render.py` against the current `aegis/canon/*/canon.lock.yaml` (raschke's D-116 amendment is now pushed to main as of this commit) would regenerate `voice_menus.json` for real, and it should stop matching the pre-v6 baseline. We're not pushing our own curated glossary into your directory ourselves — per your own design, the master file should be yours, not a parallel copy we maintain.

## 6. Three concrete live gaps found in the 14-voice check (independent of §5)

Running every voice's canon-cited fields against the LIVE `voice_menus.json` (not our regenerated copy) surfaced three real gaps that exist regardless of the provenance question above:

- **seow** is missing `bracket.risk_pct` and `bracket.stop` entirely from her live menu. Her own canon (R3, R4, R6) needs a numeric stop level to compute position size (`floor(risk_$ / (entry-stop))`) and to trail/breakeven it — she has `bracket.targets` but no stop or risk figure to act on. This is the most operationally material of the three.
- **detect-lens** cites `signal_radar` (R1, R3, R12 all read `signal_radar`/`signal_radar.note`/`.scan_date`/`.n_scored`) but the whole `signal_radar` object is absent from her live menu.
- **druckenmiller** cites `spy_roc_20d` (R3, R4) and `regime_stop_pct_ceiling` (R8, the house-law size-block rule) — neither is on his live menu.

These three should be quick menu fixes once §5 is sorted (the real pipeline reading the real canon would very likely produce them, since our `bind.py`/`ALIAS` resolves all three to real export paths already in your glossary).

## Done =
§1: `adx_14_prior` (or equivalent) + a +DI/-DI pair on every row, glossaried. §2: 7/10-period stochastic pair added (or explicitly declined with a reason). §3: `hitrate_window` + `data_quality.macro.*` confirmed live and glossary-documented, or confirmed NOT live and the AQE_INSTRUCTIONS.md §2/§4 claim corrected. §4: `thematic_baskets.*` collapsed to one generic schema entry, field count drops from 1502 to ~618 (464 real concepts + the 26-entry thematic schema replacing 910 keys, roughly). §5: `bind.py`/`render.py` can actually find a glossary at runtime and `voice_menus.json` is regenerated by really running them (menu_diff.md should then show real deltas, not `0 -> 0` for every voice with an unchanged canon). §6: seow gets `bracket.stop`/`bracket.risk_pct`, detect-lens gets `signal_radar`, druckenmiller gets `spy_roc_20d`/`regime_stop_pct_ceiling`.
