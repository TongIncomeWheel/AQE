# PMA — CIO BRIEF · 2026-10-21

**Data stamp:** AQE export 2026-10-21 08:51:38 SGT (TongIncomeWheel/AQE@main 15fc303, FRESH) · Tiger read-only 2026-10-21T06:53+00:00 · FMP fundamentals 54/54 · ledgers 2026-10-21 05:40 SGT

**Run declarations (every one from run_notes.md, plus the run manifest and this writer):**

- D1 Skill source: plugin bundle aegis-core v5.4 (R16–R21). AQE main's premarket-analysis copy is older (v5.3, no RULINGS.yaml); main is behind the plugin, not ahead.
- D2 Seat transport: compiled voice agents had no file tools in this harness (all 9 first spawns returned "not filed"). Every seat was re-spawned once as a general-purpose agent reading its OWN card + its OWN packet by path; R2 inlining replaced by path-read; figure audit (`validate --packet`) ran on every round-1 and round-2 form, with 0 fabricated figures.
- D3 Packets: built locally by `pma_pipeline.py packets` from the trimmed universe (held floor MP injected, R12); AQE pre-sliced packets not used.
- D4 Fundamentals: FMP batch pulled after RANK for the 54-name room only (54/54 served), not the full universe at GATHER (declared cut). Manifest: GATHER declared fundamentals_pack.json absent at that step.
- D5 One trend-following seat (named in Appendix A, item A.0) has a card marking it "NOT DECIDED / not wired" pending PM ruling; RUN.yaml seats it in NOMINATE and VOTE, so it ran and its ballots count. **PM to rule.**
- D6 Checkpoints: no git push after MACRO/NOMINATE/CHALLENGE/VOTE (the session has read-only git to TongIncomeWheel/AQE). The run sat on local disk until PUBLISH (via GitHub connector).
- D7 SCORECARD NOT RUN: closes_scorecard.json (FMP EOD for every ledger + AQE list name, 10 sessions) not pulled; scorecard_log.jsonl NOT advanced for the 2026-10-20 close. Manifest: scorecard.json/.md/.html and scorecard_log.jsonl absent.
- D8 REPEAT-WATCH degraded: 805 historical (date, ticker) rows have no verdict_ledger match on main; today's 54 verdicts are recorded (197 ledger rows dated today).
- D9 Broker: Tiger read-only 06:53Z. Zero working orders. `--previous` broker_stops not on main; USO vanish read from fills (STP 72 @ 156.43, 20 Oct 10:30 ET).
- D10 CHALLENGE packets built by the conductor from tally + menu-sliced rows (no tool exists for challenge packets); VOTE_PACKET 123 KB > 70 KB soft cap (54-name room).
- W1 Writer: conditions.md is filed verbatim in Appendix A (A.3), not under the cards. It names analysts, and the executive-form rule forbids that in the body. Under each card the same levels appear unattributed, read from conditions.json.
- W2 Writer: §4 shows today's repeat-watch rows verbatim; the full 960-row table (805 GAP rows) is pasted byte-for-byte in Appendix B.
- W3 Writer: the PM-lens table (§6, verbatim) labels 23 names "nominated, cut by cap". nominations.json holds none of them and R16 seats every nomination, so the label is wrong at source and not a cut. Pasted unedited.
- W4 Writer: brackets are render-only, with no intraday tape (levels only). dynCap is absent, so every bracket refuses to size. Every stop shown is AQE's 1-ATR fallback, not a structural level.
- W5 Purity: rank invariance PASS; crowding audit: top-5 by seats [CNC(-), CAH(-), LLY(-), PK(-), PRCH(-)] are 0% bracket-valid vs 17% across all 6 qualifiers (gap -17%). No sign that consensus is tracking bracket availability today.

> Verdicts: **9 ADVANCE · 26 HOLD-FOR-CONDITIONS · 19 PASS** (54 deliberated: 53 nominations + held MP). Nothing in this brief changes a verdict, rank, conviction or cap.

## §0 VERDICT TABLE

