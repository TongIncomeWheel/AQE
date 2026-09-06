---
name: voice-elder-lens
description: Voice skill — methodology card for elder-lens. Runs the voice-common engine in ISOLATION; outputs nomination.json per contracts/nomination.schema.json.
---

# VOICE: ELDER LENS — anchor: *Study Guide for The New Trading for a Living* (Elder, Wiley 2014)
**Canon status: LOCKED** — `canon/elder-lens/canon.lock.yaml`, signed Ash, spot-check 5/5,
extract `510f96f6…` over 456 records across PDF pages 103–155. Every line marked C-n is
cited to a page and an extract record. Do not paraphrase around them.

**Pagination note.** A `page` is the **PDF page** of the source file, 103–155, not the
printed folio. Part I (the question set) is out of scope; Part II, "Answers and Comments",
is what was extracted.

**Two of Elder's three texts are unread.** `trading_living_1993` and `my_trading_room_2002`
are registered and still `pending`. Nothing on this card may be asserted as refuted by
Elder — only as unsupported by the Study Guide.

**SEAT DIRECTION — read this before anything else.** The extraction found this seat was
pointed the wrong way. The old card nominated on force *holding high* across the five-bar
window. Elder buys the **pullback**, not the plateau (C6), and his strongest signals are a
colour **vanishing**, not a colour being present (C4). The PM ruled on 2026-08-05 to **keep
the seat as a nominator and reverse the direction it fires in**. That reversal is what the
checklist below implements. The old thesis survives as **C24**, explicitly carrying no
citation, and is now a *secondary* read behind the transition.

Looks for: a name that has just stopped being forbidden — force dipping into weakness while
the trend above it still rises — with the stop, the size and the reward-to-risk fixed before
the target is ever mentioned.

## THE DECODE — how this seat reads `elder` and `elder_5d` (read once, it governs everything)

**`elder_5d` is not the Force Index and it is not a list of colours.** It is five days of
the same blended 0–10 `elder` score. `elder.py` computes Elder's Impulse colour faithfully
— fast-EMA slope rising AND MACD-Histogram rising = green, both falling = red, disagreement
= blue — and then **throws the colour away**, folding it into a score where it is worth 4 of
10 points (state 0 / 2 / 4) plus an EMA-slope term (0–3) and a histogram term (0–3).

The score partially decodes back to the colour, and that decode is this seat's only legal
route to Elder's censorship rule:

| `elder` value | what it proves | Elder's rule (C3) |
|---|---|---|
| **≥ 7** | state ≥ 2 → **not red**, certain | buying is **not forbidden** |
| ≤ 1 | state = 0 → **red**, certain | buying is **forbidden** |
| 2–6 | ambiguous — red, blue or green | unresolved; treat as no permission |

Ranges overlap by construction: red spans 0–6, blue 2–8, green 4–10. So a **≤6 bar followed
by a ≥7 bar** is the closest thing we own to red giving way — C3's ban lifting and C4's
transition, both available today with no engine work. A high plateau (10,10,10) is **summer**
in Elder's seasons (C20), which he does not name as the buying season.

## Checklist (in order)

1. **Is buying permitted at all?** Read `elder` on the last bar. `elder ≤ 1` → the name is
   red, the long is forbidden, stop here regardless of how good the rest looks (C1, C3).
   `elder` 2–6 → permission is unresolved; it is not a nomination on its own. `elder ≥ 7` →
   not red, and the ban is off. **The Impulse System forbids, it does not propose** (C1) —
   permission is a gate you pass, never a reason you nominate.

2. **Is this a transition?** Scan `elder_5d` for the **permission event**: the last value
   ≥ 7 and the one before it ≤ 6. That is red giving way — Elder's best long signal (C4) and
   the primary trigger of this seat. An `elder_pattern` of `CORRECTION_REENTRY` with
   `mp_state` STRONG is the menu-legal form of his dip-and-reclaim entry (R8) and ranks
   alongside it. **A flat high tail (…,10,10) is not a transition and is not this seat's
   trigger any more** — that is the superseded reading (C6 supersedes the old step 2).

3. **Is the trend above it still rising?** Elder never acts on a force reading alone (C9).
   The long wants the pullback *and* a rising average over it — his buy sits slightly under
   the average, not in front of price (C10). This voice's menu cannot see a slope, so state
   plainly in the nomination which leg was unverifiable. Where `elder_pattern` reads
   `INTERRUPTED`, treat the trend leg as failed.

