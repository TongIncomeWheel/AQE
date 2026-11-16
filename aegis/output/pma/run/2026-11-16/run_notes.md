# Run notes 2026-11-16 (conductor) - Committee Standard Scan (whole_universe)
- TRIGGER: PM order 2026-11-16 (manual). The Sat 14 backstop and weekend runs were lost to the weekly usage limit; the AQE run for the Fri 13 close was forced (unforced runs skip Sun/Mon).
- METHOD: whole_universe (PM 2026-11-16). Seats keep all AQE fields; pool = 7 per-seat screens over the 1,087-row universe, top 25 each; AQE doors off; AQE tag in the write-up.
- DATA: AQE run finished 12:14 SGT; committee data OK (mtf 359/359, fundamentals 359/359). Book from journal 2026-11-13: RBRK 80 sell stop 99.45; SPCX -68 with a live BUY stop 145.05 per Tiger read 12:2x SGT (the journal and stops tool map only SELL stops: known mapping gap, declared).
- INBOX-CLEAN: not run (declared). ALERTS: paused by PM order; levels not loaded live until resume.
- NOMINATE: 7 seats filed (cap 6), hashes verified; 32 tickers nominated + 2 held = 34 in the room; AQE doors off (door flags are information only).
- SLATE: built by code (slate_gen.py from decision.json + the seats' own tier-2 words), validated OK: 9 slated, 2 ADVANCE (BTSG CDW), 7 WATCH (CHYM EXLS COLD PCOR EMBJ SN BBY); NOT_SLATED SPCX (0 support of 7). Market kill: SPY index logs 4-5 distribution days inside 5 weeks (C2).

CARDS FALLBACK: the v3 page was NOT published (pma_cards_v3.py exited 1:     buy = next(x for x in tr if x["kind"] == "close_above") StopIteration). The v2 page was published instead.
- DECIDE (16 Nov): QA held COLD, BTSG, CHYM; floor2 21 messages + ratify2 7 forms, all hashes verified. ratify-count: 0 AGREED; CONTESTED 6 (CDW ADVANCE; EXLS PCOR EMBJ SN BBY HOLD-FOR-CONDITIONS); DROPPED 3 (CHYM BTSG COLD); SPCX not slated. Rationale/adopt/final/position: no gaps.
- SCORECARD: graded 4 runs (10-13 Nov), asof 13 Nov close, refused 0.
- BRIEF: gate 0 FAIL; scan_funnel.md sits at the top of Appendix A (seat names in it fail QX2 in the body). Module C degraded: report C not yet run for 16 Nov.
- CARDS FALLBACK: pma_cards_v3.py crashed (StopIteration in hold_row: PCOR has no shared close_above buy line); v2 page rendered, which carries no funnel. ENG asked for a patch; v3 re-render pending.
