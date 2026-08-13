# Voice → data requirement → does AQE provide it

One row per (voice, requirement). 162 candidate rows in today's export.

**Sources.** Requirements: `aegis/canon/<voice>/canon.lock.yaml`, `recognisers[].fields`, @ main.
Coverage: measured menu population across the 162 rows. Field meanings: `AQE_FIELD_GLOSSARY.md`.

**`Provided?` values.** `YES` = exists and populated on ≥96% of rows · `PARTIAL (n/162)` = populated on some rows only · `NO — not on menu` = AQE exports it, this voice's menu does not pass it through · `NO — not in AQE` = AQE does not produce it.

**Three readings that are not defects.**
`day_vol` is a phantom menu entry — it appears on eight menus, populates 0/162, and is not a glossary field at all. The real volume field is `rvol` (live, 162/162 on oneil's menu). Rows below name `rvol`.
`bracket.valid=false` on 83% of rows is by design (glossary §4): a stop must clear ≥1×ATR room, reward:risk ≥2.0 to TP2, and the regime stop-% ceiling (8% in YELLOW). 27 of 162 clear all three today.
`subcomponents.*` and `elder_context` are exported but sit on no voice menu.

*Note: detect-lens does have a `canon.lock.yaml` in the repo (12 recognisers); it is used here in preference to its skill card.*

---

## Summary

| Voice | Requirements | Provided | Partial | Missing |
|---|---|---|---|---|
| crown | 12 | 0 | 0 | 12 |
| detect-lens | 18 | 7 | 0 | 11 |
| druckenmiller | 20 | 4 | 2 | 14 |
| elder-lens | 18 | 4 | 1 | 13 |
| livermore | 13 | 9 | 2 | 2 |
| lynch | 14 | 8 | 1 | 5 |
| minervini | 16 | 11 | 2 | 3 |
| oneil | 13 | 9 | 2 | 2 |
| raschke | 16 | 8 | 2 | 6 |
| rogers | 14 | 8 | 0 | 6 |
| seow | 18 | 6 | 1 | 11 |
| steenbarger | 15 | 7 | 2 | 6 |
| thorp | 22 | 8 | 3 | 11 |
| wyckoff | 20 | 13 | 2 | 5 |
| **Total** | **229** | **102** | **20** | **107** |

---

## The missing items, deduplicated

| # | Missing thing | Voices that need it | Provided? |
|---|---|---|---|
| 1 | Stop detail — stop price, stop type, distance in ATR, % of capital at risk, reward:risk | 9 — livermore, lynch, minervini, oneil, raschke, seow, steenbarger, thorp, wyckoff | PARTIAL (27/162) |
| 2 | Recent volume vs its own 20-day average (`rvol`) | 8 — elder-lens, livermore, minervini, raschke, rogers, steenbarger, thorp, wyckoff | NO — not on menu |
| 3 | Company fundamentals — earnings, EPS growth, P/E, PEG, dividend yield, balance sheet, sales, market cap, institutional ownership | 5 — druckenmiller, lynch, minervini, oneil, rogers | NO — not in AQE |
| 4 | Engine sub-scores (`subcomponents.*`) — ADX value, volume-profile position, squeeze and bandwidth, extension, exhaustion, days-to-earnings | 3 — detect-lens, raschke, wyckoff | NO — not on menu |
| 5 | Market regime, sector rotation table and macro block (`regime`, `srm`, `macro_weather`, `intermarket`) | 3 — druckenmiller, oneil, steenbarger | NO — not on menu |
| 6 | Raw per-bar OHLC and bar-range history | 2 — raschke, seow | NO — not in AQE |
| 7 | Market breadth — advance/decline line, new-high/new-low counts, TICK, TRIN | 2 — druckenmiller, raschke | NO — not in AQE |
| 8 | Measured forward-return statistics per signal — separation from baseline, backtest trade counts, sample window | 2 — steenbarger, thorp | NO — not in AQE |
| 9 | Sector and commodity fundamental drivers — capacity, supply, capex, input costs, production, inventory | 2 — druckenmiller, rogers | NO — not in AQE |
| 10 | The Crown macro artifact — breadth regime, single-stock-vs-index volatility gap, dealer gamma flip, trend-fund positioning, divergence count. AQE publishes `aqe_crown_macro.json` daily; nothing ingests it | 1 — crown | NO — not on menu |
| 11 | Elder-lens menu is 6 fields wide — `held`, `bracket`, `malformed_bracket`, `ma_20`, `ma_50`, `entry`, `choch_state`, `structure_shift`, `pin_bar_state`, `pin_bar_level` all exist and are all off it | 1 — elder-lens | NO — not on menu |
| 12 | Detect-lens passthroughs — `ptrs`, `lens_ranking`, `mover_subtype`, both conviction labels, `signal_radar` metadata, `choch_state`/`knn_*`, `div_*`, `pin_bar_*`/`inside_bar`/`pib_pattern` | 1 — detect-lens | NO — not on menu |
| 13 | Elder's own instruments — per-bar impulse colour, Force Index (2- and 13-bar EMAs), a fitted price channel, weekly trend direction | 1 — elder-lens | NO — not in AQE |
| 14 | Seow's own instruments — 40-day average, 20-day average slope, CCI(20), tick size, prior support and base low, days-held and high-since-entry, 63-day stock-vs-index-vs-group return | 1 — seow | NO — not in AQE |
| 15 | Thorp's risk-pricing inputs — 52-week high/low, last eleven monthly highs/lows, implied volatility, bid/ask spread and average daily traded volume, expected holding days, edge vs its trailing median | 1 — thorp | NO — not in AQE |
| 16 | Realised 30-day volatility (`vol_30d_ann`), universe-membership flags (`on_longlist`/`on_elder`/`source`) and the run `summary` | 1 — thorp | NO — not on menu |
| 17 | Wyckoff turning points — range boundary, penetration event, recovery flag (spring, upthrust, secondary test, shakeout) and the wave triad of length, cumulative volume and duration | 1 — wyckoff | NO — not in AQE |
| 18 | The bracket object is absent from druckenmiller's menu entirely — `bracket`, `bracket.valid`, `bracket.stop`, `regime_stop_pct_ceiling` | 1 — druckenmiller | NO — not on menu |
| 19 | Positioning and sentiment — surveys, fund cash levels, put/call ratio, short interest | 1 — druckenmiller | NO — not in AQE |
| 20 | The most recent swing low (`fib_swing_low`) | 1 — seow | NO — not on menu |
| 21 | Country, currency, sovereign debt, savings rate, demographics, rule of law | 1 — rogers | NO — not in AQE |
| 22 | A named catalyst forcing revaluation in 12–36 months, and the committee's own `nomination_count` per name | 1 — rogers | NO — not in AQE |
| 23 | The countable VCP contraction sequence — how many contractions, how deep | 1 — minervini | NO — not in AQE |
| 24 | Realised exit prices, to compare against the bracket's own stop and targets | 1 — steenbarger | NO — not in AQE |
| 25 | Order-fill difficulty as size is added | 1 — livermore | NO — not in AQE |

---

## Per-voice detail

### crown

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| crown | Whether the average stock is gaining on the biggest few, or losing to them | `readings.breadth.regime` | NO — not on menu |
| crown | Where that breadth reading sits inside its own 12-month range | `readings.breadth.position_in_12_month_range` | NO — not on menu |
| crown | How much breadth has moved over 5 and 20 days | `readings.breadth.change_5d_pct`, `readings.breadth.change_20d_pct` | NO — not on menu |
| crown | Whether the breadth read passed its own quality gate, and how confident it is | `readings.breadth.passed_the_gate`, `readings.breadth.confidence` | NO — not on menu |
| crown | Whether the whole macro run completed cleanly or exited early | `status`, `limits` | NO — not on menu |
| crown | The state of the gap between single-stock and index volatility | `readings.volatility.state` | NO — not on menu |
| crown | How wide that gap is against its own history, and which way it is moving | `readings.volatility.gap_vs_history`, `readings.volatility.gap_change_20d` | NO — not on menu |
| crown | The VIX level, and the point above which protection is already expensive | `readings.volatility.vix`, `key_levels` | NO — not on menu |
| crown | Which markets large speculators are crowded into, long and short, and how stale that data is | `readings.positioning.large_speculators.crowded_long`, `.crowded_short`, `.as_of` | NO — not on menu |
| crown | How many trend-following markets sit at an extreme, the resulting bias, and the size dial it implies | `readings.positioning.trend_funds.share_at_an_extreme`, `.bias`, `.size_dial` | NO — not on menu |
| crown | The dealer gamma flip level per underlying, and how far spot sits from it | `readings.positioning.option_dealers.detail.<TKR>.gamma_flip`, `.flip_distance_pct` | NO — not on menu |
| crown | How many divergence warnings are lit, and which ones | `readings.divergence.warnings_lit`, `readings.divergence.which` | NO — not on menu |

crown: 12 requirements — 0 yes, 0 partial, 12 missing.

### detect-lens

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| detect-lens | How many of the six lenses read strong | `lens_positive` | YES |
| detect-lens | How many read a warning | `lens_warnings` | YES |
| detect-lens | Which of the six lenses fired — leadership, coil, institutional money, structure, resistance, sector | `lens` | YES |
| detect-lens | Radar tag: the name is already running | `runner_setup` | YES |
| detect-lens | How many of the four runner legs fired, 0 to 4 | `runner_conviction` | YES |
| detect-lens | Radar tag: a quiet name about to move | `premove_setup` | YES |
| detect-lens | How many pre-move legs fired, 0 to 4 | `premove_conviction` | YES |
| detect-lens | The final tie-break score when lens counts are level | `ptrs` | NO — not on menu |
| detect-lens | The pre-built reading order and the note on how it was built | `lens_ranking` | NO — not on menu |
| detect-lens | The word that must travel with each conviction number — MINIMAL through MAX | `runner_conviction_label`, `premove_conviction_label` | NO — not on menu |
| detect-lens | Which family of mover the name is — explosive, trend, tight base, squeeze | `mover_subtype` | NO — not on menu |
| detect-lens | The extension evidence behind the lens — where price sits in its 50-day range, exhaustion, ATR expansion, climax risk | `subcomponents.energy.en_pos50`, `.exhaustion_score`, `.atr_score`, `subcomponents.flow.ext_score` | NO — not on menu |
| detect-lens | The change-of-character flag and the nearest-neighbour hit rate behind it, with the neighbour count | `choch_state`, `knn_prob`, `knn_significant`, `knn_neighbors_used` | NO — not on menu |
| detect-lens | Which oscillators disagree with price, and how many | `div_state`, `div_bull_count`, `div_bear_count`, `div_oscs` | NO — not on menu |
| detect-lens | Single-bar rejection candles, the inside-bar pause, and the level rejected | `pin_bar_state`, `pin_bar_level`, `inside_bar`, `pib_pattern` | NO — not on menu |
| detect-lens | The radar's own scan date, how many names it scored, and its caveat note | `signal_radar.scan_date`, `.n_scored`, `.note` | NO — not on menu |
| detect-lens | How close the name is to earnings | `subcomponents.structure.earn_score` | NO — not on menu |
| detect-lens | Whether a binary event other than earnings is pending | no event flag field | NO — not in AQE |

detect-lens: 18 requirements — 7 yes, 0 partial, 11 missing.

### druckenmiller

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| druckenmiller | The sector the name sits in, in plain words | `gics_sector_name` | YES |
| druckenmiller | Which way that sector is going | `sector_trend_state` | YES |
| druckenmiller | The name's momentum score | `sc_momentum` | YES |
| druckenmiller | How much the name moves for a 1% move in SPY, over 30 days | `beta_30d` | YES |
| druckenmiller | Which thematic basket the name belongs to | `thematic_basket` | PARTIAL (30/162) |
| druckenmiller | That basket's grade | `thematic_grade` | PARTIAL (30/162) |
| druckenmiller | Bonds, dollar and credit — direction over 5 and 20 days, and whether each is above its 20-day average | `intermarket.tlt.*`, `intermarket.uup.*`, `intermarket.hyg.*`, `macro_weather.*_direction` | NO — not on menu |
| druckenmiller | Whether credit is diverging from duration | `intermarket.hyg.hyg_tlt_spread` | NO — not on menu |
| druckenmiller | Large-cap versus broad-market spread, and SPY's own 20-day move | `intermarket.spy_iwm.spread`, `spy_roc_20d` | NO — not on menu |
| druckenmiller | VIX level, the regime label, its trend and what it implies | `regime.vix`, `regime.level`, `regime.trend`, `regime.implication` | NO — not on menu |
| druckenmiller | The stop-% ceiling the current regime imposes | `regime_stop_pct_ceiling` | NO — not on menu |
| druckenmiller | The full sector table — grade, rotation quadrant and direction, macro headwind, entry gate | `srm[]` | NO — not on menu |
| druckenmiller | Copper/gold, oil and gold direction | `macro_weather.cper_direction`, `.uso_direction`, `.gld_direction` | NO — not on menu |
| druckenmiller | Rotation quadrant and direction for each thematic basket | `thematic_baskets.*.rrg_quadrant`, `.rrg_direction` | NO — not on menu |
| druckenmiller | The stop and whether it is valid — the price half of the written invalidation | `bracket`, `bracket.valid`, `bracket.stop` | NO — not on menu |
| druckenmiller | Market-level valuation — P/E, price to book, dividend yield | none | NO — not in AQE |
| druckenmiller | Policy rate, central-bank balance sheet, or any explicit liquidity series | none | NO — not in AQE |
| druckenmiller | Real breadth — the advance/decline line and new-high/new-low counts | none | NO — not in AQE |
| druckenmiller | Positioning and sentiment — surveys, fund cash, put/call, short interest | none | NO — not in AQE |
| druckenmiller | What actually drives a sector — capacity, supply, capex, earnings, expansion announcements | none | NO — not in AQE |

druckenmiller: 20 requirements — 4 yes, 2 partial, 14 missing.

### elder-lens

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| elder-lens | The Elder impulse score, 0 to 10 | `elder` | YES |
| elder-lens | The last five days of that score, one per day | `elder_5d` | YES |
| elder-lens | Where the name is in its momentum lifecycle | `mp_state` | YES |
| elder-lens | The momentum persistence score | `mp` | YES |
| elder-lens | The five-day Elder pattern label — sustained, correction re-entry, acceleration, base | `elder_pattern` | PARTIAL (125/162) |
| elder-lens | Whether the position is already held, which decides tighten-versus-enter | `held` | NO — not on menu |
| elder-lens | The 20- and 50-day averages and the entry price, to spot a pullback into value under a rising stack | `ma_20`, `ma_50`, `entry` | NO — not on menu |
| elder-lens | The stop object and the flag for a stop too close to price to use | `bracket`, `malformed_bracket` | NO — not on menu |
| elder-lens | Whether the up-structure has already broken | `choch_state`, `structure_shift` | NO — not on menu |
| elder-lens | Rejection-candle state and the level of the rejection, so the stop is not placed beyond the tail | `pin_bar_state`, `pin_bar_level` | NO — not on menu |
| elder-lens | Recent volume vs its own average, to confirm a pullback is drying up | `rvol` (menu carries the phantom `day_vol`) | NO — not on menu |
| elder-lens | Impulse colour on the last bar — fast-EMA slope and MACD-histogram slope, as three states | none | NO — not in AQE |
| elder-lens | That same colour on the prior bar, so the change can be seen | none | NO — not in AQE |
| elder-lens | Force Index smoothed over 2 bars, signed, with a zero line | none | NO — not in AQE |
| elder-lens | Force Index smoothed over 13 bars, and its zero crossings | none | NO — not in AQE |
| elder-lens | A fitted price channel holding 90–95% of recent bars, and its upper wall | none | NO — not in AQE |
| elder-lens | Weekly trend direction, read before the daily | none | NO — not in AQE |
| elder-lens | A test for the pullback failing to extend lower | none | NO — not in AQE |

elder-lens: 18 requirements — 4 yes, 1 partial, 13 missing.

### livermore

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| livermore | Base condition, and whether the base has actually broken | `structure`, `structure_shift` | YES |
| livermore | How far price sits from its average — proximity to a fresh high | `sma_distance_pct` | YES |
| livermore | A relative reaction-size measure, standing in for the book's fixed point thresholds | `atr_14d` | YES |
| livermore | Momentum state, and whether momentum itself is accelerating | `mp_state`, `mp_accel_state` | YES |
| livermore | Whether a valid stop exists at all | `bracket.valid` | YES |
| livermore | Whether the name is already held | `held` | YES |
| livermore | Sector, its plain name, and its direction — for concentration discipline | `gics_sector`, `gics_sector_name`, `sector_trend_state` | YES |
| livermore | Where the name ranks in the set | `rank` | YES |
| livermore | The entry price | `entry` | YES |
| livermore | The stop price and what kind of level it is | `bracket.stop`, `bracket.stop_type` | PARTIAL (27/162) |
| livermore | What percentage of capital is at risk to that stop | `bracket.risk_pct` | PARTIAL (27/162) |
| livermore | Today's volume against its own 20-day average | `rvol` (menu carries the phantom `day_vol`) | NO — not on menu |
| livermore | How hard successive orders are to fill as price rises | none | NO — not in AQE |

livermore: 13 requirements — 9 yes, 2 partial, 2 missing.

### lynch

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| lynch | The sector the name sits in, coded and in plain words — the only handle on category | `gics_sector`, `gics_sector_name` | YES |
| lynch | Which way that sector is going | `sector_trend_state` | YES |
| lynch | How far price sits below its average — the depressed-price read | `sma_distance_pct` | YES |
| lynch | The 50- and 200-day averages, for the same read | `ma_50`, `ma_200` | YES |
| lynch | Base and trend condition | `structure` | YES |
| lynch | Whether the name is already held, for the rotation question | `held` | YES |
| lynch | Where it ranks in the set | `rank` | YES |
| lynch | Whether a valid stop exists | `bracket.valid` | YES |
| lynch | The stop price itself | `bracket.stop` | PARTIAL (27/162) |
| lynch | Earnings, P/E, PEG, growth rate, dividend yield | none | NO — not in AQE |
| lynch | Balance sheet — cash, debt, inventory, sales, operating cash flow, CapEx | none | NO — not in AQE |
| lynch | Market cap and institutional ownership | none | NO — not in AQE |
| lynch | The three automatic fail gates — bank-debt maturity, two-quarter inventory bubble, PEG-and-ownership test | none | NO — not in AQE |
| lynch | A business description — what the company sells, its segments, its expansion plans | none | NO — not in AQE |

lynch: 14 requirements — 8 yes, 1 partial, 5 missing.

### minervini

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| minervini | The full moving-average stack — 20, 50, 100 and 200 day | `ma_20`, `ma_50`, `ma_100`, `ma_200` | YES |
| minervini | How far price sits from its average, for the near-highs and off-lows criteria | `sma_distance_pct` | YES |
| minervini | Whether the name leads or lags, and by how much over 20 days | `rs_leadership`, `rs_spy_20d` | YES |
| minervini | Base condition, and whether it has broken out | `structure`, `structure_shift` | YES |
| minervini | Accumulation and coiling composites, as the closest read on the volume signature | `flow`, `energy` | YES |
| minervini | The entry price, to check it is close to the pivot rather than chased | `entry` | YES |
| minervini | Whether a valid stop exists | `bracket.valid` | YES |
| minervini | Whether the name is already held | `held` | YES |
| minervini | Where it ranks in the set | `rank` | YES |
| minervini | Sector, its plain name, and its direction — for the late-stage rotation warning | `gics_sector`, `gics_sector_name`, `sector_trend_state` | YES |
| minervini | The stop object as a whole, deferred to for the exit | `bracket` | YES |
| minervini | The stop price and what kind of level it is | `bracket.stop`, `bracket.stop_type` | PARTIAL (27/162) |
| minervini | What percentage of capital is at risk to that stop | `bracket.risk_pct` | PARTIAL (27/162) |
| minervini | Volume drying up in the base and expanding on the breakout | `rvol` (menu carries the phantom `day_vol`) | NO — not on menu |
| minervini | The countable contraction sequence inside the base — how many, and how deep each one is | none | NO — not in AQE |
| minervini | Earnings growth rate, EPS acceleration, and the six-category company sort | none | NO — not in AQE |

minervini: 16 requirements — 11 yes, 2 partial, 3 missing.

### oneil

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| oneil | Whether the name leads its group, and where it ranks in that group | `rs_leadership`, `rank`, `gics_sector` | YES |
| oneil | Base condition, and whether a consolidation actually completed | `structure`, `structure_shift` | YES |
| oneil | Whether the name is coiling, and where the overhead resistance sits | `lens` (`lens.coil`, `lens.structure`) | YES |
| oneil | Today's volume against its 20-day average — needs 1.40 or better to confirm a breakout | `rvol` | YES |
| oneil | How far past the pivot price already is | `entry`, `bracket.price`, `sma_distance_pct` | YES |
| oneil | Whether a valid stop exists at all | `bracket.valid` | YES |
| oneil | How far above the 200-day average price sits — a climax read at +70% | `ma_200` | YES |
| oneil | Whether a held name has closed below its 50-day average | `ma_50`, `held` | YES |
| oneil | Whether the group is confirming the breakout, or the name is running alone | `lens` (`lens.sector`), `sector_trend_state` | YES |
| oneil | What percentage of capital is at risk to the stop — rejects above 8% | `bracket.risk_pct` | PARTIAL (27/162) |
| oneil | The stop price and its reward-to-risk | `bracket.stop`, `bracket.rr` | PARTIAL (27/162) |
| oneil | Whether the market itself is in a confirmed uptrend | `srm`, `macro_weather`, `regime` | NO — not on menu |
| oneil | Earnings, return on equity, sales growth, institutional sponsorship, insider ownership | none | NO — not in AQE |

oneil: 13 requirements — 9 yes, 2 partial, 2 missing.

### raschke

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| raschke | Base condition and whether structure has shifted — to sort the name into one of four setup families | `structure`, `structure_shift` | YES |
| raschke | How far price sits from its average, and where it ranks — the extreme-and-recency pattern | `sma_distance_pct`, `rank` | YES |
| raschke | Whether the name is trending strongly, and whether that is accelerating | `mp_state`, `mp_accel_state` | YES |
| raschke | Whether the name is coiling — standing in for the short cycle pulling back against the long | `lens` | YES |
| raschke | Range contraction — 14-day ATR, and the flag for a stop too tight for the regime | `atr_14d`, `atr_caution` | YES |
| raschke | Whether a valid stop exists — false is a hard reject in this canon | `bracket.valid` | YES |
| raschke | Whether the name is already held | `held` | YES |
| raschke | The entry price | `entry` | YES |
| raschke | The stop price and what kind of level it is | `bracket.stop`, `bracket.stop_type` | PARTIAL (27/162) |
| raschke | What percentage of capital is at risk to that stop | `bracket.risk_pct` | PARTIAL (27/162) |
| raschke | Recent volume vs its own average, for the range-contraction read | `rvol` (menu carries the phantom `day_vol`) | NO — not on menu |
| raschke | The actual ADX value, to gate at above 30 | `subcomponents.mp.adx_val` | NO — not on menu |
| raschke | Daily stochastic %K and %D | none | NO — not in AQE |
| raschke | The exact rolling 20-day high and low, as a count rather than an approximation | none | NO — not in AQE |
| raschke | Per-bar high-low range history, for NR4 and NR7 counts and a 6-day vs 100-day volatility ratio | none | NO — not in AQE |
| raschke | Market breadth — TICK, TRIN, advance/decline | none | NO — not in AQE |

raschke: 16 requirements — 8 yes, 2 partial, 6 missing.

### rogers

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| rogers | The deliberation set with each name's rank | `rank` | YES |
| rogers | How far each name has run above its averages — the extension read behind the crowding challenge | `sma_distance_pct`, `ma_20`, `ma_50`, `ma_200` | YES |
| rogers | Whether the name is already held | `held` | YES |
| rogers | Base condition, and whether structure has shifted | `structure`, `structure_shift` | YES |
| rogers | Whether the name leads or lags | `rs_leadership`, `rs_spy_20d` | YES |
| rogers | The entry price, for the timing-delay challenge | `entry` | YES |
| rogers | The stop object as a whole, deferred to without argument | `bracket` | YES |
| rogers | Sector and its direction, as a weak stand-in for the commodity cycle | `gics_sector`, `gics_sector_name`, `sector_trend_state` | YES |
| rogers | Recent volume vs its own average, as crowding evidence | `rvol` (menu carries the phantom `day_vol`) | NO — not on menu |
| rogers | How many committee seats nominated the name | `nomination_count` — a committee tally, not an AQE field | NO — not in AQE |
| rogers | Country, currency, sovereign debt, savings rate, demographics, rule of law | none | NO — not in AQE |
| rogers | Book value, EPS, dividend yield, annual-report footnotes, press-release text | none | NO — not in AQE |
| rogers | Commodity prices, input costs, production and inventory | none | NO — not in AQE |
| rogers | A named catalyst that forces the market to recognise value within 12 to 36 months | none | NO — not in AQE |

rogers: 14 requirements — 8 yes, 0 partial, 6 missing.

### seow

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| seow | The 20-day moving average | `ma_20` | YES |
| seow | The 50, 100 and 200-day moving averages | `ma_50`, `ma_100`, `ma_200` | YES |
| seow | How far price sits from its average | `sma_distance_pct` | YES |
| seow | Where the name is in its momentum lifecycle | `mp_state` | YES |
| seow | Which way the sector is going | `sector_trend_state` | YES |
| seow | The entry price | `entry` | YES |
| seow | The stop price | `bracket.stop` | PARTIAL (27/162) |
| seow | The most recent swing low, to place the initial stop one tick below it | `fib_swing_low` | NO — not on menu |
| seow | The 40-day moving average — the method's own trend line | none | NO — not in AQE |
| seow | Whether the 20-day average has risen over the last five days | none | NO — not in AQE |
| seow | CCI over 20 days, to catch the oversold pullback that arms the setup | none | NO — not in AQE |
| seow | Raw daily bars — today's and the prior bar's open, high, low and close | none | NO — not in AQE |
| seow | Tick size, to place the buy-stop one tick above the prior bar's high | none | NO — not in AQE |
| seow | Prior support, and the low of a sideways base | none | NO — not in AQE |
| seow | The prior day's low, to ratchet the trailing stop each session | none | NO — not in AQE |
| seow | Days held and the highest price since entry, for the five-day time stop | none | NO — not in AQE |
| seow | Days since the swing high, and pullback bar size against a 20-day ATR | none | NO — not in AQE |
| seow | 63-day percentage change for the stock, the index and its industry group | none | NO — not in AQE |

seow: 18 requirements — 6 yes, 1 partial, 11 missing.

### steenbarger

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| steenbarger | Higher-timeframe trend context — the 50, 100 and 200-day averages and the base condition | `ma_50`, `ma_100`, `ma_200`, `structure` | YES |
| steenbarger | Whether structure has shifted | `structure_shift` | YES |
| steenbarger | The momentum score being cited as the reason | `sc_momentum` | YES |
| steenbarger | Which lenses are flashing a warning | `lens_warnings` | YES |
| steenbarger | The sector name | `gics_sector_name` | YES |
| steenbarger | How volatile the name is | `atr_14d` | YES |
| steenbarger | Whether a valid stop exists — the written invalidation, without which the nomination is blocked | `bracket.valid`, `bracket` | YES |
| steenbarger | The stop price itself | `bracket.stop` | PARTIAL (27/162) |
| steenbarger | What percentage of capital is at risk, to check size is independent of recent results | `bracket.risk_pct` | PARTIAL (27/162) |
| steenbarger | The market regime the nomination claims to be valid inside | `regime` | NO — not on menu |
| steenbarger | The sector rotation table, for the same environment test | `srm` | NO — not on menu |
| steenbarger | Recent volume vs its own average | `rvol` (menu carries the phantom `day_vol`) | NO — not on menu |
| steenbarger | Measured forward-return separation from baseline, for every signal cited | none | NO — not in AQE |
| steenbarger | How many trades a rule would have generated over the sample, so a hit rate can be recounted honestly | none | NO — not in AQE |
| steenbarger | Realised exit prices, to compare against the bracket's own stop and targets | none | NO — not in AQE |

steenbarger: 15 requirements — 7 yes, 2 partial, 6 missing.

### thorp

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| thorp | The entry price reference | `bracket.price` | YES |
| thorp | Whether a valid stop exists at all | `bracket.valid` | YES |
| thorp | The 14-day ATR, to model the stop gapping through by one day's typical range | `atr_14d` | YES |
| thorp | The fallback ATR stop used when no structural stop qualifies | `bracket.atr_fallback_stop` | YES |
| thorp | How much the name moves for a 1% move in SPY, over 30 days | `beta_30d` | YES |
| thorp | The momentum score being voted on | `sc_momentum` | YES |
| thorp | Which gate checks passed and which failed, per engine | `sc_m_gate_detail`, `sc_p_gate_detail` | YES |
| thorp | The nearest-neighbour hit rate and its threshold flag | `knn_prob`, `knn_significant` | YES |
| thorp | The stop price, and how far it sits in ATR terms | `bracket.stop`, `bracket.stop_atr_dist` | PARTIAL (27/162) |
| thorp | What percentage of capital is at risk to that stop | `bracket.risk_pct` | PARTIAL (27/162) |
| thorp | Reward-to-risk overall and to each target | `bracket.rr`, `bracket.rr_tp1`, `bracket.rr_tp2` | PARTIAL (27/162) |
| thorp | The name's realised 30-day volatility, to rank calm candidates against jumpy ones | `vol_30d_ann` | NO — not on menu |
| thorp | Whether the name is inside the universe the model was fitted on | `on_longlist`, `on_elder`, `source` | NO — not on menu |
| thorp | How many names passed the screen today | `summary` | NO — not on menu |
| thorp | Recent volume vs its own average | `rvol` (menu carries the phantom `day_vol`) | NO — not on menu |
| thorp | The 52-week high and low, to measure the price band the position must survive | none | NO — not in AQE |
| thorp | The last eleven monthly highs and lows | none | NO — not in AQE |
| thorp | Implied volatility, to compare against realised | none | NO — not in AQE |
| thorp | Bid/ask spread and average daily traded volume, to price round-trip slippage | none | NO — not in AQE |
| thorp | Expected holding days for the setup | none | NO — not in AQE |
| thorp | Backtest trade count and how many trades the rule would have generated over the sample window | none | NO — not in AQE |
| thorp | Today's median edge across passing candidates, against its own trailing median | none | NO — not in AQE |

thorp: 22 requirements — 8 yes, 3 partial, 11 missing.

### wyckoff

| Voice | What it needs (plain English) | AQE field | Provided? |
|---|---|---|---|
| wyckoff | Base condition, and whether structure has shifted | `structure`, `structure_shift` | YES |
| wyckoff | Where the name sits against range structure and overhead resistance | `lens.structure`, `lens.resistance` | YES |
| wyckoff | Whether the name is coiling | `lens.coil` | YES |
| wyckoff | Accumulation quality and coiling energy | `flow`, `energy` | YES |
| wyckoff | The 14-day ATR, and the flag for a stop too tight for the regime | `atr_14d`, `atr_caution` | YES |
| wyckoff | How far price sits from its average — near the highs or near the lows | `sma_distance_pct` | YES |
| wyckoff | The 20, 50 and 200-day averages | `ma_20`, `ma_50`, `ma_200` | YES |
| wyckoff | Momentum state, and whether it is decelerating | `mp_state`, `mp_accel_state` | YES |
| wyckoff | Bearish divergence, and how many oscillators confirm it | `div_state`, `div_bear_count` | YES |
| wyckoff | Rejection-candle state and the change-of-character flag | `pin_bar_state`, `choch_state` | YES |
| wyckoff | Whether a valid stop exists — false is a hard reject at any conviction | `bracket.valid` | YES |
| wyckoff | The target ladder above price | `bracket.targets` | YES |
| wyckoff | The entry price | `entry` | YES |
| wyckoff | The stop, its type, how far it sits in ATR terms, and the percentage at risk | `bracket.stop`, `bracket.stop_type`, `bracket.stop_atr_dist`, `bracket.risk_pct` | PARTIAL (27/162) |
| wyckoff | Reward-to-risk | `bracket.rr` | PARTIAL (27/162) |
| wyckoff | Effort against result — volume weighed against price progress | `rvol` (menu carries the phantom `day_vol`) | NO — not on menu |
| wyckoff | Volume profile — the value area, the point of control, high and low volume nodes | `subcomponents.energy.vp_position_score` | NO — not on menu |
| wyckoff | The squeeze and bandwidth-percentile sub-scores behind the coil | `subcomponents.energy.squeeze_score` | NO — not on menu |
| wyckoff | Range boundary, penetration event and recovery flag — the spring, upthrust, secondary test and shakeout | none | NO — not in AQE |
| wyckoff | The wave triad — wave length, cumulative wave volume, wave duration | none | NO — not in AQE |

wyckoff: 20 requirements — 13 yes, 2 partial, 5 missing.
