# AEGIS v4 — kernel repo
One home for the law, the process, the voices, the calculators and the contracts. Harnesses (Claude, Kimi) receive GENERATED packages — never hand-edited.

- data/ — runtime state incl. cs_weekly/ drop folder (sample Week 29 included)
- skills/ — EVERY procedure: 5 process skills + staging-gatekeeper + 10 voice skills (canon-pinned) + voice-common + 3 assurance skills
- charter/ — constitution (orchestration law) + rulebook.yaml (law) + parameters.yaml (PM-tunable, via set_param) + decisions_log
- tools/ — universe_screen · nomination_ledger · tripwires · measure_proposal · calculators/ (sizing, bs_price, hedge_engine) · mcp/ibkr_mcp (new, read-only) · catalog.md
- contracts/ — JSON schemas: aqe_export (generated from live feed) · nomination · plan · ledger · journal

- packaging/ — build_claude.py · build_kimi.py → dist/
- INTAKE/ — what the PM still needs to supply
- data/ — runtime state (created at deploy; rclone-synced to Drive)

Deploy: see DEPLOY.md (Claude project + Claude Code + Kimi CLI, step by step). Quickstart after intake: fill config/endpoints.json → `python3 packaging/build_kimi.py` → install dist/kimi per its README (or dist/claude-plugin on Claude) → shadow-run one week alongside the current system → cut over when the daily diff is boring.