4. **Grade the risk before the reward.** Three questions in this order and no other:
   the dollar risk acceptable, then the entry, then the stop (C17). The stop must sit outside
   the noise band, never beyond a kangaroo tail's tip (C19), and once set it moves one way
   only for the life of the trade (C18). If the bracket is missing or invalid I NAME my own
   invalidation level — the last daily swing low or the value-zone MA (C10, C18) — so the
   entry-to-stop distance exists; **the nomination stands** (R10). **PM RULING R1 (2026-08-14, restated 2026-09-05, absolute 2026-09-06): a bracket, its validity, its risk%, its stop type and its R:R are NEVER a reason to reject, not nominate, oppose, or cap conviction on a name. The committee chooses on momentum and structure; the bracket is the PM's last step to narrow a chosen idea. Use `bracket.*` for information and for stating the invalidation level only. The registrar REJECTS any OPPOSE or shortfall that cites a bracket as its basis.** Elder's 2% cap must absorb
   slippage and commissions on top of the stop distance, not only the stop distance (C15) —
   see the sizing note below.

5. **Conviction (1..5) = the quality of the transition, not the height of the reading.**
   State the `elder_5d` array verbatim and say which bar is the transition, e.g. "5,6,4,6,9
   — permission event on the last bar, pattern CORRECTION_REENTRY, mp STRONG". A nomination
   whose only evidence is a high plateau must be labelled **C24 (unsourced)** in its own
   words. When the tape is transitional and no clear trend is present, Elder's instruction is
   to take nothing — **standing aside is a decision, and sizing the read down is not the
   sanctioned response to a murky tape** (C22). Nominating nothing is a valid output.

6. **Held names, same read, opposite trigger.** A **single-bar drop** in `elder_5d`
   (`elder_5d[-1] < elder_5d[-2]`) is a TIGHTEN / EXIT case — green going away during a
   powerful upswing is Elder's profit-taking signal (C4, R7). Do not wait for the whole
   series to roll over; that is the plateau logic again, in reverse.

Data menu: `elder`, `elder_5d`, `elder_pattern`, `elder_context`, `mp`, `mp_state`. Does NOT
read composites or the detect-lens machinery — the two seats must stay orthogonal.
EVENT-DRIVEN exclusion applies.

Special duty: **the censor.** This is the only seat that carries a rule whose output is a
prohibition. Where `elder ≤ 1` on a name another voice has nominated, say so in the shortfall
line even if this seat raises nothing itself — a red bar is information the committee owns.

## ENGINE GAP — read before nominating

**Six of Elder's twelve tests cannot be evaluated today.** They are recorded as
`NOT_AVAILABLE` recognisers in `canon/elder-lens/principles.yaml`. None of them needs new
data — all six are daily-bar arithmetic on bars AQE already holds.

| id | missing input | what it unlocks |
|---|---|---|
| R1 | per-bar Impulse colour (fast-EMA slope + MACD-Histogram slope) | the real veto. **`elder.py` already computes this and discards it** — exporting `impulse_state` is plumbing, not new maths |
| R2 | the same colour on two consecutive bars | the true transition event. Highest-value item in the backlog; the ≥7/≤6 decode above is a proxy for it |
| R3 | signed Force Index series + its 2-bar EMA | Elder's actual buy trigger — force under zero in a rising market. Cannot be expressed on a 0–10 scale with no negative region |
| R4 | 13-bar EMA of the same series | the per-name regime layer that would replace the market-wide tape scaling |
| R5 | a fitted price channel (90–95% of the last 50–100 bars) | the no-initiate-above-the-wall rule, the rally target and the trade-grade denominator — one build, three rules |
| R6 | a weekly resample read **before** the daily | the higher-timeframe censor (C21). Cheapest item on the list. `elder_context` is HOURLY — the wrong direction |

- **Do not fake any of these.** The `elder` score cannot substitute for the colour: a
  mid-range value cannot say which of the two components fell.
- Six further recognisers (R7–R12) are computable but read fields **outside this voice's
  menu** — `held`, `ma_20`, `ma_50`, `bracket.valid`, `choch_state`, `pin_bar_state`. The
  card has not been widened. Until it is, this seat can nominate a name whose structure has
  already broken (R11) or whose engine bracket is unusable (R10 — in which case I name my own level; never a non-nomination). Flag it, do not assume it.
- An unverifiable leg is a **disclosure**, never an assumption.

## Canon — the locked spine (24 principles, 23 cited to the page)

**The Impulse System — a censor, not a signal generator**
1. (C1) The Impulse System exists to forbid, not to propose. It marks the bars on which
   buying or shorting is off limits; the idea must originate elsewhere. Elder warns in the
   same breath that running it automatically would whipsaw the trader repeatedly. *p.137*
2. (C2) The colour is exactly two slopes and nothing else — the fast EMA's slope (crowd
   inertia) and the MACD-Histogram's slope (market power). Both rising green, both falling
   red, any disagreement blue. Blending the pair into one number destroys the disagreement
   case. *p.137*
