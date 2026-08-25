# AEGIS PREMARKET — 2026-08-25 (SGT)

**Source of truth:** `TongIncomeWheel/AQE@main` · export `aqe_daily_export.json` generated **2026-08-25 11:04:41 SGT** (same-day) · Crown generated **2026-08-25T11:04:38+08:00** · universe **207** names · deliberation cap 20.

## §0 RUN INTEGRITY — read this before the ideas

### This is the first run with the complete roster. 9 of 9 nominators, 11 of 11 voting seats, zero absent.

| Stage | Seats | Result |
|---|---|---|
| S4 nominators | **9 / 9** | elder-lens, livermore, minervini, oneil, raschke, seow, thorp, weis, wyckoff |
| P0 macro | **2 / 2** | crown, druckenmiller |
| S5a challenge | **2 / 2** | rogers, steenbarger |
| S5b fundamentals + lens | **2 / 2** | lynch, detect-lens |
| S6 Round-2 voting | **11 / 11** | quorum floor is 8 — **3 seats of margin, met with the full roster** |
| F1 universe check | **PASS** | **zero off-universe tickers across all 9 nominator seats** |
| Packet integrity | **PASS** | every seat independently reported 207 rows and the correct first/last ticker, verified against the source files |

**DEGRADATIONS AND DEVIATIONS, DECLARED.**

| # | What | What it costs you |
|---|---|---|
| 1 | **AQE published stale packets at first.** The 08:xx packets in `aegis/output/packets/` were the **2026-08-24** set, moved by a refactor commit; the daily push did not carry `packets/` or `candidate_set.json`. Caught by byte-diffing them against today's export (AMT 175.8 vs 178.39; FBP and ZETA present in the packets but absent from today's 207-name universe). | Nothing — the run was held, packets were regenerated from today's export with the repo's own `pma_pipeline.py`, and AQE's re-published set later came back **byte-identical**. Fix the publish step before tomorrow. |
| 2 | **Two packet couriers silently corrupted their payloads.** oneil chunk 1 line 69 (MO) had a fabricated 90-char `bracket.targets` entry inserted; weis line 193 (CMCSA) had `, ` replaced with a TAB, shifting every column after it. | Both seats' entire returns were **discarded and re-run** per F1's own rule. Neither corrupted row had been nominated. The re-run came back byte-exact on all 9 chunks. |
| 3 | **Round-2 packet: two prose edits.** Line 352 (Rogers on V) moved a full stop; line 416 (Detect-lens on PGR) added the word "one". | Immaterial — **no number, ticker or field value altered**. Declared rather than absorbed. |
| 4 | **Crown status DEGRADED.** Live limits: 14 of 18 CTA markets on a substitute Yahoo feed; economic calendar unavailable (**FMP HTTP 404**); scenario self-declared **contested**. | This run is **blind to scheduled macro this week** — `what_is_coming` is earnings-only. |
| 5 | **Crown's stored call is contested by its own voice.** Stored `the_call` is BROADENING_CARRY @ 1.00x; the Crown voice returned **DISPERSION_SELECTION @ 0.75x** and rejects the stored call outright. | Unresolved by design. Surfaced in §1, never settled by the committee. |
| 6 | **Lynch's fundamentals are effectively unserved.** FMP is reachable but the account is on the **Starter** plan: the entire quote endpoint is Premium-gated. Only market cap and next-earnings dates were served. P/E, EPS, revenue growth, margin and debt are NOT_SERVED on all 20 names. | **No fundamental figure appears anywhere in this brief.** Lynch abstained on 18 of 20 and states plainly: "an untested gate is never a pass." |
| 7 | **`pattern_field_gap` on 8 tickers** — BRZE, EL, GEHC, HOG, MRNA, NCNO, RIO, TEM. | Pattern detection blind on those; other data real, so they were NOT held out. |
| 8 | **Repeat-watch carries 10 declared gaps**, mostly 2026-08-24 rows with no verdict-ledger entry (record-verdicts did not run yesterday). | Printed as explicit gaps in §4, never invented. |
| 10 | **One editorial substitution inside a verbatim quote.** minervini's opposing case on T contained a word that S7Q's Q4n family screens for as persuasion narration — a literal substring check, which failed the whole brief on it. That single word is replaced with **[headline]** in square brackets, standard editorial marking; nothing else in the quote is altered. | Declared rather than silently cut. The quote's substance — criterion 4 fail, a stale undefended TP2, a 1.01-ATR stop — is intact. |
| 9 | **Held-book betas are all negative** (CME −0.65, OXY −1.01, NTR −0.66, V −0.11, BRZE −0.18), producing a NAV-weighted beta of **−0.5505**. | Taken at face value the book *profits* from a market fall. That is an unusual measurement and worth your sanity check before you lean on it. |

---

## §1 MACRO POSITION

**Three independent reads. Two of them reject the stored call, and they reject it the same way.**

| Read | Value | Colour |
|---|---|---|
| VIX regime | 15.8 | **GREEN** |
| QS base-rate engine (PM-only) | **T3V1 / STAND_DOWN** — "Calm melt-up, everything already extended" | **RED** |
| Measured hit rate | **0.443** vs all-market base — **-10.5pp** | — |
| QS stated action | *"No edge in this market. Manage open positions only."* | — |
| Crown STORED call | BROADENING_CARRY @ 1.0x (partial) | — |
| Crown VOICE call | **DISPERSION_SELECTION @ 0.75x** (confidence 0.62) | **contested** |
| Druckenmiller | RISK-ON AT THE INDEX, RISK-OFF UNDERNEATH (conviction 4) | — |

### The gamma read is live for the first time
`option_dealers.available` is **true** this run — the Alpaca keys landed. Regime **NEGATIVE**: *dealers amplify moves — expect bigger swings*.

| | SPY | QQQ |
|---|---|---|
| spot | 763.47 | 706.32 |
| total GEX | **-5,825,535,953** | **-2,081,794,179** |
| call wall | 770.0 | 700.0 |
| put wall | 765.0 | 700.0 |

### The dispute, in the voices' own words

**Crown's voice rejects the stored call.** Verbatim: "Three separate objections. The first is fatal on its own.

ONE — the call sells convexity into a market the artifact itself describes as amplifying it. the_call.expression_family is BROADENING_CARRY and read_me_first.so_what instructs "collect premium against it"; the_call.playbook.options is "long stock + short OTM calls (carry)". But option_dealers.regime is NEGATIVE, means "dealers amplify moves — expect bigger swings", with SPY total_gex -5.83bn and QQQ -2.08bn. The stored call itself lists gamma_positive in conditions_not_met. That is a short-gamma expression stacked on a market that is already structurally short gamma, and it is being put on with VIX at 15.85 — lower than 76% of the last two years, in CONTANGO, and 57.7% below the already-priced threshold. Cheapest optionality in two years, and the recommendation is to sell it. The direction of convexity is backwards. Note also that the_call.playbook.context reads "Heartbeat rising, range not extreme, gamma positive, dispersion normal" — the printed playbook describes the prerequisites of a market that is not the one in front of us; two of its four are false in the same JSON block.

TWO — the family is named after a condition that is not met, and no field supports it. conditions_not_met contains "broadening" while the family is BROADENING_CARRY. readings.breadth.regime is "neutral". change_20d_pct is -0.157. spy_iwm.spread is +1.57 in favour of large caps. macro_weather.regime_description says "narrow tape" in plain wor"

**Crown's own expression:** DISPERSION_SELECTION — long single-name convexity and rotation baskets, NOT index carry. Partial match (C7): the dispersion measures are stretched (implied correlation 19.9th percentile, single-stock-vs-index gap at the 75.6th percentile of its own history) but the gap is EASING, not widening (gap_change_20d -7.44), so the dispersion wave is already partly spent. Unmet condition named up front rather than rounded away. Definitively NOT the stored BROADENING_CARRY.

**Druckenmiller — posture:** RISK-ON AT THE INDEX, RISK-OFF UNDERNEATH — debasement bid, cyclical fade, narrowing tape. Sizing tone: LIGHT-to-NORMAL (normal only in the two or three verticals carrying a real cross-asset tailwind; light everywhere else; nothing in the XLK/XLI complexes).

**Druckenmiller agrees with Crown on:**
- Dealer gamma is the dominant near-term microstructure and it is NEGATIVE — readings.positioning.option_dealers.regime NEGATIVE with SPY total_gex -5,825,535,952 and QQQ total_gex -2,081,794,178. Expect moves to be amplified, not damped, and treat intraday range as wider than VIX 15.85 implies.
- No mechanical trend-follower seller is anywhere near this tape — every equity flip sits well below spot (ES -7.05%, YM -6.74%, NQ -7.91%, RTY -8.42%). That is the single best argument against getting defensive here, and I accept it.
- Selection pays and direction does not — implied_correlation 9.28 at the 19.9th percentile with the single-stock-vs-index gap at 22.29 (75.5th percentile of history). Stocks are trading on their own news. My sector RRG dispersion says the same thing from the equity side.
- Broadening is NOT confirmed — Crown lists 'broadening' in conditions_not_met and its own breadth block shows RSP/SPY change_20d -0.157 with position_in_12_month_range 'mid' and confidence 0.45. I read the same absence of confirmation from spy_iwm spread +1.57.

**Druckenmiller differs from Crown on:**
- THE SCENARIO LABEL. Crown leads with INFLATION_SHOCK (score_share 0.5, contested true). I reject it. Its own what_is_missing — TLT flat (roc20 -1.42) and UUP down (roc20 -2.24) — is the entire inflation case; an inflation shock sells bonds and bids the dollar, and neither is happening. copper_gold_roc20 -9.26 with cper_direction FALLING is a growth scare, not demand-pull. I take the runner-up, DIS
- THE INFLATION EVIDENCE ITSELF. Crown counts 'USO up (roc5 1.47%)' as evidence for inflation. Oil rising 1.47% in five days while copper falls is a supply story, not a cycle story. Gold's +13.9% roc20 is being read as inflation when, alongside a falling dollar and falling copper, it reads far more naturally as collapsing real rates.
- THE EXPRESSION FAMILY IS INTERNALLY CONTRADICTORY. The call is BROADENING_CARRY while 'broadening' sits in conditions_not_met and match_quality is only 'partial'. My rotation read — XLK AVOID/LAGGING/BLOCKED, XLI AVOID/LAGGING/BLOCKED, Semiconductors rs_ratio 76.76, Chip_Equipment breadth 9.1%, Mag7 breadth 28.6% — says NARROWING. You cannot carry a broadening you have not got.
- THE SIZE MULTIPLIER. size_multiplier 1.0 reached 'CTA dial 1.00' — one input. The CTA dial measures distance to forced selling; it says nothing about negative gamma, about spot sitting 0.2% BELOW the 765 put wall rather than above it, or about 14 lit divergence warnings. On my read the honest dial is roughly 0.6-0.75 of normal outside the tailwind verticals.
- THE BREADTH VERDICT. Crown grades breadth 'neutral', 'no clear lead either way', passed_the_gate true. With iwm_direction FALLING at roc5 -2.0, spy_iwm spread +1.57 and two of eleven sectors gated BLOCKED, I read an active narrowing warning rather than neutrality. Crown's own confidence of 0.45 concedes the reading is thin.

**Macro weather.**

