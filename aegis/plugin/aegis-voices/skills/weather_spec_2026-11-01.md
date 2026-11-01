# Valen and Crown: the weather layer of the PMA

**What this is:** one reference for the two market-weather sources that feed the daily PMA. For each it covers the purpose, what it does, the AQE fields it reads, its guardrails, its writing style, and every place it shows up in the Committee Cards report and the CIO brief.
**Why it is needed:** neither has a working voice file that matches how it is used today.
- **Valen** never had a voice file. His rules exist only in PM rulings, AQE code and project notes.
- **Crown** has a voice card and a canon, but the PM stood him down as a voice on 30 Oct. His read now comes straight from AQE's file.

**As of:** 1 Nov 2026. Example figures are from the 29 Oct AQE files.
**Sources:** listed in §8. Every rule below is taken from those files. Nothing is invented.

---

## 1. Where they sit

```
AQE daily run (about 08:30–08:59 SGT)
  Crown steps            → aqe_crown_macro.json      (published reading copy, plain English first)
  Valen step             → aqe_valen_dashboard.json  (published)
  export build           → aqe_daily_export.json     (each row carries Valen setups and U&R)
        │
        ▼
PMA  GATHER   fetches all three. A missing file is a declared gap, never a neutral reading.
     RANK     reserves up to 3 seats for Valen undercut-and-rally reclaim names that no voice picked
     VOTE     VALEN block in the vote packet (context only, no levels)
     WRITE    brief-writer writes 12 short "Read:" paragraphs (cards_text.json → weather)
     REPORT   pma_cards.py render → Part 1 "Daily weather" (code fills every number)
```

| Role | Valen | Crown |
|---|---|---|
| Voice in the committee? | No. Never was. | **No.** Stood down on 30 Oct, along with Druckenmiller |
| Votes or nominates? | No | No |
| Where the PM sees it | Cards Part 1 blocks 1, 2, 5, 6, 7, the house setups line, a Valen row on every ADVANCE card, brief §1A | Cards Part 1 blocks 3, 3a to 3e, 4; brief §1 |
| Who writes the words | brief-writer, from the file | brief-writer, from the file (the Crown voice no longer files a form) |
| Who fills the numbers | `pma_cards.py`, never the writer | `pma_cards.py`, never the writer |

---

## 2. Crown: the macro regime

### 2.1 Purpose
Crown answers **what kind of market this is before anyone looks at a stock**. He reads positioning, breadth and regime before price, because price lags all three. His edge is knowing the market type before any risk is taken.

His worldview rests on four claims:
- Price lags. By the time a chart confirms a move, the positioning behind it is already in place.
- The index and the average stock often disagree, and the gap between them is information.
- Trend-fund and dealer flows are mechanical, so they can be anticipated.
- Volatility shows stress that the index hides.

### 2.2 Function: the order is the method
| Step | Instrument | Question |
|---|---|---|
| 1 | Heartbeat: equal-weight S&P ÷ cap-weight S&P (RSP/SPY) | Broadening or narrowing, and where in its 12-month range |
| 2 | **Gate:** confidence under 0.40 → **STOP** | A market he cannot read gets no call. That stop is a result, not a failure |
| 3 | Positioning: trend funds (replicated), CFTC speculators, dealer gamma | Who is in, and how crowded |
| 4 | Volatility: VIX, single-stock volatility (VIXEQ), the gap between them, implied correlation, curve shape | The real risk regime |
| 5 | Divergence: momentum vs price, cross-asset non-confirmation, positioning vs price | Where momentum is failing behind price |
| 6 | **Output:** one of 5 trade families + a size multiplier | The family the market permits |

**The five families** (hidden stress is checked first):
| Family | Fires when | Plain words |
|---|---|---|
| Hidden stress downside | Volatility gap elevated **and still widening** | Buy cheap index downside, small and tactical |
| Divergence pair short | Bearish divergence + narrowing + crowded trend funds | Short the stretched leader against the average stock |
| Mean-reversion premium | Positive gamma + VIX under 15 + broadening | Fade extremes, sell premium |
| Broadening carry | Broadening + mid-range + positive gamma + calm + clean trend | Own the average stock |
| Narrowing concentrated | Narrowing + trend funds risk-on + negative gamma | Stay with the leaders, keep risk defined |

