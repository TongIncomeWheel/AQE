# AEGIS PREMARKET BRIEF — Thursday 4 September 2026
**run pma-2026-09-04** · analysis only · nothing staged, nothing armed

---

## HEADER — RUN STATE AND DECLARED DEGRADATIONS

Every seat form in this run is committed with a verified packet MD5 and a verbatim proof line. 9 of 9 nominations, 11 of 11 ballots, 4 of 4 challenge forms, 2 of 2 macro forms — zero rejections at the registrar.

**Declared in `run_manifest.json`:**

| Step | Status | Note |
|---|---|---|
| GATHER | **degraded** | `data_steward_agent_bypassed_known_nonfunctional` — export and Crown datapoints taken from the verified premarket half instead. |
| MACRO | done | `macro_no_registrar_validate` — the two macro forms were not put through the registrar schema check. |
| PREPARE | done | NO Layer 0 filter (PM instruction). Full AQE universe: 162 daily_list + 2 held carried = 164. |
| RANK | done | 18 qualified from 50 nominated across 164; cap 20 did not bind. |
| VOTE / CHALLENGE / DECIDE | done | all forms MD5 + proof-line verified. |

**Declared additionally, beyond the manifest:**

1. **`signal_radar` in today's export was computed 2026-09-03** — one day behind. It was consumed by no voice and by no tool in this run. Carried as declared, not used.
2. **The coverage gate returned exit 2 and the PM overrode it.** The blocking line was the retired field `ptrs`, which AQE retired on 2026-08-13. `aqe_coverage.py` has been patched. The override was a fix to the checker, not a waiver on the data.
3. **This run was executed twice.** The first full committee was lost to a container wipe before any artifact was persisted. On the rebuild the inputs were byte-identical — packet MD5s matched — and every seat was re-spawned fresh with no memory of the lost run. Every committed form here carries a verified packet MD5 and a verbatim proof line. Nothing was carried across from the lost pass.
4. **The AQE export's `aqe_last_run.json` marker still reads 2026-09-03.** This is the known marker-publish bug. The export payload itself is stamped `2026-09-04 12:50:17 SGT` and its content is today's.
5. **Macro data holes, from the two macro forms themselves:** dealer gamma unavailable for both underlyings (Alpaca and Tiger credentials unset) so Crown's R9 knife-edge check was **skipped, not passed**; economic calendar returned FMP HTTP 404, so forward-event coverage is zero; CFTC positioning is as-of 2026-08-25, ten days behind; fourteen futures markets were sourced from Yahoo rather than the primary feed — including the DX 99.6482 level Druckenmiller leans on hardest.
6. **Druckenmiller's seat is self-declared HAND-WRITTEN and UNGROUNDED** (no canon lock, no sealed extract). His credit read, Hurst read and sector-RRG read were all NOT_SERVED to him.
7. **Two internal counts do not reconcile and are surfaced, not resolved:** the deliberation brief's header line reads `held 2` while its own next line names three held tickers (BRZE, HNGE, V); and the universe build records `qs 7` source names while PM LENS scores 9 rows with `on_qs = true`. Rogers raised the first. Neither changes a verdict.
8. **One held-book name reports earnings on Tuesday 8 September** (cited by both macro seats). Which held name is not served in today's inputs — declared gap.

---

## THE RESULT, FIRST

**One name advances: CB (Chubb).** Nine names go to the watch list under conditions. Eight are done for today.

CB is the only name in this run where the committee arrived at the same conclusion from directions that do not normally meet. The failed-breakout seat, the Wyckoff seat, the risk-arithmetic seat, the fundamentals seat, the setup-family seat and the structure-detection seat each ran their own test on their own fields, and each ended up at the same place: a large, quiet insurer resting exactly on its 50-day average, with a stop at a swing low that was actually defended, and a first target that pays 2.83 times the risk before price meets anything overhead. It is the only bracketed name in the eighteen whose reward is not measured through resistance. It is also, on the tape score, the weakest name in the set — rank 143 of 164, momentum 49.2, the only negative 20-day relative strength among the multi-seat names. Both of those things are true and the second is why four seats voted against it.

The nine holds are **watch-list entries only**. Every one of them failed on something specific and checkable, and each carries the observable that has to happen first. None of them is a soft buy, and none should be treated as one this morning.

For today's book, nothing needs doing. Three positions are held, all three are green, all three carry a stop written this morning, and the only structural problem on the book is a sector concentration breach in Healthcare that predates this run and is not made better or worse by anything the committee decided.

---

## WHAT WAS DIFFERENT TODAY

**1. No Layer 0 filter.** On PM instruction the full 164-name AQE universe went to the seats, against yesterday's filtered 44. Fifty names drew a nomination — 30.5% of the universe — 18 qualified, and the 20-name cap did not bind. Nothing was competitive on the way in.

**2. The challenge round actually moved votes.** This was not a rubber stamp. Seats withdrew their own Round-1 names, in writing, against their own R1 lines:

- **livermore** withdrew his entire XLV Key Price construction. TAK went 4 to 2, JNJ 3 to 2, and he conceded he had presented a 1.55% ATR reaction unit as a Pivotal Point: *"a 1.55% number I presented as tightness when it is one ordinary day's range."* He also cut CVX 4 to 3, withdrawing the group claim while keeping the trend read.
- **minervini** withdrew all four Round-1 nominations that failed a gate his own card serves — GNW, CVX, JNJ, CTVA. On CTVA: *"Steenbarger is right that I named a caution and priced nothing. There was no discount in my 4, and inventing one now would be worse than withdrawing."*
- **oneil** withdrew SLDE, his own solo conviction-4: *"My own C17 line makes more than 10% extended a rejection and I wrote 'late, not rejected' — that was my error, not a judgement call."*
- **thorp** withdrew NFLX, DOCS and GME after conceding detect-lens's finding that his reward numbers were measured into overhead supply. On GME: *"the ladder IS the broken structure, so the reward and the reason it is unreachable are the same field."*
- **raschke** withdrew NFLX: *"The setup I named does not exist on this chart. This is my clearest call of the ballot and it is against my own R1 line."*
- **elder-lens** withdrew UBS and **weis** withdrew WELL, both to abstain, both on the same reasoning: sizing a murky read down is not the sanctioned response, taking nothing is.

**3. Steenbarger measured the rank and found it hollow.** Conviction sum correlates **+0.907 with seat count** — the rank is 82% explained by how many seats filed. Against the fields that are supposed to discriminate it correlates **-0.319 with elder**, **-0.304 with structure**, **-0.026 with AQE rank**, -0.039 with momentum. Per-seat conviction runs *inverse* to headcount: the 7 single-seat names average 4.00 per seat, the 11 multi-seat names 3.18. Every single-seat name filed at exactly conviction 4, standard deviation 0.00, and not one seat in 32 filings used the top of its own scale. He calls that the signature of a qualification threshold, not seven independent agreements.

**4. detect-lens found bracket validity running inverse to trend order.** Nine of the eighteen carry a textbook moving-average stack; **six of those nine are bracket-INVALID**. Nine carry a disordered stack; **seven of those nine are bracket-VALID**. The mechanism is structural: a trend that has run leaves no support close enough beneath price to satisfy the gates, while a damaged chart has overhead supply directly above price that the engine converts into a target ladder. The three names trading below their own 200-day — NFLX, DOCS, GME — carry three of the four highest reward ratios in the set (DOCS 7.01, GME 4.99, NFLX 3.37), and that reward is distance to overhead resistance, not distance to profit. **All three PASSED.**

**5. Rogers found dispersion, not breadth.** Zero of the eighteen sit in a sector the engine rates "Momentum Building — Add". Fourteen read "Momentum Fading — Hold, Don't Add"; three read "Recovering From Weakness — Watch for Entry"; CTVA reads "Declining — Avoid". Financials is 7 of 18, Financials plus Healthcare is 11 of 18 (61%). His set-level point stands unanswered: `nomination_count >= 2` is a threshold calibrated on a filtered pool and it was carried unchanged onto an unfiltered one.

**6. The two macro seats disagree and the disagreement is not resolved.** Details in §1.

---

## 1. MACRO POSITION

