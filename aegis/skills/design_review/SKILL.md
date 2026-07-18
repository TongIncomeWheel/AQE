---
name: design_review
description: Aegis process skill — DESIGN & REVIEW (after post-market; autonomous; asks land in the 10:00 summary). Procedure lives HERE, not in the charter. Numbers cited as RB: keys from charter/rulebook.yaml.
---

# PROCESS: DESIGN & REVIEW (after post-market; autonomous; asks land in the 10:00 summary)
Owner: Assurance & Improvement agents.
1. **Assurance report.** Process compliance, skill usage, completeness of voices vs tickers analysed (from post-market audit).
2. **Performance measurement.** Today's actual runners vs what AQE surfaced and what the committee nominated — did the system SEE the winners? (Ledger + AQE export comparison, `tools/nomination_ledger.py report`.)
3. **Learning pass.** RB:audit.learning_lookback_days window: winners' fingerprints vs our nominations; misses classified (not in universe / in universe not nominated / nominated not deliberated / deliberated not advanced / advanced not actioned) — each class has a different fix.
4. **Backlog.** Findings become backlog items and enter the DEVELOPMENT skill's pipeline (capture → PM approve → branch build → verify/shadow → ship → remember). Design & Review only CAPTURES; the development skill owns everything after. It also re-measures items 15 sessions post-ship: did the promised effect appear?
5. **Proposal measurement.** Any field-conditional idea gets measured on the enriched panel BEFORE committee vote (`tools/measure_proposal.py` — the BULLISH_BOS lesson, permanent).
