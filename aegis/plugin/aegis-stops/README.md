# aegis-stops

Reconciles the working stop orders at Tiger against the committee's stop levels for Aegis cash equities, then turns PM-approved levels into amend requests for the staging-gatekeeper.

Installs alongside `aegis-core`, `aegis-daily` and `aegis-voices`. It adds one skill, `stop-reconcile` (trigger: `/stops`).

## What it does

1. Pulls Tiger's positions and working stops (fresh).
2. Loads the committee's stop levels from the latest PMA brief, journal or mechanical floor.
3. Classifies every name, proposes raises only, and flags unprotected, breached and unreconcilable names.
4. On the PM's explicit approval of specific levels, writes amend requests (cancel, place, verify) for the gatekeeper, or a manual Tiger checklist.
5. Verifies the book against the request once the PM has released it.

## What it never does

Cancel, place or amend an order. It is read and compute only; order entry stays with the staging-gatekeeper and the PM.

## Requirements

- Tiger MCP connector (`get_stock_positions`, `get_open_orders`, `get_account_summary`)
- Python 3 in the session sandbox (standard library only)

## Known gaps

- The Tiger MCP does not return stop trigger prices. Fix on the MCP server: return the order's `aux_price` as `stop_price`.
- Tiger has no amend call, so an amend is cancel then place.
- Committee rules are mostly close-basis; Tiger stops are intraday.

## Version

0.1.0
