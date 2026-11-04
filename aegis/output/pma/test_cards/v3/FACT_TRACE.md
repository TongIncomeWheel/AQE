# FACT_TRACE: aegis_daily_cards_v3.html (v2 sections unchanged; new section 5b at the end)

Every number is read by `build.py` from JSON or Markdown at build time. Nothing is typed in by hand except fixed doctrine thresholds that come from the real page. Run dir: `R = /home/user/pma_run/2026-11-04-r2/`. Refreshed weather (read only): `A = /home/user/AQE/aegis/output/`.

**Path note.** The brief named `/home/user/AQE/output/valen_dashboard.json` and `crown_macro.json`, but those files do not exist. The refreshed copies (13:21 / 13:20 SGT) are in `/home/user/AQE/aegis/output/`, and those are the ones used.

Short names used below: CT = `R/cards_text.json`, LV = `R/pma_levels.json`, CO = `R/consensus.json`, CP = `R/committee_position.json`, VD = `R/aqe_valen_dashboard.json` (committee copy), CM = `R/aqe_crown_macro.json` (committee copy), EX = `R/aqe_daily_export.json`, CJ = `R/cards.json`, DC = `R/decision.json`, LR = `R/aqe_last_run.json`, P4 = `R/phase4.json`, SC = `R/scorecard.md`, RV = `A/valen_dashboard.json`, RC = `A/crown_macro.json`.

## Top block
- **Header:** the date and "rerun r2, not live" come from `CT.session_label`. The count 7 is the number of ADVANCE rows in CO.
- **Title:** my own short sentence, built from the ADVANCE count, `VD.regime` ("DOWNTREND") and `CM.readings.positioning.option_dealers.regime` = NEGATIVE (the build asserts this). It replaces `CT.bottom_line.headline` to keep the first screen at 120 words. The facts are the same.
- **Ask:** taken from `CT.plan[0]` (decide on MP before 22:30 SGT) and the ADVANCE count.
- **Freshness line:**
  - Run time 07:15 comes from `LR.exported_at`.
  - "breadth stale" comes from `LR.macro_legs`.
  - Refreshed 13:21 comes from `RV.exported_at`.
  - The only leg not current is `RV.data_freshness.legs_table` positioning_cot, as of 2026-10-27.
  - "now" is the build-time clock in SGT.
- **Tiles:**
  - 7 / 1 agreed / 6 contested: CO verdict and status.
  - −3.18%: `EX.spy_roc_20d`. Close 754.35: `VD.trend[SPY].last_price`.
  - VIX 20.83: `CM.readings.volatility.vix`. "82%" is parsed from the text of `CM.read_me_first.why`.
  - 5 of 7: computed by the reward-ladder logic below.
- **Reasons:**
  - Trend: `VD.trend` daily and weekly signals.
  - Flip 768.70 and 1.9%: `CM.readings.positioning.option_dealers.detail.SPY`.
  - Leading sectors: `EX.srm[].entry_gate == PASS`.

## 1 Macro and weather
- **Valen:**
  - Prices and signals: `VD.trend[]`. Distance from the 50-day average: `VD.extension[]`.
  - 1,600 / 4,314 / 95% are parsed from `VD.breadth[0].reason`.
  - The doctrine sentence is copied whole from `CT.market.weather[1]`.
- **Dealer gamma:**
  - Spot, flip and walls for SPY and QQQ: `CM.readings.positioning.option_dealers.detail`.
  - Distances: `CM.key_levels` (SPY put wall −0.58%, call wall 2.07%).
  - Read: the last sentence of `CT.market.what_happened[2]` plus the last sentence of `CT.market.weather[2]`, both copied whole.
- **Breadth heartbeat:**
  - Days in regime, 5/20/60-day changes and confidence: `CM.readings.breadth`.
  - The 12-month high and low, the 20-day average and the −3.37% distance: `CM.key_levels` (RSP/SPY rows).
  - The line itself (252 sessions): `RC.heartbeat.series` (ratio, ma_20). Its last point, 3 Nov at 0.290661, equals the committee value.
- **Trend funds:**
  - The six nearest flips: `CM.key_levels` kind "trend followers", sorted by absolute distance.
  - Markets read, share at an extreme, size dial and lean by sector: `CM.readings.positioning.trend_funds`.
