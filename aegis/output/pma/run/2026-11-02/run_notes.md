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
- CHALLENGE: steenbarger 127,563
- FUNDAMENTALS steward (sonnet): 284,871 (39/39 served; ABBV ratios + FLYW growth spot-checked exact vs FMP)
- VOTE: oneil 217,505 · minervini 209,093 · livermore 206,347 · elder-lens 194,459 · seow 219,122 · raschke 210,665 · wyckoff 204,037
- VOTE seat notes: room 39 > 30-vote cap, every seat filed 2 parts (20+19); merge proves coverage. Size-cap re-files (text trimmed, no vote changed): livermore p1 x2, raschke p1 x1, oneil p1 x2, seow p1 x4 (over the 3-attempt brief, declared). Wyckoff: vote packet carries pvp_/bar_ fields only for its own nominees; other reads declared in cannot_see. O'Neil declared the fundamentals line off its menu. VOTE_PACKET 78,412B over the 70,000 soft cap, not trimmed.
- METER: commit adds each form's bytes to returned_bytes and the meter call adds them again, so NOMINATE/VOTE returned bytes are double-counted (conservative).
- HALTED before FLOOR at 06:43 SGT: est 1,219,340 vs ceiling 1,357,500; FLOOR (8 seats x 277KB board) projected to cross it. Awaiting PM.
- PM 06:50 SGT (in session): "Continue. We look at optimisation later, the critical part now is to prove the PMA can be produced for my quality review and reverse QA on the orchestration and deliberation process" -> spend ceiling lifted for this run. FLOOR run as Chair board post + 2 decider waves (open, then reply) so the exchange is real; 15 spawns vs RUN.yaml's 8, declared.
- FLOOR: chair 137,399 · wave1 oneil 170,312 minervini 183,060 livermore 169,169 elder-lens 169,881 seow 178,754 raschke 171,153 wyckoff 172,112 · wave2 oneil 140,379 minervini 142,346 livermore 133,459 elder-lens 127,744 seow 139,315 raschke 143,414 wyckoff 136,945 · steenbarger 108,146
- FLOOR notes: 2 waves (open + reply) + Steenbarger called on by name 10x (8 replies, MP/MA each answered once for two askers). One reply per ticker per wave meant some messages went unanswered (e.g. raschke-CHD-1 and seow-WMT-1 to livermore). Steenbarger reports NTSK divergence caution unread by any seat.
- FLOOR result: 151 msgs, floor-check OK, changed_mind 0 of 151 (QA observation), silent name: VG
- SLATE: chair (tokens in final report). 15 = cap; WATCH rule = >=half of supporters' triggers wait on a condition (Chair's counting rule, declared; TAK/GEN even split). Chair ran one stray wc -c.
- RATIFY: oneil ~(final) · minervini 103,342 · livermore 112,581 · elder-lens 107,852 · seow 125,393 · raschke 124,198 · wyckoff 117,305 · SLATE chair 210,813
- RATIFY result: 0 OBJECT across 105 answers. Recurring reservations: ADVANCE triggers read as a chase on MA/TTEK/SN (minervini, wyckoff, raschke); WATCH-vs-buy-stop-now on HOG/TAK (seow); missing seat entries on the ticket (elder-lens pullback-to-ma_20; elder-lens + seow V TIGHTEN line; raschke HOG reclaim and ABBV session-3 exit; oneil market-gate on FLYW).
