# PMA run notes -- Thu 5 Nov 2026 (for the 5 Nov US session, on the Wed 4 Nov close)

## Declared items
- DATA: AQE run 2026-11-05 (started 06:25, exported 06:44 SGT) carrying the Wed 4 Nov close; committee data OK: fundamentals 392/395, mtf 395/395, closes 708/708, published 5/5; voice packets 8/8.
- BOOK AND STOPS: from the 4 Nov journal (Tiger working orders read at the close), no live broker read this run. Book is V only: 38 sh, STP GTC 414.45. MP was stopped out on 4 Nov (-$4,902 at 36.66); the book no longer holds it.
- ROOM: 46 names in the room; MTF complete. Slate cap 25; 12 survivors, 0 excluded by the cap.
- QA (Steenbarger): HOLD on 5 tickets (BBY DG USFD WCN KDP). 35 floor messages (7 deciders x 5 tickets), floor check OK; 7/7 second ratifications filed. The ticket text is not amended (no held-ticket revision step in code).
- RESULT (R34, by code): 7 deciders, drop at 4+ objections: AGREED 1 (KO), CONTESTED 10 (ABBV CAH GLBE MFC CCEP BBY DG BALL KDP WCN), DROPPED 1 (USFD, 4 objections), NOT_SLATED 34. ADVANCE 10 (KO ABBV CAH GLBE MFC CCEP BBY DG BALL WCN); KDP is HOLD-FOR-CONDITIONS.
- R44 (deal-pinned): no ADVANCE name is pending-M&A. KDP carries ma_status PENDING_UNCLEAR, so it rides as HOLD-FOR-CONDITIONS, not ADVANCE. Manual override list (APO RY F COMP) applied: not deal-pinned.
- BRACKETS: 11 of 11 ADVANCE/HOLD names have a computed stop; only 2 clear both the atr and reward gates; 0 sized (1R $620 is the fund file's, report never change).
- MARKET KILL (declared): named by one decider (oneil), no symbol, word or watchable level; a market note, not an alert.
- COMMITTEE POSITION (R42): rationale draft valid; RATIONALE-FINAL valid; 26 amendments attached verbatim; 13 DISSENT clauses ride as minority notes. Committee conviction: CAH GLBE BBY DG 4; KO ABBV MFC CCEP BALL KDP 3; WCN 2.
- SCORECARD: graded 2025 rows over 13 runs (asof 2026-11-04), refused 0, ungraded 331 (earlier run exports rebuilt from main's git history). Advance n=107 vsSPY +0.68; Near-miss n=1446 vsSPY +1.23.
- INBOX-CLEAN: not run this run (declared).

CARDS FALLBACK: the v3 page was NOT published (pma_cards_v3.py exited 1:                    ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ FileNotFoundError: [Errno 2] No such file or directory: '/home/user/AQE/aegis/aegis/output/valen_dashboard.json'). The v2 page was published instead.

CARDS FALLBACK: the v3 page was NOT published (the plain-words gate FAILED on the v3 page or its words file: the rendered cards show committee jargon OUTSIDE the folded audit trail: C2 x1). The v2 page was published instead.