**The states he names:**
| State | Plain words |
|---|---|
| Broadening | Own breadth, but check the range first: broadening into the top of its range is late, not early |
| Narrowing | A few names carry the index. Stay with leaders and keep risk defined |
| Unreadable | Stop |
| Tired wave | Regime at the edge of its own 12-month range. The most actionable read, because it points at the turn |
| Hidden stress | Volatility gap wide **and widening** |
| Stress draining | Gap wide but shrinking. Looks the same on a chart and means the opposite: buying downside now buys the end of the move |
| Crowded | Speculators at a percentile extreme, in the same direction price is already moving. Context, never timing |
| Fragile trend complex | About two-thirds or more of markets at a trend extreme. Cut size even if the bias looks clean |
| Knife-edge | Spot within about 1% of the dealer gamma flip. Must be checked explicitly every day; it is the read most often skipped |
| Non-confirmation | Count how many warnings agree. One is a straw, several aligned with breadth are a pile |
| Already priced | VIX 25 or higher: protection is already expensive, so a spike is not a fresh reason to act |

### 2.3 AQE data points: `aqe_crown_macro.json`
| Block | Fields used | 29 Oct example |
|---|---|---|
| `status`, `status_means` | OK / DEGRADED / EARLY_EXIT | OK, every input available |
| `read_me_first` | `headline`, `why[]`, `so_what`, `what_would_change_it[]`, `caveats[]` | "A broad market, calm on the surface but with single stocks moving very differently underneath." |
| `the_call` | `expression_family`, `match_quality`, `size_multiplier`, `how_the_size_was_reached`, `conditions_met/not_met`, `playbook` | Hidden stress downside, exact fit, 0.50× |
| `how_current` | `oldest_source`, `oldest_source_days_behind`, `volatility_as_of`, positioning date | Oldest source 27 Oct, 2 days behind |
| `readings.breadth` | `regime`, `position_in_12_month_range`, `days_in_this_regime`, `change_5d/20d/60d_pct`, `confidence`, `passed_the_gate` | Broadening, mid, 8 days, confidence 0.65 |
| `readings.positioning.trend_funds` | `bias`, `markets_read`, `share_at_an_extreme`, `size_dial`, `by_sector` | Neutral, 18 markets, 0% at an extreme, dial 1.00 |
| `readings.positioning.large_speculators` | `crowded_long[]`, `crowded_short[]`, `as_of` | Long NQ RTY ZF ZS ZT; short CL NG SI (CFTC to 20 Oct) |
| `readings.positioning.option_dealers` | `regime`, `detail.SPY/QQQ` (spot, gamma_flip, flip_distance_pct, call_wall, put_wall, **assumption**) | Negative; SPY 772.31 vs flip 773.51 (0.16%) is a **knife-edge** |
| `readings.volatility` | `vix`, `single_stock_vol`, `gap`, `gap_vs_history`, `gap_change_20d`, `state`, `implied_correlation`, `term_structure` | VIX 16.9, VIXEQ 41.7, gap 24.2 at the 85th percentile, rising, contango |
| `readings.divergence` | `warnings_lit`, `which[]` | 10 lit on individual markets, momentum (RSI) type |
| `scenario` | `leading`, `score_share_of_conditions`, `coverage`, `contested`, `runner_up`, `story`, `evidence_for`, `what_is_missing` | Disinflation goldilocks 83%, **contested** with dispersion regime |
| `key_levels[]` | `kind`, `what`, `now`, `level`, `distance_pct`, `if_it_breaks` | Breadth range, volatility bands, trend-fund flip lines, gamma flip and walls |
| `what_is_coming[]` | `date`, `event`, `what_it_tests` (macro + earnings) | Core PCE 29 Oct |
| `what_changed[]` | Moves since the last run that change what a PM does | Empty means nothing material changed |
| `limits[]` | Standing caveats | Contested scenarios; a share of conditions met is not a probability |

