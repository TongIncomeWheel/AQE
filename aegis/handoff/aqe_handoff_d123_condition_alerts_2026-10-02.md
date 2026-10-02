# AQE handoff: alerts that watch the committee's conditions (D123 / R21)

**From:** Aegis PMA (aegis-core 1.23.0). **To:** AQE live alerts (`src/alerts/`). **Date:** 2026-10-02.
**Status:** build in **shadow mode**. The new checks are logged only, and the existing PMA trigger emails carry on unchanged. The PM decides the switch at the 15 Oct review.

---

## 1. What changes and what doesn't

| | Today | After this build |
|---|---|---|
| What the committee decides | unchanged | unchanged. The verdict rule, lanes and Advance/Hold are untouched |
| What AQE reads | `pma_levels.json` `rows[].triggers[]`: single price lines | the same file, same path, same `triggers[]`, **plus** `rows[].conditions`: each analyst's own buy / confirm / wrong, in shared words with numbers attached |
| How volume is judged | `intraday.py`: a linear clock, which over-reads the open and under-reads lunchtime | **against this stock's own normal volume for this time of day** (20-day average per 15-minute slot) |
| VWAP | none live | **session VWAP from today's 1-hour candles** (live gate); AQE's `vwap_14d` stays a level |
| Emails | one per trigger touch | in shadow, unchanged. After the switch, **one per change of state**, e.g. "condition met", "failed", "chased" |

## 2. The contract (what PMA sends)

- **The file:** `aegis/output/pma/pma_levels.json`. It keeps the path, the `"schema": "pma_levels.v1"` and the `triggers[]`. It gains:
  - `"conditions_schema": "pma_conditions.v1"`, set when the run compiled conditions;
  - per ADVANCE, HOLD and HELD row, `row.conditions`:

```json
"conditions": {
  "shared": {
    "buy":     [{"w":"h1_close_above","level":62.15,"x":null,"seats":["minervini","detect-lens"],"when":"1H","plain":"an hourly candle closes above pivot_high 62.15"}],
    "confirm": [{"w":"vol_x_ge","level":null,"x":1.4,"seats":["minervini","detect-lens"],"when":"LIVE","plain":"volume at least 1.4x normal for the time of day"}],
    "no_shared_buy": false,
    "wait_zone": {"lo":58.99,"hi":60.57,"members":["ma_20","vwap_14d"]},
    "chase": {"word":"close_above:pivot_high+5pct","w":"close_above","levels":[65.26],"x":null,"when":"EOD","plain":"closes above pivot_high+5pct 65.26"}
  },
  "exits": [{"w":"close_below","value":62.15,"seats":["detect-lens","minervini"],"plain":"closes below 62.15"},
            {"w":"close_below","value":60.37,"seats":["livermore"],"plain":"closes below 60.37"}],
  "analysts": [{"seat":"livermore","vote":"SUPPORT","conviction":3,"counts":true,"lane":"BREAKOUT","tf":"EOD","non_price":null,
                "buy":[{"word":"close_above:high_52w_close","w":"close_above","when":"EOD","levels":[63.89],"x":null,"plain":"..."}],
                "confirm":[], "wrong":[{"word":"fade_atr_ge:1","w":"fade_atr_ge","when":"LIVE","levels":[],"x":1.0,"plain":"..."}],
                "wait":[], "chase":null}]
}
```

- **The words:** `aegis/contracts/condition_vocab.json`, pushed with this handoff. It is the **only** dictionary both sides use. If a word is not in it, AQE logs `UNKNOWN_WORD` and skips it; it never guesses.
- **Levels arrive as numbers,** already resolved by PMA. AQE never looks a level up again.
- **`counts`:** `false` marks an advisory supporter, one outside the lane that decides that name's verdict (R14). Show it, but don't count it in "N of M".

## 3. New data AQE needs

Only for names in today's `pma_levels.json`, about 50.

| Data | How | When | Calls |
|---|---|---|---|
| **15-min bars, today** | `FMPClient.get_intraday(ticker, "15min", from=today, to=today)` (already exists, `fmp_client.py:150`) | every 15-min cycle | ~50 per cycle, ~1,300 a day |
| **15-min bars, last 20 sessions** | same call, `from = today − 30 calendar days` | **once per morning**, first cycle | ~50 a day |
| SPY 15-min bars, today | same call | every cycle | 1 per cycle |

