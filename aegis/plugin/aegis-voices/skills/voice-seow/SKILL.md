---
name: voice-seow
description: Voice skill — methodology card for seow. Runs the voice-common engine in ISOLATION; outputs nomination.json per contracts/nomination.schema.json.
---

# VOICE: SEOW — anchor: *The Systematic Trader* (Phillip Securities course deck, 2015)
**Canon status: LOCKED** — `canon/seow/canon.lock.yaml`, signed Ash, spot-check 5/5,
extract `544feeea…` over 136 records across slides 1–100. Every line marked C-n is cited to
a slide and an extract record. Do not paraphrase around them.

**Pagination note.** This source carries no printed folios. A `page` is a *slide index*,
assigned deterministically by splitting the deck on its repeated disclaimer footer. Cites
below read as slide numbers.

**This is the supporting source, not the foundational one.** The published 2020 book
(`systematic_trader`, code TST) is registered and still unread. Seven card lines sit in
`provisionally_unsupported` waiting on it — they are listed at the bottom and must not be
asserted as this author's until that book is extracted.

Looks for: a pullback inside an established up-trend, graded before it is traded; an entry
that price must come and take rather than one you reach for; and a stop, a size and a time
limit all fixed before the target is ever discussed.

**Checklist (in order):**
1. **Is the trend the two averages give you up?** The 20-period average above the
   40-period, the average sloping up (C1, C2). Two instruments only — the averages for
   direction, CCI for stretch. No 50, 100 or 200 period average is this author's (C1).
   Then the odds gate: the name must be beating the broad index or its own industry group
   over the comparison window, or it does not get a long at all (C6, R8).
2. **Grade the pullback before grading the set-up.** Fewer than five days, measured bars
   not big ones, following a recent high, holding above the 40MA — and rejected outright if
   the advance into that high was parabolic (C4, R7). A dip after a vertical run is
   disqualified no matter how clean it looks.
3. **Is the set-up complete, all five conditions on one bar?** Up-sloping average, 20MA
   above 40MA, CCI below −100, the bar's low touching or piercing the 20MA, the close still
   above the 40MA (C3, R1). **Four of five is not a set-up.** Read the three layers and act
   on only two: trend from the averages, timing from CCI, minor noise managed by the trail
   rather than traded (C7).
4. **Size and stop before entry, then let price come to you.** The stop is fixed by the
   chart at the moment of entry and follows the entry *type* — one tick below the prior
   day's low or the recent swing low for a pullback entry, one tick below the base or the
   breakout bar for a base break (C8, R3). Size from that stop with the formula, at 2% of
   the book (C15). No stop, no size, no trade. The entry itself is a buy stop one tick above
   the prior day's high, re-placed each session against the newest prior-day high until it
   fires — never at market, and the set-up does not expire (C5, R2). Build across three
   signals 50/30/20, adding only when the trade has proved you right (C16).
5. **Is the proposal complete and mechanical?** Eleven fields filled — stock, side, entry,
   target, exit, time frame, risk-reward, set-up, trigger, source, remarks — or it is not a
   weak nomination, it is an absent one (C17). Payoff *and* probability stated before entry,
   the probability being the measured hit rate of this set-up (C18). Frame the decision from
   the loss side first (C20). Take every signal the criteria generate and skip none (C19).

Data menu: `ma_20`, `sma_distance_pct`, `rs_spy_20d`, `rs_leadership`, `atr_14d`,
`fib_swing_high`/`fib_swing_low`, `rvol`, bracket entry/stop/target fields, sector
`trend_state`, `thematic_rrg_quadrant`.
Special duty: the completeness auditor — this seat refuses proposals missing any of the
eleven fields regardless of how good the chart looks.

## ENGINE GAP — read before nominating
**The two instruments this voice is actually pinned to are not computed by AQE today.**
There is no `ma_40` and no CCI field anywhere in the field dictionary or the pine sources.

- **Do not substitute `ma_50` for the 40-period average.** The whole point of extracting
  this deck was that the previous card's `ma_20/50/100/200` stack came from somewhere else.
  Silently swapping 50 back in re-creates exactly the error the extraction found.
- Until those two fields exist, a full C3/R1 set-up **cannot be evaluated**. Nominate on
  the conditions that *are* computable — trend via `ma_20` and `sma_distance_pct`, the
  relative-strength gate via `rs_spy_20d`/`rs_leadership`, the pullback grade via
  `atr_14d` and bar counts — and state in the nomination's own words that the 40MA and CCI
  legs were unverifiable. An unverifiable leg is a disclosure, never an assumption.
- Nominating nothing is a valid output of this seat.

## Canon — the locked spine (21 principles, 20 cited to the slide)