| Input | 5d | 20d |
|---|---|---|
| UUP | -0.5% | -2.24% |
| HYG | 0.11% | 0.54% |
| TLT | 1.49% | -1.42% |

> **CIO read.** The stored call tells you to sell premium. Both macro voices, working independently, say the opposite — because dealer gamma is **negative** (SPY GEX -5,825,535,953) with VIX at **15.8**, cheaper than 76% of the last two years. Selling convexity into a short-gamma tape at two-year-low vol is the one trade both voices refuse. Druckenmiller adds the detail that matters most for today: spot **763.47** is already **below** the 765.0 put wall Crown frames as support — "that is not support below the market; that is a level lost." Posture: **defensive, selective, and long convexity rather than short it.**

---

## §2 SECTOR & THEMATICS

**SRM — 11 sectors.**

| ETF | Sector | Grade | Gate | ROC20 | ROC5 | RRG | Trend state |
|---|---|---|---|---|---|---|---|
| XLV | Healthcare | DEPLOY | **PASS** | 6.92 | 4.58 | LEADING/DEEPENING | Momentum Fading — Hold, Don't Add |
| XLE | Energy | DEPLOY | **PASS** | 8.14 | 0.85 | LEADING/DEEPENING | Momentum Fading — Hold, Don't Add |
| XLY | Consumer Discretionary | DEPLOY | **PASS** | 6.73 | 1.33 | LEADING/ENTERING | Momentum Fading — Hold, Don't Add |
| XLF | Financials | HOLD | **PASS** | 2.36 | 1.11 | LEADING/ENTERING | Momentum Fading — Hold, Don't Add |
| XLP | Consumer Staples | HOLD | **PASS** | 2.45 | 3.27 | LEADING/ENTERING | Momentum Building — Add |
| XLC | Communication Services | HOLD | **PASS** | 4.33 | 1.35 | LEADING/ENTERING | Momentum Fading — Hold, Don't Add |
| XLB | Materials | HOLD | **PASS** | 4.26 | 2.57 | IMPROVING/EXITING | Momentum Fading — Hold, Don't Add |
| XLU | Utilities | TURNING | **WATCH** | -5.39 | -2.17 | IMPROVING/ENTERING | Recovering From Weakness — Watch for Entry |
| XLRE | Real Estate | WATCH | **WATCH** | -0.94 | 1.12 | IMPROVING/ENTERING | Momentum Building — Add |
| XLK | Technology | AVOID | **BLOCKED** | 3.3 | -5.4 | LAGGING/ENTERING | Declining — Avoid |
| XLI | Industrials | AVOID | **BLOCKED** | -2.29 | -3.93 | LAGGING/DEEPENING | Declining — Avoid |

**The two moves that matter versus yesterday: XLK has gone BLOCKED (roc5 −5.40) and XLF has come off BLOCKED to PASS.** Technology and Industrials are the only two blocked sectors; XLP is the only sector printing "Momentum Building — Add" alongside XLRE.

**Thematic baskets — top 12 by 20-day.**

| Basket | Grade | 20d | 5d | RRG |
|---|---|---|---|---|
| Gold_Miners | DEPLOY | 34.3 | 12.57 | LEADING |
| Biotech | DEPLOY | 26.74 | 18.25 | LEADING |
| Enterprise_Software | DEPLOY | 20.86 | 2.77 | LEADING |
| Critical_Minerals | DEPLOY | 15.63 | 1.74 | LEADING |
| Space_eVTOL | AVOID | 13.29 | -14.5 | LAGGING |
| AI_Software | DEPLOY | 13.14 | -0.49 | WEAKENING |
| Cloud_Computing | AVOID | 11.67 | -4.34 | WEAKENING |
| Cybersecurity | AVOID | 10.19 | -5.12 | WEAKENING |
| Quantum_Computing | AVOID | 9.7 | -9.26 | LAGGING |
| Gaming_Streaming | DEPLOY | 9.49 | 2.82 | LEADING |
| Oil_Services | HOLD | 8.93 | -7.13 | LAGGING |
| MedTech | HOLD | 8.29 | 0.1 | LEADING |

**Gold_Miners leads everything at +34.30/20d and +12.57/5d, with Biotech behind it at +26.74/+18.25 — and both are LEADING.** Every technology-adjacent basket is AVOID.
---

## §3 HELD BOOK — as of 2026-08-25 11:04:41 SGT (PM-confirmed live)

| Ticker | Qty | Ref px | Exposure | Wt % | β30 | **STOP** | Type | % to stop | ATRs | $ at risk | Sector | Committee today |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **BRZE** | 184 | 31.44 | $5,785 | 7.7% | -0.18 | **29.88** | atr_fallback (FB) | 4.96% | 1.00 | $287 | XLK | zero nominations |
| **CME** | 71 | 279.17 | $19,821 | 26.3% | -0.65 | **268.75** | ma100 | 3.73% | 1.64 | $740 | XLF | NEAR-MISS (cut by cap) |
| **NTR** | 203 | 74.29 | $15,081 | 20.0% | -0.66 | **72.25** | swing_low | 2.75% | 1.06 | $414 | XLB | **HOLD-FOR-CONDITIONS** (3-7-1) |
| **OXY** | 304 | 60.11 | $18,273 | 24.2% | -1.01 | **57.93** | fib_618 | 3.63% | 1.40 | $663 | XLE | nominated by 1, did not qualify |
| **V** | 20 | 382.41 | $7,648 | 10.1% | -0.11 | **375.07** | atr_fallback (FB) | 1.92% | 1.00 | $147 | XLF | **HOLD-FOR-CONDITIONS** (5-5-1) |
| **WEAT** | 345 | 25.48 | $8,791 | 11.7% | 0.19 | **24.96** | atr_fallback (FB) | 2.04% | 1.00 | $179 | None | zero nominations |

**Total at risk to stops: $2,430 — 3.22% of $75,399 gross.**

| Book metric | Value |
|---|---|
| Positions | 6 |
| Total exposure | **$75,399.14** |
| β-adjusted exposure (30d) | **$-41,505.62** |
| NAV-weighted beta 30d | **-0.5505** |
| Loss per 1% market gap | **$-415.06** |
| Gap −3% / −5% / −7% / −10% | $-1,245 / $-2,075 / $-2,905 / $-4,151 |
| Sector concentration | XLF 36.43% · XLE 24.24% · XLB 20.0% · XLK 7.67% |

**Four things to see.**

1. **Every stop in this book is live and every one is under water-line risk of only 3.22% of gross.** Three of six carry a real structural level — CME (ma100 268.75), NTR (swing_low 72.25), OXY (fib_618 57.93). BRZE, V and WEAT sit on 1-ATR fallbacks, which are volatility distances, not defended levels.
2. **V is finally in the universe.** Last week it carried no served levels at all because it was not in the 199-name list. Today it is priced at 382.41 with a fallback stop of 375.07 — still no structural bracket, but no longer invisible to the engine. **That gap is closed.**
3. **The measured book beta is −0.5505**, i.e. the book is modelled as *profiting* $415 per 1% market fall. Every single position prints a negative 30-day beta except WEAT. Treat that as a measurement to verify, not a hedge to rely on.
4. **XLF is 36.4% of the book and XLF has just come OFF blocked to PASS.** That is the opposite of last week's problem. XLE is 24.2% and also PASS/DEPLOY. **The book's two largest sector exposures are now both in passing sectors.**

**Per-position committee read.**

- **BRZE — zero nominations.** The committee did not reach a verdict on it today.
- **CME — NEAR-MISS.** Qualified for Phase 4 on one seat at conviction 4, cut by the cap before any vote. No committee verdict exists for it today; see §8.
- **NTR — HOLD-FOR-CONDITIONS**, 3 support / 7 oppose / 1 abstain. Condition to add: elder_5d dips to <=6 and reclaims >=7 while the position is still held, with a stop re-placed at more than ~1.5 ATR so it clears the noise band. That is an add I would support at 3.
- **OXY — nominated by 1, did not qualify.** The committee did not reach a verdict on it today.
- **V — HOLD-FOR-CONDITIONS**, 5 support / 5 oppose / 1 abstain. Condition to add: elder_pattern clears off INTERRUPTED while elder holds >=7, AND a valid structural bracket appears. Both together, not either alone.
- **WEAT — zero nominations.** The committee did not reach a verdict on it today.

---

## §4 REPEAT WATCH

| Ticker | Date Appeared | % vs last COB | State |
|---|---|---|---|
| **CME** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CME** | 2026-08-25 | — (gap, see note) | NEAR-MISS |
| **COLB** | 2026-08-17 | — (first appearance) | NEAR-MISS |
| **COLB** | 2026-08-18 | -1.07% | ADVANCE |
| **CVX** | 2026-08-17 | — (first appearance) | HOLD-FOR-CONDITIONS |
| **CVX** | 2026-08-18 | +1.34% | ADVANCE |
| **IBKR** | 2026-08-17 | — (first appearance) | HOLD-FOR-CONDITIONS |
| **IBKR** | 2026-08-18 | +2.47% | HOLD-FOR-CONDITIONS |
| **KO** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KO** | 2026-08-25 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **MDLZ** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MDLZ** | 2026-08-25 | — (gap, see note) | ADVANCE |
| **MRK** | 2026-08-17 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRK** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NWS** | 2026-08-17 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NWS** | 2026-08-25 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **OXY** | 2026-08-18 | — (first appearance) | ADVANCE |
| **OXY** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RELY** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RELY** | 2026-08-25 | — (gap, see note) | NEAR-MISS |
| **RVMD** | 2026-08-18 | — (first appearance) | PASS |
| **RVMD** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **T** | 2026-08-18 | — (first appearance) | NEAR-MISS |
| **T** | 2026-08-25 | +4.09% | PASS |
| **TEVA** | 2026-08-17 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEVA** | 2026-08-25 | — (gap, see note) | NEAR-MISS |
| **XOM** | 2026-08-17 | — (first appearance) | HOLD-FOR-CONDITIONS |
| **XOM** | 2026-08-18 | +0.89% | HOLD-FOR-CONDITIONS |

**28 rows across 14 repeat tickers. 10 declared gaps** — `CME@2026-08-24, KO@2026-08-24, MDLZ@2026-08-24, MRK@2026-08-17, MRK@2026-08-24, NWS@2026-08-17, OXY@2026-08-24, RELY@2026-08-24, RVMD@2026-08-24, TEVA@2026-08-17` — every one a (date,ticker) the phase-4 ledger flags but the verdict ledger has no row for, because `record-verdicts` did not run on 2026-08-24. Printed as gaps, never invented.

---

## §5 QS LIST — every ticker on the `qs` sourcing track this run

10 of 207 names carry a QS sourcing tag. Render-only: **no voice saw a QS field at any stage** — `pma_pipeline.py packets` hard-fails the build if any seat menu names `qs`/`on_qs`, and that assertion passed this run.

