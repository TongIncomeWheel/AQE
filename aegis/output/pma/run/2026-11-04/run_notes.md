# PMA run notes -- Wed 4 Nov 2026 (for the 4 Nov US session, on the Tue 3 Nov close)

Third automated run; first LIVE run with the committee-position (R42) steps on. Started ~07:55 SGT from the READY watcher hand-off (07:41); the 08:20 backstop fired while this run held the lock and started nothing.

## Declared items
- DATA: AQE run 2026-11-04 (exported 07:15:20 SGT) carrying the Tue 3 Nov close; 260 rows, 2 held (live), 0 data-quality flags; check.py ready + data Healthy (also with the broker stops). Crown DEGRADED (declared by AQE, not a block).
- COMMITTEE DATA (by code, no couriers): committee data OK 2026-11-04: mtf 261/261 complete (261 native hourly), fundamentals 260/261 (228 carried; AMRZ partial), closes 702, 800 FMP calls in 554.7s.
- BOOK AND STOPS: 3 Nov journal + live read-only Tiger pull (~07:55 SGT): 0 disagreements. V 38 sh STP GTC stop 414.45 (was 391.80 on 3 Nov: moved by the PM); MP 300 sh STP_LMT GTC stop 36.66 limit 36.66.
- LEDGERS: verdict ledger (1878 rows) and phase4 ledger from the 3 Nov run's local record; neither was pushed to main by that run.
- INBOX-CLEAN: 12 AQE alert threads trashed, 0 remaining, 6 GitHub run-failure notifications left untouched.
- ROOM: 29 tickers nominated across 7 seats; 44 in the room; MTF 44/44 complete.
- COVERAGE (pre-vote): Healthy, exit 0; standing not-served fields and name-level blanks as quoted by check.py coverage (coverage.json).
- VOTE PACKET 91 KB, over the 70 KB soft cap, not trimmed. Every seat filed three parts (15/15/14).
- VOTE: 44 names, 7 deciders; CONTESTED 38, unanimous support 5, unanimous oppose 1. 132 claims routed; OUT (no SUPPORT): TXT MP EFX.
- CROSS: wyckoff reported one process breach: ran a read-only `wc -c` on two files it was allowed to read (not permitted by the prompt); it read nothing outside its list and changed nothing.
- FUNNEL (the measurement): 132 claims routed; rulings CONFIRM 93 / REFUTE 146 / CANNOT_SEE 25; 17 names survived tier 1, 24 dropped, 3 had no SUPPORT vote; stances changed on a peer's evidence: 5 (e.g. PYPL raschke SUPPORT->ABSTAIN, MDT wyckoff ABSTAIN->SUPPORT). 33 refute pairings on the 17 survivors.
- TIMING: 7 deciders on 17 survivors: ADVANCE 8 (ROKU DIS EW BRK-B MDT FA TMO HNGE), WATCH 9, none below 4 SUPPORT. Slate-wide market kill: index under distribution (4+ distribution days in 5 weeks, or no confirmed uptrend).
- SLATE CAP (declared): the registrar and slate schema still cap the slate at 15; the PM's ruling to raise it to 25 is not in the code on main today (engineering P2 pending). 17 survived, so the 2 lowest-SUPPORT names (5 SUPPORT each; every other name has 6 or 7, no tie at the boundary) are left off the slate and listed in slate_excluded.json: FA (ADVANCE, ACT_NOW 3 / WAIT 2) and CART (WATCH). Both stand as the committee's timing call in decision.json; they simply are not on the slate or ratified.
