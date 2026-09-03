# AEGIS CIO BRIEF — 2026-09-03

Run `pma-2026-09-03` · export dated 2026-09-03, exported 14:38:31 SGT · Crown artifact generated 2026-09-03T14:38:29+08:00 · both same-day verified.

---

## THE BOTTOM LINE

**There are no trades today.** Fifteen names reached deliberation. Zero advanced. Fourteen are HOLD-FOR-CONDITIONS and one — NFLX — is a PASS. Not one name cleared the bar of support outnumbering opposition with a median support conviction of 3 or better.

That is not a near miss. Only one name in fifteen even got more support votes than opposing votes (WTRG, 4 support against 2 oppose), and its four supporters all filed at conviction 2 — the median support conviction was 2.0 against a required 3. On the other fourteen, the committee's opposition either outnumbered or tied its support.

**What it means for the book today:** nothing is bought, nothing is sold, nothing is staged. The three held positions (WEAT, BRZE, HNGE) stay as they are; today's work on them is stop discipline, not adds. The fourteen HOLD names are a **watch list, not a soft buy list.** A HOLD-FOR-CONDITIONS verdict means the committee has written down the specific, observable thing that would have to happen before the name is tradeable, and that thing has not happened. Every card in §7 carries that Condition line. Until a Condition prints, the name is a name to watch and nothing more.

**Why the whole set stalled, in one sentence:** the committee was handed a universe of names that were already selected for momentum, and then asked to find a reason to buy momentum in a tape where breadth is narrowing, the two macro seats disagree about the direction of travel, and there is no event calendar behind any entry.

---

## RUN HEADER — DEGRADATIONS, FLAGS AND DECLARED GAPS

**Degradations (verbatim from `run_manifest.json`):**

| Step | Note | Logged |
|---|---|---|
| GATHER | `data_steward_agent_bypassed_known_nonfunctional` | 07:49:49Z |
| PREPARE | `packet_local_slice` | 07:49:49Z |
| MACRO | `macro_no_registrar_validate` | 08:20:51Z |
| VOTE | `F1_deviation_caused_fabrication_attempt1_rejected_in_full` | 08:54:33Z |

**Plus, declared here as required:** the Round-2 vote was filed on the **third attempt**. Attempts 1 and 2 were rejected in full when seats returned fabricated packet contents. Attempt 1 handed each seat its packet by path rather than inlined; every return that produced a ballot invented the packet's contents — elder-lens claimed a deliberation set of AMD/APH/AVGO/BSX/CRWD/GEV/GLW/HWM/IBKR/JBL/NVDA/ORCL/PLTR/RCL/TSLA, oneil claimed TMUS/AXP/VST/MCK/BSX/CAT plus an invented duplicate-ticker defect, raschke claimed SNDK/CRDO/IBKR/APP/HOOD/ANET/MU/SMCI/RIVN, and every claimed sha256 was wrong. Attempt 2 (voice-agent filesystem) was rejected in full for the same reason. Nothing from either attempt was committed. Attempt 3 filed via general-purpose agents reading their own seat cards and the packet from disk; **every committed ballot carries a verified packet MD5 and a verbatim proof-line, checked before validation.** The read-proof gate caught 100% of the fabrication, which is why this is a caught incident and not a corrupted tally.

**Lint flags:** run-level flags — none. Seat-level — one: `VOTE/thorp` carries `BRACKET_BASIS:WTRG`.

**Seat counts:** 9 of 9 nominators committed (quorum 8/9). 4 of 4 challenge seats committed. 2 of 2 macro seats committed. 11 of 11 Round-2 ballots committed. Two Round-1 reasons (minervini on RELY, raschke on VALE) were rejected on the 300-character cap and re-authored by their own seats — judgment and conviction unchanged, conductor edited nothing.

**Declared gaps (a missing input is declared, never reconstructed):**

- `export_context.sector_layer` is **null**. §2 is built from the per-name sector and thematic fields in `candidate_set.json` and from the two macro forms. There is no separate sector-layer file this run.
- **Economic calendar: UNAVAILABLE** (FMP HTTP 404). There is no event-risk overlay on any name in this brief.
- **Dealer gamma / option positioning: UNAVAILABLE** (Alpaca and Tiger credentials absent for QQQ and SPY). The R9 knife-edge check was not run in either direction — a skipped check, not a passed one.
- **Divergence composition unread:** the export reports `warnings_lit: 13` with `which: []` empty. Thirteen warnings fired and not one is named. Both macro seats declined to round this to zero.
- **Repeat-watch ledger gaps:** 14 (date, ticker) pairs have no `verdict_ledger` row — record-verdicts was not run on those dates, or they predate the ledger. They are printed as GAP rows in §4, not silently dropped.
- **Lynch's fundamental pack is partly dark:** cash and absolute long-term debt, debt by kind and maturity, payout ratio, institutional ownership, five-year EPS series and historical P/E averages are all unserved. Several of his highest-value tests could not run.
- **No catalyst field exists on the deliberation record.** See the third process finding below.

---

## WHAT TODAY'S PROCESS TELLS YOU — FOUR FINDINGS ABOUT THE RUN, NOT ABOUT ANY NAME

These four came out of the challenge round. They are about the integrity of today's search, so they sit at the front rather than buried in a card.

**1. The filter partly agreed with itself (Rogers).** Today's universe was cut from 133 names to 44 by a new LAYER 0 rule: keep only names on **both** the AQE longlist **and** the elder list (42 names), plus the 2 held names outside that intersection. But elder-lens is also one of the nine nominating seats. Rogers, verbatim: *"The committee was handed a universe defined as the INTERSECTION of the AQE longlist and the elder list, and then one of the nine nominating seats is elder-lens itself - voting on the universe its own instrument defined."* Elder-lens filed on **7 of the 15** qualifying names (VRNS, CEG, EQT, WTRG, VALE, RELY, BNS) — the largest footprint of any seat. Any name whose second or marginal seat is elder-lens has one fewer independent confirmation than its nomination count suggests.

**2. Not one of the fifteen carries a named catalyst (Rogers).** He applied the test to all fifteen and read all 40 Round-1 reasons. Verbatim: *"NOT ONE of the fifteen names carries a named catalyst... every stated basis is price, volume, moving-average geometry, oscillator state or payoff arithmetic. There is no external event, no supply change, no demand change, no product, no policy, no filing, no earnings item mentioned anywhere in the record."* This is not a criticism of any seat — there is no catalyst field on the record, the calendar returned 404, and no seat has news or filing access. It is a structural fact the PM should have on paper: **this is a pure momentum book, priced entirely off its own charts.**

**3. The same filter switched off two of the committee's measuring instruments (Steenbarger F1).** Because admission required being on the elder list and the momentum longlist, every one of the fifteen scores elder 8–10 and sc_momentum 67.1–83.4. Verbatim: *"A field that does not vary across the candidate set carries no discriminating information, no matter how strong its absolute level. Any conviction resting on elder force or momentum strength is restating why the name was allowed into the room."*

**4. The elder seat's own veto could not fire (elder-lens, on the record).** Elder-lens filed the matching censor note itself and accepted Rogers' charge without contest. Verbatim: *"LAYER 0 admitted on the elder list, so every name here already clears my permission gate and elder LEVEL carries no discriminating information. No vote cites it."* Its red-flag veto — the instrument that exists to forbid buying a name outright — fired on **nobody** today, precisely because the filter had pre-selected elder-list names. The filter disarmed the seat's veto. Elder-lens also stated the effect on its own ballot: *"7 R1 nominations become 4 SUPPORTs, none above 3, two withdrawn to OPPOSE, and not one conviction raised."*

**And a fifth, from detect-lens, which cuts against the natural reading of the bracket column:** bracket validity is **inversely** correlated with trend order in this set. Only 5 of 15 names have a valid structural bracket — VRNS, CEG, EQT, VALE, NFLX — and **three of those five (CEG, EQT, NFLX) are the names trading BELOW their 200-day** with descending ma50 < ma100 < ma200 stacks. Verbatim: *"Any nominator citing bracket validity as a quality signal is, in this specific set, selecting for names that have been trading below old ranges long enough to leave structure behind."*