**What the tape looks like today.** It is quiet and it is leaderless, and the calm is partly unmeasured. VIX is 14.32 with the term structure in contango — below the 15.0 line where selling premium beats chasing breakouts, and 74.6% away from the 25.0 level where protection is already expensive. Single-stock volatility is 35.19 against index volatility 14.32, a 20.87-point gap, with implied correlation at 9.54 — the 22.7th percentile. In plain terms: stocks are moving on their own news, so picking names is being paid and calling the index tells you little. Nothing mechanical is queued to sell: every equity trend-follower flip level sits 7.5% to 8.9% below spot (S&P 7757.75 vs 7132.90, Nasdaq 29587.5 vs 26968.69, Russell 2971.8 vs 2729.49, Dow 53752 vs 49690.12), and 0.0% of the 18 markets read sit at a positioning extreme. Breadth is genuinely neutral rather than broadening — the average stock actually *lost* 0.898% of ground to the index over five days (RSP/SPY change_5d_pct -0.898) while the 20-day and 60-day changes are flat (+0.072%, +0.277%). Underneath that, the intermarket tape is doing something specific: TLT -1.28% over five days and below its 20-day, HYG -0.83% and below its 20-day, IWM -1.54% against SPY +0.60% over twenty days (a 1.63-point spread), gold -2.93%, oil **+9.29%**. Rising rates, softening credit, narrowing tape, oil up.

**Where the two seats disagree, left unresolved.** **Crown** filed **BROADENING_CARRY at a 0.75x size multiplier with match_quality poor**, and declared its own artifact **DEGRADED** — a deliberate cut from the artifact's own 1.00 dial, because three of four positioning stages argue for less. Crown's own naming condition is contradicted by its own breadth field (`the_call` says BROADENING while `readings.breadth.regime` says neutral), and the dealer-gamma leg is not merely unmet but **unmeasurable**: `option_dealers.available = false`, coverage 0 of 2, so **R9 — the check for whether spot is sitting on a gamma flip — was not run at all.** Crown states it plainly: a skipped check must never look like a passed check. **Druckenmiller**, working from the same datapoints file and deliberately blind to Crown's prose, read **MODERATE** and put **INFLATION_SHOCK ahead of DISPERSION**, on cross-asset corroboration: WTI 91.72 is 17.69% above its flip, Brent +15.25%, copper +14.37%, wheat +22.08%, corn +20.63%, soybeans +13.13%, silver +7.28%, gold +4.90% — commodities uniformly bid — while **every** Treasury contract trades below its flip (ZT 102.625 vs 103.5761, ZF 105.68 vs 108.02, ZN 107.625 vs 110.98, ZB 108.69 vs 113.95) with the CTA rates signal at -0.4902. His argument against the leading scenario is that dispersion is *shrinking*: `gap_change_20d = -5.59`, more than five volatility points of compression in twenty days, and the file's own note says the gap only counts as a warning while it is still widening. He also declines the premium-selling invitation outright — selling index vol with zero visibility into dealer gamma at a 22.7th-percentile implied correlation is, in his words, selling the wrong instrument for the wrong reason. **Both seats independently flag the same thing as the number to watch: the dollar.** DX sits at 99.019, **0.64% below the 99.6482 level where trend funds turn from seller to buyer**, while speculators are already crowded long it. Druckenmiller names it as the kill switch for the entire commodity-leaning posture: if DX breaks 99.6482, the correct response is to reduce, not to reason about it. That level is itself sourced from Yahoo and he says it should be re-verified before it is acted on. **This brief does not settle which seat is right.** One says take the carry at three-quarter size; the other says take normal size but tilt to real assets and refuse the carry. They agree on the environment and disagree on the expression.

**So what, for this book.** Held names, one at a time. **BRZE** — no read from either macro seat. It sits at beta_30d 0.03, its sector (XLK) reads macro HEADWIND at -1.04, and the stock has run 23.7% above its 200-day: neither the reflation tilt nor the dispersion read touches it, and a 0.03 beta means the index does not touch it either. **HNGE** — pressured, mildly. It carries beta_30d 1.61, the only real market sensitivity on the book, and it sits in XLV, whose sector gate reads CAUTION on "RRG WEAKENING + macro caution" with a headwind score of -0.44. If either macro seat is right that credit is softening (HYG -0.83%, and Druckenmiller declares credit NOT_SERVED to him at all), HNGE is where it shows up first on this book. **V** — no read. beta_30d -0.04, XLF, and the position is 4.8% in the money against a stop 1.7% below spot; the macro read does not reach it before the stop does. **For today's candidates as a group:** both seats say the same thing about how to build — name by name, on stock-specific merit, never on an index call. That is exactly what the committee did, and it produced one advance. Druckenmiller's tilt (favour real-asset and commodity-linked earners, be careful with anything whose story needs cheap long-duration money) argues *against* most of what qualified: eleven of eighteen sit in Financials and Healthcare, and the one Energy name (CVX) was cut to a hold on participation, not on thesis.

---

## 2. SECTOR & THEMATICS

| ETF | Sector | Grade | Trend state | ROC20 | Entry gate | Why |
|---|---|---|---|---|---|---|
| XLV | Healthcare | DEPLOY | Momentum Fading — Hold, Don't Add | +5.36% | **CAUTION** | RRG WEAKENING + macro caution |
| XLE | Energy | DEPLOY | Momentum Fading — Hold, Don't Add | +11.11% | WATCH | Grade DEPLOY / RRG WEAKENING / macro neutral |
| XLK | Technology | HOLD | Momentum Fading — Hold, Don't Add | +0.35% | **CAUTION** | Macro headwind (-1.04) |
| XLF | Financials | HOLD | Momentum Fading — Hold, Don't Add | +1.30% | **CAUTION** | Macro headwind (-0.90) |
| XLC | Comm Services | HOLD | Momentum Fading — Hold, Don't Add | +1.98% | **CAUTION** | Macro headwind (-1.04) |
| XLI | Industrials | TURNING | Recovering From Weakness | -5.52% | **BLOCKED** | HEADWIND macro + LAGGING RRG |
| XLY | Cons Discretionary | TURNING | Recovering From Weakness | -1.39% | **BLOCKED** | HEADWIND macro + LAGGING RRG |
| XLP | Cons Staples | TURNING | Recovering From Weakness | +0.18% | WATCH | Grade TURNING / LAGGING RRG / macro neutral |
| XLRE | Real Estate | TURNING | Recovering From Weakness | -1.25% | WATCH | Grade TURNING / LAGGING RRG / macro neutral |
| XLU | Utilities | TURNING | Recovering From Weakness | -0.81% | WATCH | Grade TURNING / LAGGING RRG / macro neutral |
| XLB | Materials | AVOID | Declining — Avoid | +0.86% | **BLOCKED** | AVOID grade |

**Backward, to the macro read.** The sector table is the reflation tape written out name by name. Energy leads on twenty-day return by a wide margin (+11.11%, next best is Healthcare at +5.36%) — which is the same thing Druckenmiller is reading in WTI 17.69% above its flip and oil up 9.29% in five days. The three sectors whose earnings depend most directly on the cost and direction of long money — Industrials -5.52%, Real Estate -1.25%, Utilities -0.81% — are the three sitting in the LAGGING RRG quadrant, and TLT is falling (-1.28% over five days, below its 20-day). That is not a coincidence and it is the one place where the two macro seats' data agrees with the sector engine without argument. What the table does *not* support is any read of breadth: **every one of the eleven sectors reads either "Momentum Fading", "Recovering From Weakness" or "Declining"**, and five of eleven are gated CAUTION or BLOCKED on macro headwind alone. That matches RSP/SPY sitting 0.85% below its own 20-day average — the level Crown itself says "turns before the regime label does" — and it is why Crown's BROADENING label is contradicted by Crown's own breadth field.

