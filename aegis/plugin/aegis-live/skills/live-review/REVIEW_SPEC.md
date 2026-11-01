# 30-minute executive review: standing procedure

PM request 2026-10-23: a review every 30 minutes during the US session, executive length, working from the
day's market action plan (Part 1 Daily Weather) and the ticker action plans (the cards / `pma_levels.json`).
READ-ONLY. Place nothing, size nothing. Any order goes only through the Tiger preview and the PM's explicit "confirm".

> **Path note for a new harness:** this spec was written for the claude.ai container at `/home/claude/pma/`.
> In this plugin: `exec_review.py` = `tools/exec_review.py`; `ibkr_conids.json`, `pm_watch.json`, `arm_brackets.json` = `config/`.
> Set `AEGIS_LIVE_DIR` to a writable working dir for `prices.json`, `bars.json`, `review_state.json`, `review_log.jsonl`.
> `send_later` (Relay) is the claude.ai scheduler. On another harness, book the same 11 + 1 slots with its own scheduler.

## Slots (SGT; shift +1h from 1 Nov 2026 when the US returns to standard time)
PM 2026-10-26 20:46: NO pre-open check; reviews run from the open to 02:31 only; executive = triggers and actions only.
- Reviews (11): 21:31, 22:01, 22:31, 23:01, 23:31, 00:01, 00:31, 01:01, 01:31, 02:01, 02:31. No pre-open, no 03:01, no 03:31.
- 04:05 = RELAY ONLY (books the next session; no after-close review, no tables). Whatever the 04:05 message says, this spec governs.
- Standard-time version: Reviews 22:31 ... 03:31 (same 11) · relay 05:05.

## Every review (do in this order, keep tool calls parallel)
1. **Plan files.** Use the newest `/home/claude/pma/dNN/` whose `pma_levels.json` has `run_date` = the current US session (Tue 27 Oct session: `d27`).
   If none, pull `aegis/output/pma/pma_levels.json` from TongIncomeWheel/AQE main. Say so if the run_date is not today's session.
   Market gates for the script: `--floor` = the put wall and `--flip` = the gamma flip from that run's Part 1 report (Tue 27 Oct: put wall 760, call wall 780, flip 774.62; SPY closed Mon at 765.37, 0.70% above the floor and 1.21% under the flip, so the stand-down starts OFF; a completed hourly SPY candle closing under 760 turns it ON until a later candle closes back above 760). QQQ: floor 700, flip 731.99, call wall 720 (information only). Dealers are short gamma. FOMC is Wed 28 Oct 14:00 ET (02:00 SGT Thu), after tonight's last review.