| Ticker | AQE rank | Door | Lane | Verdict | Consensus case (one line) | Condition / invalidation |
|---|---|---|---|---|---|---|
| **CNC** | 59 | Seats·3 · PM lens | PULLBACK | **ADVANCE** · c3 | Managed-care payer broke out to a new high through its 69.63 pivot, inside Healthcare, the only Deploy sector still marked add; the break came on light volume (0.8x), so the trade is the volume day or the pivot retest. | Confirms: hourly close above 70.97 (yesterday's intraday high) on 1.2x+ volume or dip under 69.63 (the pivot) then an hourly close back above it on 1.2x+ volume · dead below 68.53 (daily close) |
| **CAH** | 13 | Seats·2 · Elder+Lens · Strength · PM lens | MOMENTUM | **ADVANCE** · c3 | Healthcare distributor at a new high with all averages in order; it still gains ground on days the market falls (1.18). Price is full at P/E 35. | Confirms: hourly close above 257.55 (yesterday's intraday high) on 1.2x+ volume · dead below 246.46 (daily close) |
| **PK** | 25 | Seats·2 · AQE leader · PM lens | MOMENTUM | **ADVANCE** · c3 | Lodging REIT at a new high on 1.28x volume with the averages in order. It is one of five lodging names, so this is the same bet as PEB, not a second one. | Confirms: hourly close above 16.63 (yesterday's intraday high) on 1.4x+ volume · dead below 15.69 (daily close) |
| **PRCH** | 47 | Seats·2 · Elder+Lens · Lens | PULLBACK | **ADVANCE** · c3 | Fresh break to a new high on 1.42x volume out of a measured coil (lens 4/6). It lags on down days and its sector is graded Declining. | Confirms: hourly close above 18.41 (yesterday's intraday high) on 1.4x+ volume · dead below 17.57 (daily close) |
| **PEB** | 6 | Strength · Solo c4 · PM lens | MOMENTUM | **ADVANCE** · c3 | Lead lodging REIT and AQE's #6 name, at a new high on 1.36x volume. It is the most stretched ADVANCE at 11.9% above its 20-day. | Confirms: hourly close above 20.92 (yesterday's intraday high) on 1.4x+ volume · dead below 19.16 (daily close) |
| **MA** | 18 | Strength · Single seat | MOMENTUM | **ADVANCE** · c3 | Payments leader at a new high with the 20-, 50-, 100- and 200-day averages in order. There is no volume behind it yet (0.95x), so buy only the volume day. | Confirms: hourly close above 624.29 (yesterday's intraday high) on 1.4x+ volume · dead below 596.23 (daily close) |
| **HNGE** | 24 | Single seat | PULLBACK | **ADVANCE** · c3 | Healthcare fast grower (revenue +51%) at a new high on 1.99x volume, the heaviest demand of the nine. It sits 14.3% above its 20-day: buy a break, not a chase. | Confirms: hourly close above 108.00 (yesterday's intraday high) on 1.2x+ volume · dead below 99.32 (daily close) |
| **CNK** | 63 | Elder+Lens · AQE leader · PM lens · Single seat | MOMENTUM | **ADVANCE** · c3 | Cinema operator at a new high on 1.46x volume; it gains ground on days the market falls (1.43). This is the cleanest volume-confirmed break of the nine. | Confirms: hourly close above 40.35 (yesterday's intraday high) on 1.2x+ volume · dead below 38.47 (daily close) |
| **A** | 122 | Lens · Single seat | PULLBACK | **ADVANCE** · c3 | Life-science tools coiled 1% above its 20-day (0.38 ATR) just under its 174.80 high. It drew the broadest agreement of any ADVANCE: buy the break on 1.4x volume. | Confirms: hourly close above 174.80 (yesterday's intraday high) on 1.4x+ volume · dead below 168.90 (daily close) |
| **LLY** | 27 | Seats·2 · Elder+Lens · Strength · PM lens | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Mega-cap grower (revenue +45%, EPS +96%) at a new high on 1.29x volume, but already 5.65% past its pivot. Right name, late price. | Condition: hourly close above 1,311.75 (yesterday's intraday high) on 1.2x+ volume · dead below 1,196.33 (daily close) |
| **CME** | 16 | Seats·2 · Strength · AQE leader · PM lens | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Exchange broke out on 1.6x volume, but inside a repaired range. Its 50-day (275.00) is still under its 200-day (278.92) and price is 9.5% off the high. | Condition: pullback to 275.07 (the 20-day) with the Elder reading 7+ or hourly close above 299.92 (yesterday's intraday high) on 1.4x+ volume · dead below 287.01 (daily close) |
| **TRV** | 99 | Elder+Lens · PM lens · Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Cheap insurer (P/E 10.2, FCF yield ~13%) sitting 0.38% under its 52-week high on 1.34x volume. It needs the close through the high. | Condition: hourly close above 396.46 (yesterday's intraday high) on 1.2x+ volume · dead below 369.71 (daily close) |
| **CCEP** | 15 | Elder+Lens · Strength · AQE leader · Solo c4 · PM lens | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Staples bottler at a new high, but the most extended name in the room (4.43 ATR above its 20-day). | Condition: hourly close above 113.51 (yesterday's intraday high) on 1.2x+ volume · dead below 108.26 (daily close) |
| **DRH** | 19 | Strength · Solo c4 · PM lens | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Lodging REIT at a new high, but on 0.76x volume with a bearish divergence: a high made on falling volume. | Condition: hourly close above 13.88 (yesterday's intraday high) on 1.2x+ volume · dead below 12.74 (daily close) |
| **ADP** | 22 | Strength · Solo c4 | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Payroll compounder at a new high on 1.37x volume, but already 5.11% past its pivot. | Condition: hourly close above 294.27 (yesterday's intraday high) on 1.4x+ volume · dead below 275.76 (daily close) |
| **APLE** | 28 | Strength · AQE leader · Solo c4 · PM lens | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Lodging REIT at a new high on 1.4x volume. Its 50-day (16.12) is still under its 100-day (16.24). | Condition: hourly close above 17.86 (yesterday's intraday high) on 1.2x+ volume · dead below 16.52 (daily close) |
| **SHO** | 34 | Strength · AQE leader · Solo c4 · PM lens | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Lodging REIT at a new high on 1.6x volume, but 10.81% past its pivot, and its 50-day is under its 100-day. | Condition: hourly close above 12.47 (yesterday's intraday high) on 1.2x+ volume · dead below 11.05 (daily close) |
| **MET** | 69 | Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Insurer at a new high with the averages in order, on quiet volume (0.66x). | Condition: hourly close above 101.39 (yesterday's intraday high) on 1.2x+ volume · dead below 96.99 (daily close) |
| **ABBV** | 76 | Elder+Lens · Strength · PM lens · Single seat | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Pharma at a new high with the averages in order, 9.5% above its 20-day. It is part of the same Healthcare bet as CAH and LLY. | Condition: hourly close above 290.98 (yesterday's intraday high) on 1.2x+ volume · dead below 272.03 (daily close) |
| **AVPT** | 113 | Strength · Single seat | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Accelerating grower (revenue +27/22/17%) in a tight range at its high. It has not broken out yet. | Condition: pullback to 14.18 (the 20-day) with the Elder reading 7+ or hourly close above 15.43 (the pivot) on 1.4x+ volume · dead below 13.69 (daily close) |
| **ROKU** | 123 | Elder+Lens · AQE leader · Single seat | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Coiled near its highs (1.73% above its 20-day, coil strong, zero lens warnings): a range waiting to break. | Condition: hourly close above 157.57 (yesterday's intraday high) on 1.4x+ volume or pullback to 153.27 (the 20-day) with the Elder reading 7+ · dead below 153.27 (daily close) |
| **KMI** | 82 | Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Midstream name 2.16% under its high, holding its 20-day on an inside bar. It is unresolved. | Condition: hourly close above 33.68 (yesterday's intraday high) or daily close above 33.68 (yesterday's intraday high) on 1.4x+ volume · dead below 31.77 (daily close) |
| **CRM** | 190 | Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Software name contracting in a range above its 20- and 50-day at a fair price (PEG ~1.0, FCF yield ~7.6%). | Condition: hourly close above 262.33 (the pivot) on 1.4x+ volume · dead below 232.01 (daily close) |
| **BRZE** | 8 | Strength · Single seat | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Event-sized re-rating: 32.65x volume, +79 against SPY over 20 days, at a new high. | Condition: pullback to 27.90 (the 20-day) with the Elder reading 7+ or hourly close above 45.61 (yesterday's intraday high) on 1.2x+ volume · dead below 33.77 (daily close) |
| **AFL** | 165 | Elder+Lens · Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Insurer broke its structure upward above the 200-day, with a bullish pin bar. | Condition: dip under 118.09 (the pivot) then an hourly close back above it on 1.2x+ volume or daily close above 120.65 (yesterday's intraday high) · dead below 117.05 (daily close) |
| **EW** | 259 | Elder+Lens · Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | MedTech name coiled on its 50-day (88.29) with volume dried up (0.48x). | Condition: hourly close above 88.34 (yesterday's intraday high) on 1.4x+ volume or pullback to 86.38 (the 20-day) with the Elder reading 7+ · dead below 85.16 (daily close) |
| **KDP** | 9 | Elder+Lens · Strength · Single seat | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | AQE's top Staples name (rank 9) at a new high on 1.65x volume, but 7.75% past its pivot. | Condition: hourly close above 34.89 (yesterday's intraday high) on 1.2x+ volume · dead below 32.02 (daily close) |
| **CHD** | 21 | Elder+Lens · Strength · PM lens · Single seat | MOMENTUM | HOLD-FOR-CONDITIONS · c2 | Staples name at a new high (mp 94), but its averages are nearly flat: a young uptrend. | Condition: hourly close above 106.00 (yesterday's intraday high) on 1.2x+ volume · dead below 98.36 (daily close) |
| **KO** | 80 | Elder+Lens · Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Defensive stalwart 0.44% under its 52-week high, averages in order, on an inside bar. | Condition: hourly close above 93.96 (yesterday's intraday high) on 1.2x+ volume or daily close above 93.90 (the 52-week closing high) on 1.2x+ volume · dead below 88.73 (daily close) |
| **OXY** | 90 | Elder+Lens · Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Energy name ranging above averages in order; it gains ground on days the market falls (1.23). | Condition: hourly close above 63.63 (yesterday's intraday high) on 1.4x+ volume · dead below 59.54 (daily close) |
| **HOMB** | 159 | Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Cheap regional bank (P/E 11.9) coiling between its 20- and 50-day on 1.3x volume. | Condition: hourly close above 29.69 (yesterday's intraday high) on 1.4x+ volume · dead below 28.47 (daily close) |
| **ZION** | 223 | Elder+Lens · Lens · Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Cheap regional bank (P/E 7.9) squeezed and broke upward on 2.4x volume. | Condition: hourly close above 65.61 (yesterday's intraday high) on 1.4x+ volume or pullback to 62.88 (the 20-day) with the Elder reading 7+ · dead below 63.85 (daily close) |
| **ACA** | 224 | Elder+Lens · Lens · Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Tight base at a new high (structure break, 1.05% above its 20-day), lens 4/6 with no warnings. It has the widest agreement of any HOLD. | Condition: hourly close above 147.68 (yesterday's intraday high) on 1.4x+ volume or hourly close above 146.82 (the pivot) on 1.4x+ volume · dead below 146.59 (daily close) |
| **TTEK** | 234 | Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Coiled range above its 20-day. | Condition: pullback to 33.79 (the 20-day) with the Elder reading 7+ or hourly close above 35.22 (the 50-day) on 1.4x+ volume · dead below 33.79 (daily close) |
| **MRK** | 285 | Single seat | PULLBACK | HOLD-FOR-CONDITIONS · c2 | Uptrend intact (averages in order), coiled near its 20-day. | Condition: hourly close above 149.36 (yesterday's intraday high) on 1.4x+ volume or hourly close above 153.57 (the pivot) on 1.4x+ volume · dead below 145.77 (daily close) |
| **AEP** | 114 | Lens · Strength · Solo c4 | MOMENTUM | PASS · c3 | A structure break inside a downtrend: the averages are inverted and volume was 0.69x. That is a rally, not a trend. | Needs a 50-day back over its 200-day |
| **O** | 228 | Single seat | PULLBACK | PASS · c3 | Broken REIT: its structure turned down and it trades under its 200-day. The reversion case named no catalyst. | Needs a reclaim of its 200-day |
| **CCI** | 4 | Single seat | PULLBACK | PASS · c2 | Sharpest thrust in the room (+18.8% in 10 days, rank 4), running into its 200-day from below on a broken balance sheet. | Needs a close above its 200-day |
| **TDC** | 17 | Single seat | PULLBACK | PASS · c2 | Rebound in a Declining tech group, with the 50-day under both longer averages. | Needs the group off Declining |
| **LNT** | 170 | Single seat | PULLBACK | PASS · c3 | Utility bouncing inside a bearish structure under its 200-day. Reversion with no catalyst. | Needs a reclaim of its 200-day |
| **CMS** | 181 | Single seat | PULLBACK | PASS · c2 | Utility with inverted averages and 4 lens warnings, the weakest structure among the conviction-3 names. | Needs a reclaim of its 200-day |
| **KIM** | 197 | Single seat | PULLBACK | PASS · c2 | Below its 50- and 200-day: a bounce, not a base. | Needs a reclaim of its 50- and 200-day |
| **TRP** | 202 | Single seat | PULLBACK | PASS · c3 | Pipeline name with a bearish structure and its 50-day under its 200-day. Reversion with no catalyst. | Needs a 50-day back over its 200-day |
| **REG** | 204 | Single seat | PULLBACK | PASS · c3 | REIT with a bearish structure under its 50-day. Contraction inside a falling structure. | Needs a reclaim of its 50-day |
| **VTR** | 216 | Single seat | PULLBACK | PASS · c3 | REIT with a bearish structure, 13.97% off the high, on 0.59x volume. | Needs a reclaim of its 50-day |
| **CL** | 31 | Elder+Lens · Lens · Strength · Single seat | MOMENTUM | PASS · c3 | Structure break on 0.73x volume with flat averages; shrinking earnings at a premium. | Needs a volume break |
| **LYFT** | 40 | Single seat | PULLBACK | PASS · c2 | 29.8% under its high in a Declining group: a rebound, not a leader. | Needs the group off Declining |
| **DOCS** | 43 | Strength · PM lens · Single seat | MOMENTUM | PASS · c2 | Broken leader (−51% from the high) in a sharp repair, 23.5% above its 20-day. | Needs a base, not a thrust |
| **PBI** | 56 | Single seat | PULLBACK | PASS · c2 | Bearish structure; the volume came on a failed structure. | Needs structure to turn up |
| **MRSH** | 103 | Strength · AQE leader · Single seat | MOMENTUM | PASS · c2 | In a range on 0.75x volume, with an RS rank of 59. | Needs a break on volume |
| **TTAN** | 168 | Strength · Single seat | MOMENTUM | PASS · c2 | Failed up-structure in a Declining group; an unprofitable SaaS name whose growth is slowing. | Needs structure to turn up |
| **NDAQ** | 241 | Single seat | PULLBACK | PASS · c2 | In a range with mp 26, not at a high. | Needs a new high |
| **OKTA** | 306 | Single seat | PULLBACK | PASS · c2 | Elder reading has been red for four bars (0.0), a hard no-buy. The room's only pre-move tag is a radar read, not a trigger. | Elder red ban ends the bar red stops |
| **MP** | held | Held | PULLBACK | PASS · c2 | Held. The add was refused unanimously and every held review reads EXIT: stage 4, 22.86% under its 20-day, with no broker stop. | EXIT CASE — no broker stop (see §3) |

Door key: Seats·N = put up independently by N analysts · Solo c4 = one analyst at conviction 4 · Single seat = one analyst below 4 · other doors are machine flags carried for context (R17: doors seat nobody). AQE rank is out of 327 graded names.

## §0A EXECUTIVE CONSENSUS — WHY THESE ADVANCE

**The book in three lines.**

- **What they share:** 8 of 9 closed at a 52-week high (A sits 1.45% under its high), 8 of 9 have their 20-, 50-, 100- and 200-day averages in order, and the median name sits 8.2% above its 20-day. This is a breakout book, not a pullback book. 4 of 9 are Healthcare (CNC, CAH, HNGE, A), the only Deploy sector still marked add (Energy and Staples are Deploy but hold-don't-add).
- **Agreement:** strongest on A (the broadest agreement of the nine), CAH (unanimous in its lane) and CNK (no objection). It is thinnest on PRCH and HNGE, which carried over real objections. Only 3 of 9 (PRCH, HNGE, CNK) printed the 1.4x volume most buy lines ask for.
- **What kills the group thesis:** Healthcare losing its leadership, or SPY losing the 760 put wall while dealer gamma is negative. Either turns a breakout book into a list of failed breaks.

### A — ADVANCE · conviction 3

A coiled leader 1% above its 20-day (0.38 ATR, lens 4/6 with only money flow warning) carried the broadest agreement of any ADVANCE, from trend, pullback and contraction readers alike. The case against is valuation: earnings are flat (EPS +3%/+5%/+1%) at P/E 34, but price structure outvoted the earnings read. What has to stay true: the break above 174.80 comes on 1.4x volume.

### CNC — ADVANCE · conviction 3

A 94th-percentile RS leader broke through its 69.63 pivot to a new high inside Healthcare, the only Deploy sector still marked add, trading above every average, and no one argued against it. The strongest worry was participation: the break printed on 0.8x volume, and the fundamentals say turnaround (FY25 EPS −315%), not grower. It stays an ADVANCE only while it holds 68.53 and finds its volume day.

### CNK — ADVANCE · conviction 3

A new high on 1.46x volume, gaining ground on down days (1.43) with the averages in order, was the textbook break of the session, and the strength readers backed it without a single objection. Against it: a 13.8% 10-day run in a sector carrying macro headwind (−1.06), with no second name in the group. That lost because volume confirmed the break, which most of today's names lack.

### MA — ADVANCE · conviction 3

A payments leader at a new high with the 20-, 50-, 100- and 200-day averages stacked carried the momentum lane. The lens case against (2/6 strong, coil and money-flow warnings, 0.95x volume) was outweighed by trend quality. It is a buy only on a volume day above 624.29.

### PRCH — ADVANCE · conviction 3

A break to a new high on 1.42x volume out of a measured coil (lens 4/6, RS rank 99) carried the room, but over a real objection. The losing case was leadership: it lags on down days (−0.24), its sector is graded Declining, and equity is negative. The trend and coil readers outweighed it, so treat this as the smallest-conviction name of the nine.

### CAH — ADVANCE · conviction 3

A Healthcare leader at a new high, holding up on down days (1.18) with mp 87 and accelerating, was unanimous in the momentum lane. The case against was valuation: P/E 35 on +12% EPS (PEG ~2.9) and 9.53% above its 20-day, which in that lane is a weight, not a vote. It reports 11-05, inside the 11-session window.

### PK — ADVANCE · conviction 3

A lodging REIT at a new high on 1.28x volume, with the averages lined up 16.57 > 15.39 > 14.91 > 13.01, carried the momentum lane unopposed. Against it: five lodging names are one cyclical bet, and PK loses money (P/E −20) with debt above half of capital. The trend outweighed the fundamentals, but it is the same exposure as PEB, so own one, not both.

### PEB — ADVANCE · conviction 3

AQE's #6 name and the lodging theme's leader, at a new high on 1.36x volume with the averages in order, carried the momentum lane. The case against was no earnings (EPS −131%), no yield (0.19%) and an 11.88% stretch over its 20-day. If the PM wants the lodging theme, this is the one name that carries it.

### HNGE — ADVANCE · conviction 3

A Healthcare fast grower (revenue +51%) at a new high on 1.99x volume, with RS rank 99.5 and the averages in order, carried over a real objection. The losing argument was that the name sits in the pullback lane but has not pulled back: 14.27% over its 20-day on a range-expansion bar reads as climax risk. The demand was judged real, but the price is not a pullback price.

## §0B WHAT THESE WERE PICKED ON + MOMENTUM FIT

Momentum-lane verdicts were decided by the strength readers alone; pullback-lane verdicts were decided by the whole room. Five of the nine ADVANCE names are momentum-lane (CAH, PK, PEB, MA, CNK) and four are pullback-lane (CNC, PRCH, HNGE, A).

| Ticker | Lane | Momentum (mp, pace) | vs SPY 20d | Above 20-day | Volume today | From 52w high | Down-day RS | Fit for a momentum book |
|---|---|---|---|---|---|---|---|---|
| CNC | PULLBACK | 72, accelerating | +12.42 | 8.05% | 0.8x | 0.00% | +0.76 | Fresh break, needs volume |
| CAH | MOMENTUM | 87, accelerating | +16.55 | 9.53% | 1.0x | 0.00% | +1.18 | Leader, extended (3.91 ATR) |
| PK | MOMENTUM | 68, accelerating | +9.64 | 7.66% | 1.28x | 0.00% | +0.53 | Leader, lodging theme |
| PRCH | PULLBACK | 43, flat | +7.06 | 7.14% | 1.42x | 0.00% | -0.24 | Break with weak leadership |
| PEB | MOMENTUM | 84, accelerating | +13.98 | 11.88% | 1.36x | 0.00% | +0.84 | Theme leader, stretched |
| MA | MOMENTUM | 90, accelerating | +12.17 | 7.37% | 0.95x | 0.00% | +0.71 | Trend, no volume yet |
| HNGE | PULLBACK | 70, decelerating | +14.75 | 14.27% | 1.99x | 0.00% | +0.05 | Strong demand, wrong price |
| CNK | MOMENTUM | 70, accelerating | +12.46 | 9.82% | 1.46x | 0.00% | +1.43 | Cleanest fit |
| A | PULLBACK | 55, decelerating | +4.00 | 8.23% | 0.83x | -1.45% | +0.71 | Coiled, pre-break |

- **Crowding the room flagged:** five lodging REITs reached the floor (PK, PEB advance; DRH, APLE, SHO hold). That is one cyclical bet counted five times, so own PEB or PK, not both.
- **Healthcare is the biggest cluster:** CNC, CAH, HNGE and A advance, and LLY, ABBV and MRK hold. These names share one sector call, not seven independent ideas.
- **Detection tags are absent:** no room name carries a runner tag, OKTA alone carries a pre-move tag, and the best lens read is 4/6. Today's picks rest on trend and structure reads, not on detection signals.
- **QS:** every deliberated name prints 0.51–0.52 odds of touching +2 ATR in 20 sessions, against a 0.753 base for the average stock. QS sees no edge in this room; it is render-only and changed nothing.

## §1 MACRO

| Read | Number | What it means for the book | Source |
|---|---|---|---|
| Volatility | VIX 17.31 (45th pctl, 2y), contango; single-stock vs index vol gap 23.94 (83rd pctl), narrowing −0.93 over 20d | Index calm, stock-level stress leaving: permits new longs, but single names swing wide | Crown packet |
| Breadth | Broadening, 2 days old, confidence 0.65, mid-range; 5d/20d/60d +2.38/+2.01/−3.59%. Large caps beat small caps by 3.42 pts over 20d | A young turn inside a 60-day decline. Disputed (table below): no sizing up on breadth | Crown / Druckenmiller |
| Rates | Long bonds roc5 +2.25%, rising (yields falling) | A growth-scare bid, not an easing tailwind; it favours defensives and rate-sensitives | AQE macro_weather |
| Dollar | roc5 −0.41%, roc20 +1.47%, below its 20d SMA | Softening but not reflationary (copper and gold also falling). No read for the candidates | AQE intermarket |
| Credit | HY roc5 −0.34%, roc20 −2.34%, below 20d SMA; HY minus Treasury −2.59 | **The warning on the board.** Credit is softening under a calm VIX, which argues for light size on every new long | Druckenmiller |
| Commodities | Oil roc5 +4.91% · copper −1.73% · gold −1.05% · copper/gold roc5 −0.68 (roc20 +1.64) | Stagflation mix (input costs up, growth down). Headwind for MP's Materials group | AQE macro_weather |
| Positioning | Trend funds: 3 of 18 markets at an extreme (0.167), dial 1.00; CFTC (10-13, 8 days old) specs crowded long NQ and RTY | No crowding cut to size. Context only, cannot time anything | Crown |
| Dealer gamma | NEGATIVE: SPY 769.05 sits 0.77% under the 774.95 flip; put wall 760 (−1.18%), call wall 780 (+1.42%) | Knife-edge: moves get amplified. Under 760, breakouts fail more often; over 774.95, the tape calms (dealer convention assumed, not observed) | Crown |
| Index / regime | SPY 20d -0.56%, 63d +2.9%; regime GREEN; QS cell T2V1 "quiet, steady, unhurried climb", stance NORMAL | The index is flat over 20 days, so momentum longs are working against a non-trending index | AQE regime / QS |

| Seat | Family | Size | One-line call |
|---|---|---|---|
| Crown | BROADENING_CARRY (partial, 3 of 5 conditions); contested by DISPERSION_REGIME (0.83 share of conditions) | 1.00x | Broadening but young (2 days, mid-range) on a negative-gamma tape, with SPY 0.77% under its flip. No case to go above 1.00x. |
| Druckenmiller | Defensive rotation; risk call "leaning risk-off" | **light** | Bonds bid, credit soft, copper weak, defensive leadership: a defensive tilt, not a liquidation. Treat every momentum nomination as working against a non-trending index. |

- **Unresolved, left for the PM:** Crown reads breadth as broadening; Druckenmiller reads it as narrow (small caps falling, Crown's own small-cap flip at +1.49% not crossed). Crown has no credit read, and Druckenmiller weights soft high-yield credit as the leading warning.
- **What would change it:** SPY reclaiming 774.95 (dealers start damping moves, and the case for carry improves), or credit back above its 20d SMA (Druckenmiller moves to normal size). The opposite: SPY under 760 with credit weaker means cutting further. Events: claims 10-22, ISM 10-23, FOMC 10-28, Core PCE/GDP 10-29.

| Held name | Help / Headwind / No read | Why (one line, with the number) |
|---|---|---|
| MP | **Headwind** | Materials (XLB) carries macro headwind −0.94 and Critical Minerals is lagging (breadth 9.1%, 20d −10.15%). On a beta of 3.0 in a negative-gamma tape, the book loses $351 per 1% index gap |

- **Candidate set as a group:** the macro backs the Healthcare four (CNC, CAH, HNGE, A), since the sector is Deploy and leading-and-entering with a neutral macro score of 0.00. Lodging (PK, PEB) is a rate-sensitive bet that falling yields help and soft credit hurts. MA (Financials, caution −0.40), CNK (Discretionary, headwind −1.06) and PRCH (Technology, graded Avoid) sit on the wrong side of the tape. A **light** sizing call and a 9-name ADVANCE list disagree; size is the PM's.

## §2 SECTORS AND THEMES

| ETF | Sector | Grade | Trend state | 20d | 5d | RRG | Macro | Entry gate | Today's names (ADVANCE bold, HOLD plain) |
|---|---|---|---|---|---|---|---|---|---|
| XLV | Healthcare | DEPLOY | Momentum Building — Add | +5.84% | +5.99% | LEADING/ENTERING | NEUTRAL +0.00 | PASS | **CNC**, **CAH**, LLY, ABBV, **HNGE**, **A**, EW, MRK |
| XLE | Energy | DEPLOY | Momentum Fading — Hold, Don't Add | +10.02% | +1.15% | LEADING/DEEPENING | NEUTRAL -0.08 | PASS | KMI, OXY |
| XLP | Consumer Staples | DEPLOY | Momentum Fading — Hold, Don't Add | +6.07% | +4.23% | LEADING/ENTERING | TAILWIND +0.54 | PASS | CCEP, KDP, CHD, KO |
| XLF | Financials | HOLD | Momentum Fading — Hold, Don't Add | +1.68% | +1.64% | IMPROVING/ENTERING | CAUTION -0.40 | WATCH | CME, TRV, **MA**, MET, AFL, HOMB, ZION |
| XLY | Consumer Discretionary | HOLD | Momentum Fading — Hold, Don't Add | +2.82% | +2.79% | IMPROVING/EXITING | HEADWIND -1.06 | CAUTION | **CNK** |
| XLU | Utilities | HOLD | Momentum Fading — Hold, Don't Add | +3.33% | +0.02% | IMPROVING/EXITING | TAILWIND +0.54 | PASS | — |
| XLB | Materials | HOLD | Momentum Building — Add | +1.39% | +3.04% | IMPROVING/ENTERING | HEADWIND -0.94 | CAUTION | MP (held) |
| XLI | Industrials | TURNING | Recovering From Weakness — Watch for Entry | -2.04% | -1.11% | LAGGING/STABLE | HEADWIND -1.06 | BLOCKED | ADP, ACA, TTEK |
| XLC | Communication Services | TURNING | Recovering From Weakness — Watch for Entry | -2.94% | -1.86% | LAGGING/DEEPENING | HEADWIND -0.90 | BLOCKED | ROKU |
| XLRE | Real Estate | WATCH | Momentum Building — Add | -0.28% | +1.31% | IMPROVING/ENTERING | NEUTRAL +0.00 | WATCH | **PK**, **PEB**, DRH, APLE, SHO |
| XLK | Technology | AVOID | Declining — Avoid | -5.52% | -5.52% | WEAKENING/DEEPENING | HEADWIND -0.90 | BLOCKED | **PRCH**, AVPT, CRM, BRZE |

| Theme | Grade (capped) | Breadth | 20d | RRG | So what |
|---|---|---|---|---|---|
| Biotech | DEPLOY (DEPLOY) | 100.0% | +10.52% | LEADING/ENTERING | Leading, 100% breadth: confirms the Healthcare call |
| MedTech | HOLD (HOLD) | 88.9% | +1.87% | IMPROVING/ENTERING | Improving, but a bearish head-and-shoulders is forming: EW and A sit nearby |
| Insurance | HOLD (HOLD) | 90.0% | +4.38% | LEADING/ENTERING | Leading, 90% breadth: TRV, MET and AFL hold on stock-specific triggers |
| Payments | DEPLOY (AVOID) | 100.0% | +6.22% | IMPROVING/STABLE | Improving, 100% breadth, capped to Avoid by its parent: MA's group |
| Enterprise Software | DEPLOY (AVOID) | 76.2% | +11.34% | LEADING/DEEPENING | Leading, +11.34%, but capped by Technology Avoid: CRM's group |
| REITs | WATCH (WATCH) | 71.4% | -0.34% | IMPROVING/DEEPENING | Improving, 71.4% breadth: the lodging names' group, not yet a leader |
| Critical Minerals | TURNING (TURNING) | 9.1% | -10.15% | LAGGING/DEEPENING | Lagging, 9.1% breadth: MP's group, no relief from the theme |
| Semiconductors | TURNING (AVOID) | 6.7% | -9.89% | LAGGING/ENTERING | Lagging, 6.7% breadth: growth leadership is broken |
| Mag7 | AVOID (AVOID) | 57.1% | -0.75% | WEAKENING/ENTERING | Weakening; bearish rising wedge forming |

- **(a) What the table says about the macro read:** leadership is defensive and late. The only Deploy grades are Healthcare, Energy and Staples, and Energy and Staples are both marked hold-don't-add, while Technology is Avoid with its entry gate blocked. That matches Druckenmiller's rotation read more closely than Crown's broadening read.
- **(b) Where today's picks and the book sit, the uncomfortable version:** four of nine ADVANCE names sit in the only sector still marked add. The other five sit in Watch (Real Estate), Watch/Caution (Financials), Caution (Discretionary) or Blocked (Technology) sectors. The only held name sits in Materials, under a −0.94 headwind.

## §3 HELD BOOK

| Name | Qty | Entry | Mark | P&L | Stop written today | AQE state | One-line read |
|---|---|---|---|---|---|---|---|
| MP | 300 | 53.00 | 39.67 Tiger (AQE close 39.05) | ≈ −$3,999 (-25.2%) | **NONE: no working order at Tiger.** Mechanical floor 36.66 (AQE 1-ATR fallback, not a committee level) | Health EXIT (score 0.0); structure 11; momentum 0; -22.86% under its 20-day; under the 20/50/100/200-day | **EXIT CASE.** No analyst would add; every held review reads EXIT; a bullish divergence is the only counter-read |

- **MP against its floor:** the Tiger mark 39.67 sits 7.6% above the 36.66 floor (3.01/sh, ≈ $903 on 300 sh). At the floor, the open loss would be ≈ −$4,902. The floor is one ATR (2.39) under AQE's close and has no structural support beneath it.
- **Concentration:** one position, 100% Materials (XLB); 30d/60d beta 3.0; beta-adjusted exposure $35,145; ≈ $351 lost per 1% index gap (10% gap ≈ $3,514).
- **Change since the last run:** USO left the book. Its stop filled 20 Oct 10:30 ET (SELL STP 72 @ 156.43).
- **Scope:** the Tiger account also carries non-Aegis holdings (other pots). They are outside this committee's book and not read here.

## §4 REPEAT WATCH

| Ticker | Date Appeared | % vs last COB | State |
|---|---|---|---|
| **ABBV** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **ACGL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ACN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ADP** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **AEP** | 2026-10-21 | — (gap, see note) | PASS |
| **AFL** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **AIG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ALL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AMGN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AMRZ** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AMT** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ASAN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AVPT** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **AWK** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AZN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BALL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BBWI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BOX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BP** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BRO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BROS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BRZE** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **BSX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BUD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CAH** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **CART** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CCEP** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **CCI** | 2026-10-21 | — (gap, see note) | PASS |
| **CCL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CELH** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CHD** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **CL** | 2026-10-21 | — (gap, see note) | PASS |
| **CLX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CME** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **CMS** | 2026-10-21 | — (gap, see note) | PASS |
| **CNC** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **CNK** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **COP** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **COST** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CRM** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **CTAS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CVE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CVS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CVX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CXT** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DINO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DOCS** | 2026-10-21 | — (gap, see note) | PASS |
| **DRH** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **DRI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DVN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DXC** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **EBAY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ED** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ELS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **EOG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **EPD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ETSY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **FAST** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **FBP** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **FRSH** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **GDDY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **GILD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **GSK** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **GWRE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **HLN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **HNGE** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **IFF** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **INFY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ISRG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **JHX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KBR** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KDP** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **KIM** | 2026-10-21 | — (gap, see note) | PASS |
| **KMB** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KMI** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **KO** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **KR** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KSS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KVUE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KVYO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LEVI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LLY** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **LOW** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LTH** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LW** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LYFT** | 2026-10-21 | — (gap, see note) | PASS |
| **MA** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **MAS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **MDLZ** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **MET** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **MO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **MP** | 2026-10-21 | — (gap, see note) | PASS |
| **MPC** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **MRSH** | 2026-10-21 | — (gap, see note) | PASS |
| **MTCH** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **NAVN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **NDAQ** | 2026-10-21 | — (gap, see note) | PASS |
| **NKE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **NVS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **NWS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **O** | 2026-10-21 | — (gap, see note) | PASS |
| **OKTA** | 2026-10-21 | — (gap, see note) | PASS |
| **ORLY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **OTIS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **OUT** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **OXY** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **PBI** | 2026-10-21 | — (gap, see note) | PASS |
| **PBR** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PBR-A** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PEB** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **PFE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PFGC** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PINS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PK** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **PRCH** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **PSX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **RELX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **REYN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ROKU** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **ROST** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **RXO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SAP** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SCI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SHEL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SHO** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **SJM** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SPGI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SU** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **TD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **TDC** | 2026-10-21 | — (gap, see note) | PASS |
| **TEAM** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **TMO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **TTEK** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **UGI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **USFD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **V** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **VEEV** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **VERX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **VIA** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **VVV** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WAY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WCN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WDAY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WEC** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WELL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WM** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WMT** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WTRG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **XOM** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **YOU** | 2026-10-21 | — (gap, see note) | NEAR-MISS |

- **Upgrade/downgrade since last appearance:** no read. Every earlier (date, ticker) row is a ledger GAP (805 rows), so no name can be compared with its previous verdict. The full verbatim table is in Appendix B.
- **Committee memory (repeat marks):** all 9 ADVANCE names are FRESH, meaning this is the first time the committee has advanced each of them. Five earlier ADVANCE names have left the room (UBS, NFLX, RELY, ICE, T); the last recorded run is 2026-08-31.
- **Declared gap:** 13 of today's 54 deliberated names are missing from repeat_watch.json altogether (A, TRV, APLE, EW, HOMB, ZION, ACA, MRK, LNT, TRP, REG, VTR, TTAN); one of them, A, is an ADVANCE. Their verdicts are on the verdict ledger; the repeat-watch table simply does not carry them.

## §5 QS LIST

| Ticker | QS signal | Odds | Edge vs market | Note |
|---|---|---|---|---|
| — | none | — | — | 0 of 328 graded names are on the QS list today (QS status live) |

- **QS market read:** cell T2V1 / NORMAL, "Quiet, steady, unhurried climb", stance NORMAL. The average stock touches its +2 ATR target 0.753 of the time; every room name prints 0.51–0.52, an edge of −23 to −24 points. QS is render-only and gates nothing.

## §6 PM LENS

| Ticker | Sector | Checks | Lenses strong | SC-mom | Elder | Structure | QS edge | Failed check | Committee saw it? |
|---|---|---|---|---|---|---|---|---|---|
| **HLT** | Consumer Discretionary | **5/6** | 2/6 | 83.9 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **VEEV** | Healthcare | **5/6** | 1/6 | 83.3 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **PEB** | Real Estate | **5/6** | 0/6 | 81.0 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **CAH** | Healthcare | **5/6** | 3/6 | 79.4 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **CCEP** | Consumer Staples | **5/6** | 3/6 | 79.1 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **CME** | Financials | **5/6** | 2/6 | 78.9 | 10.0 | BULLISH_BOS | +-23.3pp | lens | yes — deliberated |
| **DRH** | Real Estate | **5/6** | 2/6 | 78.5 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **SN** | Consumer Discretionary | **5/6** | 3/6 | 78.5 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | **NO — zero nominations** |
| **CHD** | Consumer Staples | **5/6** | 3/6 | 77.9 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **PK** | Real Estate | **5/6** | 0/6 | 76.7 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **LLY** | Healthcare | **5/6** | 3/6 | 76.6 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **APLE** | Real Estate | **5/6** | 2/6 | 76.6 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **SHO** | Real Estate | **5/6** | 2/6 | 75.5 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **DOCS** | Healthcare | **5/6** | 2/6 | 75.2 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **ISRG** | Healthcare | **5/6** | 2/6 | 74.9 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **TAK** | Healthcare | **5/6** | 3/6 | 74.6 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | **NO — zero nominations** |
| **CNC** | Healthcare | **5/6** | 2/6 | 74.2 | 10.0 | BULLISH_BOS | +-23.3pp | lens | yes — deliberated |
| **SLDE** | Financials | **5/6** | 3/6 | 73.9 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | **NO — zero nominations** |
| **CNQ** | Energy | **5/6** | 3/6 | 73.8 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | **NO — zero nominations** |
| **CNK** | Consumer Discretionary | **5/6** | 3/6 | 73.8 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **AIG** | Financials | **5/6** | 2/6 | 73.7 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **ED** | Utilities | **5/6** | 1/6 | 72.9 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **MRNA** | Healthcare | **5/6** | 3/6 | 72.9 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | **NO — zero nominations** |
| **KMB** | Consumer Staples | **5/6** | 1/6 | 72.5 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **ACGL** | Financials | **5/6** | 1/6 | 72.3 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **ABBV** | Healthcare | **5/6** | 3/6 | 72.2 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **KVUE** | Consumer Staples | **5/6** | 2/6 | 70.8 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **TRV** | Financials | **5/6** | 3/6 | 70.3 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | yes — deliberated |
| **BALL** | Consumer Discretionary | **5/6** | 3/6 | 69.6 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **UGI** | Utilities | **5/6** | 1/6 | 69.4 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **RYAN** | Financials | **5/6** | 1/6 | 69.3 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **PFE** | Healthcare | **5/6** | 2/6 | 68.8 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **SYK** | Healthcare | **5/6** | 1/6 | 68.3 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **NVS** | Healthcare | **5/6** | 1/6 | 68.1 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **WEC** | Utilities | **5/6** | 3/6 | 67.9 | 10.0 | BULLISH_BOS | +-23.3pp | lens | nominated, cut by cap |
| **CVS** | Healthcare | **5/6** | 1/6 | 67.1 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **USFD** | Consumer Staples | **5/6** | 2/6 | 66.9 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **AMGN** | Healthcare | **5/6** | 3/6 | 66.6 | 10.0 | ABOVE_STRUCTURE | +-23.3pp | lens | nominated, cut by cap |
| **REYN** | Consumer Staples | **5/6** | 4/6 | 58.8 | 9.0 | BULLISH_BOS | +-23.3pp | lists | nominated, cut by cap |
| **PPG** | Materials | **5/6** | 4/6 | 56.2 | 9.0 | BULLISH_BOS | +-23.3pp | lists | **NO — zero nominations** |
| **HST** | Real Estate | **5/6** | 2/6 | 70.7 | 10.0 | ABOVE_STRUCTURE | +-24.3pp | lens | nominated, cut by cap |
| **BBWI** | Consumer Discretionary | **5/6** | 2/6 | 69.0 | 10.0 | ABOVE_STRUCTURE | +-24.3pp | lens | nominated, cut by cap |
| **UNH** | Healthcare | **5/6** | 3/6 | 68.5 | 10.0 | ABOVE_STRUCTURE | +-24.3pp | lens | **NO — zero nominations** |
| **MAS** | Consumer Discretionary | **5/6** | 1/6 | 66.2 | 10.0 | ABOVE_STRUCTURE | +-24.3pp | lens | nominated, cut by cap |
| **OUT** | Real Estate | **5/6** | 3/6 | 66.0 | 10.0 | BULLISH_BOS | +-24.3pp | lens | nominated, cut by cap |
| **HRL** | Consumer Staples | **5/6** | 4/6 | 47.6 | 10.0 | BULLISH_BOS | +-24.3pp | lists | **NO — zero nominations** |

**Coverage gap — 8 PM LENS name(s) the committee never saw: SN, TAK, SLDE, CNQ, MRNA, PPG, UNH, HRL.** These drew zero nominations, so they appear in no other section of this brief. Not a verdict, not an error — a name the PM's own checks flagged and the committee did not look at.

- **UNSEEN (passed the PM's own checks, zero nominations):** SN, TAK, SLDE, CNQ, MRNA, PPG, UNH, HRL. The 8 also appear in §8 as door-openers.

## §7 CARDS

ADVANCE first, then HOLD-FOR-CONDITIONS, in AQE floor order. Brackets are render-only, sized nowhere, and never a reason.

### CNC — ADVANCE · PULLBACK · conviction 3 · AQE rank 59

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 70.81 · ATR-fallback stop 68.61 (3.11%) · TP 71.21 / 74.41 / 78.47 · R:R to TP2 1.64 |
| Tape | 8.05% above 20-day · vs SPY 20d +12.42 · beats the market · mp 72 accelerating |
| Structure | broke out, averages tangled · 0.00% from 52w high · +1.69% from pivot |
| Effort | volume 0.8x · 2.51 ATR over 20-day · 10d run +9.60% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | turnaround, fundamentals neutral · P/E -6.8 · net margin -2.6% · rev +19% (latest FY) · P/FCF 3.9 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Managed-care payer broke out to a new high through its 69.63 pivot, inside Healthcare, the only Deploy sector still marked add; the break came on light volume (0.8x), so the trade is the volume day or the pivot retest.
- **Against:** Turnaround, not a grower: FY25 EPS −315% at a −2.6% net margin. Volume is behind the consensus.
- **Confirms:** hourly close above 70.97 (yesterday's intraday high) on 1.2x+ volume or dip under 69.63 (the pivot) then an hourly close back above it on 1.2x+ volume; confirmed by holds above today's VWAP · **dead** on a daily close below 68.53.
- **Levels (from the conditions file):** wait-for area 69.63; too late above 73.11; exit lines, highest first: 68.53 · 67.43 · 65.54 · 65.28 · 65.15.
- **Context:** Healthcare (XLV) DEPLOY, leading, macro neutral +0.00.

### CAH — ADVANCE · MOMENTUM · conviction 3 · AQE rank 13

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 257.55 · ATR-fallback stop 251.88 (2.2%) · TP 258.30 / 268.62 / 281.74 · R:R to TP2 1.95 |
| Tape | 9.53% above 20-day · vs SPY 20d +16.55 · beats the market · mp 87 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +3.31% from pivot |
| Effort | volume 1.0x · 3.91 ATR over 20-day · 10d run +10.33% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | stalwart, fundamentals contradicts · P/E 35.4 · net margin 0.7% · rev +14% (latest FY) · P/FCF 13.2 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2026-11-05 (11 sessions): inside the window, decide before the print |

- **For:** Healthcare distributor at a new high with all averages in order; it still gains ground on days the market falls (1.18). Price is full at P/E 35.
- **Against:** Thin-margin distributor at P/E 35 on +12% EPS (PEG ~2.9), 9.53% above its 20-day. The crowd is buying strength already priced.
- **Confirms:** hourly close above 257.55 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today · **dead** on a daily close below 246.46.
- **Levels (from the conditions file):** wait-for area 235.40; too late above 261.75; exit lines, highest first: 246.46 · 243.62 · 236.95 · 235.40 · 235.13 · 229.73.
- **Context:** Healthcare (XLV) DEPLOY, leading, macro neutral +0.00.

### PK — ADVANCE · MOMENTUM · conviction 3 · AQE rank 25

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 16.57 · ATR-fallback stop 16.13 (2.66%) · TP 16.63 / 17.11 / 17.71 · R:R to TP2 1.23 |
| Tape | 7.66% above 20-day · vs SPY 20d +9.64 · beats the market · mp 68 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +4.15% from pivot |
| Effort | volume 1.28x · 2.48 ATR over 20-day · 10d run +8.66% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (acceleration) |
| Fundamentals | cyclical, fundamentals contradicts · P/E -20.2 · net margin -6.4% · rev -2% (latest FY) · P/FCF 14.6 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Lodging REIT at a new high on 1.28x volume with the averages in order. It is one of five lodging names, so this is the same bet as PEB, not a second one.
- **Against:** Losing money (P/E −20), revenue −2%/−4%, debt above half of capital. Five lodging REITs make one cyclical bet.
- **Confirms:** hourly close above 16.63 (yesterday's intraday high) on 1.4x+ volume; confirmed by outperforms SPY today, volume at least 1.4x normal for the time of day · **dead** on a daily close below 15.69.
- **Levels (from the conditions file):** wait-for area 15.48; too late above 16.71; exit lines, highest first: 15.69 · 15.48 · 15.47 · 15.39 · 15.24 · 15.04.
- **Context:** Real Estate (XLRE) WATCH, improving, macro neutral +0.00.

### PRCH — ADVANCE · PULLBACK · conviction 3 · AQE rank 47

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 18.18 · ATR-fallback stop 17.35 (4.57%) · TP 18.37 / 19.20 / 20.21 · R:R to TP2 1.23 |
| Tape | 7.14% above 20-day · vs SPY 20d +7.06 · in line with the market · mp 43 flat |
| Structure | broke out, averages in order · 0.00% from 52w high · +1.11% from pivot |
| Effort | volume 1.42x · 1.25 ATR over 20-day · 10d run +5.88% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (acceleration) |
| Fundamentals | turnaround, fundamentals contradicts · P/E -148.3 · net margin -1.1% · rev +10% (latest FY) · P/FCF 24.7 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Fresh break to a new high on 1.42x volume out of a measured coil (lens 4/6). It lags on down days and its sector is graded Declining.
- **Against:** It does not lead the market (in line, −0.24 on down days), its sector is Declining, and equity is negative. Nothing rescues a failed leadership test.
- **Confirms:** hourly close above 18.41 (yesterday's intraday high) on 1.4x+ volume; confirmed by volume at least 1.4x normal for the time of day · **dead** on a daily close below 17.57.
- **Levels (from the conditions file):** wait-for area 17.14–17.98; too late above 18.88; exit lines, highest first: 17.98 · 17.57 · 16.97 · 16.31.
- **Context:** Technology (XLK) AVOID, weakening, macro headwind -0.90.

### PEB — ADVANCE · MOMENTUM · conviction 3 · AQE rank 6

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 20.71 · ATR-fallback stop 20.02 (3.33%) · TP 20.92 / 21.87 / 23.09 · R:R to TP2 1.68 |
| Tape | 11.88% above 20-day · vs SPY 20d +13.98 · beats the market · mp 84 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +6.21% from pivot |
| Effort | volume 1.36x · 2.35 ATR over 20-day · 10d run +9.11% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 |
| Fundamentals | cyclical, fundamentals contradicts · P/E -30.9 · net margin -3.1% · rev +2% (latest FY) · P/FCF 10.2 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Lead lodging REIT and AQE's #6 name, at a new high on 1.36x volume. It is the most stretched ADVANCE at 11.9% above its 20-day.
- **Against:** No earnings (EPS −131%) and no yield (0.19%), at 11.88% over its 20-day. The lodging group is stretched as a whole.
- **Confirms:** hourly close above 20.92 (yesterday's intraday high) on 1.4x+ volume; confirmed by outperforms SPY today, volume at least 1.4x normal for the time of day · **dead** on a daily close below 19.16.
- **Levels (from the conditions file):** wait-for area 19.09; too late above 21.45; exit lines, highest first: 19.16 · 19.09 · 19.05 · 18.81 · 18.40.
- **Context:** Real Estate (XLRE) WATCH, improving, macro neutral +0.00.

### MA — ADVANCE · MOMENTUM · conviction 3 · AQE rank 18

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 620.42 · ATR-fallback stop 610.41 (1.61%) · TP 624.29 / 645.75 / 673.04 · R:R to TP2 2.53 |
| Tape | 7.37% above 20-day · vs SPY 20d +12.17 · beats the market · mp 90 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +3.19% from pivot |
| Effort | volume 0.95x · 3.95 ATR over 20-day · 10d run +9.50% |
| Lists · Elder | longlist yes · Elder list no · Elder reading 7 |
| Fundamentals | stalwart, fundamentals neutral · P/E 34.1 · net margin 46.3% · rev +16% (latest FY) · P/FCF 34.0 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Payments leader at a new high with the 20-, 50-, 100- and 200-day averages in order. There is no volume behind it yet (0.95x), so buy only the volume day.
- **Against:** No volume expansion (0.95x), Financials is graded Hold (don't add), and the lens reads coil and money-flow warnings.
- **Confirms:** hourly close above 624.29 (yesterday's intraday high) on 1.4x+ volume; confirmed by outperforms SPY today, volume at least 1.4x normal for the time of day · **dead** on a daily close below 596.23.
- **Levels (from the conditions file):** too late above 631.29; exit lines, highest first: 596.23 · 591.22 · 580.90 · 577.83 · 570.79.
- **Context:** Financials (XLF) HOLD, improving, macro caution -0.40.

### HNGE — ADVANCE · PULLBACK · conviction 3 · AQE rank 24

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 107.51 · ATR-fallback stop 103.08 (4.12%) · TP 108.00 / 112.96 / 119.28 · R:R to TP2 1.23 |
| Tape | 14.27% above 20-day · vs SPY 20d +14.75 · in line with the market · mp 70 decelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +11.22% from pivot |
| Effort | volume 1.99x · 1.85 ATR over 20-day · 10d run +9.31% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | fast grower, fundamentals neutral · P/E 79.8 · net margin 15.1% · rev +51% (latest FY) · P/FCF 30.2 |
| QS | SKIP · odds 0.52 · edge -23.3 pts vs market |

- **For:** Healthcare fast grower (revenue +51%) at a new high on 1.99x volume, the heaviest demand of the nine. It sits 14.3% above its 20-day: buy a break, not a chase.
- **Against:** Pullback lane, but nothing has pulled back: 14.27% over its 20-day on a range-expansion bar reads as climax risk. It lags on down days (0.05).
- **Confirms:** hourly close above 108.00 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today, volume at least 1.2x normal for the time of day · **dead** on a daily close below 99.32.
- **Levels (from the conditions file):** wait-for area 99.32; too late above 112.43; exit lines, highest first: 99.32 · 94.89 · 94.44.
- **Context:** Healthcare (XLV) DEPLOY, leading, macro neutral +0.00.

### CNK — ADVANCE · MOMENTUM · conviction 3 · AQE rank 63

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 40.15 · ATR-fallback stop 38.95 (2.99%) · TP 40.35 / 41.78 / 43.59 · R:R to TP2 1.36 |
| Tape | 9.82% above 20-day · vs SPY 20d +12.46 · beats the market · mp 70 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +2.76% from pivot |
| Effort | volume 1.46x · 2.35 ATR over 20-day · 10d run +13.80% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (sustained) |
| Fundamentals | cyclical, fundamentals neutral · P/E 21.6 · net margin 6.4% · rev +2% (latest FY) · P/FCF 14.9 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Cinema operator at a new high on 1.46x volume; it gains ground on days the market falls (1.43). This is the cleanest volume-confirmed break of the nine.
- **Against:** 13.8% run in 10 days, a sector with macro headwind (−1.06), and no second name in its group.
- **Confirms:** hourly close above 40.35 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today, volume at least 1.2x normal for the time of day, volume at least 1.4x normal for the time of day · **dead** on a daily close below 38.47.
- **Levels (from the conditions file):** too late above 41.02; exit lines, highest first: 38.47 · 37.87 · 37.33 · 36.94 · 36.56.
- **Context:** Consumer Discretionary (XLY) HOLD, improving, macro headwind -1.06.

### A — ADVANCE · PULLBACK · conviction 3 · AQE rank 122

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 173.01 · ATR-fallback stop 168.32 (2.71%) · TP 177.05 / 181.32 / 186.21 · R:R to TP2 1.77 |
| Tape | 8.23% above 20-day · vs SPY 20d +4.00 · beats the market · mp 55 decelerating |
| Structure | in a range, averages in order · -1.45% from 52w high · -2.28% from pivot |
| Effort | volume 0.83x · 0.38 ATR over 20-day · 10d run +2.17% |
| Lists · Elder | longlist yes · Elder list no · Elder reading 7 (interrupted) |
| Fundamentals | stalwart, fundamentals contradicts · P/E 34.0 · net margin 19.5% · rev +7% (latest FY) · P/FCF 34.0 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2026-11-23 (23 sessions): inside the window, decide before the print |

- **For:** Life-science tools coiled 1% above its 20-day (0.38 ATR) just under its 174.80 high. It drew the broadest agreement of any ADVANCE: buy the break on 1.4x volume.
- **Against:** Flat earnings (EPS +3%/+5%/+1%) at P/E 34, so the PEG is above 10. It has not broken out yet (0.83x volume).
- **Confirms:** hourly close above 174.80 (yesterday's intraday high) on 1.4x+ volume; confirmed by volume at least 1.4x normal for the time of day · **dead** on a daily close below 168.90.
- **Levels (from the conditions file):** wait-for area 171.24; too late above 179.48; exit lines, highest first: 174.71 · 172.37 · 171.24 · 170.38 · 168.90 · 163.27 · 161.91 · 159.86 · 159.17.
- **Context:** Healthcare (XLV) DEPLOY, leading, macro neutral +0.00.

### LLY — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 27

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 1,283.66 · ATR-fallback stop 1,246.32 (2.91%) · TP 1,292.65 / 1,311.75 / 1,360.86 · R:R to TP2 0.75 |
| Tape | 8.56% above 20-day · vs SPY 20d +10.26 · beats the market · mp 86 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +5.65% from pivot |
| Effort | volume 1.29x · 2.56 ATR over 20-day · 10d run +10.90% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | fast grower, fundamentals supports · P/E 42.9 · net margin 33.5% · rev +45% (latest FY) · P/FCF 60.3 |
| QS | SKIP · odds 0.52 · edge -23.3 pts vs market |

- **For:** Mega-cap grower (revenue +45%, EPS +96%) at a new high on 1.29x volume, but already 5.65% past its pivot. Right name, late price.
- **Against:** Top of the chase band, P/FCF 60, and growth above 30% is hard to sustain. Everyone already owns it.
- **Condition:** hourly close above 1,311.75 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today · **dead** on a daily close below 1,196.33.
- **Levels (from the conditions file):** wait-for area 1,188.21; too late above 1,336.50; exit lines, highest first: 1,196.33 · 1,188.21 · 1,182.47 · 1,180.97 · 1,177.66 · 1,150.87.
- **Context:** Healthcare (XLV) DEPLOY, leading, macro neutral +0.00.

### CME — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 16

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 295.31 · ATR-fallback stop 286.49 (2.99%) · TP 308.01 / 315.46 / 324.93 · R:R to TP2 2.28 |
| Tape | 7.39% above 20-day · vs SPY 20d +11.08 · beats the market · mp 82 accelerating |
| Structure | broke out, averages mending · -9.54% from 52w high · +1.87% from pivot |
| Effort | volume 1.6x · 3.5 ATR over 20-day · 10d run +9.30% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (sustained) |
| Fundamentals | stalwart, fundamentals neutral · P/E 24.9 · net margin 63.1% · rev +6% (latest FY) · P/FCF 25.2 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Exchange broke out on 1.6x volume, but inside a repaired range. Its 50-day (275.00) is still under its 200-day (278.92) and price is 9.5% off the high.
- **Against:** Not an established uptrend: RS rank 52.6 is under the 70 floor, and Financials is graded Hold (don't add).
- **Condition:** pullback to 275.07 (the 20-day) with the Elder reading 7+ or hourly close above 299.92 (yesterday's intraday high) on 1.4x+ volume · **dead** on a daily close below 287.01.
- **Levels (from the conditions file):** wait-for area 275.07; too late above 304.39; exit lines, highest first: 287.01 · 284.12 · 271.69 · 269.29.
- **Context:** Financials (XLF) HOLD, improving, macro caution -0.40.

### TRV — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 99

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 395.73 · ATR-fallback stop 387.78 (2.01%) · TP 398.70 / 418.64 / 444.01 · R:R to TP2 2.88 |
| Tape | 7.04% above 20-day · vs SPY 20d +9.87 · beats the market · mp 68 accelerating |
| Structure | already trending, averages tangled · -0.38% from 52w high · +3.06% from pivot |
| Effort | volume 1.34x · 3.31 ATR over 20-day · 10d run +9.73% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | stalwart, fundamentals supports · P/E 10.2 · net margin 17.0% · rev +5% (latest FY) · P/FCF 7.7 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Cheap insurer (P/E 10.2, FCF yield ~13%) sitting 0.38% under its 52-week high on 1.34x volume. It needs the close through the high.
- **Against:** Underwriting-cycle risk, plus a 9.7% run in 10 days with no coil behind it.
- **Condition:** hourly close above 396.46 (yesterday's intraday high) on 1.2x+ volume · **dead** on a daily close below 369.71.
- **Levels (from the conditions file):** wait-for area 369.45; too late above 403.19; exit lines, highest first: 380.01 · 376.04 · 369.71 · 369.45 · 364.07.
- **Context:** Financials (XLF) HOLD, improving, macro caution -0.40.

### CCEP — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 15

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 113.41 · ATR-fallback stop 111.37 (1.8%) · TP 113.67 / 116.68 / 120.51 · R:R to TP2 1.6 |
| Tape | 7.72% above 20-day · vs SPY 20d +11.41 · beats the market · mp 84 accelerating |
| Structure | already trending, averages tangled · 0.00% from 52w high · +3.78% from pivot |
| Effort | volume 1.38x · 4.43 ATR over 20-day · 10d run +11.50% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (sustained) |
| Fundamentals | stalwart, fundamentals neutral · P/E 22.8 · net margin 9.3% · rev +2% (latest FY) · P/FCF 21.2 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Staples bottler at a new high, but the most extended name in the room (4.43 ATR above its 20-day).
- **Against:** A late-stage thrust: 11.5% in 10 days, Staples graded Hold (don't add), coil and money-flow warnings.
- **Condition:** hourly close above 113.51 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today · **dead** on a daily close below 108.26.
- **Levels (from the conditions file):** wait-for area 104.38; too late above 114.74; exit lines, highest first: 108.26 · 107.24 · 105.28 · 104.38 · 104.34 · 102.34.
- **Context:** Consumer Staples (XLP) DEPLOY, leading, macro help +0.54.

### DRH — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 19

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 13.79 · ATR-fallback stop 13.46 (2.39%) · TP 13.88 / 14.34 / 14.92 · R:R to TP2 1.67 |
| Tape | 10.19% above 20-day · vs SPY 20d +12.58 · beats the market · mp 90 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +6.82% from pivot |
| Effort | volume 0.76x · 3.18 ATR over 20-day · 10d run +11.39% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 |
| Fundamentals | cyclical, fundamentals neutral · P/E 18.9 · net margin 13.5% · rev -1% (latest FY) · P/FCF 17.3 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Lodging REIT at a new high, but on 0.76x volume with a bearish divergence: a high made on falling volume.
- **Against:** Fifth lodging name. A new high on 0.76x volume means buying has stopped.
- **Condition:** hourly close above 13.88 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today · **dead** on a daily close below 12.74.
- **Levels (from the conditions file):** wait-for area 12.74; too late above 14.21; exit lines, highest first: 12.74 · 12.74 · 12.41.
- **Context:** Real Estate (XLRE) WATCH, improving, macro neutral +0.00.

### ADP — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 22

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 292.75 · ATR-fallback stop 287.23 (1.89%) · TP 294.27 / 304.69 / 317.95 · R:R to TP2 2.16 |
| Tape | 7.01% above 20-day · vs SPY 20d +9.13 · beats the market · mp 78 accelerating |
| Structure | already trending, averages tangled · 0.00% from 52w high · +5.11% from pivot |
| Effort | volume 1.37x · 4.06 ATR over 20-day · 10d run +11.58% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | stalwart, fundamentals contradicts · P/E 26.7 · net margin 20.1% · rev +7% (latest FY) · P/FCF 23.3 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Payroll compounder at a new high on 1.37x volume, but already 5.11% past its pivot.
- **Against:** PEG ~2.7, and the lens shows extension without money flow (1/6).
- **Condition:** hourly close above 294.27 (yesterday's intraday high) on 1.4x+ volume; confirmed by outperforms SPY today, volume at least 1.4x normal for the time of day · **dead** on a daily close below 275.76.
- **Levels (from the conditions file):** wait-for area 270.32; too late above 299.79; exit lines, highest first: 275.76 · 273.56 · 273.00 · 270.32 · 269.33 · 264.80.
- **Context:** Industrials (XLI) TURNING, lagging, macro headwind -1.06.

### APLE — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 28

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 17.82 · ATR-fallback stop 17.46 (2.02%) · TP 17.86 / 18.38 / 19.04 · R:R to TP2 1.56 |
| Tape | 10.53% above 20-day · vs SPY 20d +13.49 · beats the market · mp 84 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +6.71% from pivot |
| Effort | volume 1.4x · 3.78 ATR over 20-day · 10d run +9.12% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (acceleration) |
| Fundamentals | cyclical, fundamentals neutral · P/E 24.1 · net margin 12.2% · rev -1% (latest FY) · P/FCF 12.5 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2026-11-05 (11 sessions): inside the window, decide before the print |

- **For:** Lodging REIT at a new high on 1.4x volume. Its 50-day (16.12) is still under its 100-day (16.24).
- **Against:** Fourth lodging name, the same exposure as PEB. Reports 11-05.
- **Condition:** hourly close above 17.86 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today · **dead** on a daily close below 16.52.
- **Levels (from the conditions file):** wait-for area 16.46; too late above 18.22; exit lines, highest first: 16.52 · 16.46 · 16.10.
- **Context:** Real Estate (XLRE) WATCH, improving, macro neutral +0.00.

### SHO — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 34

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 12.40 · ATR-fallback stop 12.12 (2.26%) · TP 12.47 / 12.85 / 13.32 · R:R to TP2 1.61 |
| Tape | 10.60% above 20-day · vs SPY 20d +12.37 · beats the market · mp 90 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +10.81% from pivot |
| Effort | volume 1.6x · 3.39 ATR over 20-day · 10d run +10.52% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (acceleration) |
| Fundamentals | cyclical, fundamentals contradicts · P/E 50.3 · net margin 5.3% · rev +6% (latest FY) · P/FCF 19.9 |
| QS | SKIP · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2026-11-06 (12 sessions): inside the window, decide before the print |

- **For:** Lodging REIT at a new high on 1.6x volume, but 10.81% past its pivot, and its 50-day is under its 100-day.
- **Against:** EPS −70% at a 50x multiple; fifth of the theme. Reports 11-06.
- **Condition:** hourly close above 12.47 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today · **dead** on a daily close below 11.05.
- **Levels (from the conditions file):** wait-for area 11.45; too late above 12.75; exit lines, highest first: 11.45 · 11.17 · 11.05.
- **Context:** Real Estate (XLRE) WATCH, improving, macro neutral +0.00.

### MET — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 69

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 101.18 · ATR-fallback stop 99.22 (1.94%) · TP 102.43 / 105.21 / 108.75 · R:R to TP2 2.06 |
| Tape | 4.32% above 20-day · vs SPY 20d +6.04 · beats the market · mp 68 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +2.77% from pivot |
| Effort | volume 0.66x · 1.75 ATR over 20-day · 10d run +4.14% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 9 (correction reentry) |
| Fundamentals | stalwart, fundamentals neutral · P/E 19.3 · net margin 4.6% · rev +10% (latest FY) · P/FCF 3.9 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Insurer at a new high with the averages in order, on quiet volume (0.66x).
- **Against:** A high on lower volume, and it is not the Financials leader (rank 69).
- **Condition:** hourly close above 101.39 (yesterday's intraday high) on 1.2x+ volume · **dead** on a daily close below 96.99.
- **Levels (from the conditions file):** wait-for area 97.75; too late above 103.35; exit lines, highest first: 97.47 · 96.99 · 95.79.
- **Context:** Financials (XLF) HOLD, improving, macro caution -0.40.

### ABBV — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 76

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 289.08 · ATR-fallback stop 282.61 (2.24%) · TP 291.40 / 300.52 / 312.12 · R:R to TP2 1.77 |
| Tape | 9.50% above 20-day · vs SPY 20d +9.56 · beats the market · mp 86 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +7.31% from pivot |
| Effort | volume 1.06x · 2.64 ATR over 20-day · 10d run +8.40% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | stalwart, fundamentals contradicts · P/E 81.4 · net margin 9.8% · rev +9% (latest FY) · P/FCF 28.0 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Pharma at a new high with the averages in order, 9.5% above its 20-day. It is part of the same Healthcare bet as CAH and LLY.
- **Against:** EPS down three years running, negative equity, and #5 in its group by rank.
- **Condition:** hourly close above 290.98 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today, volume at least 1.2x normal for the time of day · **dead** on a daily close below 272.03.
- **Levels (from the conditions file):** wait-for area 272.03; too late above 297.45; exit lines, highest first: 272.03 · 266.15 · 265.56 · 264.01.
- **Context:** Healthcare (XLV) DEPLOY, leading, macro neutral +0.00.

### AVPT — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 113

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 15.23 · ATR-fallback stop 14.65 (3.81%) · TP 15.43 / 16.27 / 17.25 · R:R to TP2 1.79 |
| Tape | 11.28% above 20-day · vs SPY 20d +16.82 · beats the market · mp 93 accelerating |
| Structure | in a range, averages in order · 0.00% from 52w high · -1.30% from pivot |
| Effort | volume 0.89x · 1.81 ATR over 20-day · 10d run +4.39% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | fast grower, fundamentals supports · P/E 45.6 · net margin 15.3% · rev +27% (latest FY) · P/FCF 32.0 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2026-11-05 (11 sessions): inside the window, decide before the print |

- **For:** Accelerating grower (revenue +27/22/17%) in a tight range at its high. It has not broken out yet.
- **Against:** No base and no pivot, a bearish divergence (2), and Technology is graded Avoid. Reports 11-05.
- **Condition:** pullback to 14.18 (the 20-day) with the Elder reading 7+ or hourly close above 15.43 (the pivot) on 1.4x+ volume · **dead** on a daily close below 13.69.
- **Levels (from the conditions file):** wait-for area 14.18; too late above 16.20; exit lines, highest first: 15.14 · 13.69 · 13.60.
- **Context:** Technology (XLK) AVOID, weakening, macro headwind -0.90.

### ROKU — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 123

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 157.57 · ATR-fallback stop 155.61 (1.24%) · TP 158.85 / 159.89 / 164.96 · R:R to TP2 1.18 |
| Tape | 1.73% above 20-day · vs SPY 20d +2.71 · beats the market · mp 38 accelerating |
| Structure | in a range, averages tangled · -1.37% from 52w high · -0.81% from pivot |
| Effort | volume 0.95x · 2.19 ATR over 20-day · 10d run +3.62% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 9 (acceleration) |
| Fundamentals | fast grower, fundamentals neutral · P/E 65.7 · net margin 6.8% · rev +15% (latest FY) · P/FCF 25.2 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Coiled near its highs (1.73% above its 20-day, coil strong, zero lens warnings): a range waiting to break.
- **Against:** Weak momentum (mp 38); only +2.71 against SPY.
- **Condition:** hourly close above 157.57 (yesterday's intraday high) on 1.4x+ volume or pullback to 153.27 (the 20-day) with the Elder reading 7+ or hourly close above 158.85 (the pivot) on 1.4x+ volume; confirmed by volume at least 1.4x normal for the time of day · **dead** on a daily close below 153.27.
- **Levels (from the conditions file):** wait-for area 153.27; too late above 159.53; exit lines, highest first: 157.87 · 154.89 · 153.27 · 152.29 · 151.31 · 150.03.
- **Context:** Communication Services (XLC) TURNING, lagging, macro headwind -0.90.

### KMI — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 82

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 33.57 · ATR-fallback stop 32.81 (2.26%) · TP 34.81 / 35.88 / 37.24 · R:R to TP2 3.04 |
| Tape | 5.68% above 20-day · vs SPY 20d +7.92 · beats the market · mp 64 decelerating |
| Structure | already trending, averages in order · -2.16% from 52w high · +4.29% from pivot |
| Effort | volume 0.96x · 2.05 ATR over 20-day · 10d run +4.38% |
| Lists · Elder | longlist yes · Elder list no · Elder reading 7 |
| Fundamentals | stalwart, fundamentals neutral · P/E 21.5 · net margin 19.3% · rev +12% (latest FY) · P/FCF 23.7 |
| QS | SKIP · odds 0.52 · edge -23.3 pts vs market |

- **For:** Midstream name 2.16% under its high, holding its 20-day on an inside bar. It is unresolved.
- **Against:** Flat averages (31.77/31.84/31.81): there is no trend to ride.
- **Condition:** hourly close above 33.68 (yesterday's intraday high) or daily close above 33.68 (yesterday's intraday high) on 1.4x+ volume · **dead** on a daily close below 31.77.
- **Levels (from the conditions file):** wait-for area 32.01; too late above 34.44; exit lines, highest first: 31.77.
- **Context:** Energy (XLE) DEPLOY, leading, macro neutral -0.08.

### CRM — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 190

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 242.43 · ATR-fallback stop 232.01 (4.3%) · TP 262.33 / 268.27 / 289.58 · R:R to TP2 2.48 |
| Tape | 4.49% above 20-day · vs SPY 20d +4.48 · beats the market · mp 33 accelerating |
| Structure | in a range, averages in order · -8.94% from 52w high · -7.59% from pivot |
| Effort | volume 0.92x · 0.95 ATR over 20-day · 10d run +7.75% |
| Lists · Elder | longlist no · Elder list yes · Elder reading 10 |
| Fundamentals | stalwart, fundamentals supports · P/E 22.0 · net margin 22.0% · rev +10% (latest FY) · P/FCF 13.2 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2026-12-02 (30 sessions): inside the window, decide before the print |

- **For:** Software name contracting in a range above its 20- and 50-day at a fair price (PEG ~1.0, FCF yield ~7.6%).
- **Against:** Technology is graded Avoid, with overhead supply 8.9% below the high.
- **Condition:** hourly close above 262.33 (the pivot) on 1.4x+ volume; confirmed by volume at least 1.4x normal for the time of day · **dead** on a daily close below 232.01.
- **Levels (from the conditions file):** wait-for area 232.01–233.99; too late above 252.98; exit lines, highest first: 257.91 · 232.01 · 229.57.
- **Context:** Technology (XLK) AVOID, weakening, macro headwind -0.90.

### BRZE — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 8

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 45.57 · ATR-fallback stop 43.06 (5.51%) · TP 45.61 / 51.96 / 60.03 · R:R to TP2 2.55 |
| Tape | 59.65% above 20-day · vs SPY 20d +79.13 · beats the market · mp 93 accelerating |
| Structure | already trending, averages tangled · 0.00% from 52w high · +30.13% from pivot |
| Effort | volume 32.65x · 7.04 ATR over 20-day · 10d run +73.01% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | fast grower, fundamentals contradicts · P/E -44.2 · net margin -13.6% · rev +24% (latest FY) · P/FCF 61.9 |
| QS | SKIP · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2026-12-08 (34 sessions): inside the window, decide before the print |

- **For:** Event-sized re-rating: 32.65x volume, +79 against SPY over 20 days, at a new high.
- **Against:** 59.65% over its 20-day is a climax footprint, on an unprofitable SaaS name whose growth is slowing.
- **Condition:** pullback to 27.90 (the 20-day) with the Elder reading 7+ or hourly close above 45.61 (yesterday's intraday high) on 1.2x+ volume · **dead** on a daily close below 33.77.
- **Levels (from the conditions file):** wait-for area 27.90; too late above 46.87; exit lines, highest first: 33.77 · 25.39.
- **Context:** Technology (XLK) AVOID, weakening, macro headwind -0.90.

### AFL — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 165

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 120.27 · ATR-fallback stop 118.19 (1.73%) · TP 122.79 / 125.93 / 130.22 · R:R to TP2 2.72 |
| Tape | 3.33% above 20-day · vs SPY 20d +5.51 · beats the market · mp 74 accelerating |
| Structure | broke out, averages tangled · -7.16% from 52w high · +1.85% from pivot |
| Effort | volume 0.78x · 2.52 ATR over 20-day · 10d run +5.84% |
| Lists · Elder | longlist no · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | stalwart, fundamentals neutral · P/E 12.9 · net margin 26.9% · rev -9% (latest FY) · P/FCF 22.8 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Insurer broke its structure upward above the 200-day, with a bullish pin bar.
- **Against:** Its 50-day is under its 100-day, RS rank is 52, and the break came on 0.78x volume.
- **Condition:** dip under 118.09 (the pivot) then an hourly close back above it on 1.2x+ volume or daily close above 120.65 (yesterday's intraday high) · **dead** on a daily close below 117.05.
- **Levels (from the conditions file):** wait-for area 116.76–118.09; too late above 122.73; exit lines, highest first: 117.05 · 116.76.
- **Context:** Financials (XLF) HOLD, improving, macro caution -0.40.

### EW — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 259

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 88.29 · ATR-fallback stop 85.98 (2.62%) · TP 89.08 / 92.95 / 96.29 · R:R to TP2 2.02 |
| Tape | -0.01% above 20-day · vs SPY 20d +0.01 · in line with the market · mp 18 decelerating |
| Structure | in a range, averages tangled · -7.24% from 52w high · -1.57% from pivot |
| Effort | volume 0.48x · 0.95 ATR over 20-day · 10d run +2.09% |
| Lists · Elder | longlist no · Elder list yes · Elder reading 9 |
| Fundamentals | stalwart, fundamentals contradicts · P/E 50.7 · net margin 15.4% · rev +12% (latest FY) · P/FCF 35.5 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** MedTech name coiled on its 50-day (88.29) with volume dried up (0.48x).
- **Against:** No trend, no high, mp 18, and the multiple runs ahead of earnings.
- **Condition:** hourly close above 88.34 (yesterday's intraday high) on 1.4x+ volume or pullback to 86.38 (the 20-day) with the Elder reading 7+ or dip under 88.29 (the 50-day) then an hourly close back above it · **dead** on a daily close below 85.16.
- **Levels (from the conditions file):** wait-for area 86.38–88.29; too late above 90.36; exit lines, highest first: 85.16 · 84.36 · 82.43.
- **Context:** Healthcare (XLV) DEPLOY, leading, macro neutral +0.00.

### KDP — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 9

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 34.63 · ATR-fallback stop 33.82 (2.34%) · TP 34.89 / 36.20 / 37.87 · R:R to TP2 1.94 |
| Tape | 9.11% above 20-day · vs SPY 20d +10.46 · beats the market · mp 80 accelerating |
| Structure | already trending, averages in order · 0.00% from 52w high · +7.75% from pivot |
| Effort | volume 1.65x · 3.22 ATR over 20-day · 10d run +11.24% |
| Lists · Elder | longlist yes · Elder list no · Elder reading 7 |
| Fundamentals | stalwart, fundamentals contradicts · P/E 34.8 · net margin 7.1% · rev +8% (latest FY) · P/FCF 23.9 |
| QS | SKIP · odds 0.52 · edge -23.3 pts vs market |

- **For:** AQE's top Staples name (rank 9) at a new high on 1.65x volume, but 7.75% past its pivot.
- **Against:** The Elder reading slipped 10→7 on the last bar (profit-taking), and PEG is above 2.
- **Condition:** hourly close above 34.89 (yesterday's intraday high) on 1.2x+ volume; confirmed by outperforms SPY today, volume at least 1.2x normal for the time of day, volume at least 1.4x normal for the time of day · **dead** on a daily close below 32.02.
- **Levels (from the conditions file):** too late above 35.35; exit lines, highest first: 32.02 · 31.86 · 31.74 · 31.73 · 31.33.
- **Context:** Consumer Staples (XLP) DEPLOY, leading, macro help +0.54.

### CHD — HOLD-FOR-CONDITIONS · MOMENTUM · conviction 2 · AQE rank 21

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 105.96 · ATR-fallback stop 104.14 (1.72%) · TP 106.00 / 109.45 / 113.83 · R:R to TP2 1.92 |
| Tape | 7.73% above 20-day · vs SPY 20d +10.80 · beats the market · mp 94 accelerating |
| Structure | already trending, averages tangled · 0.00% from 52w high · +9.19% from pivot |
| Effort | volume 1.03x · 4.21 ATR over 20-day · 10d run +9.76% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 10 (correction reentry) |
| Fundamentals | stalwart, fundamentals contradicts · P/E 34.0 · net margin 12.0% · rev +2% (latest FY) · P/FCF 22.5 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Staples name at a new high (mp 94), but its averages are nearly flat: a young uptrend.
- **Against:** RS rank 69.8 is just under 70, and it is 4.21 ATR extended.
- **Condition:** hourly close above 106.00 (yesterday's intraday high) on 1.2x+ volume; confirmed by volume at least 1.2x normal for the time of day, outperforms SPY today · **dead** on a daily close below 98.36.
- **Levels (from the conditions file):** wait-for area 98.30; too late above 107.82; exit lines, highest first: 98.36 · 98.30 · 96.48 · 96.13.
- **Context:** Consumer Staples (XLP) DEPLOY, leading, macro help +0.54.

### KO — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 80

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 93.49 · ATR-fallback stop 92.06 (1.53%) · TP 94.10 / 96.54 / 99.64 · R:R to TP2 2.13 |
| Tape | 5.40% above 20-day · vs SPY 20d +6.07 · beats the market · mp 72 accelerating |
| Structure | already trending, averages in order · -0.44% from 52w high · +4.62% from pivot |
| Effort | volume 0.97x · 3.33 ATR over 20-day · 10d run +8.49% |
| Lists · Elder | longlist yes · Elder list no · Elder reading 7 |
| Fundamentals | stalwart, fundamentals contradicts · P/E 28.1 · net margin 28.6% · rev +2% (latest FY) · P/FCF 28.1 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Defensive stalwart 0.44% under its 52-week high, averages in order, on an inside bar.
- **Against:** #5 in its group, PEG ~2.3, and the Elder reading slipped 10→7.
- **Condition:** hourly close above 93.96 (yesterday's intraday high) on 1.2x+ volume or daily close above 93.90 (the 52-week closing high) on 1.2x+ volume · **dead** on a daily close below 88.73.
- **Levels (from the conditions file):** wait-for area 88.73; too late above 93.83; exit lines, highest first: 92.64 · 88.73 · 88.70 · 88.64.
- **Context:** Consumer Staples (XLP) DEPLOY, leading, macro help +0.54.

### OXY — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 90

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 62.92 · ATR-fallback stop 61.38 (2.45%) · TP 63.77 / 65.46 / 67.62 · R:R to TP2 1.65 |
| Tape | 5.67% above 20-day · vs SPY 20d +12.30 · beats the market · mp 68 accelerating |
| Structure | in a range, averages tangled · -5.01% from 52w high · -1.33% from pivot |
| Effort | volume 0.88x · 2.46 ATR over 20-day · 10d run +7.87% |
| Lists · Elder | longlist yes · Elder list no · Elder reading 7 |
| Fundamentals | cyclical, fundamentals neutral · P/E 9.5 · net margin 28.8% · rev -2% (latest FY) · P/FCF 11.8 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2026-11-09 (13 sessions): inside the window, decide before the print |

- **For:** Energy name ranging above averages in order; it gains ground on days the market falls (1.23).
- **Against:** In a range, not at a high; Energy is graded Hold (don't add). Reports 11-09.
- **Condition:** hourly close above 63.63 (yesterday's intraday high) on 1.4x+ volume; confirmed by holds above today's VWAP · **dead** on a daily close below 59.54.
- **Levels (from the conditions file):** wait-for area 59.13; too late above 65.17; exit lines, highest first: 59.54 · 54.76.
- **Context:** Energy (XLE) DEPLOY, leading, macro neutral -0.08.

### HOMB — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 159

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 29.39 · ATR-fallback stop 28.85 (1.84%) · TP 30.28 / 31.54 / 32.69 · R:R to TP2 3.98 |
| Tape | -0.46% above 20-day · vs SPY 20d +1.42 · in line with the market · mp 53 accelerating |
| Structure | in a range, averages tangled · -6.64% from 52w high · -3.19% from pivot |
| Effort | volume 1.3x · 1.41 ATR over 20-day · 10d run +2.94% |
| Lists · Elder | longlist yes · Elder list yes · Elder reading 9 (acceleration) |
| Fundamentals | stalwart, fundamentals supports · P/E 11.9 · net margin 32.4% · rev -5% (latest FY) · P/FCF 13.7 |
| QS | SKIP · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2027-01-13 (60 sessions): inside the window, decide before the print |

- **For:** Cheap regional bank (P/E 11.9) coiling between its 20- and 50-day on 1.3x volume.
- **Against:** Under its 50-day, structure 46, RS only in line with the market.
- **Condition:** hourly close above 29.69 (yesterday's intraday high) on 1.4x+ volume; confirmed by volume at least 1.4x normal for the time of day · **dead** on a daily close below 28.47.
- **Levels (from the conditions file):** wait-for area 28.67; too late above 30.20; exit lines, highest first: 29.52 · 28.47 · 28.16 · 27.60.
- **Context:** Financials (XLF) HOLD, improving, macro caution -0.40.

### ZION — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 223

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 64.59 · ATR-fallback stop 62.88 (2.65%) · TP 70.13 / 71.26 / 72.59 · R:R to TP2 3.9 |
| Tape | -2.32% above 20-day · vs SPY 20d +2.04 · in line with the market · mp 62 accelerating |
| Structure | broke out, averages tangled · -11.89% from 52w high · +1.16% from pivot |
| Effort | volume 2.4x · 1.24 ATR over 20-day · 10d run +2.77% |
| Lists · Elder | longlist no · Elder list yes · Elder reading 9 |
| Fundamentals | stalwart, fundamentals supports · P/E 7.9 · net margin 23.5% · rev -1% (latest FY) · P/FCF 4.6 |
| QS | NONE · odds 0.51 · edge -24.3 pts vs market |
| Earnings | 2027-01-19 (64 sessions): inside the window, decide before the print |

- **For:** Cheap regional bank (P/E 7.9) squeezed and broke upward on 2.4x volume.
- **Against:** Still under its 50-day (66.12) and 11.9% off the high; bank funding data was not served.
- **Condition:** hourly close above 65.61 (yesterday's intraday high) on 1.4x+ volume or pullback to 62.88 (the 20-day) with the Elder reading 7+ or daily close above 66.12 (the 50-day) on 1.4x+ volume; confirmed by volume at least 1.4x normal for the time of day · **dead** on a daily close below 63.85.
- **Levels (from the conditions file):** wait-for area 62.88; too late above 67.04; exit lines, highest first: 66.12 · 63.85 · 62.88 · 61.50.
- **Context:** Financials (XLF) HOLD, improving, macro caution -0.40.

### ACA — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 224

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 147.45 · ATR-fallback stop 146.98 (0.32%) · TP 147.68 / 148.14 / 148.72 · R:R to TP2 1.47 |
| Tape | 1.05% above 20-day · vs SPY 20d +1.14 · beats the market · mp 63 decelerating |
| Structure | broke out, averages in order · 0.00% from 52w high · +0.43% from pivot |
| Effort | volume 0.95x · 1.49 ATR over 20-day · 10d run +0.65% |
| Lists · Elder | longlist no · Elder list yes · Elder reading 8 (accumulation base) |
| Fundamentals | cyclical, fundamentals neutral · P/E 14.7 · net margin 17.9% · rev +12% (latest FY) · P/FCF 53.6 |
| QS | SKIP · odds 0.52 · edge -23.3 pts vs market |

- **For:** Tight base at a new high (structure break, 1.05% above its 20-day), lens 4/6 with no warnings. It has the widest agreement of any HOLD.
- **Against:** No volume (0.95x) and weak flow (48.7). It needs follow-through.
- **Condition:** hourly close above 147.68 (yesterday's intraday high) on 1.4x+ volume or hourly close above 146.82 (the pivot) on 1.4x+ volume; confirmed by volume at least 1.4x normal for the time of day · **dead** on a daily close below 146.59.
- **Levels (from the conditions file):** wait-for area 146.75–146.82; too late above 148.15; exit lines, highest first: 146.82 · 146.59 · 146.35 · 146.28 · 145.92 · 135.65.
- **Context:** Industrials (XLI) TURNING, lagging, macro headwind -1.06.

### TTEK — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 234

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 34.96 · ATR-fallback stop 33.79 (3.35%) · TP 37.27 / 39.54 / 42.03 · R:R to TP2 3.91 |
| Tape | -0.73% above 20-day · vs SPY 20d -0.85 · in line with the market · mp 25 accelerating |
| Structure | in a range, averages inverted · -17.95% from 52w high · -6.20% from pivot |
| Effort | volume 0.76x · 1.41 ATR over 20-day · 10d run +4.73% |
| Lists · Elder | longlist no · Elder list yes · Elder reading 10 (acceleration) |
| Fundamentals | stalwart, fundamentals neutral · P/E 20.9 · net margin 8.6% · rev +5% (latest FY) · P/FCF 16.3 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |
| Earnings | 2026-11-11 (15 sessions): inside the window, decide before the print |

- **For:** Coiled range above its 20-day.
- **Against:** Lags the market (−0.85), longer averages inverted, 17.95% off the high. Reports 11-11.
- **Condition:** pullback to 33.79 (the 20-day) with the Elder reading 7+ or hourly close above 35.22 (the 50-day) on 1.4x+ volume · **dead** on a daily close below 33.79.
- **Levels (from the conditions file):** wait-for area 33.79; too late above 36.98; exit lines, highest first: 33.79 · 32.96.
- **Context:** Industrials (XLI) TURNING, lagging, macro headwind -1.06.

### MRK — HOLD-FOR-CONDITIONS · PULLBACK · conviction 2 · AQE rank 285

| Row | Read |
|---|---|
| Bracket (render-only, unsized) | ref 148.30 · ATR-fallback stop 144.30 (2.7%) · TP 152.80 / 156.92 / 165.27 · R:R to TP2 2.15 |
| Tape | 1.73% above 20-day · vs SPY 20d -1.17 · in line with the market · mp 23 decelerating |
| Structure | in a range, averages tangled · -5.21% from 52w high · -3.43% from pivot |
| Effort | volume 1.06x · 0.75 ATR over 20-day · 10d run +4.48% |
| Lists · Elder | longlist no · Elder list yes · Elder reading 9 (interrupted) |
| Fundamentals | stalwart, fundamentals contradicts · P/E 117.7 · net margin 4.8% · rev +1% (latest FY) · P/FCF 22.8 |
| QS | NONE · odds 0.52 · edge -23.3 pts vs market |

- **For:** Uptrend intact (averages in order), coiled near its 20-day.
- **Against:** Lags the market (−1.17), mp 23, P/E 117 on depressed earnings.
- **Condition:** hourly close above 149.36 (yesterday's intraday high) on 1.4x+ volume or hourly close above 153.57 (the pivot) on 1.4x+ volume or daily close above 149.36 (yesterday's intraday high) on 1.4x+ volume; confirmed by volume at least 1.4x normal for the time of day · **dead** on a daily close below 145.77.
- **Levels (from the conditions file):** wait-for area 145.32; too late above 153.36; exit lines, highest first: 151.57 · 145.77 · 138.80.
- **Context:** Healthcare (XLV) DEPLOY, leading, macro neutral +0.00.

### PASS — one line each

- **AEP** (MOMENTUM): A structure break inside a downtrend: the averages are inverted and volume was 0.69x. That is a rally, not a trend.
- **O** (PULLBACK): Broken REIT: its structure turned down and it trades under its 200-day. The reversion case named no catalyst.
- **CCI** (PULLBACK): Sharpest thrust in the room (+18.8% in 10 days, rank 4), running into its 200-day from below on a broken balance sheet.
- **TDC** (PULLBACK): Rebound in a Declining tech group, with the 50-day under both longer averages.
- **LNT** (PULLBACK): Utility bouncing inside a bearish structure under its 200-day. Reversion with no catalyst.
- **CMS** (PULLBACK): Utility with inverted averages and 4 lens warnings, the weakest structure among the conviction-3 names.
- **KIM** (PULLBACK): Below its 50- and 200-day: a bounce, not a base.
- **TRP** (PULLBACK): Pipeline name with a bearish structure and its 50-day under its 200-day. Reversion with no catalyst.
- **REG** (PULLBACK): REIT with a bearish structure under its 50-day. Contraction inside a falling structure.
- **VTR** (PULLBACK): REIT with a bearish structure, 13.97% off the high, on 0.59x volume.
- **CL** (MOMENTUM): Structure break on 0.73x volume with flat averages; shrinking earnings at a premium.
- **LYFT** (PULLBACK): 29.8% under its high in a Declining group: a rebound, not a leader.
- **DOCS** (MOMENTUM): Broken leader (−51% from the high) in a sharp repair, 23.5% above its 20-day.
- **PBI** (PULLBACK): Bearish structure; the volume came on a failed structure.
- **MRSH** (MOMENTUM): In a range on 0.75x volume, with an RS rank of 59.
- **TTAN** (MOMENTUM): Failed up-structure in a Declining group; an unprofitable SaaS name whose growth is slowing.
- **NDAQ** (PULLBACK): In a range with mp 26, not at a high.
- **OKTA** (PULLBACK): Elder reading has been red for four bars (0.0), a hard no-buy. The room's only pre-move tag is a radar read, not a trigger.
- **MP** (PULLBACK): Held. The add was refused unanimously and every held review reads EXIT: stage 4, 22.86% under its 20-day, with no broker stop.

## §8 NEAR MISSES

| Name | Door it nearly cleared | What it lacked |
|---|---|---|
| SLDE | Elder+Lens + Strength + AQE leader + PM lens (AQE rank 60, mp 79, 2.21% from pivot) | No analyst nominated it. Flagged for the PM only (R17): no vote, no verdict |
| CNQ | Elder+Lens + Strength + AQE leader + PM lens (AQE rank 62, mp 82, 3.57% from pivot) | No analyst nominated it. Flagged for the PM only (R17): no vote, no verdict |
| UNH | Elder+Lens + Strength + AQE leader + PM lens (AQE rank 118, mp 82, 3.13% from pivot) | No analyst nominated it. Flagged for the PM only (R17): no vote, no verdict |
| PPG | Elder+Lens + Lens + PM lens (AQE rank 236, mp 35, 0.57% from pivot) | No analyst nominated it. Flagged for the PM only (R17): no vote, no verdict |
| HRL | Elder+Lens + Lens + PM lens (AQE rank 290, mp 65, 0.64% from pivot) | No analyst nominated it. Flagged for the PM only (R17): no vote, no verdict |
| SN | Elder+Lens + Strength + PM lens (AQE rank 20, mp 79, 13.69% from pivot) | No analyst nominated it. Flagged for the PM only (R17): no vote, no verdict |
| TAK | Elder+Lens + AQE leader + PM lens (AQE rank 53, mp 72, 5.13% from pivot) | No analyst nominated it. Flagged for the PM only (R17): no vote, no verdict |
| MRNA | Elder+Lens + Strength + PM lens (AQE rank 72, mp 70, 54.76% from pivot) | No analyst nominated it. Flagged for the PM only (R17): no vote, no verdict |
| BALL | Elder+Lens + AQE leader + PM lens (AQE rank 106) | No nomination, and outside the 8 informational slots |
| AIG | Strength + AQE leader + PM lens (AQE rank 65) | No nomination, and outside the 8 informational slots |
| HST | Strength + AQE leader + PM lens (AQE rank 94) | No nomination, and outside the 8 informational slots |
| KMB | Strength + AQE leader + PM lens (AQE rank 74) | No nomination, and outside the 8 informational slots |
| ACGL | Strength + AQE leader + PM lens (AQE rank 75) | No nomination, and outside the 8 informational slots |

- 151 door-openers did not reach the floor; repeat-watch carries 112 of today's names as NEAR-MISS.

## §9 ACTION PLAN

1. **Decide MP today.** EXIT, or write a stop. No stop sits at Tiger, and the committee case is EXIT.
2. **Pick from the nine by readiness, not by count:** CNC, PK, CNK and MA sit within 0.7% of their buy lines, and A within 1.1%. HNGE and PEB are the right names at stretched prices.
3. **Own one lodging name, not two:** PEB carries the theme and PK is the same exposure.
4. **Size is the PM's:** the macro calls 1.00x (Crown) against light (Druckenmiller), credit is soft, and no bracket clears both of its gates.
5. **Watch only (no action):** the 26 HOLD names fire only on their own lines (§7). The 8 UNSEEN lens names (SN, TAK, SLDE, CNQ, MRNA, PPG, UNH, HRL) opened doors that no analyst picked.
6. **Rule on the declarations:** D5 (the unwired seat that voted) and D7 (scorecard not advanced).

## §9A WHAT TO DO WITH WHAT I OWN

| Name | Qty | Entry | Mark | Unrealised | ACTION | Trigger that changes it | Stop today | Why (one line) |
|---|---|---|---|---|---|---|---|---|
| MP | 300 | 53.00 | 39.67 | ≈ −$3,999 | **EXIT** (committee case; keep/exit is the PM's call) | A daily close back above the 50-day 50.62 with the up-structure repaired (the committee's own falsifier). Short of that, EXIT stands; a trade at 36.66 removes the last mechanical line | **NONE at the broker.** Only line on file: mechanical floor 36.66, 7.6% under the mark; not a committee level | Stage 4: under every average, structure 11, AQE health EXIT, no stop; adding to a loser is barred. No earnings date served |

- **Book concentration:** a single name, 100% Materials, beta 3.0. The whole book is one bet against its own group's headwind (−0.94).
- **Total open risk:** unbounded while no stop exists. To the 36.66 floor it is a further ≈ $903; the full market value of $11,901 is at risk on a gap.
- **USO:** off the book (stopped at 156.43 on 20 Oct). Confirm the fill is journalled; no action on the position.

## §9B WHAT TO TRADE TODAY

| Ticker | Entry reference | Stop (render-only) | What confirms | What kills it | Sector context | Ready now / needs reset |
|---|---|---|---|---|---|---|
| CNK | hourly close above 40.35 (yesterday's intraday high) on 1.2x+ volume | 38.95 (ATR fallback, 2.99%) | outperforms SPY today; volume at least 1.2x normal for the time of day; volume at least 1.4x normal for the time of day | daily close below 38.47 | Consumer Discretionary (XLY) HOLD, improving, macro headwind -1.06 | **Ready now**: 0.5% under its line, volume already 1.46x |
| A | hourly close above 174.80 (yesterday's intraday high) on 1.4x+ volume | 168.32 (ATR fallback, 2.71%) | volume at least 1.4x normal for the time of day | daily close below 168.90 | Healthcare (XLV) DEPLOY, leading, macro neutral +0.00 | **Ready now**: coiled 1.0% under the line; needs the 1.4x volume day |
| CNC | hourly close above 70.97 (yesterday's intraday high) on 1.2x+ volume or dip under 69.63 (the pivot) then an hourly close back above it on 1.2x+ volume | 68.61 (ATR fallback, 3.11%) | holds above today's VWAP | daily close below 68.53 | Healthcare (XLV) DEPLOY, leading, macro neutral +0.00 | **Ready now**: 0.2% under the line, or buy a retest of 69.63; needs volume |
| PK | hourly close above 16.63 (yesterday's intraday high) on 1.4x+ volume | 16.13 (ATR fallback, 2.66%) | outperforms SPY today; volume at least 1.4x normal for the time of day | daily close below 15.69 | Real Estate (XLRE) WATCH, improving, macro neutral +0.00 | **Ready now**: 0.4% under the line; own it or PEB, not both |
| MA | hourly close above 624.29 (yesterday's intraday high) on 1.4x+ volume | 610.41 (ATR fallback, 1.61%) | outperforms SPY today; volume at least 1.4x normal for the time of day | daily close below 596.23 | Financials (XLF) HOLD, improving, macro caution -0.40 | **Ready now, missing proof**: 0.6% under the line on 0.95x volume |
| PRCH | hourly close above 18.41 (yesterday's intraday high) on 1.4x+ volume | 17.35 (ATR fallback, 4.57%) | volume at least 1.4x normal for the time of day | daily close below 17.57 | Technology (XLK) AVOID, weakening, macro headwind -0.90 | **Ready now**: 1.3% under the line; smallest conviction of the nine |
| CAH | hourly close above 257.55 (yesterday's intraday high) on 1.2x+ volume | 251.88 (ATR fallback, 2.2%) | outperforms SPY today | daily close below 246.46 | Healthcare (XLV) DEPLOY, leading, macro neutral +0.00 | **Ready, extended**: the line is the close (257.55) at 3.91 ATR over the 20-day; the reset is 235.40 |
| PEB | hourly close above 20.92 (yesterday's intraday high) on 1.4x+ volume | 20.02 (ATR fallback, 3.33%) | outperforms SPY today; volume at least 1.4x normal for the time of day | daily close below 19.16 | Real Estate (XLRE) WATCH, improving, macro neutral +0.00 | **Needs reset**: 11.9% over the 20-day; reset toward 19.09 |
| HNGE | hourly close above 108.00 (yesterday's intraday high) on 1.2x+ volume | 103.08 (ATR fallback, 4.12%) | outperforms SPY today; volume at least 1.2x normal for the time of day | daily close below 99.32 | Healthcare (XLV) DEPLOY, leading, macro neutral +0.00 | **Needs reset**: 14.3% over the 20-day on a climax-shaped bar; reset toward 99.32 |

No sizing, no order language, nothing armed. HOLD-FOR-CONDITIONS names are not here; their lines are in §0 and §7.

## §9C THE DAY'S PLAN

1. **Before the open:** rule on MP, either EXIT or a written stop. Today it sits 7.6% above a mechanical floor with nothing at the broker.
2. **At the open:** no entries on the open print. Every buy line is an hourly close, so the first actionable bar is the 10:30 ET close.
3. **First hour:** CNK (40.35), A (174.80), CNC (70.97) and PK (16.63) are the names closest to their lines; each needs its volume (1.2–1.4x) and to beat SPY on the day.
4. **During the session:** SPY against 774.95 (the dealer flip) and 760 (the put wall). A loss of 760 means no new breakouts for the rest of the day.
5. **What changes the plan mid-day:** Healthcare reversing (CNC, CAH, HNGE and A all back under yesterday's highs) withdraws the group thesis, not just one name.
6. **Before the close:** any name bought must close above its kill line. MP must be decided before the bell, not left for tomorrow.

---

# APPENDIX A — VOTE RECORD (audit only)

Seat names, splits and verbatim reasons appear here and nowhere else.

## A.0 run_notes.md (verbatim)

```
# Run declarations — PMA 2026-10-21 (for the brief header; every one must appear)
1. Skill source: plugin bundle aegis-core v5.4 (R16–R21). AQE main's premarket-analysis copy is older (v5.3, no RULINGS.yaml) — main is behind the plugin, not ahead.
2. Seat transport: compiled voice agents had no file tools in this harness (all 9 first spawns returned "not filed"). Every seat was re-spawned once as a general-purpose agent reading its OWN card + its OWN packet by path. R2 inlining replaced by path-read; figure audit (`validate --packet`) ran on every round-1 and round-2 form — 0 fabricated figures.
3. Packets: built locally by `pma_pipeline.py packets` from the trimmed universe (held floor MP injected, R12); AQE pre-sliced packets not used.
4. Fundamentals: FMP batch pulled after RANK for the 54-name room only (54/54 served), not the full universe at GATHER — declared cut.
5. Livermore: card marks the seat "NOT DECIDED / not wired" pending PM ruling; RUN.yaml seats him in NOMINATE and VOTE, so he ran. PM to rule.
6. Checkpoints: no git push after MACRO/NOMINATE/CHALLENGE/VOTE — session has read-only git to TongIncomeWheel/AQE; run sat on local disk until PUBLISH (via GitHub connector).
7. SCORECARD: not run — closes_scorecard.json (FMP EOD for every ledger + AQE list name, 10 sessions) not pulled this run; scorecard_log.jsonl NOT advanced for 2026-10-20 close.
8. REPEAT-WATCH: degraded — 805 historical (date,ticker) rows have no verdict_ledger match on main; today's 54 verdicts are recorded.
9. Broker: Tiger read-only 06:53Z. Zero working orders. `--previous` broker_stops not on main; USO vanish read from fills (STP 72 @ 156.43, 20 Oct 10:30 ET).
10. CHALLENGE packets: built by conductor from tally + menu-sliced rows (no tool exists for challenge packets); VOTE_PACKET 123 KB > 70 KB soft cap (54-name room).
```

## A.1 Ballots by name

### CNC — ADVANCE · PULLBACK · c3

- Counting: support 5 [livermore, minervini, oneil, raschke, weis] · oppose 0 [] · abstain 6 [detect-lens, elder-lens, lynch, seow, thorp, wyckoff]
- Nominated by: livermore (c4), minervini (c4), raschke (c3)
- **livermore** SUPPORT c4: C5 new high after pullback: from_52w_hi=0.0, structure_shift=BULLISH_BOS, structure 86.3; mp_state=BUILDING/ACCELERATING (my six-column analogue, C18). XLV group confirms with CAH/LLY (C14). I am buying the BREAKOUT, not the pullback lane label.
- **minervini** SUPPORT c4: Trend Template stage 2: entry=70.81 > ma50=65.54 > ma100=64.99 > ma200=54.43, from_52w_hi=0.0, rs_rank_pct=94.86, rs LEADER downday=0.76; BULLISH_BOS at pct_from_pivot=1.69, not chased (C3,C5).
- **oneil** SUPPORT c2: L pass rs_leadership=LEADER, XLV Momentum Building; base structure=86.3 BULLISH_BOS, pct_from_pivot=1.69 in buy zone. C16 FAIL today: day_vol=0.8 under 1.40, a break nobody bought. Buy only the volume day.
- **raschke** SUPPORT c3: setup=TEST (C2/C20): structure_shift=BULLISH_BOS, structure=86.3, mp_state=BUILDING, mp_accel_state=ACCELERATING, sma_distance_pct=8.05. Buy the retest of the cleared pivot, not the break. day_vol=0.8 thin participation caps conviction at 3.
- **weis** SUPPORT c2: W23 passes: ma50=65.54>ma200=54.43, structure_shift=BULLISH_BOS on light day_vol=0.8 (W4: light effort with progress is not bearish). I do not buy the break; I buy a test of pivot_high that fails to go lower. Small bet.

### CAH — ADVANCE · MOMENTUM · c3

- Counting: support 5 [detect-lens, elder-lens, livermore, minervini, oneil] · oppose 0 [] · abstain 0 []
- Advisory: support [raschke] · oppose [lynch] · abstain [seow, thorp, weis, wyckoff]
- Nominated by: livermore (c4), minervini (c4)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong) vs coil=warn, insti_money=warn. Trend filter passes: ma50 235.13>ma100 230.6>ma200 220.36. runner False. conv=ceil(3/1.5)=2; coil warn and ext_atr20 3.91 are weights (R14).
- **elder-lens** SUPPORT c2: R8 only: elder_5d=[10, 10, 10, 7, 10], CORRECTION_REENTRY, mp_state=STRONG, mp=87.0. Shallow dip to 7 and reclaim, no red lifted, so no C4 transition. Pullback timing per C6. Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** SUPPORT c4: C5/C12 leader at a new high: from_52w_hi=0.0, ABOVE_STRUCTURE, structure 83.2, mp STRONG/ACCELERATING, rank 13; XLV Momentum Building with LLY/ABBV also at highs (C14 group confirm). sma_dist 9.53 is a weight (R14), not a veto.
- **lynch** OPPOSE c2: r1_lynch=CONTRADICT stalwart: NM=0.7%, PE=35.4 vs EPS +12% FY26 -> PEG~2.9>2 (C8 red flag); P/B=-21.1 so C12 unreadable. sma_distance_pct=9.53 is multiple expansion. Story fine, price full. Momentum lane: advisory.
- **minervini** SUPPORT c4: Stage 2 at a new high: entry=257.55 > ma50=235.13 > ma100=230.6 > ma200=220.36, from_52w_hi=0.0, rs_rank_pct=82.5, downday=1.18 (holds up on down days, C11), mp=87.0 ACCELERATING.
- **oneil** SUPPORT c3: L pass: LEADER, rank=13 tops XLV, lens.leadership=strong, lens.sector=strong. Base structure=83.2 ABOVE_STRUCTURE, pct_from_pivot=3.31 inside 5%. day_vol=1.0 short of 1.40 (C16): act only on volume. lens.coil=warn weighs.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending (C2/C7, ADX NOT_SERVED; mp proxy): structure=83.2 ABOVE_STRUCTURE, mp_state=STRONG, mp_accel_state=ACCELERATING, elder_pattern=CORRECTION_REENTRY. sma_distance_pct=9.53 is a weight: act only on the first pullback to ma_20.

### PK — ADVANCE · MOMENTUM · c3

- Counting: support 4 [elder-lens, livermore, minervini, oneil] · oppose 0 [] · abstain 1 [detect-lens]
- Advisory: support [raschke] · oppose [lynch] · abstain [seow, thorp, weis, wyckoff]
- Nominated by: livermore (c3), minervini (c3)
- **elder-lens** SUPPORT c3: Red giving way, certain: elder_5d=[1, 9, 9, 10, 10] (1 is red, 9 is not; C3/C4) three bars ago, now ACCELERATION, mp_state=BUILDING, mp=68.0. Best colour event in the room on my menu; aged, so I buy the pullback (C6/C10). Trend leg unverifiable (C9).
- **livermore** SUPPORT c3: C5 new high: from_52w_hi=0.0, ABOVE_STRUCTURE, structure 83.2, day_vol 1.28, aligned stack ma50 15.39 > ma100 14.91 > ma200 13.01. My Key Price partner to PEB for the lodging group (C14).
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT cyclical: hotel REIT, PE=-20.2, NM=-6.4%, rev -2%/-4% FY25/24, D/E=1.33 (C12 >50% debt). Five lodging REITs = one cyclical bet; no industry upturn served (C5/C18). DY=6.04% is the only prop.
- **minervini** SUPPORT c3: Stage 2 new high: entry=16.57 > ma50=15.39 > ma100=14.91 > ma200=13.01, rs_rank_pct=91.31, day_vol=1.28; pct_from_pivot=4.15 inside the band (C3,C5).
- **oneil** SUPPORT c2: L: LEADER, rank=25, #3 lodging behind PEB/DRH so inside C9 top-3. structure=83.2, pct_from_pivot=4.15 near the 5% edge. day_vol=1.28 short of 1.40. Lens mostly '--', so base read is structure only.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=83.2 ABOVE_STRUCTURE, mp_state=BUILDING, mp_accel_state=ACCELERATING, day_vol=1.28, sma_distance_pct=7.66 (weight). One of the lodging cluster; act on first pullback to ma_20 only.

### PRCH — ADVANCE · PULLBACK · c3

- Counting: support 6 [detect-lens, elder-lens, livermore, minervini, raschke, wyckoff] · oppose 3 [lynch, oneil, thorp] · abstain 2 [seow, weis]
- Nominated by: minervini (c3), raschke (c3)
- **detect-lens** SUPPORT c3: lens_positive=4 (leadership, coil, structure, resistance strong); warns: insti_money, sector. BULLISH_BOS on day_vol 1.42. Trend filter: ma50 16.97>ma100 14.97>ma200 11.67. conv=ceil(4/1.5)=3. mp FADING is not decay (R13).
- **elder-lens** SUPPORT c2: Red lifted three bars ago: elder_5d=[0, 5, 8, 10, 10], elder=10.0, ACCELERATION. mp_state=FADING (R13: not decay), mp=43.0. Real C4 event but aged and now a plateau; buy only a pullback (C6).
- **livermore** SUPPORT c2: C5 trigger present: from_52w_hi=0.0, BULLISH_BOS on day_vol 1.42, structure 82.1. But C12 wants a leading group and sector reads Declining — Avoid, rs IN-LINE. New high, lone group: small.
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT turnaround: PE=-148.3, NM=-1.1%, negative equity (P/B=-166.8, D/E=-34.2); the C5 turnaround survival test fails on the balance sheet. sector_trend_state=Declining — Avoid.
- **minervini** SUPPORT c3: Stage 2: entry=18.18 > ma50=16.97 > ma100=14.97 > ma200=11.67, rs_rank_pct=99.39, BULLISH_BOS on day_vol=1.42 at pct_from_pivot=1.11. Weights: rs IN-LINE downday=-0.24, sector Declining.
- **oneil** OPPOSE c3: R2 FAIL: rs_leadership=IN-LINE, rs_down_day_20d=-0.24, not a leader. R9 Lone Ranger: sector_trend_state Declining — Avoid, lens.sector=warn. BOS on day_vol=1.42 passes C16 but nothing rescues a failed L.
- **raschke** SUPPORT c3: setup=TEST (C2/C20): structure_shift=BULLISH_BOS, structure=82.1, day_vol=1.42 above-normal on the break, elder_pattern=ACCELERATION (advisory). mp_accel_state=FLAT tempers; mp_state=FADING is not a reason (R13). Buy the pivot retest.
- **thorp** OPPOSE c2: edge=none measured in packet; structure/composites are a shape, not a mispricing (C11); vol_measure=atr_pct 4.57% (atr 0.83/entry 18.18; rank 51/54, q4) top quartile: ranks below calmer pullback names (C6/R1); rs IN-LINE, downday -0.24. Gap of one ATR costs most here (C4).
- **wyckoff** SUPPORT c3: Edge of a coil resolving up: lens.coil=strong, energy=79.8 (measured contraction, substitute for Crabel C5); structure_shift=BULLISH_BOS on day_vol=1.42 = effort met by reward (C6). sma_distance_pct=7.14, structure=82.1. mp_accel_state=FLAT is advisory only.

### PEB — ADVANCE · MOMENTUM · c3

- Counting: support 4 [elder-lens, livermore, minervini, oneil] · oppose 0 [] · abstain 1 [detect-lens]
- Advisory: support [] · oppose [lynch] · abstain [raschke, seow, thorp, weis, wyckoff]
- Nominated by: livermore (c4)
- **elder-lens** SUPPORT c2: C24 (unsourced): elder_5d=[7, 7, 9, 10, 10], mp_state=STRONG, mp=84.0. No <=6 bar in window, so no C4 event; rising into a plateau. Desk read only, labelled. Not red.
- **livermore** SUPPORT c4: Lodging theme carrier: rank 6, from_52w_hi=0.0, ABOVE_STRUCTURE, structure 82.1, mp STRONG/ACCELERATING, day_vol 1.36. C12: the leader of the leading group; PK confirms (C14).
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT cyclical: rev +2%/yr x3, EPS -131% FY25, PE=-30.9, NM=-3.1%, D/E=1.02, DY=0.19%. No earnings, no yield: nothing for a Lynch long to rest on. sma_distance_pct=11.88.
- **minervini** SUPPORT c3: Stage 2 new high: entry=20.71 > ma50=18.51 > ma100=18.43 > ma200=15.72, rs_rank_pct=91.8, mp=84.0 ACCELERATING, day_vol=1.36. sma_dist=11.88 is a weight (R14).
- **oneil** SUPPORT c3: L pass: rank=6, #1 lodging and #1 XLRE leader (C9 first man gets the oyster). LEADER, structure=82.1, sector Building. day_vol=1.36 short of 1.40. sma_distance_pct=11.88 extended: weight (R14), pivot distance UNSERVED.

### MA — ADVANCE · MOMENTUM · c3

- Counting: support 3 [livermore, minervini, oneil] · oppose 1 [detect-lens] · abstain 1 [elder-lens]
- Advisory: support [raschke] · oppose [] · abstain [lynch, seow, thorp, weis, wyckoff]
- Nominated by: minervini (c3)
- **detect-lens** OPPOSE c2: lens_positive=2 (resistance, sector) equals warns (coil, insti_money); leadership only ok. Lens tier low; day_vol 0.95.
- **livermore** SUPPORT c3: C5 new high in an aligned trend: from_52w_hi=0.0, ABOVE_STRUCTURE, structure 83.2, mp STRONG/ACCELERATING, rank 18. day_vol 0.95, no expansion yet; Financials Fading.
- **minervini** SUPPORT c3: Stage 2 new high: entry=620.42 > ma50=577.83 > ma100=550.35 > ma200=533.51, rs_rank_pct=79.19, mp=90.0. day_vol=0.95, no expansion yet (C6).
- **oneil** SUPPORT c2: L pass: LEADER, rank=18, structure=83.2, pct_from_pivot=3.19 in zone. C16 not met: day_vol=0.95, no expansion yet. Sector Financials Fading, lens.coil=warn. Buy only on volume.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=83.2 ABOVE_STRUCTURE, mp_state=STRONG, mp_accel_state=ACCELERATING, div_state=BULLISH, day_vol=0.95. sma_distance_pct=7.37 weight; act on first pullback to ma_20.

### HNGE — ADVANCE · PULLBACK · c3

- Counting: support 4 [detect-lens, elder-lens, livermore, minervini] · oppose 3 [oneil, raschke, thorp] · abstain 4 [lynch, seow, weis, wyckoff]
- Nominated by: elder-lens (c3)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong), insti_money=warn only. day_vol 1.99, ext_atr20 1.85. Trend filter: ma50 94.09>ma100 85.11>ma200 64.44. conv=2.
- **elder-lens** SUPPORT c3: Permission event on the last bar: elder_5d=[10, 7, 5, 6, 10] (6->10), elder=10.0, CORRECTION_REENTRY, mp_state=BUILDING, mp=70.0. Pullback ending inside a reentry (C4/C6). Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** SUPPORT c3: C5/C16 new high on heavy volume: from_52w_hi=0.0, day_vol 1.99, ABOVE_STRUCTURE, aligned stack, Healthcare Building. C5: never wait for a lower price. Part of the Healthcare call.
- **minervini** SUPPORT c3: Stage 2 new high: entry=107.51 > ma50=94.09 > ma100=85.11 > ma200=64.44, rs_rank_pct=99.51, day_vol=1.99, flow=97.4. sma_dist=14.27 extended; rs IN-LINE (C3,C11).
- **oneil** OPPOSE c2: R2: rs_leadership=IN-LINE, rs_down_day_20d=0.05. Near climax: entry=107.51 vs ma_200=64.44, sma_distance_pct=14.27 (C24 watch). day_vol=1.99 is real demand, but L fails.
- **raschke** OPPOSE c2: Pullback lane but not pulled back: sma_distance_pct=14.27 on day_vol=1.99 is a range-expansion bar, mp_accel_state=DECELERATING. C19 reads that as climax risk, not entry; no retracement exists yet.
- **thorp** OPPOSE c2: edge=none measured in packet; structure/composites are a shape, not a mispricing (C11); vol_measure=atr_pct 4.12% (atr 4.43/entry 107.51; rank 49/54, q4) q4 on day_vol 1.99, 14.27% over SMA: the band to survive is wide (C3/C4).

### CNK — ADVANCE · MOMENTUM · c3

- Counting: support 4 [detect-lens, livermore, minervini, oneil] · oppose 0 [] · abstain 1 [elder-lens]
- Advisory: support [raschke] · oppose [] · abstain [lynch, seow, thorp, weis, wyckoff]
- Nominated by: minervini (c3)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong), insti_money=warn only; day_vol 1.46. Trend filter: ma50 36.56>ma100 34.6>ma200 30.65. run_10d 13.8% is a weight (R14). conv=2.
- **livermore** SUPPORT c3: C5 new high: from_52w_hi=0.0, ABOVE_STRUCTURE, structure 76.8, mp BUILDING/ACCELERATING, day_vol 1.46, LEADER. Sector Fading, no second name.
- **minervini** SUPPORT c4: Stage 2 new high: entry=40.15 > ma50=36.56 > ma100=34.6 > ma200=30.65, rs_rank_pct=89.11, LEADER downday=1.43, day_vol=1.46 expansion, SUSTAINED (C3,C6,C11).
- **oneil** SUPPORT c4: Textbook in room: LEADER rs_down_day_20d=1.43, structure=76.8, pct_from_pivot=2.76 in buy zone, day_vol=1.46 clears 1.40 (C16), lens.leadership=strong, resistance=strong. Eight-week rule watch if it vaults.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=76.8 ABOVE_STRUCTURE, mp_state=BUILDING, mp_accel_state=ACCELERATING, elder_pattern=SUSTAINED, day_vol=1.46. sma_distance_pct=9.82 is a weight; first pullback to ma_20.

### A — ADVANCE · PULLBACK · c3

- Counting: support 7 [detect-lens, minervini, oneil, raschke, seow, weis, wyckoff] · oppose 1 [lynch] · abstain 3 [elder-lens, livermore, thorp]
- Nominated by: weis (c3)
- **detect-lens** SUPPORT c3: lens_positive=4 (leadership, coil, resistance, sector strong); only insti_money warn. ext_atr20 0.38 = coiled, not stretched. Trend filter: ma50 159.86>ma100 147.23>ma200 134.85. conv=ceil(4/1.5)=3. mp FADING not decay (R13).
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT stalwart: rev +7%/-5%/0%, EPS +3%/+5%/+1%, PE=34.0 -> PEG >10 (C8 red flag). Clean balance sheet (D/E=0.54) but no growth to justify the multiple.
- **minervini** SUPPORT c3: Stage 2 base near highs: entry=173.01 > ma50=159.86 > ma100=147.23 > ma200=134.85, from_52w_hi=-1.45, rs_rank_pct=89.84; RANGE, coil strong, ext_atr20=0.38 tight (C4).
- **oneil** SUPPORT c2: Base forming: LEADER, structure=82.1 RANGE, lens.coil=strong, ma_50=159.86 over ma_200=134.85. Not yet broken out; day_vol=0.83. Buy only the pivot breakout on volume (C16).
- **raschke** SUPPORT c2: setup=BREAKOUT from contraction (C12 approx): structure=82.1, structure_shift=RANGE, lens.coil=strong, energy=84.0, day_vol=0.83 quiet. mp_state=FADING is not a reason (R13); mp_accel_state=DECELERATING and elder_pattern=INTERRUPTED cap at 2.
- **seow** SUPPORT c3: Closest to my C3 dip: entry=173.01 just 1.0% over ma_20=171.24 (ext_atr20=0.38), tide up ret_63d=29.63, from_52w_hi=-1.45% (dip follows a recent high), run_10d=2.17 measured not parabolic. C6 passes: rs_spy_20d=4.0. CCI and 40MA legs unverifiable - capped at 3.
- **weis** SUPPORT c3: W21 hinge in an uptrend: inside_bar=True, was_squeezed=True on light day_vol=0.83; W23 passes ma20=171.24>ma50=159.86>ma200=134.85; ext_atr20 0.38 not stretched. mp FADING is not a reason (R13). Unresolved.
- **wyckoff** SUPPORT c3: Near the top of a range with measured contraction: structure_shift=RANGE, lens.coil=strong, energy=84.0, ext_atr20=0.38; quiet effort day_vol=0.83. Matches C14 absorption terrain (clue set unservable). structure=82.1 over ma_50=159.86 > ma_200=134.85.

### LLY — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 5 [detect-lens, elder-lens, livermore, minervini, oneil] · oppose 0 [] · abstain 0 []
- Advisory: support [lynch, raschke] · oppose [] · abstain [seow, thorp, weis, wyckoff]
- Nominated by: livermore (c4), minervini (c3)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong), only coil=warn, insti_money=ok. Trend filter: ma50 1182.47>ma100 1171.06>ma200 1081.75. day_vol 1.29. runner False. conv=ceil(3/1.5)=2.
- **elder-lens** SUPPORT c2: R8 only: elder_5d=[9, 10, 10, 7, 10], CORRECTION_REENTRY, mp_state=STRONG, mp=86.0. Dip to 7 reclaimed; no <=6 bar, so no C4 event. Buy the pullback into value (C10), not the print. Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** SUPPORT c4: C5 new high on above-normal participation: from_52w_hi=0.0, day_vol 1.29, ABOVE_STRUCTURE, structure 82.1, mp STRONG/ACCELERATING. Key Price pair with CAH (C14): two related leaders at highs together.
- **lynch** SUPPORT c3: r1_lynch=SUPPORT fast grower: rev +45% FY25, EPS +96%, NM=33.5%, PE=42.9 -> PEG~0.45 (C8 bargain band). Caveats: growth >30% is the C17 unsustainable flag, P/FCF=60.3. structure=82.1, rs_leadership=LEADER.
- **minervini** SUPPORT c3: Stage 2 new high: entry=1283.66 > ma50=1182.47 > ma100=1171.06 > ma200=1081.75, rs_rank_pct=90.21, day_vol=1.29 expansion; pct_from_pivot=5.65 is at the top of the chase band (C5).
- **oneil** SUPPORT c2: L pass: LEADER, rank=27, lens.leadership=strong, sector strong. structure=82.1. day_vol=1.29 just short of 1.40. LATE BUY: pct_from_pivot=5.65 (C17 warning band, no adds per C21). Weight, not veto (R14).
- **raschke** SUPPORT c2: setup=RETRACEMENT pending (C7 approx): structure=82.1 ABOVE_STRUCTURE, mp_state=STRONG, mp_accel_state=ACCELERATING, day_vol=1.29. sma_distance_pct=8.56 extension is a weight; Holy-Grail-style entry on first pullback to ma_20, buy stop over bar_high.

### CME — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 2 [elder-lens, oneil] · oppose 2 [livermore, minervini] · abstain 1 [detect-lens]
- Advisory: support [raschke, wyckoff] · oppose [] · abstain [lynch, seow, thorp, weis]
- Nominated by: oneil (c3), raschke (c3)
- **elder-lens** SUPPORT c2: C24 (unsourced) only: elder_5d=[10, 10, 10, 10, 10] SUSTAINED, mp_state=STRONG, mp=82.0. A flat high tail is summer (C20), not my trigger; sized at 2 as a desk read, not Elder's. Not red.
- **livermore** OPPOSE c2: C5 needs an established uptrend and a fresh new high. from_52w_hi=-9.54 and ma50 275.0 under ma200 278.92: a BOS inside a repaired range, not a trend-column new high. Sector Fading. Not my entry yet.
- **minervini** OPPOSE c3: Trend Template fails: ma50=275.0 < ma200=278.92 (criterion 4), rs_rank_pct=52.63 below the 70 floor (criterion 8), from_52w_hi=-9.54. Break inside a repairing range, not stage 2 (C2,C3).
- **oneil** SUPPORT c2: Was conv 3. BOS on day_vol=1.6 clears 1.40, pct_from_pivot=1.87, LEADER rank=16. But ma_50=275.0 under ma_200=278.92: base is a repair, not a prior uptrend (C12), and sector Fading tests Lone Ranger (C25).
- **raschke** SUPPORT c3: setup=TEST/breakout (C2/C20): structure_shift=BULLISH_BOS, structure=77.9, mp_state=STRONG, mp_accel_state=ACCELERATING, day_vol=1.6 participation on the break, sma_distance_pct=7.39 not climactic. Entry on a retest of the cleared pivot.
- **wyckoff** SUPPORT c2: structure_shift=BULLISH_BOS on day_vol=1.6: effort with reward out of a repaired range (ma_50=275.0 under ma_200=278.92). Range edge resolving up; lens.coil=-- so contraction unmeasured. Spring/back-up not detectable; I want the low-volume test of the break (C9).

### TRV — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 6 [detect-lens, livermore, lynch, minervini, oneil, raschke] · oppose 0 [] · abstain 5 [elder-lens, seow, thorp, weis, wyckoff]
- Nominated by: minervini (c4)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong) vs coil=warn, insti_money=warn. Trend filter: ma50 369.71>ma100 354.06>ma200 325.14. runner False. conv=2.
- **livermore** SUPPORT c3: C5 setup one step short: from_52w_hi=-0.38, ABOVE_STRUCTURE, structure 76.8, mp BUILDING/ACCELERATING, day_vol 1.34, LEADER. I act only on the close through the 52-week high, not before.
- **lynch** SUPPORT c4: r1_lynch=SUPPORT stalwart: PE=10.2, EPS +28% FY25/+68% FY24, NM=17.0%, D/E=0.34, P/FCF=7.7 (FCF yield ~13%, C13 terrific); PEG well <1 (C8). structure=76.8, rs_leadership=LEADER.
- **minervini** SUPPORT c4: Stage 2 within from_52w_hi=-0.38: entry=395.73 > ma50=369.71 > ma100=354.06 > ma200=325.14, rs_rank_pct=85.68, LEADER downday=0.89, day_vol=1.34, tight vcp_tightness_pct=67.8 (C3,C4).
- **oneil** SUPPORT c2: L pass: LEADER, rs_down_day_20d=0.89, lens.leadership=strong. structure=76.8, pct_from_pivot=3.06 in zone. day_vol=1.34 just short of 1.40. Sector Financials Fading weighs (C25). lens.coil=warn.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=76.8 ABOVE_STRUCTURE, mp_state=BUILDING, mp_accel_state=ACCELERATING, day_vol=1.34, elder_pattern=CORRECTION_REENTRY, div_state=BULLISH. sma_distance_pct=7.04: wait for the first pullback to ma_20.

### CCEP — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 5 [detect-lens, elder-lens, livermore, minervini, oneil] · oppose 0 [] · abstain 0 []
- Advisory: support [raschke] · oppose [] · abstain [lynch, seow, thorp, weis, wyckoff]
- Nominated by: minervini (c4)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong) vs coil=warn, insti_money=warn. Trend filter: ma50 105.28>ma100 103.84>ma200 99.69. ext_atr20 4.43 is a weight, not a veto (R14). conv=2.
- **elder-lens** SUPPORT c2: C24 (unsourced): elder_5d=[10, 10, 10, 10, 10] SUSTAINED, mp_state=STRONG, mp=84.0. Plateau is summer (C20), not Elder's buying season; filed as labelled desk read at 2.
- **livermore** SUPPORT c3: C5 new high: from_52w_hi=0.0, ABOVE_STRUCTURE, structure 80.0, mp STRONG/ACCELERATING, day_vol 1.38, rank 15. Staples peers KDP/CHD also at highs (C14). ext_atr20 4.43 is a weight (R14).
- **minervini** SUPPORT c3: Stage 2 new high: entry=113.41 > ma50=105.28 > ma100=103.84 > ma200=99.69, rs_rank_pct=75.52, day_vol=1.38, SUSTAINED. ext_atr20=4.43 is the room's most extended (weight, R14).
- **oneil** SUPPORT c2: L: LEADER, rank=15 #2 in XLP, lens.leadership=strong. structure=80.0, pct_from_pivot=3.78 in zone. day_vol=1.38 a hair short of 1.40. Sector Fading and lens.coil=warn weigh.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=80.0 ABOVE_STRUCTURE, mp_state=STRONG, mp_accel_state=ACCELERATING, elder_pattern=SUSTAINED, day_vol=1.38. sma_distance_pct=7.72 is a weight; buy stop over bar_high only after a pullback to ma_20.

### DRH — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 3 [elder-lens, livermore, minervini] · oppose 2 [detect-lens, oneil] · abstain 0 []
- Advisory: support [] · oppose [] · abstain [lynch, raschke, seow, thorp, weis, wyckoff]
- Nominated by: livermore (c4)
- **detect-lens** OPPOSE c2: lens_positive=2 (leadership, resistance) equals lens_warnings (coil, insti_money); div BEARISH/1; day_vol 0.76 on run_10d 11.39%. Lens does not rank this into a top tier.
- **elder-lens** SUPPORT c2: C24 (unsourced): elder_5d=[7, 10, 10, 10, 10], mp_state=STRONG, mp=90.0. No <=6 bar, no C4 event; plateau held four bars. Labelled desk read; I buy a pullback only.
- **livermore** SUPPORT c3: C5 new high: from_52w_hi=0.0, structure 84.2, mp STRONG/ACCELERATING, rank 19. But day_vol 0.76 into the high and div BEARISH/1: same lodging exposure as PEB, not additive.
- **minervini** SUPPORT c2: Stage 2 new high: entry=13.79 > ma50=12.51 > ma100=12.37 > ma200=11.12, rs_rank_pct=86.78, mp=90.0. But day_vol=0.76 (no C6 expansion) and div BEARISH/1.
- **oneil** OPPOSE c2: C25 sell test on entry: new-high run on day_vol=0.76 is a high on lower volume, buying has stopped; div_state=BEARISH. #2 lodging by rank=19 so L passes, but distribution shows before price. Weight, not extension.

### ADP — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 4 [elder-lens, livermore, minervini, oneil] · oppose 1 [detect-lens] · abstain 0 []
- Advisory: support [raschke] · oppose [lynch] · abstain [seow, thorp, weis, wyckoff]
- Nominated by: minervini (c4)
- **detect-lens** OPPOSE c2: lens_positive=1 (resistance strong) vs coil=warn, insti_money=warn; leadership only ok. Lens does not support the read.
- **elder-lens** SUPPORT c2: R8 only: elder_5d=[10, 10, 10, 7, 10], CORRECTION_REENTRY, mp_state=STRONG, mp=78.0. Dip to 7 reclaimed; no red lifted, so weaker than a C4 transition. Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** SUPPORT c3: Textbook C5: ma20 270.32 dipped under ma50 273.56 (normal reaction), now from_52w_hi=0.0 with mp STRONG/ACCELERATING, day_vol 1.37, ABOVE_STRUCTURE. Industrials Recovering, not yet a leading group.
- **lynch** OPPOSE c2: r1_lynch=CONTRADICT stalwart: rev +7%/yr x3, EPS +9-11%, NM=20.1%, PE=26.7 -> PEG~2.7>2 (C8); yield-adj (10+2.3)/26.7=0.46 poor (C9). Quality fine, price full. sma_distance_pct=7.01.
- **minervini** SUPPORT c3: Stage 2 new high: entry=292.75 > ma50=273.56 > ma100=257.59 > ma200=238.99, rs_rank_pct=90.58, day_vol=1.37, flow=92.1. pct_from_pivot=5.11 past the chase line (C5).
- **oneil** SUPPORT c2: L pass: LEADER, rank=22, rs_down_day_20d=0.73. structure=80.0. day_vol=1.37 just short of 1.40. LATE: pct_from_pivot=5.11 (C17 warning, no adds). Sector Recovering, lens.coil=warn.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=80.0 ABOVE_STRUCTURE, mp_state=STRONG, mp_accel_state=ACCELERATING, day_vol=1.37, elder_pattern=CORRECTION_REENTRY, div_state=BULLISH. sma_distance_pct=7.01 weight; first pullback to ma_20 is the entry.

### APLE — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 3 [elder-lens, livermore, minervini] · oppose 1 [oneil] · abstain 1 [detect-lens]
- Advisory: support [] · oppose [] · abstain [lynch, raschke, seow, thorp, weis, wyckoff]
- Nominated by: livermore (c4)
- **elder-lens** SUPPORT c2: Ambiguous bar lifted three bars ago: elder_5d=[6, 9, 10, 10, 10], ACCELERATION, mp_state=STRONG, mp=84.0. 6->9 is my permission proxy (C3/C4) but aged into a plateau; pullback only (C6).
- **livermore** SUPPORT c2: C5 new high: from_52w_hi=0.0, mp STRONG/ACCELERATING, day_vol 1.4. Fourth lodging name; ma50 16.12 under ma100 16.24 shows the intermediate column only just repaired. Same exposure as PEB.
- **minervini** SUPPORT c2: New high, rs_rank_pct=88.0, day_vol=1.4, entry=17.82 > ma200=14.41, but ma50=16.12 < ma100=16.24: criterion 4 in doubt; sma_dist=10.53 (C3).
- **oneil** OPPOSE c2: C9: rank=28 is the #4 lodging name behind PEB/DRH/PK, the sympathy competitor I am told not to buy. day_vol=1.4 passes C16 and LEADER, but ma_50=16.12 under ma_100=16.24 weakens base.

### SHO — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 3 [elder-lens, livermore, minervini] · oppose 2 [detect-lens, oneil] · abstain 0 []
- Advisory: support [] · oppose [lynch] · abstain [raschke, seow, thorp, weis, wyckoff]
- Nominated by: livermore (c4)
- **detect-lens** OPPOSE c2: lens_positive=2 (leadership, resistance) equals warns (coil, insti_money); ma50 11.21 below ma100 11.36. Lens tier low.
- **elder-lens** SUPPORT c2: elder_5d=[6, 10, 10, 10, 10]: 6->10 permission proxy four bars back, ACCELERATION, mp_state=STRONG, mp=90.0. Aged event now a plateau; buy the pullback into value (C10), not the print.
- **livermore** SUPPORT c2: C5 new high: from_52w_hi=0.0, mp STRONG/ACCELERATING, day_vol 1.6. Fifth lodging name, ma50 11.21 under ma100 11.36. Duplicate of the PEB call.
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT cyclical: EPS -70% FY25, -85% FY24, PE=50.3, GM=2.4%, NM=5.3%. Two years of falling earnings at a 50x multiple (C17 cyclical). sma_distance_pct=10.6.
- **minervini** SUPPORT c2: New high, rs_rank_pct=83.72, day_vol=1.6, entry=12.4 > ma200=10.42, but ma50=11.21 < ma100=11.36: criterion 4 in doubt; sma_dist=10.6 (C3).
- **oneil** OPPOSE c2: C9: rank=34 is the #5 lodging name, sympathy not leadership. day_vol=1.6 passes C16 and LEADER, but ma_50=11.21 under ma_100=11.36, lens.coil=warn. Buy the first man, not the fifth.

### MET — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 5 [elder-lens, livermore, minervini, raschke, weis] · oppose 1 [oneil] · abstain 5 [detect-lens, lynch, seow, thorp, wyckoff]
- Nominated by: elder-lens (c3)
- **elder-lens** SUPPORT c3: Permission event on the last bar: elder_5d=[7, 7, 9, 6, 9] (6->9), elder=9.0, CORRECTION_REENTRY, mp_state=BUILDING, mp=68.0. Pullback ending inside a reentry (C4/C6). Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** SUPPORT c2: C5 new high: from_52w_hi=0.0, ABOVE_STRUCTURE, structure 78.9, mp BUILDING/ACCELERATING. Thin: day_vol 0.66 and Financials Fading. Small.
- **minervini** SUPPORT c2: Template passes: entry=101.18 > ma50=96.99 > ma100=93.57 > ma200=84.84, from_52w_hi=0.0, rs_rank_pct=85.07. day_vol=0.66 no volume; buy only the breakout (C5,C6).
- **oneil** OPPOSE c2: C25: at the high on day_vol=0.66, a high on lower volume. rank=69 is not a group leader in Financials; lens mostly '--' so no base read beyond structure=78.9. Not a buy under my method.
- **raschke** SUPPORT c3: setup=RETRACEMENT (C2): structure=78.9 ABOVE_STRUCTURE, sma_distance_pct=4.32 close to the average, mp_state=BUILDING, mp_accel_state=ACCELERATING, elder_pattern=CORRECTION_REENTRY, div_state=BULLISH. Buy stop over bar_high; day_vol=0.66 quiet.
- **weis** SUPPORT c2: W23 passes: ma20=97.75>ma50=96.99>ma200=84.84, at high (from_52w_hi 0.0%). Dry effort day_vol=0.66 with elder dip 6->9: contraction/dry-up read only (W21), NOT absorption (R11 not served). Proxy-grade: small bet.

### ABBV — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 4 [detect-lens, elder-lens, livermore, minervini] · oppose 1 [oneil] · abstain 0 []
- Advisory: support [raschke] · oppose [lynch] · abstain [seow, thorp, weis, wyckoff]
- Nominated by: livermore (c3)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong) vs coil=warn, insti_money=warn. Trend filter: ma50 264.01>ma100 252.87>ma200 234.51. adx 33.94 mature trend. conv=2.
- **elder-lens** SUPPORT c2: R8 only: elder_5d=[10, 10, 10, 7, 10], CORRECTION_REENTRY, mp_state=STRONG, mp=86.0. Dip to 7 reclaimed, no red lifted; weaker than a C4 transition. Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** SUPPORT c3: C5 new high: from_52w_hi=0.0, ABOVE_STRUCTURE, structure 77.9, mp STRONG/ACCELERATING; XLV peers CAH/LLY at highs too (C14). Part of the one Healthcare call.
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT stalwart: EPS -1%/-12%/-59% over 3y, PE=81.4, negative equity (P/B=-86.2, D/E=-11.9). Earnings trend and balance sheet contradict a stalwart buy. sma_distance_pct=9.5.
- **minervini** SUPPORT c3: Stage 2 new high: entry=289.08 > ma50=264.01 > ma100=252.87 > ma200=234.51, rs_rank_pct=89.6, mp=86.0, LEADER downday=0.84; day_vol=1.06 modest.
- **oneil** OPPOSE c2: C9: rank=76 is #5 in XLV behind CAH/HNGE/LLY/CNC, the competitor moving in sympathy. day_vol=1.06 under 1.40. lens.coil=warn. Leadership belongs to the group's top names.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=77.9 ABOVE_STRUCTURE, mp_state=STRONG, mp_accel_state=ACCELERATING, elder_pattern=CORRECTION_REENTRY, day_vol=1.06. sma_distance_pct=9.5 weight; first pullback to ma_20.

### AVPT — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 2 [elder-lens, minervini] · oppose 1 [oneil] · abstain 2 [detect-lens, livermore]
- Advisory: support [lynch] · oppose [raschke] · abstain [seow, thorp, weis, wyckoff]
- Nominated by: elder-lens (c3)
- **elder-lens** SUPPORT c3: R8 dip-reclaim: CORRECTION_REENTRY, mp_state=STRONG, mp=93.0; elder_5d=[4, 9, 6, 10, 10] shows a <=6 bar giving way two bars ago, elder=10.0 now. Transition real, not today's bar.
- **lynch** SUPPORT c2: r1_lynch=SUPPORT fast grower: rev +27/22/17% (accelerating), NM=15.3%, D/E=0.04, PE=45.6 -> PEG~1.7 on rev. Early innings, clean balance sheet; valuation full, FCF yield ~3% (P/FCF=32). Sector Declining — Avoid.
- **minervini** SUPPORT c2: Template passes: entry=15.23 > ma50=13.69 > ma100=12.77 > ma200=11.76, from_52w_hi=0.0, rs_rank_pct=92.53. Weights: RANGE, div BEARISH/2, flow=52.6, sector Declining.
- **oneil** OPPOSE c3: R3: structure_shift=RANGE, no completed base and no pivot. R9 Lone Ranger: Technology Declining — Avoid, lens.sector=warn. div_state=BEARISH, div_bear_count=2. day_vol=0.89.
- **raschke** OPPOSE c2: No setup type fits (C2): structure_shift=RANGE so no test or break, sma_distance_pct=11.28 inside the range, and the bearish_divergence caution fires (div_state=BEARISH, div_bear_count=2). Extension is a weight only; the divergence plus no setup is the basis.

### ROKU — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 3 [detect-lens, elder-lens, minervini] · oppose 0 [] · abstain 2 [livermore, oneil]
- Advisory: support [raschke, weis, wyckoff] · oppose [] · abstain [lynch, seow, thorp]
- Nominated by: wyckoff (c3)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, coil, resistance strong), zero warns; coil strong and run_10d 3.62% = coiled, not extended. Trend filter: ma50 154.89>ma100 146.66>ma200 125.88. runner False. conv=2.
- **elder-lens** SUPPORT c2: elder_5d=[3, 8, 8, 9, 9]: ambiguous 3 gave way four bars back, ACCELERATION, mp_state=BUILDING, mp=38.0. Aged C4 proxy, still rising; mp low. Pullback only (C6). Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **minervini** SUPPORT c3: Stage 2 base near highs: entry=157.57 > ma50=154.89 > ma100=146.66 > ma200=125.88, from_52w_hi=-1.37, rs_rank_pct=88.62, RANGE with coil strong, energy=84.9: a contraction to break (C4).
- **raschke** SUPPORT c3: setup=BREAKOUT from contraction (C12/C13 approx, bar_range_history NOT_SERVED): structure_shift=RANGE, sma_distance_pct=1.73, lens.coil=strong, energy=84.9, day_vol=0.95 quiet, mp_accel_state=ACCELERATING, div_state=BULLISH. Straddle the range; buy the upside break.
- **weis** SUPPORT c2: W21 hinge read: RANGE on ma20=153.27/ma50=154.89 (sma_dist 1.73%), quiet day_vol=0.95, from_52w_hi -1.37%; preceding read up (ma100=146.66>ma200=125.88, elder 3->9). inside_bar not served here: proxy, small bet. Advisory lane.
- **wyckoff** SUPPORT c3: Range-edge terrain: structure_shift=RANGE, lens.coil=strong, energy=84.9 (measured contraction); sma_distance_pct=1.73 sitting on ma_20=153.27/ma_50=154.89. Quiet effort day_vol=0.95, mp_accel_state=ACCELERATING. Wrong below ma_20=153.27 (own level). Spring not detectable.

### KMI — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 2 [raschke, weis] · oppose 3 [detect-lens, minervini, oneil] · abstain 6 [elder-lens, livermore, lynch, seow, thorp, wyckoff]
- Nominated by: weis (c3)
- **detect-lens** OPPOSE c2: lens_positive=2 (resistance, sector) equals warns (coil, insti_money); flat MAs ma50 31.77 ma100 31.84 ma200 31.81: no trend for the lens to ride.
- **minervini** OPPOSE c3: No trend: ma50=31.77 < ma100=31.84 vs ma200=31.81 flat (criteria 3,4 unproven), rs_rank_pct=58.02 below 70 (C3).
- **oneil** OPPOSE c2: No base: ma_50=31.77, ma_100=31.84, ma_200=31.81 flat, no prior uptrend (C12). day_vol=0.96, no breakout. LEADER tag alone is not CAN SLIM.
- **raschke** SUPPORT c2: setup=RETRACEMENT (C2): structure=74.7 ABOVE_STRUCTURE, sma_distance_pct=5.68, div_state=BULLISH, day_vol=0.96. mp_accel_state=DECELERATING keeps it at 2; buy stop over bar_high after a hold of ma_20.
- **weis** SUPPORT c2: W21 hinge: inside_bar=True on day_vol=0.96 above ma20=32.01, BULLISH structure, from_52w_hi -2.16%. Unresolved. W23 only half-passes: ma50=31.77/ma100=31.84/ma200=31.81 are flat.

### CRM — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 5 [lynch, minervini, raschke, weis, wyckoff] · oppose 3 [livermore, oneil, thorp] · abstain 3 [detect-lens, elder-lens, seow]
- Nominated by: wyckoff (c3)
- **livermore** OPPOSE c2: C5: from_52w_hi=-8.94, structure_shift=RANGE, Technology Declining — Avoid. Not at a new high, not in a leading group (C12).
- **lynch** SUPPORT c3: r1_lynch=SUPPORT stalwart: rev +10/9/11%, EPS +22% FY26, NM=22.0%, PE=22.0 -> PEG~1.0; P/FCF=13.2 (FCF yield ~7.6%). D/E=1.09 watch. Reasonable price for steady growth. Sector Declining — Avoid.
- **minervini** SUPPORT c2: Template mostly passes: entry=242.43 > ma50=232.01 > ma100=202.3 > ma200=198.88, from_52w_hi=-8.94, rs_rank_pct=84.15; RANGE with coil strong. Sector Declining; buy only the pivot break (C4,C5).
- **oneil** OPPOSE c3: R9: Technology Declining — Avoid, lens.sector=warn. lens.resistance=warn is overhead supply. structure_shift=RANGE, no completed base. day_vol=0.92.
- **raschke** SUPPORT c2: setup=BREAKOUT from contraction (C12 approx): structure_shift=RANGE, structure=68.4, lens.coil=strong, energy=72.3, sma_distance_pct=4.49, mp_accel_state=ACCELERATING, day_vol=0.92 quiet. Lens resistance=warn caps it at 2.
- **thorp** OPPOSE c2: edge=none measured in packet; structure/composites are a shape, not a mispricing (C11); vol_measure=atr_pct 3.65% (atr 8.84/entry 242.43; rank 46/54, q4) q4: ranks below calmer pullbacks (C6/R1). RANGE, mp 33.0.
- **weis** SUPPORT c2: W21 contraction in an uptrend: RANGE, ma20=233.99>ma50=232.01>ma100=202.3>ma200=198.88, day_vol=0.92, ext_atr20 0.95, coil strong. inside_bar not served here: proxy read, small bet.
- **wyckoff** SUPPORT c3: Range with measured contraction: structure_shift=RANGE, lens.coil=strong, energy=72.3; price held above ma_20=233.99 and ma_50=232.01 (sma_distance_pct=4.49) = springboard terrain (Type 3 shape, C8, not detectable). Overhead supply lens.resistance=warn. Enter on a low-volume test (C23 B-grade path).

### BRZE — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 2 [elder-lens, livermore] · oppose 2 [detect-lens, oneil] · abstain 1 [minervini]
- Advisory: support [] · oppose [lynch, raschke, seow, thorp, wyckoff] · abstain [weis]
- Nominated by: elder-lens (c2)
- **detect-lens** OPPOSE c2: lens_positive=2 (leadership, resistance) vs 3 warns (coil, insti_money, sector); day_vol 32.65 reads as a single event, runner_conviction 3 untagged.
- **elder-lens** SUPPORT c2: R8 only: CORRECTION_REENTRY, mp_state=STRONG, mp=93.0; elder_5d=[7, 10, 7, 7, 10] shallow dip to 7 and reclaim, no red lifted, no C4 event. Pullback timing (C6) only: I do not buy the spike.
- **livermore** SUPPORT c2: C16: a brand-new high on news-scale volume (day_vol 32.65, from_52w_hi=0.0) is a sound buy in my book. But sma_dist 59.65 and a Declining group: tiny, guarded by the danger signal. I do not act on the reason for the move (C11).
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT fast grower: unprofitable SaaS, rev +33->26->24% decelerating (C17 sell signal), NM=-13.6%, PE=-44.2, P/FCF=61.9 (FCF yield ~1.6%, C13 fail). No earnings to compound. sma_distance_pct=59.65.
- **oneil** OPPOSE c4: C24 climax: entry=45.57 vs ma_200=23.98, sma_distance_pct=59.65, day_vol=32.65 heaviest volume day. A name to sell into, not buy. R9: Technology Declining — Avoid. Extension alone is a weight (R14); the climax set is not.
- **raschke** OPPOSE c3: Climax, not setup: day_vol=32.65 range-expansion bar with sma_distance_pct=59.65. C19 says a parabolic or range-expansion bar marks a climax; I decline to call a visual climax entry (C10). Extension alone is a weight (R14); the climax bar is the basis.
- **seow** OPPOSE c3: C4/R7: a dip after a parabolic advance is disqualified however clean it looks - run_10d=73.01 is a near-vertical run, entry=45.57 is 63% over ma_20=27.9 (ext_atr20=7.04). Not an extension call (R14 weight), a parabolic disqualifier. Advisory, momentum lane.
- **thorp** OPPOSE c3: edge=none measured in packet; structure/composites are a shape, not a mispricing (C11); vol_measure=atr_pct 5.51% (atr 2.51/entry 45.57; rank 53/54, q4) q4, day_vol 32.65 after run_10d 73.01%: a one-day event, not a priced edge; gap risk is the whole case (C4/C15).
- **wyckoff** OPPOSE c2: day_vol=32.65 at a new high with sma_distance_pct=59.65: a climax footprint (C17), far from any range edge. Net volume (FORCE) unmeasurable, so climax vs ignition cannot be split; the trade is not here. Advisory vote.

### AFL — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 2 [raschke, weis] · oppose 4 [livermore, minervini, oneil, seow] · abstain 5 [detect-lens, elder-lens, lynch, thorp, wyckoff]
- Nominated by: weis (c2)
- **livermore** OPPOSE c2: C5: from_52w_hi=-7.16, ma50 116.39 under ma100 118.55; a BOS inside a range, not a trend-column new high. Financials Fading.
- **minervini** OPPOSE c3: Trend Template fails: ma50=116.39 < ma100=118.55, rs_rank_pct=51.9 below 70, from_52w_hi=-7.16 (C3).
- **oneil** OPPOSE c2: No clean base: ma_50=116.39 under ma_100=118.55, lens.leadership=warn. BOS on day_vol=0.78, a C16 hard reject.
- **raschke** SUPPORT c2: setup=TEST (C2/C20): structure_shift=BULLISH_BOS, structure=63.2, sma_distance_pct=3.33 near the level, mp_accel_state=ACCELERATING, elder_pattern=CORRECTION_REENTRY. day_vol=0.78 light; buy only a pivot reclaim.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-2.68, from_52w_hi=-7.16%. Price 4.6% over ma_20=115.02 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **weis** SUPPORT c2: W6/W7 DEGRADED single-bar rejection: pin_bar_state=BULLISH_PIN, BULLISH_BOS, choch BULLISH, entry 120.27 above ma200=115.4. Stack ROLLING (ma50=116.39<ma100=118.55) caps it at a small bet.

### EW — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 3 [detect-lens, elder-lens, wyckoff] · oppose 4 [livermore, lynch, minervini, oneil] · abstain 4 [raschke, seow, thorp, weis]
- Nominated by: wyckoff (c2)
- **detect-lens** SUPPORT c2: lens_positive=3 (coil, insti_money, sector strong), leadership warn only. Coiled and quiet: day_vol 0.48, adx 11.96. ma50 88.29>ma200 85.16. premove 0/4: radar only. conv=2.
- **elder-lens** SUPPORT c2: elder_5d=[7, 8, 6, 9, 9]: a 6 gave way two bars ago, elder=9.0 held. mp_state=BUILDING, mp=18.0 is thin; pattern None. Real C4 proxy, low belief. Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** OPPOSE c3: C5: structure_shift=RANGE, sma_dist -0.01, mp 18.0, from_52w_hi=-7.24, day_vol 0.48. No trend, no high, no buying power.
- **lynch** OPPOSE c2: r1_lynch=CONTRADICT stalwart: rev +12%, EPS -74% FY25 after +202% one-off, PE=50.7 -> PEG >4 on rev (C8). D/E=0.07 clean. Multiple ahead of earnings.
- **minervini** OPPOSE c2: Template fails criterion 8: rs_rank_pct=65.97 below 70; entry=88.29 sits on ma50=88.29, mp=18.0, day_vol=0.48, rs IN-LINE (C3,C11).
- **oneil** OPPOSE c3: R2: rs_leadership=IN-LINE, rs_down_day_20d=-0.12. structure=44.2 RANGE, day_vol=0.48.
- **wyckoff** SUPPORT c2: Springboard-shaped terrain only: structure_shift=RANGE, lens.coil=strong, energy=71.4; entry=88.29 on ma_50=88.29 (sma_distance_pct=-0.01), above ma_200=85.16, dry effort day_vol=0.48. mp_accel_state=DECELERATING tempers it. No spring type callable.

### KDP — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 4 [detect-lens, livermore, minervini, oneil] · oppose 1 [elder-lens] · abstain 0 []
- Advisory: support [raschke] · oppose [lynch] · abstain [seow, thorp, weis, wyckoff]
- Nominated by: oneil (c2)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong) vs coil=warn, insti_money=warn; day_vol 1.65. Trend filter: ma50 31.74>ma100 31.42>ma200 29.7. conv=2.
- **elder-lens** OPPOSE c2: Green going away on the last bar: elder_5d=[10, 10, 10, 10, 7]. C4: green vanishing in an upswing marks the swing's approaching end, a profit-taking signal, not an entry. mp_state=STRONG, mp=80.0 noted.
- **livermore** SUPPORT c3: C5 new high: from_52w_hi=0.0, ABOVE_STRUCTURE, structure 80.0, mp STRONG/ACCELERATING, day_vol 1.65, rank 9. Staples peers CCEP/CHD at highs (C14).
- **lynch** OPPOSE c2: r1_lynch=CONTRADICT stalwart: rev +8/4/5%, NM=7.1%, PE=34.8 -> PEG >2 (C8), D/E=1.37; yield-adj PEG ~0.5 poor (C9). Slow business at a growth multiple.
- **minervini** SUPPORT c2: Stage 2 new high: entry=34.63 > ma50=31.74 > ma100=31.42 > ma200=29.7, rs_rank_pct=85.31, day_vol=1.65, flow=98.7. pct_from_pivot=7.75 is a chase (C5): wait for a fresh base.
- **oneil** SUPPORT c2: Unchanged conv 2. L: LEADER, rank=9 #1 in XLP. structure=80.0, day_vol=1.65 clears 1.40 (C16). LATE BUY: pct_from_pivot=7.75 over pivot_high=32.14, C17 warning band, no adds. Sector Fading.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=80.0 ABOVE_STRUCTURE, mp_state=STRONG, mp_accel_state=ACCELERATING, div_state=BULLISH, day_vol=1.65. sma_distance_pct=9.11 is a weight; first pullback to ma_20.

### CHD — HOLD-FOR-CONDITIONS · MOMENTUM · c2

- Counting: support 3 [detect-lens, elder-lens, livermore] · oppose 2 [minervini, oneil] · abstain 0 []
- Advisory: support [raschke] · oppose [lynch] · abstain [seow, thorp, weis, wyckoff]
- Nominated by: elder-lens (c2)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong) vs coil=warn, insti_money=warn. ma50 98.36>ma100 98.09>ma200 96.94 (flat but passing). ext_atr20 4.21 is a weight (R14). conv=2.
- **elder-lens** SUPPORT c2: R8 only: CORRECTION_REENTRY, mp_state=STRONG, mp=94.0; elder_5d=[10, 10, 10, 7, 10] shallow dip to 7 and reclaim, no red lifted, no C4 event. Pullback timing per C6.
- **livermore** SUPPORT c2: C5 new high: from_52w_hi=0.0, mp STRONG/ACCELERATING, structure 84.2. But ma50 98.36, ma100 98.09, ma200 96.94 nearly flat: the uptrend column is young. Small.
- **lynch** OPPOSE c2: r1_lynch=CONTRADICT stalwart: rev +2/4/9% slowing, EPS +27/-23/+82 erratic, PE=34.0, DY=1.15%; yield-adj PEG <1 (C9). Stalwart priced like a grower.
- **minervini** OPPOSE c2: Template criterion 8 fails: rs_rank_pct=69.77 under 70; ma50=98.36 / ma100=98.09 / ma200=96.94 nearly flat, ext_atr20=4.21 (C3,C5).
- **oneil** OPPOSE c2: No prior uptrend under the base: ma_50=98.36 vs ma_200=96.94 flat (C12). day_vol=1.03 under 1.40. #3 XLP by rank=21 but sector Fading, lens.coil=warn.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=84.2 ABOVE_STRUCTURE, mp_state=STRONG, mp_accel_state=ACCELERATING, elder_pattern=CORRECTION_REENTRY, day_vol=1.03. sma_distance_pct=7.73 weight; first pullback to ma_20.

### KO — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 5 [detect-lens, livermore, minervini, raschke, weis] · oppose 3 [elder-lens, lynch, oneil] · abstain 3 [seow, thorp, wyckoff]
- Nominated by: weis (c2)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong), coil warn only. Trend filter: ma50 88.7>ma100 85.7>ma200 81.2. conv=2.
- **elder-lens** OPPOSE c2: Green going away on the last bar: elder_5d=[10, 10, 10, 10, 7]. C4: the swing's approaching end, a profit-taking bar, not an entry bar. mp_state=BUILDING, mp=72.0.
- **livermore** SUPPORT c2: C5 one step short: from_52w_hi=-0.44, ABOVE_STRUCTURE, aligned stack, mp BUILDING/ACCELERATING. Staples group at highs (C14). I act only on the close through the 52-week high.
- **lynch** OPPOSE c2: r1_lynch=CONTRADICT stalwart: rev +2/3/6%, EPS 3y avg ~12%, PE=28.1 -> PEG~2.3>2 (C8); yield-adj ~0.5 (C9 poor). Great business, full price: a C20 rotation question, not an entry.
- **minervini** SUPPORT c3: Stage 2 near high: entry=93.49 > ma50=88.7 > ma100=85.7 > ma200=81.2, from_52w_hi=-0.44, rs_rank_pct=82.13, LEADER downday=0.95. day_vol=0.97; buy the new-high break (C3,C5).
- **oneil** OPPOSE c2: C9: rank=80 is #5 in XLP, sympathy not leadership. day_vol=0.97 under 1.40, lens.coil=warn.
- **raschke** SUPPORT c2: setup=RETRACEMENT pending: structure=74.7 ABOVE_STRUCTURE, sma_distance_pct=5.4, mp_state=BUILDING, mp_accel_state=ACCELERATING, div_state=BULLISH, day_vol=0.97. Buy stop over bar_high after a pullback to ma_20.
- **weis** SUPPORT c2: W21 hinge near highs: inside_bar=True, day_vol=0.97, ALIGNED, ma20=88.73>ma200=81.2, from_52w_hi -0.44%. ext_atr20 3.33 after run_10d 8.49% caps it at a small bet.

### OXY — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 2 [detect-lens, raschke] · oppose 4 [elder-lens, livermore, minervini, oneil] · abstain 5 [lynch, seow, thorp, weis, wyckoff]
- Nominated by: weis (c2)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, resistance, sector strong), coil warn only; structure_shift RANGE. Trend filter: ma50 59.54>ma100 57.02>ma200 55.24. conv=2.
- **elder-lens** OPPOSE c2: Green going away on the last bar: elder_5d=[10, 7, 10, 10, 7]. Second fade in five bars; C4 reads it as a swing ending. mp_state=BUILDING, mp=68.0.
- **livermore** OPPOSE c2: C5: from_52w_hi=-5.01, structure_shift=RANGE, Energy Fading. Inside a range, not a new high; I never buy the pullback.
- **minervini** OPPOSE c2: Template criterion 8 fails: rs_rank_pct=67.2 under 70; RANGE, from_52w_hi=-5.01 (C3,C11).
- **oneil** OPPOSE c2: R3: structure_shift=RANGE, no completed base. day_vol=0.88. Energy Fading.
- **raschke** SUPPORT c2: setup=RETRACEMENT (C2): structure=77.9, structure_shift=RANGE inside the swing, sma_distance_pct=5.67, mp_state=BUILDING, mp_accel_state=ACCELERATING, day_vol=0.88. Buy stop over bar_high on a hold of ma_20.

### HOMB — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 4 [detect-lens, elder-lens, lynch, wyckoff] · oppose 4 [livermore, minervini, oneil, seow] · abstain 3 [raschke, thorp, weis]
- Nominated by: wyckoff (c2)
- **detect-lens** SUPPORT c2: lens_positive=2 (coil, sector strong), zero warns, all six lenses served; day_vol 1.3. ma50 29.52>ma200 28.47. Coiled, quiet; no tag. conv=ceil(2/1.5)=2.
- **elder-lens** SUPPORT c2: elder_5d=[5, 7, 9, 9, 9]: a 5 gave way four bars back, ACCELERATION, mp_state=BUILDING, mp=53.0. Aged C4 proxy, held at 9. Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** OPPOSE c3: C5: structure_shift=RANGE, sma_dist -0.46, from_52w_hi=-6.64, rs IN-LINE. Neither trend nor high.
- **lynch** SUPPORT c3: r1_lynch=SUPPORT stalwart: regional bank, PE=11.9, NM=32.4%, D/E=0.15, DY=2.93%, EPS +20/4/24%. Yield-adj PEG (16+2.9)/11.9~1.6 passes (C9). Rev -5% FY25 is the watch item. Tax-loss window (C23).
- **minervini** OPPOSE c3: Not stage 2: entry=29.39 < ma50=29.52, structure 46.3, rs IN-LINE, rs_rank_pct=64.01 (C2,C3).
- **oneil** OPPOSE c3: R2: IN-LINE. R3: structure=46.3 RANGE.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-3.29, from_52w_hi=-6.64%. Price 2.5% over ma_20=28.67 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **wyckoff** SUPPORT c2: Range-middle pullback with effort: structure_shift=RANGE, lens.coil=strong, energy=63.0; entry=29.39 between ma_20=28.67 and ma_50=29.52, above ma_200=28.47. day_vol=1.3 with mp_accel_state=ACCELERATING = effort meeting reward (C6). No spring object.

### ZION — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 4 [detect-lens, elder-lens, lynch, weis] · oppose 4 [livermore, minervini, oneil, seow] · abstain 3 [raschke, thorp, wyckoff]
- Nominated by: weis (c2)
- **detect-lens** SUPPORT c3: lens_positive=4 (leadership, coil, structure, sector strong) vs insti_money, resistance warn; BULLISH_BOS on day_vol 2.4. ma50 66.12>ma200 63.6 passes dual-MA. conv=ceil(4/1.5)=3.
- **elder-lens** SUPPORT c2: elder_5d=[2, 7, 7, 8, 9]: ambiguous 2 gave way four bars back and has risen every bar since (spring shape, C20). mp_state=BUILDING, mp=62.0. Aged event. Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** OPPOSE c3: C5/C16: entry 64.59 under ma50 66.12, sma_dist -2.32, from_52w_hi=-11.89. A bounce in a sold-off name, not a new high.
- **lynch** SUPPORT c3: r1_lynch=SUPPORT stalwart: regional bank, PE=7.9, P/FCF=4.6, NM=23.5%, EPS +23/14%, DY=2.83%. Yield-adj PEG ~2.6 fabulous (C9). sma_distance_pct=-2.32 in tax-loss window (C23 context). Funding (C15) unserved.
- **minervini** OPPOSE c3: Not stage 2: entry=64.59 < ma50=66.12 < ma100=67.23, rs_rank_pct=53.37, from_52w_hi=-11.89 (C2,C3).
- **oneil** OPPOSE c3: R2: IN-LINE. structure=36.8, entry=64.59 under ma_50=66.12. day_vol=2.4 bounce in a sold-off name, not a base breakout.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-7.82, from_52w_hi=-11.89%. Price 2.7% over ma_20=62.88 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **weis** SUPPORT c2: W21 hinge resolved up with effort: squeeze_breakout_state=BREAKOUT_UP, was_squeezed=True, volume confirmed, day_vol=2.4; choch BULLISH, BULLISH_BOS. Entry 64.59 under ma50=66.12 (ROLLING): small bet.

### ACA — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 7 [detect-lens, elder-lens, livermore, minervini, oneil, raschke, weis] · oppose 0 [] · abstain 4 [lynch, seow, thorp, wyckoff]
- Nominated by: raschke (c2)
- **detect-lens** SUPPORT c3: lens_positive=4 (leadership, insti_money, structure, resistance strong), zero warns; BULLISH_BOS. Trend filter: ma50 145.92>ma100 142.75>ma200 129.43. Exhaustion RISK flagged. conv=ceil(4/1.5)=3.
- **elder-lens** SUPPORT c2: elder_5d=[5, 5, 5, 8, 8]: three <=6 bars gave way two bars ago, ACCUMULATION_BASE, elder=8.0. mp_state=FADING (R13: not decay), mp=63.0. Real C4 proxy, low belief.
- **livermore** SUPPORT c2: C5 new high at the base: from_52w_hi=0.0, BULLISH_BOS, sma_dist 1.05, aligned stack. mp FADING/DECELERATING (R13: not decay) and day_vol 0.95; needs follow-through.
- **minervini** SUPPORT c2: Template passes: entry=147.45 > ma50=145.92 > ma100=142.75 > ma200=129.43, from_52w_hi=0.0, rs_rank_pct=83.84; BOS at sma_dist=1.05, tight. day_vol=0.95, flow=48.7 weak (C6).
- **oneil** SUPPORT c2: Tight base near highs: LEADER, BULLISH_BOS, structure=71.6, sma_distance_pct=1.05, lens 4 strong, 0 warns, ma_50=145.92 over ma_200=129.43. C16 not met: day_vol=0.95. Buy only on volume.
- **raschke** SUPPORT c2: setup=TEST at the base (C2/C20): structure_shift=BULLISH_BOS, sma_distance_pct=1.05 entry next to the level, atr_14d=0.47 contraction proxy, structure=71.6, elder_pattern=ACCUMULATION_BASE. mp_accel_state=DECELERATING caps at 2; FADING is not a reason (R13).
- **weis** SUPPORT c2: W21 contraction read: atr 0.47 narrow, run_10d 0.65%, at high (from_52w_hi 0.0%), ACCUMULATION_BASE; W23 passes ma20=146.75>ma50=145.92>ma200=129.43; BOS. Range proxy (W5), no inside_bar served.

### TTEK — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 2 [elder-lens, wyckoff] · oppose 4 [livermore, minervini, oneil, seow] · abstain 5 [detect-lens, lynch, raschke, thorp, weis]
- Nominated by: wyckoff (c2)
- **elder-lens** SUPPORT c2: elder_5d=[5, 9, 9, 10, 10]: a 5 gave way four bars back, ACCELERATION, mp_state=BUILDING, mp=25.0 thin. Aged C4 proxy. Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** OPPOSE c3: C5: from_52w_hi=-17.95, structure_shift=RANGE, sma_dist -0.73, rs IN-LINE. No high, no trend.
- **minervini** OPPOSE c3: Not stage 2: entry=34.96 < ma50=35.22, ma100=32.77 < ma200=33.01, from_52w_hi=-17.95, rs_spy_20d=-0.85 (C2,C3,C11).
- **oneil** OPPOSE c3: R2: IN-LINE, rs_spy_20d=-0.85. structure=43.2 RANGE.
- **seow** OPPOSE c2: C6/R8 odds gate fails: rs_spy_20d=-0.85, the name is lagging the index, and C6 says a laggard does not get a long at all regardless of set-up. Price 3.5% over ma_20=33.79. 40MA/CCI unverifiable.
- **wyckoff** SUPPORT c2: Coiled range: structure_shift=RANGE, lens.coil=strong, energy=64.7; entry=34.96 under ma_50=35.22, above ma_20=33.79 and ma_200=33.01. Quiet effort day_vol=0.76, mp_accel_state=ACCELERATING. structure=43.2 is soft; turning point unseen.

### MRK — HOLD-FOR-CONDITIONS · PULLBACK · c2

- Counting: support 3 [detect-lens, minervini, weis] · oppose 4 [livermore, lynch, oneil, seow] · abstain 4 [elder-lens, raschke, thorp, wyckoff]
- Nominated by: wyckoff (c2)
- **detect-lens** SUPPORT c2: lens_positive=3 (leadership, coil, sector strong), insti_money warn only; ext_atr20 0.75 not stretched. Trend filter: ma50 145.77>ma100 134.92>ma200 125.27. conv=2.
- **livermore** OPPOSE c2: C5: from_52w_hi=-5.21, structure_shift=RANGE, mp 23.0 DECELERATING. Uptrend intact but no new high to buy.
- **lynch** OPPOSE c2: r1_lynch=CONTRADICT stalwart: rev +1/7/1%, TTM PE=117.7, NM=4.8% (depressed earnings, cause unserved), P/FCF=22.8 (FCF yield ~4.4%<5%, C13). Price has outrun earnings.
- **minervini** SUPPORT c2: Template passes: entry=148.3 > ma50=145.77 > ma100=134.92 > ma200=125.27, from_52w_hi=-5.21, rs_rank_pct=85.8; RANGE, coil strong. mp=23.0 and rs_spy_20d=-1.17 are weights (C4).
- **oneil** OPPOSE c3: R2: IN-LINE, rs_spy_20d=-1.17. structure=46.3 RANGE.
- **seow** OPPOSE c2: C6/R8 odds gate fails: rs_spy_20d=-1.17, the name is lagging the index, and C6 says a laggard does not get a long at all regardless of set-up. Price 2.1% over ma_20=145.32. 40MA/CCI unverifiable.
- **weis** SUPPORT c2: Uptrend gate: ma50=145.77>ma100=134.92>ma200=125.27. elder_5d [6,6,7,1,9]: the 1->9 is a multi-day rejection of weakness, my only multi-day trace. Quiet ext_atr20 0.75, coil strong. Proxy grade, small bet.

### AEP — PASS · MOMENTUM · c3

- Counting: support 1 [elder-lens] · oppose 3 [livermore, minervini, oneil] · abstain 1 [detect-lens]
- Advisory: support [raschke] · oppose [seow, weis] · abstain [lynch, thorp, wyckoff]
- Nominated by: elder-lens (c4)
- **elder-lens** SUPPORT c3: Permission event on the last bar plus R8: elder_5d=[10, 7, 10, 6, 10] (6->10), CORRECTION_REENTRY, mp_state=STRONG, mp=86.0. Best transition read I hold (C4). Trend leg unverifiable on my menu (C9).
- **livermore** OPPOSE c3: C5 fails: no established uptrend. from_52w_hi=-8.27, ma50 122.73 < ma100 126.97 < ma200 127.57, day_vol 0.69. A BOS inside a downtrend is a rally, not a new high.
- **minervini** OPPOSE c4: Trend Template fails: ma50=122.73 < ma100=126.97 < ma200=127.57, entry=127.22 under ma200 (criteria 1,4), rs_rank_pct=38.19, from_52w_hi=-8.27. Not stage 2 (C2,C3).
- **oneil** OPPOSE c4: No base, no prior uptrend: ma_50=122.73 < ma_100=126.97 < ma_200=127.57 inverted (C12). BOS on day_vol=0.69, a C16 hard reject. Utilities Fading. A break inside a downtrend is repair, not leadership.
- **raschke** SUPPORT c2: setup=TEST (C2/C20): structure_shift=BULLISH_BOS, structure=71.6, sma_distance_pct=3.66 near the level, mp_state=STRONG, mp_accel_state=ACCELERATING. day_vol=0.69 light break keeps conviction at 2; buy only a retest that reclaims the pivot.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-4.4, from_52w_hi=-8.27%. Price 4.4% over ma_20=121.89 is a bounce inside a falling tide, not a pullback in an up-trend. (advisory, momentum lane) 40MA/CCI unverifiable.
- **weis** OPPOSE c3: W23/W10: stack inverted ma50=122.73<ma100=126.97<ma200=127.57, entry 127.22 under ma200. A BULLISH_BOS on day_vol=0.69 inside a downtrend is the bottom-picker case; W10 reads it as short evidence, never long.

### O — PASS · PULLBACK · c3

- Counting: support 1 [thorp] · oppose 8 [detect-lens, livermore, minervini, oneil, raschke, seow, weis, wyckoff] · abstain 2 [elder-lens, lynch]
- Nominated by: thorp (c3)
- **detect-lens** OPPOSE c3: lens_positive=2 (coil, insti_money) vs 3 warns (leadership, structure, resistance); BEARISH_CHOCH; dual-MA fails ma50 58.44<ma200 61.7.
- **livermore** OPPOSE c4: C5/C16: BEARISH_CHOCH, structure 36.8, entry 56.34 under ma200 61.7, from_52w_hi=-16.61. A falling stock bought for a low price is exactly what I never do.
- **minervini** OPPOSE c4: Stage 4: BEARISH_CHOCH, entry=56.34 < ma50=58.44 < ma100=60.62 < ma200=61.7, rs_rank_pct=22.64, from_52w_hi=-16.61. Buying weakness (C2,C11).
- **oneil** OPPOSE c4: R3 FAIL: structure=36.8 BEARISH_CHOCH, entry=56.34 under ma_200=61.7, ma_50=58.44 under ma_200. No base, no leadership; a sold-off name. I do not buy reclaims.
- **raschke** OPPOSE c2: No long setup (C2): structure_shift=BEARISH_CHOCH, structure=36.8, sma_distance_pct=-3.6. The up-structure failed; a Turtle Soup test needs a fresh extreme failure I cannot see (n_day_extreme substitute only).
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-13.36, from_52w_hi=-16.61%. Price 2.7% over ma_20=54.85 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **thorp** SUPPORT c3: cohort signal_hit_rate_20d=57.0 n=251 (~2.2 SE over coin-flip); vol_measure=atr_pct 1.60% (atr 0.9/entry 56.34; rank 6/54, q1) calmest of my cohort (C6). Mean-reversion inside BEARISH_CHOCH, structure 36.8. Gapped worst case 4.24% stated in R1 (C2/C4).
- **weis** OPPOSE c3: W10/W23: BEARISH_CHOCH, stack inverted ma50=58.44<ma200=61.7, entry 56.34 under both. The elder 6->9 reentry is a spring-shaped read in a downtrend: short evidence, never long.
- **wyckoff** OPPOSE c2: structure_shift=BEARISH_CHOCH, entry=56.34 under ma_50=58.44 and ma_200=61.7: the broken low is now a ceiling (C3). structure=36.8. Markdown, not a range edge. lens.coil=strong is contraction inside a falling structure.

### CCI — PASS · PULLBACK · c2

- Counting: support 0 [] · oppose 7 [livermore, lynch, minervini, oneil, thorp, weis, wyckoff] · abstain 4 [detect-lens, elder-lens, raschke, seow]
- Nominated by: livermore (c3)
- **livermore** OPPOSE c3: Withdrawn on review. C5 needs an established uptrend: ma50 74.08 < ma100 77.76 < ma200 82.31, entry 81.14 under ma200, from_52w_hi=-17.93. A sharp rally into the long average, not a new high.
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT turnaround: tower REIT, rev -35% FY25, negative equity (P/B=-10.7, D/E=-7.16), EPS -360% FY24. Shrinking with a broken balance sheet (C12, C5 survival). ma_50=74.08<ma_200=82.31.
- **minervini** OPPOSE c4: Not stage 2: entry=81.14 < ma200=82.31, ma50=74.08 < ma100=77.76 < ma200, rs_rank_pct=36.47, from_52w_hi=-17.93. Rally into the long average (C2,C3).
- **oneil** OPPOSE c3: No uptrend base: entry=81.14 still under ma_200=82.31, ma_50=74.08 < ma_200 inverted. rs_leadership=IN-LINE fails R2. A rally into the long average is repair.
- **thorp** OPPOSE c2: edge=none measured in packet; structure/composites are a shape, not a mispricing (C11); vol_measure=atr_pct 3.13% (atr 2.54/entry 81.14; rank 42/54, q4) q4 after run_10d 18.83% inside an inverted stack: wide band, no measured mispricing (C3/C6).
- **weis** OPPOSE c2: W23: inverted ma50=74.08<ma100=77.76<ma200=82.31; run_10d 18.83% rally to entry 81.14 just under ma200. W14: in a downtrend, a rally to resistance is where upthrusts work. Upthrust not confirmable (R8), so only 2.
- **wyckoff** OPPOSE c2: Rally of 18.83% into ma_200=82.31 from below (entry=81.14): an old level acting as ceiling (C3), sma_distance_pct=9.54 extended. Upthrust risk at the ceiling (C10), unserved. Not a range edge from support.

### TDC — PASS · PULLBACK · c2

- Counting: support 1 [elder-lens] · oppose 5 [detect-lens, livermore, minervini, oneil, thorp] · abstain 5 [lynch, raschke, seow, weis, wyckoff]
- Nominated by: elder-lens (c3)
- **detect-lens** OPPOSE c2: lens_positive=1 (resistance) vs warns insti_money, sector; ma50 28.91 below ma100 30.51 and ma200 29.78: dual-MA fails.
- **elder-lens** SUPPORT c2: R8 dip-reclaim: CORRECTION_REENTRY, mp_state=STRONG, mp=76.0; elder_5d=[6, 10, 6, 10, 10], a <=6 bar gave way two bars ago, elder=10.0 now. Transition real, not today's bar.
- **livermore** OPPOSE c3: C5 fails: from_52w_hi=-14.33, ma50 28.91 under ma100 30.51 and ma200 29.78, sector Declining — Avoid. A rebound, not a new high in a leading group (C12).
- **minervini** OPPOSE c3: Trend Template fails: ma50=28.91 < ma200=29.78 < ma100=30.51 (criterion 4), from_52w_hi=-14.33, rs IN-LINE, sector Declining (C3).
- **oneil** OPPOSE c3: R2: rs_leadership=IN-LINE. R9: Technology Declining — Avoid, lens.sector=warn. ma_50=28.91 under ma_200=29.78. day_vol=0.84. Lone Ranger in a broken group.
- **thorp** OPPOSE c2: edge=none measured in packet; structure/composites are a shape, not a mispricing (C11); vol_measure=atr_pct 3.27% (atr 1.06/entry 32.45; rank 43/54, q4) q4 while labelled PULLBACK 12.24% over SMA; ranks below calmer equivalents (C6/R1).

### LNT — PASS · PULLBACK · c3

- Counting: support 1 [thorp] · oppose 8 [detect-lens, livermore, minervini, oneil, raschke, seow, weis, wyckoff] · abstain 2 [elder-lens, lynch]
- Nominated by: thorp (c3)
- **detect-lens** OPPOSE c3: lens_positive=1 (sector) vs 3 warns (leadership, coil, structure); BEARISH_CHOCH; dual-MA fails ma50 66.96<ma200 70.37.
- **livermore** OPPOSE c3: C5/C16: BEARISH_CHOCH, entry 68.27 under ma200 70.37, from_52w_hi=-12.51. No uptrend, no new high.
- **minervini** OPPOSE c4: Not stage 2: BEARISH_CHOCH, ma50=66.96 < ma100=70.27 < ma200=70.37, entry=68.27 below ma200, rs_rank_pct=37.58 (C2,C3).
- **oneil** OPPOSE c4: R3 FAIL: structure=54.7 BEARISH_CHOCH, ma_50=66.96 under ma_200=70.37. No base, no leader in group. Utilities Fading.
- **raschke** OPPOSE c2: No long setup (C2): structure_shift=BEARISH_CHOCH, structure=54.7, sma_distance_pct=1.95. Failed up-structure; nothing to test or retrace into.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-7.77, from_52w_hi=-12.51%. Price 4.5% over ma_20=65.36 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **thorp** SUPPORT c3: cohort signal_hit_rate_20d=57.0 n=251 (~2.2 SE over coin-flip); vol_measure=atr_pct 1.76% (atr 1.2/entry 68.27; rank 13/54, q1). Reversion inside BEARISH_CHOCH, structure 54.7. Gapped worst case 3.68% in R1 (C2/C4).
- **weis** OPPOSE c3: W10/W23: BEARISH_CHOCH, ma50=66.96<ma100=70.27<ma200=70.37, entry 68.27 under ma200. The elder 6->10 reentry is a spring-shaped read in a downtrend: short evidence.
- **wyckoff** OPPOSE c2: structure_shift=BEARISH_CHOCH; entry=68.27 under ma_100=70.27 and ma_200=70.37, the old levels now ceilings (C3). lens.coil=warn: no contraction. Markdown, not a range edge.

### CMS — PASS · PULLBACK · c2

- Counting: support 1 [thorp] · oppose 8 [detect-lens, livermore, minervini, oneil, raschke, seow, weis, wyckoff] · abstain 2 [elder-lens, lynch]
- Nominated by: thorp (c3)
- **detect-lens** OPPOSE c3: lens_positive=1 (sector) vs 4 warns (leadership, coil, insti_money, structure); BEARISH_CHOCH; inverted ma50 66.97<ma100 70.38<ma200 72.6. Weakest lens read in room.
- **livermore** OPPOSE c3: C5/C16: BEARISH_CHOCH, ma50 66.97 < ma100 70.38 < ma200 72.6, from_52w_hi=-14.41. A falling column.
- **minervini** OPPOSE c4: Not stage 2: BEARISH_CHOCH, ma50=66.97 < ma100=70.38 < ma200=72.6, rs_rank_pct=26.38, from_52w_hi=-14.41 (C2,C3).
- **oneil** OPPOSE c4: R3 FAIL: structure=54.7 BEARISH_CHOCH, ma_50=66.97 < ma_100=70.38 < ma_200=72.6. Lens 4 warns. Nothing CAN SLIM here.
- **raschke** OPPOSE c2: No long setup (C2): structure_shift=BEARISH_CHOCH, structure=54.7, sma_distance_pct=2.17, lens warns on structure, coil, insti_money and leadership. Failed up-structure.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-7.52, from_52w_hi=-14.41%. Price 5.2% over ma_20=65.04 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **thorp** SUPPORT c2: cohort signal_hit_rate_20d=57.0 n=251 (~2.2 SE over coin-flip); vol_measure=atr_pct 1.74% (atr 1.19/entry 68.42; rank 12/54, q1). lens_warnings 4, the room's high; edge is cohort-level, not name-level, so weight cut (C22). Gapped worst case 3.54% in R1.
- **weis** OPPOSE c3: W10/W23: BEARISH_CHOCH, ma50=66.97<ma100=70.38<ma200=72.6, entry 68.42 under all three longer averages. A reentry inside a downtrend is short evidence, never long.
- **wyckoff** OPPOSE c3: structure_shift=BEARISH_CHOCH, inverted stack ma_50=66.97 < ma_200=72.6; lens.coil=warn, lens.structure=warn. Failed up-structure, rally into ceilings (C3). No contraction, no edge.

### KIM — PASS · PULLBACK · c2

- Counting: support 1 [elder-lens] · oppose 5 [livermore, minervini, oneil, seow, weis] · abstain 5 [detect-lens, lynch, raschke, thorp, wyckoff]
- Nominated by: elder-lens (c3)
- **elder-lens** SUPPORT c2: Permission event on the last bar: elder_5d=[8, 9, 9, 6, 9] (6->9), elder=9.0, CORRECTION_REENTRY, mp_state=BUILDING, mp=66.0. C4/C6 pullback end. Trend leg (rising average, C9/C10) is off my menu: disclosed, not assumed.
- **livermore** OPPOSE c3: C5/C16: entry 23.0 under ma50 23.15 and ma200 23.4, from_52w_hi=-12.81, rank 197. Bought low, not bought strong.
- **minervini** OPPOSE c4: Not stage 2: entry=23.0 < ma50=23.15 < ma200=23.4, ma100=24.16 above both, rs_rank_pct=40.45, structure 42.1 (C2,C3).
- **oneil** OPPOSE c3: R3: structure=42.1, entry=23.0 under ma_50=23.15 and ma_200=23.4. A bounce in a sold-off name, not a base breakout.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-12.01, from_52w_hi=-12.81%. Price 2.9% over ma_20=22.36 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **weis** OPPOSE c2: W10/W23: entry 23.0 under ma50=23.15, ma100=24.16 and ma200=23.4; structure 42.1. A BOS on day_vol=1.11 inside a downtrend is the bottom-picker case. Only 2: stack not fully inverted.

### TRP — PASS · PULLBACK · c3

- Counting: support 1 [thorp] · oppose 8 [detect-lens, livermore, minervini, oneil, raschke, seow, weis, wyckoff] · abstain 2 [elder-lens, lynch]
- Nominated by: thorp (c3)
- **detect-lens** OPPOSE c2: lens_positive=2 (insti_money, sector) equals warns (leadership, structure); BEARISH_CHOCH; dual-MA fails ma50 61.34<ma200 63.4.
- **livermore** OPPOSE c3: C5/C16: BEARISH_CHOCH, ma50 61.34 under ma200 63.4, from_52w_hi=-12.86. No trend column to ride.
- **minervini** OPPOSE c4: Not stage 2: BEARISH_CHOCH, ma50=61.34 < ma200=63.4 < ma100=64.62, from_52w_hi=-12.86, rs_rank_pct=50.67 (C2,C3).
- **oneil** OPPOSE c3: R3 FAIL: structure=54.7 BEARISH_CHOCH, ma_50=61.34 under ma_200=63.4. day_vol=0.66. Energy Fading.
- **raschke** OPPOSE c2: No long setup (C2): structure_shift=BEARISH_CHOCH, structure=54.7, sma_distance_pct=0.74, day_vol=0.66. Failed up-structure.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-11.54, from_52w_hi=-12.86%. Price 3.3% over ma_20=59.84 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **thorp** SUPPORT c3: cohort signal_hit_rate_20d=57.0 n=251 (~2.2 SE over coin-flip); vol_measure=atr_pct 2.17% (atr 1.34/entry 61.79; rank 25/54, q2). Reversion inside BEARISH_CHOCH, structure 54.7, day_vol 0.66. Gapped worst case 4.34% in R1 (C2/C4).
- **weis** OPPOSE c3: W10/W23: BEARISH_CHOCH, ma50=61.34<ma200=63.4<ma100=64.62, entry 61.79 under ma200. Reentry inside a downtrend reads as short evidence.
- **wyckoff** OPPOSE c2: structure_shift=BEARISH_CHOCH; entry=61.79 under ma_200=63.4 and ma_100=64.62 (ceilings, C3); structure=54.7. Markdown with no measured contraction (lens.coil=ok). No edge.

### REG — PASS · PULLBACK · c3

- Counting: support 1 [thorp] · oppose 8 [detect-lens, livermore, minervini, oneil, raschke, seow, weis, wyckoff] · abstain 2 [elder-lens, lynch]
- Nominated by: thorp (c3)
- **detect-lens** OPPOSE c2: lens_positive=2 (coil, insti_money) equals warns (leadership, structure); BEARISH_CHOCH; dual-MA fails ma50 74.1<ma200 76.51.
- **livermore** OPPOSE c3: C5/C16: BEARISH_CHOCH, sma_dist -1.22, ma50 74.1 under ma200 76.51. A low price, not strength.
- **minervini** OPPOSE c4: Not stage 2: BEARISH_CHOCH, entry=73.2 < ma50=74.1 < ma200=76.51, rs_rank_pct=27.78, from_52w_hi=-11.47 (C2,C3).
- **oneil** OPPOSE c4: R2 and R3 fail: IN-LINE, structure=42.1 BEARISH_CHOCH, ma_50=74.1 under ma_200=76.51.
- **raschke** OPPOSE c2: No long setup (C2): structure_shift=BEARISH_CHOCH, structure=42.1, sma_distance_pct=-1.22. Failed up-structure, nothing to test.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-10.97, from_52w_hi=-11.47%. Price 1.4% over ma_20=72.21 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **thorp** SUPPORT c3: cohort signal_hit_rate_20d=57.0 n=251 (~2.2 SE over coin-flip); vol_measure=atr_pct 1.48% (atr 1.08/entry 73.2; rank 3/54, q1) calm q1. Reversion inside BEARISH_CHOCH, structure 42.1. Gapped worst case 5.33% in R1 is the cost that sizes it (C9).
- **weis** OPPOSE c3: W10/W23: BEARISH_CHOCH, ma50=74.1<ma200=76.51<ma100=76.84, entry 73.2 under ma50; structure 42.1. A reentry inside a downtrend is short evidence, never long.
- **wyckoff** OPPOSE c2: structure_shift=BEARISH_CHOCH, entry=73.2 under ma_50=74.1 and ma_200=76.51 (ceilings, C3); structure=42.1. Contraction (lens.coil=strong) inside a falling structure is not a range edge.

### VTR — PASS · PULLBACK · c3

- Counting: support 1 [thorp] · oppose 8 [detect-lens, livermore, minervini, oneil, raschke, seow, weis, wyckoff] · abstain 2 [elder-lens, lynch]
- Nominated by: thorp (c3)
- **detect-lens** OPPOSE c2: lens_positive=1 (insti_money) vs warns (structure, resistance); BEARISH_CHOCH. Lens tier low.
- **livermore** OPPOSE c3: C5/C16: BEARISH_CHOCH, sma_dist -1.76, from_52w_hi=-13.97. No uptrend to buy a new high in.
- **minervini** OPPOSE c4: Not stage 2: BEARISH_CHOCH, entry=86.49 < ma50=88.04 < ma100=88.78, rs_rank_pct=56.06, from_52w_hi=-13.97 (C2,C3).
- **oneil** OPPOSE c3: R3 FAIL: structure=44.2 BEARISH_CHOCH, entry=86.49 under ma_50=88.04. day_vol=0.59.
- **raschke** OPPOSE c2: No long setup (C2): structure_shift=BEARISH_CHOCH, structure=44.2, sma_distance_pct=-1.76, day_vol=0.59. Failed up-structure.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-11.0, from_52w_hi=-13.97%. Price 2.5% over ma_20=84.36 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **thorp** SUPPORT c3: cohort signal_hit_rate_20d=57.0 n=251 (~2.2 SE over coin-flip); vol_measure=atr_pct 2.12% (atr 1.83/entry 86.49; rank 23/54, q2). Reversion inside BEARISH_CHOCH, structure 44.2, day_vol 0.59. Gapped worst case 4.58% in R1 (C2/C4).
- **weis** OPPOSE c2: W23: BEARISH_CHOCH, entry 86.49 under ma50=88.04 and ma100=88.78; ma20=84.36 below ma200=86.18. Intermediate trend down; reentry read is short evidence (W10). 2: long average still under price.
- **wyckoff** OPPOSE c2: structure_shift=BEARISH_CHOCH, entry=86.49 under ma_50=88.04 and ma_200=86.18 crossover zone; lens.resistance=warn overhead; structure=44.2. Ceiling above (C3), no contraction (lens.coil=ok).

### CL — PASS · MOMENTUM · c3

- Counting: support 1 [detect-lens] · oppose 2 [minervini, oneil] · abstain 2 [elder-lens, livermore]
- Advisory: support [raschke] · oppose [lynch] · abstain [seow, thorp, weis, wyckoff]
- Nominated by: raschke (c2)
- **detect-lens** SUPPORT c3: lens_positive=4 (leadership, structure, resistance, sector strong), coil warn only; BULLISH_BOS. ma50 89.19 above ma200 89.15 (flat). day_vol 0.73 light. conv=ceil(4/1.5)=3.
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT stalwart: rev +1%, EPS -25% FY25, PE=37.2, P/B=319.1, D/E=33.3 (near-zero equity, C12 fail), DY=2.23%. Shrinking earnings at a premium.
- **minervini** OPPOSE c2: Template fails: ma50=89.19 < ma100=90.14, ma200=89.15 flat (criteria 3,4), from_52w_hi=-4.64, day_vol=0.73 on the BOS (C3,C6).
- **oneil** OPPOSE c3: C16 hard reject: BULLISH_BOS on day_vol=0.73, a break nobody bought. Flat MAs ma_50=89.19, ma_200=89.15: no prior uptrend. rank=31 #4 in XLP (C9).
- **raschke** SUPPORT c2: setup=TEST (C2/C20): structure_shift=BULLISH_BOS, structure=74.7, sma_distance_pct=6.0, mp_state=STRONG, mp_accel_state=ACCELERATING. day_vol=0.73 light participation on the break keeps it at 2; buy the retest only.

### LYFT — PASS · PULLBACK · c2

- Counting: support 1 [raschke] · oppose 4 [livermore, minervini, oneil, thorp] · abstain 6 [detect-lens, elder-lens, lynch, seow, weis, wyckoff]
- Nominated by: raschke (c2)
- **livermore** OPPOSE c3: C5: from_52w_hi=-29.79, structure_shift=RANGE, Technology Declining — Avoid. Far from any high; a rebound, not a leader.
- **minervini** OPPOSE c3: Trend Template fails criterion 7: from_52w_hi=-29.79, beyond 25% of the high; RANGE, sector Declining (C3).
- **oneil** OPPOSE c3: R9: Technology Declining — Avoid, lens.sector=warn. structure_shift=RANGE, no completed base. day_vol=0.96. Lens '--' leaves no base read.
- **raschke** SUPPORT c2: setup=RETRACEMENT (C2): structure=84.2, structure_shift=RANGE inside the swing, sma_distance_pct=5.94, mp_state=BUILDING, mp_accel_state=ACCELERATING, elder_pattern=CORRECTION_REENTRY (advisory). Lens mostly '--' caps it at 2.
- **thorp** OPPOSE c2: edge=none measured in packet; structure/composites are a shape, not a mispricing (C11); vol_measure=atr_pct 3.30% (atr 0.57/entry 17.25; rank 44/54, q4) q4, RANGE, 29.79% under 52w high: wide band, unmeasured (C3/C6).

### DOCS — PASS · MOMENTUM · c2

- Counting: support 1 [elder-lens] · oppose 4 [detect-lens, livermore, minervini, oneil] · abstain 0 []
- Advisory: support [] · oppose [] · abstain [lynch, raschke, seow, thorp, weis, wyckoff]
- Nominated by: elder-lens (c2)
- **detect-lens** OPPOSE c2: lens_positive=2 (resistance, sector) equals warns (leadership, coil); from_52w_hi -51.31% and run_10d 20.01%: thrust without lens leadership.
- **elder-lens** SUPPORT c2: R8 only: CORRECTION_REENTRY, mp_state=STRONG, mp=92.0; elder_5d=[7, 10, 7, 7, 10] shallow dip to 7 and reclaim, no red lifted. Pullback timing (C6); I buy value, not the stretch.
- **livermore** OPPOSE c3: C5/C16: from_52w_hi=-51.31, ret_12m -50.64, ma100 24.19 under ma200 25.97. A sharp rally in a broken stock, not a new high in a trend.
- **minervini** OPPOSE c3: Broken leader (C13): from_52w_hi=-51.31, ret_12m=-50.64, ma100=24.19 under ma200=25.97. Criterion 7 fails (C3).
- **oneil** OPPOSE c3: Base is a repair: ma_100=24.19 under ma_200=25.97, lens.leadership=warn, lens.coil=warn. sma_distance_pct=23.46 extended. day_vol=1.4 meets volume but no sound base under it.

### PBI — PASS · PULLBACK · c2

- Counting: support 1 [thorp] · oppose 5 [livermore, minervini, oneil, raschke, seow] · abstain 5 [detect-lens, elder-lens, lynch, weis, wyckoff]
- Nominated by: thorp (c2)
- **livermore** OPPOSE c3: C5/C16: BEARISH_CHOCH, from_52w_hi=-6.16, ma50 16.81 under ma100 17.17. No trend column.
- **minervini** OPPOSE c3: Not stage 2: BEARISH_CHOCH, ma50=16.81 < ma100=17.17 (criterion 4), mp=48.0 (C2,C3).
- **oneil** OPPOSE c3: R3 FAIL: structure=63.2 BEARISH_CHOCH. day_vol=1.58 on a failed structure is not a base breakout.
- **raschke** OPPOSE c2: No long setup (C2): structure_shift=BEARISH_CHOCH, structure=63.2, day_vol=1.58 on a failed up-structure. Coil is strong but the shift is down.
- **seow** OPPOSE c2: C2/C3 need an established up-tide to buy a dip in: ret_63d=-3.45, from_52w_hi=-6.16%. Price 3.9% over ma_20=16.71 is a bounce inside a falling tide, not a pullback in an up-trend. 40MA/CCI unverifiable.
- **thorp** SUPPORT c2: cohort signal_hit_rate_20d=57.0 n=251 (~2.2 SE over coin-flip); vol_measure=atr_pct 2.65% (atr 0.46/entry 17.37; rank 35/54, q3) mid-set. Reversion inside BEARISH_CHOCH, structure 63.2. Gapped worst case 5.24% in R1. Conv 2: mid vol, edge cohort-level only.

### MRSH — PASS · MOMENTUM · c2

- Counting: support 1 [elder-lens] · oppose 3 [detect-lens, minervini, oneil] · abstain 1 [livermore]
- Advisory: support [raschke] · oppose [] · abstain [lynch, seow, thorp, weis, wyckoff]
- Nominated by: raschke (c2)
- **detect-lens** OPPOSE c2: lens_positive=2 (resistance, sector) vs 3 warns (leadership, coil, insti_money); day_vol 0.75.
- **elder-lens** SUPPORT c2: C24 (unsourced): elder_5d=[9, 10, 10, 10, 10] SUSTAINED, mp_state=STRONG, mp=82.0. Plateau is summer (C20); labelled desk read at 2, pullback entry only.
- **minervini** OPPOSE c2: Template criterion 8 fails: rs_rank_pct=59.24 under 70; RANGE, day_vol=0.75 (C3,C6).
- **oneil** OPPOSE c2: lens.leadership=warn, structure_shift=RANGE, day_vol=0.75: no breakout, no confirmed leadership.
- **raschke** SUPPORT c2: setup=RETRACEMENT (C2): structure=69.5, structure_shift=RANGE, sma_distance_pct=5.54 holding above the average, mp_state=STRONG, mp_accel_state=ACCELERATING, elder_pattern=SUSTAINED, div_state=BULLISH (advisory).

### TTAN — PASS · MOMENTUM · c2

- Counting: support 0 [] · oppose 4 [detect-lens, livermore, minervini, oneil] · abstain 1 [elder-lens]
- Advisory: support [] · oppose [lynch, raschke, wyckoff] · abstain [seow, thorp, weis]
- Nominated by: thorp (c2)
- **detect-lens** OPPOSE c3: lens_positive=0 vs 4 warns (leadership, structure, resistance, sector); BEARISH_CHOCH; runner_conviction 3 untagged after run_10d 17.53%.
- **livermore** OPPOSE c4: C5/C16: BEARISH_CHOCH, structure 46.3, from_52w_hi=-26.83, entry 80.71 with ma20 69.41 under ma50 76.29; Technology Declining. A failed up-structure is not momentum.
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT fast grower: unprofitable SaaS, rev +31->26->24% decelerating (C17), NM=-12.1%, PE=-58.9, P/FCF=60.9 (C13 fail). structure_shift=BEARISH_CHOCH, sector Declining — Avoid.
- **minervini** OPPOSE c3: Not stage 2: BEARISH_CHOCH, entry=80.71 with ma50=76.29 above ma20=69.41, from_52w_hi=-26.83 fails criterion 7 (C2,C3).
- **oneil** OPPOSE c4: R3 FAIL: structure=46.3 BEARISH_CHOCH. R9: Technology Declining — Avoid. Lens 4 warns.
- **raschke** OPPOSE c2: No long setup (C2): structure_shift=BEARISH_CHOCH, structure=46.3, lens warns on leadership, structure, resistance, sector. A failed up-structure is not a test, retracement or breakout.
- **wyckoff** OPPOSE c2: structure_shift=BEARISH_CHOCH (up-structure failed), structure=46.3, lens.resistance=warn overhead; rally of 17.53% into supply. No contraction measured (lens.coil=ok). Advisory vote.

### NDAQ — PASS · PULLBACK · c2

- Counting: support 1 [detect-lens] · oppose 3 [livermore, minervini, oneil] · abstain 7 [elder-lens, lynch, raschke, seow, thorp, weis, wyckoff]
- Nominated by: wyckoff (c2)
- **detect-lens** SUPPORT c2: lens_positive=3 (coil, insti_money, sector strong), leadership warn only. Trend filter: ma50 94.59>ma100 91.57>ma200 90.44. adx 14.88 quiet: coil. conv=2.
- **livermore** OPPOSE c2: C5: from_52w_hi=-6.12, structure_shift=RANGE, mp 26.0 DECELERATING. Not a new high.
- **minervini** OPPOSE c2: Template criterion 8 fails: rs_rank_pct=62.0 under 70; mp=26.0, rs IN-LINE, elder INTERRUPTED (C3,C11).
- **oneil** OPPOSE c3: R2: IN-LINE. structure=43.2 RANGE, no completed base.

### OKTA — PASS · PULLBACK · c2

- Counting: support 1 [detect-lens] · oppose 6 [elder-lens, livermore, lynch, oneil, seow, thorp] · abstain 4 [minervini, raschke, weis, wyckoff]
- Nominated by: seow (c2)
- **detect-lens** SUPPORT c2: premove_setup=true, premove_conviction 4/4 (only tag in room); runner_conviction 3; coil strong. lens_positive=2 vs 3 warns. Radar: launch historically lags the tag, not same-day. conv=2.
- **elder-lens** OPPOSE c5: CENSOR: elder=0.0, elder_5d=[3, 1, 0, 0, 0]. Red is certain (<=1) on four bars; Elder's rule forbids buying while red (C1/C3). Hard no-buy, whatever else looks good.
- **livermore** OPPOSE c4: C5: a buy on the pullback itself: run_10d -11.27%, entry 194.02 under ma20 210.0, from_52w_hi=-16.42. Never buy the reaction.
- **lynch** OPPOSE c3: r1_lynch=CONTRADICT fast grower: rev +22->15->12% decelerating (C17 sell signal), PE=114.8, NM=9.6%, P/FCF=33.4 (FCF yield ~3%). EPS +688% is base effect. Multiple prices fading growth.
- **oneil** OPPOSE c3: Not a breakout: entry=194.02 under ma_20=210.0, IN-LINE, Technology Declining — Avoid. I do not buy pullbacks or reclaims.
- **seow** OPPOSE c2: Re-walked my own gates: C6/R8 odds gate FAILS (rs_spy_20d=-0.76 lags the index; a laggard gets no long at all). C4 grade fails: run_10d=-11.27 over 10 sessions is longer than a <5-day dip. 20MA over 40MA and close over the 40MA still hold.
- **thorp** OPPOSE c3: edge=none measured in packet; structure/composites are a shape, not a mispricing (C11); vol_measure=atr_pct 5.62% (atr 10.91/entry 194.02; rank 54/54, q4) highest in room, run_10d -11.27%, elder 0.0: the widest band to survive and no measured mispricing (C3/C6).

### MP — PASS · PULLBACK · c2

- Counting: support 0 [] · oppose 11 [detect-lens, elder-lens, livermore, lynch, minervini, oneil, raschke, seow, thorp, weis, wyckoff] · abstain 0 []
- **detect-lens** OPPOSE c2: ADD: no. lens=null, lens_positive=null: lens cannot read. Off-lens: BEARISH_CHOCH, ma50 50.62<ma100 51.74<ma200 56.14, rs_spy_20d -22.93. Held verdict: EXIT-CASE on trend filter; keep/exit is the PM's call.
- **elder-lens** OPPOSE c4: ADD question: no. elder=3.0 is unresolved permission (2-6 band), mp=0.0 FADING, elder_5d absent so R7 cannot be read. No colour event to buy. Held book: EXIT-CASE on my read; the add is refused, the exit is the PM's.
- **livermore** OPPOSE c5: ADD: OPPOSE (C4, never average down). HOLD: EXIT-CASE. entry 53.0, sma_dist -22.86, structure 11.0, BEARISH_CHOCH, inverted stack, unrealised -4185.0. C3/C22: the loss is the market saying I am wrong.
- **lynch** OPPOSE c3: ADD: no. Held, keep/exit=EXIT-CASE to PM. NM=-19.9%, OM=-33.1%, P/FCF=-13.8 cash burn; structure=11.0 BEARISH_CHOCH, sma_distance_pct=-22.86. C22 down-buy needs a verified intact story; unserved. Stop: house law.
- **minervini** OPPOSE c5: ADD: no; never average down (C9). Held name in stage 4: BEARISH_CHOCH, ma50=50.62 < ma100=51.74 < ma200=56.14, sma_dist=-22.86, rs_spy_20d=-22.93, structure 11.0, unrealised -4185.0. Keep/exit: EXIT (C7,C10).
- **oneil** OPPOSE c5: ADD: NO. EXIT. Held qty 300.0 @ 53.0 at unrealised -4185.0: adding is averaging down, barred (C20), and the loss is past the C20 cost stop. structure=11.0 BEARISH_CHOCH, sma_distance_pct=-22.86, under ma_50=50.62 (R8).
- **raschke** OPPOSE c4: ADD=no. Held, EXIT-CASE (R7/C1/C18): structure=11.0, structure_shift=BEARISH_CHOCH, sma_distance_pct=-22.86, mp_accel_state=DECELERATING. No setup type fits; no structural swing stop sits nearby, so risk is undefined. Keep is not supported: exit.
- **seow** OPPOSE c4: ADD: no - C16, adding to a losing position is not in the method at any size (unrealised -4185.0). KEEP/EXIT: EXIT. Held since 2026-10-08, far past the C11 day-5 time stop; price below ma_20=44.94 (sma_dist -22.86), rs_spy_20d=-22.93 fails C6.
- **thorp** OPPOSE c3: ADD: no. vol_measure=atr_pct 4.51% (atr 2.39/entry 53.0; rank 50/54, q4) q4; structure 11.0, sc_mom 22.7, unrealised -4185.0 with no written stop: unwatched loss is the whole position (C2/C9). Keep/exit: EXIT-CASE unless a loss boundary is written today.
- **weis** OPPOSE c4: ADD: no. W23/W10: stack inverted ma50=50.62<ma100=51.74<ma200=56.14, BEARISH_CHOCH, structure 11.0, rs_spy_20d -22.93, price below vwap14 43.6. No rejection of weakness in packet. Keep/exit: exit-lean, PM's call.
- **wyckoff** OPPOSE c3: ADD: no. structure=11.0, structure_shift=BEARISH_CHOCH, sma_dist=-22.86, under ma_20=44.94/ma_50=50.62/ma_200=56.14: markdown, no range, no spring. Hold: EXIT-CASE; no danger point (written stop None).

## A.2 Held reviews, MP (round 1, verbatim)

- **elder-lens** EXIT-CASE: elder=3.0 (2-6, no buy permission), mp=0.0, mp_state=FADING; elder_5d=null and elder_pattern=null so R7 cannot read; live_px=39.05 vs entry=53.0, unreal_usd=-4185.0, hl_state=EXIT. C18: no stop on record (held_sl=null) - a losing trade is never handed more room.
- **livermore** EXIT-CASE: structure=11.0, structure_shift=BEARISH_CHOCH, sma_distance_pct=-22.86, mp_state=FADING, mp_accel_state=DECELERATING vs held=True cost entry=53.0: up-trend has ended (C20) and the loss is no longer small (C3); never average down (C4); no broker stop means the danger signal is already passed unacted. Exit, review, wait for the next setup (C22).
- **minervini** EXIT-CASE: Stage 2 lost: live_px=39.05 below ma_20=44.94, ma_50=50.62, ma_200=56.14; structure_shift=BEARISH_CHOCH, structure=11.0, rs_spy_20d=-22.93, unreal_usd=-4185 vs entry 53.0. C7/C10: exit, never hold a loser to be proven right; no broker stop on it.
- **oneil** EXIT-CASE: C20 breached: held_book.live_px=39.05 vs held_book.entry=53.0 (unreal_usd=-4185.0), far past the 7-8% automatic stop, and no broker stop exists. 10-week line failed (R8): ma_50=50.62, sma_distance_pct=-22.86; structure=11.0, BEARISH_CHOCH, day_vol=0.66. Never average down.
- **raschke** EXIT-CASE: Up-structure failed: structure_shift=BEARISH_CHOCH, structure=11.0, sma_distance_pct=-22.86, mp_accel_state=DECELERATING; live_px=39.05 vs entry=53.0, unreal_usd=-4185.0 with NO broker stop. C17/C1/C21: the swing-low stop is long breached; cut the loss, do not let drawdown recovery eat the book.
- **seow** EXIT-CASE: C14/C20 loss-side first: live_px=39.05 vs cost 53.0 (unreal_usd=-4185.0), below ma_20=44.94 and ma_50=50.62, sma_distance_pct=-22.86, rs_spy_20d=-22.93, hl_state=EXIT, mp=0.0; close is below support and no broker stop protects it.
- **thorp** EXIT-CASE: No measured edge: sc_momentum=22.7, sc_m_gate_detail=1 (all fail), held_book.hl_state=EXIT, hl_score=0.0, vwap BELOW; live_px=39.05 vs entry=53.0, unreal_usd=-4185.0. atr_14d=2.39 (6.12% of px, top-quartile vol). No broker stop: unwatched loss unbounded (C9).
- **weis** EXIT-CASE: W23 trend gate fails: live_px=39.05 vs entry=53.0, sma_distance_pct=-22.86, ma_20=44.94 < ma_50=50.62 < ma_200=56.14, choch_state=BEARISH, structure_shift=BEARISH_CHOCH, mp=0.0, hl_state=EXIT; pin_bar_state=NONE, no spring signal; div_state=BULLISH is the only offset.
- **wyckoff** EXIT-CASE: Range failed: structure_shift=BEARISH_CHOCH, structure=11.0, live_px=39.05 vs entry 53.0, sma_distance_pct=-22.86 under ma_20=44.94/ma_50=50.62/ma_200=56.14; mp_state=FADING, mp_accel_state=DECELERATING. Old bottom is now ceiling (C3); no structural danger point exists below and broker has no stop.

## A.3 conditions.md (verbatim: what each analyst said would make them act, and what would prove them wrong)

## What each analyst said would make them act, and what would prove them wrong — 2026-10-21

### CNC · ADVANCE · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 70.97 (2: livermore, oneil); dips under pivot_high 69.63 then closes the hour back above it (2: raschke, weis)
**Confirmed by:** holds above today's VWAP
**Wait-for area:** 69.63–69.63 (pivot_high)
**Too late past:** closes above pivot_high+5pct 73.1115
**Exit lines, highest first:** 68.53 (livermore, minervini, raschke) · 67.43 (oneil) · 65.54 (minervini) · 65.28 (weis) · 65.1452 (oneil)

| Analyst | Acts when | Wrong when |
|---|---|---|
| livermore support c4 | an hourly candle closes above bar_high 70.97 and volume at least 1.2x normal for the time of day and holds above today's VWAP | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 68.53 |
| minervini support c4 | an hourly candle closes above pivot_high 69.63 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 68.53 or closes below ma_50 65.54 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above bar_high 70.97 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 67.43 or closes below entry-8pct 65.1452 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c3 | dips under pivot_high 69.63 then closes the hour back above it and volume at least 1.2x normal for the time of day | closes below pivot_high-0.5atr 68.53 |
| seow abstain c- | an hourly candle closes above bar_high 70.97 | closes below ma_40 65.55 |
| weis support c2 | dips under pivot_high 69.63 then closes the hour back above it and holds above today's VWAP | closes below ma_20 65.28 |

### CAH · ADVANCE · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 257.55 (4: detect-lens, livermore, minervini, oneil)
**Confirmed by:** outperforms SPY today
**Wait-for area:** 235.4–235.4 (ma_20)
**Too late past:** closes above pivot_high+5pct 261.755
**Exit lines, highest first:** 246.455 (livermore, minervini) · 243.62 (oneil) · 236.946 (oneil) · 235.4 (detect-lens, minervini) · 235.13 (raschke) · 229.73 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 257.55 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 235.4 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 235.4 | elder reading drops to 1 or less or closes below ma_20-1atr 229.73 |
| livermore support c4 | an hourly candle closes above bar_high 257.55 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 246.455 |
| lynch oppose c2 | — | — |
| minervini support c4 | an hourly candle closes above bar_high 257.55 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 235.4 or closes below pivot_high-0.5atr 246.455 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c3 | an hourly candle closes above bar_high 257.55 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 243.62 or closes below entry-8pct 236.946 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 257.55 and holds above today's VWAP | closes below ma_50 235.13 |
| seow abstain c- | an hourly candle closes above bar_high 257.55 | closes below ma_40 235.5 |

### LLY · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 1311.75 (4: detect-lens, livermore, minervini, oneil)
**Confirmed by:** outperforms SPY today
**Wait-for area:** 1188.21–1188.21 (ma_20)
**Too late past:** closes above pivot_high+10pct 1336.5
**Exit lines, highest first:** 1196.33 (livermore, minervini) · 1188.21 (detect-lens, minervini) · 1182.47 (lynch, raschke) · 1180.97 (oneil) · 1177.66 (oneil) · 1150.87 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 1311.75 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 1188.21 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 1188.21 | elder reading drops to 1 or less or closes below ma_20-1atr 1150.87 |
| livermore support c4 | an hourly candle closes above bar_high 1311.75 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 1196.33 |
| lynch support c3 (advisory) | not a price call | closes below ma_50 1182.47 · C17/C24: growth deceleration with PE held, or institutional ownership >75% (gate 3); both unserved, PM to verify. Late innings at this size. |
| minervini support c3 | an hourly candle closes above bar_high 1311.75 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 1188.21 or closes below pivot_high-0.5atr 1196.33 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above bar_high 1311.75 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 1177.66 or closes below entry-8pct 1180.97 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 1311.75 and holds above today's VWAP | closes below ma_50 1182.47 |
| seow abstain c- | an hourly candle closes above bar_high 1311.75 | closes below ma_40 1171.58 |

### CME · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Wait-for area:** 275.07–275.07 (ma_20)
**Too late past:** closes above pivot_high+5pct 304.395
**Exit lines, highest first:** 287.01 (raschke, wyckoff) · 284.12 (oneil) · 271.685 (oneil) · 269.29 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 275.07 | elder reading drops to 6 or less or elder reading drops to 1 or less or closes below ma_20-1atr 269.29 |
| livermore oppose c2 | closes above high_52w_close 326.46 and volume at least 1.2x normal for the time of day | — |
| minervini oppose c3 | — | — |
| oneil support c2 | an hourly candle closes above bar_high 299.92 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 284.12 or closes below entry-8pct 271.685 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c3 (advisory) | dips under pivot_high 289.9 then closes the hour back above it and volume at least 1.2x normal for the time of day | closes below pivot_high-0.5atr 287.01 |
| seow abstain c- | an hourly candle closes above bar_high 299.92 | closes below ma_40 276.5 |
| wyckoff support c2 (advisory) | dips under pivot_high 289.9 then closes the hour back above it and volume at most 1x normal for the time of day | closes below pivot_high-0.5atr 287.01 |

### PK · ADVANCE · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 16.63 (3: livermore, minervini, oneil)
**Confirmed by:** outperforms SPY today; volume at least 1.4x normal for the time of day
**Wait-for area:** 15.48–15.48 (ma_20)
**Too late past:** closes above pivot_high+5pct 16.7055
**Exit lines, highest first:** 15.69 (livermore, minervini) · 15.48 (minervini) · 15.47 (oneil) · 15.39 (raschke) · 15.2444 (oneil) · 15.04 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| elder-lens support c3 | elder reading 7 or more and comes back to ma_20 15.48 | elder reading drops to 1 or less or closes below ma_20-1atr 15.04 |
| livermore support c3 | an hourly candle closes above bar_high 16.63 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 15.69 |
| lynch oppose c3 | — | — |
| minervini support c3 | an hourly candle closes above bar_high 16.63 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 15.48 or closes below pivot_high-0.5atr 15.69 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above bar_high 16.63 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 15.47 or closes below entry-8pct 15.2444 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 16.63 and holds above today's VWAP | closes below ma_50 15.39 |
| seow abstain c- | an hourly candle closes above bar_high 16.63 | closes below ma_40 15.41 |

### PRCH · ADVANCE · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 18.41 (3: detect-lens, livermore, wyckoff)
**Confirmed by:** volume at least 1.4x normal for the time of day
**Wait-for area:** 17.14–17.98 (ma_20, pivot_high)
**Too late past:** closes above pivot_high+5pct 18.879
**Exit lines, highest first:** 17.98 (detect-lens, wyckoff) · 17.565 (livermore, minervini, raschke) · 16.97 (minervini) · 16.31 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c3 | an hourly candle closes above bar_high 18.41 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high 17.98 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 17.14 | elder reading drops to 1 or less or closes below ma_20-1atr 16.31 |
| livermore support c2 | an hourly candle closes above bar_high 18.41 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 17.565 |
| lynch oppose c3 | — | — |
| minervini support c3 | an hourly candle closes above pivot_high 17.98 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 17.565 or closes below ma_50 16.97 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c3 | — | — |
| raschke support c3 | dips under pivot_high 17.98 then closes the hour back above it and volume at least 1.2x normal for the time of day | closes below pivot_high-0.5atr 17.565 |
| seow abstain c- | an hourly candle closes above bar_high 18.41 | closes below ma_40 17.01 |
| thorp oppose c2 | — | — |
| wyckoff support c3 | an hourly candle closes above bar_high 18.41 and volume at least 1.4x normal for the time of day | closes below pivot_high 17.98 |

### TRV · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 396.46 (3: detect-lens, oneil, raschke)
**Wait-for area:** 369.45–369.45 (ma_20)
**Too late past:** closes above pivot_high+5pct 403.19
**Exit lines, highest first:** 380.015 (minervini) · 376.04 (oneil) · 369.71 (lynch, minervini, raschke) · 369.45 (detect-lens, livermore) · 364.072 (oneil)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 396.46 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 369.45 or structure turns bearish |
| livermore support c3 | closes above high_52w_close 397.22 and volume at least 1.2x normal for the time of day | falls 1.5 ATR off the day's high or closes below ma_20 369.45 |
| lynch support c4 | not a price call | closes below ma_50 369.71 · Cat losses or reserve charges breaking EPS; P/E far above its own average (C17). Underwriting-cycle data unserved. |
| minervini support c4 | an hourly candle closes above pivot_high 383.99 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 380.015 or closes below ma_50 369.71 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above bar_high 396.46 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 376.04 or closes below entry-8pct 364.072 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 | an hourly candle closes above bar_high 396.46 and holds above today's VWAP | closes below ma_50 369.71 |
| seow abstain c- | an hourly candle closes above bar_high 396.46 | closes below ma_40 370.16 |

### PEB · ADVANCE · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 20.92 (3: livermore, minervini, oneil)
**Confirmed by:** outperforms SPY today; volume at least 1.4x normal for the time of day
**Wait-for area:** 19.09–19.09 (ma_20)
**Too late past:** closes above pivot_high+10pct 21.45
**Exit lines, highest first:** 19.155 (livermore, minervini) · 19.09 (minervini) · 19.0532 (oneil) · 18.81 (oneil) · 18.4 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 19.09 | elder reading drops to 6 or less or elder reading drops to 1 or less or closes below ma_20-1atr 18.4 |
| livermore support c4 | an hourly candle closes above bar_high 20.92 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 19.155 |
| lynch oppose c3 | — | — |
| minervini support c3 | an hourly candle closes above bar_high 20.92 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 19.09 or closes below pivot_high-0.5atr 19.155 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c3 | an hourly candle closes above bar_high 20.92 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 18.81 or closes below entry-8pct 19.0532 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| seow abstain c- | an hourly candle closes above bar_high 20.92 | closes below ma_40 18.58 |

### CCEP · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 113.51 (4: detect-lens, livermore, minervini, oneil)
**Confirmed by:** outperforms SPY today
**Wait-for area:** 104.38–104.38 (ma_20)
**Too late past:** closes above pivot_high+5pct 114.744
**Exit lines, highest first:** 108.26 (livermore, minervini) · 107.24 (oneil) · 105.28 (raschke) · 104.38 (detect-lens, minervini) · 104.337 (oneil) · 102.34 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 113.51 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 104.38 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 104.38 | elder reading drops to 6 or less or elder reading drops to 1 or less or closes below ma_20-1atr 102.34 |
| livermore support c3 | an hourly candle closes above bar_high 113.51 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 108.26 |
| minervini support c3 | an hourly candle closes above bar_high 113.51 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 104.38 or closes below pivot_high-0.5atr 108.26 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above bar_high 113.51 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 107.24 or closes below entry-8pct 104.337 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 113.51 and holds above today's VWAP | closes below ma_50 105.28 |
| seow abstain c- | an hourly candle closes above bar_high 113.51 | closes below ma_40 104.77 |

### DRH · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 13.88 (2: livermore, minervini)
**Confirmed by:** outperforms SPY today
**Wait-for area:** 12.74–12.74 (ma_20)
**Too late past:** closes above bar_high+1atr 14.21
**Exit lines, highest first:** 12.745 (livermore, minervini) · 12.74 (minervini) · 12.41 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens oppose c2 | — | — |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 12.74 | elder reading drops to 6 or less or elder reading drops to 1 or less or closes below ma_20-1atr 12.41 |
| livermore support c3 | an hourly candle closes above bar_high 13.88 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 12.745 |
| minervini support c2 | an hourly candle closes above bar_high 13.88 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 12.74 or closes below pivot_high-0.5atr 12.745 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c2 | — | — |
| seow abstain c- | an hourly candle closes above bar_high 13.88 | closes below ma_40 12.52 |

### ADP · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 294.27 (3: livermore, minervini, oneil)
**Confirmed by:** outperforms SPY today; volume at least 1.4x normal for the time of day
**Wait-for area:** 270.32–270.32 (ma_20)
**Too late past:** closes above bar_high+1atr 299.79
**Exit lines, highest first:** 275.76 (livermore, minervini) · 273.56 (raschke) · 273 (oneil) · 270.32 (minervini) · 269.33 (oneil) · 264.8 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens oppose c2 | — | — |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 270.32 | elder reading drops to 1 or less or closes below ma_20-1atr 264.8 |
| livermore support c3 | an hourly candle closes above bar_high 294.27 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 275.76 |
| lynch oppose c2 | — | — |
| minervini support c3 | an hourly candle closes above bar_high 294.27 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 270.32 or closes below pivot_high-0.5atr 275.76 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above bar_high 294.27 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 273 or closes below entry-8pct 269.33 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 294.27 and holds above today's VWAP | closes below ma_50 273.56 |
| seow abstain c- | an hourly candle closes above bar_high 294.27 | closes below ma_40 273.32 |

### APLE · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 17.86 (2: livermore, minervini)
**Confirmed by:** outperforms SPY today
**Wait-for area:** 16.46–16.46 (ma_20)
**Too late past:** closes above bar_high+1atr 18.22
**Exit lines, highest first:** 16.52 (livermore, minervini) · 16.46 (minervini) · 16.1 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 16.46 | elder reading drops to 1 or less or closes below ma_20-1atr 16.1 |
| livermore support c2 | an hourly candle closes above bar_high 17.86 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 16.52 |
| minervini support c2 | an hourly candle closes above bar_high 17.86 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 16.46 or closes below pivot_high-0.5atr 16.52 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c2 | — | — |
| seow abstain c- | an hourly candle closes above bar_high 17.86 | closes below ma_40 16.12 |

### SHO · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 12.47 (2: livermore, minervini)
**Confirmed by:** outperforms SPY today
**Wait-for area:** 11.45–11.45 (ma_20)
**Too late past:** closes above bar_high+1atr 12.75
**Exit lines, highest first:** 11.45 (minervini) · 11.17 (elder-lens) · 11.05 (livermore, minervini)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens oppose c2 | — | — |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 11.45 | elder reading drops to 1 or less or closes below ma_20-1atr 11.17 |
| livermore support c2 | an hourly candle closes above bar_high 12.47 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 11.05 |
| lynch oppose c3 | — | — |
| minervini support c2 | an hourly candle closes above bar_high 12.47 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 11.45 or closes below pivot_high-0.5atr 11.05 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c2 | — | — |
| seow abstain c- | an hourly candle closes above bar_high 12.47 | closes below ma_40 11.26 |

### MA · ADVANCE · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 624.29 (3: livermore, minervini, oneil)
**Confirmed by:** outperforms SPY today; volume at least 1.4x normal for the time of day
**Too late past:** closes above pivot_high+5pct 631.292
**Exit lines, highest first:** 596.225 (livermore, minervini) · 591.22 (oneil) · 580.9 (minervini) · 577.83 (raschke) · 570.786 (oneil)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens oppose c2 | — | — |
| livermore support c3 | an hourly candle closes above bar_high 624.29 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 596.225 |
| minervini support c3 | an hourly candle closes above bar_high 624.29 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 580.9 or closes below pivot_high-0.5atr 596.225 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above bar_high 624.29 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 591.22 or closes below entry-8pct 570.786 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 624.29 and holds above today's VWAP | closes below ma_50 577.83 |
| seow abstain c- | an hourly candle closes above bar_high 624.29 | closes below ma_40 579.23 |

### MET · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 101.39 (2: livermore, raschke)
**Wait-for area:** 97.75–97.75 (ma_20)
**Too late past:** closes above bar_high+1atr 103.35
**Exit lines, highest first:** 97.47 (livermore, minervini) · 96.99 (minervini, raschke, weis) · 95.79 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| elder-lens support c3 | elder reading 7 or more and comes back to ma_20 97.75 | elder reading drops to 1 or less or closes below ma_20-1atr 95.79 |
| livermore support c2 | an hourly candle closes above bar_high 101.39 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 97.47 |
| minervini support c2 | an hourly candle closes above pivot_high 98.45 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 97.47 or closes below ma_50 96.99 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c2 | — | — |
| raschke support c3 | an hourly candle closes above bar_high 101.39 and holds above today's VWAP | closes below ma_50 96.99 |
| seow abstain c- | an hourly candle closes above bar_high 101.39 | closes below ma_40 97.21 |
| weis support c2 | closes above bar_high 101.39 and volume at least 1.4x normal for the time of day | closes below ma_50 96.99 |

### ABBV · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 290.98 (3: detect-lens, livermore, minervini)
**Confirmed by:** outperforms SPY today; volume at least 1.2x normal for the time of day
**Wait-for area:** 272.03–272.03 (ma_20)
**Too late past:** closes above bar_high+1atr 297.45
**Exit lines, highest first:** 272.03 (detect-lens, minervini) · 266.155 (livermore, minervini) · 265.56 (elder-lens) · 264.01 (raschke)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 290.98 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 272.03 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 272.03 | elder reading drops to 1 or less or closes below ma_20-1atr 265.56 |
| livermore support c3 | an hourly candle closes above bar_high 290.98 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 266.155 |
| lynch oppose c3 | — | — |
| minervini support c3 | an hourly candle closes above bar_high 290.98 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 272.03 or closes below pivot_high-0.5atr 266.155 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c2 | — | — |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 290.98 and holds above today's VWAP | closes below ma_50 264.01 |
| seow abstain c- | an hourly candle closes above bar_high 290.98 | closes below ma_40 265.87 |

### AVPT · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Wait-for area:** 14.18–14.18 (ma_20)
**Too late past:** closes above pivot_high+5pct 16.2015
**Exit lines, highest first:** 15.14 (minervini) · 13.69 (lynch, minervini) · 13.6 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| elder-lens support c3 | elder reading 7 or more and comes back to ma_20 14.18 | elder reading drops to 1 or less or closes below ma_20-1atr 13.6 |
| livermore abstain c- | closes above pivot_high 15.43 and volume at least 1.2x normal for the time of day | — |
| lynch support c2 (advisory) | not a price call | closes below ma_50 13.69 · C17/C24: revenue deceleration with PE held (PEG >2) or institutional ownership >75%; both unserved, PM to verify. |
| minervini support c2 | an hourly candle closes above pivot_high 15.43 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 15.14 or closes below ma_50 13.69 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c3 | — | — |
| raschke oppose c2 | — | — |
| seow abstain c- | an hourly candle closes above bar_high 15.49 | closes below ma_40 13.78 |

### ROKU · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Confirmed by:** volume at least 1.4x normal for the time of day
**Wait-for area:** 153.27–153.27 (ma_20)
**Too late past:** closes above bar_high+1atr 159.53
**Exit lines, highest first:** 157.87 (minervini) · 154.89 (minervini) · 153.27 (weis, wyckoff) · 152.29 (raschke) · 151.31 (elder-lens) · 150.03 (detect-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 157.57 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below base_low_20d 150.03 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 153.27 | elder reading drops to 1 or less or closes below ma_20-1atr 151.31 |
| livermore abstain c- | closes above high_52w_close 159.76 and volume at least 1.2x normal for the time of day | — |
| minervini support c3 | an hourly candle closes above pivot_high 158.85 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 157.87 or closes below ma_50 154.89 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| raschke support c3 (advisory) | an hourly candle closes above pivot_high 158.85 and volume at least 1.4x normal for the time of day | closes below ma_20-0.5atr 152.29 |
| seow abstain c- | an hourly candle closes above bar_high 157.57 | closes below ma_40 154.61 |
| weis support c2 (advisory) | closes above bar_high 157.57 and volume at least 1.4x normal for the time of day | closes below ma_20 153.27 |
| wyckoff support c3 (advisory) | an hourly candle closes above bar_high 157.57 and volume at least 1.4x normal for the time of day | closes below ma_20 153.27 |

### HNGE · ADVANCE · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 108 (3: detect-lens, livermore, minervini)
**Confirmed by:** outperforms SPY today; volume at least 1.2x normal for the time of day
**Wait-for area:** 99.32–99.32 (ma_20)
**Too late past:** closes above bar_high+1atr 112.43
**Exit lines, highest first:** 99.32 (detect-lens, minervini) · 94.89 (elder-lens) · 94.445 (livermore, minervini)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 108 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 99.32 or structure turns bearish |
| elder-lens support c3 | elder reading 7 or more and comes back to ma_20 99.32 | elder reading drops to 1 or less or closes below ma_20-1atr 94.89 |
| livermore support c3 | an hourly candle closes above bar_high 108 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 94.445 |
| minervini support c3 | an hourly candle closes above bar_high 108 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 99.32 or closes below pivot_high-0.5atr 94.445 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c2 | — | — |
| raschke oppose c2 | — | — |
| seow abstain c- | an hourly candle closes above bar_high 108 | closes below ma_40 95.61 |
| thorp oppose c2 | — | — |

### CNK · ADVANCE · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 40.35 (4: detect-lens, livermore, minervini, oneil)
**Confirmed by:** outperforms SPY today; volume at least 1.2x normal for the time of day; volume at least 1.4x normal for the time of day
**Too late past:** closes above pivot_high+5pct 41.0235
**Exit lines, highest first:** 38.47 (livermore, minervini) · 37.87 (oneil) · 37.33 (detect-lens, minervini) · 36.938 (oneil) · 36.56 (raschke)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 40.35 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 37.33 or structure turns bearish |
| livermore support c3 | an hourly candle closes above bar_high 40.35 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 38.47 |
| minervini support c4 | an hourly candle closes above bar_high 40.35 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 37.33 or closes below pivot_high-0.5atr 38.47 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c4 | an hourly candle closes above bar_high 40.35 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 37.87 or closes below entry-8pct 36.938 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 40.35 and holds above today's VWAP | closes below ma_50 36.56 |
| seow abstain c- | an hourly candle closes above bar_high 40.35 | closes below ma_40 36.39 |

### KMI · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Wait-for area:** 32.01–32.01 (ma_20)
**Too late past:** closes above bar_high+1atr 34.44
**Exit lines, highest first:** 31.77 (raschke, weis)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens oppose c2 | — | — |
| livermore abstain c- | closes above high_52w_close 34.31 and volume at least 1.2x normal for the time of day | — |
| minervini oppose c3 | — | — |
| oneil oppose c2 | — | — |
| raschke support c2 | an hourly candle closes above bar_high 33.68 and holds above today's VWAP | closes below ma_50 31.77 |
| seow abstain c- | an hourly candle closes above bar_high 33.68 | closes below ma_40 31.73 |
| weis support c2 | closes above bar_high 33.68 and volume at least 1.4x normal for the time of day | closes below ma_50 31.77 |

### A · ADVANCE · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 174.8 (6: detect-lens, minervini, oneil, raschke, seow, wyckoff)
**Confirmed by:** volume at least 1.4x normal for the time of day
**Wait-for area:** 171.24–171.24 (ma_20)
**Too late past:** closes above bar_high+1atr 179.48
**Exit lines, highest first:** 174.71 (minervini) · 172.37 (oneil) · 171.24 (weis) · 170.38 (seow) · 168.9 (raschke, wyckoff) · 163.27 (detect-lens) · 161.91 (seow) · 159.86 (minervini) · 159.169 (oneil)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c3 | an hourly candle closes above bar_high 174.8 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below base_low_20d 163.27 or structure turns bearish |
| livermore abstain c- | closes above high_52w_close 175.55 and volume at least 1.2x normal for the time of day | — |
| lynch oppose c3 | — | — |
| minervini support c3 | an hourly candle closes above pivot_high 177.05 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 174.71 or closes below ma_50 159.86 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above pivot_high 177.05 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 172.37 or closes below entry-8pct 159.169 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 | an hourly candle closes above pivot_high 177.05 and volume at least 1.4x normal for the time of day | closes below ma_20-0.5atr 168.9 |
| seow support c3 | an hourly candle closes above bar_high 174.8 and ma_20 171.24 above ma_40 161.91 | closes below ma_40 161.91 or closes below bar_low 170.38 · CCI<-100 and 20MA slope not computed by AQE (disclosed). After fill: breakeven at +5%, trail under prior-day low, exit on time at day 5 (C9-C12). |
| weis support c3 | closes above bar_high 174.8 and volume at least 1.4x normal for the time of day | closes below ma_20 171.24 |
| wyckoff support c3 | an hourly candle closes above pivot_high 177.05 and volume at least 1.4x normal for the time of day | closes below ma_20-0.5atr 168.9 |

### CRM · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** an hourly candle closes above pivot_high 262.33 (2: minervini, raschke)
**Confirmed by:** volume at least 1.4x normal for the time of day
**Wait-for area:** 232.01–233.99 (ma_20, ma_50)
**Too late past:** closes above bar_high+1atr 252.98
**Exit lines, highest first:** 257.91 (minervini) · 232.01 (lynch, minervini, weis, wyckoff) · 229.57 (raschke)

| Analyst | Acts when | Wrong when |
|---|---|---|
| livermore oppose c2 | — | — |
| lynch support c3 | not a price call | closes below ma_50 232.01 · C18 diworseification: a large unrelated acquisition; revenue growth fading with PEG above 2; leverage rising (D/E watch). |
| minervini support c2 | an hourly candle closes above pivot_high 262.33 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 257.91 or closes below ma_50 232.01 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c3 | — | — |
| raschke support c2 | an hourly candle closes above pivot_high 262.33 and volume at least 1.4x normal for the time of day | closes below ma_20-0.5atr 229.57 |
| seow abstain c- | an hourly candle closes above bar_high 244.14 | closes below ma_40 239.89 |
| thorp oppose c2 | — | — |
| weis support c2 | closes above bar_high 244.14 and volume at least 1.4x normal for the time of day | closes below ma_50 232.01 |
| wyckoff support c3 | comes back to ma_20 233.99 and volume at most 0.8x normal for the time of day | closes below ma_50 232.01 |

### BRZE · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Wait-for area:** 27.9–27.9 (ma_20)
**Too late past:** closes above bar_high+0.5atr 46.865
**Exit lines, highest first:** 33.765 (livermore) · 25.39 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens oppose c2 | — | — |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 27.9 | elder reading drops to 1 or less or closes below ma_20-1atr 25.39 |
| livermore support c2 | an hourly candle closes above bar_high 45.61 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 33.765 |
| lynch oppose c3 | — | — |
| oneil oppose c4 | — | — |
| raschke oppose c3 | — | — |
| seow oppose c3 | — | — |
| thorp oppose c3 | — | — |
| wyckoff oppose c2 | — | — |

### AFL · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Wait-for area:** 116.76–118.09 (pin_bar_level, pivot_high)
**Too late past:** closes above bar_high+1atr 122.73
**Exit lines, highest first:** 117.05 (raschke) · 116.76 (weis)

| Analyst | Acts when | Wrong when |
|---|---|---|
| livermore oppose c2 | — | — |
| minervini oppose c3 | — | — |
| oneil oppose c2 | — | — |
| raschke support c2 | dips under pivot_high 118.09 then closes the hour back above it and volume at least 1.2x normal for the time of day | closes below pivot_high-0.5atr 117.05 |
| seow oppose c2 | — | — |
| weis support c2 | closes above bar_high 120.65 and closes in the top 0.5 of the day's range | closes below pin_bar_level 116.76 |

### EW · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Wait-for area:** 86.38–88.29 (ma_20, ma_50)
**Too late past:** closes above bar_high+1atr 90.36
**Exit lines, highest first:** 85.16 (wyckoff) · 84.36 (elder-lens) · 82.43 (detect-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 88.34 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below base_low_20d 82.43 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 86.38 | elder reading drops to 1 or less or closes below ma_20-1atr 84.36 |
| livermore oppose c3 | — | — |
| lynch oppose c2 | — | — |
| minervini oppose c2 | — | — |
| oneil oppose c3 | — | — |
| seow abstain c- | an hourly candle closes above bar_high 88.34 and outperforms SPY today | closes below ma_40 87.49 |
| wyckoff support c2 | dips under ma_50 88.29 then closes the hour back above it and volume at most 0.8x normal for the time of day | closes below ma_200 85.16 |

### KDP · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 34.89 (4: detect-lens, livermore, minervini, oneil)
**Confirmed by:** outperforms SPY today; volume at least 1.2x normal for the time of day; volume at least 1.4x normal for the time of day
**Too late past:** closes above pivot_high+10pct 35.354
**Exit lines, highest first:** 32.02 (detect-lens, minervini) · 31.8596 (oneil) · 31.74 (raschke) · 31.735 (livermore, minervini) · 31.33 (oneil)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 34.89 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 32.02 or structure turns bearish |
| elder-lens oppose c2 | — | — |
| livermore support c3 | an hourly candle closes above bar_high 34.89 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 31.735 |
| lynch oppose c2 | — | — |
| minervini support c2 | an hourly candle closes above bar_high 34.89 and volume at least 1.4x normal for the time of day and outperforms SPY today | closes below ma_20 32.02 or closes below pivot_high-0.5atr 31.735 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above bar_high 34.89 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 31.33 or closes below entry-8pct 31.8596 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 34.89 and holds above today's VWAP | closes below ma_50 31.74 |
| seow abstain c- | an hourly candle closes above bar_high 34.89 | closes below ma_40 31.93 |

### CHD · HOLD-FOR-CONDITIONS · MOMENTUM

**Shared by the supporters:** an hourly candle closes above bar_high 106 (2: detect-lens, livermore)
**Confirmed by:** volume at least 1.2x normal for the time of day; outperforms SPY today
**Wait-for area:** 98.3–98.3 (ma_20)
**Too late past:** closes above bar_high+1atr 107.82
**Exit lines, highest first:** 98.36 (raschke) · 98.3 (detect-lens) · 96.48 (elder-lens) · 96.13 (livermore)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 106 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 98.3 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 98.3 | elder reading drops to 1 or less or closes below ma_20-1atr 96.48 |
| livermore support c2 | an hourly candle closes above bar_high 106 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 96.13 |
| lynch oppose c2 | — | — |
| minervini oppose c2 | — | — |
| oneil oppose c2 | — | — |
| raschke support c2 (advisory) | an hourly candle closes above bar_high 106 and holds above today's VWAP | closes below ma_50 98.36 |
| seow abstain c- | an hourly candle closes above bar_high 106 | closes below ma_40 97.91 |

### KO · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 93.96 (2: detect-lens, raschke); closes above high_52w_close 93.9 (2: livermore, weis)
**Wait-for area:** 88.73–88.73 (ma_20)
**Too late past:** closes above pivot_high+5pct 93.828
**Exit lines, highest first:** 92.64 (weis) · 88.73 (detect-lens, livermore) · 88.7 (minervini, raschke) · 88.645 (minervini)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 93.96 and volume at least 1.2x normal for the time of day and outperforms SPY today | closes below ma_20 88.73 or structure turns bearish |
| elder-lens oppose c2 | — | — |
| livermore support c2 | closes above high_52w_close 93.9 and volume at least 1.2x normal for the time of day | falls 1.5 ATR off the day's high or closes below ma_20 88.73 |
| lynch oppose c2 | — | — |
| minervini support c3 | an hourly candle closes above pivot_high 89.36 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 88.645 or closes below ma_50 88.7 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c2 | — | — |
| raschke support c2 | an hourly candle closes above bar_high 93.96 and holds above today's VWAP | closes below ma_50 88.7 |
| seow abstain c- | an hourly candle closes above bar_high 93.96 | closes below ma_40 88.67 |
| weis support c2 | closes above bar_high 93.96 and volume at least 1.4x normal for the time of day | closes below bar_low 92.64 |

### OXY · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 63.63 (2: detect-lens, raschke)
**Confirmed by:** holds above today's VWAP
**Wait-for area:** 59.13–59.13 (ma_20)
**Too late past:** closes above bar_high+1atr 65.17
**Exit lines, highest first:** 59.54 (raschke) · 54.76 (detect-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 63.63 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below base_low_20d 54.76 or structure turns bearish |
| elder-lens oppose c2 | — | — |
| livermore oppose c2 | closes above high_52w_close 66.24 and volume at least 1.2x normal for the time of day | — |
| minervini oppose c2 | — | — |
| oneil oppose c2 | — | — |
| raschke support c2 | an hourly candle closes above bar_high 63.63 and holds above today's VWAP | closes below ma_50 59.54 |
| seow abstain c- | an hourly candle closes above bar_high 63.63 | closes below ma_40 59.54 |

### HOMB · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 29.69 (2: detect-lens, wyckoff)
**Confirmed by:** volume at least 1.4x normal for the time of day
**Wait-for area:** 28.67–28.67 (ma_20)
**Too late past:** closes above bar_high+1atr 30.2
**Exit lines, highest first:** 29.52 (lynch) · 28.47 (wyckoff) · 28.16 (elder-lens) · 27.6 (detect-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 29.69 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below base_low_20d 27.6 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 28.67 | elder reading drops to 1 or less or closes below ma_20-1atr 28.16 |
| livermore oppose c3 | — | — |
| lynch support c3 | not a price call | closes below ma_50 29.52 · C15: deposit/funding stress or credit losses (unserved); revenue decline turning EPS growth negative. |
| minervini oppose c3 | — | — |
| oneil oppose c3 | — | — |
| seow oppose c2 | — | — |
| wyckoff support c2 | an hourly candle closes above ma_50 29.52 and volume at least 1.4x normal for the time of day | closes below ma_200 28.47 |

### ZION · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Confirmed by:** volume at least 1.4x normal for the time of day
**Wait-for area:** 62.88–62.88 (ma_20)
**Too late past:** closes above pivot_high+5pct 67.0425
**Exit lines, highest first:** 66.12 (lynch) · 63.85 (detect-lens) · 62.88 (weis) · 61.5 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c3 | an hourly candle closes above bar_high 65.61 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high 63.85 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 62.88 | elder reading drops to 1 or less or closes below ma_20-1atr 61.5 |
| livermore oppose c3 | — | — |
| lynch support c3 | not a price call | closes below ma_50 66.12 · C15 bank funding: deposit flight or credit-quality charge (unserved, PM to verify); EPS turning negative. |
| minervini oppose c3 | — | — |
| oneil oppose c3 | — | — |
| seow oppose c2 | — | — |
| weis support c2 | closes above ma_50 66.12 and volume at least 1.4x normal for the time of day | closes below ma_20 62.88 · Catalyst NONE - price shape only. |

### ACA · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** an hourly candle closes above bar_high 147.68 (2: detect-lens, livermore); an hourly candle closes above pivot_high 146.82 (2: minervini, oneil)
**Confirmed by:** volume at least 1.4x normal for the time of day
**Wait-for area:** 146.75–146.82 (ma_20, pivot_high)
**Too late past:** closes above bar_high+1atr 148.15
**Exit lines, highest first:** 146.82 (detect-lens) · 146.585 (livermore, minervini, raschke) · 146.35 (oneil) · 146.28 (elder-lens) · 145.92 (minervini, weis) · 135.654 (oneil)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c3 | an hourly candle closes above bar_high 147.68 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high 146.82 or structure turns bearish |
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 146.75 | elder reading drops to 1 or less or closes below ma_20-1atr 146.28 |
| livermore support c2 | an hourly candle closes above bar_high 147.68 and volume at least 1.2x normal for the time of day and outperforms SPY today | falls 1.5 ATR off the day's high or closes below pivot_high-0.5atr 146.585 |
| minervini support c2 | an hourly candle closes above pivot_high 146.82 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 146.585 or closes below ma_50 145.92 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil support c2 | an hourly candle closes above pivot_high 146.82 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below pivot_high-1atr 146.35 or closes below entry-8pct 135.654 · C/A/S/I NOT_AVAILABLE (no EPS, sales, sponsor count); market_gate DELEGATED: void if index under distribution; RS via rs_leadership substitute |
| raschke support c2 | dips under pivot_high 146.82 then closes the hour back above it and volume at least 1.2x normal for the time of day | closes below pivot_high-0.5atr 146.585 |
| seow abstain c- | an hourly candle closes above bar_high 147.68 | closes below ma_40 146.11 |
| weis support c2 | closes above bar_high 147.68 and volume at least 1.4x normal for the time of day | closes below ma_50 145.92 |

### TTEK · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Wait-for area:** 33.79–33.79 (ma_20)
**Too late past:** closes above ma_50+5pct 36.981
**Exit lines, highest first:** 33.79 (wyckoff) · 32.96 (elder-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| elder-lens support c2 | elder reading 7 or more and comes back to ma_20 33.79 | elder reading drops to 1 or less or closes below ma_20-1atr 32.96 |
| livermore oppose c3 | — | — |
| minervini oppose c3 | — | — |
| oneil oppose c3 | — | — |
| seow oppose c2 | — | — |
| wyckoff support c2 | an hourly candle closes above ma_50 35.22 and volume at least 1.4x normal for the time of day | closes below ma_20 33.79 |

### MRK · HOLD-FOR-CONDITIONS · PULLBACK

**Shared by the supporters:** none — each supporter named a different trigger (see below).
**Confirmed by:** volume at least 1.4x normal for the time of day
**Wait-for area:** 145.32–145.32 (ma_20)
**Too late past:** closes above bar_high+1atr 153.36
**Exit lines, highest first:** 151.57 (minervini) · 145.77 (minervini, weis) · 138.8 (detect-lens)

| Analyst | Acts when | Wrong when |
|---|---|---|
| detect-lens support c2 | an hourly candle closes above bar_high 149.36 and volume at least 1.4x normal for the time of day and holds above today's VWAP | closes below base_low_20d 138.8 or structure turns bearish |
| livermore oppose c2 | closes above high_52w_close 156.45 and volume at least 1.2x normal for the time of day | — |
| lynch oppose c2 | — | — |
| minervini support c2 | an hourly candle closes above pivot_high 153.57 and volume at least 1.4x normal for the time of day | closes below pivot_high-0.5atr 151.57 or closes below ma_50 145.77 · SEPA element 2 (EPS growth/acceleration) NOT_SERVED; fundamentals leg not run |
| oneil oppose c3 | — | — |
| seow oppose c2 | — | — |
| weis support c2 | closes above bar_high 149.36 and volume at least 1.4x normal for the time of day | closes below ma_50 145.77 |

# APPENDIX B — REPEAT WATCH, full table (verbatim)

| Ticker | Date Appeared | % vs last COB | State |
|---|---|---|---|
| **AAPL** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AAPL** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AAPL** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AAPL** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AAPL** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AAPL** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AAPL** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ABBV** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ABBV** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ABBV** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ABBV** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ABBV** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ABBV** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ABBV** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ABBV** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ABBV** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **ACGL** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ACGL** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ACGL** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ACGL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ACN** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ACN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ADP** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ADP** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ADP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ADP** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **AEP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AEP** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AEP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AEP** | 2026-10-21 | — (gap, see note) | PASS |
| **AFL** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AFL** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **AIG** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AIG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ALL** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ALL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AMGN** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AMGN** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AMGN** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AMGN** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AMGN** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AMGN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AMRZ** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AMRZ** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AMT** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AMT** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ANET** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ANET** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ASAN** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ASAN** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ASAN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AVPT** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AVPT** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AVPT** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AVPT** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AVPT** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **AWK** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AWK** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **AZN** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AZN** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AZN** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **AZN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BALL** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BALL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BBWI** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BBWI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BDX** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BDX** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BOX** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BOX** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BOX** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BOX** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BOX** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BOX** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BOX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BP** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BRK-B** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BRK-B** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BRK-B** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BRO** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BRO** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BRO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BROS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BROS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BRZE** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BRZE** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BRZE** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BRZE** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BRZE** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **BSX** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BSX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **BTI** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BTI** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BTI** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BUD** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **BUD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CAH** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CAH** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CAH** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **CART** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CART** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CCC** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCC** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCC** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCEP** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCEP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCEP** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCEP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCEP** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **CCI** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCI** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCI** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCI** | 2026-10-21 | — (gap, see note) | PASS |
| **CCL** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCL** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCL** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCL** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CCL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CDNS** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CDNS** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CDNS** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CDNS** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CDNS** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CDNS** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CELH** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CELH** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CHD** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CHD** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CHD** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CHD** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CHD** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **CIEN** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CIEN** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CIEN** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CIEN** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CIEN** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CIEN** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CL** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CL** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CL** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CL** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CL** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CL** | 2026-10-21 | — (gap, see note) | PASS |
| **CLX** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CLX** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CLX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CME** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CME** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CME** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CME** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **CMS** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CMS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CMS** | 2026-10-21 | — (gap, see note) | PASS |
| **CNC** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNC** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNC** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNC** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNC** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **CNK** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNK** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNK** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNK** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNK** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNK** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNK** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **CNP** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNQ** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNQ** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CNQ** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **COP** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **COP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **COP** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **COP** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **COST** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **COST** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **COST** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **COST** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **COST** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **COST** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CRM** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CRM** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **CTAS** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CTAS** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CTAS** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CTAS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CTAS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CVE** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CVE** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CVE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CVS** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CVS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CVS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CVX** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CVX** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CVX** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CVX** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CVX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **CXT** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CXT** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **CXT** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DDOG** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DDOG** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DDOG** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DDOG** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DDOG** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DDOG** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DDOG** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DDOG** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DDOG** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DG** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DG** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DG** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DINO** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DINO** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DINO** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DINO** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DINO** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DINO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DIS** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DIS** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DIS** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DIS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DLTR** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DLTR** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DOCS** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DOCS** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DOCS** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DOCS** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DOCS** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DOCS** | 2026-10-21 | — (gap, see note) | PASS |
| **DRH** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DRH** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DRH** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DRH** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DRH** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DRH** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **DRI** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DRI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DUK** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DUK** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DVN** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DVN** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DVN** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DVN** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DVN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **DXC** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DXC** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DXC** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **DXC** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **EBAY** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EBAY** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EBAY** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EBAY** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EBAY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ED** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ED** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ED** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **EL** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EL** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ELF** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ELF** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ELS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ELS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **EOG** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EOG** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EOG** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EOG** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EOG** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EOG** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EOG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **EPD** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EPD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **EQNR** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EQNR** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ETSY** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ETSY** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ETSY** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ETSY** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ETSY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **EVRG** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EVRG** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EVRG** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EVRG** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EXPE** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **EXPE** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FAST** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FAST** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FAST** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FAST** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FAST** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **FBP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FBP** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **FE** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FE** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FRSH** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FRSH** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FRSH** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FRSH** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **FTNT** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTNT** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTRE** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **FTRE** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GDDY** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GDDY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **GILD** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GILD** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GILD** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GILD** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GILD** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GILD** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GILD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **GM** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GM** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GME** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GOOG** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GOOG** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GOOG** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GOOG** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GOOG** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GSK** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GSK** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **GTLB** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GTLB** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GTLB** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GTLB** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GTLB** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GWRE** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GWRE** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **GWRE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **HD** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HD** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HDB** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HDB** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HLN** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HLN** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HLN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **HNGE** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HNGE** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HNGE** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HNGE** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HNGE** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HNGE** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HNGE** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HNGE** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HNGE** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **HPE** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HPE** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HPE** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HPE** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HPE** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HPE** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HUM** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HUM** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **HUM** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **IFF** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **IFF** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **IFF** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **INFY** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **INFY** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **INFY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ISRG** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ISRG** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ISRG** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ISRG** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ISRG** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ISRG** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ISRG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ITUB** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ITUB** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ITUB** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ITUB** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ITUB** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ITUB** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **JHX** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **JHX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KBR** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KBR** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KDP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KDP** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KDP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KDP** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **KIM** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KIM** | 2026-10-21 | — (gap, see note) | PASS |
| **KMB** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KMB** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KMI** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KMI** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KMI** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KMI** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KMI** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KMI** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **KO** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KO** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KO** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KO** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **KR** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KR** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KR** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KSS** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KSS** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KSS** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KSS** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KSS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KSS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KVUE** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KVUE** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KVUE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **KVYO** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KVYO** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KVYO** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **KVYO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LEVI** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LEVI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LLY** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LLY** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LLY** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LLY** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LLY** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **LOW** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LOW** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LOW** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LTH** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LTH** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LW** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LW** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LW** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **LYFT** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **LYFT** | 2026-10-21 | — (gap, see note) | PASS |
| **MA** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MA** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MA** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **MAS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MAS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **MDLZ** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MDLZ** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MDLZ** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **MDT** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MDT** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MET** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MET** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MET** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MET** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MET** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **MNST** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MNST** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MNST** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MO** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MO** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MO** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MO** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **MP** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MP** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MP** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MP** | 2026-10-21 | — (gap, see note) | PASS |
| **MPC** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MPC** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MPC** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MPC** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MPC** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MPC** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **MRNA** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRNA** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRNA** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRNA** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRNA** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRNA** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRNA** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRSH** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRSH** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRSH** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRSH** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRSH** | 2026-10-21 | — (gap, see note) | PASS |
| **MRVL** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MRVL** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MTCH** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **MTCH** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **NAVN** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NAVN** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NAVN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **NDAQ** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NDAQ** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NDAQ** | 2026-10-21 | — (gap, see note) | PASS |
| **NKE** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NKE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **NOW** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NOW** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTAP** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTAP** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTAP** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTAP** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTAP** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTAP** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTAP** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTAP** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTAP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTNX** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTNX** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTNX** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTNX** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTNX** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTNX** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NTSK** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NVS** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NVS** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NVS** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NVS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NVS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **NWS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **NWS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **O** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **O** | 2026-10-21 | — (gap, see note) | PASS |
| **OKE** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKE** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OKTA** | 2026-10-21 | — (gap, see note) | PASS |
| **OMC** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OMC** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OPLN** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OPLN** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OPLN** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ORLY** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ORLY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **OTIS** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OTIS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OTIS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **OUT** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OUT** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OUT** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OUT** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OUT** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **OXY** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OXY** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OXY** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OXY** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **OXY** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **P** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **P** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **P** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **P** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **P** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **P** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **P** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PATH** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PATH** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBF** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBF** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBF** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBF** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBF** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBI** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBI** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBI** | 2026-10-21 | — (gap, see note) | PASS |
| **PBR** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBR** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBR** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBR** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBR** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBR** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PBR-A** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBR-A** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBR-A** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBR-A** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PBR-A** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PDD** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PDD** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PEB** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **PFE** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PFE** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PFE** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PFE** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PFGC** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PFGC** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PFGC** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PFGC** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PG** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PG** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PG** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PG** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PINS** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PINS** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **PK** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PK** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PK** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PK** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PK** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **PLTR** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PLTR** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PLTR** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PLTR** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PLTR** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PLTR** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PLTR** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PM** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PM** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PM** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PM** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PM** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PM** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PRCH** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PRCH** | 2026-10-21 | — (gap, see note) | ADVANCE |
| **PSX** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PSX** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PSX** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PSX** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PSX** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **PSX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **RBRK** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RBRK** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RBRK** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RBRK** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RBRK** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RBRK** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RBRK** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RBRK** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RBRK** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RELX** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RELX** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RELX** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RELX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **REYN** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **REYN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ROKU** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ROKU** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **ROST** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ROST** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ROST** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ROST** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ROST** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ROST** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **RXO** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RXO** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RXO** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RXO** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RXO** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RXO** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RXO** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RXO** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RXO** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **RXO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SAP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SAP** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SAP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SAP** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SCI** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SCI** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SCI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SHEL** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHEL** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHEL** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHEL** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHEL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SHO** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHO** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHO** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHO** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHO** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHO** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **SHOP** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHOP** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHOP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHOP** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SHOP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SJM** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SJM** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SJM** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SLDE** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SLDE** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SNOW** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SNOW** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SNPS** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SNPS** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SNPS** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SNPS** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SNPS** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SO** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SO** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SO** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SO** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SONY** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SONY** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SONY** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SPGI** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SPGI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SU** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SU** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SU** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SU** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SU** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **SYNA** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SYNA** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SYNA** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SYNA** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SYNA** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SYNA** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **SYNA** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TAK** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TAK** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TAK** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TD** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TD** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **TDC** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TDC** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TDC** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TDC** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TDC** | 2026-10-21 | — (gap, see note) | PASS |
| **TEAM** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEAM** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEAM** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEAM** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEAM** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEAM** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEAM** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEAM** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEAM** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **TEVA** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEVA** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEVA** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEVA** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEVA** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEVA** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEVA** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TEVA** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TJX** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TJX** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TJX** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TJX** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TJX** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TJX** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TMO** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **TTE** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TTE** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TTEK** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **TTEK** | 2026-10-21 | — (gap, see note) | HOLD-FOR-CONDITIONS |
| **UBER** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UBER** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UGI** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UGI** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **UL** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UL** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UNH** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UNH** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UNH** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UNH** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UNP** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **UNP** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USFD** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USFD** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USFD** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USFD** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USFD** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **USO** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **USO** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **V** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **V** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **V** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **VEEV** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VEEV** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VEEV** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VEEV** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **VERX** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VERX** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VERX** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VERX** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **VIA** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VIA** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VIA** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VIA** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VIA** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VIA** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **VIK** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VIK** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VLTO** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VLTO** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VLTO** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VRSK** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VRSK** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VRSK** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VVV** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VVV** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VVV** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **VVV** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WAY** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WAY** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WAY** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WAY** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WAY** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WAY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WCN** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WCN** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WDAY** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WDAY** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WEAT** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-09-26 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-09-29 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-09-30 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEAT** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEC** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEC** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WEC** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WELL** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WELL** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WELL** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WM** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WM** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WMT** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WMT** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WMT** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WMT** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WMT** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WMT** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **WRB** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WRB** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WRB** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WRB** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WRB** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WRB** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WTRG** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **WTRG** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **XOM** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **XOM** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **XOM** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **XOM** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **XOM** | 2026-10-19 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **XOM** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **YOU** | 2026-10-01 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **YOU** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **YOU** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **YOU** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **YOU** | 2026-10-21 | — (gap, see note) | NEAR-MISS |
| **ZETA** | 2026-10-05 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZETA** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZETA** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZETA** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZETA** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-09-21 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-09-22 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-09-23 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-09-24 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-09-25 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-10-08 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-10-09 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-10-12 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-10-13 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |
| **ZS** | 2026-10-15 | — (gap, see note) | GAP: no verdict_ledger row for this (date,ticker) -- record-verdicts was not run, or predates the ledger |

---

DRAFT — PM approval required. Nothing is staged, nothing is armed.