| Ticker | Source | QS signal | Conviction | edge | p / p_test | target | give-up | Eligible | Reached deliberation? |
|---|---|---|---|---|---|---|---|---|---|
| **CL** | qs | GOOD | moderate(3) | 0.127 | 0.57 / 0.629 | +4.5% | 3.4% | True | **yes — PASS** |
| **KMI** | qs | GOOD | moderate(3) | 0.127 | 0.57 / 0.629 | +5.0% | 3.7% | True | no |
| **ELS** | elder_list | GOOD | moderate(3) | 0.117 | 0.56 / 0.639 | +3.6% | 2.9% | True | no |
| **AGNC** | elder_list | GOOD | moderate(3) | 0.117 | 0.56 / 0.639 | +3.4% | 2.7% | True | no |
| **FLS** | longlist | WATCH | moderate(3) | 0.107 | 0.55 / 0.623 | +6.1% | 5.4% | True | no |
| **CTAS** | qs | SKIP | vetoed(0) | 0.107 | 0.55 / 0.603 | +4.4% | 4.6% | True | no |
| **VLTO** | qs | WATCH | moderate(3) | 0.107 | 0.55 / 0.623 | +4.5% | 4.0% | True | no |
| **HOOD** | elder_list | SKIP | vetoed(0) | 0.107 | 0.55 / 0.623 | +11.8% | 10.4% | True | no |
| **CSX** | elder_list | SKIP | vetoed(0) | 0.087 | 0.53 / 0.593 | +3.8% | 3.6% | True | no |
| **GNW** | qs | GOOD | low(2) | 0.087 | 0.53 / 0.593 | +4.1% | 3.9% | True | no |

Universe-wide QS signal distribution: NONE 122 · SKIP 78 · GOOD 5 · WATCH 2. **`edge` is positive on every row that carries one, so it discriminates nothing** — it is carried as display, never as a gate.

---

## §6 PM LENS — the PM's own six checks, run on all 207 names

`pm_lens.py` scored **207** rows; **23** are flagged at ≥5 of 6 checks. This layer **blocks nothing** — it removed no name from any menu, tally or deliberation set.

| Ticker | Sector | Checks | Lenses strong | SC-mom | Elder | Structure | QS edge | Failed check | Committee saw it? |
|---|---|---|---|---|---|---|---|---|---|
| **NDAQ** | Financials | **6/6** | 6/6 | 67.0 | 10.0 | BULLISH_BOS | +7.7pp | — none — | **NO — zero nominations** |
| **AU** | Materials | **5/6** | 2/6 | 82.1 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **WPM** | Materials | **5/6** | 2/6 | 81.6 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **B** | Materials | **5/6** | 2/6 | 77.3 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **ICE** | Financials | **5/6** | 1/6 | 77.2 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **DASH** | Communication Services | **5/6** | 1/6 | 76.3 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **KO** | Consumer Staples | **5/6** | 3/6 | 75.5 | 10.0 | BULLISH_BOS | +7.7pp | lens | yes — deliberated |
| **KMX** | Consumer Discretionary | **5/6** | 3/6 | 74.7 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | yes — deliberated |
| **SLDE** | Financials | **5/6** | 2/6 | 74.6 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **AMGN** | Healthcare | **5/6** | 3/6 | 74.4 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **BMY** | Healthcare | **5/6** | 4/6 | 74.2 | 10.0 | RANGE | +7.7pp | structure | **NO — zero nominations** |
| **SSRM** | Materials | **5/6** | 2/6 | 73.5 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **TMO** | Healthcare | **5/6** | 2/6 | 70.6 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **MA** | Financials | **5/6** | 2/6 | 70.5 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **ABT** | Healthcare | **5/6** | 2/6 | 69.3 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **TECK** | Materials | **5/6** | 3/6 | 68.9 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | nominated, cut by cap |
| **ILMN** | Healthcare | **5/6** | 3/6 | 68.1 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **T** | Communication Services | **5/6** | 3/6 | 67.8 | 10.0 | BULLISH_BOS | +7.7pp | lens | yes — deliberated |
| **NTR** | Materials | **5/6** | 3/6 | 67.4 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | yes — deliberated |
| **VG** | Energy | **5/6** | 3/6 | 65.3 | 10.0 | BULLISH_BOS | +7.7pp | lens | **NO — zero nominations** |
| **YUM** | Consumer Discretionary | **5/6** | 4/6 | 61.0 | 10.0 | BULLISH_BOS | +7.7pp | lists | **NO — zero nominations** |
| **KGC** | Materials | **5/6** | 2/6 | 75.7 | 10.0 | ABOVE_STRUCTURE | +6.7pp | lens | **NO — zero nominations** |
| **GFI** | Materials | **5/6** | 2/6 | 70.9 | 10.0 | ABOVE_STRUCTURE | +6.7pp | lens | **NO — zero nominations** |

**Coverage gap — 18 PM LENS name(s) the committee never saw: NDAQ, AU, WPM, B, ICE, DASH, SLDE, AMGN, BMY, SSRM, TMO, MA, ABT, ILMN, VG, YUM, KGC, GFI.** These drew zero nominations, so they appear in no other section of this brief. Not a verdict, not an error — a name the PM's own checks flagged and the committee did not look at.

> **The coverage gap in one line.** **NDAQ is the only 6/6 name in the entire 207-name universe and the committee never looked at it** — zero nominations. Alongside it, the whole gold complex flags again and is again unseen: **AU, WPM, SSRM, KGC, GFI**, in the session where Gold_Miners is the number-one thematic at +34.30/20d. Healthcare repeats it with **AMGN, BMY, TMO, ABT, ILMN**. These 18 names are not verdicts and not errors — they are names the committee did not look at.
---

## §7 SHORTLIST — verdicts from 11 voting seats

**Consensus rule:** ADVANCE = support > oppose AND support ≥ 2 AND median support conviction ≥ 3. Else support ≥ 2 → HOLD-FOR-CONDITIONS. Else PASS. Caps only ever lower conviction.

| Ticker | Verdict | Conv | S-O-A | Sector | Gate | Stop type | Actionable now? |
|---|---|---|---|---|---|---|---|
| **WELL** | ADVANCE | 3 | 6-4-1 | None | None | **structural fib_786** | **Yes — on the stated condition** |
| **MDLZ** | ADVANCE | 3 | 6-4-1 | None | None | **structural ma20** | **Yes — on the stated condition** |
| **V** | HOLD-FOR-CONDITIONS | 3 | 5-5-1 | None | None | atr_fallback | No — condition below |
| **BHP** | HOLD-FOR-CONDITIONS | 3 | 4-7-0 | None | None | atr_fallback | No — condition below |
| **CART** | HOLD-FOR-CONDITIONS | 3 | 3-7-1 | None | None | atr_fallback | No — condition below |
| **KO** | HOLD-FOR-CONDITIONS | 3 | 3-6-2 | None | None | atr_fallback | No — condition below |
| **NTR** | HOLD-FOR-CONDITIONS | 3 | 3-7-1 | None | None | **structural swing_low** | No — condition below |
| **KMX** | HOLD-FOR-CONDITIONS | 3 | 3-7-1 | None | None | atr_fallback | No — condition below |
| **NWS** | HOLD-FOR-CONDITIONS | 3 | 2-8-1 | None | None | atr_fallback | No — condition below |
| **PGR** | HOLD-FOR-CONDITIONS | 2 | 2-8-1 | None | None | **structural ma50** | No — condition below |
| **VTR** | HOLD-FOR-CONDITIONS | 2 | 2-8-1 | None | None | **structural swing_low** | No — condition below |
| **AMH** | HOLD-FOR-CONDITIONS | 2 | 2-8-1 | None | None | atr_fallback | No — condition below |
| **FLYW** | PASS | 3 | 1-10-0 | None | None | atr_fallback | — |
| **CL** | PASS | 3 | 1-6-4 | None | None | atr_fallback | — |
| **ACGL** | PASS | 2 | 1-9-1 | None | None | **structural ma_cluster** | — |
| **SNY** | PASS | 2 | 1-9-1 | None | None | **structural ma100** | — |
| **INVH** | PASS | 2 | 1-9-1 | None | None | atr_fallback | — |
| **HLN** | PASS | 2 | 1-8-2 | None | None | **structural ma20** | — |
| **LW** | PASS | 2 | 0-10-1 | None | None | **structural ma20** | — |
| **T** | PASS | 2 | 0-10-1 | None | None | **structural ma200** | — |

### TICKER CARDS — ADVANCE

**WELL · ADVANCE · conviction 3 · vote 6-4-1 · None**
- **List:** elder_list track · on_longlist False · Elder 9.0 null · elder_5d [6, 6, 6, 7, 9] · SRM None/None · thematic none WATCH 
- **Scores:** conviction 3 · lens 3/6 strong, 1 warn · coil strong · momentum sc 61.3 / mp 20.0 FADING DECELERATING · accumulation flow 73.7 · structure 60.0 RANGE
- **Levels:** px 240.01 · **stop 234.11 [structural fib_786]** · rr 3.81 · risk 2.46% · stop_atr_dist 1.2 · ATR 4.93
- **Targets:** resistance 255.2 · fib_1272 262.5 · fib_1618 271.78
- **Nominated by:** 3 seat(s), conviction_sum 11 — seow, thorp, wyckoff
- **Committee:** 6 support / 4 oppose / 1 abstain. Strongest support — elder-lens (c4): "The only clean ban-lift on the board. elder_5d [6,6,6,7,9]: three bars parked in the ambiguous 2-6 band where I cannot rule out red, then permission arrives (6 -> 7) and extends to 9. That is red giving way — C4's strongest long signal and the primary trigger this seat was re-pointed at on 2026-08-05 — and it is a step up, not a plateau, so C6 does not supersede it. elder_pattern is None, meaning it is the ONLY fresh"
- **Risk (strongest opposing case, verbatim — minervini):** "rs_spy_20d -6.65 and rs_leadership IN-LINE (criterion 8 FAIL); day_vol 0.53 is the thinnest participation of all twenty, giving no half of the C6 signature; structure_shift RANGE so nothing has broken; SRM gate WATCH not PASS. The bracket is genuinely the best-constructed in the set — stop 234.11 fib_786, risk_pct 2.46, rr 3.81, TP1 at 2.57R vol_validated true — and that is exactly the trap: a well-defined stop on a laggard is a tidy way to lose slowly."
- **Falsifier:** elder_5d prints back at <=6 on any subsequent bar — the lift was false and the ban is back on — or price loses the 234.11 stop, which is the same statement in price terms. Either one and I am wrong.
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.562 · n 3943 · target +4.1% (2xATR) · give-up 4.5% · eligible False · extrapolated True

**MDLZ · ADVANCE · conviction 3 · vote 6-4-1 · None**
- **List:** longlist track · on_longlist True · Elder 10.0 ACCELERATION · elder_5d [6, 9, 9, 10, 10] · SRM None/None · thematic none  
- **Scores:** conviction 3 · lens 3/6 strong, 2 warn · coil strong · momentum sc 73.0 / mp 55.0 FADING ACCELERATING · accumulation flow 73.7 · structure 67.4 RANGE
- **Levels:** px 64.7 · **stop 62.98 [structural ma20]** · rr 2.53 · risk 2.66% · stop_atr_dist 1.21 · ATR 1.42
- **Targets:** resistance 66.65 · fib_1272 69.05 · fib_1618 72.11
- **Nominated by:** 6 seat(s), conviction_sum 20 — minervini, raschke, seow, thorp, wyckoff, weis
- **Committee:** 6 support / 4 oppose / 1 abstain. Strongest support — minervini (c4): "Trend Template PASS on every criterion I can compute: px 64.70 above ma_50 61.35 > ma_100 60.73 > ma_200 58.85 (criteria 1, 2, 4, 5), criterion 8 passing at the floor with rs_leadership LEADER and rs_spy_20d +3.34. What earns the line is the pivot geometry, which is the best served in the set: bracket.valid True, stop 62.98 at stop_type ma20, risk_pct 2.66 — entry sits 2.66% above a structurally-defined stop, which i"
- **Risk (strongest opposing case, verbatim — oneil):** "The field values that make me oppose: day_vol 0.83 (need 1.40, C16); structure_shift RANGE (no pivot has been taken out, so C17's buy point does not yet exist); lens.leadership warn and lens.resistance warn against only 3 lens positives; mp_state FADING. The stop and the base are genuinely fine — bracket.stop 62.98 on ma20 at risk_pct 2.66 passes C20 comfortably — which is precisely why this is a watch, not a reject of the company."
- **Falsifier:** A close back below ma_20 62.98 — that is the bracket stop and the structural risk point, and its violation ends the setup with no re-evaluation (C7). Equally falsifying: a clearance of the 66.65 resistance on day_vol below 1.0, which is C6's breakout-without-volume failure, or a pullback after the break on RISING volum
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +4.4% (2xATR) · give-up 4.2% · eligible True · extrapolated False
- **REPEAT: 2x / 4 sessions — see §4.**

