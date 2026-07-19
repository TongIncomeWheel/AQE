---
name: ops-status
description: Renders the /ops card (D-45) — the one-glance SYSTEM liveness view (is the machinery alive, did the loops fire, is the state fresh, are the alert channels up). The operational sibling of /status (which is the BOOK cockpit). Triggers on "/ops". Reads TODAY'S FILES from the workspace (never conversation state, G3), so it is correct in any fresh chat. Reuses tools/daily_flow_audit.py — does not re-reconstruct the flow. Owned by Engineering & Change (self-heal + assurance); read-only, places/sizes/arms nothing (constitution law 1).
---

# /ops — is the system alive?

`/status` shows the **book**. `/ops` shows the **machine**: are the scheduled loops
firing, when did each last run and when's the next, is the data underneath fresh,
is self-heal current, and are the alert channels up. Read-only. It never places,
sizes, or arms anything (constitution law 1).

## What it runs

- **`/ops`** → `python3 tools/ops_status.py` — the token-cheap in-chat card:
  overall status (ALIVE / PARTIAL / DEGRADED), dynCap + open count, historical
  store size + last self-heal, kernel commit, layers that ran vs sat idle today,
  open exceptions, and whether the WhatsApp + watchdog channels are configured.
- **`/ops --render`** → `python3 tools/ops_status.py <today> --render` — also
  writes the full HTML dashboard to `data/eod/<date>/ops_status_<date>.html`
  (the same flight-recorder idiom as the daily flow audit).

## Doctrine

- **Reuse, not clone.** The "what ran today" reconstruction comes from
  `tools/daily_flow_audit.py` (D-43). This skill adds live liveness/freshness on
  top; it does not re-implement the audit.
- **Fail-visible (law 3).** Anything it can't read is marked **PARTIAL** and
  listed — never faked. A `PARTIAL` card is a real signal (a channel is down, a
  file is missing), not a cosmetic state.
- **Order-blind (law 1).** Surfaces state only. For a manual fix, see the
  `recover` skill (`/heal`, `/recover`, `/repull`, `/reseed`).