2. **Live prices (IBKR, never FMP delayed).** Names = every ADVANCE and HELD ticker in the levels file + SPY + the names in `pm_watch.json`
   (about 30; levels file ADVANCE/HELD rows on 27 Oct: IOT, DBX, VSXY, HOG, ESTC, TRV, CNQ, CVE, TEAM, MP, V from today, LTH, RBRK, DHR from 26 Oct and AMGN, KDP, CHD, CCEP, ELV, XOM, RXO from 23 Oct; watch: GTLB, ZS, ACN and FTNT, SHOP removed). A watch entry may carry a `note`; surface it in the review on the day it matters (FTNT earnings Wed 28 Oct, the same day as the FOMC). Contract ids in `ibkr_conids.json`. `get_price_snapshot(contract_id, market_data_names=["last","change","prior_close","high","low","volume","top_status"])`.
   `volume` is today's cumulative shares; put it in prices.json as `"volume"` (the script uses it for the volume pace; the bar sum is only a fallback).
   If `prior-close` comes back empty, use last − change. Run the script from `/home/claude/pma` with paths like `live/work/prices.json` and `d27/pma_levels.json`; never pass `--now` on a live review (it is ET, for tests only).
   **Rate limit 10/s and 30/min:** call in batches of 7 or fewer (one parallel block per batch), batches back to back, never more than 30 in a minute. Retry a rejected one once.
   If `last` is flagged `is_close` with no trade time, or `top_status` is not REALTIME, say "stale price" for that name; never present it as live.
   Write `/home/claude/pma/live/work/prices.json` as `{"TICKER":{"last":x,"prior_close":y,"change_pct":z,"high":h,"low":l}}` (omit what was not returned; `change_pct` is IBKR's % change).
3. **Run** `python3 /home/claude/pma/live/exec_review.py --prices prices.json --levels <dNN>/pma_levels.json --export <dNN>/aqe_daily_export.json --floor <put wall> --flip <flip>`.
   If stderr prints `NEEDS BARS: A,B,C`: fetch FMP `intraday-1-hour` for just those names (today), save as `/home/claude/pma/live/work/bars.json` `{"A":[bars newest first]}`, rerun with `--bars bars.json`.
   Never show the PM the first pass when bars were needed.
   **Also fetch SPY's FMP `intraday-1-hour` bars (today) every review** and pass the close of the latest COMPLETED candle as `--spy-close X`: a completed hourly close under the floor keeps the stand-down on until a later candle closes back above it (a spot print above the floor is not enough).
3b. **Arm-ready brackets (PM 2026-10-27 19:35: tighter flags on ESTC and VSXY).** Read `/home/claude/pma/live/arm_brackets.json`; ignore it if its `session` is not today's US date. Per name, show a row only when it changes what the PM does: price inside the entry window with the flag met = "Bracket window live: queue Tiger preview on your word (limit L, stop S, ~N sh)" (N = floor(620 / (L - S)) at the live price); price above the window top = "Window shut: above the 2.0 reward-to-risk ceiling X"; price at or under the bracket stop = "Stop level hit". Otherwise print nothing. This tighter flag is in addition to the committee trigger (ESTC still reports at 107.09). Nothing is placed without the Tiger preview and the PM's explicit "confirm".
4. **AQE alerts (names outside the committee's ADVANCE list).** Gmail `[AQE]` newer than the last review; open the newest digest in full.
   Add at most 5 plain lines for HOLD / watch / dip-buy names whose state changed. Skip anything already in the script output.
5. **Tiger (read-only).** Positions, open orders, fills since the last review. Flag any fill with no stop, and any stop that differs from the committee's. One line per exception, nothing if clean.

## Output (PM 2026-10-26: executive, TRIGGERS AND ACTIONS ONLY, to save tokens and PM reading time)
Run every step above (the checks still happen); show only this:
1. Header + one Market line (floor/stand-down state; say only if it changed or it is the first review).
2. One table of ONLY the names that need the PM: trigger hit, within reach of the trigger (as the script flags), broke its exit/kill price, or a held name close to its broker stop. Columns: Name · Price · Trigger/Stop · Action. Action is a plain verb from the plan ("Buy trigger hit: queue the Tiger preview on your word", "Wait", "Exit price broken").
3. Exceptions only: Tiger fill with no stop or a stop that differs from the committee; an AQE alert that changed a name's state into a trigger. Nothing if clean.
- Do NOT print unchanged names, the full watch table, price tables, or the script's full output.
- **If nothing fired and nothing is within reach:** ONE line: "HH:MM · SPY x · no trigger, no action." (add the stand-down state only if it changed).
- First review (21:31): add the one line "Gate: stand-down ON/OFF" and the names to watch at the open, as a single line.
- Plain English, no jargon, no prose paragraphs. Never write "line" (except "Bottom line"), "hourly close" or "AQE default".
- **Momentum names are never called "stretched".** A momentum-lane name trading above its trigger is strength, not a flaw (PM 2026-10-23; the market-hours doctrine and R14). Do not ask for a pullback on one.
  The only limits are the plan's own: its too-late price, its volume and beat-SPY conditions, and the market floor. Distance above the trigger and distance to the stop are reported as plain facts, never as a reason to skip.
  Pullback-lane names (shown as PULLBACK in the levels file) are judged on their own plan.
- **Sizing (PM 2026-10-27 01:22: "1%"): 1R = 1% of $62K = $620.** For every name in the table with a hit or within-reach trigger, add `~N sh` = floor(620 / (current price - stop)) and the stop, at the live price (recompute each review; never reuse an old count). Use the committee stop in the levels file; if the stop type is aqe_atr_fallback, say so. Arithmetic only, never a recommendation; any order still goes through the Tiger preview and the PM's explicit "confirm". Ignore the share counts in the AQE alert emails (they use 3% of $75K = $2,250).

## Special slots
- **21:31 first review (no pre-open):** the market is open; same steps. Add the AQE-engine-alive check only if no `[AQE]` mail or ledger update has been seen in the last 30 minutes (then say so first).
- **Held names:** a held name appears in the table only when it is within reach of its broker stop or has broken it. No "carrying overnight" section.
- **04:05 RELAY ONLY:** skip prices, tables and the Tiger book. Do the Relay below and print only `Relay booked: ...` or `RELAY FAILED: <reason>`.

## Relay (04:05): book the NEXT US session with send_later (initiation human_request)
Next session = next weekday evening in SGT (Saturday in SGT means Monday evening). Skip a US market holiday.
Book 12 messages: 11 reviews, each `Scheduled: executive review HH:MM SGT. Follow /home/claude/pma/live/REVIEW_SPEC.md exactly (read it first).` and the relay `Scheduled: RELAY ONLY 04:05 SGT. Follow /home/claude/pma/live/REVIEW_SPEC.md exactly (read it first): book the next session, print one line.`
Times while the US is on daylight time (until 1 Nov 2026): 21:31, 22:01, 22:31, 23:01, 23:31, 00:01, 00:31, 01:01, 01:31, 02:01, 02:31, then relay 04:05.
Standard time (1 Nov 2026 to 7 Mar 2027): add one hour to each (22:31 ... 03:31, relay 05:05). Finish with `Relay booked: <first and last time, dates>` or `RELAY FAILED: <reason>`.
`send_later` is rate limited (about 9 bookings in a burst, then "try again in ~50s"): book the first 9 in one block, wait about a minute with a background sleep (`run_in_background`; a foreground sleep is blocked), then book the rest. Do not pass any parameter other than at, message, initiation, name.
For a new session also: resolve any new ticker's contract id (search_contracts) and add it to `ibkr_conids.json`; the script lists none missing, so check names against the file.

## If this folder is missing (container was reset)
Restore from the Trading Strategy project docs: `claude/exec_review.py` -> `/home/claude/pma/live/exec_review.py`,
`claude/live_review_spec_2026-10-23.md` -> `REVIEW_SPEC.md`, `claude/ibkr_conids.json` -> `ibkr_conids.json`; recreate `pm_watch.json` from the project notes if absent (script skips the watch table without it).
The previous-review state is `review_state.json` (a missing one only means "first review of the session").