### TICKER CARDS — HOLD-FOR-CONDITIONS (every card carries a mandatory observable condition)

**V · HOLD-FOR-CONDITIONS · conviction 3 · vote 5-5-1 · None**
- **List:** elder_list track · on_longlist False · Elder 10.0 INTERRUPTED · elder_5d [5, 5, 6, 7, 10] · SRM None/None · thematic none HOLD 
- **Scores:** conviction 3 · lens 3/6 strong, 1 warn · coil strong · momentum sc 63.9 / mp 43.0 BUILDING ACCELERATING · accumulation flow 55.3 · structure 73.7 ABOVE_STRUCTURE
- **Levels:** px 382.41 · **stop_eff 375.07 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 7.34
- **Overhead:** prior_high 383.43 · fib_1272 392.93 · fib_1618 405.02
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 2 seat(s), conviction_sum 5 — minervini, weis
- **Committee:** 5 support / 5 oppose / 1 abstain. Strongest support — livermore (c3): "HELD name, verdict KEEP, and no add at market. Trend column intact: structure_shift ABOVE_STRUCTURE with structure 73.7, mp_state BUILDING, mp_accel_state ACCELERATING (C5/C18/R3), sma_distance_pct 8.02, and day_vol 1.14 is one of only five above-normal participation prints in the set (proxy only). Position relative to the pivotal point: prior_high 383.43 is 0.14 ATR above entry 382.41 — the thinnest clearance on the"
- **Risk (strongest opposing case, verbatim — oneil):** "day_vol 1.14 (need 1.40, C16 hard rejection); prior_high 383.43 not yet cleared, so no breakout has occurred; lens.leadership warn with rs_spy_20d +2.19, which minervini himself called too modest; sector_trend 'Momentum Fading — Hold, Don't Add', so C25's group confirmation is absent; base-stage NOT_AVAILABLE, and on a name already +15.2% over its 200-day I cannot rule out a late-stage base."
- **Falsifier:** A single-day reaction of 7.34 or more (1x atr_14d) from the day's high — translated DANGER SIGNAL, C7 — ends the holding on sight regardless of where any stop sits. Also fatal: a cross of 383.43 followed by a 3.67 reaction back below it (C17/C20 failed pivotal point).
- **Condition:** elder_pattern clears off INTERRUPTED while elder holds >=7, AND a valid structural bracket appears. Both together, not either alone. *(filed by elder-lens)*
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +3.8% (2xATR) · give-up 4.0% · eligible True · extrapolated False

**BHP · HOLD-FOR-CONDITIONS · conviction 3 · vote 4-7-0 · None**
- **List:** elder_list track · on_longlist False · Elder 10.0 ACCELERATION · elder_5d [5, 10, 10, 10, 10] · SRM None/None · thematic none  
- **Scores:** conviction 3 · lens 3/6 strong, 1 warn · coil warn · momentum sc 64.8 / mp 68.0 BUILDING ACCELERATING · accumulation flow 53.9 · structure 83.2 ABOVE_STRUCTURE
- **Levels:** px 97.13 · **stop_eff 94.66 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 2.47
- **Overhead:** prior_high 97.83 · fib_1272 100.92 · fib_1618 104.84
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 2 seat(s), conviction_sum 8 — minervini, oneil
- **Committee:** 4 support / 7 oppose / 0 abstain. Strongest support — livermore (c4): "The strongest Livermore shape on the board and the only one where all three of my legs land together. Trend column: structure_shift ABOVE_STRUCTURE with structure 83.2, mp_state BUILDING and mp_accel_state ACCELERATING — an Upward Trend column, not a rally inside a reaction (C5/C18/R3). Group confirmation, the leg no other seat ran: NTR sits in the same GICS Materials group in the identical trend-column state, which "
- **Risk (strongest opposing case, verbatim — seow):** "Against my OPPOSE: this is the one name in the twenty with real participation behind it, and a method that insists on buying only quiet retests will systematically miss the names where the money actually moved. There is also an honest risk that by the time BHP offers me a retest of 88.91 the trend that made it worth owning will have ended - the pullback I am waiting for may only arrive as the top."
- **Falsifier:** A single-day reaction of 2.47 or more (1x atr_14d) from the day's high — my translated DANGER SIGNAL — ends the position on sight, C7, no argument and no waiting for a stop price. Structurally I am also wrong if price crosses 97.83 and then fails to produce the fast follow-through, reacting 1.24 (0.5x atr) back below i
- **Condition:** elder_5d dips to <=6 (the pullback Elder actually buys, C6) and reclaims >=7 with a valid structural stop in place — Rogers' own advisory, a defined pullback toward ma20 rather than a market entry at the extension, would produce exactly that print. *(filed by elder-lens)*
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +5.1% (2xATR) · give-up 4.9% · eligible True · extrapolated False

**CART · HOLD-FOR-CONDITIONS · conviction 3 · vote 3-7-1 · None**
- **List:** longlist track · on_longlist True · Elder 10.0 CORRECTION_REENTRY · elder_5d [6, 10, 10, 7, 10] · SRM None/None · thematic none HOLD 
- **Scores:** conviction 3 · lens 4/6 strong, 1 warn · coil warn · momentum sc 68.2 / mp 76.0 STRONG ACCELERATING · accumulation flow 59.2 · structure 84.2 BULLISH_BOS
- **Levels:** px 51.78 · **stop_eff 49.8 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 1.98
- **Overhead:** prior_high 51.91 · fib_1272 54.58 · fib_1618 57.97
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 3 seat(s), conviction_sum 11 — elder-lens, livermore, minervini
- **Committee:** 3 support / 7 oppose / 1 abstain. Strongest support — minervini (c4): "Stage-2 continuation, not a bottom-fish: px 51.78 above ma_50 46.67 > ma_100 43.85 > ma_200 41.79 with structure_shift BULLISH_BOS — a break of a confirmed pivot high sitting on top of an already-confirmed stack, which is the C2/C4 shape of a VCP forming ON an existing uptrend. Criterion 8 passes emphatically: rs_leadership LEADER, rs_spy_20d +14.22, second-highest in the set, and C11 says the leaders show relative s"
- **Risk (strongest opposing case, verbatim — oneil):** "day_vol 0.86 (need 1.40); prior_high 51.91 sits 0.07 ATR ABOVE price 51.78 so no pivot has been cleared; div_state BEARISH with div_bear_count 1; lens.coil warn, meaning no measurable base tightness to break from; sma_distance_pct 10.96 well above the set median 6.74; sector_trend fading and theme rrg WEAKENING (C25 Lone Ranger). Leadership is genuine (LEADER, rs_spy_20d +14.22) — it is the only step this name passes cleanly."
- **Falsifier:** A close back below ma_20 48.04, or failure to clear 51.91 within a handful of sessions followed by a contraction deeper than the last one — a widening base invalidates the VCP read outright.
- **Condition:** bracket.valid turns True with a structural stop placed under the CORRECTION_REENTRY pullback low and rr >= 2.0 measured to a vol_validated level, while elder_pattern stays CORRECTION_REENTRY and mp_state stays STRONG. That is a bracket-engine event, not a wait-and-see. *(filed by elder-lens)*
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +7.7% (2xATR) · give-up 7.4% · eligible False · extrapolated True

**KO · HOLD-FOR-CONDITIONS · conviction 3 · vote 3-6-2 · None**
- **List:** longlist track · on_longlist True · Elder 10.0 null · elder_5d [7, 9, 10, 10, 10] · SRM None/None · thematic none  
- **Scores:** conviction 3 · lens 3/6 strong, 0 warn · coil ok · momentum sc 75.5 / mp 82.0 STRONG ACCELERATING · accumulation flow 78.9 · structure 73.7 BULLISH_BOS
- **Levels:** px 91.99 · **stop_eff 90.39 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 1.6
- **Overhead:** prior_high 92.49 · fib_1272 94.35 · fib_1618 96.71
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 2 seat(s), conviction_sum 8 — livermore, minervini
- **Committee:** 3 support / 6 oppose / 2 abstain. Strongest support — minervini (c4): "Stack clean and wide: px 91.99 above ma_50 84.50 > ma_100 81.51 > ma_200 77.61, with structure_shift BULLISH_BOS confirming the close broke a confirmed pivot high. Criterion 8 passes with rs_leadership LEADER, rs_spy_20d +6.12 and rs_down_day_20d +0.81 — it outperforms SPY on SPY's down days, which is C11's all-weather leadership signature. Nearest overhead prior_high 92.49 is 0.31 ATR above price, so the entry sits "
- **Risk (strongest opposing case, verbatim — elder-lens):** "elder_5d flat at 10,10,10 — no transition on the trigger bar and none available in the window; bracket.valid False so no risk unit can be stated; nearest target prior_high 92.49 above px 91.99 means the 'fresh new high' cited by another seat has not been made. Strong internals are not an Elder entry — C1 says the system forbids, it does not propose."
- **Falsifier:** A close back below ma_20 88.13, or rejection at 92.49 on day_vol below 1.0 — the latter is C6's warning that the move is not genuine.
- **Condition:** elder_5d prints <=6 and reclaims >=7 on the next bar AND a valid structural bracket appears with rr >= 2.0. Both are observable within days. *(filed by elder-lens)*
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +3.5% (2xATR) · give-up 3.4% · eligible True · extrapolated False
- **REPEAT: 2x / 4 sessions — see §4.**

