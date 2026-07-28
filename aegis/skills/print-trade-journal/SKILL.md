---
name: print-trade-journal
description: Aegis process skill — PRINT TRADE JOURNAL (PTJ shorthand). The one place that documents every write to the held book across the day, so post-market, premarket, and market-hours each point HERE instead of re-explaining the rule inline. No model reasoning — this is control-plane sequencing over tools/held_book_refresh.py and tools/portfolio_metrics.py.
---

# PROCESS: PRINT TRADE JOURNAL — /ptj (kernel-native, revives the retired standalone skill's name)

**What this is.** The journal (`data/journal/aegis_journal_YYYY-MM-DD.json`) gets written to several
times across one day, by three different sessions, each for a different reason. This skill is the
single place all three of those writes are defined, so nobody has to re-derive the rule or guess
what's safe to touch. It is invoked inline — read into whichever orchestrator's context needs it
at that moment — not spawned as its own agent, because none of this needs judgment: it is a
sequence of tool calls and a fixed rule about what happens on a data-quality problem.

**The rule, stated once (repeat this to yourself before touching the journal):**
**A write is never blocked by a data-quality problem. It always writes. If something is off — a
stop that doesn't match the broker, a position that's never had AQE data, a name missing from
today's export — it gets a named entry in `review_flags` on that same write, and the PM sees it
in the morning summary or the premarket held-book render. Nothing gets silently defaulted, nothing
gets silently dropped, and nothing halts the write over it.** The only thing that DOES halt a
write is the journal itself failing to build or failing schema validation — a data-quality flag on
one ticker is never that.

## THE FIVE OPERATIONS

| # | Operation | Who runs it, and when | Tool | Touches | Never touches |
|---|---|---|---|---|---|
| 1 | **Execution** | Post-market, first thing — reconciles broker fills into `open_positions`/`closed_trades`, rolls dynCap. The only operation allowed to add or remove a position row. | (post-market's own journal-build step) | qty, entry, entry_date, stop_live_broker, tp1-3, trigger, broker, unrealised_usd, mark_price, closed_trades, dyncap | aqe_snapshot, aqe_snapshot_as_of, metrics |
| 2 | **Carry-forward** | Post-market, immediately after Execution, same session — post-market always runs before premarket pulls AQE, so this is the only way today's file starts with ANY market-data context. | `held_book_refresh.py carry-forward` | aqe_snapshot, aqe_snapshot_as_of (only where currently null) | everything else |
| 3 | **Metrics** | Post-market, right after Carry-forward — computes the real portfolio numbers off whatever's attached. | `portfolio_metrics.py compute` | metrics only | open_positions, review_flags stay as Carry-forward left them |
| 4 | **AQE refresh** | Premarket, right after the day's AQE pull — the update this whole design exists for. | `held_book_refresh.py refresh` | aqe_snapshot, aqe_snapshot_as_of (unconditionally, for matched tickers) | execution-truth fields |
| 5 | **Stop update** | Premarket, right after the trailing-stop floor is computed — writes the new number in and checks it against the broker. | `held_book_refresh.py stop-update` | stop_reference, stop_match | stop_live_broker (read-only comparison, never written) |

A sixth touch happens outside this table: **market-hours**, when a live fill or a take-profit
lands mid-session. That is Execution-class work (same fields, same tool family) sourced from a
live broker pull instead of post-market's end-of-day reconciliation — market-hours cites
Operation 1's field list for what it's allowed to touch, same discipline, different trigger.

## PROCEDURE (what each caller actually does)

1. **If you are post-market:** run Operation 1 (your own fills logic), then Operation 2
   (`carry-forward --journal <today> --prior <most recent prior journal with a snapshot>`), then
   Operation 3 (`compute --journal <today>`). All three, same file, same session, in that order —
   Metrics needs whatever Carry-forward just attached.
2. **If you are premarket:** after your AQE pull lands, run Operation 4
   (`refresh --journal <today> --export <today's export>`), then run your trailing-stop
   calculation, then run Operation 5 (`stop-update --journal <today> --stops <ticker: new_stop map>`).
3. **If you are market-hours:** on an observed fill, update the affected position's
   execution-truth fields the same way Operation 1 does (same field list, same file) — this is
   still a journal write, not a separate store.
4. **Whoever runs last in a given session** should glance at `review_flags` added THIS run and
   make sure anything `severity: high` is going to actually reach the PM (post-market: the
   morning summary; premarket: the held-book section of the plan render) — the flag existing in
   the file is necessary but not sufficient, it has to surface somewhere a person looks.

## WHAT THIS SKILL MUST NOT DO
Compute anything itself (all five operations are `tools/held_book_refresh.py` /
`tools/portfolio_metrics.py`, deterministic, no model) · invent a sixth write path outside the
table above · suppress or soften a `review_flags` entry to make a run look cleaner · let a
data-quality flag block a write · touch `stop_live_broker` anywhere except Operation 1's fill
reconciliation.

## ON FAILURE
- Any of the five operations errors (bad JSON, journal missing) → that IS a write failure, not a
  data-quality flag — halt the calling session's ordering rule the same as a journal validation
  failure, page.
- `review_flags` entries are idempotent per (ticker, condition) within a day's file — a re-run of
  the same operation refreshes the existing entry's detail in place rather than duplicating it, so
  the list reflects CURRENT conditions, not an ever-growing log. A flag disappears the next time
  that operation runs and no longer finds the condition (e.g. `stop_mismatch` clears once a later
  Stop update finds `stop_match: MATCH`). Since each day gets its own dated journal file, nothing
  carries across days either — a flag that matters past one day belongs in the Pipeline Ledger or
  a page, not left to accumulate here.