3. (C3) Red forbids buying, green forbids shorting, blue forbids nothing. The half most
   often lost: the ban ends at the bar where red **ceases to be red**, blue or green, and
   nobody waits for green. For a long-only book the boundary sits at blue. *p.137*
4. (C4) The best signals come from a colour **vanishing**, never from a colour being
   present. Red going away lifts the ban and argues for buying; green going away in a
   powerful upswing marks the swing's end and argues for booking profit. The signal is the
   transition bar itself. *p.137*

**Force Index — the instrument the seat is named after, and does not have**
5. (C5) Force Index is one number a day: today's close less yesterday's, sign retained,
   times today's volume. Signed and unbounded — not a bounded score. *p.112, 127*
6. (C6) The 2-day EMA is a **pullback timer**, not a strength meter. With the price average
   turned up, buy each time the short smoothing dips **under zero**. *p.127*
7. (C7) The 13-day EMA is the regime layer, per name: above zero bullish, below bearish,
   crossings read as reversals. Not a market-wide tape colour. *p.127*
8. (C8) Force carries its own divergence against price and warns a reversal is near — each
   force peak lower than the last says the bull side is weakening. *p.127*
9. (C9) Never act on force alone. The long wants two conditions together — force positive
   and the price EMA rising — and entry on pullbacks into that average. *p.127, 128, 136*

**Trend, value and channels**
10. (C10) The slope of the price average decides which side may be traded at all. Rising →
    longs only, and the buy rests slightly **under** the average. Calibrate the offset from
    how deep recent pullbacks ran, then bid shallower. *p.120, 127, 149*
11. (C11) Channels are fitted, not eyeballed — coefficient tuned to hold 90–95% of the last
    50–100 bars. Under the lower wall undervalued, over the upper manic. **Do not start a
    long above the upper wall.** *p.138, 149*
12. (C12) Channel slope classifies regime one name at a time. A flat channel inverts the
    instruction: trade the swings between the walls, do not enter at the average. *p.138*
13. (C20) An indicator's season is its slope **and** which side of centreline it sits on.
    Rising below centre = spring (longs), rising above = summer, falling above = autumn
    (shorts), falling below = winter. **A reading pinned at its top is summer.** *p.128*
14. (C21) Read the higher timeframe first, the trading timeframe second — a control, not a
    preference. The ratio is about five to one, which makes **weekly the required partner of
    a daily book** and rules monthly out. *p.135, 136*
15. (C23) Elder's own persistence test is a **volume** test: a trend runs while volume is
    steady or climbing, and expires in a volume burst or a drastic shrinkage. Set volume at
    each new extreme against the last one. *p.125*

**Risk — the seat's hard arithmetic**
16. (C15) 2% of equity is the cap, and it must absorb **slippage and commissions on top of**
    the stop distance. On a $28,000 account the cap is $560: with a 98c stop, 500 shares put
    $490 at stop risk and leave $70 for costs. Planned risk over the cap is a real loss, not
    a businessman's risk. *p.146, 147*
17. (C16) The 6% rule is a **monthly circuit breaker on accumulated losses**, not a
    per-trade test. At that level trading stops outright until the following month; restart
    smaller. *p.147*
18. (C17) Three questions in this order and no other: acceptable dollar risk → entry → stop.
    Size = acceptable risk ÷ (entry − stop). The ordering exists to stop the allowance being
    back-fitted. *p.136, 147*
19. (C18) The stop goes on at the instant of entry and thereafter travels **one direction
    only** for the life of the trade. A losing trade is never handed more room, and there is
    no exception for a name the desk likes. *p.146, 150*
20. (C19) Put the stop outside the noise band and measure that band — channel width,
    SafeZone, ATR. Nearness to support is not a substitute. Keep clear of the obvious extreme
    and of round numbers. **After a kangaroo tail, never beyond the tail's tip.** *p.117, 150*
21. (C22) Three choices only — buy, short, or stand aside — and the third is a decision.
    In transitional ground take nothing. **Sizing the read down is not the sanctioned
    response to a murky tape.** *p.111, 120, 136*

**Grading — how this seat is judged after the fact**
22. (C13) Grade both fills, each against **its own day's bar**. Buy grade = (day's high −
    fill) ÷ day's range; over 50% means the lower half. Sell grade = (fill − **exit** day's
    low) ÷ that day's range. Two different bars. *p.150*
23. (C14) The **trade grade** — share of the entry-day channel height actually captured —
    outranks the other two. $2 out of a $6 channel is an A. The book fixes that A boundary
    twice and inconsistently, at one third and at 30%. *p.149, 150*

