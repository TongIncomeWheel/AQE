---
name: voice-detect-lens
description: Voice skill — methodology card for detect-lens. Runs the voice-common engine in ISOLATION; outputs nomination.json per contracts/nomination.schema.json.
---

# VOICE: DETECT LENS — the 10th nominator (Decision D-5; non-human seat)
Role: nominates purely from AQE detect/lens machinery — no narrative, no framework, pure signal mechanics. The Ledger will prove or kill this seat.
Procedure: 1) rank universe by lens_positive (count of strong lenses; extension/structure excluded per feed spec) 2) overlay runner_setup / premove_setup conviction tags 3) top 10 by lens rank, tie-broken by premove/runner conviction 4) output reasons = the lens fields themselves, verbatim ("5/6 lenses strong; premove 4/4").
Constraints: reads only lens_ranking, lens block, signal_radar, lens_warnings. Never reads composites (that's the voices' territory — the seat must stay orthogonal). EVENT-DRIVEN exclusion applies.

**PROVENANCE — READ THIS FIRST. This card carries a HAND-TRANSCRIBED canon, not a locked one.**
The 24 principles below were extracted and page-verified from four PM-supplied books on
2026-08-08/09 through the full blind chain (chunk → blind extract → seal → synthesize).
That extraction was **destroyed three times by workspace resets** before it could reach a
committed lock, and the source PDFs were wiped with it. What survives — and what is written
below — is the verified 24-principle spine, preserved in the Project as
`claude/canon_detect_lens_24_principles_2026-08-10.md`.

**What that means, stated plainly and never to be softened:** there is no
`canon/detect-lens/canon.lock.yaml`, no sealed `extract.jsonl`, and no PM spotcheck behind
these citations. The page numbers were verified at extraction time but **cannot be
re-verified today** because the source files are gone. This card therefore builds only under
`AEGIS_ALLOW_HANDWRITTEN_CANON`, is stamped UNGROUNDED by the validator, and its `C-ids`
resolve against nothing in `contracts/canon_index.json`. **Deployed on PM ruling 2026-08-11
("I just want the voices deployed for use") as a TRANSITIONAL card.** Re-supply the four
PDFs and this seat goes through the identical pipeline that grounded steenbarger end-to-end.

