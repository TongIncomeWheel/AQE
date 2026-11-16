# Run notes 2026-11-17 (conductor) - Committee Standard Scan (whole_universe)
- TRIGGER: READY watcher hand-off 07:38 SGT (READY + data handoff Healthy); routine AEGIS pma-auto enabled.
- DATA: AQE run 2026-11-17 finished 07:17 SGT; 215 names, candidate set 215; committee data OK. Book from journal 2026-11-16: RBRK 80 sell stop 99.45; SPCX -68 with a live BUY stop 145.05 per Tiger read 07:4x SGT. Declared known mapping gap: the journal and the stops tool map only SELL stops, so check.py data shows "SPCX: stop journal None vs broker 145.05"; the broker side is the one with the working order, not a loosened stop. Proceeding, declared (same as 13 and 16 Nov).
- INBOX-CLEAN: not run (alerts paused by PM order, no [AQE] mail generated). ALERTS paused: levels published but not watched live until the PM resumes.
- Crown DEGRADED (declared by the nightly); positioning_cot as of 2026-11-10 (weekly cadence).
