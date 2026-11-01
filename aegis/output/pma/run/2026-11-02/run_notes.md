# PMA run notes — Mon 2 Nov 2026 (run for the 2 Nov US session on the Fri 30 Oct close)

First automated pilot, fired on the PM's direct instruction in the conductor session ("Fire it now", ~06:05 SGT).

## Declared items
- DATA: AQE export run 2026-11-02 (exported 02:59:37 SGT) carrying the Fri 30 Oct close (unr_as_of 2026-10-30), 257 rows, 0 data-quality flags, held MP+V live; check.py ready + data Healthy. Crown DEGRADED (declared by AQE).
- LEDGERS: from aegis/output/pma/run/2026-10-29/ (last PMA run); canonical aegis/data/pma stops at 28 Oct. No PMA ran for the 30 Oct session.
- SEAT TRANSPORT: path-read per RUN.yaml (standard since 2026-10-21): each seat read its own generated agent card + voice-common + its canon lock + schema + its own packet by path. Packets total 721KB, so inlining was not workable.
- METER BASIS: seats metered on the registrar's byte basis (inlined file bytes + returned form bytes / 4), the basis the 1,357,500 ceiling was calibrated on. GATHER carries the data-steward's ACTUAL subagent tokens (411,931, sonnet). Actual subagent tokens are logged below and reported at DONE.
- INBOX-CLEAN: 37 trashed (36 from AQE Alerts + 1 self-forwarded [AQE] subject), 6 GitHub [TongIncomeWheel/AQE] notifications left untouched, 0 remaining.
- BROKER (Tiger read-only 06:16 SGT): V 38 sh STP_LMT GTC stop 391.80 lmt 390.80; MP 300 sh STP_LMT GTC stop 36.66 lmt 36.66.
- CLOSES: 459/459 symbols served 14-30 Oct; ACA only through 22 Oct. Cross-check vs export last_close on 257 names: 0 mismatch.
- FUNDAMENTALS: deferred to post-RANK for the deliberation set (connector is single-symbol).
- NOMINATE seat notes: minervini read packet columns off its card menu (ma_150, low_52w, pct_from_52w_high, rs_rank_pct, pivot_high, pct_from_pivot, elder_context.vcp) and declared it; oneil read pivot_high/pct_from_pivot (named in its card R5, not on its menu) and declared it; raschke first two filings rejected for reason length only; wyckoff filtered the packet by grep rather than reading every row, declared, 5 nominations with shortfall.

## Actual subagent tokens
- data-steward closes (sonnet): 411,931
- NOMINATE: oneil 190,459 · minervini 213,374 · livermore 175,177 · elder-lens 171,508 · seow 208,584 · raschke 181,673 · wyckoff 200,187