**SCOPE EXPANSION, PM instruction 2026-08-08** ("these are a few more books to aid detect
lens"): the seat's original design — "this lens has no book, its canon IS the engine" — is
superseded for these sources. `aqe_dictionary` remains the mechanical spine (what fields
exist, how they compute); the books ground WHICH readings of those fields matter. The seat
stays MECHANICAL and no-narrative. Whole-chart, multi-week phase judgment is explicitly OUT
and remains the `wyckoff` voice's territory.

**Sources:** LTMS — Kratter, *Learn to Trade Momentum Stocks* (2018) · DTM2 — Ceponas, *Day Trading: Momentum, Level 2 and Reading the Tape* (2023) · SOTM — Clenow, *Stocks on the Move* (2015) · TATH — Weis, *Trades About to Happen* (2013). Antonacci (*Dual Momentum*) and Miller (*Momentum Trading*) are ROUTED to this seat by PM ruling 2026-08-10 but are **not yet extracted** — they appear nowhere below and must never be cited until they are.

**DEPLOYMENT SPLIT, PM ruling 2026-08-09** ("we can split ceponas to premarket and during
market then to make full use of him as i have more live data during market hours"): the
Ceponas tape cluster (C6-C11) is `NOT_APPLICABLE` during premarket nomination — no live tape
exists before the open, which is not a data gap. During the Intraday Review Pod
(`market_hours/SKILL.md` step 3c) the PM MAY supply a live Level 2/tape read against C6-C9's
vocabulary, declared `PM_OBSERVED`. Not supplied for a given check = `NOT_SERVED`. Verified
at grounding time: no automated feed exists and no MCP connector (Tiger, IBKR) exposes
equity Level 2 depth.

**WHAT I CANNOT SEE**

| Method element | Standing in Aegis |
|---|---|
| **Level 2 depth, print rate, live spread** (C6-C11) | **No automated feed.** Premarket: N/A. Market hours: **PM_OBSERVED** when the PM supplies it, else NOT_SERVED. Never inferred from price/volume bars. |
| **Exact ranking formula** — regression slope × R² (C12) | **NOT_SERVED.** `sc_momentum` is a DIFFERENT construct (flow/energy/structure/mp/elder composite, scoring.py v1.8.0). Never conflate. |
| **Single-day gap magnitude over a lookback** (C15) | **NOT_SERVED.** `day_vol`/`atr_14d` are dispersion, not a gap-event flag. |
| **Trend filters, ATR sizing, bracket discipline** (C1-C3, C5, C13-C15, C17-C18) | **SERVED.** `ma_50`/`ma_100`/`ma_200`, `atr_14d`, `bracket.*` are real. |
| **Weis bar tests** (C19-C24) | **POSSIBLE OVERLAP, UNCONFIRMED** with `structure`/`structure_shift`/`energy`/`flow`. An open mapping question, never an asserted match. |

**Every nomination or pod check carries a `declared` block or it does not ship:**
`canon_status: HAND-TRANSCRIBED, UNGROUNDED — no lock, no sealed extract, citations not re-verifiable (see PROVENANCE)` ·
`tape_read: NOT_APPLICABLE (premarket) | PM_OBSERVED (market hours, PM supplied) | NOT_SERVED (market hours, unsupplied) — never fabricated (C6-C9)` ·
`spread_read: same three-way declaration as tape_read (C10)` ·
`ranking_formula: sc_momentum used, NOT Clenow's regression-slope-x-R² (C12) — declare the distinction` ·
`gap_filter: NOT_SERVED (C15)` ·
`trend_filter: ma_50/ma_100/ma_200 (C1, C14, C15, SERVED)` ·
`sizing_shape: atr_14d + bracket.risk_pct (C5, C13, SERVED)` ·
`exit_philosophy: fixed stop/target (Kratter C2/C4) OR rank/regime-only, no stop (Clenow C16) — declare which is in force, never blend silently`.

**Advisory only, never a vote: `sc_momentum` (proxy for C12, never its equivalent), `structure`, `structure_shift`, `energy`, `flow` (possible C19-C24 overlap, unconfirmed).**

**PM-read discipline, not a forbidden field: tape_read is a real citable field when the PM has actually supplied it. Asserting a Level 2/tape read he did not supply is what is never mine — declare NOT_APPLICABLE or NOT_SERVED instead, every time (C6-C11).**

---

Checklist: 1) rank by lens_positive and overlay runner/premove tags (house design, unchanged) 2) apply the trend/sizing spine where fields exist (C1-C3, C5, C13-C15, C17-C18) 3) apply the Level 2/tape spine per the premarket/market-hours deployment split, never fabricated (C6-C11) 4) apply single-event mechanical tests, never a whole-chart phase verdict (C19-C24) 5) output reasons as the lens fields themselves, verbatim, plus the `declared` block including canon_status.

1. **Rank and tag, house design unchanged.** Rank by `lens_positive`, overlay `runner_setup`/`premove_setup` conviction, top 10 tie-broken by premove/runner conviction. Predates and is unaltered by this grounding.
2. **Trend/sizing spine where real fields exist.** `ma_50`/`ma_100`/`ma_200` for the dual-MA gate (C1) and Clenow's trend/regime filters (C14, C15, C17, C18); `atr_14d` + `bracket.risk_pct` for sizing (C5, C13). Declare `exit_philosophy` — Kratter's fixed stop/target or Clenow's rank-only, never blended.
3. **Level 2/tape spine per the deployment split.** Premarket: declare `NOT_APPLICABLE` and do not infer tape state from bars. Market hours: if the PM supplied a read, declare `PM_OBSERVED` and apply C6-C9's vocabulary to what he actually said; else `NOT_SERVED`.
4. **Single-event mechanical tests only.** C19-C24 each test ONE bar or a short FIXED sequence. If a check would require judging where price sits in a multi-week schematic, that is the `wyckoff` voice's job — do not attempt it.
5. **Output.** Lens fields verbatim, plus the full `declared` block. `canon_status` is mandatory on every nomination while this card remains hand-transcribed.

---

## Canon — 24 principles (HAND-TRANSCRIBED, UNGROUNDED, citations not re-verifiable)

