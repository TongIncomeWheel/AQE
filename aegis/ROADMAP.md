# Aegis Build Roadmap (PM-set sequence, 19 Jul)
The agreed order of work. Migration (BL-033) is a LATE build step, not near-term.

1. **AQE spec & cleanup** — the declared data object AQE conforms to; every field's definition + method + enum; gaps listed for the AQE build track. *(in progress — AQE_SPEC.md, field_dictionary.json complete to 97 fields)*
2. **Update data dictionary & taxonomy** — refresh the bridge after the spec.
3. **Orchestration & desk audit** — audit the Chief + six-desk design for completeness and correctness.
4. **Output audit** — audit every artifact each phase produces.
5. **Persistent interface & orchestration in Claude** — how the UX, harness and orchestration platform actually work and persist.
6. **Deployment packaging with auth details** — DELIVERED (2026-07-19): aegis/INSTALL.md (AI-actionable runbook) + contracts/install_manifest.json (machine-readable twin) + aegis/.gitignore (secret guard). A fresh AI executes it phase-by-phase, stops at [PM] gates. Remaining human step: run it in a new workspace.
7. **Full UAT** — end-to-end user acceptance ahead of a trading day.

Then, and only then, the mechanical file migration (BL-033) and go-live.