---

## 1. MACRO POSITION

**Plainly, what the tape looks like today.** The index is quiet and the inside of the market is not. VIX is 15.2 with the term structure in contango — lower than 85% of the past two years — and there is no volatility accident in progress (single-stock vs index vol gap 20.59, compressing, gap_change_20d -7.08). Beneath that calm, the average stock is losing to the index: equal-weight against cap-weight (RSP/SPY) sits at 0.285692, which is **0.47% below its own 20-day average of 0.287029**, with the 5-day change at -1.462%. Small caps are losing to large by 1.32 over 20 days (SPY roc20 -0.60 vs IWM roc20 -1.92). Eight of eleven sectors are below their 20-day average. The one genuine trend is energy and commodities: oil is up 10.84% over five days and 22.87% over twenty (USO), XLE roc20 +13.59 and leading, agricultural commodities +15.60 roc20 on 100% member breadth. Rates are the live pressure — TLT roc5 -1.62, roc20 -1.27, below its 20-day, with trend-following funds short the rates complex at -0.5241.

**Where the two macro seats disagree — surfaced, not settled.** Crown emits **BROADENING_CARRY at 0.75x** but grades its own match quality **poor** and lists `broadening` in its *not met* conditions — Crown's words: *"CONTRADICTED, not merely absent."* Druckenmiller, served data points only with Crown's family and size deliberately withheld, independently read **narrowing** and **LIGHT**: *"A one-day-old label at 0.45 confidence should not outweigh five converging proxies."* They also disagree on the scenario. Crown reports INFLATION_SHOCK leading at 0.75 share-of-conditions with DOLLAR_SQUEEZE inside 12%, and calls the overlap contested. Druckenmiller says the inflation label is overstated: *"a commodity-led inflation repricing does not arrive with gold AND copper both falling"* (GLD roc5 -4.40, CPER roc5 -1.32) and would relabel it an oil-supply move on top of rising real rates. He also rejects the dollar-squeeze runner-up as noise (UUP roc20 +0.28%, with DX at 99.356 still 0.47% below its trend-follower flip at 99.8263). **Both readings are left standing for the PM.** What they agree on: the oil move is real and confirmed on four independent measures; rates are the live pressure channel; the tape is narrow; volatility is genuinely normal rather than suppressed.

**So what — what this read means for the book.**

- **WEAT (held):** *helped, and crowded.* Agriculture is the single strongest trend in the dataset (Agri_Commodities roc20 +15.60, roc5 +9.86, 100% member breadth, LEADING/DEEPENING) and WEAT's own trend column is intact (rs_spy_20d 16.4, mp 89.0 STRONG). It is also the most crowded position in the dataset — CTA agricultural bias +0.6578, the highest of any sector, with large speculators crowded long corn, soybeans and wheat. Druckenmiller's words: *"that is a stop-discipline point rather than an add point."* The nearest wheat CTA flip is 24.12% away, so there is no mechanical trigger nearby.
- **BRZE (held):** *pressured.* Its basket, Enterprise_Software, carries a DEPLOY grade (roc20 +11.9, 71.4% breadth) but Druckenmiller flags a RISING_WEDGE BEARISH FORMING on it at fit 0.833, with Cloud_Computing showing the same pattern already TRIGGERED and Payments carrying it too — *"Three linked complexes showing the same bearish structure is a cluster."* Its own participation is thin (day_vol 0.52) and momentum is FADING.
- **HNGE (held):** *pressured.* Healthcare (XLV) is one of only two DEPLOY-grade sectors and it reads "Momentum Fading — Hold, Don't Add" with divergence -5.69, RRG quadrant WEAKENING/ENTERING. HNGE's own flow is 43.4 and its momentum state is FADING.
- **Today's fifteen candidates, as a group:** *headwind.* Every one of them is a breakout, re-entry or continuation thesis, and those are broadening-tape trades. Breadth is narrowing on every proxy either macro seat could construct. Seven of the fifteen sit in Energy (5) and Utilities (2); the Energy grade is "Momentum Fading — Hold, Don't Add." Add the missing calendar: **a VIX of 15.2 with no event overlay is an unmeasured tape, not a calm one** (Rogers' phrasing, and both macro seats say the same).
- **One dated risk, unattributed:** the export flags a held-book **earnings event on 2026-09-08** as the report most able to move the book. The record does not name which position it belongs to, and with the calendar at 404 there is no layer behind that flag. **No read** on its direction or outcome.

---

## 2. SECTOR & THEMATICS

*Declared: `export_context.sector_layer` is null. This section is built from the per-name sector and thematic fields in the candidate set and from the two macro forms.*

| Sector | Gate | Sector trend state | Names in today's 15 |
|---|---|---|---|
| Energy | PASS | Momentum Fading — Hold, Don't Add | 5 — LNG, EQT, COP, OXY, CVX |
| Utilities | WATCH | Recovering From Weakness — Watch for Entry | 2 — CEG, WTRG |
| Materials | PASS | Momentum Fading — Hold, Don't Add | 2 — VALE, CTVA |
| Technology | WATCH | Recovering From Weakness — Watch for Entry | 2 — VRNS, RELY |
| Financials | BLOCKED | Declining — Avoid | 2 — SLDE, BNS |
| Industrials | WATCH | Recovering From Weakness — Watch for Entry | 1 — DE |
| Communication Services | PASS | Momentum Fading — Hold, Don't Add | 1 — NFLX |
| Healthcare | PASS | Momentum Fading — Hold, Don't Add | 0 (held: HNGE) |
| Consumer Discretionary | WATCH | Recovering From Weakness — Watch for Entry | 0 |
| Consumer Staples | BLOCKED | Declining — Avoid | 0 |

Baskets represented in the 44-name universe: Agri_Commodities DEPLOY (4 names), Gaming_Streaming DEPLOY (2), plus one each of Biotech DEPLOY, Enterprise_Software DEPLOY, Midstream_MLP DEPLOY, Cybersecurity TURNING, Infra_Power TURNING, Big_Banks TURNING, E_Commerce TURNING.

**Backwards — why these groups look the way they do in this environment.** Energy and agriculture lead because that is where the actual price move is: oil +22.87% over twenty days, agricultural commodities +15.60% on full member participation, oil services +12.15 roc5 at 62.5% breadth, midstream +5.06 at 80% breadth. Four separate layers — futures, sector, basket and CTA positioning — point the same way, which is why both macro seats accept the energy move as real. But leadership is late rather than early: only two sectors carry a DEPLOY grade (XLE and XLV) and **both are labelled "Momentum Fading — Hold, Don't Add"** with negative divergence (XLV -5.69, XLE -9.32). Utilities, Technology and Industrials read "Recovering From Weakness — Watch for Entry" — a *watch* label, not a *deploy* label. Financials and Consumer Staples read "Declining — Avoid." On Rogers' count of the entry-gate layer, **zero of eleven sector gates are OPEN**: 2 WATCH, 4 CAUTION, 5 BLOCKED.

**Forwards — where today's output actually sits against that.** It sits badly, and this is the uncomfortable sentence said outright: **seven of the fifteen names concentrate in Energy and Utilities, and Energy — the largest single block at 5 names — is the sector the system's own macro layer grades "Hold, Don't Add."** All five Energy names carry a *strong* sector lens reading while the macro grade for Energy says fade; detect-lens filed that contradiction as a binding fact — *"One-third of the deliberation set sits on that contradiction."* Two more names (SLDE, BNS) sit in Financials, which reads "Declining — Avoid" and gates BLOCKED. Lynch put the concentration in its plainest form: *"five of fifteen names (LNG, EQT, COP, OXY, CVX) are driven by one commodity variable, plus VALE on ore and CEG on power. That is one bet wearing seven tickers, not seven ideas."* Steenbarger adds that 12 of the 15 sit in a same-sector pair or larger, and that livermore explicitly used COP as CVX's confirming second name — making at least that pair non-independent by the seat's own construction. Against the held book: WEAT sits in the strongest and most crowded trend on the board; BRZE sits in a DEPLOY basket carrying a bearish structural pattern shared by two related complexes; HNGE sits in a DEPLOY sector that is fading.

