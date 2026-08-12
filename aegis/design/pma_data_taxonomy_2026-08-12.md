# PMA Data Taxonomy — 2026-08-12

**What each voice needs, what it was offered, what it actually got, and what that cost.**

> PM's brief: *"I need a data taxonomy where I can see what data each voice needs, did they get it or not. This is to backlog into AQE build. If we don't give the voices what they need then they are blind."*

**Sources.** Needs = `aegis/canon/<voice>/canon.lock.yaml` → `recognisers[].fields` and `methods[].fields`. Menu = `VOICE_MENUS` in `aegis/packaging/build_claude.py`. Served = non-null coverage measured across all 162 rows of `aegis/data/pma/2026-08-12/candidate_set.json`. Declared = each seat's own `declared.not_served[]` and `data_gaps[]` in `aegis/data/pma/2026-08-12/voices/<voice>.json`. Run date 2026-08-12; export date 2026-07-28 (15 days stale, PM-acknowledged).

---

## 1. Executive summary

Eleven seats sat. Between them their canon requires **256 field references**. **121 of those (47%) arrived populated and on the menu.** The other **135 (53%) did not** — and only a minority of that shortfall is a data-sourcing problem. Forty-six field references are for data that **already exists in `candidate_set.json` at 96-100% coverage and was simply cut off at the menu** before the packet was written. Twenty-one are the bracket family, present on 27 of 162 rows. Ten are `day_vol`, a field that appears on eight menus and exists on zero rows. Only 58 need genuinely new sourcing. The single biggest cost of the day was not analytical disagreement: 135 of 162 names were removed by a missing stop before a single method was applied, and the seats say so in their own words — Seow: *"that single gate did 83% of today's work."*

| Voice | Fields its canon needs | Served (on menu, ≥96% populated) | Blind | Blind: thin/zero data | Blind: in the export, off its menu | Blind: not in the export | Menu size |
|---|---|---|---|---|---|---|---|
| detect-lens | 55 | 14 | **41** | 3 | 30 | 8 | 8 |
| elder-lens | 13 | 2 | **11** | 2 | 9 | 0 | 6 |
| livermore | 18 | 14 | 4 | 4 | 0 | 0 | 19 |
| lynch | 12 | 11 | 1 | 1 | 0 | 0 | 17 |
| minervini | 24 | 20 | 4 | 4 | 0 | 0 | 24 |
| oneil | 23 | 18 | 5 | 3 | 0 | 2 | 28 |
| raschke | 16 | 13 | 3 | 3 | 0 | 0 | 18 |
| seow | 33 | 3 | **30** | 1 | 3 | 26 | 10 |
| steenbarger | 10 | 6 | 4 | 2 | 0 | 2 | 15 |
| thorp | 29 | 2 | **27** | 3 | 4 | 20 | 18 |
| wyckoff | 23 | 18 | 5 | 5 | 0 | 0 | 31 |
| **TOTAL** | **256** | **121** | **135** | **31** | **46** | **58** | — |

**Impact.** The four worst-served seats — detect-lens, elder-lens, seow and thorp — are blind on 109 of the 135 blind references between them, and three of those four are blind *mainly because of the menu, not the data*. detect-lens has an 8-field menu against a 55-field canon. elder-lens has a 6-field menu and was never shown the `bracket` object its own R10 says is mandatory before it may nominate at all. Fixing the menus costs no new data feed.

---

## 2. Per-voice

Legend for **Served?**: `YES` = on menu and populated ≥96% of 162 rows · `THIN` = on menu but populated on 27/162 (17%) or 125/162 (77%) · `ZERO` = on menu, populated on 0 rows · `OFF-MENU` = populated in the export but cut before the packet · `ABSENT` = not in the export at all.