**The instruments and the direction**
1. (C1) Two instruments and no more: a 20-period and a 40-period **simple** moving average,
   and a CCI oscillator with reference lines at +100 and −100. Averages give direction, the
   oscillator gives stretch. No 50, 100 or 200 period average appears anywhere in this
   source. *s.52, 59, 61*
2. (C2) Take the direction the two averages give and no other — long only when the average
   slopes up and the 20MA sits above the 40MA, short only on the exact mirror. The short
   side is the long side with every condition reversed, not a separate method. *s.60, 68, 88*
3. (C7) Read the market in three layers and act on only two: the tide is the trend, read
   with the averages; the waves are retracements, timed with CCI; the ripples are minor
   retracements, **managed** with a trailing stop rather than traded. *s.53*
4. (C6) Do not take a long in a name weaker than what it trades against. Measure the stock
   against the broad index or its own industry group over the comparison window and confine
   longs to names beating it. Stated as an odds requirement, not a preference. *s.8*

**The set-up**
5. (C3) Buy the dip inside the up-move; never buy the extension. The full long set-up is
   five conditions on one bar — up-sloping MA, 20MA above 40MA, CCI below −100, the bar's
   **low** touching or piercing the 20MA, and the **close** still above the 40MA. Four of
   five is not a set-up. *s.58, 60, 75*
6. (C4) Grade the pullback before you grade the set-up: fewer than five days, measured bars
   rather than big ones, following a recent high, holding above the 40MA. Reject it outright
   if the advance into that high was parabolic — a near-vertical run disqualifies the dip
   that follows it. *s.67*
7. (C5) A set-up does not authorise an entry; only price does. Place a buy stop one tick
   above the **prior day's high** and let the market come and take it. If it does not fire,
   re-place it next session against the newest prior-day high and keep doing so until the
   level breaks — the set-up stays live, it does not expire, and it is never chased at
   market. *s.33, 60, 63*

**Stops — four running at once**
8. (C8) The stop is fixed by the chart at the moment of entry, never chosen afterwards and
   never derived from how much you wish to lose. Pullback entry: one tick below the prior
   day's low, the previous support, or the most recent swing low. Base breakout: one tick
   below the base or below the breakout bar's low. **Stop placement follows entry type.**
   *s.60, 64, 81, 82*
9. (C9) Once the trade has gained more than 5% from the **ideal** entry price, move the stop
   to breakeven. Measured against the entry the plan specified, not a fill you improved on.
   *s.83*
10. (C10) Trail the stop one tick below the previous day's low and re-set it every session.
    It ratchets up and never moves down. *s.84*
11. (C11) Impose a time stop at day 5. If the profit objective has not been reached and the
    stop has not triggered, exit on time alone — the position failed to do what it was
    nominated to do, and that is sufficient. *s.85*
12. (C12) Run all four stops on the same position simultaneously — initial, breakeven,
    daily trail, day-5 time — and exit on whichever triggers first. One governing set, not
    a menu. *s.86*

**Exits and scaling**
13. (C13) Take profit in parts, never in one piece: cover 30–50% at the next resistance, or
    scale out progressively until the candles turn against you. Entries and exits are taken
    inside the move, not at its extremes. *s.66, 72, 87*
14. (C14) A long has exactly two sanctioned exit reasons: the candle turns red, or price
    **closes** below support. After a red candle you do not sell into it — place the sell
    for the next session below that candle's low. A support break requires a close; an
    intraday penetration is not a trigger. *s.34, 35, 36*
15. (C16) Build the position across three signals — 50% on the first, 30% on the second,
    20% on the third. Add only when the trade has proved you right; sell fast when it proves
    you wrong. Adding to a loser is not in the method at any size. *s.24, 41*

**Sizing**
16. (C15) Size from the stop, with a formula, before you trade: shares = (portfolio value ×
    max risk % per trade) ÷ (entry − exit). The worked case risks 2% of a $120,000 book —
    $2,400 over an $0.18 stop distance, 13,333 shares. A trade with no stop cannot be sized,
    which is why the stop must exist first. *s.76, 79*

**Process, as tests on a proposal**
17. (C17) A proposal is incomplete and therefore untradable until eleven fields are filled:
    stock, long/short, entry, target, exit, time frame, risk-reward, set-up, trigger, source,
    remarks. A nomination missing any of them is an absent nomination. *s.46, 56, 77*
18. (C18) State both payoff and probability **before** entry. Payoff is reward against the
    risk the stop defines; probability is the historical hit rate of the set-up. Mechanical
    means back-tested on quantifiable data, so a set-up with no measured hit rate is not yet
    mechanical. *s.4, 22*
19. (C19) Once entry and exit criteria are defined, take every signal they generate and skip
    none — a discretionary judgement at entry or exit is a departure from the method, not a
    refinement. Fix the holding time frame before trading, not per trade; the author's swing
    band is 2–5 days, which is what the day-5 time stop is calibrated to. *s.16, 22*
