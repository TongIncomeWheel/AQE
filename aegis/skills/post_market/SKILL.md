---
name: post_market
description: Aegis process skill — POST MARKET (04:00–10:00 SGT; autonomous). Procedure lives HERE, not in the charter. Numbers cited as RB: keys from charter/rulebook.yaml.
---

# PROCESS: POST MARKET (04:00–10:00 SGT; autonomous)
Owner: Post-Market Orchestrator.
1. **Journal snap.** Reconcile fills from both brokers (execution truth), roll dynCap (RB:capital.dyncap_method), write `data/journal/aegis_journal_YYYY-MM-DD.json` (RB:journal.naming), validate vs contracts/ptj.schema.json, sync to Drive.
2. **Portfolio metrics snap.** Exposure, leverage, NAV-β (gate window RB:risk.gates.portfolio_beta), VaR, sector concentration, stop audit (live vs reference, MATCH/MISMATCH/MISSING) → metrics file + flags.
3. **Usage & completeness audit.** Per voice and committee: ran? on time? data pulls tagged? any fabrication/staleness? → `data/audit/audit_YYYY-MM-DD.json` (RB:audit).
4. Outputs feed straight into Design & Review; PM sees everything in the 10:00 morning summary.