### 2.1 detect-lens — canon needs 55 fields, menu offers 8

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `lens`, `lens_positive`, `lens_warnings`, `runner_*`, `premove_*` | Yes | YES (100%) | The six-lens read that produced all 10 nominations. This half worked. |
| `lens.leadership`, `lens.insti_money`, `lens.sector` | No (arrive inside `lens`) | YES (100%) | Leadership / institutional / sector sub-lenses — used. |
| `lens.extension` | Yes (inside `lens`) | **ZERO (0/162)** | The extension lens. 6 lenses become 5 evaluable; every "4/6" in this file is really 4/5. |
| `structure`, `energy`, `flow`, `mp`, `elder`, `sc_momentum`, `ptrs` | **No** | OFF-MENU (100%) | Seven engine composites the canon names, all populated, none delivered. |
| `ma_50 / ma_100 / ma_200` | **No** | OFF-MENU (99-100%) | Seat's own words: *"off-menu; C1/C14/C15 trend gate unevaluated."* |
| `atr_14d`, `bracket.risk_pct`, `bracket.stop` | **No** | OFF-MENU / THIN | Seat: *"C5/C13 sizing and C2/C16 exit discipline unevaluated."* |
| `knn_*` (7 fields), `div_*` (5), `choch_*`, `pin_bar_state`, `inside_bar`, `pib_pattern`, `mover_subtype`, `subcomponents.*` (4) | **No** | OFF-MENU (98%) | 20+ recogniser inputs sitting in the export, cut at the menu. |
| `pin_bar_date`, `pin_bar_level` | No | **ZERO (0/162)** | Pin-bar level tests dead even if the menu were widened. |
| `lens_ranking`, `signal_radar` (+ sub-keys) | No | ABSENT | Named as permitted inputs on the card; no such key in the export. |
| Event / earnings / catalyst flag | No | ABSENT | Seat: *"any of the 10 names below may be sitting on an earnings date… This is the single largest hole in this nomination."* |

**Most damaging gap for this seat: the menu itself.** Forty-one of 55 canon inputs did not reach it, and 30 of those 41 are populated at 98-100% in `candidate_set.json`. This is the cheapest large fix in the whole backlog.

### 2.2 elder-lens — canon needs 13 fields, menu offers 6

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `elder`, `elder_5d`, `mp`, `mp_state` | Yes | YES (100%) | The 0-10 blend the seat was forced to decode as a proxy trigger. |
| `elder_pattern` | Yes | **THIN (125/162, 77%)** | Null on 37 rows. Seat: *"PAYX — my joint-highest-conviction name — is one"* of them. |
| `bracket` (entry, stop, stop_type, risk, rr) | **No** | OFF-MENU (object 100%; `stop` 17%) | Seat: *"R10 says a missing or invalid bracket means NO NOMINATION… the field exists and the rule that needs it exists, and the menu stands between them."* |
| `entry`, `ma_20`, `ma_50`, `held`, `structure_shift`, `choch_state`, `pin_bar_state`, `malformed_bracket` | **No** | OFF-MENU (96-100%) | R7 exit censor, R9 pullback-into-value, R11 broken-structure guard — all unrun. |
| `pin_bar_level` | No | **ZERO (0/162)** | C19: stop may never sit beyond a kangaroo tail's tip. Unvalidatable. |
| Impulse colour / transition (`impulse_state`) | No | ABSENT | Seat, severity critical: *"THE VETO ITSELF"* and *"THE TRUE TRIGGER of this reversed seat."* |
| Signed Force Index + 2-bar and 13-bar EMA | No | ABSENT | *"This seat is NAMED after an instrument it does not have… Not one nomination in this file used Elder's buy trigger."* |
| Fitted price channel; weekly trend direction; account equity | No | ABSENT | *"ONE BUILD, THREE RULES"* (channel); weekly is *"the cheapest item on the backlog"*; no sizing possible. |

**Most damaging gap for this seat: the impulse-colour transition** — its own words, *"Highest-value item in the backlog"* — with the off-menu `bracket` a close second, and the second one is free.

### 2.3 livermore — canon needs 18 fields, menu offers 19

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `mp_state`, `mp_accel_state`, `structure`, `structure_shift`, `sma_distance_pct`, `atr_14d`, `rank`, `held`, `gics_sector*`, `sector_trend_state`, `bracket.valid` | Yes | YES (96-100%) | The eligibility screen that produced 4 names. |
| `bracket.stop`, `bracket.stop_type`, `bracket.risk_pct` | Yes | **THIN (27/162)** | C9's absorbable-maximum-loss gate cut 135 of 162 before any tape logic ran. |
| `day_vol` | Yes | **ZERO (0/162)** | *"day_vol is ON MY MENU but is ABSENT FROM ALL 162 CANDIDATE ROWS. I have not even the proxy."* |
| A bullish break-of-structure value | Yes (via `structure_shift`) | **Structurally absent** | Across 162 rows `structure_shift` is only RANGE (129), BEARISH_CHOCH (26), null (7). *"NOT ONE name in this packet can satisfy step 1 in full."* |
| Intraday print sequence / time-and-sales | No | ABSENT | *"TAPE READING — the actual reason I existed… this is the largest single gap in this seat."* |
| Two-stock group Key Price; cost basis / open gain | No | ABSENT | Group-leadership confirmation approximated by hand; C10 profit-banking cannot be raised on any held name. |

