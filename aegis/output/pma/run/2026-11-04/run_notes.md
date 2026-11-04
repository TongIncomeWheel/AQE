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