**Forward, to today's output — and this is the uncomfortable sentence.** **Not one of the eighteen names the committee deliberated sits in a sector the engine rates "Momentum Building — Add".** Fourteen of the eighteen sit in "Momentum Fading — Hold, Don't Add", including all seven Financials and all four Healthcare names. Three sit in "Recovering From Weakness — Watch for Entry" (BBY, WELL, GME). One — CTVA — sits in "Declining — Avoid", and its single nominator named that caution in his own reason and then withdrew the name in Round 2. The advance, CB, sits in XLF: gate CAUTION, macro headwind -0.90, sector trend state "Hold, Don't Add", though XLF is the one sector in the LEADING RRG quadrant and DEEPENING. Steenbarger's F5 is the sharp version: 30 of 32 Round-1 filings never named the sector state at all, and where a seat did name it, it did not move the number. **The held book sits in the same place.** XLK is CAUTION on macro headwind (BRZE), XLV is CAUTION on RRG weakening (HNGE), XLF is CAUTION on macro headwind (V). All three held names are in sectors the engine says hold and do not add to. That is consistent with the book as it stands — nothing here argues for adding to any of the three.

---

## 3. HELD BOOK REVIEW

Source: today's AQE export `held_book` (`exported_at 2026-09-04 12:50:17 SGT`). AQE is the source of truth for this section.

**Book at a glance:** 3 positions · total exposure **$26,853.20** · beta-adjusted exposure **$21,068.46** · NAV-weighted beta (30d and 60d both) **0.7846** · loss per 1% gap **$210.68**. Gap scenarios: -3% → **-$632**, -5% → **-$1,053**, -7% → **-$1,475**, -10% → **-$2,107**.

**Sector concentration — a real breach, and it is named.** `sector_weights` in today's export: **XLV 49.01%**, XLF 28.21%, XLK 22.78%. The PM's morning note records XLV at 49.3%; the export computes 49.01% on today's marks. Either figure is a **breach of the 35% cap by roughly 14 percentage points**, carried by a single position (HNGE, $13,160 of $26,853 exposure). Nothing in today's committee output touches it: the one advance is XLF, and every XLV name in the deliberation set (JNJ, MDT, TAK, DOCS) is a hold or a pass. This breach is not resolved by anything in this brief.

### BRZE — $33.25 · +$402.02 · XLK
| | |
|---|---|
| Entry / qty | 31.0651 · 184 shares · opened 2026-08-21 |
| **Stop written this morning** | **31.0651 — raised to breakeven, position +6.2R** (was 30.80) |
| Targets on file | TP1 35.02 · TP2 38.85 |
| AQE state | sc_momentum 71.8 · elder 7.0 · structure 52.0 · mp FADING / DECELERATING · hl_state **HOLD** |
| Structure | ABOVE_STRUCTURE, ref 26.85 · ma20 30.71 · ma50 26.87 · ma200 24.71 · 23.7% above the 200-day |
| Risk | beta_30d 0.03 · ATR 1.55 · vol_30d_ann 65.1% · exposure $6,118 |
| QS | qs_signal **SKIP**, edge +7.7pp, not on the QS track. PM LENS check score 3 of 6, committee status UNSEEN (drew zero nominations). |

The stop is now at cost. Momentum is fading and decelerating while price sits 23.7% above its 200-day — the position is mature, and the breakeven stop is the appropriate expression of that. Divergence NONE, CHoCH still BULLISH (dated 2026-05-26), price above the 14-day VWAP at 31.51.
**Context:** no read. Its sector (XLK) is gated CAUTION on a -1.04 macro headwind, but at beta 0.03 the index is not what moves this name, and neither macro seat's tilt reaches it. Watch the stock, not the tape.

### HNGE — $90.76 · +$85.81 · XLV
| | |
|---|---|
| Entry / qty | 90.1682 · 145 shares |
| **Stop written this morning** | **86.23** (was 85.70) |
| Targets on file | none set |
| AQE state | sc_momentum 67.2 · elder 4.0 · mp FADING · hl_state **HOLD** · structure_shift RANGE |
| Structure | ma20 89.32 · ma50 85.03 · ma200 56.53 |
| Risk | **beta_30d 1.61 — the only real market sensitivity on the book** · ATR 4.54 · exposure **$13,160 (49.01% of the book)** |
| QS | not scored in PM LENS (not in the 162-row daily list). No QS reading served — declared gap, not a NONE. |

Barely above water at +$85.81 on a $13,160 position, with the stop 5.0% below spot. This is the position that carries the concentration breach and it is the position that carries the book's beta.
**Context:** pressured. XLV's entry gate is CAUTION on "RRG WEAKENING + macro caution" (headwind -0.44) and the sector reads "Momentum Fading — Hold, Don't Add" despite a DEPLOY grade. At beta 1.61 this is also the name that moves most if either macro seat is right about credit softening (HYG -0.83% and below its 20-day; Druckenmiller has no credit read served at all).

### V — $378.75 · +$346.01 · XLF
| | |
|---|---|
| Entry / qty | 361.4496 · 20 shares |
| **Stop written this morning** | **372.19** (was 371.45) |
| Targets on file | none set |
| AQE state | sc_momentum 61.0 · elder 3.0 · mp FADING · hl_state **TIGHTEN** · structure_shift RANGE · div_state **BEARISH** · knn_prob 0.80 |
| Structure | ma20 371.10 · ma50 362.30 · ma200 333.82 |
| Risk | beta_30d -0.04 · ATR 6.56 · exposure $7,575 |
| QS | not scored in PM LENS (not in the 162-row daily list). No QS reading served — declared gap, not a NONE. |

AQE reads **TIGHTEN**, and the stop written this morning at 372.19 does exactly that — 1.7% below spot, just under the 20-day at 371.10. Momentum fading, elder down to 3.0, and a bearish divergence on the record. The position is +4.8% and the stop protects most of it.
**Context:** no read. XLF is gated CAUTION on macro headwind (-0.90) but sits LEADING/DEEPENING on the RRG; at beta -0.04 the macro read does not reach this position before the stop does.

**One book-level note carried from both macro seats:** a held-book name reports earnings on **Tuesday 8 September**. Which one is not served in today's inputs. Any risk added between now and then sits inside that window.

---

## 4. REPEAT WATCH

| Ticker | Date Appeared | % vs last COB | State |
|---|---|---|---|
| **NFLX** | 2026-08-31 | — (first appearance) | ADVANCE |
| **NFLX** | 2026-09-04 | +1.16% | PASS |
| **SLDE** | 2026-08-31 | — (first appearance) | HOLD-FOR-CONDITIONS |
| **SLDE** | 2026-09-04 | +5.32% | PASS |
| **UBS** | 2026-08-31 | — (first appearance) | ADVANCE |
| **UBS** | 2026-09-04 | +1.46% | HOLD-FOR-CONDITIONS |

Three names return from the 2026-08-31 set inside the five-session window. All three moved up against the last close and all three were **downgraded** by today's committee: NFLX from ADVANCE to PASS (+1.16%), SLDE from HOLD-FOR-CONDITIONS to PASS (+5.32%), UBS from ADVANCE to HOLD-FOR-CONDITIONS (+1.46%). In each case the downgrade came from a seat withdrawing its own prior case, not from the price moving away. NFLX was withdrawn by both of its Round-1 nominators (raschke on setup family, thorp on conditioned reward). SLDE was withdrawn by its only nominator on his own extension rule. UBS was withdrawn to abstain by elder-lens on an unevaluable trend leg.

---

## 5. QS LIST

The QS track carries **9 rows** in today's PM LENS scoring (`on_qs = true`). The universe build recorded `qs 7` as a source-list count — the two do not reconcile and the discrepancy is declared, not resolved. **The QS track contributed zero names to the deliberation set on its own** (Rogers, set-level finding); the one QS name that qualified did so through the elder list.

| Ticker | Sector | QS signal | QS edge | PM LENS checks | Committee status |
|---|---|---|---|---|---|
| **CB** | Financials | **WATCH** | +10.7pp | 2/6 | **DELIBERATED — 2 seats, conviction sum 8 → ADVANCE** |
| STGW | Comm Services | **STRONG** | +11.7pp | 1/6 | UNSEEN — zero nominations |
| HOOD | Financials | SKIP | +10.7pp | 3/6 | UNSEEN — zero nominations |
| ORI | Financials | WATCH | +10.7pp | 2/6 | UNSEEN — zero nominations |
| EBC | Financials | SKIP | +10.7pp | 2/6 | UNSEEN — zero nominations |
| FE | Utilities | WATCH | +10.7pp | 1/6 | UNSEEN — zero nominations |
| NEE | Utilities | WATCH | +10.7pp | 1/6 | UNSEEN — zero nominations |
| EVRG | Utilities | WATCH | +10.7pp | 1/6 | UNSEEN — zero nominations |
| ZS | Technology | WATCH | +7.7pp | 1/6 | UNSEEN — zero nominations |