**Most damaging gap for this seat: there is no bullish structure value in the export.** Its entry trigger cannot exist in this data, so every nomination is an eligibility read, not a triggered entry.

### 2.4 lynch — canon needs 12 fields, menu offers 17

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `gics_sector*`, `sector_trend_state`, `sma_distance_pct`, `ma_50`, `ma_200`, `structure`, `rank`, `held`, `bracket.valid` | Yes | YES (99-100%) | The whole price half of the seat. |
| `bracket.stop` | Yes | **THIN (27/162)** | Stop position — the only risk statement this seat makes. |
| EPS, growth rate, P/E, dividend, cash, debt, equity, OCF, CapEx, market cap | No | ABSENT | *"PEG, yield-adjusted PEG, net cash floor, effective P/E, equity ratio and FCF yield cannot be produced. No number in this file is a valuation."* |
| Inventory vs sales, two consecutive quarters | No | ABSENT | *"Directly blocks the Cyclical read on CSX… Cheapest high-value ask on my list."* |
| Institutional ownership % | No | ABSENT | Two thresholds ride on it (60% Fast Grower sell, 75% Fail Gate 3). |
| Category placement inputs; bank vs funded debt; capital intensity | No | ABSENT | *"C6 makes every other test conditional on the category… Every nomination below is therefore provisional by construction."* |

**Most damaging gap for this seat: there is no fundamental layer at all.** Its three automatic fail gates could not be tested, so its own instruction stands: read every conviction as capped.

### 2.5 minervini — canon needs 24 fields, menu offers 24

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `entry`, `ma_20/50/100/200`, `sma_distance_pct`, `rs_leadership`, `rs_spy_20d`, `structure`, `structure_shift`, `flow`, `energy`, `rank`, `held`, `gics_sector*`, `sector_trend_state`, `bracket.valid` | Yes | YES (96-100%) | The served-6 Trend Template; 43 of 162 cleared it. |
| `bracket.stop`, `bracket.stop_type`, `bracket.risk_pct` | Yes | **THIN (27/162)** | C15 sizing. Only 2 of the 43 Trend-Template passers had a valid bracket. |
| `day_vol` | Yes | **ZERO (0/162)** | *"the volume signature (C6) — day_vol is absent from every row… even the breakout-day half is unobservable."* |
| 52-week high and low | No | ABSENT | Trend Template criteria 6 and 7 cannot be run. *"sma_distance_pct measures extension from an SMA, not proximity to a high."* |
| MA history / 200-day slope | No | ABSENT | Criterion 3 (200-day rising ≥1 month) not inferred, by choice. |
| VCP contraction count and depth | No | OFF-MENU proxy exists | `elder_context.vcp.vcp_tightness_pct` / `vcp_label` are populated on 155/162 (96%) and were never offered. |
| Earnings growth, EPS acceleration, sponsorship, company category | No | ABSENT | The fundamental half of the Trend Template. |

**Most damaging gap for this seat: the 52-week high/low.** Two of eight Trend Template criteria are unrunnable without it, and no proxy in the export substitutes for either.

### 2.6 oneil — canon needs 23 fields, menu offers 28

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `rs_leadership`, `rank`, `structure`, `structure_shift`, `lens.*`, `ma_50/200`, `entry`, `rvol`, `sc_momentum`, `sma_distance_pct`, `sector_trend_state`, `gics_sector`, `held`, `bracket.price`, `bracket.valid` | Yes | YES (100%) | The L and the technical half of the N. |
| `bracket.stop`, `bracket.risk_pct` | Yes | **THIN (27/162)** | C20/R6 rejected 135 names outright for having no stop. |
| `day_vol` | Yes | **ZERO (0/162)** | *"the field my own card's R4 names… My C16 breakout-volume test could not be run as written on ANY name."* |
| `lens.extension` | Yes (inside `lens`) | **ZERO (0/162)** | Extension cross-check fell back to `sma_distance_pct` vs the set median. |
| `srm_weather`, `macro_brief` | No | ABSENT (frame-level, not row-level) | M gate DELEGATED — *"the gate that decides three stocks in four is not mine to close today."* |
| Quarterly/annual EPS, sales, ROE, cash flow | No | ABSENT | *"The single most weighted letter in CAN SLIM is untested on all four names."* |
| `high_52w` + a labelled pivot / handle peak | No | ABSENT | C7 untestable; and because `entry == bracket.price` on all 162 rows, C17's "never more than 5% past the pivot" has no pivot to measure from. |
| Base stage count, base geometry, group rank, sponsor count, share volume | No | ABSENT | *"A fourth-stage breakout — a sell in my canon — would read to me exactly like a first-stage one."* |