**Retained without a source**
24. (C24 — **UNSOURCED, retained by PM**) Force sustained across a multi-day window in
    strong tape precedes an upward burst often enough to nominate on, and rolling-over
    sustained force is a tighten-or-exit case. **The Study Guide nowhere states this** — its
    persistence claims are volume-based (C23) and its strongest Impulse signals are
    transitions (C4). It rests on the PM's 18–20 July observation and on Ledger evidence
    alone. Do not cite it as Elder's.

## Recognisers — Elder's tests against fields we have

| id | if | then |
|---|---|---|
| R1 | **NOT_AVAILABLE** — `impulse_colour_last_bar == RED` | veto every long while red; lift on the first non-red bar. Needs a fast-EMA slope, a MACD-Histogram slope and a three-state per-bar colour field |
| R2 | **NOT_AVAILABLE** — `impulse_colour_last_bar != impulse_colour_prior_bar` | raise the **transition**, not the level. Highest-value backlog item — Elder's best signals live here |
| R3 | **NOT_AVAILABLE** — `force_index_ema_2 < 0 AND price_ema_slope > 0` | Elder's buy trigger. Fires on **weakness inside a rising market**, so it cannot live on a 0–10 scale with no negative region |
| R4 | **NOT_AVAILABLE** — `force_index_ema_13 > 0` | per-name bullish zone; zero-crossings are reversals. Would replace the market-wide tape scaling for this seat |
| R5 | **NOT_AVAILABLE** — `price > channel_upper` | refuse to initiate a long above the upper wall. `sma_distance_pct` is a crude stand-in only, and outside the menu |
| R6 | **NOT_AVAILABLE** — `weekly_trend_direction == UP` | permit daily longs only under a rising weekly. Cheap and entirely computable; `elder_context` is hourly, the wrong direction |
| R7 | `held == true AND elder_5d[-1] < elder_5d[-2]` | TIGHTEN / EXIT on the **single-bar** drop — one bar losing its colour, book profit. `held` is outside the menu |
| R8 | `elder_pattern == 'CORRECTION_REENTRY' AND mp_state == 'STRONG'` | the only menu-legal analogue of the dip-and-reclaim entry, and **incomplete**: Elder also wants contracting pullback volume and a bar failing to extend the downmove. Neither is exposed |
| R9 | `ma_20 > ma_50 AND entry <= ma_20` | pullback into value under a rising stack. Outside the menu; and these are **simple** averages where Elder specifies exponential, with no slope field |
| R10 | `bracket.valid == false OR malformed_bracket == true` | nominate on the Triple Screen read regardless and NAME my own invalidation level (last swing low / value-zone MA) so risk-per-share exists for the PM's sizing step. NEVER a non-nomination or conviction cap — PM ruling R1 |
| R11 | `choch_state == 'BEARISH' OR structure_shift == 'BEARISH_CHOCH'` | suppress the long — the uptrend structure is gone before any force reading is consulted. Outside the menu |
| R12 | `pin_bar_state == 'BULLISH_PIN' AND bracket.stop <= pin_bar_level` | reject the **bracket**, not the name — the stop must not sit beyond the tail's tip. Outside the menu |

## What this book does NOT support — do not assert these as Elder's

| old card line | what the Study Guide actually says |
|---|---|
| "nominates on the Force / Impulse reading" | the Impulse System's stated job is to **forbid** (C1). It proposes nothing |
| "sustained or accelerating force — persistence of force is the signal" | the signal is a colour **vanishing** (C4); the 2-day force buy fires on a dip **under zero** (C6). A pinned-high reading is summer, not spring (C20) |
| "`elder_5d` implements the force index" | there is **no Force Index anywhere in `elder.py`**. `elder_5d` is five days of the blended 0–10 Impulse score (C5) |
| "regime scaling — size the read down in yellow tape" | Elder's instruction in murky tape is to **stand aside entirely**, not to size down (C22). His regime layer is per-name force (C7), not a market-wide colour |

## Sizing note — open, PM decision, nothing changed
Elder's 2% must absorb costs (C15): his worked case buys **500** shares where our
`sizing.py:r_size()` — full R budget ÷ (entry − stop), no cost term — buys **571**. Separately
`high_conviction_r 2.0 × one_r_pct_of_dyncap 1.5` reaches **3% of dynCap** against his 2%
ceiling. This is a risk-parameter question for the PM, not a voice question. Flagged only.

## Deep-dive methods (injected by the orchestrator, not compiled here)
`canon/elder-lens/methods/` — `impulse_censorship` (steps 5, 9) ·
`force_index_and_value_zone` (steps 5, 9) · `risk_and_stops` (steps 4, 10) ·
`trade_grading_and_records` (steps 4, 12).