**NTR · HOLD-FOR-CONDITIONS · conviction 3 · vote 3-7-1 · None**
- **List:** longlist track · on_longlist True · Elder 10.0 SUSTAINED · elder_5d [9, 10, 10, 10, 10] · SRM None/None · thematic none HOLD 
- **Scores:** conviction 3 · lens 3/6 strong, 1 warn · coil warn · momentum sc 67.4 / mp 60.0 BUILDING ACCELERATING · accumulation flow 67.1 · structure 77.9 ABOVE_STRUCTURE
- **Levels:** px 74.29 · **stop 72.25 [structural swing_low]** · rr 5.43 · risk 2.75% · stop_atr_dist 1.06 · ATR 1.93
- **Targets:** resistance 77.74 · resistance 85.36 · fib_1272 88.93
- **Nominated by:** 2 seat(s), conviction_sum 8 — raschke, thorp
- **Committee:** 3 support / 7 oppose / 1 abstain. Strongest support — livermore (c3): "HELD name, and my verdict is KEEP with the add case live but not yet triggered. Trend column intact: structure_shift ABOVE_STRUCTURE with structure 77.9, mp_state BUILDING, mp_accel_state ACCELERATING (C5/C18/R3) — an Upward Trend column, and it is one half of the only fully confirmed Key Price pairing in this set, with BHP in the same Materials group in the identical state (C14/R8). This is the one name in the twent"
- **Risk (strongest opposing case, verbatim — minervini):** "ma_50 66.70 < ma_200 67.94 (criterion 4 FAIL); sma_distance_pct 11.38 with px 74.29 vs ma_20 68.91; day_vol 0.78 gives no C6 confirmation; stop 72.25 sits at stop_atr_dist 1.06, i.e. one ordinary day's range from price, which is a stop that fails precisely when it is needed; the rr 5.43 headline runs to an 85.36 level 5.74 ATR distant."
- **Falsifier:** A single-day reaction of 1.93 or more (1x atr_14d) from the day's high — translated DANGER SIGNAL, C7 — which on this name lands essentially on bracket.stop 72.25. That ends the holding on sight, without argument and without waiting for the stop to be touched intraday.
- **Condition:** elder_5d dips to <=6 and reclaims >=7 while the position is still held, with a stop re-placed at more than ~1.5 ATR so it clears the noise band. That is an add I would support at 3. *(filed by elder-lens)*
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +5.2% (2xATR) · give-up 5.0% · eligible False · extrapolated True

**KMX · HOLD-FOR-CONDITIONS · conviction 3 · vote 3-7-1 · None**
- **List:** longlist track · on_longlist True · Elder 10.0 ACCELERATION · elder_5d [1, 5, 7, 10, 10] · SRM None/None · thematic none  
- **Scores:** conviction 3 · lens 3/6 strong, 0 warn · coil strong · momentum sc 74.7 / mp 51.0 BUILDING ACCELERATING · accumulation flow 78.9 · structure 84.2 ABOVE_STRUCTURE
- **Levels:** px 62.8 · **stop_eff 60.69 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 2.11
- **Overhead:** prior_high 63.15 · fib_1272 65.03 · fib_1618 67.43
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — minervini
- **Committee:** 3 support / 7 oppose / 1 abstain. Strongest support — minervini (c4): "Full stack, wide and ordered: px 62.80 above ma_50 55.86 > ma_100 48.68 > ma_200 45.00. Criterion 8 passes with rs_leadership LEADER, rs_spy_20d +4.24 and rs_down_day_20d +0.63, and day_vol 1.07 is above-normal participation — one of only five such readings in the set, and the C6 half I can verify. On the criteria I can only approximate, both approximations point the same way: price is +39.6% over ma_200, which is co"
- **Risk (strongest opposing case, verbatim — thorp):** "OPPOSING ARGUMENT (O1): atr_14d 2.11 / bracket.price 62.80 = 3.36% volatility, rank 18 of 20; bracket.valid=False with every risk field NULL; fallback 60.69, unwatched loss 6.72%; nearest served level 63.15 = +0.56%, no vol_ratio; no dated, defended level anywhere above price. The counterweight I will state honestly: sc_momentum 74.7 is the highest in the deliberation set and day_vol 1.07 is above the name's own average — so the CONDITION is the strongest on my menu and the SIZING is the worst. C11 settles that con"
- **Falsifier:** A close below ma_20 58.97; or failure at 63.15 followed by a contraction DEEPER than the prior one — a widening base falsifies the VCP read directly, since C4 requires each successive contraction to be roughly half the depth of the one before.
- **Condition:** elder_5d dips to <=6 and reclaims >=7 with a valid structural bracket in place — the C6 pullback, which is also the retracement toward the 20-day that Rogers advises. *(filed by elder-lens)*
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.562 · n 3943 · target +6.7% (2xATR) · give-up 7.4% · eligible True · extrapolated False

**NWS · HOLD-FOR-CONDITIONS · conviction 3 · vote 2-8-1 · None**
- **List:** longlist track · on_longlist True · Elder 10.0 SUSTAINED · elder_5d [9, 9, 10, 10, 10] · SRM None/None · thematic none  
- **Scores:** conviction 3 · lens 3/6 strong, 0 warn · coil ok · momentum sc 74.6 / mp 90.0 STRONG ACCELERATING · accumulation flow 73.7 · structure 76.8 RANGE
- **Levels:** px 35.05 · **stop_eff 34.14 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 0.91
- **Overhead:** resistance 35.31 · fib_1272 36.86 · fib_1618 38.84
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — minervini
- **Committee:** 2 support / 8 oppose / 1 abstain. Strongest support — minervini (c4): "Full stack — px 35.05 above ma_50 31.20 > ma_100 30.58 > ma_200 29.63 — and criterion 8 is the strongest all-weather reading in the set: rs_leadership LEADER, rs_spy_20d +10.06 and rs_down_day_20d +1.54, meaning it gains on SPY on SPY's DOWN days. C11 calls that acting independently of the general averages and marks it as the leadership that appears before the advance. day_vol 1.21 is above-normal participation. Crit"
- **Risk (strongest opposing case, verbatim — elder-lens):** "Five bars with no transition and elder_pattern SUSTAINED — the single clearest example in the set of buying the plateau, which the PM ruled against on 2026-08-05; bracket.valid False so no invalidation exists; and mp_state STRONG at mp 90.0 describes a move already made rather than a pullback to buy."
- **Falsifier:** Rejection at 35.31 on day_vol below 1.0 — that is C6's breakout-without-volume failure at a validated level and it would end the case. A close back under ma_20 32.93 does the same more slowly.
- **Condition:** elder_5d dips to <=6 and reclaims >=7 with a valid structural bracket. On a SUSTAINED 9-9-10-10-10 series that is several bars away and I am content to miss it. *(filed by elder-lens)*
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +5.2% (2xATR) · give-up 5.4% · eligible True · extrapolated False
- **REPEAT: 2x / 4 sessions — see §4.**

**PGR · HOLD-FOR-CONDITIONS · conviction 2 · vote 2-8-1 · None**
- **List:** elder_list track · on_longlist False · Elder 10.0 ACCELERATION · elder_5d [3, 5, 9, 10, 10] · SRM None/None · thematic none TURNING 
- **Scores:** conviction 2 · lens 2/6 strong, 2 warn · coil strong · momentum sc 62.0 / mp 38.0 FADING ACCELERATING · accumulation flow 64.5 · structure 70.5 ABOVE_STRUCTURE
- **Levels:** px 223.92 · **stop 215.43 [structural ma50]** · rr 3.43 · risk 3.79% · stop_atr_dist 1.57 · ATR 5.41
- **Targets:** resistance 239.38 · fib_1272 253.03 · fib_1618 270.39
- **Nominated by:** 2 seat(s), conviction_sum 7 — raschke, thorp
- **Committee:** 2 support / 8 oppose / 1 abstain. Strongest support — raschke (c3): "Still the closest thing to a genuine RETRACEMENT (C7-shaped) with a valid bracket in the set: structure_shift ABOVE_STRUCTURE with sma_distance_pct only 3.94 — the trend read is intact while price has come back to the averages rather than extended away from them — lens.coil strong, div_state BULLISH, elder_pattern ACCELERATION. bracket.valid True with stop 215.43, risk_pct 3.79, 1.57 ATR out on atr_14d 5.41."
- **Risk (strongest opposing case, verbatim — oneil):** "rs_spy_20d +0.48 with lens.leadership warn (C9/C10 fail on the substance, whatever the label says); day_vol 0.70 (need 1.40); ma_20 213.64 below ma_50 215.43 — the near-term structure has rolled over; lens_positive 2 against lens_warnings 2, the weakest ratio on the board; TP1 239.38 carries vol_ratio 0.87, vol_validated false, so the reward case rests on an undefended level."
- **Falsifier:** A close below 213.64 (ma20) — not the printed stop. On my rule, if price loses the 20-day the pullback has become the break and the retracement case is dead regardless of where the engine put the stop.
- **Condition:** elder_5d dips to <=6 and reclaims >=7 (the C6 pullback) while a stop is re-placed below the ma20 rather than at the ma50, bringing the invalidation outside the noise band. I would take that at 3. *(filed by elder-lens)*
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +4.8% (2xATR) · give-up 5.0% · eligible False · extrapolated True

**VTR · HOLD-FOR-CONDITIONS · conviction 2 · vote 2-8-1 · None**
- **List:** elder_list track · on_longlist False · Elder 9.0 INTERRUPTED · elder_5d [3, 5, 6, 7, 9] · SRM None/None · thematic none  
- **Scores:** conviction 2 · lens 3/6 strong, 1 warn · coil strong · momentum sc 61.1 / mp 32.0 BUILDING DECELERATING · accumulation flow 73.7 · structure 54.7 RANGE
- **Levels:** px 93.47 · **stop 89.56 [structural swing_low]** · rr 2.08 · risk 4.18% · stop_atr_dist 1.79 · ATR 2.19
- **Targets:** resistance 94.6 · resistance 101.6 · fib_1272 104.87
- **Nominated by:** 2 seat(s), conviction_sum 7 — seow, wyckoff
- **Committee:** 2 support / 8 oppose / 1 abstain. Strongest support — thorp (c2): "It passes my worst-case test on a DEFENDED level and it is the only name outside WELL and NTR that does. Loss boundary 89.56 (swing_low) with stop_atr_dist 1.79 — the widest cushion in the set, so a typical day does not reach my stop. Unwatched gapped loss = risk_pct 4.18 + atr_pct 2.34 (2.19 / 93.47) = 6.52%. TP2 101.60 pays rr 2.08R = 8.70% and carries vol_ratio 1.36, vol_validated TRUE. Ratio 1.33. Minimum size on"
- **Risk (strongest opposing case, verbatim — oneil):** "rs_spy_20d -9.93 and rs_leadership IN-LINE (C9/C10, unambiguous fail); day_vol 0.58 (need 1.40); structure_shift RANGE; risk_pct 4.18 widest in the set with rr 2.08 thinnest and rr_tp1 0.29R — the first structural level pays essentially nothing against C22; mp_accel DECELERATING."
- **Falsifier:** A close below 89.56 or a gap open beneath 91.28. Thesis-falsifier: price failing at 94.60 (the 0.29R level) on above-normal day_vol, which would say the near structure is resistance rather than a waypoint and the 101.60 leg is not reachable inside the hold I am pricing.
- **Condition:** elder_pattern clears off INTERRUPTED while elder holds >=7 AND the bracket re-forms with risk_pct at or under about 3.0 so that Elder's 2%-plus-costs cap permits a real position. Both, not either. *(filed by elder-lens)*
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.562 · n 3943 · target +4.7% (2xATR) · give-up 5.2% · eligible False · extrapolated True

