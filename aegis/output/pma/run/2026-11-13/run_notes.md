# Run notes 2026-11-13 (conductor)
- TRIGGER: READY watcher hand-off 07:38 SGT. Gate Healthy (AQE run finished 07:20 SGT; export 305 rows, 2 held live; committee data OK mtf 333/334, fundamentals 334/334, closes 1007).
- MACRO FRESHNESS: dispersion_vixeq and dspx one session old (publisher lag, WARN); COT 3 Nov (weekly cadence).
- BOOK (journal 12 Nov + live read-only Tiger pull 07:38 SGT): RBRK 80 stop 99.45; SPCX short -68 with a live BUY stop at 145.05 (HELD) per Tiger. The journal and the stops tool map only SELL stops, so `check.py data --broker-stops` FAILs 'SPCX: stop journal None vs broker 145.05'. This is the known short-stop mapping gap (same as 12 Nov, there 148.15), not a real disagreement; broker read taken as right and the run proceeds, DECLARED. SPCX confirmed Aegis by the PM 12 Nov.
- CLOSED SINCE YESTERDAY (journal 12 Nov, source broker_fill): EBAY 150 stopped out at 119.48 (entry 122.92, -$515.70); GPN 100 stopped out at 95.09 (entry 102.15, -$706.10). Both were protected by their broker stops, which filled.
- INBOX-CLEAN: not run (declared).
- ALERTS: paused by PM order 12 Nov (flag aqe_alerts_paused.json); published levels will not be loaded into live alerts until the PM resumes.
