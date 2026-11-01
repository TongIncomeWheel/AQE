# Stop reconcile: file contracts and rules

## Input files

`positions.json`
```json
{"as_of": "ISO time", "positions": [{"symbol": "NTRA", "qty": 17, "mark": 428.80}]}
```

`tiger_orders.json` (SELL stop orders only; `side` optional, defaults to SELL)
```json
{"as_of": "ISO time", "orders": [
  {"id": "4472...", "symbol": "NTRA", "type": "STP_LMT", "qty": 17,
   "limit_price": 372.15, "stop_price": null, "status": "HELD"}]}
```
`stop_price` stays null because the Tiger MCP does not return it. If the MCP server is later changed to return the trigger, populate it: the script then uses `stop_price` and reports `trigger` instead of `limit-only`.

`committee_stops.json`
```json
{"as_of": "2026-09-26", "source": "pma_brief_2026-09-26 section 9A",
 "stops": {"NTRA": {"level": 399.42, "basis": "close", "action": "HOLD", "note": "trail"},
           "WEAT": {"level": null, "basis": null, "action": "EXIT", "note": ""}}}
```

## Status table

| Status | Meaning | Proposal |
|---|---|---|
| `ALIGNED` | Tiger within tolerance (default 0.5%) of committee | none |
| `TIGER_TIGHTER` | Tiger stop above the committee level | none (ratchet: stops only rise) |
| `TIGER_LOOSER` | Tiger stop below the committee level | RAISE to the committee level |
| `BREACHED` | Mark at or below the committee level | none; exit-or-override is the PM's call |
| `NO_TIGER_STOP` | Position has no working stop | PLACE if a committee level exists below the mark; otherwise PM decision |
| `COMMITTEE_EXIT` | Committee says EXIT with no level | none |
| `NO_COMMITTEE_LEVEL` | Held at Tiger, not in the committee's book | none |
| `TIGER_TRIGGER_HIDDEN` | Plain `STP` order; Tiger returns no price | none; cannot reconcile |

For a stop-limit the limit is shown with an asterisk. A sell stop-limit's trigger is at or above its limit, so a `TIGER_TIGHTER` verdict is safe and a `TIGER_LOOSER` verdict can be slightly pessimistic.

## Ticket guards

- level must be below the live mark
- level must not be below the current Tiger level unless the row carries `allow_lower: true`
- `qty` on the approval row must equal the held quantity
- committee data older than `--stale-days` (default 3) refuses unless `--allow-stale`
- amend order: cancel, then place, then verify; never the reverse

## Verify statuses

| Status | Meaning | Urgency |
|---|---|---|
| `OK` | New stop-limit with the expected limit and qty is working, old order gone, position qty unchanged | none |
| `NOT_REPLACED` | Old order still working, new one absent | act |
| `UNPROTECTED` | No stop working on the symbol | urgent |
| `DOUBLE_SELL_RISK` | Old and new both working: oversell risk | urgent |
| `MISMATCH` | Anything else | investigate |

## Why ratchet-only

A stop that only ever moves up protects a gain and cannot be quietly loosened by a stale level or an error. Loosening is a conscious PM decision: set `allow_lower` on that row alone.

## Why the PM approves levels, not tables

A table is context. Approval is a specific level for a specific symbol. Approving "the proposals" invites the system to decide which levels were meant; approving "NTRA at 399.42" does not.
