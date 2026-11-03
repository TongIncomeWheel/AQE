# Elder data pack — what it takes to switch on elder-lens R1–R6 (spec for sign-off, 3 Nov 2026)

**Status: SIGNED by the PM 2026-11-03 ("Yes build the Elder pack") and BUILT** (`src/engines/elder_series.py`, canon R1-R6 flipped live, voice menu +8 columns, coverage capabilities cleared). Values appear on the next nightly export; settings are the constants at the top of `elder_series.py`. Original spec follows.

**(was) specified, not built.** The six recognisers are the only standing capability gap the per-voice coverage check
reports (`contracts/voice_coverage.json` → `capabilities`). They stay switched off in the canon
(`aegis-voices/canon/elder-lens/canon.lock.yaml`, each `if:` begins `NOT_AVAILABLE:`). Building the data without
the canon flip changes nothing a seat does, and flipping the canon without the data would have the seat reason on
fields that do not exist. Both halves are a **signal definition** (the PM/canon owner signs), so this is the whole
change, written out, for one yes.

## The eight fields (all from the daily panel AQE already holds; data only — never a gate, never sizing)

| Field | Definition (Elder's own, from *Trading for a Living* / the Triple Screen) | Unlocks |
|---|---|---|
| `impulse_colour_last_bar` | Last completed bar: **GREEN** if EMA13 of close rose vs the prior bar **and** MACD-histogram (12,26,9) rose; **RED** if both fell; else **BLUE**. | R1 |
| `impulse_colour_prior_bar` | Same, for the bar before. | R2 (colour change) |
| `force_index_ema_2` | EMA(2) of Force Index, FI = (close − prior close) × volume. | R3 |
| `price_ema_slope` | EMA13 of close, last bar minus prior bar (sign is what R3 reads). | R3 |
| `force_index_ema_13` | EMA(13) of the same Force Index series. | R4 |
| `channel_upper`, `channel_lower` | Value EMA(22) ± k·EMA(22); **k = the 95th percentile, over the last 100 bars, of max(\|high − EMA\|, \|low − EMA\|) / EMA** — i.e. the narrowest symmetric percentage channel that contains 95% of the last 100 bars' highs and lows. | R5 |
| `weekly_trend_direction` | Weekly bars from the daily panel (ISO week); **UP** if EMA13 of weekly closes rose vs the prior week, **DOWN** if it fell, **FLAT** if equal. Read before the daily, as the canon requires. | R6 |

Choices the signer should look at: the channel is a percentile fit (Elder tunes "to hold 90–95%"; 95% on 100 bars is the
stated upper end); the weekly trend uses EMA13 slope (the Triple Screen's first screen); impulse uses the 12/26/9 MACD
the books use. Each is one constant in `src/engines/elder_series.py` if the signer prefers another.

## What building it touches (additive; ~1 day with tests)

1. `src/engines/elder_series.py` (new, pure pandas) + wire into `enrichment.compute_bar_fields` and the `_ek` whitelist in `drive_sync._v21_record_fields`.
2. Glossary, field schema, taxonomy row for each field (the repo's tests require all three).
3. `voice_menus.json["elder-lens"]` + 9 columns (the packet grows ~9 columns for one voice).
4. **Canon edit (the sign-off):** for R1–R6 replace the `NOT_AVAILABLE:` prefix with the live condition and add the field names to each recogniser's `fields:`; rebuild the lock hash with `canon_build.py`. Then the six move from `capabilities` (standing, with reasons) to ordinary SERVED fields and the coverage check holds them to it.
5. Held rows already get the same fields (this change-set's held-row completion).

## Decision needed

One word: **yes** (build exactly the above) or the changes you want (a different MACD, channel coverage, weekly smoothing).
Until then the check names all six every run, with this document as the reason.
