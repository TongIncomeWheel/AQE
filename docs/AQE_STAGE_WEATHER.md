# Stage Weather — the four-stage market cycle

**Status:** Phase 1 built 2026-11-10 on branch `claude/intelligent-hopper-m78oal`, not yet on `main`.
The `IMPL_*` measurement thresholds need **PM sign-off** before merge (see §6).

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
- **No `stage` column on `daily_list` yet.** That changes the export schema (`_REQUIRED_FIELDS`, the field glossary,
  voice packets); it is Phase 2 and needs a PM call.

## 6. Open decisions for the PM

1. **Sign off the `IMPL_*` numbers** in `src/stages/spec.py`: flat band ±0.5% over 4 weeks, 2-week confirmation,
   ±3-pt breadth band. They were chosen once and documented, not fitted.
2. **Phase 2:** add `stage` / `stage_candidate` / `rs_mansfield` to every `daily_list` + `held_positions` row
   (the Minervini seat already proxies Stage 2 with the Trend Template; this makes it explicit).
3. **Committee wiring:** the data-steward fetches `aqe_stage_weather.json` beside the other macro artifacts
   (it is already published to `aegis/output`); whether a seat reads it is the committee's design call.
4. **Whole-market breadth:** run the same classifier over `ma_panel.parquet` (~2000 names, VALEN breadth's source)
   for a true market Stage 2 share. This needs weekly bars from that panel.

## 7. First real read (SPY/QQQ from FMP, session 2026-11-09)

- **SPY: Stage 2 (Advancing) since 2026-04-24, 29 weeks.** The last completed week closed 2.1% *below* a still-rising
  30-week average (750.74), so it reads **Stage 3, unconfirmed**. The forming week has bounced back to a Stage 2 read.
- **QQQ: Stage 3 (Topping), confirmed 2026-10-30**, 7.5% under its 30-week average, RS against SPY −3.5.
- **History reconstructed:** Stage 3 Mar-2025 → Stage 4 Apr-2025 → Stage 1 May-2025 → Stage 2 Jun/Aug-2025 → Stage 3 Mar-2026 → Stage 2 May-2026.