Valen's file also carries a short Crown summary (`crown_cockpit`: breadth range, trend-fund crowding, dispersion, divergence count, COT). Part 1 block 4 reads COT from there first.

### 2.4 Guardrails
| Rule | What it means in practice |
|---|---|
| Never sizes | Emits a multiplier on the PM's own risk per trade, capped at 1.15×. Tactical families **cap** rather than multiply. The arithmetic is always shown |
| Never names a ticker | A family, never a stock. The setup is someone else's job |
| Places nothing | Read-only |
| No probabilities | A scenario score is the **share of its conditions met**. It is never fitted, never backtested and has no base rate |
| The gate stops the run | Confidence under 0.40 → EARLY_EXIT. Downstream sections are empty because they never ran. Never read them as "quiet" |
| Freshness | The read is only as current as its oldest input. Stale-but-present counts as a failure. State the oldest source |
| Missing is refused, not zeroed | "Unavailable" ≠ "neutral". A gamma map without open interest is UNAVAILABLE, never flat |
| Assumptions ship as assumptions | The dealer side is a convention, not observed data. Say so on every gamma read |
| Proxies are labelled, never dropped | Most trend markets run on ETF proxies, so the flip levels are in fund units |
| Contested is not a call | When two stories fit, or the family and the raw breadth disagree, say "contested" and don't resolve it |
| A thin reading cannot lead | A scenario under 60% coverage cannot lead |
| Standalone | Reads nothing from the sector model (SRM), Macro Weather or Thematic RRG, and none of them reads Crown. The scenario layer is the one named merge point |

### 2.5 Writing style
- **Four blocks, in this order:** Headline (what kind of market, one sentence) · Why (4 to 6 reasons, each with its number) · So what (family and multiplier) · What would change it (**real levels**, e.g. "if natural gas trades below 2.98, trend funds start selling"). Never a sentiment.
- **No jargon without its meaning, no claim without its number.** "Breadth is weak" fails; so does a bare "0.328".
- Banned words in AQE's plain-English output: percentile, dispersion, gex, vixeq, heartbeat, flip_risk.
- **Percentile trap:** Crown writes "VIX lower than X% of the past two years", which means percentile 100 − X. Write "higher than 74% of days", never "26th percentile", and only call VIX quiet below the median.
- **The mechanical label is not the headline** (PM, 26 Aug: "ignore the label, and let crown's voice work out ... in plain actionable insight english"). Lead with the reasoned read. Show `the_call` as a traceable data point and say plainly how good the fit is.

