---
name: live-review
description: "Aegis LIVE REVIEW — the 30-minute executive review during the US session (11 slots 21:31–02:31 SGT on US daylight time, +1h on standard time) plus the 04:05 relay. Reads the day's pma_levels.json, live IBKR prices, the AQE alert notice (tools/aqe_notice.py; Gmail [AQE] only as fallback) and the Tiger book, runs tools/exec_review.py, and prints triggers and actions only. READ-ONLY: places nothing, sizes nothing. Triggers: live review, executive review, 30-min review, /review, relay."
---

# LIVE REVIEW (aegis-live)

**The procedure is `REVIEW_SPEC.md` in this folder. Read it first and follow it exactly.** This card only maps it to the plugin.

| Spec says | In this plugin |
|---|---|
| `/home/claude/pma/live/exec_review.py` | `${CLAUDE_PLUGIN_ROOT}/tools/exec_review.py` |
| `ibkr_conids.json`, `pm_watch.json`, `arm_brackets.json` | `${CLAUDE_PLUGIN_ROOT}/config/` |
| `/home/claude/pma/live/work/`, `review_state.json` | `$AEGIS_LIVE_DIR` (any writable dir that persists across the session) |
| `/home/claude/pma/dNN/pma_levels.json` | today's PMA run dir, or `TongIncomeWheel/AQE@main aegis/output/pma/pma_levels.json` |
| `send_later` relay | the harness's own scheduler (cron, GitHub Actions or a scheduled task): 11 reviews + 1 relay per session |

Always pass `--watch`, `--state` and `--export` explicitly. The script's defaults point at the claude.ai container.

## Inputs this skill depends on (produced elsewhere)
- `pma_levels.json`: written by `/pma` LEVELS and published at PUBLISH (aegis-core).
- Market gates `--floor` / `--flip`: from that run's card report, Part 1 Daily Weather (GEX block).
- `aegis/output/alerts/live/latest.json` on `main`: the AQE alert engine's per-cycle notice (contract `aegis-core/contracts/aqe_alert_notice.schema.json`), read by `tools/aqe_notice.py`.
- Connectors: IBKR `get_price_snapshot` (live price, never FMP delayed), FMP `intraday-1-hour`, Tiger read-only; Gmail search only as the fallback when no notice is published.

## Hard rules
- Read-only. Any order goes only through the Tiger preview and the PM's explicit "confirm" (aegis-core staging-gatekeeper law).
- 1R = $620 (PM 2026-10-27). Share count = floor(620 / (price − stop)), arithmetic only.
- Output is triggers and actions only. If nothing happened, print one line.

## Config files are dated snapshots
`pm_watch.json` (26 Oct) and `arm_brackets.json` (session 27 Oct) are the last versions the PM set. The script ignores `arm_brackets.json` when its `session` is not today's date. Update both from the PM before the next session.