**Most damaging gap for this seat: the C letter (earnings).** Every one of its four names could be a clean base on collapsing earnings and the seat would not see it.

### 2.7 raschke — canon needs 16 fields, menu offers 18

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `mp_state`, `mp_accel_state`, `structure`, `structure_shift`, `sma_distance_pct`, `atr_14d`, `atr_caution`, `lens`, `rank`, `held`, `entry`, `bracket.valid` | Yes | YES (96-100%) | The RETRACEMENT branch — 4 of its 5 nominations. |
| `bracket.stop`, `bracket.stop_type` | Yes | **THIN (27/162)** | *"135 names rejected outright for having no structural stop, before I looked at a single setup."* |
| `day_vol` | Yes | **ZERO (0/162)** | Kills Crabel NR4/NR7 (C12) and the 6d/100d HV gate outright. |
| ADX / +DI / −DI | **No** | **OFF-MENU (98%)** | Seat: *"no directional-strength field exists anywhere in the packet."* It does: `subcomponents.mp.adx_val` and `di_bullish` are populated on 159/162. The Holy Grail (C7) and ADX Gapper (C8) were gated on a declared weak substitute for a field the export already carries. |
| %K/%D stochastic | No | ABSENT | The Anti (C6) is defined by the 7/10 hook. *"SHO is nominated on shape resemblance at conviction 2 for exactly this reason."* |
| Intraday bars, opening print, gap, VWAP, prior-day high/low | No | ABSENT | *"It KILLS four named setup families outright"* — Turtle Soup, TS+1, 80-20, Momentum Pinball, plus the gap family. |
| Breadth / TICK / TRIN; news; cost basis | No | ABSENT | C16, C15, C19 unrun. |

**Most damaging gap for this seat: the intraday layer** — four setup families declined outright, not approximated. The most *embarrassing* gap is ADX: it exists, at 98% coverage, and the menu hid it.

### 2.8 seow — canon needs 33 fields, menu offers 10

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `sma20` → `ma_20`, `sector_trend_state`, `entry` | Yes | YES (100%) | The one dip-to-20MA measurement it could make. |
| `stop` → `bracket.stop` | Yes | **THIN (27/162)** | Used only as proof a stop of measurable width exists (the C15 gate), never as its stop. |
| `atr20` → `atr_14d`; `target` → `bracket.targets`; `risk_pct` → `bracket.risk_pct` | **No** | OFF-MENU (100% / 100% / 17%) | R7's "big candles" test and the C15 size formula both unrunnable. |
| `sma40` (the 40-period SMA) | No | ABSENT | *"The direction test, the set-up's fifth condition and the pullback's holding test are ALL unevaluable. ma_50 is present and was deliberately NOT substituted."* |
| Daily bar OHLC — `open`, `high`, `low`, `close` as separate fields | No | ABSENT | *"Widest single gap."* No bar low → C3 untestable. No prior-day high → **no trigger price can be stated for any pick**. No prior-day low → no C8 stop, no C10 trail. No open → C14's "candle turns red" cannot be armed. |
| `cci20` | No | ABSENT | *"C3's third condition (CCI below −100) cannot be tested on any of the 162 names."* |
| Swing lows / prior support / base low | No | OFF-MENU proxy exists | `fib_swing_low` is populated on 155/162 (96%) and was never offered. |
| `portfolio_value`, `days_held`, 63-day relative-strength series, pullback day-count, 10-day run % | No | ABSENT | No share count stated for any pick; checklist step 2 is `no_data` on all nine. |
| Measured historical hit rate | No | ABSENT | *"By this author's own definition none of the nine is a mechanical trade today."* |

**Most damaging gap for this seat: the daily OHLC bar.** Without a prior-day high there is no buy-stop level, so this seat produced nine study candidates and zero order-ready proposals — it audited itself and recorded checklist step 5 as `fail` on every one.