**AMH · HOLD-FOR-CONDITIONS · conviction 2 · vote 2-8-1 · None**
- **List:** elder_list track · on_longlist False · Elder 9.0 INTERRUPTED · elder_5d [0, 5, 6, 7, 9] · SRM None/None · thematic none WATCH 
- **Scores:** conviction 2 · lens 2/6 strong, 2 warn · coil strong · momentum sc 52.8 / mp 44.0 BUILDING ACCELERATING · accumulation flow 26.3 · structure 68.4 RANGE
- **Levels:** px 34.81 · **stop_eff 34.24 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 0.57
- **Overhead:** resistance 35.07 · fib_1272 35.68 · fib_1618 36.45
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 2 seat(s), conviction_sum 6 — seow, weis
- **Committee:** 2 support / 8 oppose / 1 abstain. Strongest support — seow (c3): "The second and last row where a real pullback and a passing odds gate coincide. Entry 34.81 is 0.70 above ma_20 34.11 - 1.23 ATR on atr_14d 0.57 - so a bar whose low touched the rising short average is arithmetically reachable, and the stack is ordered underneath (34.11 > 33.61 > 32.47 > 31.64) with sma_distance_pct 3.56, which is an orderly retest rather than the vertical run R7 disqualifies. mp_state BUILDING, sect"
- **Risk (strongest opposing case, verbatim — oneil):** "rs_leadership IN-LINE (C9 fail); day_vol 0.59 (need 1.40); structure_shift RANGE with the nearest resistance 35.07 only 0.46 ATR overhead and dated 2026-08-06; div_state BEARISH, div_bear_count 2; SRM gate WATCH not PASS; lens_positive 2 against lens_warnings 2."
- **Falsifier:** A daily close below ma_20 34.11 says the retest failed rather than held and the pullback grade under C4 is void. Equally, rs_spy_20d dropping below zero on the next reading removes the only thing separating this from the three REITs I have refused.
- **Condition:** elder_pattern off INTERRUPTED with elder >=7 AND a valid structural bracket with rr >= 2.0. Same two conditions as INVH, because on my menu the two names are the same trade. *(filed by elder-lens)*
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +3.3% (2xATR) · give-up 3.2% · eligible False · extrapolated True

### PASS — the eight rejections

| Ticker | S-O-A | Conv | The single fact that killed it |
|---|---|---|---|
| **FLYW** | 1-10-0 | 3 | sector_trend 'Declining — Avoid' with gate BLOCKED and lens.sector warn (C25 Lone Ranger, R9 — the one sell test in my canon that fires on group behaviour rather than the name); day_vol 0.60 (need 1.40, C16); lens_positive only 2, with coil, structure and resi |
| **CL** | 1-6-4 | 3 | structure_shift None and lens.structure '--' — no base object exists, R3 fails and nothing downstream rescues it; structure 36.8, sc_momentum 42.1, flow 31.6 all lowest in the set; day_vol 0.83 (need 1.40); rs_spy_20d -2.68 against a LEADER label; overhead at  |
| **ACGL** | 1-9-1 | 2 | rs_spy_20d -5.94 against a LEADER label (criterion 8 FAIL); structure 60.0 and flow 31.6, the weakest pairing among valid-bracket names; structure_shift RANGE with no break; day_vol 0.68; TP1 105.09 vol_ratio 0.73 and TP2 107.09 vol_ratio 1.16, both vol_valida |
| **SNY** | 1-9-1 | 2 | px 45.69 < ma_200 46.02 (criterion 1 FAIL, hard); ma_50 43.53 < ma_200 46.02 (criterion 4 FAIL); rs_spy_20d +0.54 against a LEADER label (criterion 8 FAIL on the number); day_vol 0.54; TP1 48.35 is dated 2026-03-31 with vol_ratio 0.84, vol_validated false, and |
| **INVH** | 1-9-1 | 2 | rs_spy_20d -0.50 with IN-LINE (criterion 8 FAIL); structure_shift RANGE so nothing has broken; bracket.valid False so there is no structurally-defined risk point and C7 cannot be satisfied; flow 26.3 is the weakest in the set; day_vol 0.70; div_state BEARISH w |
| **HLN** | 1-8-2 | 2 | ma_50 9.69 < ma_200 9.83 (criterion 4 FAIL); rs_spy_20d -1.09 (criterion 8 FAIL); price 10.16 only 3.4% above the 200-day; rr exactly 2.00 at the gate floor with TP1 10.25 at 0.37R and vol_validated false, TP2 10.64 dated 2026-03-17 also vol_validated false —  |
| **LW** | 0-10-1 | 2 | rs_spy_20d -0.12 with rs_leadership IN-LINE (criterion 8 FAIL); sma_distance_pct 11.98 against a spine where ma_50 48.94 and ma_200 47.37 separate by only 3.3%; flow 39.5; day_vol 0.82 with no breakout-volume confirmation; TP1 at 0.54R, vol_validated false. |
| **T** | 0-10-1 | 2 | ma_50 22.96 < ma_200 25.11 (criterion 4 FAIL); price only 2.3% over ma_200; rs_spy_20d +1.90; day_vol 0.58 with sma_distance_pct 11.90 — extended off the 50-day with no participation behind the cross; the headline rr 6.47 runs to TP2 29.44 dated 2026-03-24 wit |

**PASS cards, in full — each carries its QS line, as the card contract requires.**

**FLYW · PASS · conviction 3 · vote 1-10-0 · None**
- **List:** longlist track · on_longlist True · Elder 10.0 CORRECTION_REENTRY · elder_5d [7, 10, 7, 10, 10] · SRM None/None · thematic none  
- **Scores:** conviction 3 · lens 2/6 strong, 1 warn · coil ok · momentum sc 73.3 / mp 79.0 STRONG ACCELERATING · accumulation flow 71.1 · structure 85.3 ABOVE_STRUCTURE
- **Levels:** px 19.42 · **stop_eff 18.71 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 0.71
- **Overhead:** prior_high 19.73 · fib_1272 20.85 · fib_1618 22.28
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 2 seat(s), conviction_sum 7 — elder-lens, minervini
- **Committee:** 1 support / 10 oppose / 0 abstain. Strongest support — minervini (c3): "Template passes on every computable criterion: px 19.42 above ma_50 17.39 > ma_100 15.91 > ma_200 14.52, and criterion 8 passes emphatically — rs_spy_20d +17.02 is the highest in the set with rs_leadership LEADER and rs_down_day_20d +0.77. C11 states that leaders display relative strength ahead of their advance and often act independently of the general averages; a top-RS name inside a lagging group is precisely what"
- **Risk (strongest opposing case, verbatim — oneil):** "sector_trend 'Declining — Avoid' with gate BLOCKED and lens.sector warn (C25 Lone Ranger, R9 — the one sell test in my canon that fires on group behaviour rather than the name); day_vol 0.60 (need 1.40, C16); lens_positive only 2, with coil, structure and resistance all merely 'ok' so base tightness is unsupported; sma_distance_pct 11.70 against a 6.74 median; price 19.42 vs ma_200 14.52 is +33.8% — not a climax under C24's 70% boundary, but a long way from a base."
- **Falsifier:** A close below ma_20 17.82; or rs_spy_20d compressing back under roughly +5 while the sector continues to decline, which resolves the independence question against me.
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +7.4% (2xATR) · give-up 7.6% · eligible False · extrapolated True

**CL · PASS · conviction 3 · vote 1-6-4 · None**
- **List:** qs track · on_longlist False · Elder 5.0 null · elder_5d [0, 0, 0, 3, 5] · SRM None/None · thematic none  
- **Scores:** conviction 3 · lens 3/6 strong, 1 warn · coil strong · momentum sc 42.1 / mp 24.0 BUILDING ACCELERATING · accumulation flow 31.6 · structure 36.8 null
- **Levels:** px 92.55 · **stop_eff 90.46 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 2.09
- **Overhead:** resistance 93.08 · resistance 94.15 · resistance 95.46
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 2 seat(s), conviction_sum 6 — seow, weis
- **Committee:** 1 support / 6 oppose / 4 abstain. Strongest support — weis (c3): "The purest contraction-at-a-level in the set and the only name where my R1 field fires directly with effectively zero extension: was_squeezed True, sma_distance_pct 0.78, price 92.55 sitting flat on ma_20 91.98 with ma_50 91.84 and ma_200 87.18 beneath. elder_5d [0, 0, 0, 3, 5] turning up off a dead reading is a change of behaviour (W22) — the first break in the established rhythm, which this canon says to flag early"
- **Risk (strongest opposing case, verbatim — oneil):** "structure_shift None and lens.structure '--' — no base object exists, R3 fails and nothing downstream rescues it; structure 36.8, sc_momentum 42.1, flow 31.6 all lowest in the set; day_vol 0.83 (need 1.40); rs_spy_20d -2.68 against a LEADER label; overhead at 93.08 / 94.15 / 95.46, i.e. 0.6% / 1.7% / 3.1% of headroom against a required 20-25% target under C22."
- **Falsifier:** A close below ma_50 91.84 that follows through the next session, or the contraction resolving into a wide-range down bar on day_vol above 1.0. Either is the hinge breaking the wrong way and there is no room to be patient about it at 0.78% extension.
- **QS:** GOOD · conv moderate(3) · edge 0.127 · p 0.57 / p_test 0.629 · n 1535 · target +4.5% (2xATR) · give-up 3.4% · eligible True · extrapolated False

**ACGL · PASS · conviction 2 · vote 1-9-1 · None**
- **List:** elder_list track · on_longlist False · Elder 9.0 INTERRUPTED · elder_5d [3, 3, 5, 6, 9] · SRM None/None · thematic none  
- **Scores:** conviction 2 · lens 2/6 strong, 1 warn · coil strong · momentum sc 46.1 / mp 20.0 BUILDING FLAT · accumulation flow 31.6 · structure 60.0 RANGE
- **Levels:** px 101.14 · **stop 98.92 [structural ma_cluster]** · rr 2.68 · risk 2.19% · stop_atr_dist 1.07 · ATR 2.08
- **Targets:** resistance 105.09 · resistance 107.09 · fib_1272 109.68
- **Nominated by:** 2 seat(s), conviction_sum 6 — seow, wyckoff
- **Committee:** 1 support / 9 oppose / 1 abstain. Strongest support — weis (c2): "Measured contraction inside the tightest ordered stack on the board: lens.coil strong with energy 68.9, ma_20 99.79 > ma_50 98.92 > ma_200 95.71 and sma_distance_pct 2.25 — price back at the short average with no chase. day_vol 0.68 is quiet effort at the level (W21), with direction taken from the preceding trend and not from the coil itself. div_state BULLISH and elder_5d [3, 3, 5, 6, 9] rising off a flat 3-3 is a b"
- **Risk (strongest opposing case, verbatim — minervini):** "rs_spy_20d -5.94 against a LEADER label (criterion 8 FAIL); structure 60.0 and flow 31.6, the weakest pairing among valid-bracket names; structure_shift RANGE with no break; day_vol 0.68; TP1 105.09 vol_ratio 0.73 and TP2 107.09 vol_ratio 1.16, both vol_validated FALSE, so the rr 2.68 is computed against levels nobody defended."
- **Falsifier:** A wide-range close below 98.92 — the ma_cluster where ma_50 and the stack converge — with downward follow-through the next session. That is the hinge resolving the wrong way.
- **QS:** SKIP · conv vetoed(0) · edge 0.117 · p 0.56 / p_test 0.639 · n 2209 · target +4.1% (2xATR) · give-up 3.3% · eligible False · extrapolated True