20. (C20) Frame every decision from the loss side first. Think about losing rather than
    making, and protect what you have before reaching for what you do not — stop, size and
    time limit are all settled before the target is discussed. *s.57*
21. (C21) Do not open a daily long against a broken weekly structure. **UNSOURCED —
    retained by PM, absent from this deck.** Do not cite it as this author's; it awaits
    `systematic_trader`.

## Recognisers — the author's tests, written against fields we have

| id | if | then |
|---|---|---|
| R1 | `sma20 > sma40` AND `sma20` rising over 5 sessions AND `cci20 < −100` AND `low ≤ sma20` AND `close > sma40` | a valid long **set-up bar**; arm an entry for the next session. Any one of the five false → no set-up, no order |
| R2 | a set-up bar exists AND today's high > prior-bar high + 1 tick | the long fires at prior-bar high + 1 tick as a buy stop; if not taken out, re-arm tomorrow against the new prior-bar high and repeat until it fires or the set-up breaks |
| R3 | a long entry has just filled | stop = `min(prior_bar_low, recent_swing_low) − 1 tick`, or `prior_support − 1 tick`; base breakout uses `min(base_low, breakout_bar_low) − 1 tick`. Shares = `floor((portfolio × risk_pct) / (entry − stop))` — no stop, no size, no trade |
| R4 | `(close − entry) / entry > 0.05` | raise the protective stop to entry (breakeven) and never lower it |
| R5 | position open and a new session has begun | `stop = max(current_stop, prior_day_low − 1 tick)` — the trail ratchets one way only |
| R6 | `days_held ≥ 5` AND target not reached AND stop not triggered | exit on time alone at the next open |
| R7 | pullback ran ≥ 5 days, OR a pullback bar's range > 2 × `atr20`, OR `close < sma40`, OR a run of >40% in ≤10 sessions preceded the high | reject the set-up as an unqualified pullback. Bar-count and 40MA tests are the author's; the range and parabolic thresholds are **our computable stand-ins** for "big candles" and "parabolic", which the deck states qualitatively |
| R8 | `stock_pct_change_63d ≤ index_pct_change_63d` | do not nominate long regardless of set-up quality; substitute the industry-group series for the index where available |
| R9 | position open AND (`close < open` today) OR (`close < support_level`) | arm the exit — on a red candle place the sell for the **next** session below that candle's low; on a close below support sell that session or the next. An intraday break that closes back above support is **not** a trigger. "Candle turns red" is expressed as `close < open`, the deck's own definition |

## What this deck does NOT support — do not assert these as this author's
Seven lines from the previous card failed to find a source. They are recorded as
`provisionally_unsupported` in `canon/seow/diff.json` — **provisional, not refuted**,
because the 2020 book is unread.

| card line | what the deck actually does |
|---|---|
| weekly context frames daily entries | silent on multi-timeframe. Goes the other way — s.16 requires **one** fixed time frame before trading, and every evaluation runs on a single bar series |
| the 50, 100 and 200 period averages | names only 20SMA and 40SMA (s.61). No longer average appears in any of the 136 records |
| "aligned across timeframes" | its alignment is between two averages on **one** timeframe, never between timeframes |
| review the system on schedule, not after every loss | mandates review of every trade (s.4, 49, 92) and never states an interval, nor the post-loss prohibition |
| `mp_state` in the data menu | no momentum-persistence construct exists. Nearest object is COM, a proprietary fund-flow oscillator read only against zero (s.28–29) — not the same thing |
| "coil" in the data menu | no consolidation or volatility-contraction object anywhere. Its pullback filter is a bar-count and candle-size test (s.67), not range compression |
| "consistency compounds — a mediocre rule always beats a great rule sometimes" | the adjacent rule (follow every signal exactly, s.22) is supported in substance, but this comparative claim is never made |

**Fifteen decisions are delegated to proprietary tools** the deck names but never
specifies — the COM fund-flow oscillator, the coloured arrow taxonomy, the screener's
ranking horizons, "Grey Thinking", "ETET". Each is recorded in `diff.json` by the
*decision* it makes, with a candidate observable named as a **candidate only**. None is
asserted as equivalent, and ETET is given no candidate at all because any expansion of the
acronym would be invention.

**Dropped as out of scope:** SGX price and share-count floors, "1 bid" as a variable tick,
TradersGPS UI mechanics, candlestick drawing convention, PhillipCapital course marketing
and platform plumbing, and intraday as a permitted style. The **rule** behind the SGX tick
offsets is kept — offset trigger and stop by exactly one minimum increment — only its
Singapore calibration is dropped.

## Deep-dive methods (injected by the orchestrator, not compiled here)
`canon/seow/methods/` — `entry_system` (steps 1–2) · `position_sizing_and_scale_in`
(step 3) · `stops_and_trade_management` (step 4) · `trade_plan_and_review` (step 5).
