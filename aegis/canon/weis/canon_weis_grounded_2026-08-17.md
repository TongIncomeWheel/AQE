# Weis — grounded canon (2026-08-17), REPO-SAFE COPY

**Source:** David H. Weis, *Trades About to Happen: A Modern Adaptation of the Wyckoff Method*, Wiley 2013.
Full text read across 5 independent extraction passes. No chapter unread.

**COPYRIGHT NOTE.** This repo is PUBLIC. Per the standing rule recorded in `aegis/.gitignore` and
`canon_build.py` — *copyrighted source text never enters version control* — the ~20 verbatim
quotations that ground this canon are **withheld from this file**. The authoritative quoted copy
lives in the private claude.ai project doc `claude/canon_weis_2026-08-17_grounded.md`.
What follows is derived analysis: paraphrased principles, field mappings, and scope rulings.

**Status: GROUNDED, PENDING PM SIGN-OFF. Not locked. This seat must not nominate until the
collision below is ruled.**

---

## BLOCKING FINDING — this seat already exists inside `detect-lens`

`canon_detect_lens_24_principles_2026-08-10` was built from FOUR books. Three of them are the
three books the PM has queued as "new momentum specialist" seats:

| Queued book | Already seated as | Scope |
|---|---|---|
| Weis, *Trades About to Happen* | detect-lens **C19-C24** | mechanical single-bar/short-sequence tests |
| Kratter, *Learn to Trade Momentum Stocks* | detect-lens **C1-C5** | 50/200 MA cross, 15% stop, 4x target, sizing |
| Ceponas, *Day Trading: Momentum, Level 2, Tape* | detect-lens **C6-C11** | ruled NOT_APPLICABLE premarket 2026-08-09 |

**Why this is blocking.** Qualification is `seat_count >= 2 OR solo conviction >= 4`. If `weis`
nominates on a spring read and `detect-lens` nominates the same name on C21 — which IS Weis's
spring — the tally records 2 seats and the deliberation set treats it as independent convergence.
It is one method counted twice. Same defect for kratter/detect-lens C1-C5. The corruption is not
random: it concentrates on exactly the setups the doctrine is best at, i.e. the names most likely
to reach the cap.

**Second finding: a `ceponas` nominator seat cannot be built.** His method is order-book depth and
Time & Sales print speed. No Level 2 field exists in `aqe_daily_export.json`, and there is no tape
before the open by definition. A ceponas S4 nominator would receive a packet containing zero
readable fields. It abstains every session or it fabricates. Recommend: not seated as a nominator;
retain PM-observed market-hours only, exactly as ruled 2026-08-09.

**Recommended resolution.** Decompose the composite. `detect-lens` keeps Clenow (C12-C18) plus its
native lens-engine fields; `weis` and `kratter` become first-class seats carrying full canons;
`ceponas` stays unseated premarket. Net S4 nominators: **10** (8 existing + weis + kratter).

---

## What this seat is

**The failed-breakout seat.** Weis does not buy strength; he buys the failure of weakness — the
break that does not follow through. He is explicitly anti-pattern-recognition and
anti-breakout-chasing, which makes him the structural counterweight to oneil/minervini/livermore,
who buy confirmed strength. Where they need the breakout to hold, Weis needs it to fail.

Non-redundant against every current S4 seat EXCEPT detect-lens C19-C24 — the collision above.

## Principles W1-W23 (derived, paraphrased)

**Effort vs result — the master diagnostic**
- W1 Volume is effort; range and net progress are result. The mismatch is the signal; neither level alone is.
- W2 Large effort + small reward = the trend's own side is being absorbed.
- W3 Formulaic volume tables are explicitly disowned as too simplistic to capture nuance.
- W4 Low volume with continued progress is NOT automatically bearish.
- W5 True range substitutes for volume as an effort proxy — Weis's own stated fallback.

