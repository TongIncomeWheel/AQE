# PMA run notes — Wed 28 Oct 2026 session (run dir d28)

Conductor notes, written before WRITE. Every item below is a declared item for the brief header.

## Declared items
- LEDGER SOURCE (GATHER ticked degraded): verdict_ledger and phase4_ledger were read from AQE main `aegis/output/pma/run/2026-10-27/`, not the canonical `aegis/data/pma/` path, because the 27 Oct canonical push is held for the PM's yes. Content is byte-identical to the local d27 copies (md5 verified).
- NO MID-RUN CHECKPOINT PUSHES, by design: `git_sync.py` default paths include `aegis/data`, which is held for PM approval and would rebuild the HF Space. The run sat on local disposable disk until PUBLISH. One consolidated push at PUBLISH, under `aegis/output/pma/` only, with read-back verification.
- CANONICAL RECORD PUSH PENDING PM YES: `aegis/reports/pma/2026-10-28.md` + `latest.md`, `aegis/data/pma/{verdict,phase4}_ledger.json`, `data/pma/2026-10-28/`. Until pushed, tomorrow's GATHER again reads the run/ copy and repeat-watch keeps showing ledger gaps for older dates.
- SEAT TRANSPORT: seats ran as general-purpose agents reading their own card + packet by path. Lynch is consulted only (R22): 10 voters.
- FUNDAMENTALS PACK: 121 names = 98 carried from the 27 Oct pack + 23 newly seated names pulled fresh on 28 Oct after RANK (profile, metrics-ratios-ttm, income growth x3). 0 gaps. HNGE's 2023 growth row is zero-filled by FMP (IPO 2025), left as returned. FMP's quote tool is not on the plan.
- CHALLENGE FORMS ARE NOT COVERED BY THE FIGURE AUDIT (no registrar validate mode for them). The conductor traced every figure by hand (`ch_trace_round.py`, rounding-tolerant). Lynch: all traced except 3 items: the prompt's own broker stops (V 391.80, MP 36.66) and ETSY -2.21, a 0.01 misround of -2.2048. Detect-lens: three derived room means (2.09, 2.27, 0.46) are labelled "computed from packet rows" (derived arithmetic, declared).
- VOTE PACKET is 133,534 bytes, over the soft 70,000 limit (normal; 27 Oct was 135,776). Not trimmed.
- V LIVE PRICE: the export's held-row live_px for V reads 401.86 = the 27 Oct close (matches the FMP close). Tiger's mark of 397.25 at 06:42Z 28 Oct is a pre-market mark, so not a data fault.
- BROKER (read-only, 2026-10-28T06:42Z): V 38 sh STP_LMT GTC stop 391.80 limit 390.80; MP 300 sh STP_LMT GTC stop 36.66 limit 36.66. The book is MP and V only: no entry was taken in the Tue 27 Oct US session.
- SEOW filed 0 nominations in round 1 (its CCI set-up leg failed on every row). A valid, declared output. At VOTE Seow stated that ma_40 and CCI are not served by AQE and capped convictions at 3.
- DETECT-LENS treated nine rows with four of six lens reads showing '--' (HOG, CART, ETSY, BBWI, BILL, BRZE, NTSK, ASAN, KVYO) as a feed gap (absence is not agreement) and abstained on all but CART.
- SEAT ISOLATION: Wyckoff opened registrar.py (head and a grep) and listed the filenames in forms/r2/ (no other seat's content read); Seow read the first 60 lines of registrar.py. Neither changed any vote; all ballots passed the figure audit.
- THORP's first part 1 was rejected by the registrar for quoting another ticker's figure inside the APLE row ("FABRICATED FIGURE"). Re-filed and passed.
- SCORECARD: grades 8 runs (15 to 27 Oct) as of the 27 Oct close, horizon 5 sessions, beta cap 2.5. 536 closes loaded; the 27 Oct closes for 501 symbols come from the export's last_close (spot-checked 80 of 80 equal to the FMP close) plus single-symbol FMP pulls. 0 rows refused; 178 ungraded rows have no session after the run yet.
- REPEAT-WATCH reports 452 ledger gaps for dates that predate the verdict ledger (normal).
- PACKETS: no stamp file shipped on main; md5 recorded at PREPARE (`packets_manifest.json`).
- INBOX-CLEAN: 20 [AQE] threads trashed. One GitHub notification left untouched by rule: "[TongIncomeWheel/AQE] Run failed: AQE voice packets sync - main (9620f43)". Not checked by this run; flagged to the PM.
- PURITY: invariance PASS. Crowding audit: top-5 by seats are 40% bracket-valid against 18% across all 11 qualifiers (gap +22%); no sign consensus tracks bracket availability.

## Open PM decisions (not for the committee, listed in the plan's open items)
1. Push the canonical record paths to AQE main (rebuilds the HF Space).
2. VSXY stop choice from 27 Oct (91.60 vs the committee's 88.64). VSXY is not in today's room.
3. Whether to arm ESTC, or to preview HOG / A (nothing is armed; any order only through the Tiger preview and the PM's explicit "confirm").
4. The GitHub "AQE voice packets sync" failure (9620f43) is unchecked.
5. The ESTC LOCK (PM 28 Oct 01:30 SGT) and the HOG / A focus (PM 28 Oct 01:35 SGT) are dated to the 27 Oct session; they need re-dating or release for tonight's reviews.