---

## 3. HELD BOOK REVIEW

*Source: the export's own `held_book`. AQE is the source of truth. Three positions.*

### WEAT — rank 17 · entry 27.86 · no GICS sector (gate CHECK)
- **Trend:** rs_spy_20d +16.4, LEADER, structure_shift ABOVE_STRUCTURE, sma_distance 13.53% over the ma50, price well above ma200 22.65. mp 89.0 STRONG and ACCELERATING, flow 88.2, structure 74.7, elder 7.0.
- **Against it:** day_vol 0.79 — participation below its own norm. Daily candle **SHOOTING_STAR (bearish)**, weekly **BEARISH_HARAMI**. Elder exhaustion check reads **CAUTION**: volume contracting on up bars, at structural resistance. No valid bracket (no structural support passes the three gates); ATR fallback stop 27.24.
- **QS:** SKIP, conviction 0 (vetoed — jumpy path + volume noise, exhaustion footprint). Not QS-eligible today.
- **Context:** *Helped by the macro read, and crowded.* Agriculture is the strongest trend in the dataset (100% member breadth, roc20 +15.60) and simultaneously the most crowded position in it (CTA ags bias +0.6578, speculators crowded long corn, soy and wheat). Nearest wheat CTA flip is 24.12% away — no mechanical trigger nearby. Beta_252d -0.131: this position is not moving with the index.

### BRZE — rank 44 · entry 32.94 · Technology (XLK), gate WATCH
- **Trend:** rs_spy_20d +26.23, LEADER, ABOVE_STRUCTURE, sma_distance 23.85% — the most extended thing in the book. Basket Enterprise_Software, grade DEPLOY, RRG LEADING/ENTERING; sector trend "Recovering From Weakness — Watch for Entry."
- **Against it:** day_vol 0.52 — the thinnest participation anywhere in the book or the candidate set. mp 79.0 but **FADING**. structure 56.6. Weekly candle BEARISH_HARAMI. Bracket is valid (stop 30.33) but rr_tp1 is only 0.8 — the first target pays less than one unit of risk.
- **QS:** NONE, conviction 2 (low). Not QS-eligible today.
- **Context:** *Pressured.* Its own basket carries a RISING_WEDGE BEARISH FORMING at fit 0.833, and Druckenmiller flags Cloud_Computing with the same pattern already TRIGGERED plus Payments carrying it — three linked complexes, which he calls a cluster rather than a coincidence. The DEPLOY grade is defensible; treating it as unqualified leadership is not.

### HNGE — rank 72 · entry 91.85 · Healthcare, gate PASS
- **Trend:** rs_spy_20d +14.29, IN-LINE, structure_shift RANGE, sma_distance 8.53%, price far above ma200 56.28. structure 76.8, elder 8.0. Weekly candle BULLISH_ENGULFING.
- **Against it:** flow 43.4 — weak. mp 65.0 **FADING**, RRG WEAKENING/ENTERING. day_vol 0.92. No valid bracket. structure_shift RANGE means nothing has broken in either direction.
- **QS:** NONE, conviction 2 (low). Not QS-eligible today.
- **Context:** *Pressured.* XLV is one of only two DEPLOY-grade sectors and it reads "Momentum Fading — Hold, Don't Add" with divergence -5.69. **Note for the record:** weis nominated HNGE in Round 1 at conviction 3 as an **add** to the existing position — a coiled hinge on 0.92x volume, with the seat's own R6 proxy warning on FADING/DECELERATING momentum. It did not qualify for deliberation (one seat, conviction 3, against a solo bar of 4), so the add was never voted on. It is listed in §8.

**Book-level:** the export flags a held-book earnings event on **2026-09-08** as the report most able to move it. The record does not say which position. There is no calendar layer behind that flag (FMP 404) and no seat takes a view on its outcome. **No read.**

---

## 4. REPEAT WATCH

*Pasted verbatim from `repeat_watch.json` (as_of 2026-09-03). The GAP rows are declared, not dropped: 14 (date, ticker) pairs have no verdict-ledger row.*

| Ticker | Date Appeared | % vs last COB | State |
|---|---|---|---|
| **CME** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CME** | 2026-08-25 | — (gap, see note) | NEAR-MISS |
| **CTVA** | 2026-09-02 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CTVA** | 2026-09-03 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **CVX** | 2026-08-17 | — (first appearance) | HOLD-FOR-CONDITIONS |
| **CVX** | 2026-08-18 | +1.34% | ADVANCE |
| **CVX** | 2026-09-02 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CVX** | 2026-09-03 | +4.47% | HOLD-FOR-CONDITIONS |
| **DE** | 2026-09-02 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DE** | 2026-09-03 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **EQT** | 2026-09-02 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EQT** | 2026-09-03 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **KO** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KO** | 2026-08-25 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **LNG** | 2026-09-02 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LNG** | 2026-09-03 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **MDLZ** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MDLZ** | 2026-08-25 | — (gap, see note) | ADVANCE |
| **OXY** | 2026-08-18 | — (first appearance) | ADVANCE |
| **OXY** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OXY** | 2026-09-03 | +3.17% | HOLD-FOR-CONDITIONS |
| **RELY** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RELY** | 2026-08-25 | — (gap, see note) | NEAR-MISS |
| **RELY** | 2026-09-03 | +0.86% | HOLD-FOR-CONDITIONS |
| **RVMD** | 2026-08-18 | — (first appearance) | PASS |
| **RVMD** | 2026-08-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SLDE** | 2026-09-02 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SLDE** | 2026-09-03 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **T** | 2026-08-18 | — (first appearance) | NEAR-MISS |
| **T** | 2026-08-25 | +4.09% | PASS |
| **T** | 2026-09-02 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WELL** | 2026-08-25 | — (first appearance) | ADVANCE |
| **WELL** | 2026-09-02 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WTRG** | 2026-08-25 | — (first appearance) | NEAR-MISS |
| **WTRG** | 2026-09-03 | +0.51% | HOLD-FOR-CONDITIONS |

**Reading it:** CVX is on its fourth appearance and has now been HOLD, ADVANCE, gap, HOLD — it is up 4.47% since last close-of-business and the committee has gone from advancing it to holding it. WTRG and RELY have both moved from NEAR-MISS to HOLD-FOR-CONDITIONS without ever advancing. OXY advanced on 2026-08-18 and comes back today at HOLD, +3.17%.

---

## 5. QS LIST

**The QS track is empty today. No name in the deliberation set is listed on QS — `on_qs` is false for all fifteen.** Seven names were not QS-eligible at all (volume did not beat its own 10-day average) and were scored against the eligible cohort as a read-across, never listed; the other eight were eligible but produced only 0 recipe hits against a minimum of 2. The full block is rendered per ticker below regardless, as required.

