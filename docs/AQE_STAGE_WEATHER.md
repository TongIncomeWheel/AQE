# Stage Weather — the four-stage market cycle

**Status:** built 2026-11-10 on branch `claude/intelligent-hopper-m78oal`, not yet on `main`.
Phase 1 = market / sector / breadth artifact. Phase 2 (same day, PM: "show market, sector and ticker level") =
ticker-level columns on every export row + the committee canon's own tests. The `IMPL_*` thresholds need
**PM sign-off** before merge (§6).

The vocabulary is the committee's own: Minervini canon C2 is this same four-stage cycle, O'Neil C2 is the
market-top count, Wyckoff's accumulation/distribution are Stages 1 and 3. AQE's job is the parameters, the
compute and the reporting; the voices interpret.

## 1. What it is

A weather layer that answers one question at three levels: **which stage of the cycle are we in?**

| Stage | Weinstein | Market-cycle word (Wyckoff / Schwab) | What the chart shows |
|---|---|---|---|
| 1 | Basing | Accumulation | Price chops around a flat 30-week average after a fall |
| 2 | Advancing | Mark-up | Price above a **rising** 30-week average |
| 3 | Topping | Distribution | The average rolls flat after a rise; price chops around it |
| 4 | Declining | Mark-down | Price below a **falling** 30-week average |

Levels read, in order:
1. **Market**: SPY (leads) and QQQ.
2. **Sectors**: the 11 GICS ETFs (`srm.GICS_ETFS`), each with Mansfield RS against SPY.
3. **Breadth**: the share of every single name on AQE's weekly panel in each stage, now vs 1 and 4 weeks ago.
4. **Book**: the stage of every held position, plus the daily_list names changing stage this week.

Source: Stan Weinstein, *Secrets for Profiting in Bull and Bear Markets* (1988), ch. 2. The PM's reference, Schwab's
"Four Stages of Stock Market Cycles", summarises the same model. Schwab's site blocks automated reads, so its text
was **not** transcribed; nothing here claims to come from it.

## 2. The rule (`src/stages/classify.py`)

Every call is made on **completed weekly bars** (`panel_weekly.parquet`, the same panel every engine reads):

```
close > MA30w  and  MA30w slope (4 wk) > +0.5%   -> Stage 2 reading
close < MA30w  and  MA30w slope (4 wk) < -0.5%   -> Stage 4 reading
anything else                                    -> transitional:
                                                    Stage 3 if it follows 2 or 3,
                                                    Stage 1 if it follows 4 or 1
```

- **Confirmation.** A new stage needs **2 consecutive completed weeks**. One week is shown as `candidate`
  (the warning), never as the stage.
- **The forming week** (any mid-week run) is excluded from the call and reported as `candidate_forming` only.
- **Cold start.** A series that begins inside a range has no prior trend, so the 52-week range position seeds it
  (top half = 3, bottom half = 1) and the row carries `seeded: true` until the first real transition.
  With ~5 years of panel history this only touches names listed recently.
- **NA, never a guess.** A name needs 34 completed weeks or it is `status: NA` with the reason.
- **Evidence only, never inputs.** `rs_mansfield` / `rs_rising` (ratio to SPY vs its own 52-week average),
  `updown_volume_ratio` (avg up-week volume ÷ avg down-week volume over 10 weeks), `range_pos_52w`, `pct_from_ma30w`.
  If RS moved the stage, the stage would stop being Weinstein's and nobody could tell which fact produced it.

## 2b. Parameters: three sources, three prefixes (`src/stages/spec.py`)

| Prefix | Source | Values |
|---|---|---|
| `WS_*` | Weinstein | 30-week MA, 52-week Mansfield RS line |
| `CANON_*` | the committee's locked canon (`aegis/canon/*/canon.lock.yaml`) | Minervini C2: Stage 2 confirmed only ≥25% off the 52-week low. Minervini C3: Trend Template, 8 criteria, all-or-nothing (30% off low, within 25% of high, RS ≥70). O'Neil C2: distribution days, 25 sessions, ≥4 = top signal |
| `IMPL_*` | AQE's measurement where the source gives words, not numbers | ±0.5% flat band, 2-week confirmation, 200-day "rising a month" = above its level 21 sessions ago, ±3-pt breadth band |

## 2c. Ticker level (`src/stages/ticker.py`, stamped in the export build)

Every `daily_list` + `held_positions` row (and every Report B universe row) carries:

| Field | Meaning |
|---|---|
| `stage` / `stage_name` | confirmed Weinstein stage (null = too little weekly history, reason in `stage_detail.reason`) |
| `stage_candidate` | what the latest data reads; differs from `stage` = a change in progress |
| `stage_weeks` | weeks in the current stage |
| `stage_transition` | set only in the confirming week (BREAKOUT, TOPPING, BREAKDOWN, BASING, …) |
| `trend_template` | Minervini C3: PASS / FAIL / NA (an input missing → NA, never a pass by omission) |
| `trend_template_met` | criteria passed, 0-8 |
| `stage2_confirmed` | Minervini C2: Stage 2 **and** ≥25% off the 52-week low |
| `stage_detail` | everything behind those: MA30w + slope, Mansfield RS, up/down volume, the sector ETF's stage, the market stage, every Trend Template criterion |

The Trend Template reads the row's **own** `entry`, `ma_50/150/200`, `high_52w`, `low_52w`, `rs_rank_pct`, so the
checklist shows the numbers the row shows. Criterion 3 (200-day rising a month) is computed from the daily panel,
both ends from the same series. Criterion 8 uses `rs_rank_pct` as AQE's stand-in for IBD RS and says so (`rs_basis`).