**The false break**
- W6 SPRING = penetration of defined support that fails to follow through and reverses up.
- W7 Confirmation is a combination: narrow range or low volume on the penetration (washout, not real supply) OR heavy volume with disproportionately small progress; no follow-through next 1-2 bars; close back above the level with ease.
- W8 Penetration depth is BOUNDED. A break too deep for the range structure is not a spring and must not be classified as one.
- W9 SECONDARY TEST: pullback on lower volume and narrower range holding above the spring low confirms. Break materially below on heavy volume voids.
- W10 TREND GATES THE SPRING. Springs in an uptrend are the higher-probability case. Springs in a downtrend are the lowest-conviction case in the book and read as SHORT evidence, not long.
- W11 Degree scales with the timeframe of the level violated. Terminal shakeouts resolving multi-year ranges are the highest class.
- W12 GAPPING SPRING — gap up after a demoralising breakdown, near prior bar's high, volume soaring. Weis's stated favourite. Works in uptrends, rarely in downtrends.
- W13 UPTHRUST = mirror. Confirmed when the close erases the breakout bar's range. Size-bounded ~10-15% new high. A narrow-range new high is inherently suspect.
- W14 UPTHRUSTS GATED INVERSELY — they rarely pan out in an uptrend, they flourish in a downtrend. An upthrust on a long candidate in a healthy uptrend is a caution flag, not a reversal call.
- W15 An upthrust is ending action, not necessarily terminal action. It ends the leg, not the trend.

**Absorption**
- W16 ABSORPTION = the process by which long liquidation, profit taking and new short selling are overcome. Directional, not tightness-based — wide swings across a level can still be absorption. Test: threatening bars fail to produce follow-through; price presses the boundary without giving ground.
- W17 Bullish signature: rising supports; volume increases near the top of the area; no downward follow-through after a threatening bar; price presses resistance without giving ground; sometimes resolved by a spring; minor upthrusts fail to break it down.
- W18 BAG-HOLDING — persistent heavy selling against a low that fails to produce weakness. Shorts being trapped. Bullish.
- W19 FAILED ABSORPTION INVERTS. Repeated failed springs at a low mean sellers are absorbing the buying. Bearish.

**Thrust decay and contraction**
- W20 SHORTENING OF THRUST = diminished progress high-to-high or low-to-low. Minimum THREE impulses. Past four, the trend may be too strong to trade against — suppress the counter-trend signal. With only two, consider spring/upthrust instead.
- W21 CONTRACTION PRECEDES EXPANSION. Crabel's narrow-range family imported wholesale (2Bar NR, 3Bar NR, NR4, NR7, inside day, ID/NR4), equated with Wyckoff's hinge. Narrow phase is the setup, wide-range break the trigger. DIRECTION IS NOT IMPLIED by contraction — read it from the preceding price/volume behaviour.
- W22 CHANGE OF BEHAVIOUR. The first bar breaking the trend's established rhythm — first outside reversal against the move, largest counter-trend range of the sequence — is an early warning to flag even when not actionable.

**Trend supremacy**
- W23 The trend overrides all other particulars of market context. Every setup above is conditioned on trend first. This is why W10 and W14 point in opposite directions.

23 principles — within the PRINCIPLES_MAX = 25 bound.

## Data standing

**SERVED**

| Principle | Fields |
|---|---|
| W1, W2, W5 | day_vol, flow, atr_14d, energy |
| W6-W8 (degraded) | pin_bar_state, structure_shift, sma_distance_pct, bracket.stop, bracket.valid |
| W13 (degraded) | pin_bar_state, choch_state, structure_shift |
| W16-W19 | flow, structure, energy, bq.bq_base_dur |
| W20 (proxy only) | mp_accel_state, sc_momentum, div_state, div_bear_count |
| W21 | energy.squeeze_score, bq.bq_range_tight, bq.bq_base_dur, inside_bar, atr_caution |
| W22 | choch_state, structure_shift, elder_pattern |
| W23 | ma_20/50/200, sma_distance_pct, mp_state, sector_trend_state |

**NOT SERVED, ranked by damage**

1. **Multi-bar follow-through.** W7 and W9 CANNOT EXECUTE AS WRITTEN. The export is a single-day
   snapshot; "penetration with no follow-through" is a sequence and the seat sees one frame.
   Nearest proxies: pin_bar_state (penetration and recovery WITHIN one bar), elder_5d (5-day trace).
   Every spring call must be labelled a single-bar rejection read, never a confirmed spring.
2. **Close-location value** (close-low)/(high-low). Weis's most-used primitive, on nearly every page.
   No field exists. Highest-value, lowest-cost engine ask this seat generates — also serves
   wyckoff, raschke, elder-lens.
3. **Penetration depth vs a violated support level.** W8's depth bound cannot be enforced.
   bracket.stop is a PROPOSED stop, not a level price has broken.
4. **Successive thrust magnitudes.** W20 degrades to proxy. mp_accel_state is momentum
   deceleration, not high-to-high progress across three impulses. Cite as proxy, declared.