| Ticker | Signal | Conviction | Eligible | p | p_test | edge | analogues | Vetoes | Why not listed |
|---|---|---|---|---|---|---|---|---|---|
| VRNS | SKIP | 0 (vetoed) | yes | 0.520 | 0.562 | +0.077 | 3,943 | jumpy path + volume noise | only 0 recipe hits (needs >= 2) |
| LNG | SKIP | 0 (vetoed) | yes | 0.520 | 0.552 | +0.077 | 116,228 | jumpy path + volume noise | only 0 recipe hits (needs >= 2) |
| CEG | NONE | 2 (low) | yes | 0.520 | 0.571 | +0.077 | 44,370 | — | only 0 recipe hits (needs >= 2) |
| EQT | NONE | 2 (low) | no | 0.520 | 0.552 | +0.077 | 116,228 | — | not QS-eligible today (volume did not beat its own 10-day average) |
| WTRG | SKIP | 0 (vetoed) | yes | 0.520 | 0.571 | +0.077 | 44,370 | jumpy path + volume noise | only 0 recipe hits (needs >= 2) |
| DE | NONE | 2 (low) | yes | 0.520 | 0.552 | +0.077 | 116,228 | — | only 0 recipe hits (needs >= 2) |
| VALE | NONE | 2 (low) | no | 0.520 | 0.552 | +0.077 | 116,228 | — | not QS-eligible today (volume did not beat its own 10-day average) |
| RELY | SKIP | 0 (vetoed) | yes | 0.520 | 0.571 | +0.077 | 44,370 | exhaustion footprint | only 0 recipe hits (needs >= 2) |
| CTVA | NONE | 2 (low) | yes | 0.520 | 0.552 | +0.077 | 116,228 | — | only 0 recipe hits (needs >= 2) |
| SLDE | SKIP | 0 (vetoed) | yes | 0.520 | 0.571 | +0.077 | 44,370 | jumpy path + volume noise; exhaustion footprint | only 0 recipe hits (needs >= 2) |
| COP | NONE | 2 (low) | no | 0.520 | 0.552 | +0.077 | 116,228 | — | not QS-eligible today (volume did not beat its own 10-day average) |
| BNS | NONE | 2 (low) | no | 0.520 | 0.552 | +0.077 | 116,228 | — | not QS-eligible today (volume did not beat its own 10-day average) |
| OXY | NONE | 2 (low) | no | 0.520 | 0.552 | +0.077 | 116,228 | — | not QS-eligible today (volume did not beat its own 10-day average) |
| NFLX | SKIP | 0 (vetoed) | no | 0.520 | 0.552 | +0.077 | 116,228 | exhaustion footprint | not QS-eligible today (volume did not beat its own 10-day average) |
| CVX | NONE | 2 (low) | no | 0.520 | 0.552 | +0.077 | 116,228 | — | not QS-eligible today (volume did not beat its own 10-day average) |

All odds above refer to the same objective: **touch +2×ATR14 within 20 sessions**, against a market average of 0.443.

Held book QS: **WEAT** SKIP, conviction 0 (vetoed — "jumpy path + volume noise", "exhaustion footprint"), not QS-eligible today. **BRZE** NONE, conviction 2 (low), not QS-eligible today. **HNGE** NONE, conviction 2 (low), not QS-eligible today. No held name is on QS either.

---

## 6. PM LENS

*Pasted verbatim from `pm_lens.json`. Run on the FULL 133-row export, not the LAYER-0 44, with min_checks 5 — an independent lane that blocks nothing and feeds nothing upstream.*

| Ticker | Sector | Checks | Lenses strong | SC-mom | Elder | Structure | QS edge | Failed check | Committee saw it? |
|---|---|---|---|---|---|---|---|---|---|
| **PBR** | Energy | **5/6** | 3/6 | 73.4 | 10.0 | ABOVE_STRUCTURE | +10.7pp | lens | **NO — zero nominations** |
| **LNG** | Energy | **5/6** | 1/6 | 78.7 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | yes — deliberated |
| **PSX** | Energy | **5/6** | 2/6 | 75.6 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **VLO** | Energy | **5/6** | 2/6 | 75.5 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **DINO** | Energy | **5/6** | 2/6 | 74.7 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **MPC** | Energy | **5/6** | 2/6 | 73.8 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **COP** | Energy | **5/6** | 4/6 | 72.4 | 10.0 | BULLISH_BOS | +7.7pp | lens | yes — deliberated |
| **EQNR** | Energy | **5/6** | 4/6 | 70.1 | 10.0 | BULLISH_BOS | +7.7pp | lens | **NO — zero nominations** |
| **CVX** | Energy | **5/6** | 4/6 | 69.3 | 10.0 | BULLISH_BOS | +7.7pp | lens | yes — deliberated |
| **DUOL** | Technology | **5/6** | 1/6 | 67.5 | 10.0 | ABOVE_STRUCTURE | +7.7pp | lens | **NO — zero nominations** |
| **AAPL** | Technology | **5/6** | 4/6 | 58.8 | 10.0 | BULLISH_BOS | +7.7pp | lists | **NO — zero nominations** |

**Coverage gap — 8 PM LENS name(s) the committee never saw: PBR, PSX, VLO, DINO, MPC, EQNR, DUOL, AAPL.** These drew zero nominations, so they appear in no other section of this brief. Not a verdict, not an error — a name the PM's own checks flagged and the committee did not look at.

**The eight unseen names, one line each — no verdict attaches to any of them:**

- **PBR** — a name the committee never looked at. Energy, 5/6 checks, the highest QS edge in the lens table at +10.7pp.
- **PSX** — a name the committee never looked at. Energy, 5/6 checks, above structure.
- **VLO** — a name the committee never looked at. Energy, 5/6 checks, above structure.
- **DINO** — a name the committee never looked at. Energy, 5/6 checks, above structure.
- **MPC** — a name the committee never looked at. Energy, 5/6 checks, above structure.
- **EQNR** — a name the committee never looked at. Energy, 5/6 checks, bullish break of structure, 4 of 6 lenses strong.
- **DUOL** — a name the committee never looked at. Technology, 5/6 checks, above structure.
- **AAPL** — a name the committee never looked at. Technology, 5/6 checks, bullish break of structure; the only one of the eight whose failed check is *lists* rather than *lens*.

**Worth the PM's attention:** seven of the eight unseen names are Energy. The committee deliberated five Energy names and the PM's own lens flagged seven more it never saw — a direct consequence of the LAYER-0 intersection, since a name has to be on both lists to enter the room at all.

---

## 7. SHORTLIST — TICKER CARDS

**Crowding audit (printed once, from `purity_check.json`):** invariance **PASS**. *"crowding audit: top-5 by seats [VRNS(V), CEG(V), LNG(-), WTRG(-), EQT(V)] are 60% bracket-valid vs 33% across all 15 qualifiers (gap +27%). No sign that consensus is tracking bracket availability today."*

**How to read these cards.** Every name below is **HOLD-FOR-CONDITIONS except NFLX, which is a PASS**. A HOLD is a watch-list entry, not a soft buy. Nothing here is staged. The **Condition** line on each card is the specific, observable thing that would have to happen before the name becomes tradeable — drawn from the opposing seats' own written falsifiers, so the name that would clear the objection is the name that wrote it. The strongest opposing case is quoted verbatim and attributed; it is not summarised into agreement.

**Vote detail — the counts, which belong here and not at the top:**

| Ticker | Verdict | Conv | Support | Oppose | Abstain | Median support conv | Median oppose conv |
|---|---|---|---|---|---|---|---|
| VRNS | HOLD-FOR-CONDITIONS | 2 | 4 | 7 | 0 | 2.0 | 4.0 |
| LNG | HOLD-FOR-CONDITIONS | 3 | 5 | 5 | 1 | 3.0 | 3.0 |
| CEG | HOLD-FOR-CONDITIONS | 3 | 5 | 6 | 0 | 3.0 | 4.5 |
| EQT | HOLD-FOR-CONDITIONS | 2 | 4 | 7 | 0 | 2.0 | 4.0 |
| WTRG | HOLD-FOR-CONDITIONS | 2 | 4 | 2 | 5 | 2.0 | 3.5 |
| DE | HOLD-FOR-CONDITIONS | 3 | 4 | 5 | 2 | 3.5 | 3.0 |
| VALE | HOLD-FOR-CONDITIONS | 2 | 2 | 8 | 1 | 2.0 | 3.0 |
| RELY | HOLD-FOR-CONDITIONS | 2 | 3 | 5 | 3 | 2.0 | 3.0 |
| CTVA | HOLD-FOR-CONDITIONS | 2 | 2 | 7 | 2 | 2.5 | 3.0 |
| SLDE | HOLD-FOR-CONDITIONS | 2 | 2 | 7 | 2 | 2.5 | 3.0 |
| COP | HOLD-FOR-CONDITIONS | 2 | 3 | 6 | 2 | 2.0 | 3.0 |
| BNS | HOLD-FOR-CONDITIONS | 2 | 2 | 6 | 3 | 2.5 | 4.0 |
| OXY | HOLD-FOR-CONDITIONS | 2 | 2 | 6 | 3 | 2.0 | 2.5 |
| NFLX | **PASS** | 2 | 1 | 9 | 1 | 2.0 | 4.0 |
| CVX | HOLD-FOR-CONDITIONS | 3 | 3 | 6 | 2 | 3.0 | 3.0 |

