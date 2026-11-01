# PMA run notes — Thu 29 Oct 2026 session (run dir d29)

Conductor notes, written before WRITE. Every item below is a declared item for the brief header.

## Declared items
- DATA: AQE export dated Thu 29 Oct 08:51 SGT carries the Wed 28 Oct close (the FOMC day; the decision landed at 14:00 ET inside that session). 215 daily-list names, 0 data-quality flags, unr_as_of 2026-10-28 on every row. Engine run status success, voice packets 12/12.
- LEDGERS: verdict_ledger and phase4_ledger read from the canonical AQE main path aegis/data/pma/ (the 28 Oct canonical record was pushed in commit da7c709 on the PM's approval). No ledger-source degradation today.
- NO MID-RUN CHECKPOINT PUSHES, by design: git_sync.py default paths include aegis/data, which rebuilds the HF Space. The run sat on local disposable disk until PUBLISH. One consolidated push at PUBLISH under aegis/output/pma/ only, with read-back verification. The canonical record paths (aegis/reports/pma/, aegis/data/pma/, data/pma/2026-10-29/) are held for the PM's yes, as on 28 Oct.
- SEAT TRANSPORT: seats ran as general-purpose agents reading their own card + packet by path. Lynch is consulted only (R22): 10 voters.
- FUNDAMENTALS PACK: 141 names = 121 carried from the 28 Oct pack + 20 newly seated names pulled fresh on 29 Oct after RANK (profile, metrics-ratios-ttm, income growth x3). 0 gaps. GMAB's 2025 growth row is in USD while earlier rows are DKK (FMP), so its 2025 revenue growth is distorted by the currency switch; EQH and CCI carry negative-equity ratios. Left as returned.
- CHALLENGE FORMS ARE NOT COVERED BY THE FIGURE AUDIT (no registrar validate mode for them). Not hand-traced today; their figures are the seats' own reading of their packets.
- VOTE PACKET is 130,531 bytes, over the soft 70,000 limit (normal; 28 Oct was 133,534). Not trimmed.
- BROKER (read-only, 2026-10-29T04:14Z): V 38 sh STP_LMT GTC stop 391.80 limit 390.80; MP 300 sh STP_LMT GTC stop 36.66 limit 36.66. No entry was taken in the Wed 28 Oct US session (no Aegis fills in Tiger; the only fills are Project MD options, not Aegis).
- SCORECARD: grades 9 runs (15 to 28 Oct) as of the 28 Oct close, horizon 5, beta cap 2.5. 573 symbols; the 28 Oct closes come from the export's last_close (215) plus 357 single-symbol FMP pulls; ACA returned no FMP row (null). 0 rows refused; 40 ungraded.
- REPEAT-WATCH reports 398 ledger gaps for dates that predate the verdict ledger (normal).
- PACKETS: no stamp file shipped on main; md5 recorded at PREPARE (packets_manifest.json).
- INBOX-CLEAN: 18 [AQE] threads trashed, 0 remaining. Two GitHub notifications left untouched by rule: "[TongIncomeWheel/AQE] Run failed: AQE voice packets sync - main" for 9620f43 and for da7c709. Not checked by this run; flagged to the PM.
- PURITY: invariance PASS. Crowding audit: top-5 by seats are 0% bracket-valid against 21% across all 14 qualifiers; no sign consensus tracks bracket availability.
- SEAT NOTES: O'Neil's first part-1 ballot was rejected by the registrar for a threshold written as a figure ("day_vol 1.40"); re-filed, no figure changed. Raschke's card says ADX is not served but the packet now carries adx_14 (card is stale; level used, slope declared not served). Seow and Elder-lens note ma_40, cci_20 and elder_5d are not served on the held rows MP and V. Detect-lens flags seven names (HOG, EOG, CDW, CSX, BRZE, GMAB, BBWI) whose lens block reads '--' on four of six lenses (a feed gap, not agreement).
- CROWN ARTIFACT (seat report): read_me_first says the size cut is "because the trend is crowded", but trend funds show 0 of 18 markets at an extreme (dial 1.00), so the 0.50x comes from the family cap; and the QQQ call wall 720 sits at the same strike as the put wall. Both listed in the Crown form's limits.

## Open PM decisions (not for the committee, listed in the plan's open items)
1. Push the canonical record paths for 29 Oct to AQE main (rebuilds the HF Space).
2. VSXY stop choice from 27 Oct (91.60 vs the committee's 88.64). VSXY is not in today's room.
3. The PM's overnight overrides (ESTC LOCK with the VWAP dip version, HOG/A focus, GTLB watch, cyber do-not-chase) are dated to the 28 Oct session; re-date or release them for tonight's reviews. ESTC is not in today's room (logged as a near-miss).
4. The GitHub "AQE voice packets sync" failures (9620f43, da7c709) are unchecked.
5. Whether to add AXGN to the watch (raised 28 Oct, unanswered).
- TOOL GAP (LEVELS): V is HOLD-FOR-CONDITIONS on the ADD question, but `pma_cards.py triggers` only builds an add card for a held name when the verdict is ADVANCE, so LEVELS refused the file ("V: HOLD with no trigger and no not_structured_yet reason"). Fixed at the card file: a V hold card with no trigger and a stated not_structured_yet reason (no shared buy level; the broker stop 391.80 is the exit). V's alert row is therefore watched as a held name only. The code fix belongs in pma_cards.py.
- PUBLISH: pushed under aegis/output/pma/ only (commit 90732e8): pma_levels.json, levels/2026-10-29.json + support (cards, broker stops), levels_parts transport copy (6 parts), scorecard/2026-10-29.md, scorecard_log.jsonl, run/2026-10-29/ (ledgers, brief, run notes). Read-back: pma_levels parsed-equal, 0 blob mismatches. Canonical record paths NOT pushed (held for the PM's yes).
- LIVE REVIEW SPEC updated for tonight (d29 plan, SPY floor 750 / flip 773.51, QQQ 720 / 726.74); IBKR contract ids added for EMR, CDW, NTSK.
