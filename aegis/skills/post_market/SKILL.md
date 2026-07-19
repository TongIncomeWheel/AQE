---
name: post_market
description: Aegis process skill — POST MARKET (04:00–10:00 SGT; autonomous). Procedure lives HERE, not in the charter. Numbers cited as RB: keys from charter/rulebook.yaml.
---

# PROCESS: POST MARKET (04:00–10:00 SGT; autonomous)
**Desk sequence (D-26/D-32):** the Chief adopts **Operations** for steps 1–2 (journal, metrics — the book of record) then **Engineering & Change** for steps 2b–3 (scorer + audit — independent assurance grades the day Operations recorded). Physical move to `orchestration/` = BL-033.
1. **Journal snap.** Reconcile fills from both brokers (execution truth), roll dynCap (RB:capital.dyncap_method), write `data/journal/aegis_journal_YYYY-MM-DD.json` (RB:journal.naming), validate vs contracts/journal.schema.json, sync/archive-commit. **Ordering rule (Arch-F9): if the journal write or validation fails, STOP — no ledger/pipeline mutation, no held-list emit; page the PM.**
2. **Portfolio metrics snap.** Exposure, leverage, NAV-β (gate window RB:risk.gates.portfolio_beta), VaR, sector concentration, stop audit (live vs reference, MATCH/MISMATCH/MISSING) → metrics file + flags.
2b. **Criteria evaluation + voice memory (D-14).** The scorer evaluates the day against RB:performance (per-voice hit/excess targets, committee precision, plan trigger quality, execution slippage, system uptime) → `scorecard.json` (contracts/scorecard.schema.json) with PASS / WATCH / FAIL verdicts; two consecutive failing windows on any voice = automatic Engineering Bench review item. Then `tools/voice_memory.py update --scorecard <scorecard>` rebuilds every voice's bounded memory (stats vs targets, open picks, last-10 outcomes, standing lessons with evidence + expiry) — what each voice reads at tomorrow's spawn.
3. **Usage & completeness audit.** Per voice and committee: ran? on time? data pulls tagged? any fabrication/staleness? → `data/audit/audit_YYYY-MM-DD.json` (RB:audit).
4. Outputs feed straight into Design & Review; PM sees everything in the 10:00 morning summary.

## ON FAILURE (RB:exceptions; records to data/eod/DATE/exceptions/)
- One broker pull fails → retry once → still down: reconcile from the other broker, journal marked PARTIAL_SOURCES; PAGE.
- Both pulls fail → journal from gatekeeper records only, marked **PROVISIONAL** → ledger/held-list mutations HALT; engine reuses last GOOD journal; PAGE.
- Journal fails validation → HALT everything downstream (already law) + PAGE.
- GitHub archive push fails → retry once → queue the commit locally; morning summary.
- Scorer/learning failures never block accounting — they defer to tomorrow and are noted.