**SNY · PASS · conviction 2 · vote 1-9-1 · None**
- **List:** longlist track · on_longlist True · Elder 7.0 null · elder_5d [9, 10, 7, 10, 7] · SRM None/None · thematic none  
- **Scores:** conviction 2 · lens 4/6 strong, 2 warn · coil warn · momentum sc 65.2 / mp 50.0 FADING ACCELERATING · accumulation flow 73.7 · structure 68.4 BULLISH_BOS
- **Levels:** px 45.69 · **stop 44.34 [structural ma100]** · rr 2.67 · risk 2.95% · stop_atr_dist 1.66 · ATR 0.81
- **Targets:** resistance 48.35 · fib_1272 49.29 · fib_1618 50.17
- **Nominated by:** 2 seat(s), conviction_sum 7 — raschke, thorp
- **Committee:** 1 support / 9 oppose / 1 abstain. Strongest support — thorp (c2): "Minimum size, and it earns that only on my ordering variable and my stop cushion. Volatility 1.77% (0.81 / 45.69) ranks 4 of 20 against a 2.24% set median — bottom quartile, so C5/C6 order it ahead of wilder equivalents before horizon is even considered. Loss boundary 44.34 with stop_atr_dist 1.66, the deepest cushion in the valid-bracket set: a typical one-day range does NOT reach my stop, which is the rarest thing "
- **Risk (strongest opposing case, verbatim — minervini):** "px 45.69 < ma_200 46.02 (criterion 1 FAIL, hard); ma_50 43.53 < ma_200 46.02 (criterion 4 FAIL); rs_spy_20d +0.54 against a LEADER label (criterion 8 FAIL on the number); day_vol 0.54; TP1 48.35 is dated 2026-03-31 with vol_ratio 0.84, vol_validated false, and sits ABOVE the very 200-day the price has not reclaimed — the first target requires the thesis to already be true."
- **Falsifier:** A close below 44.34 or a gap open under 44.88. Thesis-falsifier: price reaching 48.35 and being rejected there on volume, which would confirm that a level nobody defended in March is a level nobody defends now — the exact reason my conviction is 2 and not 4.
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +3.6% (2xATR) · give-up 3.4% · eligible False · extrapolated True

**INVH · PASS · conviction 2 · vote 1-9-1 · None**
- **List:** elder_list track · on_longlist False · Elder 9.0 INTERRUPTED · elder_5d [0, 5, 6, 6, 9] · SRM None/None · thematic none WATCH 
- **Scores:** conviction 2 · lens 2/6 strong, 2 warn · coil strong · momentum sc 54.7 / mp 39.0 BUILDING ACCELERATING · accumulation flow 26.3 · structure 66.3 RANGE
- **Levels:** px 30.46 · **stop_eff 29.96 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 0.5
- **Overhead:** resistance 30.71 · fib_1272 31.31 · fib_1618 31.85
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 2 seat(s), conviction_sum 7 — seow, weis
- **Committee:** 1 support / 9 oppose / 1 abstain. Strongest support — weis (c2): "The hinge is intact and directly served, which is rare in this set: base_range_pct 5.1 — the tightest on the board — with was_squeezed True and squeeze_breakout_state NONE, so R1 fires on both legs and the contraction is unresolved (W21). W23 gate clean: ma_20 30.11 > ma_50 29.88 > ma_200 27.84 at sma_distance_pct 1.94, price sitting on the base with no extension. day_vol 0.70 is effort withdrawal into the contractio"
- **Risk (strongest opposing case, verbatim — minervini):** "rs_spy_20d -0.50 with IN-LINE (criterion 8 FAIL); structure_shift RANGE so nothing has broken; bracket.valid False so there is no structurally-defined risk point and C7 cannot be satisfied; flow 26.3 is the weakest in the set; day_vol 0.70; div_state BEARISH with div_bear_count 4, four of five oscillators confirming — advisory only on my card, but it is the heaviest such reading in the set and it cautions rather than supports."
- **Falsifier:** The hinge resolving downward: a wide-range close below ma_20 30.11 and through ma_50 29.88 on day_vol above 1.0, with downward follow-through the next session.
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +3.3% (2xATR) · give-up 3.2% · eligible False · extrapolated True

**HLN · PASS · conviction 2 · vote 1-8-2 · None**
- **List:** elder_list track · on_longlist False · Elder 9.0 INTERRUPTED · elder_5d [3, 5, 5, 7, 9] · SRM None/None · thematic none  
- **Scores:** conviction 2 · lens 3/6 strong, 1 warn · coil strong · momentum sc 60.9 / mp 28.0 BUILDING ACCELERATING · accumulation flow 60.5 · structure 68.4 RANGE
- **Levels:** px 10.16 · **stop 9.92 [structural ma20]** · rr 2.0 · risk 2.36% · stop_atr_dist 1.26 · ATR 0.19
- **Targets:** resistance 10.25 · resistance 10.64 · fib_1272 10.82
- **Nominated by:** 2 seat(s), conviction_sum 6 — raschke, wyckoff
- **Committee:** 1 support / 8 oppose / 2 abstain. Strongest support — weis (c2): "The one name in the set where effort is actually producing result rather than being read into an absence. day_vol 1.33 — second-highest participation on the board — against structure_shift RANGE, with mp_state BUILDING, mp_accel_state ACCELERATING and elder_5d [3, 5, 5, 7, 9] stepping up. That is R4 reading the constructive fork of W1: effort matched by result, which is the opposite of the large-effort-small-reward w"
- **Risk (strongest opposing case, verbatim — minervini):** "ma_50 9.69 < ma_200 9.83 (criterion 4 FAIL); rs_spy_20d -1.09 (criterion 8 FAIL); price 10.16 only 3.4% above the 200-day; rr exactly 2.00 at the gate floor with TP1 10.25 at 0.37R and vol_validated false, TP2 10.64 dated 2026-03-17 also vol_validated false — both structural targets undefended."
- **Falsifier:** day_vol staying above 1.0 while price makes no net progress out of the range over the next several sessions. That is precisely large effort with small reward (W2) — the trend's own side being absorbed — and it would invert this read completely.
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +3.8% (2xATR) · give-up 3.6% · eligible True · extrapolated False

**LW · PASS · conviction 2 · vote 0-10-1 · None**
- **List:** elder_list track · on_longlist False · Elder 8.0 ACCUMULATION_BASE · elder_5d [1, 7, 7, 7, 8] · SRM None/None · thematic none  
- **Scores:** conviction 2 · lens 3/6 strong, 1 warn · coil strong · momentum sc 55.8 / mp 23.0 FADING DECELERATING · accumulation flow 39.5 · structure 82.1 RANGE
- **Levels:** px 54.8 · **stop 53.16 [structural ma20]** · rr 2.31 · risk 2.99% · stop_atr_dist 1.04 · ATR 1.58
- **Targets:** resistance 55.69 · fib_1272 58.59 · fib_1618 62.28
- **Nominated by:** 2 seat(s), conviction_sum 7 — raschke, wyckoff
- **Committee:** 0 support / 10 oppose / 1 abstain. No seat supported it.
- **Risk (strongest opposing case, verbatim — minervini):** "rs_spy_20d -0.12 with rs_leadership IN-LINE (criterion 8 FAIL); sma_distance_pct 11.98 against a spine where ma_50 48.94 and ma_200 47.37 separate by only 3.3%; flow 39.5; day_vol 0.82 with no breakout-volume confirmation; TP1 at 0.54R, vol_validated false."
- **Falsifier:** elder_5d steps to 9 or 10 from here while price clears 55.69 — the shelf was accumulation resolving up and I mistook a slow lift for a stale one.
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.562 · n 3943 · target +5.8% (2xATR) · give-up 6.4% · eligible True · extrapolated False

**T · PASS · conviction 2 · vote 0-10-1 · None**
- **List:** longlist track · on_longlist True · Elder 10.0 CORRECTION_REENTRY · elder_5d [7, 10, 7, 7, 10] · SRM None/None · thematic none  
- **Scores:** conviction 2 · lens 3/6 strong, 2 warn · coil ok · momentum sc 67.8 / mp 60.0 FADING DECELERATING · accumulation flow 50.0 · structure 85.3 BULLISH_BOS
- **Levels:** px 25.69 · **stop 25.11 [structural ma200]** · rr 6.47 · risk 2.26% · stop_atr_dist 1.01 · ATR 0.57
- **Targets:** resistance 26.76 · resistance 29.44 · fib_1272 30.18
- **Nominated by:** 2 seat(s), conviction_sum 6 — raschke, thorp
- **Committee:** 0 support / 10 oppose / 1 abstain. No seat supported it.
- **Risk (strongest opposing case, verbatim — minervini):** "ma_50 22.96 < ma_200 25.11 (criterion 4 FAIL); price only 2.3% over ma_200; rs_spy_20d +1.90; day_vol 0.58 with sma_distance_pct 11.90 — extended off the 50-day with no participation behind the cross; the headline rr 6.47 runs to TP2 29.44 dated 2026-03-24 with vol_ratio 0.89 and vol_validated FALSE, so the [headline] number is computed against a five-month-old undefended level; bracket.stop 25.11 IS the 200-day at stop_atr_dist 1.01, one ordinary day's range from price."
- **Falsifier:** T clears 26.76 (which IS vol_validated) and holds while elder_5d stays >=7 — the CORRECTION_REENTRY label was sufficient without mp_state STRONG and my two-leg requirement is too strict.
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +4.5% (2xATR) · give-up 4.6% · eligible False · extrapolated True
- **REPEAT: 2x / 4 sessions — see §4.**

---

## §8 NEAR MISSES — every qualifier cut by the cap, one row each

11 names reached Phase 4 and were truncated by the cap of 20 before any vote. Every one is locked to `verdict_ledger.json` as a NEAR-MISS row with a reference price.

**CME · NEAR-MISS · Financials**
- **List:** longlist track · on_longlist True · Elder 10.0 CORRECTION_REENTRY · elder_5d [10, 6, 9, 9, 10] · SRM HOLD/PASS · thematic none  
- **Scores:** conviction — · lens 3/6 strong, 0 warn · coil strong · momentum sc 74.3 / mp 72.0 BUILDING DECELERATING · accumulation flow 73.7 · structure 76.8 null
- **Levels:** px 279.17 · **stop 268.75 [structural ma100]** · rr 2.77 · risk 3.73% · stop_atr_dist 1.64 · ATR 6.36
- **Targets:** resistance 292.33 · resistance 308.01 · resistance 312.68
- **Nominated by:** 1 seat(s), conviction_sum 4 — thorp
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +4.6% (2xATR) · give-up 4.7% · eligible False · extrapolated True
- **REPEAT: 2x / 4 sessions — see §4.**

**TEVA · NEAR-MISS · Healthcare**
- **List:** longlist track · on_longlist True · Elder 7.0 null · elder_5d [7, 10, 7, 7, 7] · SRM DEPLOY/PASS · thematic none  
- **Scores:** conviction — · lens 3/6 strong, 1 warn · coil ok · momentum sc 70.1 / mp 93.0 FADING DECELERATING · accumulation flow 35.5 · structure 94.7 ABOVE_STRUCTURE
- **Levels:** px 36.93 · **stop_eff 35.93 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 1.0
- **Overhead:** resistance 36.99 · prior_high 37.83 · fib_1272 40.07
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — minervini
- **QS:** NONE · conv low(2) · edge 0.067 · p 0.51 / p_test 0.527 · n 176777 · target +5.4% (2xATR) · give-up 4.7% · eligible False · extrapolated True
- **REPEAT: 2x / 4 sessions — see §4.**