### 2.6 What Crown feeds in the report
| Output | Block | What is rendered |
|---|---|---|
| Cards Part 1 | 3 · Crown macro layer | Headline, oldest source date |
| | 3a · Market heartbeat | Regime, gate passed/failed, days, 12-month range (low/now/high), 5/20/60-day change, its 20-day line, confidence |
| | 3b · Positioning | Trend-fund bias, size dial, share at an extreme, lean by sector, the 6 nearest flip lines |
| | 3c · Volatility | VIX, VIXEQ, gap vs its calm/elevated bands, 2-year percentile, 20-day change, implied correlation, curve |
| | 3d · Divergence | Market-level warnings (n of 8), count on individual markets, types firing |
| | 3e · Call and macro story | Family, fit, multiplier, conditions met/not met, leading story, whether contested, what would change it, the next 5 macro events with what each tests |
| | 4 · COT | Crowded long / crowded short in plain names, report date |
| | 2 · GEX light | SPY/QQQ spot, flip, gap to flip, put/call walls (shared with Valen's gamma block) |
| Brief | §1 Macro | Table of read · number · source; the family and size line; a table of what helps or hurts each held name |
| Cards words | `weather.heartbeat/positioning/volatility/divergence/call/cot` | One "Read:" paragraph each |

---

## 3. Valen: the VIV System weather, house setups and no-buy list

### 3.1 Purpose
Valen is the PM's target model for the daily report (PM, 23 Oct). His book is *The VIV System: 21 Building Blocks to Profitability* (v1.3, Sep 2026). AQE ports three parts of it:
- **Part 1, the weather:** check the market first. One word sets how hard to push today. It never picks the stock.
- **Part 3, the house:** five measured setups, graded per stock against his own checklists.
- **The no-buy list:** deal-breakers. One yes means no.

His order: stance first, then the headline, then the groups (where to hunt), then the charts. "Never before."

The PM asked for Valen to take real space in the report: "very little of Valen data available ... I want to see it take space" (23 Oct).

### 3.2 Function
| Piece | Rule in plain words |
|---|---|
| Stance | RISK ON / NEUTRAL / RISK OFF, plus one line on why. It changes on rules, "never on a feeling, and never on one session" |
| Trend regime | SPY daily buy (above the 10- and 20-day lines, 10 above 20), weekly buy (same test on weekly bars), above a rising 5-day. All yes = UPTREND, all no = DOWNTREND, mixed = **CHOP** ("chop is where breakouts get sold") |
| Extension | SPY/QQQ distance from the 50-day in daily ranges (ATRs; about 6 is the extreme for an index). VIX/VIX3M: under 0.82 calm, over 1.00 stress |
| Checklist | Net new highs (8-day vs 20-day), today's 4% count, 5-day count ≥ 1.00, month 25% count. "More yes, more size." The net-new-highs row alone decides how open trades are managed |
| Instruments | 5- and 10-day 4% ratios (0.50 / 1.00 / 2.00 bands), T2108 (stocks above their 40-day: under 20 washed out, over 80 overheated, above 50 for risk-on), big movers |
| What would change it | To positive: T2108 clears 50, monthly risers clear 350, 5-day count above 1.00. To negative: 5-day count under 0.70 |
| Groups and rotation | Themes ranked on 1 week and 1 month; "thrust" = week minus month; % off the 52-week high. "Leading" = strong and near highs. "Off the floor" = 15–25% below highs, a lesser bounce trade |
| Five setups | VCP · high tight flag (only) · undercut-and-rally (U&R) · episodic pivot plus delayed EP · parabolic as a **long-only risk warning** |
| Other U&R supports | Gaps, trendlines, EMA9/EMA21 and the swing low (PM, 8 Oct: "keep it simple") |
| No-buy list | Stretched (ATR-extended), earnings within 5 sessions, below the 200-day, and so on. Flags per name |

**U&R in the export (PM, 12 Oct):** `MET` means a support was undercut by a shallow dip and the last completed day closed back above it (the reclaim day). `SETUP` means it was undercut within 3 sessions and is still under. `NA` means too little history, never a silent NO. The live alert uses the same rules, so the column and the alert cards cannot disagree.

### 3.3 AQE data points
**`aqe_valen_dashboard.json`** (Valen step in the daily run):
| Block | Fields | 29 Oct example |
|---|---|---|
| `read_me_first` | `headline`, `because[]`, `so_what` (handbook doctrine), `watch_for[]`, `caveats`, `as_of` | NEUTRAL; "Mixed signals — half size, best setups only, take profit sooner" |
| `stance` | `word`, `status`, `reason` | NEUTRAL, OK |
| `regime` | UPTREND / DOWNTREND / CHOP | CHOP |
| `trend[]` | SPY/QQQ `last_price`, `daily_buy_signal`, `weekly_buy_signal`, `above_rising_5d` | SPY: daily no, weekly yes, 5-day no |
| `extension[]` | ATR multiples, VIX/VIX3M, `flag` | SPY 0.67, QQQ 0.02, VIX/VIX3M 0.91 |
| `breadth[]` | `label`, `section` (checklist/instrument), `kind`, `value`, `display` | T2108 42.5; 5-day 4% count 2.24 |
| `gex` | SPY `regime`, `light`, `flip`, `call_wall`, `put_wall`, `flip_distance_pct`, `commentary` | Flip 773.51, walls 780 / 750 |
| `crown_cockpit` | Crown's breadth range, trend-fund crowding, dispersion, divergence, COT | see §2.3 |
| `history[]` | `now`, `5d_ago`, `1mo_ago` for stance, regime and key readings | Stance NEUTRAL, 5 days ago RISK_OFF |
| `neighbourhood[]` | Plain lines on where leadership is | "On both week and month lists: Cybersecurity, Space eVTOL, Defense Tech, Oil Services, Homebuilders" |
| `theme_leaders[]`, `rotation[]` | `since_open_pct`, `ret_1w_pct`, `ret_1m_pct`, `thrust`, `pct_off_52w_high`, `rotation_state`, `rrg_quadrant` | 35 baskets |
| `selection` | `relative_strength[]`, `funnel`, `no_buy_list[]` (ticker + flags) | APLE: 4.2 ATR extended; earnings in 5 sessions |
| `house` | `setups[]` per ticker (`grades[]`: setup, status, pivot, stop, `checks[]` with rule / value / PASS-FAIL / hard), `computed`, `graded`, `in_theme` | VRT: episodic pivot TRIGGERED, 9 of 9 checks |
| `execution` | `entries[]`, `stop_breaches[]` | Pattern triggers per name |
| `management` | `held_facts[]` (entry, live price, R multiple, days held), `streak` | MP 300 @ 53.00, last 41.06 |

**On each `daily_list` / `held_positions` row of the export:** `setups[]`, `unr_status`, `unr_note`, `unr_as_of`, `unr_level`. Top level: `unr_summary`, which lists the MET and SETUP names on the Longlist and Elder list.

### 3.4 Guardrails
| Rule | What it means in practice |
|---|---|
| Stance is a reading, never a size | AQE exports the word only. The handbook's sizing line is printed as **quoted doctrine**, "not an Aegis rule. AQE makes no sizing decision" |
| Sizing stays the PM's | PM, 23 Oct: "ok to follow his sizing rule, anyway in practice I normally follow R value". 1R = $620 (PM, 27 Oct) |
| Population is stated | Breadth is measured on AQE's curated panel (about 800 stocks), not the whole market. Say so on every breadth read |
| Whole-market thresholds | The "350 monthly risers" flip rule is a whole-market number and is unreachable on AQE's list. Never cite it as reachable |
| No levels to the voices | The vote packet carries setup **status and checklist pass counts** only. Pivots and stops never reach a voice |
| Missing = declared gap | "Valen dashboard not served this run — declared gap, not a neutral reading." This applies to the vote packet and the Cards alike |
| U&R is one setup, not his entry rule | Show it only when it happened (MET or forming), in words. Say nothing on NO or NA (PM, 23 Oct) |
| Thresholds already met are dropped | "What would change the stance" hides items whose threshold is already cleared |
| Parabolic = warning only | Long-only risk warning, never a short call |
| Reserved seats | Up to 3 names that are U&R MET on the reclaim day and on the Longlist or Elder list, with no voice nomination, are seated and voted. Say "in the room on a reserved reclaim seat; no voice nominated it" |
| Data is measured, not tuned | Handbook thresholds are transcribed with page cites. AQE's own measurements are labelled as AQE's |

### 3.5 Writing style
Valen's own voice in the handbook is first-person, short and rule-led: "If the market check is not green, do not push." "One yes means no." The report keeps that plainness.
- Quote the handbook as **doctrine**. Never present it as an Aegis rule.
- Use his words: stance, chop, in-theme, leading vs off the floor, reclaim day, washed out / overheated.
- Every figure comes with what it means for a momentum book today ("Read: ...").
- Example from the file: "SPY's daily, weekly and 5-day trend checks disagree with each other — that is chop, and chop is where breakouts get sold."
- Never write "Valen U&R NO". Silence is the correct output.

### 3.6 What Valen feeds in the report
| Output | Block | What is rendered |
|---|---|---|
| Cards header | `stance_pill` | e.g. "NEUTRAL · HALF SIZE" (stance + doctrine, short) |
| Cards Part 1 | 1 · Situational awareness and stance | Stance and trend pills, SPY/QQQ signal table, stretch table, VIX curve explainer, quoted doctrine |
| | 2 · GEX light | Shared with Crown's dealer detail |
| | 5 · Direction of the wind | Gauge bars (T2108, 5- and 10-day 4% counts, net new highs), checklist pass/fail, instruments |
| | 6 · Weather turning | Now vs 5 days vs 1 month; what would change the stance |
| | 7 · Theme leaders and rotation | Leaders (leading / off the floor), the 6 sharpest turns by thrust, neighbourhood lines |
| | 8 · Strong stocks riding a group turn | Built from the export's sector and theme grades. Information only |
| | House setups across the list | Counts by setup and status; "None is TRIGGERED or READY" when true |
| Each ADVANCE card | Valen row | Setups with status, U&R words, ⛔ no-buy flag |
| Vote packet | VALEN block | Weather line, trend, extension, breadth, gamma, leadership; per name setups (n of m checks passed), U&R and no-buy flags. **No levels** |
| Brief | §1A Valen | Stance now / 5 days / 1 month, trend, extension and breadth table, gamma, themes, watch-for, house-setup counts |
| Brief §0 | Two columns | "Valen setup", "U&R", plus ⛔ for any ADVANCE or HOLD on the no-buy list |
| Rank | Reserved seats | Up to 3 U&R reclaim names |

---

## 4. The 12 weather paragraphs: who supplies each

The brief-writer writes **one short paragraph per key** in `cards_text.json → weather`. The renderer **refuses** to publish if any key is missing while the Valen file is served. Quote only figures that are in the files, and never type a level.

| Key | Source | What the paragraph must say |
|---|---|---|
| stance | Valen | Stance and its 5-day / 1-month change, SPY/QQQ daily and weekly signals, stretch vs the 50-day, VIX/VIX3M |
| gex | Valen `gex` + Crown dealers | The light, distance to the flip, put/call walls, what a break of each means |
| heartbeat | Crown breadth | Regime, days in it, 5/20/60-day change, place in the 12-month range, the 20-day line that would end it |
| positioning | Crown trend funds | Bias, crowding, size dial, sector lean, the nearest flip lines and how far away they are |
| volatility | Crown volatility | VIX and its 2-year standing (100 − X), VIXEQ, the gap and its band, direction, implied correlation, curve |
| divergence | Crown + cockpit | What is lit at market level and on individual markets; whether breadth agrees |
| call | Crown `the_call` + `scenario` | Family and fit, failed conditions, leading story and whether contested, next scheduled test |
| cot | Crown / cockpit | Crowded long and short in plain names, which matter for equities, the report's age |
| checklist | Valen breadth | Which items pass, the weak instruments, stated as AQE-list numbers |
| turning | Valen history + watch_for | Now vs 5 days vs 1 month; what would change the stance; no unreachable whole-market thresholds |
| themes | Valen theme leaders / rotation | True leaders vs bounces off the floor vs violent turns in broken groups |
| groups | Export sector and theme grades | Turning groups and their strongest names, which are already leading, "a place to look, not a list to buy" |

The `market.weather` lines (Crown, Valen, gamma) end with **"Our read:"**, the one-line synthesis.

---

## 5. Shared writing rules (cio-voice + brief-writer)

1. **So-what rule:** every figure must say what it means and what it changes for the book today. A number that changes no decision is not written.
2. **Executive form:** tables and one-line statements. No paragraph longer than two sentences.
3. **Plain English:** "buy above 158.85", never "line" for a price. Spell out acronyms on first use.
4. **Never cite a ruling or section by number.** Say what the rule does.
5. **The uncomfortable read gets written.** If the weather argues against a name or the book, say so.
6. **Numbers come from code.** The writer never types a level except when quoting one from a run file.
7. **Degraded mode:** a missing input is a one-line declared gap. The report always lands.
8. Footer: "DRAFT — PM approval required. Nothing is staged, nothing is armed."

---

## 6. Conflicts and gaps found while writing this

| # | Item | Effect | Owner |
|---|---|---|---|
| 1 | The run map still has a MACRO step that spawns Crown and Druckenmiller, and the vote packet still reads their forms | Conflicts with the 30 Oct stand-down; costs two spawns | PMA code |
| 2 | The 26 Aug rule says Crown's **voice** read leads §1. With the voice stood down, the read now comes from `read_me_first` | §1 needs restating: lead with `read_me_first`, show `the_call` with its fit | PM confirm |
| 3 | Crown's charter says dealer positioning is off in the daily run; the 29 Oct file shows it on (`available: true`) | The charter caveat is stale | Canon text |
| 4 | Crown's VIX sentence inverts the percentile ("lower than 26%" = 74th percentile) | Has misled one brief already | AQE `explain.py` |
| 5 | Valen breadth is the curated panel only; T2108, % above 20/50/200 and the 25% counts are whole-market in his book | Stance can never reach the "350 risers" flip | AQE (breadth substrate, PM decision pending) |
| 6 | Missing Valen items: manage note driven by net new highs, three-month 25% count, last-5-trades check, % above 20/50/200, NAAIM, per-position trim/trail rows, the three risk limits, drawdown ladder | Part 1 is not yet his full card | AQE / PMA backlog |
| 7 | The VALEN parabolic / no-buy text sits in every vote row and was cited in about 26% of opposes | Proposed: move it to a risk block beside the verdict | Change package (PM ruling) |
| 8 | Sizing: Valen ¼–⅓% per trade, 1R = $620, AQE CLAUDE.md still says 3% | Three figures in circulation | PM: name one, then change all places together |
| 9 | Valen has no single owner or step in the job register | Weather can slip without anyone noticing | Operating model |

---

## 7. Paste-ready brief for any harness (Claude, Claude Code, Grok)

> You write the Daily Weather for the Aegis PMA from three files: `aqe_crown_macro.json`, `aqe_valen_dashboard.json` and `aqe_daily_export.json`. Crown and Valen are **reading sources, not voices**: they never vote, nominate, size or name a trade.
> Crown: read in his order (breadth → gate → positioning → volatility → divergence → family). If the gate failed, say the market is unreadable and stop. State the oldest source date. Report the family and multiplier as a multiplier on the PM's own risk, never a size. Call two fitting stories contested. Check the gamma-flip distance against about 1% and name a knife-edge.
> Valen: give the stance word first and quote his doctrine as the handbook's, not an Aegis rule. Say every breadth number is on AQE's ~800-stock panel. Mention U&R only when MET or forming. Flag no-buy names with ⛔. Never pass a Valen pivot or stop to a voice.
> For each of the 12 weather keys write one or two sentences: the figure, then what it means for a momentum book today. Plain English, no jargon without its meaning, no claim without its number, no ruling numbers, no levels typed by hand. A missing file is a declared gap, never a neutral reading.

---

## 8. Source index

| File | What it holds |
|---|---|
| `aegis-voices/agents/voice-crown.md` | Crown operating card (recognisers, output shape) |
| `aegis-voices/canon/crown/CROWN_VOICE_CHARTER.md`, `canon.lock.yaml` | Crown's 39 principles, 11 recognisers, 4 refusals, deviations, limits |
| `aegis-core/agents/brief-writer.md` | cards_text schema, the 12 weather keys, brief §1 and §1A |
| `aegis-core/tools/pma_cards.py` | Part 1 rendering (`_weather_part1`, `_valen_card`, `_wind_gauges`, `_group_turns`), refusal rules |
| `aegis-core/tools/pma_pipeline.py` | Vote-packet VALEN block (`_valen_lines`), Crown packet, reserved U&R seats |
| `aegis-core/skills/pma/RUN.yaml`, `RULINGS.yaml` | GATHER fetch, MACRO step, REPORT reads; reserved seats; Part 1 layout; group-turn section |
| AQE `docs/AQE_VALEN_DASHBOARD_PROPOSAL.md`, `AQE_VALEN_HOUSE_SETUPS_PROPOSAL.md` | Valen port, stance-not-size and population rulings, five setups |
| AQE `docs/AQE_CROWN_*.md`, `src/macro/crown/`, `src/valen/` | Build docs and code |
| Project `valen_playbook_map_2026-10-23.md` | The 21 building blocks with page cites, gap table |
| Project `pma_crown_render_rule_2026-08-26.md` | Crown voice read leads, the label is demoted |
| Project `DECISIONS_2026-10-30.md` | Crown and Druckenmiller stood down; weather comes from the AQE files |
| AQE output `aqe_crown_macro.json`, `aqe_valen_dashboard.json` (29 Oct) | Live field shapes and example figures |