### 2.9 steenbarger — canon needs 10 fields, menu offers 15

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `ma_50/100/200`, `structure`, `bracket.valid`, `lens_warnings`, `sc_momentum`, `gics_sector_name` | Yes | YES (99-100%) | The MA-stack ordering and lens-conflict read behind all 5 names. |
| `bracket.stop`, `bracket.risk_pct` | Yes | **THIN (27/162)** | Risk geometry — the only quantified half of this seat's case. |
| `day_vol` | Yes | **ZERO (0/162)** | *"Menu-listed, absent from every row."* |
| `regime`, `srm` (as row-joined objects) | No | ABSENT at row level | Regime label exists in the frame; the **conditional edge estimate per lens given this regime** does not. *"Size may NOT be justified on environment match alone for any name above."* |
| Forward-return separation vs baseline | No | ABSENT | *"Every field I cited above… is UNPROVEN in the R1 sense: described, never leaned on as measured edge."* |
| Explicit invalidation field; first-class ABSTAIN verdict | No | NOT SERVED BY CONTRACT | Cannot formally stand aside on the other 157 names. |
| Ledger memory of its own prior nominations; realised-exit data | No | ABSENT | Cannot see whether it is re-clustering into XLF/XLI across days. |

**Most damaging gap for this seat: measured forward-return separation.** This is the seat whose entire canon is "is this edge real" — and nothing in the packet is measured, so it graded structure instead of edge.

### 2.10 thorp — canon needs 29 fields, menu offers 18

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `atr_14` → `atr_14d`, `bracket.price`, `bracket.valid`, `bracket.rr/rr_tp1/rr_tp2`, `sc_momentum`, gate details | Yes | YES / THIN | The R-multiple worst-case test that produced 4 names. |
| `stop_price` → `bracket.stop`, `stop_distance_pct` → `bracket.risk_pct` | Yes | **THIN (27/162)** | *"20 of the 27 valid-bracket names failed R3"* — the survivors were 4. |
| `avg_daily_volume` → `day_vol` | Yes | **ZERO (0/162)** | Liquidity and cost modelling. *"a realistic round-trip cost could flip the sign of the whole decision."* |
| `realised_vol_30d` | **No** | **OFF-MENU (100%)** | `vol_30d_ann` is populated on all 162 rows and was never offered. |
| `entry_price`, `candidate_set_vol_rank`, `universe_membership` | **No** | OFF-MENU (100%) | Derivable from data already in the export. |
| `high_52w` / `low_52w`, `monthly_high_11` / `monthly_low_11` | No | ABSENT | *"The canon volatility measure (high-to-low range over its midpoint) cannot be computed."* |
| `bid` / `ask` / spread / commission / fill model | No | ABSENT | *"Every R-multiple I quote is gross."* |
| Backtest trade count, hit rate, signal edge current + trailing median, sample window | No | ABSENT | *"This is the largest hole in my read and it caps every conviction at 3."* |
| `implied_vol`, return series on a log scale, `position_size_pct` | No | ABSENT | C7/C23 cheap-to-model check and C16 reliability test out of reach. |

**Most damaging gap for this seat: measured base rates.** Its canon is arithmetic on a proven edge; with no hit rate it can price a structure but never demonstrate one, and it capped every conviction at 3 for exactly that reason.

### 2.11 wyckoff — canon needs 23 fields, menu offers 31

| Data the voice needs | On its menu? | Served? | What it enables or blocks |
|---|---|---|---|
| `structure`, `structure_shift`, `mp_state`, `mp_accel_state`, `energy`, `flow`, `lens.coil/structure/resistance`, `sma_distance_pct`, `ma_50/200`, `atr_14d`, `atr_caution`, `pin_bar_state`, `choch_state`, `div_state`, `div_bear_count` | Yes | YES (96-100%) | Geography, contraction and the coil test — its only objective entry-timing filter. |
| `bracket.stop`, `bracket.stop_type`, `bracket.stop_atr_dist`, `bracket.risk_pct` | Yes | **THIN (27/162)** | *"83% of the field carries invalid_reason 'no valid bracket'. This single gate, not my geography or contraction test"* did the cutting. |
| `day_vol` | Yes | **ZERO (0/162)** | *"Effort, the volume half of C6/C16, and with it R4, R5 and the C15 trap reject."* |
| `range_high` / `range_low` | No | ABSENT | No range boundary object — C1, C3, C7, C10. |
| `last_penetration {level, direction, volume_ratio, recovered}` | No | ABSENT | *"no spring and no upthrust can be detected"* — the two signature Wyckoff events. |
| Wave objects; daily OHLCV bar series; net up-minus-down volume | No | ABSENT | C13/C19/C20, C4/C5/C11/C12/C17, C16/C6 — *"FORCE is unreconstructable from daily bars at all."* |
| Volume profile — value area, VPOC, HVN/LVN | **No** | **OFF-MENU (98%)** | Seat: *"Computed by the Energy engine as vp_position_score and discarded before export."* It is **not** discarded — `subcomponents.energy.vp_position_score` is populated on 159/162. The menu discarded it. |
| `lens.extension` | Yes (inside `lens`) | **ZERO (0/162)** | Mid-move-vs-edge test fell back to `sma_distance_pct`. |