- **Volatility:**
  - VIX, single-stock volatility, gap, gap vs history (79%), 20-day change, implied correlation and curve shape: `CM.readings.volatility`.
  - Calm and elevated bands: `CM.key_levels` volatility rows. Implied-correlation percentile (71.2): `CM.key_levels` correlation row.
  - Data date: `CM.how_current.volatility_as_of`.
  - Read: the "Read:" sentence of `CT.weather.volatility`, copied whole.
- **Divergence:**
  - 1 of 8: `VD.crown_cockpit.divergence`. The 9 on individual markets: `CM.readings.divergence.warnings_lit`.
  - Read: two whole sentences from `CT.weather.divergence`.
- **Crown's call:**
  - Family, fit, the 1.00x multiplier, and conditions met and not met: `CM.the_call`.
  - The 58% story and the runner-up: `CM.scenario`.
  - Read: `CM.scenario.story` plus the first clause of `CM.read_me_first.so_what`. The clause was cut at the dash, not reworded.
  - Collapsed: `CM.read_me_first.what_would_change_it`.
- **Coming events:**
  - Source: `CM.what_is_coming` (kind macro). SGT times are converted from ET with zoneinfo.
  - Shown: today through 11 Nov, at most 5 rows. Collapsed: all of them, with what each one tests.
  - Read: last sentence of `CT.market.what_happened[3]`.
- **Speculator crowding:**
  - Which markets are crowded: `VD.crown_cockpit.cot`.
  - Percentiles: `RC.cot.markets[*].percentile`. This is the same 27 Oct report; the committee copy carries no percentiles.
  - Next release 6 Nov: `RV.data_freshness.legs_table` COT detail.
  - Read: the last clause of the `CT.weather.cot` "Read:" sentence, plus the dates. **Judgement call:** this is the one copied text shortened inside a sentence (to "Crowding is fuel ... never a timing signal").
- **Direction of the wind:**
  - 37%, 1,600 / 4,314 and 95%: parsed from `VD.breadth[0].reason`.
  - The 11 stale gauges: `VD.breadth[].label`.
  - Read: the "Read:" sentence of `CT.weather.checklist`, copied whole.
- **Weather turning:** `VD.history` (trend regime; SPY distance from the 50-day average now, 5 days ago and 1 month ago).

## 2 Sector and theme strength
- **Sectors:**
  - Values: `EX.srm[]` roc20 and entry_gate.
  - Read: `CT.money[0].meaning` and `CT.money[2].meaning`, copied whole. Collapsed: the full `CT.money` table.
- **Themes:**
  - Values: `VD.theme_leaders` where rotation_state is LEADING or OFF_THE_FLOOR, in the same order as the real page. Showing the first 5.
  - Collapsed: `VD.neighbourhood`, the full leaders list, and `VD.rotation` (top 6 by thrust).
  - Read: the "Read:" sentence of `CT.weather.themes`.
- **Group turns:**
  - Recomputed from `EX.daily_list` (on_longlist or on_elder, rs_spy_20d, entry, ma_50, thematic_baskets) and `EX.srm`, with the same rule as the real page's `_group_turns`. Verdict tags come from CO.
  - The counts match the real page: Industrials 37, Technology 27, Communication Services 9, Semiconductors 2.
  - Read: the "Read:" sentence of `CT.weather.groups`.
- **Valen house setups:**
  - Counted from `EX.daily_list[].setups` plus held rows, with parabolic and failed-leader warnings left out (R41).
  - Totals: 72 failed, 4 watch, 1 past the pivot, 0 triggered or ready. These match the real page's per-setup line.

## 3 What happened
- **Index and list:**
  - Tuesday SPY +0.30%, list −0.91% and 58/350: the last row of the SC "list vs the market" table.
  - SPY 20-day: `EX.spy_roc_20d`. Distance from the 50-day (1.62): `VD.extension`.
- **Rates, dollar and commodities:**
  - Five-day values: `EX.macro_weather.*_roc5`. Read: `EX.macro_weather.regime_description`, copied whole.
  - Collapsed 20-day view: `EX.intermarket` (TLT, UUP, HYG roc20; IWM roc20).
