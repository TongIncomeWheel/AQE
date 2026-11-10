# PMA run notes -- Tue 10 Nov 2026 (for the 10 Nov US session, on the Mon 9 Nov close)

## Declared items
- TRIGGER: run started by the READY watcher's hand-off at 07:41 SGT after the data handoff read Healthy; `AEGIS pma-auto` was enabled (the PM's switch). No run lock existed.
- DATA: AQE run 2026-11-10 (06:30 to 07:15 SGT) carrying the Mon 9 Nov close; committee data OK: fundamentals 285/286 (AMRZ partial), mtf 286/286, closes 717/717, published 5/5; voice packets 7/7. Cboe single-stock volatility, DSPX and implied correlation read 6 Nov (publisher lag, WARN); COT 3 Nov (weekly cadence).
- BOOK AND STOPS: the book is FLAT. Export held_positions empty; the 9 Nov journal open_positions empty; the live read-only Tiger pull at GATHER shows only the options-wheel stock lines (COIN CRCL CRDO KO MARA MCD NVDA) and no working stock orders. The PM confirmed on 9 Nov that V was sold for target. Stops file: 0 positions.
- DATA CHECK: Healthy (the flat-book skip of the held-health fields is PR #67).
- ROOM: 50 names, MTF complete, seven deciders, all seven nominations in before the tally.
- FUNNEL: 142 claims, CONFIRM 101 / REFUTE 133 / CANNOT_SEE 50; 17 survivors; tier 2: ADVANCE 8, WATCH 7, NOT_SLATED 2. Slate cap 25: 15 slated, none cut by the cap.
- QA (Steenbarger): HOLD on 4 tickets (ABBV COR CHD LION); 28 floor messages (7 x 4), floor check OK; 7/7 second ratifications filed. The RATIFY2 and FLOOR2 prompt text named the previous day's held tickets by mistake; each seat answered the four tickets in slate_held.json (the validator enforces that), so the filed forms are unaffected.
- RESULT (R34, by code): 7 deciders, drop at 4+ objections: AGREED 0, CONTESTED 11, DROPPED 4 (ABBV CHD SHW LION), NOT_SLATED 35. ADVANCE 7, all contested (SWK PG TMO JNJ SJM COR CNK); HOLD-FOR-CONDITIONS 4 (MGNI BDX VSXY SONY).
- MARKET KILL: named by one decider: "Index not in a Confirmed Uptrend, or 4-5 distribution days in 4-5 weeks (C1, C2)"; no watchable level.
- R44: deal-pin manual override list (APO RY F COMP) applied.
- COMMITTEE POSITION (R42): rationale draft valid; RATIONALE-FINAL valid; 9 amendments attached verbatim; 26 DISSENT clauses ride as minority notes. Committee conviction: TMO SJM COR 4; SWK PG JNJ MGNI BDX CNK SONY 3; VSXY 2.
- SWK: the supporters share no buy line (conditions compile: no shared buy), so its card says so.
- BRACKETS: 11 of 11 ADVANCE/HOLD names have a computed stop; 2 clear both the atr and reward gates; 0 sized (1R $620 is the fund file's, never changed here).
- PURITY: ranking invariant to every bracket field: PASS.
- SCORECARD: graded with history exports to 9 Nov; the 30 Oct to 5 Nov exports were not re-pulled, so those runs' rows are ungraded (declared).
- INBOX-CLEAN: not run this run (declared).

CARDS FALLBACK: the v3 page was NOT published (the plain-words gate FAILED on the v3 page or its words file: the rendered cards still show raw field names: close_above x1, pivot_high x1). The v2 page was published instead.

CARDS FALLBACK: the v3 page was NOT published (the plain-words gate FAILED on the v3 page or its words file: the rendered cards still show raw field names: close_above x1, pivot_high x1). The v2 page was published instead.