**Most damaging gap for this seat: `day_vol`.** Wyckoff is effort-versus-result; with no volume there is no effort, and half the method is inert. Its own `not_served[]` lists it first.

---

## 3. The AQE backlog, ranked

Rank = (voices blocked × severity). Severity 3 = blocks a hard gate, veto or trigger the canon states as mandatory · 2 = blocks a named test · 1 = degrades a read.

### 3.1 CONCRETE FIELDS — fixable in the exporter, no new data source

| # | Gap | Voices blocked | What breaks | Priority |
|---|---|---|---|---|
| 1 | **Bracket family populated on only 27/162 rows** (`stop` 17%, `risk_pct` 17%, `stop_type` 17%, `rr` 17%, `stop_atr_dist` 17%, `rr_tp1/tp2` 17%) | **11 of 11** | No stop → no size → no entry. 135 names removed before any method ran. Minervini: 43 passed the Trend Template, 2 had a bracket. Thorp: 20 of the surviving 27 failed R3. | **P0** (33) |
| 2 | **`day_vol` — on 8 menus, populated on 0 rows** | **7** (oneil, wyckoff, raschke, steenbarger, minervini, livermore, thorp) | O'Neil C16 breakout volume; Wyckoff effort + C15 trap reject; Minervini C6 volume signature; Raschke NR4/NR7 + HV gate; Livermore fill-difficulty proxy; Thorp liquidity and cost model. | **P0** (21) |
| 3 | **Menu truncation — fields already in `candidate_set.json` at 96-100%, cut before the packet** (46 field references) | **6** (detect-lens 30, elder-lens 9, thorp 4, seow 3, raschke ADX, wyckoff volume profile) | elder-lens never saw `bracket` though R10 forbids nomination without it. raschke declared ADX absent — `subcomponents.mp.adx_val` is 98% populated. wyckoff declared volume profile discarded — `subcomponents.energy.vp_position_score` is 98% populated. thorp declared no realised vol — `vol_30d_ann` is 100%. detect-lens lost its whole engine-composite and knn/div layer. | **P0** (18) — cheapest fix in the backlog |
| 4 | **`elder_context` off every menu** (155/162, 96%) | 4 (elder-lens, minervini, wyckoff, oneil) | Carries `volume.avg_vol_20d`, `up_bar_vol_ratio`, `vol_trend_5d`, `vcp.vcp_tightness_pct`, `vwap_5d` — a partial answer to `day_vol`, to Minervini's VCP count and to Wyckoff's effort read. elder-lens declared it "ABSENT from this packet". | **P1** (12) |
| 5 | **`lens.extension` — key present, null on all 162 rows** | 3 (detect-lens, oneil, wyckoff) | The extension lens. detect-lens's "4/6" scores are really 4/5; oneil and wyckoff both fell back to `sma_distance_pct`. | **P1** (6) |
| 6 | **`pin_bar_level` / `pin_bar_date` — null on all 162 while `pin_bar_state` is 98%** | 2 (elder-lens, detect-lens) | Elder C19: a stop may never sit beyond a kangaroo tail's tip. State without level is unusable. | **P2** (4) |
| 7 | **`elder_pattern` populated on 125/162 (77%)** | 1 (elder-lens) | Checklist step 2 pattern confirmation and step 3 INTERRUPTED filter return `no_data` on 37 rows — including PAYX, the seat's joint-highest conviction name. | **P2** (2) |
| 8 | **`thematic_basket` / `thematic_grade` on 30/162 (19%)** | 1 (druckenmiller — seat did not sit today) | Thematic overlay unusable when that seat returns. | **P3** (1) |

**Impact.** Rows 1-4 are all packaging or population defects in data the system already computes. Fixing them returns 85 of the 135 blind field references without sourcing a single new feed.