FMP Starter serves these (PMA tested `intraday-1-hour` and `-15-min` on 2026-10-01). The data is still 15-minute delayed, as today.

## 4. New module: `src/alerts/live_measures.py` (pure functions, unit-tested)

1. **`volume_profile(bars_20d) -> {slot: avg_volume}`.** One slot per 15 minutes on the 09:30 grid (26 slots). Use the average over the last 20 full sessions; drop half days. Cache it per ticker per day in `aegis/output/alerts/volume_profile/<date>.json` so it is built once.
2. **`vol_x(today_bars, profile) -> {so_far, last_slot}`:**
   - `so_far` = Σ today's volume through the last completed slot ÷ Σ the profile over the same slots.
   - `last_slot` = the last completed slot's volume ÷ its profile slot.
   - **This replaces the linear clock.** `vol_x_ge:1.4` is tested against `so_far`.
   - Evidence (NTAP, 4 weeks): the first hour carries ~21% of the day, each midday hour 8–12%, the last hour ~25%. At 10:30 a normal day is 0.2× the full-day average.
3. **`hourly(bars_15m) -> list of completed 1-hour candles`.** Roll the 15-min bars up on the 09:30 grid (09:30–10:30, …, 15:30–16:00). A candle counts only when **all** of its 15-minute bars are in.
4. **`session_vwap(hourly_candles) -> float`:**
   - Σ(typical × volume) ÷ Σ volume over today's completed hourly candles, where typical = (H+L+C)/3.
   - Not used as a gate until **2** candles are complete; before that, report it with `provisional: true`.
5. **`heat_row(today_bars, profile) -> [x per hour]`:** each completed hour's volume ÷ its normal hour, for the heatmap.
6. **`rs_today(quote, spy_quote) -> float`:** the stock's % change today minus SPY's.

## 5. The evaluator: `evaluate_conditions(row, live, now_et)` (pure)

Inputs: the row's `conditions`, plus `live` = quote, completed hourly candles, `vol_x`, session VWAP, `rs_today`, ATR (`row.atr_14d` or the export).

**Word semantics.** `condition_vocab.json` is the spec. In short:

| Word | True when |
|---|---|
| `close_above` / `close_below` L | **final cycle only (15:45 ET)**, on `price` as the provisional close. Confirmed next morning against the real close. Before 15:45: not evaluated |
| `h1_close_above` / `h1_close_below` L | the last completed hourly candle's close is above / below L |
| `trade_above` / `trade_below` L | `day_high ≥ L` / `day_low ≤ L`. **INFO only, never an email on its own** |
| `reclaim` L | `day_low < L` and the last hourly close is above L |
| `reject` L | `day_high > L` and the last hourly close is below L |
| `in_zone` L | `abs(price − L) ≤ 0.25 × ATR`, or `day_low ≤ L + 0.25 × ATR` |
| `vol_x_ge` x / `vol_x_le` x | `vol_x.so_far ≥ x` / `≤ x`. Not evaluated before the first slot completes |
| `above_vwap_s` | last hourly close above session VWAP (needs 2 or more candles) |
| `below_vwap_s` n | the last n hourly closes are all under session VWAP |
| `rs_today_gt_spy` | `rs_today > 0` |
| `fade_atr_ge` x | `(day_high − price) / ATR ≥ x` |
| `clv_ge` / `clv_le` x | final cycle: `(price − day_low)/(day_high − day_low)` vs x |
| `red_bar` | final cycle: `price < open` |
| `elder_*`, `ma_above`, `choch_bearish`, `age_ge` | **COB words.** PMA already judged them at the close. AQE reports them as given and does not re-evaluate them intraday |

Each word returns `TRUE`, `FALSE` or `NOT_YET` (data not ready, e.g. before the second hourly candle). **`NOT_YET` is never treated as `FALSE`.**

**Per name, per cycle, compute:**
- **`buy_met`:** every word in `shared.buy` **and** `shared.confirm` is TRUE.
  - If `no_shared_buy` is true, use each counting supporter's own buy + confirm, and report "k of n analysts' conditions met".