---

### 1 · VRNS — HOLD-FOR-CONDITIONS (conviction 2) · rank 13 · Technology
Entry 46.76 · ma200 32.46 · sma_dist 7.54% · day_vol **4.45** (three times any other name) · rs_spy_20d 8.34 · **rs_leadership LAGGARD** · rs_downday **-1.38** · BULLISH_BOS · div NONE · gate WATCH · basket Cybersecurity TURNING
Bracket **valid** — stop 43.48 (ma50), risk 7.01% (widest valid-bracket risk in the set), rr_tp1 0.85.
QS: **SKIP**, conviction 0 (vetoed — jumpy path + volume noise), p 0.52, edge +7.7pp.
Fundamentals: pe -38.33, net margin -20.55%, int_cov -198.31, D/E 1.161, fcf yield 2.27%, Piotroski 4 (lowest in the pack), Altman 2.29.
**Context:** headwind. Technology reads "Recovering From Weakness — Watch for Entry"; the name itself is the only LAGGARD in the fifteen.
**Strongest opposing case — detect-lens, conviction 5, verbatim:** *"Fast end INVERTED: ma20 42.97 < ma50 43.48 while price 46.76 sits 7.54% above ma50 - a vertical snap off a dip, not a sustained advance... Bracket valid but hostile: stop ma50 43.48 = 7.01% risk (widest valid bracket here) and TP1 49.54 = 0.85R on unvalidated pivot vol 0.75 - the first overhead sits INSIDE one unit of risk."*
**Also on the record:** this was the most-nominated name in Round 1 (6 seats, sum 18) and it collapsed to 4 support against 7 oppose. Rogers called it the day's Darling of the Mob: *"six seats bought a one-bar volume event and none of them let the leadership reading outrank it."* Steenbarger: the six Round-1 reasons all trace to the same single bar — *"Six seats reading one bar through six lenses is one observation, not six."*
**CONDITION:** a close above **49.54 on day_vol ≥ 1.5** with **ma20 crossing back above ma50**. That repairs the inverted fast end and clears the 0.85R shelf in one move. Until then: watch only.

### 2 · LNG — HOLD-FOR-CONDITIONS (conviction 3) · rank 8 · Energy
Entry 295.86 · ma200 239.57 · sma_dist 12.22% · day_vol 1.65 · rs_spy_20d 16.73 · LEADER · rs_downday **+2.05** (one of only two positives in the set) · ABOVE_STRUCTURE · gate PASS
Bracket **invalid** — no structural support passes the three gates; only floor is a 1-ATR fallback at 288.02 (2.65% below).
QS: **SKIP**, conviction 0 (vetoed — jumpy path + volume noise), p 0.52, edge +7.7pp.
Fundamentals: pe 21.92, fcf yield **11.35%**, net margin 13.11%, **D/E 4.289** (equity ratio 18.9%), current 0.871, int_cov 9.45, Altman 2.24, Piotroski 7.
**Context:** headwind. The cleanest ascending stack in the set, in the sector its own macro grade calls "Momentum Fading — Hold, Don't Add." Also flagged by the PM Lens at 5/6 checks.
**Strongest opposing case — wyckoff, conviction 3, verbatim:** *"ABOVE_STRUCTURE at sma_distance_pct 12.22 is the middle of a move, not the edge of a range where one side's force is about to be proven or broken... day_vol 1.65 with flow 93.4 is genuine effort, but effort spent mid-move is not the geography my method pays for."*
**Lynch's separate flag:** most levered non-financial in the pack — *"81% debt in FUNDED bonds with long maturities is a financeable infrastructure structure; the same 81% in callable bank debt is what kills companies. I cannot see the kind, so I will not bless it."*
**CONDITION:** an orderly, **low-volume pullback into ma20 275.97 that holds**, with the coil lens turning strong. That converts the extension into a retest and gives the name a stop that is a chart level rather than an ATR fallback.

### 3 · CEG — HOLD-FOR-CONDITIONS (conviction 3) · rank 37 · Utilities
Entry 290.04 · **ma200 296.83 — price is BELOW it** · ma50 265.47 < ma100 274.75 < ma200 296.83 (descending slow stack) · sma_dist 9.25% · day_vol 1.13 · IN-LINE · BULLISH_BOS · **div BEARISH, 3 bearish** · gate WATCH · basket Infra_Power TURNING
Bracket **valid** — stop 276.84 (swing low), risk 4.55%, rr_tp1 1.51.
QS: **NONE**, conviction 2 (low), p 0.52, edge +7.7pp.
Fundamentals: pe 28.19, **peg 3.862 / fwd_peg 2.779**, p_fcf 337.07 = **fcf yield 0.30%**, Altman 1.61, Piotroski 5.
**Context:** headwind. Utilities reads "Recovering From Weakness — Watch for Entry"; the name is a bounce underneath a falling 200-day.
**Strongest opposing case — lynch, conviction 5, verbatim:** *"My firmest call: both category branches condemn it... fcf_yld 0.30% fails C13 outright - 337x free cash flow against a 28.19 P/E is Pig Iron, not Philip Morris (C16). Altman 1.61 distress band, Piotroski 5."* Detect-lens, also conviction 5, is verbatim: *"BULLISH_BOS here is a pivot break sitting underneath a falling 200-day."*
**Rogers' note, unanswered:** no Round-1 reason for CEG mentioned the 200-day at all; elder-lens confirmed on its ballot that ma200 is off its data menu.
**CONDITION:** **two consecutive closes above ma200 296.83 on day_vol > 1.3.** That converts the bounce into a reclaim and retires the trend-order objection. A separate fundamental condition, if the PM weights Lynch: operating cash flow exceeding CapEx for two consecutive quarters.

### 4 · EQT — HOLD-FOR-CONDITIONS (conviction 2) · rank 7 · Energy
Entry 55.77 · **ma200 56.19 — price is BELOW it** · ma50 52.51 < ma100 54.23 < ma200 (descending) · sma_dist 6.2% · day_vol 0.94 · LEADER · **structure_shift BEARISH_CHOCH — the only one in the set** · div BEARISH 2 · gate PASS
Bracket **valid** — stop 54.23 (ma100), risk 2.76% (tightest in the set), **rr_tp1 0.45**.
QS: **NONE**, conviction 2 (low), not QS-eligible today, p 0.52, edge +7.7pp.
Fundamentals: pe 12.26, fcf yield **10.80%**, net margin 30.68% (highest of the five energy names), D/E 0.224, current 0.673, Altman 2.41, Piotroski 7.
**Context:** headwind. Energy graded "Hold, Don't Add," and this is the one name in the set whose up-structure has already failed.
**Strongest opposing case — detect-lens, conviction 5, verbatim:** *"The only BEARISH_CHOCH in the set - the up-structure failed... Sharpest fact: TP1 56.47 (vol-validated 1.36) IS effectively the ma200 56.19, worth 0.45R against 2.76% risk. The name pays a full unit of risk to earn 0.45 reaching the average it already sits below."*
**Rogers' note:** all four Round-1 nominators wrote the objection into their own reasons and nominated anyway — *"everyone attends, nobody commits."*
**CONDITION:** a **close above 56.47 on day_vol ≥ 1.2 that then holds ma200 56.19 as support for two sessions.** Equivalently, structure_shift flipping from BEARISH_CHOCH to BULLISH_BOS on day_vol above 1.0 while 54.23 holds.