### 3.2 CONCEPT GAPS — need new data sourcing

| # | Gap | Voices blocked | What breaks | Priority |
|---|---|---|---|---|
| 1 | **Daily OHLC bar series** (open/high/low/close + per-bar volume, joined to the row) | **8** (seow, wyckoff, raschke, elder-lens, livermore, minervini, thorp, detect-lens) | Seow: no prior-day high → **no trigger price for any pick**; no prior-day low → no stop, no trail; no open → no red-candle exit. Wyckoff: no two-bar relationship, no close-position-in-range, no bar-measured SOT. Raschke: NR4/NR7 and the 80-20 family. Minervini: VCP depth. detect-lens: single-day gap magnitude (C15 disqualifier). | **P0** (24) |
| 2 | **Event / earnings dates + news** | 4 (detect-lens, raschke, oneil, lynch) | detect-lens: *"the single largest hole in this nomination"* — its EVENT-DRIVEN exclusion could not be applied to any of its 10 names. Raschke C15 (news and price reaction to it). Grep of all 162 rows returns zero keys matching `event`. | **P0** (12) |
| 3 | **Portfolio / account state** (equity, cost basis, days_held, open P&L, realised exits, commissions, slippage) | **6** (elder-lens, seow, raschke, livermore, thorp, steenbarger) | No seat can state a share count. Elder C15's 2% cap and C16's 6% monthly breaker; Seow's `shares = (portfolio value × risk %) / (entry − exit)`; Seow's day-5 time stop on V/NU/VRSK; Livermore C10 profit-banking; Thorp's gross-only R-multiples; Steenbarger's realised-exit-vs-bracket comparison. | **P1** (12) |
| 4 | **Intraday tape** (time-and-sales, print sequence, bid/ask, VWAP, TICK/TRIN, L2 depth) | 5 (livermore, raschke, wyckoff, thorp, detect-lens) | Livermore: *"the actual reason I existed."* Raschke: four setup families declined outright. Wyckoff: net up-minus-down volume, FORCE. Thorp: spread and fill model. | **P1** (10) |
| 5 | **Earnings / fundamentals** (quarterly + annual EPS, sales, ROE, cash flow, debt, inventory, market cap) | 3 (lynch, oneil, minervini) | O'Neil's C and A letters — *"the single most weighted letter in CAN SLIM is untested."* Lynch's entire mathematical library and all three automatic fail gates. Minervini C1 element 2 and C12. | **P1** (9) |
| 6 | **52-week high and low** | 3 (minervini, oneil, thorp) | Minervini Trend Template criteria 6 and 7. O'Neil C7 new-high confirmation and C17's pivot reference. Thorp's canon volatility measure (C5). | **P1** (9) |
| 7 | **Measured base rates** (hit rate, trade count, signal edge current + trailing median, sample window) | 3 (thorp, seow, steenbarger) | Thorp: *"caps every conviction at 3."* Seow C18: *"none of the nine is a mechanical trade today."* Steenbarger C1/C2: every field cited is UNPROVEN in the R1 sense. | **P1** (9) |
| 8 | **Institutional ownership / sponsorship** | 3 (lynch, oneil, minervini) | Lynch's 60% Fast Grower sell signal and 75% Fail Gate 3; O'Neil's I letter (sponsor count, trend, fund quality); Minervini C2/C6/C14 supporting evidence. | **P2** (6) |
| 9 | **Weekly-timeframe resample** (`weekly_trend_direction`, read before the daily) | 2 (elder-lens, seow) | Elder C21 calls the ~5:1 ratio *"a CONTROL, not a preference"*; the seat calls this *"the cheapest item on the backlog."* Seow C21 same shape. | **P2** (6) |
| 10 | **A bullish break-of-structure value in `structure_shift`** | 1 (livermore; oneil C7 adjacent) | `structure_shift` takes only RANGE / BEARISH_CHOCH / null across 162 rows. RANGE is the *absence* of the trigger, not its presence — so Livermore's C5 confirming-new-high can never be satisfied by this export in principle. | **P1** (3, but structural) |
| 11 | **Range boundaries + penetration events** (`range_high/low`, `last_penetration{level, direction, volume_ratio, recovered}`, wave objects) | 1 (wyckoff) | Springs and upthrusts — the two signature Wyckoff events — are undetectable. C7-C10, C13, C19, C20. | **P2** (3) |
| 12 | **Impulse colour + signed Force Index** (elder engine internals) | 1 (elder-lens) | *"THE VETO ITSELF"* and *"THE TRUE TRIGGER."* Note: `elder.py` computes the colour and blends it away — this is arguably a concrete fix, not a sourcing one. | **P0 for this seat** (3) |
| 13 | **ADX / +DI / −DI as a first-class field**, `%K/%D` stochastic, `cci_20`, `ma_40` | 2 (raschke, seow) | ADX already exists inside `subcomponents.mp` (see concrete #3); the stochastic, CCI and 40-period SMA do not exist anywhere. Raschke's Anti (C6) and Seow's C1/C3/C7 timing layer. | **P2** (4) |

**Impact.** Two sourcing projects — a **daily OHLC bar series** and an **event/earnings calendar** — touch 10 of the 11 seats between them, and the bar series alone is the prerequisite for the six named setup families (Turtle Soup, TS+1, 80-20, Momentum Pinball, ADX Gapper, Whiplash) that Raschke declined outright rather than approximate.

---

## 4. The two headline findings

### (a) `day_vol` is offered to eight voices and exists on zero rows — and that is worse than omitting it

`day_vol` appears on the menus of **oneil, wyckoff, raschke, steenbarger, thorp, minervini, rogers and livermore**. It appears in the recogniser fields of five canons. It is populated on **0 of 162 rows** — the key is not in `candidate_set.json` at all, so the packet builder silently drops it and the seat receives a packet where the field simply is not there.

This is not a neutral omission. A menu is a promise: it tells a seat "this data is yours to read." Six of the eight seats caught it and declared it — Wyckoff listed it first in `not_served`, O'Neil wrote *"ABSENT from all 162 rows in this packet though it is listed on the packet menu"*, Livermore wrote *"day_vol is ON MY MENU but is ABSENT FROM ALL 162 CANDIDATE ROWS. I have not even the proxy."* They caught it because these seats are disciplined about declaring. **A seat that is less disciplined, or a future seat, reads a volume field on its menu and narrates a volume read it never made.** The failure mode is not a missing number; it is a fabricated one. Either populate `day_vol` or remove it from all eight menus — leaving it in place is the one option that invites the system to lie to the PM.

### (b) The bracket family is served on 17% of rows, and that single gap out-filtered every method in the committee combined

`bracket.stop` and its siblings are populated on **27 of 162 rows (17%)**. `bracket.stop` is on nine menus and in seven canons; `bracket.risk_pct` on seven; `bracket.stop_type` on four; `bracket.rr` on three. On the 135 rows without one, `bracket.invalid_reason` reads *"no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)."*

Every seat that gates on risk hit this wall before it applied a single element of its own method, and they said so independently:

- **Seow:** *"162 rows in; 135 carry a null bracket.stop and were refused outright by C15 (no stop, no size, no trade) before any chart quality was read — that single gate did 83% of today's work."*
- **Wyckoff:** *"83% of the field carries invalid_reason… This single gate, not my geography or contraction test"* did the cutting.
- **Raschke:** *"R6/C17 first: bracket.valid=true on only 27 — 135 names rejected outright for having no structural stop, before I looked at a single setup."*
- **O'Neil:** *"162 candidates; 135 carry bracket.valid=false and are rejected outright under C20/R6, leaving 27."*
- **Livermore:** the C9 gate reduced 162 → 27 as step one of the screen.
- **Minervini:** 43 names cleared the observable Trend Template; **2** of them had a valid bracket.
- **Thorp:** of the 27 survivors, 20 failed R3 on `rr_tp1` versus the R-cost of a one-ATR gap — leaving 4.

The committee's nine methodologies, run independently, collectively narrowed 162 names to a deliberation set of 16. **The bracket gate alone narrowed 162 to 27.** The committee is currently a second-order filter on top of a first-order data defect — and the defect is in one object. Of the 27 stops that do exist, 12 are literally `ma_20` (Seow: *"which is NOT a C8 stop"*), 6 are swing lows, 4 are other MAs, 2 fib levels. Widening bracket coverage is the highest-leverage single change available to AQE: it is the only fix that would let the committee's own methods, rather than the exporter, decide what gets nominated.

---

*Compiled 2026-08-12 from the 11 seat nomination files, their canon locks, `VOICE_MENUS`, and all 162 rows of `candidate_set.json`. Coverage percentages are measured, not estimated. Every quoted line is verbatim from the seat that wrote it.*
