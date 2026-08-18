# PREMARKET COMMITTEE BRIEF — Tue 18 Aug 2026
**Data 11:28 SGT · brief 12:0x SGT · US open ~21:30 SGT · export FRESH (0d) · Crown DEGRADED: 14 Yahoo-sourced futures legs, FMP econ calendar 404, CFTC positioning 7d old (2026-08-11) · roster: 9 S4 nominators + Rogers/Steenbarger (challenge) + Lynch/Detect-lens (S5b+R2) — PM-selected "keep old roster" over v4.1's 10-nominator design, see §12**

## 1 · REGIME — three reads, side by side, unresolved

| Read | Says | Used by |
|---|---|---|
| **Crown (NOW) — canon-grounded correction, see §12** | Gate **passed** (`passed_the_gate=true`); breadth **narrowing** (confidence 0.65, day 1 of this regime), `position_in_12_month_range`=mid (no tired-wave signal today). `the_call.expression_family`=`BROADENING_CARRY`, partial match (4/5 conditions), size **1.00x** — but per Crown's own canon (recogniser R2 + principle C37), this is a **contested call, not a clean one**: scoring all five families against today's real fields, the family narrowing breadth actually points to (NARROWING_CONCENTRATED) only satisfies 1 of 3 of its own conditions today (trend funds aren't risk-on, gamma is positive not negative) — which is *why* the mechanical scorer preferred BROADENING_CARRY despite missing its own headline ingredient (broadening). The next-closest alternative, DIVERGENCE_PAIR_SHORT (2 of 3 — narrowing + divergence agree, only crowded trend funds is missing), is named explicitly rather than left buried in the artifact's own scoring. **QQQ gamma flip (734.66, spot 729.87) sits 0.66% away — inside Crown's own ~1% "knife-edge" threshold (recogniser R9): the character of the QQQ tape can change without price moving much.** SPY's flip (789.27, 2.15% away) is not knife-edge. | committee context |
| **Druckenmiller (NEXT)** | Guarded risk-on, not clean: VIX 15.2 calm, credit holding (HYG +0.16 5d, spread +1.03 vs TLT) — but TLT is falling harder than the dollar (real bond sell-off), gold bid, copper/gold ratio deteriorating (roc20 −5.31, a genuine deflation/growth-scare tilt under a calm VIX print). **Sizing tone: NORMAL**, concentrated Tech/Energy/Materials. `regime.hurst`/`regime.trend` both null — cannot deliver the momentum-vs-mean-reversion caveat this seat leads with; declared, not guessed | committee context |
| **QS regime** | `T3V1 / STAND_DOWN`, RED — "Calm melt-up, everything already extended. No edge in this market. Manage open positions only." avg_stock_hits_target 0.443 (below the market's own base rate) | **no seat — PM only** |

**Crown × Druck agreement** — *agrees on:* calm-VIX surface, credit not confirming stress, dispersion genuine (not one-way). *differs on:* Crown's own breadth reading (narrowing) is in real, scored contest with the BROADENING_CARRY family it mechanically selected — not a footnote, a named alternative family with its own score (see left column); Druckenmiller reads the copper/gold deflation tilt as a real cross-current Crown's mechanical commodity-leg scoring doesn't price the same way. **Conflict stated. Your call, not the committee's.**

**Data-integrity note (Crown, canon-grounded correction):** two blocks of the same Crown artifact disagree on UUP's roc5 sign (`scenario.what_is_missing` says −0.14%, `read_me_first.what_would_change_it` says +0.14%) — cross-checked against the independent intermarket packet, which confirms −0.14% (the `scenario` block is right, `read_me_first` is the stale one, resolved not just flagged). `oldest_source_days_behind` reads 1 at the top level but COT positioning is dated 2026-08-11, 7 days behind — the top-line staleness figure understates it, and this has now persisted across two consecutive sessions unfixed.

## 2 · SECTOR & THEMATIC ALIGNMENT (Crown × Druck over the daily report)

- **Aligned tailwind:** XLK, XLE both DEPLOY/PASS (Druck's srm read); XLB HOLD but the only explicit TAILWIND-flagged sector (0.52) — three sectors carry the deliberation set's real weight.
- **Aligned headwind:** XLU, XLP both **BLOCKED** (headwind −0.74 each); XLF HOLD with macro CAUTION (−0.5) — and the book's 40.63% XLF weight sits directly against that read (§3).
- **Contested:** Energy — XLE DEPLOY/PASS on Druck's sector table, and 6 of today's 20 deliberation names are Energy (OXY, DVN, CVX, XOM, EQNR + attempted 6th) — but Steenbarger's SF1 finding (below) flags this as the largest single-sector concentration in the set, converging on `structure_shift` as one shared field rather than four independent depths.
- **Financials, same tension:** XLF carries macro CAUTION from Druckenmiller, yet 7 of the 20 deliberation names are Financials (TPG, BBVA, IBKR, COLB + 3 more) — Steenbarger's SF1/SF2 findings (§12) name this explicitly as the set's second concentration risk, with two nominators (livermore, BBVA; TPG's nominator) citing sector-group confirmation as part of their own case — a process flag, not a name-quality one.
- **No thematic-basket cross-check available for the deliberation set** — Druckenmiller's basket read (Chip_Equipment, Semiconductors, Oil_Services, Nuclear_Energy, Critical_Minerals, Gold_Miners, Infra_Power, AI_Infrastructure, Space_eVTOL, Autonomous_Robotics) fed his own R1 macro-ticker nominations, which are **excluded from today's tally** (design note, §12) — declared, not silently dropped.

## 3 · HELD BOOK — before any new idea
**$143,013.25 · 12 positions · β(30d) 0.414 · XLK 55.89% + XLF 40.63% = 96.5% in two sectors — same concentration the sector read above flags as XLF-headwind**

*State/stop fields (`hl_state`, `held_sl`) are carried forward from the last full held-book grading (as of 2026‑08‑15/17) against today's live prices (as of 2026‑08‑18 11:28 SGT) — position count, tickers, exposure and prices are today's live PTJ export; the state grading itself is 3 sessions old and not regenerated in today's run. Declared gap, not fabricated freshness.*

| Flag | Names | $ / % of book |
|---|---|---|
| **Stops ABOVE market — breached** (recomputed vs today's live px) | **PTRN −27.2%, VRSK −4.4%, SPGI −2.5%, DDOG −0.4%** | ~$33,904 = 23.7% |
| No stop, largest position (17.8%) | **IBM** | $25,402 |
| At the line (<3% cushion) | EXEL +2.2% | — |
| EXIT-state (last grading) exposure | DDOG, V, SPGI, PTRN, EXEL, VRSK | **$46,051 = 32.2% of book** |
| **Cross-reference to today's deliberation set** | **NTAP** is held (15.99% wt, last-graded HOLD) *and* is today's #NTAP HOLD-FOR-CONDITIONS name below — the committee is independently re-underwriting a name already in the book | — |

## 4 · REPEAT WATCH — names qualifying in 2+ of the last 5 sessions (visibility only; not fed to the R2 committee vote — PM ruling 2026-08-18)

*Simplified per PM request 2026-08-18 ("I only need the ticker, date appeared, % vs last COB, state"). One row per appearance. 2026-08-17 prices/states below are reconstructed by hand from that day's published committee report — the automated verdict ledger only started logging 2026-08-18, so this cross-day view isn't mechanical yet (gap noted in §12). Window is currently 2 sessions deep and will build toward a true 5-session view as more sessions run.*

| Ticker | Date Appeared | % vs last COB | State |
|---|---|---|---|
| **CVX** | 2026-08-17 | — (first appearance) | HOLD-FOR-CONDITIONS |
| **CVX** | 2026-08-18 | **+1.34%** | **ADVANCE** |
| **COLB** | 2026-08-17 | — (first appearance) | NEAR-MISS (cut by cap, never argued) |
| **COLB** | 2026-08-18 | **−1.07%** | **ADVANCE** |
| **XOM** | 2026-08-17 | — (first appearance) | HOLD-FOR-CONDITIONS |
| **XOM** | 2026-08-18 | **+0.89%** | HOLD-FOR-CONDITIONS |
| **IBKR** | 2026-08-17 | — (first appearance) | HOLD-FOR-CONDITIONS |
| **IBKR** | 2026-08-18 | **+2.47%** | HOLD-FOR-CONDITIONS |

*State reads exactly as the committee produced it — ADVANCE, HOLD-FOR-CONDITIONS, or PASS (voted down). NEAR-MISS is a fifth, distinct state that shows up only in history: it means the name was nominated but cut by the deliberation-set cap before anyone voted on it — not the same as PASS, which means the committee argued it and voted it down.*

## 5 · QS LIST — full ticker-level regime-model shortlist (7/279 today)

*Added per PM request 2026-08-18 ("all tickers on QS list to be shown... it's not in daily CIO report"). QS is the third regime read at §1 (`T3V1/STAND_DOWN`, PM-only, never a committee seat) — this is that same model's own ticker-level output, rendered in full for the first time. All 7 names entered today's 279-ticker universe on the "qs" sourcing track and carry no technical coverage on any committee seat's menu (`NO_TECHNICAL_COVERAGE`, per the 2026-08-17 no-blank-data audit) — none were nominated, voted, or argued by the committee. PM-only awareness, exactly like the regime line above, never a committee input.*

| Ticker | Sector | QS Signal | Conviction | Price now | Target (+2×ATR) | Give-up (−2×ATR) | Why / veto |
|---|---|---|---|---|---|---|---|
| **GIS** (QS rank 1) | Consumer Staples | STRONG | 3 moderate | $37.98 | $40.19 (+5.8%) | $35.77 | "Strong position in range, momentum still quiet, not yet outrunning the market" |
| **WFC** (QS rank 2) | Financials | GOOD | 2 low | $87.54 | $91.20 (+4.2%) | $83.88 | "Weekly not overbought, MA stack aligned, range tightening, base maturing" |
| **PK** (QS rank 3) | Real Estate | GOOD | 2 low | $15.00 | $15.83 (+5.6%) | $14.17 | "Sitting near its highs, momentum still quiet, not yet outrunning the market" |
| **AMAT** (QS rank 4) | Technology | WATCH | 3 moderate | $535.31 | $606.31 (+13.3%) | $464.31 | "Weekly not overbought, MA stack aligned, range tightening" |
| **CCC** (QS rank 5) | Technology | WATCH | 2 low | $6.69 | $7.33 (+9.5%) | $6.05 | "Strong position in range, momentum still quiet, weekly not overbought" |
| **FITB** (unranked) | Financials | **SKIP — vetoed** | 0 | $57.60 | $59.77 (+3.8%) | $55.43 | Veto: "fading laggard" |
| **REYN** (unranked) | Consumer Staples | **SKIP — vetoed** | 0 | $25.91 | $27.15 (+4.8%) | $24.67 | Veto: "fading laggard" |

GIS/WFC/PK/AMAT/CCC carry a live QS signal (STRONG/GOOD/WATCH); FITB and REYN were vetoed by QS's own engine ("fading laggard") and are shown for completeness, not as ideas. QS's win-rate edge on this cohort (`odds.edge`) runs 7.7–11.7pp above its own 44.3% market base rate — real, but this is a regime-model read, not a committee-vetted name; no bracket, no falsifier, no bear case exists for any of these seven.

## 6 · ACTIONABLE IDEAS — 6 ADVANCE cleared consensus today (soft cap is 5; disclosed, not trimmed — see rationale below)

*QS regime for context on every card: `T3V1/STAND_DOWN`, RED, "no edge, manage open positions only" — PM-only, never a seat input, never a gate. QS's own ticker-level shortlist is at §5.*

### DVN — ADVANCE · conviction 4 · R2 split SUPPORT 7 / OPPOSE 1 (elder-lens) / ABSTAIN 3
| | |
|---|---|
| **Nominated (R1)** | minervini (5) · weis (3) · oneil (3) — the only name in the full 187-ticker universe carrying `squeeze_breakout_state=BREAKOUT_UP` with `squeeze_breakout_volume_confirmed=True` |
| **R2 support (attributed)** | livermore: "structure_shift=ABOVE_STRUCTURE, bracket valid, stop 45.93 (fib_618), risk_pct 3.45% — day_vol 1.46 the strongest above-average print in the set." lynch: "cleanest balance sheet of the 4 energy names (equity ratio ~78%), genuine net insider buying 2026Q2 (40 acquired vs 8 disposed)." |
| **Bear case (verbatim, elder-lens OPPOSE)** | "DVN did not clear my R1 checklist across the full 187-ticker screen — weis's own CORRECTION_REENTRY case describes 'elder_5d mostly 9-10' but the specific permission-event sequencing I require isn't independently confirmed on my menu." |
| **Counter-argument (minervini, conv 5, self-steelmanned)** | "squeeze_breakout_state is a single-day label — I cannot see the multi-week contraction sequence behind it; VCP contraction count is NOT_SERVED on my menu." |
| **Rogers flag** | CROWDING note: nomination_count=3 (weis, minervini, oneil), sumc=11 — "solidly inside the crowded tier, though not the top pole; genuine multi-framework convergence, not decoration." |
| **Falsifiers** | livermore/lynch: close through bracket stop 45.93; Steenbarger's SF1 sector-cluster caveat (Energy = 5/20 names, DVN is one) |
| **Entry frame (PM bracket, never a gate)** | stop 45.93 (fib_618, valid=True), risk_pct 3.45%, rr_tp2 2.67 |

### CVX — ADVANCE · conviction 3 · R2 split SUPPORT 5 / OPPOSE 0 / ABSTAIN 6
| | |
|---|---|
| **Nominated (R1)** | thorp (4, solo) — "stop_atr_dist 1.92 is the widest ATR-cushion I found in the file; worst-case ~1.52R against a stated 2.51R reward to TP2." |
| **R2 support** | detect-lens: "3/6 lenses strong, 0 warnings — a cleaner lens block than BBVA at the same tier." lynch: "equity ratio ~84%, FCF yield 6.28% — but payout ratio 84.4% is the one metric in my file that trips Lynch's own 80%+ payout caution." weis: "clean W23 stack (193.31>184.28>177.58), elder_5d 9-10 across the entire week." |
| **Bear case** | Zero OPPOSE this round — 6 of 11 seats ABSTAIN rather than vote, largely on missing menu fields (minervini, oneil, seow, raschke, wyckoff each cite specific absent fields for CVX, not a negative read). Rogers: "Solo by count and narrowness — the nomination rests entirely on bracket-cushion math, not a structure or leadership case." |
| **Falsifier** | thorp: "widened stop_atr_dist reading was PARTIAL, never PASS, on Step 1 — no signal_id/backtest field to confirm the level is anything but a good cushion." |
| **Rogers flag** | CROWDING, single-seat (thorp) — smallest attribution base of the 6 ADVANCE names |
| **Entry frame** | stop 194.35 (fib_618, valid=True), risk_pct 4.12%, rr_tp2 2.51 |

### OXY — ADVANCE · conviction 3 · R2 split SUPPORT 7 / OPPOSE 3 (elder-lens, oneil, thorp) / ABSTAIN 1
| | |
|---|---|
| **Nominated (R1)** | weis (3) · minervini (4) · raschke (3) · wyckoff (4) — top seat-count in today's set, sumc=14 |
| **R2 support** | lynch: "P/E 8.88x, FCF yield 9.05%, analyst consensus target $65.92 vs $59.04 spot (+11.7%)." wyckoff: "BULLISH_BOS confirmed pivot break — the old ceiling is being treated as the new floor." |
| **Bear case (oneil, OPPOSE)** | "structure_shift=BULLISH_BOS is real and passes base integrity, but day_vol=0.65 fails my R4 breakout-volume substitute hard — under +40% confirmed volume, C16 says the break isn't defended." |
| **Counter-argument (minervini, conv 4)** | "day_vol=0.65 at the BOS print is below-normal — Rogers' certainty challenge is right that four seats converged on a break not defended by heavy participation." |
| **Rogers flag (CROWDING, verbatim)** | "On the Contrarian Temp Check this is squarely a Darling of the Mob — the widest committee agreement in today's book, exactly the condition under which I hunt for" [reversal risk]. **Directly answered by wyckoff's own counter-argument above** — the committee conceded the volume gap rather than papering over it. |
| **Entry frame** | stop 56.72 (ma20, valid=True), risk_pct 3.93%, rr_tp2 3.63 |

### EQNR — ADVANCE · conviction 3 · R2 split SUPPORT 6 / OPPOSE 3 (oneil, raschke, wyckoff) / ABSTAIN 2
| | |
|---|---|
| **Nominated (R1)** | elder-lens (3) · minervini (4) — structure=91.6, one of the highest reads in the entire 20-name file |
| **R2 support** | lynch: "FCF yield 9.6%, ROE 21.6%; equity ratio ~57% below my 75% sound line but well above the 50% distress line — moderate, not weak." detect-lens: "4/6 lenses strong, 0 warnings." |
| **Bear case (oneil, OPPOSE)** | "Two independent disqualifiers: sma_distance_pct=14.39% breaches my 10% hard-rejection line, and bracket.valid=False fails outright — the position cannot be taken at any size, per my own card." |
| **Entry frame — no valid bracket today.** `bracket.valid=False`, `invalid_reason`: "no structural support passes the 3 gates (atr≥1.0, rr≥2.0, risk%≤regime ceiling)." Every SUPPORT seat (minervini, thorp, wyckoff) independently disclosed this — **name analysis stands; entry is the PM's own step, not the committee's.** |
| **Rogers flag** | "One of the highest structure reads in the entire set carried by only two seats — the committee's method diversity hasn't caught up to what the score already shows." |

### BBVA — ADVANCE · conviction 3 · R2 split SUPPORT 5 / OPPOSE 2 (oneil, wyckoff) / ABSTAIN 4
| | |
|---|---|
| **Nominated (R1)** | livermore (4) · seow (2) — "day_vol 1.45, the best fill-participation proxy in this financials group; atr_14d 0.50, my tightest translated danger-signal unit" |
| **R2 support** | lynch (conv 4): "best-behaved bank on the metrics that translate — P/E 12.87x, div yield 3.24% at 46.7% payout (well below the 80% line), ROE 19.3%." |
| **Bear case (oneil, OPPOSE)** | "sma_distance_pct=11.90% breaches my 10% hard-rejection extension line, and bracket.valid=False fails outright." |
| **Counter-argument (lynch, conv 4, self-steelmanned)** | "Steenbarger independently found BBVA's own nominator (livermore) explicitly cited 'financials-group-confirmed' as a stated reason — SF2, group-confirmation-as-evidence, not four independent depths." |
| **Entry frame — no valid bracket.** `atr_fallback_stop=28.30` is a reference level only, per PM ruling R1 — never a defended stop on any seat's card. |

### COLB — ADVANCE · conviction 3 · R2 split SUPPORT 6 / OPPOSE 4 (minervini, oneil, seow, thorp) / ABSTAIN 1
| | |
|---|---|
| **Nominated (R1)** | livermore (3) · raschke (4) · wyckoff (3) — tightest predetermined risk in the entire 20-name set, `bracket.risk_pct=1.98%` |
| **Bear case (thorp, OPPOSE)** | "My own R1 screen dropped COLB for 'R3 margin too thin, near-reject' — bracket.rr=2.08 sits right at my checklist floor with essentially no room once worst-case gap math applies." Steenbarger, independently: 7th member of a 7-name Financials cluster — the single most sector-concentrated name in the deliberation set. |
| **Counter-argument (raschke, conv 4, self-steelmanned)** | "COLB is the 7th member of an already-crowded 7-name Financials cluster (Steenbarger SF1) — 35% of the entire 20-name set." |
| **Entry frame** | stop 31.70 (ma20, valid=True), risk_pct 1.98%, rr_tp2 2.08 — tightest-risk name of the session, but the crowding flag above is real and named by two independent processes (thorp's own R1 rejection logic on a different name, Steenbarger's cluster count). |

*Why 6, not 5: DVN and CVX cleared with the cleanest oppose-adjusted margins (support−oppose of 6 and 5 respectively); OXY/EQNR/BBVA followed at margin 3–4; COLB is the softest of the six (margin 2, sits inside the session's most sector-concentrated cluster) and would be the first cut if a hard 5-cap were enforced. Flagged for your read, not pre-trimmed by Alfred.*

## 7 · HOLD-FOR-CONDITIONS (9 names) — condition line mandatory on each, synthesized from the seat's own R2 falsifier where filed

| Ticker | Conv | Split (S/O/A) | Condition |
|---|---|---|---|
| **TPG** | 3 | 2/6/3 | Condition: close through the ma200 structural stop (49.35) invalidates; needs two or more other XLF-cluster names to independently confirm their own BOS/ABOVE_STRUCTURE reads before the sector-crowding flag (SF1/SF2) clears. |
| **IBKR** | 3 | 3/4/4 | Condition: needs a close that holds above bracket.stop (90.41) through the next session, and mp_accel_state to avoid flipping DECELERATING — either failure moves this toward OPPOSE per raschke/wyckoff's own filed falsifiers. |
| **NTAP** | 3 | 3/5/3 | Condition: structure_shift must not flip to BEARISH_CHOCH and rs_leadership must not reverse to LAGGARD (minervini's filed line) — **also the held-book cross-reference in §3**; a repeat committee read on a name already in the book. |
| **SE** | 3 | 3/3/5 | Condition: needs ma_50 to close back above ma_200 (resolving the current stack ambiguity) — a close below ma_20 (112.24) voids the structural case outright (weis/thorp's filed lines). |
| **MS** | 2 | 3/7/1 | Condition: needs the next-bar elder read to hold above 6 and mp_state to move off FADING toward BUILDING/STRONG — currently the weakest-margin HOLD in the set (3 support vs 7 oppose). |
| **XOM** | 2 | 6/3/2 | Condition: needs mp_accel_state to reaccelerate and div_state to clear to NONE/BULLISH — thorp/detect-lens flag a close below bracket.stop (156.25) as the hard invalidation. Best-supported HOLD (6 support) — closest to promotion. |
| **SHAZ** | 2 | 3/4/4 | Condition: `ma_200` is a genuine data_gap (null on the record, independently flagged by both wyckoff and Steenbarger — the "good" form of convergence, shared observation of missing data, not shared narrative) — needs that field repaired before a full trend-context read is possible; short of that, a close through the ma50 stop (68.38) invalidates. |
| **AMBP** | 2 | 3/5/3 | Condition: needs day_vol to expand above 1.0 as the range resolves upward — Steenbarger flags this as one of seow's four templated MA-stack write-ups (SF3); a close below 4.96 invalidates immediately. |
| **ARMK** | 2 | 2/6/3 | Condition: needs a structural bracket to actually form (bracket.valid remains False with only atr_fallback_stop=60.47 as reference) — weakest-supported HOLD alongside MS (2 support vs 6 oppose). |

## 8 · PASSED (5 names) — declared, not silently dropped

**WPM** (3, 1S/6O/4A) — single-seat (minervini, conv 4), no cross-voice convergence; bracket.valid=False. **RVMD** (2, 0S/8O/3A) — unanimous-adjacent reject; independent finding across R2 seats of a bearish-divergence signal neither R1 nominator (single-seat) had visibility into at nomination time — worth a specific look before next session. **EVRG** (2, 0S/10O/1A) — the session's cleanest PASS, 10 of 11 seats opposed. **FIGR** (2, 1S/8O/3A) — Steenbarger's own finding: sole nominator's conviction 4 leans on one extreme day_vol print (2.52, next-highest in the set is 1.46) — a recency-bias-shaped single-field read, not a persistence pattern. **APO** (2, 1S/6O/4A).

## 9 · NEAR MISS (cut by the cap, not by quality)

**T** (rank 18, sc_mom 73.4, structure_shift BEARISH_CHOCH — real, not automatically bullish) · **FLR** (rank 145, sc_mom 52.0, structure_shift RANGE) · **CLX** (rank 79, sc_mom 67.8, structure_shift ABOVE_STRUCTURE) — all 3 carried 1 seat / conviction-sum 4, cut at the cap=20 boundary along with 14 other single-seat names. Same tiebreak mechanism as the Aug-17 committee-redesign ruling (seat_count → conviction_sum → SRM entry gate → thematic support → sc_momentum) — no gate applied.

## 10 · KEY LEVELS (nearest first)
**QQQ gamma flip 734.66 (spot 729.87, 0.66% away — inside Crown's ~1% knife-edge threshold, see §1)** · UST 2Y trend-fund buy trigger 103.64 (now 103.03, 0.6% away) · USD (DX) trend-fund sell trigger 98.84 (now 99.60, 0.8% away — the UUP data-integrity flag in §1 is resolved: the scenario block's −0.14%/−1.02% is the correct read) · single-stock vol elevated-band trigger 23.10 (current gap 22.46, and falling — gap_change_20d −9.56, moving away from the trigger) · SPY gamma flip 789.27 (spot 772.67, 2.15% away — not knife-edge) · RSP/SPY breadth ratio 0.2857 (12-month range 0.2722–0.2988 — closing toward the top of range would end the leadership trade and open the broad-tape trade)

## 11 · WHAT WOULD CHANGE THE READ
UST 2Y >103.64 → trend funds start buying, rates leg turns · DX <98.84 → trend funds start selling, dollar leg turns (subject to the internal data-consistency flag above) · single-stock vol gap closing above 23.10 while index stays calm → dispersion/crowding warning, the artifact's earliest tracked signal · RSP/SPY closing the gap to the index → ends the leadership/selection trade, opens a broad-tape trade · gold (GLD) reversing off its current RISING read → would remove one leg of Druckenmiller's guarded-risk-on read

## 12 · GAPS, RESIDUALS & PROCESS DISCLOSURES — declared, not hidden

- **Roster-version conflict, PM-resolved.** Today's S4/S5/S6 already ran the older 9-nominator + Rogers/Steenbarger + Lynch/Detect-lens roster before the newer `pma_design_v4.1` (10-nominator, S5=Rogers-only, S5L=Lynch-only) design doc was checked against it. PM chose "keep old roster" — this run's 11-seat R2 (9 S4 nominators + Lynch + Detect-lens) reflects that choice, not v4.1's structure.
- **Crown/Druckenmiller ticker-nomination deviation.** Per v4.1's framing, both are P0 macro/weather voices whose deliverable is "never a ticker." Druckenmiller's actual output this run included 10 basket-representative ticker nominations with convictions — a real design deviation. Alfred excluded these from the tally/rank/consensus chain (treated as macro/thematic context only, feeding §1–§2 above), consistent with the standing framing; the raw nominations exist in the run artifacts if you want them reviewed separately.
- **Sector concentration, independently found (Steenbarger SF1).** Energy = 5/20 and Financials = 7/20 of today's deliberation set — 60% of the shortlist in two sectors, one (Financials) carrying macro CAUTION from Druckenmiller. Both concentrations are named against specific tickers in §6/§7 above rather than asserted in the abstract.
- **Group-confirmation-as-evidence (Steenbarger SF2).** At least 3 nominators (BBVA/livermore, TPG's nominator, COLB indirectly) cited sector-cluster membership itself as part of their supporting case — flagged as a process concern, not a name-quality one; each instance is named on its card/condition line above.
- **Templated reasoning (Steenbarger SF3).** Four of seow's write-ups (AMBP, NTAP, ARMK, and a fourth) were flagged as near-identical MA-stack templates. Seow's own R2 filing directly answered this critique with name-specific differentiation on all four (see raw R2 record) — the self-correction mechanism the process is built to produce.
- **Bracket-invalidity rate (Steenbarger SF5).** EQNR, BBVA, TPG, NTAP, ARMK, WPM all carry `bracket.valid=False` — no PM entry can be sized off a committee-defined stop for 6 of the 20 names, disclosed explicitly on every affected card/condition line above rather than silently defaulting to `atr_fallback_stop`.
- **Attribution-file bug, self-caught.** The pre-cap deliberation-attribution file initially carried 3 tickers (T, FLR, CLX) that the cap had already dropped — caught by Steenbarger's own S5a challenge run, who declared the discrepancy rather than analyzing the extra names. Alfred fixed the underlying file (filtered to the true 20-name capped set) before building the Round 2 evidence pack; the already-issued S5a challenge documents (Rogers, Steenbarger) retain the original 23-entry reference set, a disclosed provenance quirk that produced no fabricated analysis on the 3 extra names.
- **Obligation register: 219/220 cells carried a filed falsifier** (1 gap: detect-lens/MS OPPOSE, no falsifier filed — declared here, not backfilled); **20/20 conviction≥4 SUPPORTs carried a self-authored counter-argument**; **220/220 cells carried a reply to the named Rogers/Steenbarger challenge.** Quorum 11/11 seats, coverage 20×11 = 220/220 cells complete.
- **Held-book state staleness (§3).** Live prices/exposure are today's PTJ export; `hl_state`/`held_sl` grading is 3 sessions old. Recommend re-running the held-book grading pass before next session if this gap matters to today's sizing decisions.
- **Crown canon-grounding fix, applied mid-run.** Crown's real methodology canon (39 principles, 11 recognisers, 4 refusals — `aegis/canon/crown/canon.lock.yaml`, PM-signed 2026-08-11) has been locked in the repo for a week, but the installed plugin never had a `voice-crown.md` agent card built from it — every other voice seat has one; Crown didn't. Result: Crown's first pass today read the raw artifact fields correctly but without applying his own interpretive layer (e.g., the QQQ gamma-flip knife-edge condition, recogniser R9, went unnamed). A `voice-crown.md` card was built from the real canon this session and Crown was re-run against it; §1/§10 above reflect the corrected, canon-grounded read. The regime characterization itself didn't change — the raw data was already accurate — but the interpretation is now sharper (the contested-family scoring in §1, the knife-edge flag on QQQ) and two additional gaps surfaced: (1) the pipeline's `packets/crown.json` file doesn't carry Crown's actual artifact schema at all — this run's corrector had to locate the real `aqe_crown_macro.json` directly, confirming the canon's own long-standing note that Crown ingestion was never fully wired; (2) the UUP data-integrity flag is now resolved rather than just flagged. **This card exists only in this session's workspace — it needs to be committed into the actual plugin source (not just patched locally) so it survives into the next session,** the same durable-fix gap noted in the Aug-14 committee-redesign ruling (R4) and evidently never closed for Crown specifically.
- **Phase-4 REPEAT flags — now a standing, visible section (§4), not buried here.** Moved out of disclosures per PM request 2026-08-18 ("I would have wanted to see... this could be useful for the committee as well for a second look") — see §4 for the full table. PM ruling: visibility only for now, not fed to the R2 committee vote as an input; a second option (surfacing the flag to the voting seats themselves) was considered and deferred. §4's cross-day view (2026-08-17 rows) was hand-reconstructed from that day's published brief, not pulled from the automated verdict ledger — the ledger only began logging 2026-08-18, so there's a real gap between "visible" and "mechanical" here; closing it means backfilling the ledger schema for prior sessions or accepting it only deepens from today forward.
- **QS ticker-level list — now a standing, visible section (§5), not previously rendered at all.** Per PM request 2026-08-18 ("all tickers on QS list to be shown... it's not in daily CIO report") — QS's per-ticker engine (signal, conviction, price/target/give-up, why, vetoes) has run every session, but only its aggregate regime read (§1) ever reached the brief; the ticker-level output was computed and discarded. §5 now renders the full list every run. These 7 names carry no technical coverage on any committee seat's menu, so there is no committee nomination, vote, bracket, or bear case for any of them — QS-only read, PM awareness, same standing as the regime line at §1.

---

**DRAFT — PM approval required. Nothing is staged, nothing is armed.**

*Render rules: sector-strength ordering is presentation, never a gate · every number resolves to a stage artifact · seats' words verbatim, never paraphrased by Alfred · conflicts surfaced, never resolved.*