- **`lit`:** the counting supporters whose own buy + confirm are all TRUE now. The email shows it as "3 of 4".
- **`wrong_lit`:** the supporters any one of whose `wrong` words is TRUE now. A supporter in `wrong_lit` is removed from `lit`.
- **`chased`:** the `shared.chase` word is TRUE.
- **`exit_hit`:** the highest `exits[]` level crossed. This is a **daily close** for `close_below`. An hourly close below it is only a WARN.

## 6. State and alerts

Per name, keep a state in `aegis/output/alerts/pma_condition_state.json`, keyed `<run_date>:<ticker>` so carried rows keep their history.

| State | Enter when | Email after the switch (shadow: log only) |
|---|---|---|
| WATCHING | start of day | — |
| **CONDITION MET** | `buy_met` turns true (or a majority of counting supporters lit) | ACTION |
| **FAILED PUSH** | was CONDITION MET or traded through the shared buy level, then an hourly close back under it | WARN |
| **CHASED** | `chased` true | WARN |
| **ANALYST OUT** | a new supporter enters `wrong_lit` (e.g. Livermore's ≥ 1 ATR fade) | WARN |
| **EXIT LINE** | daily close below an `exits[]` level | ACTION (held) / WARN (shortlist) |

- **Change only:** an email goes out only on a **change** of state, and once per state per day.
- **What the email shows:** the plain words PMA sent (`plain`), the live numbers behind them, and the heatmap row. For example:

> **HPE · CONDITION MET** · 3 of 4 momentum analysts
> - Hour closed 64.20 above pivot 62.15 (Minervini, Detect-lens).
> - Volume 1.6× normal for 11:30.
> - Above today's VWAP 63.80.
> - Chase line 65.26.
> - Hourly volume vs normal: 2.1 · 1.4 · 1.1

- **Volume heatmap in the after-close digest:** one row per PMA name, one cell per hour (`heat_row`), coloured ≤0.7 / 0.7–1.3 / ≥1.3.

## 7. Shadow mode and logging (the 15 Oct review needs this)

- **The switch:** a config flag `PMA_CONDITIONS_MODE = "shadow"` (the default) or `"live"`. In `shadow`, nothing in §6 is emailed; the existing trigger path runs exactly as today.
- **The log:** every cycle, write one line per name to `aegis/output/alerts/condition_ledger/<date>.jsonl`:
  - `ts`, `ticker`, `state`;
  - the words, each with TRUE / FALSE / NOT_YET and its live value;
  - `vol_x`, session VWAP, `rs_today`, `lit`, `wrong_lit`;
  - the old trigger that fired, if any, at the same time.
- **The digest:** a daily summary file, `aegis/output/alerts/condition_ledger/<date>.summary.json`. PMA's scorecard reads it to grade "condition met" against "price touch" over the next close and the next 5 sessions.

## 8. Fixes to make at the same time

1. **`intraday.py` volume pace:** move it to `vol_x.so_far`. Keep the old linear figure in the ledger for two weeks for comparison.
2. **The denominator:** use the per-slot profile from §4.1 (built from the stock's own 15-minute bars), not the quote's 50-day/3-month `avg_volume`.
3. **`high_52w` is a closing high.** PMA now refuses a trade-through line pinned to yesterday's close. AQE should label `high_52w` as "52-week closing high" in any email text.

## 9. Tests AQE should add

- **Volume:** `vol_x` on a normal day reads about 1.0 at 10:30, 12:30 and 15:30; the linear clock does not.
- **Hourly candles:** a partial hourly candle is never used.
- **Session VWAP:** it is not a gate before the second candle.
- **The HPE 2026-09-30 bars** (they are in the PMA run folder). The result must be: above the 62.15 pivot every hour, but `above_vwap_s` FALSE in 6 of 7 hours, and `fade_atr_ge:1` almost true (a 0.90 ATR fade). So no CONDITION MET is emitted on a rule that requires `above_vwap_s`.
- **`NOT_YET`** never fires a state.
- **Shadow mode** sends zero new emails.
- **Back-compatibility:** a levels file without `conditions` behaves exactly as today.

---

**Guardrails, unchanged:** alerts only. Never place, change, cancel or size an order. The PM's broker stop is the level in force on every held name. Nothing observed intraday feeds back into a committee vote.