**Read the QS edge with care.** PM LENS's own rule note states it plainly: QS edge is positive on 100% of the 162 scored rows, so it cannot discriminate and it is ranking/display only. The one row worth the PM's eye is **STGW — the only STRONG signal on the track, at the highest edge (+11.7pp), and the committee never looked at it** (it drew one nomination from seow in Round 1 and did not qualify). Three Utilities names carry WATCH, in the sector gated WATCH with a LAGGING RRG — consistent, and not a reason to act.

---

## 6. PM LENS

| Ticker | Sector | Checks | Lenses strong | SC-mom | Elder | Structure | QS edge | Failed check | Committee saw it? |
|---|---|---|---|---|---|---|---|---|---|
| **UBS** | Financials | **5/6** | 2/6 | 76.5 | 9.0 | ABOVE_STRUCTURE | +7.7pp | lens | yes — deliberated |
| **GDDY** | Technology | **5/6** | 2/6 | 74.6 | 10.0 | BULLISH_BOS | +7.7pp | lens | **NO — zero nominations** |
| **GEN** | Technology | **5/6** | 2/6 | 72.5 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **BSBR** | Financials | **5/6** | 4/6 | 72.4 | 10.0 | BULLISH_BOS | +7.7pp | lens | yes — deliberated |
| **BOX** | Technology | **5/6** | 2/6 | 72.3 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **MFG** | Financials | **5/6** | 2/6 | 72.0 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **RELY** | Technology | **5/6** | 4/6 | 70.5 | 9.0 | BULLISH_BOS | +7.7pp | lens | **NO — zero nominations** |
| **DUOL** | Technology | **5/6** | 1/6 | 70.1 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **SONY** | Technology | **5/6** | 3/6 | 70.0 | 10.0 | BULLISH_BOS | +7.7pp | lens | **NO — zero nominations** |
| **GNW** | Financials | **5/6** | 4/6 | 69.6 | 9.0 | BULLISH_BOS | +7.7pp | lens | yes — deliberated |
| **PRCH** | Technology | **5/6** | 2/6 | 69.1 | 8.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **AAPL** | Technology | **5/6** | 2/6 | 68.4 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **WAY** | Technology | **5/6** | 4/6 | 63.0 | 10.0 | BULLISH_BOS | +7.7pp | lists | **NO — zero nominations** |
| **TMUS** | Communication Services | **5/6** | 4/6 | 61.1 | 10.0 | BULLISH_BOS | +7.7pp | lists | **NO — zero nominations** |

**Coverage gap — 11 PM LENS name(s) the committee never saw: GDDY, GEN, BOX, MFG, RELY, DUOL, SONY, PRCH, AAPL, WAY, TMUS.** These drew zero nominations, so they appear in no other section of this brief. Not a verdict, not an error — a name the PM's own checks flagged and the committee did not look at.

**Reading it.** Six checks; the flag threshold is 5 of 6. Fourteen names cleared it out of 162 scored. The binding check across the whole universe is **C6_lens** — "lens count ≥4/6 strong AND coil strong AND insti_money strong" — which only **6 of 162** rows passed; every one of the fourteen flagged names failed on exactly that check, and two failed on the lists check instead. For context on how tight the funnel is: C1_lists passed 58 of 162, C4_structure 72, C3_sector 78, C5_vwap 78, C2_rs 128.

**Three of the fourteen were deliberated: UBS, BSBR, GNW.** All three came back HOLD-FOR-CONDITIONS. That is the PM's own checklist and the committee landing in different places on the same three names, which is worth knowing but is not a contradiction — the lens is a visibility layer and explicitly not a gate.

**Eleven names the committee never looked at.** GDDY, GEN, BOX, MFG, RELY, DUOL, SONY, PRCH, AAPL, WAY, TMUS. Each of these passed 5 of the PM's 6 checks and drew zero nominations from any of the nine nominating seats. They appear nowhere else in this brief. They are not verdicts and they are not errors — they are names the PM's own checks flagged and the committee did not look at. Seven of the eleven are Technology; XLK is gated CAUTION on macro headwind. Two of them were nominated by a single seat and fell below the qualification threshold (GDDY by livermore at conviction 3, AAPL by minervini at conviction 3) — the rest drew nothing at all.

---

## 7. SHORTLIST — TICKER CARDS

**Purity check: invariance PASS.** `crowding audit: top-5 by seats [BBY(V), GNW(V), NFLX(V), CB(V), CVX(-)] are 80% bracket-valid vs 56% across all 18 qualifiers (gap +24%). No sign that consensus is tracking bracket availability today.` (top-rate 80.0% vs base-rate 55.6%, gap +24.4pp, warn flag false).

Ranking key: `seat_count > conviction_sum > srm_entry_gate > thematic_support > sc_momentum`. Steenbarger's F2 stands against that key and is reproduced here rather than argued with: conviction sum correlates +0.907 with seat count and -0.319 with elder, -0.304 with structure, -0.026 with AQE rank. **The rank order below is a headcount order.** Read the cards, not the order.

---

### ✅ ADVANCE — CB (Chubb Ltd) · Financials · $348.25

**6 support · 4 oppose · 1 abstain · median support conviction 4 · verdict conviction 4**

| | |
|---|---|
| Bracket | **VALID** — stop **342.22** (swing_low_2), risk **1.73%**, rr 4.37, **rr_tp1 2.83** |
| Tape | rank **143 of 164** · sc_momentum **49.2** (lowest in the set) · structure 44.2 · shift RANGE · rs_spy_20d **-2.23** |
| Structure | ma20 343.20 **below** ma50 347.72; ma50 > ma100 336.19 > ma200 326.12; price **on** the 50-day (sma_dist 0.15%) |
| Effort | day_vol 1.20 · ATR 5.88 = **1.69% of price, the calmest name in the set** · flow 53.9 · energy 68.1 |
| Elder | 8.0, series [3, 0, 3, 3, 8], pattern INTERRUPTED · mp BUILDING / ACCELERATING · div NONE/0 |
| Lens | leadership ok · coil **strong** · insti_money **strong** · structure ok · resistance ok · sector **strong** · 0 warnings |
| Fundamentals | pe **12.24** · peg 0.5062 · net_margin 18.06% · piotroski 7 · int_cov 14.12 · eps_g **+13.0%** on rev_g +6.5% · payout 13.8% |
| **QS** | **on the QS track — signal WATCH, edge +10.7pp.** PM LENS 2 of 6. |

**Why six seats from six directions landed on the same name.**

- **thorp (5, raised from 4)** — risk arithmetic. *"All four averages sit BELOW price 348.25, so nothing overhead conditions the ladder: TP1 at 2.83R is open air."* Gapped loss 1.98R plus 0.25R cost leaves +0.60R net. It is the only bracketed name in the eighteen whose reward is not measured through resistance, and **the only surviving R3 pass** after he withdrew NFLX, DOCS and GME. He raised his conviction because *"the challenge round removed the objection instead of adding one."*
- **raschke (5)** — setup family. *"The packet's one genuine C20 double stop point."* Price resting on its 50-day is the higher low inside an intact up-structure; invalidation and trigger sit close together by construction, which is her lowest-risk location.
- **lynch (4)** — fundamentals. *"The cleanest fundamental profile of the eighteen."* pe 12.24, peg 0.5062 on the 0.5 bargain line, earnings growing at twice sales through underwriting, which for a P&C insurer is the right way round.
- **wyckoff (4)** — role reversal. Price sits on the ma50 axis; danger point is the swing_low_2 at 342.22, *"the only bracket here paying above 2R before it meets supply."*
- **weis (3, new in Round 2)** — failed breakout. He did not file this in Round 1 and says so: *"a failed break of the ma50 axis inside an intact uptrend with a defended swing low beneath it."* Three sessions at elder 3 or below including a zero, no downward follow-through, then 8.
- **detect-lens (3)** — structure detection. *"Mechanically the best-shaped risk in the set: bracket VALID on a swing_low_2 stop — a level actually defended, not an average."*