### 5 · WTRG — HOLD-FOR-CONDITIONS (conviction 2) · rank 11 · Utilities
Entry 41.55 · ma200 38.98 · **sma_dist 4.77% — the shallowest extension in the set** · day_vol 1.43 · LEADER · **structure_shift NULL — nothing has broken in either direction** · **div BEARISH, 4 bearish (joint-highest)** · gate WATCH
Bracket **invalid** — and for a different reason from the others: *"no structural resistance above price."* The target list is empty. No computable R:R.
QS: **SKIP**, conviction 0 (vetoed — jumpy path + volume noise), p 0.52, edge +7.7pp.
Fundamentals: **p_fcf -24.13 = fcf yield -4.14%** while paying a 3.34% dividend. D/E 1.214, int_cov 2.62 (thinnest of any operating company in the pack), Altman 0.99, fwd_peg 4.158, Piotroski 7.
**Context:** headwind. Utilities is a "watch for entry" grade, and this name is levered into the one macro pressure both seats agree on — rising rates.
**Strongest opposing case — lynch, conviction 4, verbatim:** *"A dividend funded by the balance sheet, not by the business. p_fcf -24.13 = fcf_yld -4.14%: it CONSUMES free cash while paying a 3.34% yield - a hard C13 failure, not a near miss... int_cov 2.62 is the thinnest of any operating company here, into live rate risk. Altman 0.99 is deep distress."*
**Note for the PM:** this is **the only name where support outnumbered opposition** (4 to 2, with 5 abstentions). It failed on depth, not on count — all four supporters filed at conviction 2, median 2.0 against a required 3. Rogers: *"Four seats agreed on a name where nothing has happened yet."*
**CONDITION:** **ma100 38.74 crossing above ma200 38.98 while price clears its range top on day_vol above 1.5** — the trend criterion repairs and a pivot actually prints, in place of a null structure_shift.

### 6 · DE — HOLD-FOR-CONDITIONS (conviction 3) · rank 10 · Industrials
Entry 698.37 · ma200 566.01 · sma_dist 13.43% · day_vol 1.63 · rs_spy_20d 14.71 · LEADER · ABOVE_STRUCTURE · div BEARISH 1 · gate WATCH · basket **Agri_Commodities DEPLOY** · srm gate **BLOCKED**
Bracket **invalid** — no structural support passes the three gates; 1-ATR fallback 677.77.
QS: **NONE**, conviction 2 (low), p 0.52, edge +7.7pp.
Fundamentals: pe 38.71, peg -6.513 (P/E expansion at trough earnings — the legitimate cyclical buy shape), fwd_peg 1.709, fcf yield 2.05%, D/E 2.293 (confounded by the captive finance arm — Lynch declares this, does not assert it), int_cov 3.12.
**Context:** helped by one thing, pressured by another. Its basket is the strongest trend on the board (Agri_Commodities, 100% breadth) and it is also the most crowded (CTA ags bias +0.6578). Industrials reads "Recovering From Weakness — Watch for Entry."
**Strongest opposing case — wyckoff, conviction 3, verbatim:** *"ABOVE_STRUCTURE at sma_distance_pct 13.43, the break already behind price, which is the middle of a move rather than the edge where force is proven or broken... day_vol 1.63 with flow 94.7 is real effort; effort in mid-move is not what my method pays for."*
**Lynch abstained** and said why: *"genuinely undecidable today"* without dealer inventory and two quarters of sales growth — one data item that would flip the name either way.
**CONDITION:** an **orderly low-volume reaction into 626.89 / 615.68 that holds**, with the coil lens turning strong — a legal dip into the rising 20-day rather than an entry at the top of a completed thrust.

### 7 · VALE — HOLD-FOR-CONDITIONS (conviction 2) · rank 59 · Materials
Entry 15.73 · ma200 15.14 · ma50 14.66 sits **below** both ma100 15.53 and ma200 15.14 · sma_dist 7.28% · day_vol 1.08 · LEADER · ABOVE_STRUCTURE · div BULLISH · gate PASS
Bracket **valid** — stop 15.14, risk 3.75%, rr_tp1 1.07.
QS: **NONE**, conviction 2 (low), not QS-eligible today, p 0.52, edge +7.7pp.
Fundamentals: pe 31.67, net margin 5.23%, **fwd_peg 16.206**, Altman 1.59, fcf yield 5.58%, div yield **6.95%**.
**Context:** headwind. Materials reads "Momentum Fading — Hold, Don't Add," and the weakest rank and momentum score in the set (sc_mom 68.0).
**Strongest opposing case — lynch, conviction 4, verbatim:** *"The 6.95% yield is the trap, not the thesis: a variable commodity payout, not Slow Grower income, and the payout ratio - C17's actual gate - is unserved... fwd_peg 16.206 says recovery is not coming - a C8 red flag by a wide margin. Altman 1.59 distress band."*
**Rogers' blind spot, declared:** *"VALE is an iron-ore business and I cannot see a single unit of iron-ore supply, inventory, production or price."*
**CONDITION:** a **close above 16.36 on day_vol ≥ 1.5, together with ma50 crossing back above ma200 15.14.** 16.36 is the first of four overhead levels, three of them volume-validated — the thickest validated ceiling in the set.

### 8 · RELY — HOLD-FOR-CONDITIONS (conviction 2) · rank 40 · Technology
Entry 26.82 · ma200 18.57 · sma_dist 10.47% · day_vol 1.45 · LEADER · **structure_shift RANGE — price is still inside the swing** · gate WATCH
Bracket **invalid** — no structural support passes the three gates; fallback 25.69.
QS: **SKIP**, conviction 0 (vetoed — exhaustion footprint), p 0.52, edge +7.7pp.
Fundamentals: **the cleanest balance sheet in the pack** — D/E 0.034 (equity ratio 96.7%), current 3.181, int_cov 17.83, Altman 9.71, fcf yield 7.72%, pe 18.46 on net margin 16.85%.
**Context:** headwind. Technology reads "Recovering From Weakness — Watch for Entry"; momentum on the name is FADING and DECELERATING.
**Strongest opposing case — detect-lens, conviction 4, verbatim:** *"the binding fact is overhead: R@27.15 sits 0.29 ATR above price with pivot vol_ratio 2.82, VOLUME VALIDATED - the heaviest-defended and closest overhead level in the whole set. Beneath it no structural support passes the gates."*
**The supporting case, for balance — lynch, conviction 4:** the pass rests on the balance sheet and cash generation, explicitly **not** on PEG — *"I explicitly DO NOT lean on peg_ttm 0.010 - that implies a growth rate near 1,800% and is an earnings-inflection artefact, not a bargain."*
**CONDITION:** a **close above 27.15 on day_vol ≥ 1.5 with momentum acceleration turning back to ACCELERATING.** That is the single defended level standing between this name and open air.

### 9 · CTVA — HOLD-FOR-CONDITIONS (conviction 2) · rank 2 · Materials
Entry 89.96 · ma200 77.14 · **ma20 80.27 is the LOWEST of the fast averages**, below ma100 81.29 and ma50 83.06 · sma_dist 8.31% (but 12.07% above the ma20) · day_vol 1.93 · LEADER · **structure_shift RANGE** · gate PASS · basket **Agri_Commodities DEPLOY**
Bracket **invalid** — no structural support passes the three gates; fallback 87.65.
QS: **NONE**, conviction 2 (low), p 0.52, edge +7.7pp.
Fundamentals: pe 59.58, net margin 5.66%, **fwd_peg 5.707**, fcf yield 1.05%. Balance sheet is fine — D/E 0.194, Altman 3.01, int_cov 17.38, Piotroski 7. Lynch: *"It fails on what you pay, not on what you own."*
**Context:** mixed. In the strongest basket on the board (Agri_Commodities DEPLOY) inside a sector graded "Momentum Fading — Hold, Don't Add."
**Strongest opposing case — wyckoff, conviction 3, verbatim:** *"structure_shift reads RANGE, so no confirmed pivot has been broken, and ma20 80.27 is the LOWEST of the fast averages, below both ma100 81.29 and ma50 83.06, with price 12.07% above it. That is a snapback off a dip, not a coiled boundary."*
**Rogers on the conviction:** highest average Round-1 conviction in the set (4.0 across two seats), and both seats made the same observation — price pressing a resistance level from ~1% below on 1.93x volume — *"High conviction resting on an event that has not occurred."*
**CONDITION:** **ma20 rising back above ma50 83.06 with price within 3.5% of it** — the 20-day repaired and the snapback converted into a base. A break of the 90.97 level would separately convert the RANGE into a confirmed pivot.

