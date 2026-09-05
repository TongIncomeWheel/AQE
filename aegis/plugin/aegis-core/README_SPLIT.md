# aegis-core — process and orchestration

**Layer: PROCESS. kernel_build `86525f9`.**
The voices are NOT in this plugin. They ship in `aegis-voices`, cut from the same build and
carrying the same `kernel_build` stamp. Install both; verify the stamps match.

Removed from this plugin at split time: 13 `agents/voice-*.md` and the
voice methodology skills including `voice-common` (the shared voice engine travels with the
voices, so the knowledge layer stands alone).

Retained: the loops (premarket, market_hours, post_market, weekly, design_review), the
desks, `committee-desk` (deliberation is process, not voice), `staging-gatekeeper` (the sole
order path), and the supporting tooling and contracts.
