# Run declarations — PMA 2026-10-21 (for the brief header; every one must appear)
1. Skill source: plugin bundle aegis-core v5.4 (R16–R21). AQE main's premarket-analysis copy is older (v5.3, no RULINGS.yaml) — main is behind the plugin, not ahead.
2. Seat transport: compiled voice agents had no file tools in this harness (all 9 first spawns returned "not filed"). Every seat was re-spawned once as a general-purpose agent reading its OWN card + its OWN packet by path. R2 inlining replaced by path-read; figure audit (`validate --packet`) ran on every round-1 and round-2 form — 0 fabricated figures.
3. Packets: built locally by `pma_pipeline.py packets` from the trimmed universe (held floor MP injected, R12); AQE pre-sliced packets not used.
4. Fundamentals: FMP batch pulled after RANK for the 54-name room only (54/54 served), not the full universe at GATHER — declared cut.
5. Livermore: card marks the seat "NOT DECIDED / not wired" pending PM ruling; RUN.yaml seats him in NOMINATE and VOTE, so he ran. PM to rule.
6. Checkpoints: no git push after MACRO/NOMINATE/CHALLENGE/VOTE — session has read-only git to TongIncomeWheel/AQE; run sat on local disk until PUBLISH (via GitHub connector).
7. SCORECARD: not run — closes_scorecard.json (FMP EOD for every ledger + AQE list name, 10 sessions) not pulled this run; scorecard_log.jsonl NOT advanced for 2026-10-20 close.
8. REPEAT-WATCH: degraded — 805 historical (date,ticker) rows have no verdict_ledger match on main; today's 54 verdicts are recorded.
9. Broker: Tiger read-only 06:53Z. Zero working orders. `--previous` broker_stops not on main; USO vanish read from fills (STP 72 @ 156.43, 20 Oct 10:30 ET).
10. CHALLENGE packets: built by conductor from tally + menu-sliced rows (no tool exists for challenge packets); VOTE_PACKET 123 KB > 70 KB soft cap (54-name room).