### 10 · SLDE — HOLD-FOR-CONDITIONS (conviction 2) · rank 1 · Financials
Entry 24.18 · ma200 18.59 · full ascending stack 24.18 > 22.38 > 21.17 > 19.61 > 18.59 · **sma_dist 14.19% — second-most extended in the set** · day_vol 2.85 · LEADER · BULLISH_BOS · **sector gate BLOCKED, sector trend "Declining — Avoid"** · srm **BLOCKED**
Bracket **invalid** — no structural support passes the three gates; fallback 23.48.
QS: **SKIP**, conviction 0 (vetoed — jumpy path + volume noise, exhaustion footprint), p 0.52, edge +7.7pp.
Fundamentals: pe 5.29, peg 0.043, net margin 40.02%, fcf yield 36.63%, Piotroski 8 — and **fwd_peg -3.584**.
**Context:** direct headwind. The top-ranked name in the universe sits in the one sector the system tells you to avoid.
**Strongest opposing case — wyckoff, conviction 3, verbatim:** *"BULLISH_BOS at sma_distance_pct 14.19 puts the break well behind price, the middle of a move rather than an edge. Step 2 cannot be walked at all: lens.coil reads '--', so my only objective entry-timing test is DARK, and lens.resistance is '--' too, so I have no overhead-supply read."* Detect-lens adds that this is *"the least instrumented name in the set"* — four of six lenses reading '--', with null mp_accel, div_state and div_bear.
**Lynch's reclassification, which is the whole call:** *"a 40% net margin in property insurance is a hard-market-plus-light-catastrophe artefact, i.e. peak-cycle earnings... I refuse to let the committee read 5.29x as cheap."*
**CONDITION:** a **measured pullback to within 3.5% of ma20 22.38 that holds, with the sector trend state lifting off "Declining."** Both halves are required — the location and the group.

### 11 · COP — HOLD-FOR-CONDITIONS (conviction 2) · rank 36 · Energy
Entry 137.20 · ma200 112.29 · **sma_dist 15.26% — the most extended name in the set** · **day_vol 0.86, below its own 20-day average, on a BULLISH_BOS** · rs_downday **+2.18** (best in the set) · LEADER · gate PASS
Bracket **invalid** — no structural support passes the three gates.
QS: **NONE**, conviction 2 (low), not QS-eligible today, p 0.52, edge +7.7pp.
Fundamentals: **the best composite in the pack** — Piotroski 9 (top of fifteen), Altman 3.52, fcf yield 11.72%, equity ratio 73.8%, int_cov 11.74, current 1.542, net margin 14.65%, pe 18.15.
**Context:** headwind. Energy graded "Hold, Don't Add." Also flagged by the PM Lens at 5/6 checks with 4 of 6 lenses strong.
**Strongest opposing case — oneil, conviction 4, verbatim:** *"a BULLISH_BOS printed on day_vol 0.86, below the name's own 20-day average. Under +40% is not a weaker buy, it is a rejection - nobody bought this break. Step 4 compounds it: sma_distance_pct 15.26 is the highest of all fifteen against a 9.25 median, so I am being asked to pay up for a move already made."*
**Note:** COP is also the name livermore used as CVX's confirming second name, which makes that pair non-independent by the seat's own construction (Steenbarger F5).
**CONDITION:** a **close above 137.37 on day_vol at or above 1.40** — the breakout bar the volume objection asks for. Wyckoff's variant: day_vol sustained above 1.5 on a hold above 137.37 within roughly five sessions.

### 12 · BNS — HOLD-FOR-CONDITIONS (conviction 2) · rank 69 (lowest to qualify) · Financials
Entry 93.31 · ma200 78.08 · sma_dist 5.46% · **day_vol 0.67 (joint-lowest)** · IN-LINE · rs_downday -0.07 · **structure_shift RANGE** · **div BEARISH, 4 bearish (joint-highest)** · **gate BLOCKED, sector "Declining — Avoid"** · sc_mom 67.1 (weakest in the set)
Bracket **invalid** — no structural support passes the three gates; fallback 91.43.
QS: **NONE**, conviction 2 (low), not QS-eligible today, p 0.52, edge +7.7pp.
Fundamentals: **read with care.** Lynch's explicit warning — Altman 0.02, current 0.044, int_cov 0.46 and D/E 3.056 are *"structurally normal-to-meaningless for a bank. These four fields must NOT be read as distress by any seat."* He abstained rather than opine.
**Context:** direct headwind. Lowest rank, lowest volume, weakest momentum score, in the sector graded avoid.
**Strongest opposing case — livermore, conviction 4, verbatim:** *"structure_shift RANGE - nothing has broken, so C5 limb (c) is simply absent. rank 69 is the lowest in the set and day_vol 0.67 is joint-lowest: C12 is explicit that I trade the leading, most active names in leading groups, and this is neither."*
**Rogers' catalyst finding, sharpest here:** *"What would force the market to reprice a rank-69 financial in a declining group inside 12 to 36 months? Nothing on this record answers that, and 'nothing overhead' is an absence, not a cause."*
**CONDITION:** a **close above 94.96 on day_vol ≥ 1.5 with the bearish divergence count falling below 2.** 94.96 is a volume-validated overhead level 0.88 ATR up.

### 13 · OXY — HOLD-FOR-CONDITIONS (conviction 2) · rank 53 · Energy
Entry 60.91 · ma200 52.22 · **ma50 55.75 sits below ma100 56.31 — the middle of the stack is still repairing** · sma_dist 9.25% · **day_vol 0.67 (joint-lowest)** · LEADER · rs_downday +1.91 · **structure_shift RANGE** · div BEARISH 1 · gate PASS · elder 8.0 (lowest in the set)
Bracket **invalid** — no structural support passes the three gates.
QS: **NONE**, conviction 2 (low), not QS-eligible today, p 0.52, edge +7.7pp.
Fundamentals: pe 9.16, peg 0.034, **fwd_peg -0.246**, net margin 28.79% (best of the energy cohort), fcf yield 8.77%, equity ratio 74.1%, Altman 2.06 (weakest of the five energy names), Piotroski 7. Lynch flags that the **preferred equity stack is invisible** in the served D/E.
**Context:** headwind. Energy graded "Hold, Don't Add," and this is the least-participated name in that block.
**Strongest opposing case — oneil, conviction 4, verbatim:** *"day_vol 0.67, joint-lowest in the set - there is no breakout to buy. Step 2 fails on its own terms: ma_50 55.75 sits BELOW ma_100 56.31, so the middle of the structure is still repairing and there is no completed base behind a prior +30% advance."*
**Repeat watch:** OXY advanced on 2026-08-18 and returns today at HOLD, +3.17% since last COB.
**CONDITION:** a **clearance of 61.24 on day_vol above 1.40, with ma50 crossing back over ma100** — participation plus a repaired middle stack, both required.

### 14 · NFLX — **PASS** (conviction 2) · rank 47 · Communication Services
Entry 82.73 · **ma200 87.19 — price is BELOW it** · ma50 75.08 < ma100 81.56 < ma200 87.19 (fully descending) · sma_dist 10.19% · day_vol 0.79 · BULLISH_BOS · gate PASS · basket Gaming_Streaming DEPLOY
Bracket **valid** — stop 78.66, risk 4.92%, **rr_tp1 2.15 (best in the set)**.
QS: **SKIP**, conviction 0 (vetoed — exhaustion footprint), not QS-eligible today, p 0.52, edge +7.7pp.
Fundamentals: net margin 28.22%, Altman 10.20, int_cov 16.94, equity ratio 67.8% — and **peg_ttm 0.753 against fwd_peg 4.281**, fcf yield 3.19%, 11.49x book.
**Context:** headwind. Communication Services reads "Momentum Fading — Hold, Don't Add," and the name is below its own falling 200-day.
**Verdict: PASS — the only one today.** One seat supported (thorp, conviction 2, on payoff arithmetic); nine opposed.
**Strongest opposing case — detect-lens, conviction 5, verbatim:** *"The fact I want on the record: ma200 87.19 sits BETWEEN the 82.73 entry and TP1 91.48 and appears NOWHERE in the target ladder, so the bracket prices a 2.15R first target straight across an unlisted, declining 5.4% obstacle."* Minervini, also conviction 5: *"Three fails with the slow stack fully descending - C2's stage 4 shape, and such purchases are prohibited however good the arithmetic looks."*
**Rogers' inverse test, on the record:** he examined whether the crowd had left something unpriced and concluded the reservation is real — *"Thorp's stated basis is pure worst-case arithmetic - a payoff-ratio argument, not a reason the price should rise."*
**Since this is a PASS, it carries no Condition line.** The name leaves today's process. Detect-lens's stated falsifier, for the record only: a close above ma200 87.19 held two sessions on day_vol ≥ 1.2.