Top level: `stage_market` (SPY/QQQ stage + distribution days, 11 sectors, breadth, headline) and `stage_status`
(live/error, unreadable names, counts by stage, Trend Template passes, names that changed stage). `summary` gains
`stage_status`, `market_stage`, `stage_2_count`, `trend_template_pass_count`. Scanner shows the six flat columns
next to the list flags.

## 3. Market read (categorical, no score)

`market_read.stage` = SPY's confirmed stage. `breadth_agreement` compares it with the single-name breadth:

| SPY stage | Breadth vs 4 weeks ago | Read |
|---|---|---|
| 2 | Stage 2 share falling **or** Stage 4 share rising (±3 pts band) | `NARROWING`: index carried by fewer names |
| 2 | otherwise | `CONFIRMS` |
| 3 / 4 | Stage 2 share rising **or** Stage 4 share falling | `IMPROVING_UNDERNEATH` |
| 1 | Stage 2 share rising | `IMPROVING_UNDERNEATH` |
| any | breadth unavailable | `UNTESTED` |

`change_in_progress` is true when SPY's latest completed week or the forming week reads a different stage.

## 4. Outputs

| File | Where | Contents |
|---|---|---|
| `output/stage_weather.json` | local + Daily Persist | full read incl. `by_ticker` (every panel name) |
| `output/aqe_stage_weather.json` | GitHub `aegis/output` (Step 8a-2) + Daily Persist | `read_me_first` plain English, then market / sectors / breadth / held / changes |

Pipeline: **Step 8a-1c**, after Step 8 (so held/daily_list are this run's) and before the GitHub publish.
Wrapped like Crown/VALEN: a failure prints `[WARN]` and never takes the export down.
Loud, never silent: no weekly panel → `status: UNAVAILABLE`; unreadable export → `held_status` /
`daily_list_status: UNAVAILABLE - …`; a held name with no panel history → its row is `NA` with the reason, not dropped.

Page: **Stage Weather** (`src/ui/pages/9_Stage_Weather.py`), plain tables, one-click copy for AIC.

## 5. What it deliberately does NOT do

- **No gate, no size, no disposition.** It is a reading, the same category as VALEN's `regime`. The
  `so_what` lines are Weinstein's doctrine, quoted as doctrine.
- **Not the whole US market.** Breadth is AQE's own panel (`population: aqe_panel_equities`, ~800 names incl.
  basket constituents and held names), labelled as such.
- **Standalone.** Reads nothing from VALEN / Crown / SRM and feeds nothing to them (the Crown rule), so the
  overlap (VALEN 10/20-day trend, SRM sector grades) stays measurable before anyone merges them.
- **Not a `_REQUIRED_FIELDS` key.** If the stamp fails the export still ships; `stage_status: error` says nothing
  was read. Voice packets don't carry the columns yet (§6.3).

## 6. Open decisions for the PM

1. **Sign off the `IMPL_*` numbers** in `src/stages/spec.py`: flat band ±0.5% over 4 weeks, 2-week confirmation,
   ±3-pt breadth band. They were chosen once and documented, not fitted.
2. ~~Phase 2: ticker-level columns~~ — built (§2c).
3. **Committee wiring:** the data-steward fetches `aqe_stage_weather.json` beside the other macro artifacts
   (it is already published to `aegis/output`); whether a seat reads it is the committee's design call.
4. **Whole-market breadth:** run the same classifier over `ma_panel.parquet` (~2000 names, VALEN breadth's source)
   for a true market Stage 2 share. This needs weekly bars from that panel.

## 7. First real read (SPY/QQQ from FMP, session 2026-11-09)

- **SPY: Stage 2 (Advancing) since 2026-04-24, 29 weeks.** The last completed week closed 2.1% *below* a still-rising
  30-week average (750.74), so it reads **Stage 3, unconfirmed**. The forming week has bounced back to a Stage 2 read.
- **QQQ: Stage 3 (Topping), confirmed 2026-10-30**, 7.5% under its 30-week average, RS against SPY −3.5.
- **History reconstructed:** Stage 3 Mar-2025 → Stage 4 Apr-2025 → Stage 1 May-2025 → Stage 2 Jun/Aug-2025 → Stage 3 Mar-2026 → Stage 2 May-2026.

## 8. First production read (Daily Persist snapshot, export 2026-11-10, panel through 2026-11-09)

- **Market:** SPY Stage 2 with a Stage 3 read pending; QQQ Stage 3. **Distribution days: SPY 8, QQQ 9 in 25 sessions**
  (canon top signal = 4). Using IBD's usual 0.2% minimum decline still gives 7 and 9, so the count is not inflated by flat days.
- **Sectors:** Stage 2 = XLB, XLE, XLF, XLP, XLV · Stage 3 = XLI, XLK, XLRE · Stage 1 = XLY · Stage 4 = XLC, XLU.
- **Breadth (827 names):** Stage 2 40.3% (37.2% four weeks ago), Stage 4 23.1% (34.0%). The decline is
  clearing underneath while the index tops: more names basing (Stage 1 7.3% → 14.0%).
- **Daily list (286):** Stage 1 51 · Stage 2 127 · Stage 3 49 · Stage 4 58 · 1 unreadable (WSE, short history).
  Trend Template PASS 66, Stage 2 confirmed (C2) 117. **Longlist: 112 of 223 in Stage 2, 45 in Stage 4**;
  Elder: 74 of 182 in Stage 2, 41 in Stage 4. 42 names confirmed a stage change this week.
- Held book was empty in that snapshot, so held rows were exercised in tests only.
- Timing: the stamp adds ~7 s to the export build.