Six different tests. One name. Note what none of them claims: not one supporter argues the tape is strong.

**Strongest opposing case, quoted verbatim and attributed.** From **oneil**, who voted OPPOSE at conviction 3: *"Step1 fails on the group test rather than the label: rank 143 of 164, sc_mom 49.2, rs_spy_20d -2.23. C9 buys the No.1-3 name in its group and this is the one the group leaves behind... Step2 fails: RANGE with ma20 343.20 under ma50 347.72, no base completed. Step3 day_vol 1.20, under 1.40."* And from **livermore**, OPPOSE 3: *"structure_shift RANGE with sma_distance_pct 0.15 — price is sitting on its own average and nothing has broken. That is the reaction itself, and C5 forbids buying it; there is no new high to confirm anything."* **minervini**, OPPOSE 3, adds the stage read: *"Not a stage-2 candidate... rs_spy_20d -2.23 is the only negative 20-day RS among the multi-seat names."* **elder-lens** opposed at 2 on a single label — the elder pattern reads INTERRUPTED, which his card treats as a failed trend leg, and he wrote the reversal condition himself: *"If INTERRUPTED is a soft label rather than a failed leg, this is a conviction-3 support."*

**seow abstained** and the reason is a data gap, not a judgement: *"ma_20 343.20 sits 1.30% BELOW ma_50 347.72 — the exact case where a 40-period average decides direction, and my card forbids substituting the 50 for it."* His falsifier: ma_40 or CCI being served would settle the name in one reading.

**Falsifiers the committee agreed on:** a close below **342.22** ends it (thorp, raschke, weis, wyckoff all name that level). detect-lens adds: ma20 343.20 continuing to fall away beneath ma50 turns the short-end roll into a genuine down-cross.

**Context:** headwind, mild. XLF is gated CAUTION on a -0.90 macro headwind and reads "Momentum Fading — Hold, Don't Add", though it is the one sector sitting LEADING and DEEPENING on the RRG. Neither macro seat's tilt argues for a P&C insurer specifically; Druckenmiller's reflation lean is neutral here (an insurer earns on float, which rising short rates help) but that connection is not served by any field in this run, so it is stated as **no read** rather than as support.

---

### ⏸ HOLD-FOR-CONDITIONS — nine names, watch list only

These are **not** soft buys. Each failed on something specific. Each carries the observable that has to happen before it is tradeable. Nothing below is staged.

---

#### BBY (Best Buy) · Consumer Discretionary · $87.49 — 7 support, 4 oppose, **median support conviction 2**

**BBY drew the most support in the run and still did not advance. It missed on conviction, not on headcount.** Seven seats voted for it; five of those seven filed at conviction 2, and the two nominators who had filed 3s in Round 1 (weis, wyckoff) came down to 2. Steenbarger measured it: BBY tops the set at 4 seats and conviction sum 12 with **the lowest mean per-seat conviction on the board (3.0 in R1)** and the second-lowest structure score (50.5).

| | |
|---|---|
| Bracket | VALID — stop 83.75 (ma cluster), risk 4.27%, rr 2.37, **rr_tp1 0.74** — the first structural target pays less than 1R |
| Tape | rank 47 · sc_mom 71.2 · structure **50.5** (second-lowest in the set) · shift **RANGE** — nothing has broken · sma_dist 4.46% |
| Effort | **day_vol 0.79 — below normal** · flow 82.9 · energy 84.9 |
| Elder | 7.0, [0, 0, 3, 5, 7], ACCUMULATION_BASE · mp BUILDING/ACCELERATING · div BULLISH/0 |
| Lens | **lens_positive 0 — not one of six reads strong**; resistance **warn** |
| Fundamentals | pe 14.53 · yield 4.37% · piotroski 8 · int_cov 40.87 · **eps_g +17.4% on rev_g +0.4%** |
| QS | qs_signal **SKIP**, edge +7.7pp, not on the track. PM LENS 1 of 6. |

The case for it is a coil: was_squeezed true, vcp_tightness 69.3, and a dry-up in volume before a break. The case against is that the break has not happened and the first target pays 0.74R. lynch's fundamental note is the one nobody on the tape said: *"eps_g +17.4% sits on rev_g +0.4%. Earnings are growing 43x faster than sales. That is margin and share count, not a business getting bigger."*

> **Condition: a close through the confirmed pivot high (base top ≈ 90.26), flipping structure_shift from RANGE to BULLISH_BOS, on day_vol ≥ 1.40.** Four seats independently named a version of this line — detect-lens (day_vol > 1.2), livermore (> 1.0), oneil (≥ 1.40 within 10 sessions, "converts this to a SUPPORT at 4 the same day"), wyckoff (> 1.5 through 90.26). Until that print, this is a watch.

**Context:** headwind. XLY is **BLOCKED** — "HEADWIND macro + LAGGING RRG", ROC20 -1.39%, macro headwind -1.50, the worst headwind score of the eleven sectors. Neither macro seat's tilt supports a US retailer.

---

#### GNW (Genworth) · Financials · $10.38 — 4 support, 7 oppose, conviction 3

The densest agreement in Round 1 (3 seats, all at conviction 4) and the clearest reversal in Round 2. Rogers went hunting for the hidden flaw in the most confidently held name and found it; minervini then withdrew.

| | |
|---|---|
| Bracket | VALID — stop 10.14 (fib_618), risk **2.31%**, rr 2.29, rr_tp1 1.29 |
| Tape | rank 64 · sc_mom 69.6 · structure 68.4 · shift **BULLISH_BOS** · sma_dist 5.69% (unextended) |
| Effort | **day_vol 2.29 — 229% of its own 20-day average**, second-heaviest in the set |
| Elder | 9.0, [6,6,6,7,9] · mp BUILDING/ACCELERATING · **div BEARISH, div_bear_count 2 — uncited by all three R1 nominators** |
| Lens | **lens_positive 4, lens_warnings 0** — coil, structure, resistance, sector all strong |
| Fundamentals | **rev_g -10.9%, eps_g -20.3%** · fwd_peg 8.3802 · no dividend · piotroski 8 |
| QS | qs_signal SKIP, edge +7.7pp. PM LENS **5 of 6 — flagged**, failed only C6_lens. |

detect-lens still calls it *"the only name in 18 where every mechanical test agrees"* on the chart. lynch calls it *"the widest price-vs-fundamentals gap in the set"*: a shrinking insurer with no dividend underneath it. Steenbarger's F11 is the technical objection nobody priced — **the stop at 10.14 sits 1.81% ABOVE the ma20 at 9.96**, so an ordinary pullback to the rising 20-day stops the trade out before the trend structure is even tested. detect-lens, who supports the name, conceded that point in his own self-counter.

> **Condition: two consecutive quarters of positive revenue growth** (lynch, minervini and oneil all name a version of this; oneil specifies EPS up ≥ +20% YoY with sales turning positive, and says he reverses to SUPPORT on the same chart). **On the tape side, the shorter check: day_vol holding above 1.0 for three consecutive sessions** — detect-lens's own falsifier is that day_vol falling back under 1.0 for three sessions makes the single 2.29 bar a one-day event rather than accumulation.

**Context:** headwind. XLF gated CAUTION, macro headwind -0.90, "Momentum Fading — Hold, Don't Add".

---

#### MET (MetLife) · Financials · $99.23 — 5 support, 5 oppose, 1 abstain, conviction 3

The most evenly split name in the run. On trend order, confirmed break, lens count and effort, detect-lens grades it *"the second-best mechanical read in the set after GNW"*.

