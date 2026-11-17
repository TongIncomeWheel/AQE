# Valen entry layer (PM 2026-11-17)

Source: the Valen Setups and Theme Leaders requirements draft (artifact version 1794796198-ad95, items B1.2, B1.3, B1.6, B3.4, B4.4, C7, C8). AQE stays data-only: every item below is a fact or a boolean. Nothing sizes a trade, nothing blocks an alert, nothing places an order.

## What is built (entry layer, PR 1)

| Item | Where | What it says |
|---|---|---|
| Stop fit (DAY-1 / ALT-3) | `src/valen/entry.py` `stop_fit`; daily export column `stop_fit` on every `daily_list` and `held_positions` row | Entry = last close, stop = one tick under the last bar's low, `atr_multiple` = (entry - stop) / ATR14, `lod_dist_atr`, `within_cap` (cap 1 ATR, Valen: "too far? skip"), `fit` GOOD (LoD distance 0.70 or less) / OK / TOO_FAR / NA |
| Stop fit live | `src/alerts/live_entry.py` `build`; one "Entry check:" line on a U&R card | Same arithmetic on spot and the live low of day |
| Volume pass/fail (ALT-2) | `live_entry.volume_gate` | Share of a normal day's volume (20-day profile) at Valen's two marks, 20% by 09:35 and 40% by 10:00. Read at the first completed 15-minute bar at or after each mark (09:45, 10:00). No profile = UNKNOWN, never a pass |
| 30-minute pivot (ALT-4) | `live_entry.pivot_30m` | After a 30-minute candle undercuts the daily level, the first green 30-minute candle sets the pivot (its high) and the stop (its low minus a tick); TRIGGERED when a later bar breaks the pivot |
| Opening-range break (ALT-1) | `live_entry.orb`, `ready_pivot` | **SHADOW MODE.** For names Daily marks READY (VCP, high tight flag, episodic pivot): state ORB_BREAK = closes above the opening-range high AND above the daily pivot AND the volume gate passes. Written to the condition ledger line as `shadow_entry`; never on a card, never in an email, until the PM says go |

Thresholds live in `src/valen/spec.py` (`ENTRY_*`), one place, never tuned.

## Stated limits

- FMP's intraday feed here is 15-minute and delayed; Valen's charts are 1 and 5 minute. The opening range is the opening 15 minutes (Valen: 5), the 09:35 mark is read at the 09:45 bar, 30-minute candles are exact pairs of 15-minute bars. Every readout carries this.
- Valen's full intraday volume schedule is truncated on the captured page, so only the two printed marks are implemented; none is guessed.
- The card line is only printed on U&R cards (an armed name). The U&R lifecycle emails are still off by default (`CONDITION_UNR_ENABLED`, PM 2026-11-04) and alerts remain paused: this build changes no email behaviour.

## Out of scope (PM 2026-11-17)

DAY-6 letter grade, DAY-7 Momentum Breakout, ALT-6, ALT-7.

## Defaults I chose for the draft's open questions (PM may overrule)

EP stop cap: Daily `stop_fit` uses the 1.0 ATR cap for every row; the existing EP grade keeps its own HB_EP_STOP_MAX_ATR = 1.5 in the `setups` block (the draft leaves 1.0 vs 1.5 unsettled; I left both constants as they are).

Q3-Q5 belong to the theme layer, which is the next PR; defaults stated then. Entry-layer questions answered here: the stop cap is the handbook's 1.0 ATR (the Grader's 1-1.5x ADR is a different measure and not used); the LoD preference is 0.70 (outer edge of Valen's "60 to 70%").
