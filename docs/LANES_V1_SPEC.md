# Lanes v1: three lanes by code, lead seats decide (SPEC for the conductor and PM, 4-5 Nov 2026)

**Status: PROPOSED. Not switched on.** `RUN.yaml parameters.lanes_v1: off`; ruling R43 is `status: proposed`; nothing in the live
run calls the code. Code: `aegis/plugin/aegis-core/skills/pma/tools/lanes_v1.py` (pure functions, tested). Dry-run below is on the
4 Nov r2 files (`aegis/output/pma/run/2026-11-04-r2/consensus.json` + the 4 Nov export, continuation fields computed from the
panel because that export predates them).

## 1. Today
Every ticket carries MOMENTUM or PULLBACK as a **label** (R14, superseded by R32: all seven deciders count on every ticket).
The lane is set by the doors that admitted the name, not by the shape of the chart. DROP = 4 of 7 objections.

## 2. The three lanes (assigned by code from AQE fields, first match wins, deterministic)
| Lane | Rule | Judged against |
|---|---|---|
| MOMENTUM_BREAKOUT | `0 <= pct_from_pivot <= 5`, or `< 0` and within 3% of the 20-bar high with a tight bar (squeeze / NR4 / NR7 / coil lens strong) | the base pivot, the 5% chase line, the volume test |
| MOMENTUM_CONTINUATION | `pct_from_pivot > 5` AND a continuation pause high exists (3-10 bar tight window ended within 5 bars) | the continuation pivot: BELOW = coiling under the pause high, 0-5% = buy zone, >5% = extended; stretch in daily ranges over the 20-day; "more than 70% over the 200-day" is a **warning, not a veto** |
| PULLBACK | `pct_from_pivot < 0` and (reclaim day, or holding a rising 20-day, or the 50-day) | reclaim of the rising average / the U&R reclaim |
| UNLANED | none of the above (e.g. extended with no pause high) | every seat counts, exactly as today |

## 3. Voice leads (advisors = the other deciders; the seven are oneil, minervini, livermore, elder-lens, seow, raschke, wyckoff)
| Lane | Leads | Advisors | Source |
|---|---|---|---|
| CONTINUATION | livermore, seow, elder-lens, raschke | oneil, minervini, wyckoff | **PM signed** (wyckoff placed by me; PM named O'Neil and Minervini only) |
| BREAKOUT | oneil, minervini, livermore, wyckoff | elder-lens, seow, raschke | **proposed**: the base-pivot / volume-test seats |
| PULLBACK | seow, elder-lens, raschke, wyckoff | oneil, minervini, livermore | **proposed**: Seow's method *is* the pullback setup (20 above 40, CCI under -100); Elder and Raschke trade the dip; Wyckoff reads the reclaim |

## 4. What must change in the packets before it can be switched on (the real work)
Leads can only judge a continuation ticket by its own method if they SEE it. Today every card's `pct_from_pivot` and chase line vote
against continuation names. To switch on: (a) `voice_menus.json`: add `continuation_pivot`, `continuation_low`, `pct_from_continuation_pivot`,
`continuation_state`, `extension_bracket` to the four continuation leads' menus (and `pct_from_pivot` stays for the others); (b) the vote
prompt states the ticket's lane and the lane's yardstick ("for MOMENTUM_CONTINUATION judge against the continuation pivot, not the base
pivot"); (c) `ratify-count` calls `lanes_v1.lane_status` when `lanes_v1: on` and prints advisor objections on the ticket, uncounted.
(a)-(c) are about a day of work with tests; the continuation fields exist in the export from 5 Nov.

## 5. Counting rule, measured on 4 Nov (16 slated tickets + 1; "today" = actual r2 status)
Lead objections decide; advisor objections are shown, never counted. Two threshold modes for the PM to pick between:
* **proportional** = DROP at `ceil(leads_present / 2)` lead objections (4 leads -> 2);
* **absolute** = DROP at the room's own 4, counted among the leads (all four leads must object).

| Ticker | Lane | Today | Proportional | Absolute |
|---|---|---|---|---|
| ROKU | BREAKOUT | AGREED | AGREED | AGREED |
| SN | CONTINUATION | CONTESTED | **DROPPED** | CONTESTED |
| V | BREAKOUT | CONTESTED | CONTESTED | CONTESTED |
| BRK-B | BREAKOUT | CONTESTED | **DROPPED** | CONTESTED |
| DIS | BREAKOUT | CONTESTED | CONTESTED | CONTESTED |
| TMO | BREAKOUT | CONTESTED | CONTESTED | CONTESTED |
| EW | CONTINUATION | CONTESTED | **AGREED** | AGREED |
| HNGE | CONTINUATION | CONTESTED | CONTESTED | CONTESTED |
| MDT | BREAKOUT | DROPPED | DROPPED | **CONTESTED** |
| AJG | BREAKOUT | CONTESTED | CONTESTED | CONTESTED |
| HOG | CONTINUATION | DROPPED | DROPPED | **CONTESTED** |
| TTEK | CONTINUATION | DROPPED | DROPPED | **CONTESTED** |
| VLTO | CONTINUATION | DROPPED | DROPPED | **CONTESTED** |
| GEN | CONTINUATION | CONTESTED | **DROPPED** | CONTESTED |
| SWK | CONTINUATION | CONTESTED | **DROPPED** | CONTESTED |
| FA | PULLBACK | CONTESTED | CONTESTED | CONTESTED |
| CART | PULLBACK | DROPPED | DROPPED | **CONTESTED** |

Lanes on the 17: BREAKOUT 7, CONTINUATION 8, PULLBACK 2. Changes vs today: proportional 5 (EW saved; SN, BRK-B, GEN, SWK newly
dropped), absolute 6 (all six are DROPPED -> CONTESTED: MDT, HOG, TTEK, VLTO, CART, plus EW AGREED).
**Plain reading.** (1) The mechanism works: EW's three objections were all advisors' (O'Neil, Minervini, Wyckoff) and are shown, not
counted. (2) It is **not a way to buy more momentum by itself.** On continuation names the leads (Livermore, Seow, Elder) objected
too: HOG, TTEK, VLTO were each opposed by Livermore and Seow, and SN/GEN/SWK by Elder and Seow. Under proportional counting those
names are dropped *more* easily, because 2 of 4 leads is a lower bar than 4 of 7. (3) Those leads voted on cards that still showed the
base pivot and the chase line; section 4 is what lets them vote on the continuation pivot. The dry-run therefore measures the
counting rule only, not what the leads would say on a continuation card. A second dry-run belongs after section 4.
(4) **Absolute mode almost abolishes DROP** (needs all four leads); that is a very different committee. I recommend proportional, or
proportional with a floor: DROP needs `max(2, ceil(leads/2))` lead objections AND at least one lead's `would_clear` unanswered. PM's call.

## 6. Decisions for the PM
1. Breakout leads (oneil, minervini, livermore, wyckoff) and pullback leads (seow, elder-lens, raschke, wyckoff): yes / change.
2. Wyckoff as an advisor, not a lead, on continuation: yes / lead.
3. Threshold: proportional (recommended) or absolute.
4. Authorise section 4 (packets + prompt + ratify-count wiring), then a second dry-run on a fresh run before `lanes_v1: on`.
