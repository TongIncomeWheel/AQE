# PMA run notes -- Mon 9 Nov 2026 (for the 9 Nov US session, on the Fri 6 Nov close)

## Declared items
- DATA: AQE run 2026-11-09 (forced rebuild, 14:55 to 15:36 SGT) carrying the Fri 6 Nov close; committee data OK: fundamentals 220/221, mtf 221/221, closes 683/713, published 5/5; voice packets 8/8. The committee-data fetch hit its 900 s budget; closes are missing for VRT VRTX VSAT VST VSTS VZ W WAY (declared gaps, 95% rule met).
- BOOK AND STOPS: the book is FLAT. Export held_positions empty; the 5 and 6 Nov journals show open_positions empty and the 5 Nov journal books one closed trade (V, closed for target per the PM). Stops file built from the 6 Nov journal: 0 positions. The Tiger wheel stock lines (COIN CRCL CRDO KO MARA MCD NVDA) belong to the options wheel, not this committee, and are not in the book.
- DATA CHECK: `check.py data` first returned 8 FAILs on hl_score / hl_state (held-position health fields, absent from a flat-book export). Fixed at source in PR #67 (c00a5400): a flat book now skips them with one WARN; re-run on main reads Healthy, 0 FAIL.
- ROOM: 51 names in the room; MTF complete. Seven deciders. Wyckoff's nomination landed after the first tally; the tally, room, MTF and the challenge were rebuilt with all seven and the challenge re-filed before anyone voted.
- FUNNEL: 156 claims, CONFIRM 107 / REFUTE 186 / CANNOT_SEE 19; 19 survivors; tier 2: ADVANCE 3 (CHYM BILL KO), WATCH 16. Slate cap 25: 19 slated, none cut by the cap.
- QA (Steenbarger): HOLD on 4 tickets (KO AEE MGNI TOST); 28 floor messages (7 deciders x 4), floor check OK; 7/7 second ratifications filed.
- RESULT (R34, by code): 7 deciders, drop at 4+ objections: AGREED 0, CONTESTED 16, DROPPED 3 (MGNI AEE TOST), NOT_SLATED 32. ADVANCE 3, all contested (BILL CHYM KO). 13 slated WATCH names ride as HOLD-FOR-CONDITIONS.
- MARKET KILL: named by one decider (oneil): "No confirmed uptrend (C1): SPY close_below ma_50"; no watchable level, a market note not an alert.
- R44: deal-pin manual override list (APO RY F COMP) applied: not deal-pinned.
- COMMITTEE POSITION (R42): rationale draft valid; RATIONALE-FINAL valid; 25 amendments attached verbatim; 28 DISSENT clauses ride as minority notes. Committee conviction: BILL 4; CHYM ABNB KO HLT LTH AJG BDX STGW CAH CHD EL ADP 3; AHR JAN VSXY 2.
- BRACKETS: 16 of 16 ADVANCE/HOLD names have a computed stop; 6 clear both the atr and reward gates; 0 sized (1R $620 is the fund file's, never changed here).
- PURITY: ranking invariant to every bracket field: PASS.
- SCORECARD: graded with the 5 Nov run's history exports (to 29 Oct) plus today's; the 30 Oct to 5 Nov exports were not re-pulled, so those runs' rows are ungraded this time (declared).
- INBOX-CLEAN: not run this run (declared).
- RUN INTERRUPTION: the account's 5-hour usage limit hit during tier 2 of Report C; its eight tier-2 seats were re-run in full after the reset. Nothing else was replayed.

CARDS FALLBACK: the v3 page was NOT published (pma_cards_v3.py exited 1:                    ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ FileNotFoundError: [Errno 2] No such file or directory: '/home/user/AQE/aegis/aegis/output/valen_dashboard.json'). The v2 page was published instead.

CARDS FALLBACK: the v3 page was NOT published (the plain-words gate FAILED on the v3 page or its words file: the rendered cards still show raw field names: close_below x52, ma_50 x52). The v2 page was published instead.