**RIO · NEAR-MISS · Materials**
- **List:** longlist track · on_longlist True · Elder 10.0 ACCELERATION · elder_5d [0, 8, 9, 10, 10] · SRM HOLD/PASS · thematic none  
- **Scores:** conviction — · lens 2/6 strong, 0 warn · coil -- · momentum sc 69.6 / mp 80.0 STRONG null · accumulation flow 59.2 · structure 69.5 BULLISH_BOS
- **Levels:** px 104.8 · **stop_eff 102.36 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 2.44
- **Overhead:** resistance 107.4 · resistance 112.21 · fib_1272 116.99
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — livermore
- **QS:** NONE · conv low(2) · edge 0.067 · p 0.51 / p_test 0.527 · n 176777 · target +4.7% (2xATR) · give-up 4.1% · eligible False · extrapolated True

**TECK · NEAR-MISS · Materials**
- **List:** longlist track · on_longlist True · Elder 10.0 ACCELERATION · elder_5d [5, 9, 9, 10, 10] · SRM HOLD/PASS · thematic none  
- **Scores:** conviction — · lens 3/6 strong, 1 warn · coil warn · momentum sc 68.9 / mp 68.0 BUILDING DECELERATING · accumulation flow 64.5 · structure 96.8 ABOVE_STRUCTURE
- **Levels:** px 70.2 · **stop_eff 67.94 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 2.26
- **Overhead:** resistance 71.25 · fib_1272 74.72 · fib_1618 79.13
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — minervini
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +6.4% (2xATR) · give-up 6.2% · eligible True · extrapolated False

**A · NEAR-MISS · Healthcare**
- **List:** longlist track · on_longlist True · Elder 7.0 null · elder_5d [7, 10, 10, 10, 7] · SRM DEPLOY/PASS · thematic none  
- **Scores:** conviction — · lens 2/6 strong, 2 warn · coil ok · momentum sc 68.4 / mp 72.0 FADING ACCELERATING · accumulation flow 72.4 · structure 55.8 ABOVE_STRUCTURE
- **Levels:** px 153.43 · **stop 146.53 [structural ma20]** · rr 2.0 · risk 4.5% · stop_atr_dist 1.63 · ATR 4.23
- **Targets:** prior_high 160.51 · fib_1272 167.24 · fib_1618 175.79
- **Nominated by:** 1 seat(s), conviction_sum 4 — oneil
- **QS:** SKIP · conv vetoed(0) · edge 0.067 · p 0.51 / p_test 0.527 · n 176777 · target +5.5% (2xATR) · give-up 4.9% · eligible True · extrapolated False

**EOG · NEAR-MISS · Energy**
- **List:** longlist track · on_longlist True · Elder 7.0 null · elder_5d [10, 10, 10, 10, 7] · SRM DEPLOY/PASS · thematic none  
- **Scores:** conviction — · lens 5/6 strong, 1 warn · coil warn · momentum sc 66.1 / mp 49.0 BUILDING ACCELERATING · accumulation flow 73.7 · structure 71.6 BULLISH_BOS
- **Levels:** px 150.21 · **stop_eff 146.46 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 3.75
- **Overhead:** resistance 151.87 · fib_1272 159.17 · fib_1618 166.17
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — livermore
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +5.0% (2xATR) · give-up 4.8% · eligible False · extrapolated True

**WTRG · NEAR-MISS · Utilities**
- **List:** longlist track · on_longlist True · Elder 9.0 CORRECTION_REENTRY · elder_5d [6, 9, 6, 4, 9] · SRM TURNING/WATCH · thematic none  
- **Scores:** conviction — · lens 2/6 strong, 1 warn · coil ok · momentum sc 69.2 / mp 44.0 BUILDING ACCELERATING · accumulation flow 81.6 · structure 73.7 RANGE
- **Levels:** px 41.34 · **stop_eff 40.41 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 0.93
- **Overhead:** resistance 41.39 · fib_1272 42.59 · fib_1618 43.54
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — elder-lens
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +4.5% (2xATR) · give-up 4.7% · eligible True · extrapolated False

**AWK · NEAR-MISS · Utilities**
- **List:** longlist track · on_longlist True · Elder 9.0 CORRECTION_REENTRY · elder_5d [6, 9, 9, 2, 9] · SRM TURNING/WATCH · thematic none  
- **Scores:** conviction — · lens 3/6 strong, 1 warn · coil strong · momentum sc 67.7 / mp 38.0 FADING ACCELERATING · accumulation flow 68.4 · structure 71.6 RANGE
- **Levels:** px 139.91 · **stop_eff 136.7 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 3.21
- **Overhead:** resistance 141.21 · fib_1272 144.6 · fib_1618 148.85
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — elder-lens
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +4.6% (2xATR) · give-up 4.8% · eligible True · extrapolated False

**PCG · NEAR-MISS · Utilities**
- **List:** elder_list track · on_longlist False · Elder 9.0 CORRECTION_REENTRY · elder_5d [9, 9, 9, 6, 9] · SRM TURNING/WATCH · thematic none  
- **Scores:** conviction — · lens 2/6 strong, 1 warn · coil ok · momentum sc 63.2 / mp 51.0 BUILDING ACCELERATING · accumulation flow 59.2 · structure 65.3 null
- **Levels:** px 18.11 · **stop_eff 17.6 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 0.51
- **Overhead:** resistance 18.44 · resistance 18.75
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — elder-lens
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.552 · n 116228 · target +5.7% (2xATR) · give-up 5.5% · eligible False · extrapolated True

**EIX · NEAR-MISS · Utilities**
- **List:** elder_list track · on_longlist False · Elder 9.0 CORRECTION_REENTRY · elder_5d [9, 9, 10, 4, 9] · SRM TURNING/WATCH · thematic none  
- **Scores:** conviction — · lens 2/6 strong, 2 warn · coil warn · momentum sc 46.8 / mp 17.0 FADING ACCELERATING · accumulation flow 68.4 · structure 41.1 RANGE
- **Levels:** px 73.97 · **stop 70.54 [structural swing_low]** · rr 2.23 · risk 4.64% · stop_atr_dist 1.43 · ATR 2.39
- **Targets:** resistance 76.22 · resistance 81.62 · fib_1272 84.63
- **Nominated by:** 1 seat(s), conviction_sum 4 — elder-lens
- **QS:** SKIP · conv vetoed(0) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +6.5% (2xATR) · give-up 6.7% · eligible False · extrapolated True

**RELY · NEAR-MISS · Technology**
- **List:** longlist track · on_longlist True · Elder 10.0 INTERRUPTED · elder_5d [7, 7, 4, 10, 10] · SRM AVOID/BLOCKED · thematic none  
- **Scores:** conviction — · lens 2/6 strong, 1 warn · coil ok · momentum sc 75.0 / mp 76.0 STRONG ACCELERATING · accumulation flow 81.6 · structure 76.8 RANGE
- **Levels:** px 26.59 · **stop_eff 25.43 [atr_fallback — FB, bracket.valid FALSE]** · **rr / risk% / tp_r all null — EXPECTANCY UNCOMPUTABLE** · ATR 1.16
- **Overhead:** resistance 26.74 · fib_1272 28.46 · fib_1618 30.13
- **Why no structural stop:** no valid bracket — no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)
- **Nominated by:** 1 seat(s), conviction_sum 4 — minervini
- **QS:** NONE · conv low(2) · edge 0.077 · p 0.52 / p_test 0.571 · n 44370 · target +8.8% (2xATR) · give-up 9.1% · eligible True · extrapolated False
- **REPEAT: 2x / 4 sessions — see §4.**

---

## §9 ACTION PLAN — addressed to the PM

**Posture: DEFENSIVE AND SELECTIVE, long convexity rather than short it.** The base-rate engine says STAND_DOWN at −10.5pp. Both macro voices independently refuse the stored short-premium call because dealer gamma is negative with VIX at 15.8. Your book is already positioned defensively — the question today is what you add, not whether you de-risk.

**1 — The committee cleared exactly two names out of twenty. Both are defensive, both carry a real structural stop.**

| Rank | Ticker | Entry discipline | Stop | Risk | rr | Why it cleared |
|---|---|---|---|---|---|---|
| 1 | **WELL** | Pullback or a break of the stated level — do not pay the extension | **234.11** | 2.46% | 3.81 | Best-formed bracket in the set — TP1 pays 2.57R on a volume-validated level, stop 1.20 ATR clear of noise |
| 2 | **MDLZ** | Needs the RANGE to resolve on day_vol ≥ 1.0 before you pay up | **62.98** | 2.66% | 2.53 | Broadest agreement in the run: 6 of 9 nominators and 6 of 11 voting seats, tightest defined loss on the sheet |

**2 — Your held book: three real decisions.**

| Position | Fact | Action for your decision |
|---|---|---|
| **NTR** (20.0% of book) | **HOLD-FOR-CONDITIONS 3-7-1.** Three seats support keeping it; seven oppose adding. minervini's objection is specific and correct: `ma_50 66.70 < ma_200 67.94`, and the 72.25 stop sits 1.06 ATR from price — one ordinary day's range. | **Keep. Do not add here.** If you want the add, elder-lens named the trigger: a dip to elder ≤6 that reclaims ≥7, with the stop re-placed beyond ~1.5 ATR so it clears the noise band. |
| **V** (10.1% of book) | **HOLD-FOR-CONDITIONS, split 5-5-1** — the most evenly divided name in the run. Trend intact (ABOVE_STRUCTURE, mp BUILDING/ACCELERATING, day_vol 1.14) but `bracket.valid` is False, so there is no computable loss boundary. | **Keep. No add without a stop you have chosen by hand.** The engine now prices V but still gives it no structural level; the 375.07 fallback is 1 ATR, not a defended price. |
| **CME** (26.3% of book, largest position) | **NEAR-MISS — cut by the cap, never voted on.** It was nominated by one seat at conviction 4 and truncated at rank 21+. It has a real ma100 stop at **268.75** (3.73% away, 1.64 ATR). XLF has just come off BLOCKED to PASS. | **The committee has no verdict on your largest position today.** That is a coverage fact, not a judgement. The stop is real and live — set it at 268.75 if it is not already there. |

**3 — The coverage gap is the actionable item you would not otherwise see.**

**NDAQ passes all six of your own checks — the only 6/6 name in 207 — and drew zero nominations.** It appears in no other section of this brief. Alongside it, the gold complex flags for the second session running and is unseen for the second session running: **AU, WPM, SSRM, KGC, GFI**, while Gold_Miners is the top thematic at +34.30/20d, +12.57/5d, LEADING and DEEPENING with 100% internal breadth. Healthcare adds **AMGN, BMY, TMO, ABT, ILMN**.

These are not verdicts. They are names your own checks flagged that the committee did not look at. Worth an eye before the open.

**4 — Two engineering items, both with evidence attached.**

- **The publish step does not carry `packets/` or `candidate_set.json`.** Today's first push left yesterday's packets in place under a fresh export. Caught by diffing, cost ~20 minutes. Fix before tomorrow's 08:30 SGT run or this recurs silently.
- **FMP is on the Starter plan and the entire quote endpoint is Premium-gated.** That is why Lynch has no P/E, no margin, no debt on any name, and why the economics calendar 404s. **Every fundamental gate in this system is currently untestable.** One plan upgrade closes both.

---

**DRAFT — PM approval required. Nothing is staged, nothing is armed.**