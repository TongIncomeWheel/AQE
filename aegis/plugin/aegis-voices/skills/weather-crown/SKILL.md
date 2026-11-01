---
name: weather-crown
description: READING CARD, not a voice — how the PMA reads AQE's Crown macro file (aqe_crown_macro.json) for the Daily Weather. Crown stood down as a voice on 2026-10-30 (R31); his read now comes straight from the file. Loaded by the brief-writer at WRITE and by the Cards renderer's Part 1. Never votes, nominates, sizes or names a ticker. Source of truth: ../weather_spec_2026-11-01.md (PM memory, extracted 2026-11-01).
---
# WEATHER — CROWN: the macro regime, read from AQE's file

**I am a reading source, not a seat.** Nothing here files a form, votes, or enters the tally. The brief-writer writes
my words; `pma_cards.py` fills every number. The full specification (purpose, function, every field, guardrails,
style, every place I appear) is `aegis-voices/skills/weather_spec_2026-11-01.md` §2 — this card is the operating cut.

## Purpose
What kind of market this is **before anyone looks at a stock**: positioning, breadth and regime before price,
because price lags all three. Four claims: price lags; index and average stock disagree and the gap is information;
trend-fund and dealer flows are mechanical so they can be anticipated; volatility shows stress the index hides.

## The order is the method (read `aqe_crown_macro.json` in this sequence)
1. **Heartbeat** `readings.breadth` — RSP/SPY regime, place in the 12-month range, days in regime, 5/20/60-day change, confidence.
2. **Gate** — `passed_the_gate` false / confidence < 0.40 → the market is UNREADABLE. **Stop.** Downstream blocks are empty because they never ran; never read them as quiet.
3. **Positioning** `readings.positioning` — trend funds (bias, share at an extreme, size dial, by sector, flip lines), large speculators (crowded long/short, CFTC date), option dealers (regime, SPY/QQQ spot vs gamma flip, walls, **assumption** stated).
4. **Volatility** `readings.volatility` — VIX, single-stock vol, the gap and its band, 20-day change, implied correlation, curve.
5. **Divergence** `readings.divergence` — warnings lit, which.
6. **The call** `the_call` — one of five families + a size multiplier (≤ 1.15×; tactical families CAP). `scenario` — leading story, share of conditions met, coverage, contested, runner-up.
Always: `status` / `status_means`, `how_current.oldest_source` (the read is as current as its oldest input), `read_me_first` (headline, why[], so_what, what_would_change_it[], caveats[]), `key_levels[]`, `what_is_coming[]`, `what_changed[]`, `limits[]`.

## States I name (plain words)
Broadening (check the range first — into the top is late) · Narrowing (stay with leaders, risk defined) · Unreadable (stop) ·
Tired wave (regime at the edge of its 12-month range — the most actionable read) · Hidden stress (vol gap wide **and widening**) ·
Stress draining (wide but shrinking — buying downside now buys the end of the move) · Crowded (context, never timing) ·
Fragile trend complex (~⅔ of markets at an extreme — cut size) · **Knife-edge** (spot within ~1% of the gamma flip — check every day) ·
Non-confirmation (count the warnings that agree) · Already priced (VIX ≥ 25 — protection is already expensive).

## Guardrails (each one binding)
Never sizes (a multiplier on the PM's own 1R, arithmetic shown) · never names a ticker · places nothing · no probabilities
(a scenario score is the share of conditions met) · the gate stops the run · freshness: state the oldest source, stale-but-present
is a failure · missing is refused, never zeroed (a gamma map without open interest is UNAVAILABLE, never flat) · assumptions
ship as assumptions (dealer side) · proxies labelled, never dropped (flip levels in fund units) · contested is not a call ·
a scenario under 60% coverage cannot lead · standalone (reads nothing from SRM / Macro Weather / Thematic RRG).

## Writing style (brief-writer, cio-voice)
Four blocks in order: **Headline** (what kind of market, one sentence) · **Why** (4–6 reasons, each with its number) ·
**So what** (family and multiplier) · **What would change it** (real levels: "if natural gas trades below 2.98, trend funds
start selling"). No jargon without its meaning, no claim without its number. Banned in output: percentile, dispersion, gex,
vixeq, heartbeat, flip_risk. **Percentile trap:** Crown's "VIX lower than X% of the past two years" means percentile 100−X —
write "higher than 74% of days", never "26th percentile"; call VIX quiet only below the median. **The mechanical label is not
the headline** (PM 2026-08-26): lead with the reasoned read from `read_me_first`; show `the_call` as a traceable data point
and say plainly how good the fit is.

## Where I appear
Cards Part 1 blocks 3 (headline, oldest source), 3a heartbeat, 3b positioning, 3c volatility, 3d divergence, 3e call + macro
story + next 5 events, 4 COT, 2 GEX light (shared with Valen's gamma block). Brief §1. `cards_text.json → weather.{heartbeat,
positioning, volatility, divergence, call, cot}` — one "Read:" paragraph each (spec §4). Vote packet: `r2digest --crown` line.
A missing file is a **declared gap, never a neutral reading**.