5. **Volume at prior pivots.** Weis compares to volume at named prior structural points, not to a
   moving average. Only rolling-average comparison available.
6. **Secondary test detection.** W9 unserved.

**OUT OF SCOPE — permanently, by construction. Not gaps.** The seat is FORBIDDEN from asserting
these; doing so is a blocking defect:

- **Wave volume.** The Weis Wave sums volume WITHIN a price wave from tick/minute data. A daily bar
  collapses a session's competing buy and sell effort into one undifferentiated number. Up-wave vs
  down-wave volume cannot be recovered. Never phrase daily volume in wave-volume language.
- **Tape reading, Level 2, order flow, "moment of recognition."** Chapters 9-10 are structurally
  intraday. None of it exists premarket.
- **Renko brick / tick point-and-figure counts.** Chapter 11. Weis himself flags a daily-close P&F
  chart filters out intraday highs and lows and is inferior.
- **Net up/down volume splits.** Requires buyer- vs seller-initiated attribution. Not derivable
  from daily OHLCV; Weis endorses no estimation heuristic.

Matches the house pattern set by the steenbarger card's pm_only split: material that cannot be
honestly executed is retained and tagged, never quietly dropped and never faked.

## Voice menu — weis

Doctrinally distinct from `wyckoff`, which shares the same ancestor. Wyckoff keeps the
campaign/phase lens (lens.coil, lens.structure, lens.resistance). Weis takes the false-break and
narrow-range-contraction family — his own imported Crabel toolkit (W21), traceable to source.

ticker, pin_bar_state, choch_state, inside_bar, structure, structure_shift, energy,
energy.squeeze_score, bq.bq_base_dur, bq.bq_range_tight, flow, day_vol, atr_14d, atr_caution,
sma_distance_pct, ma_20, ma_50, ma_200, mp_state, mp_accel_state, sc_momentum, div_state,
div_bear_count, elder_pattern, elder_5d, sector_trend_state, entry, bracket.stop,
bracket.stop_type, bracket.valid, bracket.atr_fallback_stop, bracket.risk_pct

32 fields. No rs_leadership/rs_spy_20d (leadership is oneil/minervini; Weis never ranks by relative
strength). No knn_prob (thorp). No thematic fields (druckenmiller). No lens.* decomposition (wyckoff).

## Conviction grading 1-5

- **5** Terminal shakeout, or spring undercutting a higher-timeframe prior low, with monthly-degree
  tightness or historic volume. NOT REACHABLE on current fields — no multi-timeframe join. Reserved.
- **4** Gapping spring in an established uptrend (W12), or absorption with the full W17 signature
  intact, trend-confirmed per W23.
- **3** Ordinary minor spring within a clean uptrend correction — Weis's own framing is a "small
  bet." Also contraction (W21) with a bullish preceding read.
- **2** Setup lacking supporting context, or any read resting on a rank-4 proxy field.
- **1 / DO NOT NOMINATE** Any spring-shaped read inside an established downtrend (W10). Weis reads
  these as SHORT evidence. The seat must not nominate them long.

## Page basis — known defect, declared

Extraction passes returned CONFLICTING page indices. One located Ch7 at PDF pp.138-148 where
range arithmetic implied pp.160+. A second found printed-book and PDF folios diverge by ~22 pages
throughout. A third flagged its citations as positional estimates, not verified folios.

The existing detect-lens canon cites TATH by PRINTED page. Citations in the project-doc copy are
PDF-page-approximate, marked "~p." throughout, NOT folio-verified, and must not be treated as
citation-grade. Same defect recorded in the druckenmiller and livermore locks.

**Open item:** re-extract in 5-page windows against visible folios before `canon_build.py seal`.
Until then this canon is grounded but NOT SEALABLE.

## Decisions required from PM

1. **Decompose detect-lens?** Hand C19-C24 to `weis` and C1-C5 to `kratter`, leaving detect-lens on
   Clenow C12-C18 + native lens fields. Alternative: keep detect-lens composite and do NOT seat
   weis/kratter — the double-count is otherwise structural and will corrupt seat_count.
2. **Confirm ceponas stays unseated premarket.** Recommend yes.
3. **S4 nominator count lands at 10, not 13.** SKILL.md and S6B need correcting either way.
4. **Add close-location-value to the export?** Rank-2 gap, cheapest high-value ask, serves 4 seats.
