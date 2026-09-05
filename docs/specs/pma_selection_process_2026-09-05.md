# HOW A NAME GETS FROM AQE TO THE BRIEF — the funnel, end to end
Date 2026-09-05 · Every number below is 2026-09-04's actual run · Revised funnel per PM instructions of 2026-09-05

---

## A · THE FUNNEL AS IT RUNS TODAY

```
AQE export ─── 162 scored names ───────────────────────────────────────────────────────┐
     │                                                                                 │
 [1] PACKETS    each of 9 seats gets ALL 162 rows, ONLY its own columns               │  PM LENS (side lane)
     │          blind: no seat sees another seat's columns, reasoning or picks          │  PM's 6 checks on all 162
     ▼                                                                                 │  ≥5/6 → flagged
 [2] NOMINATE   each seat walks its checklist, files ≤10 names, conviction 1-5         │  14 names flagged
     │          9 seats → 64 filings on 50 distinct names                              │  11 of them the committee
     ▼                                                                                 │  NEVER LOOKED AT
 [3] QUALIFY    a name goes forward if  2+ seats named it                              │  (flashed beside, not inside
     │                              OR  1 seat named it at conviction 4+               │   — PM ruling 2026-08-19,
     │          50 → 18   (11 via two seats, 7 via the one-seat exception)             │   now REVERSED)
     ▼                                                                                 │
 [4] RANK       order: seat count, then conviction sum, then sector gate,              │
     │          then thematic, then sc_momentum.  Cap 20.  (cap did not bind)          │
     ▼                                                                                 │
 [5] CHALLENGE  4 seats read all 18 + every R1 reason + fundamentals:                  │
     │          Rogers (crowding/certainty/timing), Steenbarger (conviction audit,     │
     │          obligations), Lynch (fundamentals), Detect-lens (structure)            │
     ▼                                                                                 │
 [6] VOTE       11 seats (9 nominators + Lynch + Detect-lens) read everything          │
     │          from [5], vote SUPPORT / OPPOSE / ABSTAIN + conviction on all 18       │
     ▼                                                                                 │
 [7] DECIDE     ADVANCE  = support > oppose  AND  ≥2 support  AND  median support conviction ≥3
     │          HOLD     = ≥2 support but fails one of the above
     │          PASS     = otherwise
     │          18 → 1 ADVANCE (CB) · 9 HOLD · 8 PASS                                  │
     ▼                                                                                 ▼
 [8] BRIEF      verdicts + conditions + macro + held book + PM lens table ─────────────┘
```

**Only [2] and [3] filter.** [4] re-orders. [5] argues. [6]–[7] decide. AQE's own score enters only as the 5th tiebreak in [4].

---

## B · WHY IT DID NOT WORK FOR A MOMENTUM BOOK — three specific leaks

| Leak | Where | What happened on 09-04 |
|---|---|---|
| **Leaders die at [2]** | Nomination | 32 names had `elder_pattern` SUSTAINED/ACCELERATION. 10 nominated, 3 voted, 0 advanced. VLO (rank 10, RS +21.7), MPC, DINO, DUOL: zero nominations. Cause: the cards' "am I chasing" test has a precise field (`sma_distance_pct`); their "is this a leader" test has no 52-week high, no RS percentile, no pivot — so it runs on a 3-bucket proxy. Sharp reject beats fuzzy accept. |
| **The one-seat exception is 39% of the vote and 0% of the output** | [3] | 7 of 18 came in on one seat at conviction exactly 4 (stdev 0.00). 6 PASS, 1 HOLD, 0 ADVANCE. |
| **PM lens is a side lane** | side | 11 names passed the PM's own 5-of-6 and were never deliberated. Ruling now reversed by PM. |

---

## C · THE REVISED FUNNEL — PM instructions 2026-09-05, sized on real data

Four doors into the deliberation set instead of one. **The committee still votes on everything; independence is untouched.** What changes is what it is *forced to look at*.

```
 [3'] ADMIT — a name enters the deliberation set through ANY of:

   DOOR 1  seat consensus     nominated by ≥2 seats                              11 names   (was the only door)
   DOOR 2  sustained strength  elder ≥7 on each of the last 3 bars               24 names
                              AND detect-lens ≥3 of 6 lenses strong
   DOOR 3  PM lens             ≥5 of the PM's 6 checks                            14 names
   DOOR 4  AQE leader          elder_pattern SUSTAINED or ACCELERATION             7 names
                              AND rs_leadership LEADER AND mp_state STRONG

   The one-seat-at-conviction-4 exception is CLOSED.
   Union on 09-04: 46 names, of which 26 no seat had nominated.

 [4'] CAP 30 — DOOR 1 names are always kept (they are the committee's own picks).
              DOORS 2-4 fill the remaining slots by AQE rank.
              On 09-04: 11 + 19 = 30. Cut: the lowest-ranked door 2-4 names.

 Every admitted name carries its door(s) on the packet, so Round 2 can see
 "DOOR 4 only — no seat nominated this" and vote accordingly.
```

**What this would have put in front of the committee on 09-04 that it never saw:** VLO, MPC, DINO, DUOL, PBR-A, KDP (leaders) · GDDY, GEN, BOX, MFG, RELY, PRCH, AAPL, SONY (PM lens) · OKTA, PFE, TEAM, LNG, COP, SU, BKR, VG (sustained-strength).

**Why this works for a momentum book:** the four doors are four independent definitions of "strong right now" — the committee's judgment, Elder's force held three days, the PM's own six checks, and AQE's leader classification. A name that clears any one of them is at least worth a vote. A name that clears three is a momentum candidate by any definition, and today's process would still have let it die silently at nomination. Under the revised funnel it cannot.

**Cost:** vote round grows from 18 to 30 names. Each seat's ballot is bounded at 24KB, so ~800 bytes per name. Tight but workable; if it isn't, cap at 25.

---

## D · WHAT THE COMMITTEE STILL DOES, UNCHANGED

- Nominators still nominate blind, on their own columns only.
- Challenge seats still read everything and argue.
- Every voter still files SUPPORT/OPPOSE/ABSTAIN with a reason, an opposing case on every OPPOSE, and a falsifier.
- Consensus arithmetic unchanged.
- **Bracket and R:R are never a reason to reject. Ever.** (PM ruling R1, restated; the three cards that still say otherwise get the line deleted.)
- Chart patterns stay out of deliberation (PM 2026-09-05).

---

## E · THE ONE THING STILL OPEN

DOOR 4 (AQE leader) is defined on today's fields and is crude — `rs_leadership` is a 3-bucket. Once AQE serves `rs_rank_pct` and `pct_from_52w_high` (see the packet spec), DOOR 4 becomes: **RS percentile ≥80 AND within 15% of 52-week high AND elder_pattern SUSTAINED/ACCELERATION.** That is Minervini's and O'Neil's actual leader definition, computed properly, applied before any seat has to say "too extended."