- **Volatility:**
  - VIX against 3-month VIX now / 5 days / 1 month (0.98 / 0.92 / 0.85): `VD.history`.
  - The 0.82 and 1.00 bands and the read sentence come from the real page's "What these mean" explainer (rendered HTML only).

## 4 Your book
- **V and MP:**
  - Quantity, entry, last price, P&L and stop: `EX.held_positions`.
  - MP's 20-day average and stop distance: `VD.management.trim_trail`.
  - The add line 423.72 is parsed from `CT.book[V].why`. The read lines are `CT.book[].why`, cut at a semicolon boundary: for V the "reports" clause moved to a tag; for MP the share and P&L clause is dropped because the strip shows it.
- **Concentration:**
  - Beta-adjusted exposure, betas, sector weights, cost of a 1% gap and the gap scenarios: `EX.held_book`.
  - Trim/trail table: `VD.management.trim_trail`.
  - "Management switch not served": `VD.management.manage_note.status`.

## 5 The tickers
- **Changed since yesterday:** the tickers are parsed from `CT.changed[]`. Collapsed: those sentences, verbatim.
- **Void line:** `DC.market_kill.plain`, with the canon codes and seat names stripped (the same rule as the real page's `_plain_void`).
- **Reward chart and cards, mechanics as in v1:**
  - Entry = the close_above level in `LV.triggers`. Stop and targets = `LV.levels.stop` and `.tp`. These are identical to `R/brackets.json`.
  - R = (TP − entry) / (entry − stop). Only levels at 1.0R or more count as targets.
  - Shares = floor(620 / risk).
- **Card fields:**
  - Volume requirement: `CJ.advance[t].triggers` close_above.volume_min_x. Dead-if level: close_below level.
  - Last close: `EX.daily_list[t].entry`. Status: CO. Conviction: `CP[t].committee_conviction`.
  - Sector: `EX.daily_list.gics_sector_name`, gate from `EX.srm`.
  - The "Reports ..." sentence is copied whole from `CT.cards[t].sector_note`.
  - Wait for, Why and Wrong if: `CT.cards[t].reason.*`, verbatim.
- **Reward too thin:** ROKU has one target at 2.1R (168.20). FA has no level reaching 1R; its nearby levels are 21.86, 22.37 and 22.78 at −0.4R, 0.0R and 0.3R.
- **Two-sector line:** my own sentence, from each name's sector in EX and the put-wall distance in `CM.key_levels`. It restates the facts in `CT.common_risk`.
- **HOLD table:**
  - Wait zone: parsed from `CJ.hold[t].triggers` (the "wait area X-Y" action text).
  - Buy level and volume: close_above. Dead if: close_below, or `kills` for V.
  - AQE rank: `EX.daily_list.rank`. Collapsed: `CT.holds[]`.
- **PASS list:** `CT.passes[]` for every PASS row in CO (32 rows; 5 have status DROPPED).
- **Strong names, Detect lens and top 20:**
  - Strong and reclaim seats: `P4.strong_seats` and `P4.unr_seats`. The next-strongest table: `P4.informational`.
  - Detect lens: `EX.lens_ranking.ranked[:10]`.
  - Top 20: `EX.daily_list` by rank, with sector state from `EX.srm` (same rule as the real page). Committee verdict: CO.

## 6 The plan
- `CT.plan[]`, verbatim. The text before the first colon became the time label, and the first letter of the remainder was capitalised.

## 7 Scorecard
- Bars and beat counts: the SC "Full-horizon calls only" table.
- Collapsed: the SC "list vs the market" table.
- Yesterday's figures: the last row of that table.

## 8 Read with care
- `CT.caveats` items 0, 1 and 7 to 12, verbatim apart from the term swaps listed below.
- `LR.committee_data_status` and `LR.ma_panel_refresh`.
- **Refreshed facts after the committee:**
  - Stance RISK_OFF: `RV.stance`.
  - 50.3% of 3,777 stocks above the 40-day line, and the 5-day count of 0.45: `RV.breadth`.
  - Flip 770.69 / 2.17%: `RV.gex`.
  - Two change lines: `RC.what_changed.changes`.

## Taken only from the rendered real page (HTML text, not a JSON key)
- The VIX/VIX3M bands (under 0.82 calm, over 1.00 stress) and that read sentence.
- The VIX thresholds of 15 (sell premium) and 25 (protection expensive). These also appear as `CM.key_levels` rows.
- The explainer wording behind the "What ... is" clicks: the flip and walls, the equal-weight line, trend funds, volatility, divergence, crowding (85th and 15th percentile), and the 40-day line (20%, 80%, 50%).
- (A buy-signal definition was drafted, could not be traced to a run file, and was removed from the page.)

## Left out deliberately, with reasons
- **Caveats 2 to 6** (rationale-file engineering, the QA hold list, result-by-code, committee position, the commit hash). They contain rule codes (R34, R42), vote counts ("7 of 7", "2-2 ties") or seat language, which the brief forbids, and the copy rule does not allow rewording them. The decision-relevant pieces appear elsewhere: the DIS earnings date on its card, the agreed and contested status on each card, and the conviction per card.
- **Seat names, per-seat objections and minority notes** (the audit trails), the "Voted for it" column of the top 20, and Valen's no-buy list and parabolic warnings (R41).
- **The real page shows "Net new highs ... Worsening" in the wind block.** That comes from a null value read as false in `pma_cards.py::_wind_gauges`. The gauge was stale, so v2 lists it as stale instead.

## Source inconsistencies seen (not resolved, shown as the sources state them)
- **V's add line:** `CT.book` and `CT.plan` say a daily close above 423.72 on 1.4x volume. `CJ.hold.V` and the real page's HOLD row say an hourly close above 425.51 on 1.4x volume. v2 shows 423.72 in the book and 425.51 in the HOLD table, as the real page does.
- **The 5-year Treasury** is listed as crowded long at the 99th percentile while its net position is short (`RC.cot.markets.ZF.net_spec` < 0). Shown as the file states.

## Term swaps (wording only, never a fact)
In copied PASS and HOLD reasons and caveats: "rs rank" became "strength rank", "ATRs" became "daily ranges", "Elder impulse" became "momentum score" and "RSI" became "momentum". The real page applies the same kind of swap.

---

## 5b The three AQE lists against the committee (new in v3)

Every figure is computed by `lists_vs_committee.build(R)` (zero model calls; `build()` ran in about 0.06 s, the whole module as a process about 0.12 s, the whole page build about 0.25 s). `build.py` only draws what it returns. The figures below are this run's values; the code recomputes them each run.

### Definitions (reused from the real page's code, `AQE/aegis/plugin/aegis-core/skills/pma/tools/pma_cards.py`)
- **In the room** = the ticker has an entry in `CO` (44 entries). Same test as `_detect_lens_panel` / `_top20_panel` ("not in the room" = no consensus entry).
- **Outcome:** `CO[].verdict` ADVANCE -> Advance; HOLD-FOR-CONDITIONS -> Hold; PASS -> Passed in the room (status NOT_SLATED or DROPPED, sub-label from `CO[].status`); no entry -> Never in the room.
- **Elder top 15:** `EX.daily_list[]` with `on_elder` true (136 names), sorted by `elder` high to low, then `rank` (AQE rank) low to high; first 15.
- **AQE top 20:** `EX.daily_list[]` sorted by `rank`, first 20 (as `_top20_panel`).
- **Detect lens top 15:** `EX.lens_ranking.ranked[]` in its stored order (strong-lens count desc, warnings asc, momentum desc, per `_detect_lens_panel`), first 15.
- **Union:** 40 different tickers across the three lists.

### A. Outcome chart and read
| Figure | Value | Source |
|---|---|---|
| Elder top 15 outcomes | 1 advance, 0 hold, 7 passed, 7 never | CO verdict/status per ticker, absent = never |
| AQE top 20 outcomes | 0 advance, 2 hold, 6 passed, 12 never | same |
| Detect lens top 15 outcomes | 2 advance, 1 hold, 4 passed, 8 never | same |
| All three (40) | 3 advance, 3 hold, 12 passed, 22 never | same, over the union |
| Section title "took 18 of the 40" | 40 - 22 | union |
| "13 of the 22 it never saw are extended" | tag x outcome cross-count | tag rules below |
| Agrees most / least | advance + hold per list: lens 3/15, AQE 2/20, Elder 1/15 | computed |
| Sector buckets | DEPLOY: Elder 10/15, AQE 11/20, lens 12/15; TURNING with gate BLOCKED: 3/3/3 | `EX.srm[sector].grade` / `.entry_gate` for the row's `gics_sector_name` (DEPLOY sectors are all quadrant LEADING) |
| Strength seats (10 names) and reclaim-day seats (3) | BRZE, GMAB, HAYW, EFX, ACN, GPK, GEN, RHI, KVYO, CART; HNGE, BILL, KBR | `P4.strong_seats[]`, `P4.unr_seats[]` |
| "Doors flag, never seat" | rule text | `P4.doors_rule` (each door: "FLAG ONLY ... never seats a name") |
| "doors flagged 17 of the 22" | never-in-room tickers found in `P4.dropped[]` (parsed ticker before "(") or `P4.informational[]` | P4 |
| 44 names in the room | `len(CO)` | CO |

### B. The three tables (one row per name)
- **Sector** = `gics_sector_name`; state = `EX.srm[].grade`, `.rrg_quadrant`, and ", gate blocked" when `.entry_gate` = BLOCKED.
- **Theme basket** = first entry of the row's `thematic_baskets[]` (`basket`, `grade`, `rrg_quadrant`); week / month % = `VD.theme_leaders[name].ret_1w_pct` / `.ret_1m_pct`. A dash = no basket on the row.
- **Over 20-day (ranges)** = `extension_atr_20`. **Under 20-bar high** = `(hi_20d - entry) / hi_20d x 100`. **Volume vs avg** = `day_vol`.
- **Setup** = the tag rule below; the small line under it is the rule that fired (hidden when the reason column already states the same fact).
- **Reason**, voted names: Advance = first sentence of `CT.cards[t].case`; Hold = `CT.holds[t]`; Passed = `CT.passes[t]`; each through the plain-words pass. Never in the room: "No voice nominated it;" + the FIRST of these stored facts that applies: `pct_from_pivot` > 5 -> `entry/ma_200 - 1` > 70% -> sector `entry_gate` BLOCKED (or grade TURNING) -> `day_vol` < 1.4 -> `extension_atr_20` > 4 -> "no single stored AQE fact stands out".
- Table headlines: extended / never counts per list (above); Detect "9 are breaking out".

### C. Tag rules (exact, first match wins) — `lists_vs_committee.setup_tag`
1. **EXTENDED** if any: `pct_from_pivot` > 5.0 (committee line: CO SN objection "a late buy past pivot_high +5pct"; glossary for `pct_from_pivot`: 0-5% buy zone); `(entry / ma_200 - 1) x 100` > 70 (committee line: CO HNGE objection "more than 70% above the 200-day", also CT.passes BRZE); `extension_atr_20` > 4.0 (**AQE tag rule, not a committee rule**).
2. **BREAKING OUT** if 0 <= `pct_from_pivot` <= 5.0.
3. **COILING** if `pct_from_pivot` < 0 AND under-20-bar-high <= 3.0% (**AQE tag rule**) AND any of `was_squeezed`, `nr4_flag`, `nr7_flag`, `lens.coil` == "strong".
4. **PULLBACK / SUPPORT BOUNCE** if `pct_from_pivot` < 0 AND any of: `unr_status` in (MET, SETUP) or a `setups` grade named "undercut..." with status TRIGGERED/READY/WATCH; `entry` > `ma_20` with `ma_20_slope_5d_pct` > 0; `entry` > `ma_50`.
5. **OTHER** otherwise (0 names today).
- The **reclaim-day flag** (rule 4's first test) is also counted on its own; a breaking-out name keeps its breakout tag.
- The committee's volume line, 1.4x (CO: "on volume at least 1.4x normal", the would-clear line on most volume objections, e.g. BRK-B), is used only in the reason column, not in the tag.

### D. Alignment chart and read
| Figure | Value | Source |
|---|---|---|
| Advance mix (7) | 4 breaking out (ROKU, BRK-B, DIS, TMO), 1 pullback (FA), 2 extended (EW 6.1% past pivot; HNGE 20.9% past pivot and 72% over the 200-day) | tag rules on EX rows of CO ADVANCE tickers |
| Hold mix (5) | 2 breaking out (V, AJG), 3 extended (SN 5.1%, GEN 17.8%, SWK 13.3% past pivot) | same, CO HOLD-FOR-CONDITIONS |
| Elder / AQE / lens mix | 3 brk, 1 coil, 11 ext / 4 brk, 16 ext / 9 brk, 1 coil, 3 pull, 2 ext | tag rules |
| "pullback" lane 4 of 7 | ROKU, TMO, HNGE, FA | `CO[].lane` |
| lane meaning | MOMENTUM = opened STRENGTH or AQE_LEADER door; PULLBACK = all other admitted names | `P4.lanes_rule` |
| 3 carry a reclaim-day flag | ROKU, TMO, HNGE (`unr_status` MET) | EX |
| Triggers | 6 = `h1_close_above:bar_high`, 1 = `h1_close_above:pivot_high` (FA) | `CO[].trigger.word` |

### E. Objection themes (keyword rules on `CO[].objections[].objection`, case-insensitive regex; one objection can match several themes)
Scope: the 17 names with status AGREED / CONTESTED / DROPPED (NOT_SLATED names carry no objections); 50 objections on 16 names.
| Theme | Regex | Objections | Names |
|---|---|---|---|
| No volume test, or volume too light | `volume\|day_vol\|nobody bought` | 23 | 14 |
| Objects to a dip-and-reclaim ticket: wants the new-high break | `reclaim:ma_20\|reclaim of ma_20` | 20 | 4 (CART, HOG, TTEK, VLTO) |
| No countable base or tight pause | `no base\|countable base\|tight base\|base uncounted\|base unconfirmed\|gives no base\|out of a base\|tightest contraction\|tight, quiet pause` | 13 | 10 |
| Objects to buying the break: wants a pullback or pull-in first | `pullback into\|into value\|at value\|value reclaim\|first pullback\|pullback in progress\|adds on the test\|away from the creek\|in front of price\|under the rising average\|not above the prior high` | 10 | 8 |
| Strength or trend not confirmed | `trend template\|not a leader\|in-line\|stage 2\|only barely\|lh/ll` | 8 | 7 |
| Last bar reads as profit-taking or selling | `green going away\|profit-taking\|single-bar drop\|last-bar drop\|distribution` | 6 | 5 |
| Objects to waiting for a pull-in: buy the strength now | `pull-in step\|pull-in precondition\|no pull-in\|skip (a\|my) signal\|skips my signal` | 4 | 4 |
| Chasing: too far past the line | `late buy\|past pivot_high\|chasing\|climax\|70% above\|not on extension` | 4 | 4 |
| Sector or group blocked | `\bsector\b\|blocked\|headwind` | 0 | 0 |
- "24 push toward buying the break" = dip-ticket 20 + no-wait 4; "10 toward waiting for a pullback" = the wants-pullback theme.
- "4 of the 5 dropped names were dip-and-reclaim tickets" = CO status DROPPED (HOG, TTEK, VLTO, CART, MDT) whose `trigger.word` starts `reclaim:` (all but MDT).
- **Quotes:** for each theme, a whole sentence of a matching objection that itself matches the theme regex, contains no voice name or "Elder", has rule-code parentheses removed (`(C5, C6)` etc.), goes through the real page's `plain_words` + `plain_prose` (imported from pma_cards.py) plus four trigger-word swaps (`reclaim:ma_20`, `h1_close_above:bar_high`, `h1_close_above:pivot_high`, `close_above:bar_high` -> plain words), and then still contains no underscore, colon, "--", indicator shorthand (H1/W/D/EMA/HH-HL/LH-LL/Creek/coil/cmf/Template/ticket...), bare rule code or number list. The longest such sentence under 150 characters is shown; a sentence is used for one theme only. Themes with no surviving sentence say so (base, trend, profit-taking). Quoted from: volume EW, dip ticket HOG, wants pullback V, no wait AJG, chasing V.

### Not sourced / judgement calls
- The 4-daily-range stretch line and the 3%-of-high coil line are my AQE tag rules; the committee filed no number for either.
- Precedence (extended > breaking out > coiling > pullback) is my choice; it is why TMO and ROKU read "breaking out" although they also carry a reclaim-day flag and TMO's card calls it "a quiet back-up". Both facts are shown.
- The never-in-room "single fact" order is my choice (the committee's chase lines first, then sector, volume, stretch); it says "first fact that applies", never "the reason".
- The objection themes are keyword rules; an objection can count in more than one theme.