### 15 · CVX — HOLD-FOR-CONDITIONS (conviction 3) · rank 50 · Energy
Entry 211.76 · ma200 180.58 · sma_dist 11.67% · **day_vol 0.96 on a claimed BULLISH_BOS** · **flow 50.0 — the lowest in the deliberation set** · LEADER · rs_downday +1.78 · div BEARISH 1 · gate PASS
Bracket **invalid** — no structural support passes the three gates.
QS: **NONE**, conviction 2 (low), not QS-eligible today, p 0.52, edge +7.7pp.
Fundamentals: sound on every solvency test served — D/E 0.195 (equity ratio 83.7%), Altman 3.76 (highest of the energy names), int_cov 23.13 (strongest coverage in the pack), current 1.358, fcf yield 6.41%, 3.33% yield. Against: Piotroski 6, net margin 9.87% (thinnest of the five), fwd_peg -1.128.
**Context:** headwind. Energy graded "Hold, Don't Add." Also flagged by the PM Lens at 5/6 checks with 4 of 6 lenses strong — and detect-lens notes the lens block and the flow engine disagree outright on this name.
**Strongest opposing case — oneil, conviction 4, verbatim:** *"a new high on lower volume means institutional buying has stopped. day_vol 0.96 on a claimed BULLISH_BOS is a C16 hard rejection, and flow 50.0 is the lowest of all fifteen. Its group confirmation is COP, which broke on day_vol 0.86 with mp_accel FLAT - the same doubt counted twice is not the group confirmation R9 requires."*
**Repeat watch:** CVX is on its fourth appearance, +4.47% since last COB, and has moved from ADVANCE (2026-08-18) to HOLD today.
**CONDITION:** a **follow-through close on day_vol at or above 1.40 with flow lifting off 50.0.** Wyckoff's variant is stricter: day_vol above 1.5 holding above 214.71.

---

## 8. NEAR MISSES

**The 20-name cap did not bind. `phase4.dropped` is empty — nobody was cut by the cap.** Fifteen of the 44 scanned names qualified for deliberation and all fifteen were deliberated. Rogers filed that abundance as its own challenge: *"the screen is finding more, not because more is there, but because the screen was narrowed to the part of the tape that still looks alive."*

The rows below are the **threshold misses** — names that drew exactly one nomination and fell short of the solo bar (a single seat needs conviction ≥ 4). One row each, with the nominating seat's own words.

| Ticker | Sector / trend | Seat | Conv | Rank | day_vol | Why it fell short | Context line |
|---|---|---|---|---|---|---|---|
| **ADM** | Consumer Staples — "Declining — Avoid" | minervini | 3 | 25 | 0.92 | *"Capped at 3 because day_vol 0.92 fails the breakout-volume half of the signature."* | Direct headwind — the sector gates BLOCKED and reads avoid. |
| **CNH** | Industrials — "Recovering From Weakness" | oneil | 3 | 6 | 2.60 | *"Held to 3: 25.2% above its 10-week line (most extended name in the set) and base_range 32.3% sits at the deep edge."* | Mixed — DE's own confirming Industrials name, and the most extended thing scanned. |
| **CVE** | Energy — "Momentum Fading — Hold, Don't Add" | weis | 3 | 56 | 0.67 | Inside bar with volume dried to 0.67x; hinge unresolved. | Headwind — a sixth Energy name into a sector graded hold-don't-add. |
| **HNGE** | Healthcare — "Momentum Fading — Hold, Don't Add" | weis | 3 | 72 | 0.92 | **This was an ADD to an existing held position.** *"R6 proxy warns mp FADING / DECELERATING - disclosed."* | Headwind — held name, fading sector, fading momentum. The add was never voted on. |
| **CVNA** | Consumer Discretionary — "Recovering From Weakness" | wyckoff | 2 | 75 | 0.84 | *"Stop ma100 70.31, risk 5.19%, rr 2.02 marginal."* | No read — the sector is a watch grade and no macro layer speaks to this name. |

---

## 9. ACTION PLAN — ADDRESSED TO THE PM

**1. There is nothing to approve today.** Zero advances means no entry, no bracket, no size, no stage. The three held positions stand. **Nothing is armed.**

**2. Treat the fourteen HOLD names as a watch list with fourteen named triggers.** Each card in §7 carries one Condition line — a specific, observable event, taken from the opposing seat's own written falsifier. If a Condition prints, that name comes back to the committee with the objection that stopped it already answered. If none print, none come back. **None of them is a soft buy in the meantime.**

**3. The filter question needs your ruling before the next run.** Rogers asked for a counterfactual and it was not produced: how many of the fifteen would still carry two or more seats if elder-lens's vote were struck from every line, and how many would have qualified from the unfiltered 133? This is a cheap number and it decides whether today's consensus was a search result or a filter artefact. Elder-lens itself accepted the charge without contest and reported the effect on its own ballot (7 nominations became 4 supports, none above 3, two withdrawn to oppose, not one conviction raised).

**4. Two seats' instruments were switched off by that same filter and should be re-armed or re-scoped.** Elder level (all 8–10) and sc_momentum (all 67.1–83.4) carried no discriminating information across the fifteen, and elder-lens's red-flag veto could not fire on anybody. A gate that admits only pre-approved names cannot then be used as evidence about them.

**5. Decide which macro seat governs entry timing.** Crown reads BROADENING with its own defining condition contradicted and match quality poor; Druckenmiller independently reads NARROWING. Every thesis in today's set is a broadening-tape trade. Rogers asked for this to be settled before a vote, not after. It is surfaced here unresolved, as the contract requires.

**6. Set the Energy bucket cap before entries, not after them.** Five of fifteen candidates sit in Energy, plus two in Utilities, in a sector graded "Momentum Fading — Hold, Don't Add" — and the PM Lens separately flagged seven Energy names the committee never saw (PBR, PSX, VLO, DINO, MPC, EQNR, and COP/CVX/LNG which it did). Lynch's line stands unanswered: *"That is one bet wearing seven tickers, not seven ideas."*

**7. Put the missing overlays on the record.** Today's entries — had there been any — would have carried **no event-risk overlay** (economic calendar 404) and **no dealer positioning read** (gamma unavailable). A VIX of 15.2 with no calendar is an unmeasured tape, not a calm one. There is one dated risk visible: a held-book earnings event on **2026-09-08**, position unnamed on the record.

**8. Engine asks, carried forward from the challenge seats:** a catalyst/event field on the deliberation record (Rogers' most transferable test can be asked today but never answered); a commodity and input-cost series (5 Energy + 2 Materials names with zero visibility into the physical material); the `held` column in the technical rows passed to the challenge seat; and Lynch's ruling request — does the Fast Grower PEG gate read trailing or forward? NFLX passes on 0.753 and trips on 4.281, and the gate is an automatic override, so the ambiguity has to be resolved before it is next applied.

**9. Process note worth keeping.** The read-proof gate caught 100% of a three-seat fabrication incident before anything was committed. Two full vote attempts were thrown away rather than accepted degraded. That cost time and cost nothing else. Every ballot behind this brief carries a verified packet MD5 and a verbatim proof-line.

---

DRAFT — PM approval required. Nothing is staged, nothing is armed.