| | |
|---|---|
| Bracket | **INVALID** — no structural support passes the three gates · atr_fallback_stop 97.34 (1.90% of price) |
| Tape | rank 65 · sc_mom 69.4 · structure 71.6 · shift BULLISH_BOS · sma_dist 5.48% |
| Effort | day_vol 1.28 · flow 86.8 · energy 81.5 |
| Elder | 7.0, [6,0,0,5,7], INTERRUPTED · mp BUILDING/ACCELERATING · div NONE/0 |
| Lens | lens_positive 4, 0 warnings · **rs IN-LINE, rs_spy_20d -1.32** |
| Fundamentals | **eps_g -19.7% on rev_g +10.2%** — margin compression · net_margin 4.61%, thinnest of any financial here · fwd_peg 1.73 |
| QS | qs_signal NONE, edge +7.7pp. PM LENS 3 of 6. |

detect-lens's set-level finding lands squarely here: the cleaner the stack, the less likely a valid stop exists. **thorp abstained** — no target ladder is served, so his reward test is unevaluable and he declines to size rather than guess.

> **Condition: a served structural stop level with rr_tp1 above 2.25R** (thorp's own falsifier — the exact thing missing today). **Alternatively, on the tape: rs_spy_20d turning positive with rs_down_day_20d above 0.25 while the 6.3% base holds** — minervini says that clears his criterion 8 and he would file it at 4.

**Context:** headwind. XLF gated CAUTION on macro headwind. A life insurer's earnings are pressured, not helped, by the reflation tilt Druckenmiller reads — but no field in this run tests that link, so it is stated as an observation, not a signal.

---

#### CVX (Chevron) · Energy · $211.29 — 3 support, 7 oppose, 1 abstain, conviction 3

The one Energy name in the set, in the one sector with double-digit twenty-day momentum (+11.11%) and the only sector gate above CAUTION. It was cut on participation, not on thesis.

| | |
|---|---|
| Bracket | **INVALID** — no structural support passes the gates · atr_fallback_stop 207.38 (1.85%) |
| Tape | rank 79 · sc_mom 66.9 · structure **83.2** · shift BULLISH_BOS · **sma_dist 10.96% — third-most extended in the set** |
| Effort | **day_vol 0.84 — below normal on the bar the break is claimed** · flow 51.3 |
| Elder | 10.0, [3,7,10,10,10], ACCELERATION · mp STRONG/ACCELERATING · div BEARISH/1 |
| Lens | lens_positive 4 — leadership, structure, resistance, sector strong; **coil warn** |
| Fundamentals | rev_g -4.6%, **eps_g -31.9%** · fcf_yld 6.42% positive through a -31.9% year · payout 67.3% · d/e 0.1953 |
| QS | qs_signal SKIP, edge +7.7pp. PM LENS 4 of 6. |

lynch is the strongest supporter and reads it as a cyclical, deliberately inverted: *"a HIGH P/E on trough earnings is the entry, a LOW P/E on peak earnings is the exit... A cyclical that funds its dividend and its balance sheet at the bottom of the cycle is a cyclical you can wait in."* Rogers's timing objection is the counterweight: *"A break of structure that nobody turned up for is not a break, it is a drift."* minervini withdrew here on his own rule — day_vol 0.84 against a C6 that requires expansion. **thorp abstained** on the missing target ladder.

> **Condition: a pullback that holds ma20 at 202.14, followed by a close to new highs on day_vol ≥ 1.40.** Five separate seats — minervini, oneil, raschke, weis, wyckoff — independently wrote that same shape as the thing that would reverse them. Entry 10.96% extended, on below-normal volume, is not it.

**Context:** the only genuine macro tailwind in the whole shortlist. XLE is the strongest sector on the board (ROC20 +11.11%, gate WATCH, macro flag NEUTRAL), and Druckenmiller's reflation read — WTI 17.69% above its flip, oil +9.29% in five days — points directly at it. That tailwind is exactly why it is worth waiting for the entry rather than chasing this one.

---

#### JNJ (Johnson & Johnson) · Healthcare · $278.43 — 3 support, 6 oppose, 2 abstain, conviction 2

The name where a seat wrote down the flaw and nominated anyway — then, in Round 2, priced it.

| | |
|---|---|
| Bracket | **INVALID** — atr_fallback_stop 272.77 (2.03%) |
| Tape | rank 50 · sc_mom 70.7 · structure 74.7 · shift BULLISH_BOS · sma_dist 6.61% (unextended) |
| Effort | **day_vol 0.92 — below normal on the break bar** · flow 67.1 |
| Elder | 10.0, [3,0,6,9,10], ACCELERATION · mp BUILDING/ACCELERATING · div BEARISH/1 |
| Lens | lens_positive 4; **insti_money warn** |
| Fundamentals | pe 32.19 · **fwd_peg 3.21, past the 2.0 red-flag line** · fcf_yld 2.79%, below the 5% fail line · piotroski 8 · net_margin 21.48% |
| QS | qs_signal NONE, edge +7.7pp. PM LENS 4 of 6. |

livermore cut 3 to 2 with the clearest line of the day on the difference between flagging and pricing: *"I flagged the participation and did not price it. Steenbarger is right that a flag which costs nothing is not a flag; this is what pricing it looks like."* lynch refuses the headline growth number: an 88.9% single-year EPS move on 6.05% revenue growth is a base effect off a prior-year charge, and feeding it into a PEG formula manufactures a "fabulous" reading that is fiction.

> **Condition: a close above the break bar's high on day_vol ≥ 1.40 within 10 sessions** (oneil — "converts this to SUPPORT at 4"). minervini sets the same shape at ≥ 1.2; wyckoff adds that div_bear_count should return to 0.

**Context:** headwind. XLV is gated CAUTION on "RRG WEAKENING + macro caution" and the book already carries 49% XLV exposure through HNGE. Adding a second Healthcare name would deepen a breach, not diversify it.

---

#### UBS (UBS Group) · Financials · $55.70 — 3 support, 5 oppose, 3 abstain, conviction 2

Was ADVANCE on 2026-08-31. Down to HOLD today, +1.46% against that close, and the downgrade came from a seat withdrawing rather than from price.

| | |
|---|---|
| Bracket | **INVALID** — atr_fallback_stop 54.79 (1.63% — the tightest volatility unit in the set, on a line nothing has defended) |
| Tape | rank **15** — the second-highest AQE rank in the set · sc_mom 76.5 · structure 73.7 · shift ABOVE_STRUCTURE |
| Effort | day_vol 1.30 · **flow 96.1 — the highest money flow in the set bar SLDE's 100.0** |
| Elder | 9.0, [9,9,4,6,9], CORRECTION_REENTRY · **mp FADING / DECELERATING — the only doubly-negative momentum state in the set** |
| Lens | lens_positive 2 |
| Fundamentals | pe 18.50 · eps_g +54.7% on rev_g -0.5% · bank-structure ratios (altman_z -0.26, d/e 4.21) are **not** distress readings |
| QS | qs_signal NONE, edge +7.7pp. PM LENS **5 of 6 — flagged**, failed only C6_lens. |

**elder-lens withdrew his own Round-1 nomination to abstain**, and the reasoning is the run's cleanest statement of discipline: *"In R1 I wrote 'nothing settles it. Taken small.' C22 says sizing the read down is NOT the sanctioned response to a murky tape — the sanctioned response is to take nothing."* **lynch also abstained**: he has no CET1 and no NPL ratio, so his balance-sheet toolkit does not run on a bank at all. detect-lens's set-level warning applies hard here: the 1.63% fallback stop is one ordinary day's range on a line nobody has defended, which makes UBS look *cheaper* on risk than names with real structural stops. It is not.

> **Condition: mp_state turning back to BUILDING or STRONG with mp_accel_state ACCELERATING, while price holds above ma20 54.05.** livermore, seow and raschke each name that same reversal; raschke adds day_vol above 1.3 out of the 5.7% base. Alternatively oneil's: day_vol ≥ 1.40 on a close through the base high — *"I would file it at 4 that day."*

**Context:** headwind. XLF gated CAUTION on macro headwind -0.90. Note also that a Swiss bank is directly exposed to the dollar level both macro seats flagged; that link is not served by any field in this run, so it is a watch item, not a read.

---

#### MDT (Medtronic) · Healthcare · $93.10 — 5 support, 6 oppose, conviction 2

A solo conviction-4 nomination in Round 1 (wyckoff) that drew four more supporters in Round 2 and still lost the count.

| | |
|---|---|
| Bracket | VALID — stop **89.73 (ma200)**, risk 3.62%, rr 2.01 — **clears the ≥2.0 gate by 0.01** · **rr_tp1 0.48** |
| Tape | rank 72 · sc_mom 68.6 · structure 74.7 · shift RANGE · sma_dist 7.68% |
| Structure | **ma100 83.07 sits BELOW ma200 89.73 — the long end is inverted** · ma20 91.38 > ma50 86.46 · price 3.8% above a just-reclaimed 200-day |
| Effort | day_vol 0.96 · **flow 46.1 — second-lowest in the set** · energy 84.9 |
| Elder | 7.0, [3,0,6,6,7], INTERRUPTED · mp BUILDING/ACCELERATING |
| Lens | lens_positive 3, **lens_warnings 2 — leadership warn, insti_money warn** |
| Fundamentals | pe 22.76 · fwd_peg 3.20 · **eps_g +3.31% on rev_g +8.43% — margin compression**, the mirror image of CB · payout 69.7% |
| QS | qs_signal SKIP, edge +6.7pp. PM LENS 2 of 6. |

The whole case rests on a 200-day reclaim that has just happened and has not been retested. lynch declines to read the served current_ratio at all (0.1506 is below FMP's own quick_ratio of 0.1706 for the same period — arithmetically impossible) and grades the name QUALITY_CONCERN: *"the Stalwart is fully valued."*

> **Condition: a close through the range high on day_vol ≥ 1.40, with the 200-day at 89.73 holding as support on the retest** (oneil). Every supporter names the same invalidation from the other side: **a close back below 89.73 ends the read entirely** (seow, weis, wyckoff, raschke all name that level).

**Context:** headwind. XLV gated CAUTION; the book is already 49% XLV.

---

#### BSBR (Banco Santander Brasil) · Financials · $6.02 — 3 support, 8 oppose, conviction 2

| | |
|---|---|
| Bracket | VALID — stop 5.82, risk 3.32%, rr 2.75, **rr_tp1 0.05 — the first structural target is effectively at the entry price** |
| Tape | rank 35 · sc_mom 72.4 · structure 81.1 · shift BULLISH_BOS · sma_dist 9.24% |
| Structure | **long end inverted: ma50 5.51 < ma100 5.57 < ma200 5.93.** Price has only just reclaimed the 200-day, by 1.5% |
| Effort | day_vol 1.52 · flow 78.9 · energy 79.8 |
| Elder | 10.0, [7,4,1,7,10], INTERRUPTED · mp BUILDING/**DECELERATING** |
| Lens | **lens_positive 4, lens_warnings 0** |
| Fundamentals | div_yld **7.58%** · rev_g +17.5%, eps_g -4.6% · BRL reporter, USD ADR market cap · bank-structure ratios are not distress |
| QS | qs_signal NONE, edge +7.7pp. PM LENS **5 of 6 — flagged**, failed only C6_lens. |

Rogers's rr_tp1 finding lands hardest here: at 0.05R the first structural resistance sits essentially at the entry, while the quoted 2.75 is a TP2 number. lynch grades it QUALITY_CONCERN specifically on the dividend — *"the dividend is the problem"* — and cannot split the Brazilian JCP payout from ordinary dividends.

> **Condition: ma50 and ma100 crossing back above ma200 while price holds 5.93** — the reclaim actually completing. detect-lens, minervini, seow and oneil each name that same repair. Until the 50/100/200 sequence is in rising order, the "reclaim" is one bar old.

**Context:** headwind. XLF gated CAUTION. An emerging-market bank ADR is also directly exposed to the DX 99.6482 tripwire both macro seats named — a dollar break upward is a headwind to this name specifically, though no field in this run measures it.

---

#### WELL (Welltower) · Real Estate · $241.09 — 2 support, 7 oppose, 2 abstain, conviction 2

The least extended name in the set (sma_dist 1.79%) and the least resolved.

| | |
|---|---|
| Bracket | VALID — stop 234.11, risk 2.90%, rr 2.02 — **clears the ≥2.0 gate by 0.02** · **rr_tp1 0.28** |
| Tape | rank 103 · sc_mom 63.5 · structure 60.0 · shift RANGE |
| Structure | **ma20 236.90 and ma50 236.86 have converged to within $0.02 — a dead-flat 20/50** over ma100 224.15 > ma200 210.71 |
| Effort | **day_vol 0.83 — below normal** · flow 81.6 |
| Elder | 9.0, **[4, 0, 8, 3, 9] — no rhythm at all** · pattern INTERRUPTED · mp BUILDING/ACCELERATING |
| Lens | lens_positive 2 — leadership and insti_money strong |
| Fundamentals | **CANNOT_JUDGE** — REIT; pe 124.92 and peg 15.97 are GAAP-depreciation artifacts, and FFO/AFFO are not served |
| QS | qs_signal NONE, edge +7.7pp. PM LENS 1 of 6. |

**weis withdrew his own Round-1 nomination to abstain**: *"Steenbarger F17 credited me with pricing an absent precondition; the completion of that discipline is withdrawal, not a preserved 2."* **lynch abstained** — every valuation test he owns is denominated in the wrong unit for a REIT.

> **Condition: ma20 and ma50 separating upward into rising order, with a break to new highs on day_vol ≥ 1.40 and rs turning LEADER** (oneil). Four seats name the same separation. A dead-flat 20/50 on 0.83 volume is a coil that has not resolved in either direction — and raschke's falsifier says a downward resolution is itself directional information.

**Context:** headwind. XLRE is gated WATCH with a LAGGING RRG and ROC20 -1.25%, and Druckenmiller's read is specifically to be careful with anything whose story needs cheap long-duration money. TLT is falling (-1.28% over 5 days, below its 20-day). A healthcare REIT is the clearest example of that caution in this set.

---

### ❌ PASS — eight names, done for today

---

**NFLX · Comm Services · $82.67 — 0 support, 11 oppose.** Unanimous, and both of its Round-1 nominators did the opposing. **raschke** withdrew: *"NFLX is not making fresh highs... Reclassified, this fits none of my four types."* **thorp** withdrew: conditioning the reward at the overhead ma200 turns his R1 net margin from +0.59R to **-0.66R**. detect-lens's structural read is the reason: price 82.67 is **5.0% below its own ma200 at 87.04** with the long end fully inverted (ma50 75.29 < ma100 81.35 < ma200 87.04). The 3.37 reward ratio measures the distance up into supply. QS: signal SKIP, edge +7.7pp; PM LENS 3 of 6. *Context: XLC gated CAUTION on macro headwind -1.04.*

**GME · Consumer Discretionary · $19.23 — 1 support, 10 oppose.** The most broken chart in the packet: fully inverted stack (18.44 < 20.30 < 21.64 < 22.19), price 13.3% below its 200-day, structure 31.6, BEARISH_CHOCH. **thorp withdrew his own solo conviction-4**: *"the ladder IS the broken structure, so the reward and the reason it is unreachable are the same field."* Conditioned, his +2.48R becomes **-0.42R**. Rogers's catalyst check fails outright — no thesis about the business, only reward arithmetic. **raschke alone supported at 3** on her Turtle Soup family and that is the honest dissent: the only negative extension in the set, div BULLISH, day_vol 1.18. QS: signal SKIP, edge +6.7pp; PM LENS 2 of 6. *Context: XLY is BLOCKED — worst macro headwind of the eleven sectors at -1.50.*

**DOCS · Healthcare · $27.10 — 0 support, 11 oppose.** Unanimous. The most extended name in the set at sma_dist **16.96%** while price still sits **below** its 200-day, on **day_vol 0.33 — one third of normal participation**. Risk 9.67%, the widest in the set. thorp: *"R1 conv 2, sized small... Detect-lens showed the gain side is an artifact too, so both terms of R3 were wrong in the same direction. Small is not the answer; out is."* QS: signal SKIP, edge +7.7pp; PM LENS 1 of 6. *Context: XLV gated CAUTION.*

**VRNS · Technology · $46.51 — 0 support, 11 oppose.** Unanimous. **livermore withdrew from SUPPORT to OPPOSE at the same conviction**: *"I called it the cleanest new-high entry while my own record said mp FADING. That is a reason written after a name."* Both R1 seats called the ma50 stop structural on a name whose ma20 43.17 has already crossed *under* its ma50 43.67 — the widest risk in the valid-bracket set at 6.11%. Fundamentals: TTM net loss, net_margin -20.55%. QS: signal SKIP, edge +7.7pp; PM LENS 3 of 6. *Context: XLK gated CAUTION on macro headwind -1.04.*

**SLDE · Financials · $24.73 — 0 support, 8 oppose, 3 abstain.** **oneil withdrew his own solo conviction-4**: *"My own C17 line makes more than 10% extended a rejection and I wrote 'late, not rejected' — that was my error, not a judgement call."* sma_dist **16.09%**, flow 100.0, day_vol 2.67 — the heaviest participation in the set, and the reason it is late. detect-lens: **four of six lenses print `--` (no data)**, and absence is never agreement; it holds AQE rank 6 on momentum alone. One post-IPO fiscal year (IPO 2025-06-18) underpins every growth figure. Was HOLD on 2026-08-31; +5.32% since, now PASS. QS: signal SKIP, edge +7.7pp; PM LENS 4 of 6. *Context: XLF gated CAUTION.*

**CTVA · Materials · $88.64 — 0 support, 10 oppose, 1 abstain.** **minervini withdrew his own solo conviction-4**: *"I named a caution and priced nothing. There was no discount in my 4, and inventing one now would be worse than withdrawing."* The only name in the set whose sector reads **"Declining — Avoid"**, in the only BLOCKED-on-AVOID sector (XLB). Stack jumbled — ma20 80.86 is the *lowest* of the four averages while price sits 9.6% above it. Four of six lenses print `--`. pe 58.70. QS: signal NONE, edge +7.7pp; PM LENS 1 of 6. *Context: XLB is BLOCKED outright.*

**TAK · Healthcare · $18.71 — 1 support, 9 oppose, 1 abstain.** **livermore cut 4 to 2 and withdrew the XLV Key Price construction that carried it.** Steenbarger showed the confirmation was circular — TAK was confirmed by JNJ and JNJ by TAK, both nominated by the same seat, and the confirming leg came on day_vol 0.92 which livermore himself had flagged. What remains: flow **32.9, the lowest money flow in the set**, div BEARISH with **div_bear_count 3, the highest in the set**, and a 1.55% "tight" stop that is one ordinary day's ATR range. QS: signal SKIP, edge +7.7pp; PM LENS 3 of 6. *Context: XLV gated CAUTION.*

**SPGI · Financials · $450.58 — 1 support, 8 oppose, 2 abstain.** elder-lens's solo conviction-4, sustained as the only support. The structural problem: **ma100 420.25 sits below ma200 446.85**, and price at 450.58 is only 0.83% above the 200-day, having thrust 5.5% clear of a bunched ma20/ma50 straight into it. detect-lens's worst-case finding sits here: **the atr_fallback_stop at 438.63 is BELOW the ma200 at 446.85** — the arithmetic stop only fires after the trend read has already failed. lynch grades it QUALITY_OK, the only "financial" where his industrial tests are actually valid. QS: signal SKIP, edge +7.7pp; PM LENS 3 of 6. *Context: XLF gated CAUTION.*

---

## 8. NEAR MISSES

**There are no cap-cut qualifiers today. The 20-name cap did not bind** — 18 qualified against a cap of 20, and `phase4.json` records `dropped: []`. This section would normally list every name the cap removed; today the honest entry is that the cap removed nothing.

What sits immediately below the line instead is the population the qualification threshold excluded: **32 names that drew exactly one nomination below the solo-high-conviction bar.** They are listed here because Rogers's set-level challenge is precisely about that threshold — a constant tuned on a filtered pool, carried unchanged onto an unfiltered one — and the PM should see what it excluded.

| Conviction 3 (22 names) | Nominating seat |
|---|---|
| HOOD, RSG, TDC, GILD, NOW | elder-lens |
| GDDY, KDP | livermore |
| LNG, AMGN, AAPL | minervini |
| GWRE, CNH, WTRG | oneil |
| STAG, SNOW, TRP | raschke |
| STGW | seow |
| KSS, IBN, MGNI, ADM | weis |
| KD | wyckoff |

| Conviction 2 (10 names) | Nominating seat |
|---|---|
| CRWD | elder-lens |
| AEP | raschke |
| APH, TD, CART | seow |
| RBLX, MSTR | thorp |
| BKR, AWK | weis |
| CEG | wyckoff |

Two of these overlap with the PM LENS coverage gap and are worth one line each: **GDDY** (livermore, 3) and **AAPL** (minervini, 3) both passed 5 of the PM's 6 checks and both fell below the qualification bar — so a name the PM's own checklist flagged was seen by exactly one seat and then dropped. **STGW** (seow, 2) is the only STRONG signal on the QS track. *Context for the group: 5 of the 32 sit in Utilities or Real Estate, both LAGGING on the RRG; the Technology names sit under a -1.04 macro headwind.*

---

## 9. ACTION PLAN — for the PM

**1. The book needs nothing today.** Three positions, all green, all with stops written this morning: BRZE 31.0651 (breakeven, +6.2R), HNGE 86.23, V 372.19. AQE reads BRZE and HNGE HOLD and V TIGHTEN, and the V stop at 372.19 — 1.7% under spot and just below the 20-day at 371.10 — already expresses the tighten. No stop moves are outstanding.

**2. The one thing on the book that genuinely needs a decision is the concentration breach.** XLV is **49.01%** of the book against a 35% cap (the PM's morning note reads 49.3%; either way it is ~14 points over), and it is one position — HNGE, $13,160 of $26,853 exposure, carrying a beta of 1.61 against a book beta of 0.78. Nothing in today's output reduces it: every XLV name the committee looked at is a hold or a pass. This is a sizing decision, not a committee decision, and it sits with the PM.

**3. CB is the only name with a verdict to act on, and it is a decision, not an instruction.** No bracket is staged and nothing is armed. If the PM wants it, the levels the committee actually agreed on are: entry area 348.25, **stop 342.22** (the defended swing low, 1.73% risk), first target at 2.83R. The invalidation is unusually clean — four separate seats named 342.22 as the line — and the reason to take it is that it is the only bracketed name in the set whose reward is not measured into overhead supply. The reason to hesitate is on the record and is not softened: rank 143 of 164, momentum 49.2, the only negative 20-day relative strength among the multi-seat names, and nothing has broken (shift RANGE). Four seats voted against it on exactly that.

**4. Treat all nine HOLDs as watch-list entries with a trigger, and nothing more.** Each carries an observable condition in §7. Five of them share one shape — **a close through the level on day_vol ≥ 1.40** — which is a single scan, not nine: BBY through ≈90.26, CVX after holding ma20 202.14, JNJ above the break bar high, MDT through the range high with 89.73 holding, WELL on the 20/50 separating. Three carry a slower condition that will not resolve this week: GNW needs two quarters of positive revenue, BSBR needs the 50/100/200 sequence repaired, MET needs a served structural stop.

**5. Two things this run surfaced that the PM may want to rule on.** First, Rogers's engine ask: `nomination_count >= 2` was calibrated on a filtered pool and was carried unchanged onto an unfiltered one, where seven of eighteen qualifiers arrived with zero peer corroboration, every one at exactly conviction 4. Second, Steenbarger's F2: the ranking key is 82% explained by headcount and runs *inverse* to the fields it is meant to weigh. Neither changes a verdict today. Both change what the rank means tomorrow.

**6. Watch the dollar.** DX 99.019 against 99.6482 — 0.64% away, the level where trend funds turn buyer, with speculators already crowded long. Both macro seats named it independently. Druckenmiller's instruction if it breaks is explicit: reduce, do not reason about it. The level is Yahoo-sourced and should be re-verified against a primary feed before it is acted on.

**7. Eleven names the committee never looked at are listed in §6, and one QS name (STGW, the only STRONG signal on the track) is in §5.** They are not verdicts. They are the gap between the PM's own checks and where the seats chose to look.

---

**DRAFT — PM approval required. Nothing is staged, nothing is armed.**
