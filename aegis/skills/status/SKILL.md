---
name: status
description: Renders the /status card (D-22, G5) — the one-glance consolidated view of the Aegis book. Triggers on "/status". Reads TODAY'S FILES from the persistent Cowork workspace (never conversation state, G3), so it is correct in any fresh chat. Owned by the Chief cockpit; read-only, places nothing.
---

# SKILL: /status — the consolidated cockpit card (D-22 / G5)

## What it is
The single card that answers "where do things stand" at a glance: open Aegis positions + P&L, autopilot armed-state + expiry, alerts armed/fired, and the plan headline. It is the union of `/fa` + `/ap` + `/watch`, rendered — the artifact the PM asked to be able to *visualize*.

## Reads (from the persistent workspace — NOT chat memory, G3/G1)
All from today's shelf in the Cowork workspace, so a brand-new chat renders correctly:
- `data/persistent/autopilot.json` (via `tools/autopilot.py status`) — armed?, expiry, orders used/max. Fail-safe OFF on any read error.
- `data/persistent/dyncap_ledger.json` (via `tools/dyncap_ledger.py`) — dynamic capital; shows "awaiting allocation" if unset (BL-030).
- The Aegis book — the latest Aegis PTJ (source of truth, D-21); positions + unrealised.
- Today's `plan_YYYY-MM-DD.json` — headline + counts (advancing/watch), approval status.
- Today's intraday alerts record — armed names + fires so far.

## Renders
A self-contained HTML card (the fixed D-22 layout): header (deployment · armed pill · date) → autopilot → weather → positions & P&L (Aegis sub-fund only, never co-mingled) → alerts → "do next" command row. Delivered to the PM inline. Missing inputs render as an explicit "awaiting …" line, never a blank or a guess.

## Rules
- Read-only. Places, sizes, arms nothing. Toggles are their own commands.
- AEGIS-scoped only (D-17/D-21) — never show co-mingled broker totals as Aegis.
- If a source file is missing/stale, say so on the card (fail-visible), don't fabricate.