### Kratter (LTMS) — entry/exit/sizing
- **C1** — Buy signal: 50-day MA closes above 200-day MA AND price trades above the 50-day MA. (p.27, 30)
- **C2** — Fixed 15% stop below entry — deliberately wide for momentum volatility. (p.31)
- **C3** — Trend-invalidation exit: 50-day MA closes below 200-day MA, checked once daily (lagging by design). (p.31, 37)
- **C4** — Default 300%/4x target via preset limit; alternate policy holds through to the C3 exit. (p.31)
- **C5** — Size = (account × % risked) / (entry − stop). (p.35)

### Ceponas (DTM2) — Level 2 / tape *(no automated feed; see deployment split)*
- **C6** — Buy trigger: ASK depleting while the BID one level below holds, confirmed by rising print speed. (p.60-70)
- **C7** — Exit trigger: a large supporting BID draining fast while T&S accelerates. (p.61-62)
- **C8** — Hidden buyer/seller: displayed size that will not shrink despite repeated fills is concealed size. Never probe with test orders. (p.63-64)
- **C9** — Book shape: dense BID + thin ASK favourable, inverse avoid; a sudden opposing wall triggers exit/avoidance. (p.28, 75, 96)
- **C10** — Spread gate: ideal $0.01, hard max $0.05 — wait for compression on a marginal breach. (p.96, 130)
- **C11** — Every chart trigger needs tape confirmation; halts tradeable only on 1st/2nd halt-up, scale out 50% on resumption. (p.38, 107-109)

### Clenow (SOTM) — systematic quant momentum
- **C12** — Ranking formula: 90-day annualised exponential regression slope × R². (p.70-71, 225)
- **C13** — ATR risk-parity sizing: shares = (account value × risk factor) / ATR. (p.86-88, 229)
- **C14** — Index regime gate: benchmark vs its own 200dma gates NEW buys only, never forces an exit. (p.64-65, 96)
- **C15** — Per-name filters: above own 100dma; disqualified on any single gap >15% in the trailing 90 sessions. (p.81-82, 104)
- **C16** — No price stop by design — exits via rank cutoff and 100dma only; index removal forces exit. (p.94-95, 107)
- **C17** — Rebalance cadence: recompute target size periodically, trade only past a ~5% tolerance band. (p.91, 96, 99)
- **C18** — Weekly re-check of every held name against entry criteria; redeploy freed cash only if C14 is still bullish. (p.95-96, 99)

### Weis (TATH) — single-bar / short-sequence tests
- **C19** — Effort-vs-result: volume against price-range progress on one bar or a short fixed pair; large effort/little result (or the reverse) is a divergence flag. (p.18, 61, 103)
- **C20** — Shortening of the Thrust: shrinking swing distances over 3+ successive swings flags fading momentum; past 4, suppress the counter-trend signal. (p.72, 106, 215)
- **C21** — Spring: support penetration with no downside follow-through; disqualify if too deep for recent volatility; confirm on a lower-volume secondary test. (p.60, 98-99)
- **C22** — Upthrust (mirror): close above resistance erased by a later close below the breakout/pre-breakout lows; size-bound ~10-15% new high; a narrow-range new extreme is suspect. (p.77, 124-128)
- **C23** — Climactic volume: extreme volume/range over a defined lookback. Key reversal bar: low undercuts prior low, close exceeds prior high (mirror for bearish). (p.59, 69, 73)
- **C24** — Bar toolkit: true range (gap-inclusive); narrow-range family (NR4/NR7/inside day/hinge); close-location value; percent-retracement (<50% strength, 50% stop reference). (p.18, 70, 85, 187)

## KNOWN CONFLICT — do not silently resolve
Kratter's fixed 15% stop and 300% target (C2, C4) and Clenow's no-stop, rank-only exit
discipline (C16) are **directly opposed philosophies**. Both are retained, tagged by source.
Every nomination must declare which is in force. Merging them into one house rule is a
defect, and the choice is a committee-charter decision, not this seat's.

---

**What this card does NOT let me claim:** that these citations are locked, spotchecked, or
currently verifiable — they are not, and `canon_status` says so on every nomination. That
Antonacci or Miller support anything — they are routed here but unextracted. That
`sc_momentum` equals Clenow's formula. That a gap field exists. That any C19-C24 bar test
extends into a multi-week phase verdict — that belongs to `wyckoff`.
