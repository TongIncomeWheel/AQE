# Run notes 2026-11-12 (conductor)
- TRIGGER: pma-auto 08:20 SGT backstop. First pass blocked at the handoff gate (Cboe dispersion/DSPX one session behind two nights, publisher timing); engineering PR #93 turned that into a labelled WARN; gate then Healthy at 08:34 SGT. Started 08:35 SGT.
- DATA: AQE run 2026-11-12 finished 07:33 SGT, committee data OK (fundamentals 484/485, mtf 484/485, closes 995/995). Macro: dispersion_vixeq and dspx one session old (publisher lag); COT 3 Nov (weekly cadence).
- BOOK (journal 11 Nov + live read-only Tiger pull 08:36 SGT): EBAY 150 stop 119.49, GPN 100 stop 97.45, RBRK 80 stop 99.45 (all three now protected at the broker); SPCX -68 (short, auto-included unrecognised fill) has a live BUY stop at 148.15 per Tiger but broker_stops reads 'no stop' because the stops tool only maps SELL stops: declared; PM to confirm SPCX is Aegis.
- INBOX-CLEAN: not run (declared).
- LEDGER: the phase-4 ledger step was not run on 11 Nov; backfilled 11 Nov rows today before repeat watch (11 Nov's published repeat counts were computed without its own day).
- SPCX row in held_table.md hand-corrected by the conductor: it is a short with a live BUY stop at 148.15 (Tiger read 08:36 SGT); held_view maps only SELL stops and printed NO STOP / SET-STOP / negative dollars. Engineering to handle shorts.
