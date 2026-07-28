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

## THE OPERATIONS

| # | Operation | Who runs it, and when | Tool | Touches | Never touches |
|---|---|---|---|---|---|
| 1 | **Execution** | Post-market, first thing — reconciles broker fills into `open_positions`/`closed_trades`, rolls dynCap. The only operation allowed to add or remove a position row. | (post-market's own journal-build step) | qty, entry, entry_date, stop_live_broker, tp1-3, trigger, broker, unrealised_usd, mark_price, closed_trades, dyncap | aqe_snapshot, aqe_snapshot_as_of, metrics |
| 1a | **Aegis-membership sort** | Post-market, immediately after Execution, same file, before anything else reads it — not every broker fill is an Aegis trade. | `held_book_refresh.py classify` | aegis_status (confirmed/pending_review), drops non-Aegis rows entirely, review_flags | execution-truth fields on rows it keeps |
| 2 | **Carry-forward** | Post-market, immediately after the membership sort, same session — post-market always runs before premarket pulls AQE, so this is the only way today's file starts with ANY market-data context. | `held_book_refresh.py carry-forward` | aqe_snapshot, aqe_snapshot_as_of (only where currently null) | everything else |
| 3 | **Metrics** | Post-market, right after Carry-forward — computes the real portfolio numbers off whatever's attached, for CONFIRMED positions only. Recomputes unconditionally every run (no LLM cost, no reason to skip). | `portfolio_metrics.py compute` | metrics only | open_positions, review_flags stay as Carry-forward left them |
| 4 | **AQE refresh** | Premarket, right after the day's AQE pull — the update this whole design exists for. | `held_book_refresh.py refresh` | aqe_snapshot, aqe_snapshot_as_of (unconditionally, for matched tickers) | execution-truth fields |
| 5 | **Stop update** | Premarket, right after the trailing-stop floor is computed — writes the new number in and checks it against the broker. | `held_book_refresh.py stop-update` | stop_reference, stop_match | stop_live_broker (read-only comparison, never written) |
| 5a | **Membership decision** | Premarket, at PM approval — the PM confirms or rejects each `pending_review` row from Operation 1a. | `held_book_refresh.py confirm` / `reject` | aegis_status, review_flags, and (on reject) the persistent exclusion list | everything else |
| 5b | **Metrics recompute** | Premarket, immediately after 5a, only if 5a changed anything — the numbers must reflect the PM's decision same-day, not tomorrow. | `portfolio_metrics.py compute` | metrics only | — |

A further touch happens outside this table: **market-hours**, when a live fill or a take-profit
lands mid-session. That is Execution-class work (same fields, same tool family) sourced from a
live broker pull instead of post-market's end-of-day reconciliation — market-hours cites
Operation 1's field list for what it's allowed to touch, same discipline, different trigger. A
market-hours fill that doesn't match a staged order should go through the same membership sort
before it's trusted for anything.

**5a/5b are captured here as the target, not yet wired into premarket's own SKILL.md** —
premarket's step sequence hasn't been walked and amended for this yet; that happens when premarket
gets the same review post-market just got.

## AEGIS-MEMBERSHIP SORTING (Operation 1a) — not every fill is ours

The PM runs other books on the same brokers (a standing example: a MARA/AMAT options wheel that
is explicitly out of Aegis's scope per the Charter). Operation 1 cannot tell an Aegis trade from
one of those just by looking at a fill, so Operation 1a decides, conservatively, right after
Operation 1 and before anything else touches the file:

1. **Matches a staged Aegis order** (or was already `confirmed` on a prior run) → `aegis_status:
   confirmed`. Silent — nothing for the PM to decide.
2. **Matches the persistent exclusion list** (`data/persistent/non_aegis_exclusions.json` — a
   PM already rejected this ticker before) → dropped from `open_positions` entirely, silent.
   Non-Aegis positions are never carried in this book. The exclusion list itself IS the record —
   ticker, date, reason — there is no separate archive of rejected fills; that would be
   over-engineering something whose only job is keeping today's portfolio numbers honest.
3. **Neither** → `aegis_status: pending_review`. Pulled INTO `open_positions` anyway — it's real
   capital, so it gets stops and carry-forward like anything else — and flagged once
   (`review_flags`, type `pending_review`) so it reaches the PM at the next premarket approval,
   never buried, never re-flagged daily once seen.

The PM's decision at premarket is final and one-way: **confirm** flips the row to `confirmed` and
clears the flag; **reject** removes the row and writes the ticker once to the exclusion list, so
it is silently excluded — never re-surfaced as pending — every day after, even if the broker keeps
reporting it. Either decision must be followed immediately by a Metrics recompute (Operation 5b)
so the same day's numbers reflect it, not tomorrow's.

## STORAGE — where every write actually lands (plain confirmation, kept next to the write rules on purpose)

**The journal lives in this repo and goes to GitHub. There is no other copy anywhere — Google
Drive was retired as a store for it.** `data/journal/aegis_journal_YYYY-MM-DD.json` is a plain
file in the kernel's own git repository; `tools/git_sync.py` commits and pushes it to
`github.com/TongIncomeWheel/AQE.git`. That push IS the "saved" moment — a write that only reaches
local disk has not actually gone anywhere durable yet.

**This matters because each scheduled run is its OWN session with its OWN fresh checkout of the
repo.** Post-market, premarket, and market-hours don't share a running process or a shared disk —
each one clones the repo fresh when it starts and only ever sees what the LAST push put there.
So the write rules and the push have to travel together, at every single touch point, or a write
that's real on one session's disk is invisible everywhere else:

| Session | Operations it runs | Pushes to GitHub? |
|---|---|---|
| Post-market | 1, 1a, 2, 3 (Execution, Membership sort, Carry-forward, Metrics) | Yes — always, end of its journal step |
| Premarket | 4, 5, (5a/5b once wired) (AQE refresh, Stop update, Membership decision, Metrics recompute) | Yes — right after its last write, same run |
| Market-hours | Execution-class, on an observed fill only | Yes — right after that fill's update, skipped on a quiet cycle |

**This was a real gap, found and closed while confirming this, not a pre-existing guarantee:**
until this was checked, only post-market ever pushed. Premarket's AQE refresh and stop update, and
market-hours' fill updates, were landing on that session's local disk and nowhere else — gone the
moment the session ended, never seen by tomorrow's post-market carry-forward or by any other
session that day. All three now push. If `GITHUB_PAT` is missing, every push fails the same way
(committed locally, not pushed) and that must be stated plainly in that session's run outcome, not
silently treated as done.

## PROCEDURE (what each caller actually does)

1. **If you are post-market:** run Operation 1 (your own fills logic), then Operation 1a
   (`classify --journal <today> --exclusions data/persistent/non_aegis_exclusions.json --staged
   <today's staged-orders list>`), then Operation 2 (`carry-forward --journal <today> --prior
   <most recent prior journal with a snapshot>`), then Operation 3 (`compute --journal <today>`).
   All four, same file, same session, in that order — Membership sort must run before anything
   else reads the file, and Metrics needs whatever Carry-forward just attached. Then push
   (`git_sync.py`) as you already do.
2. **If you are premarket:** after your AQE pull lands, run Operation 4
   (`refresh --journal <today> --export <today's export>`), then run your trailing-stop
   calculation, then run Operation 5 (`stop-update --journal <today> --stops <ticker: new_stop map>`).
   Once the PM approves the plan, for each `pending_review` row route the PM's decision through
   Operation 5a (`confirm --journal <today> --ticker <T>` or `reject --journal <today> --ticker <T>
   --exclusions data/persistent/non_aegis_exclusions.json`), then Operation 5b
   (`compute --journal <today>`) if 5a touched anything, so the numbers reflect it same-day.
   **Then push** — `tools/git_sync.py -m "premarket held-book refresh <DATE>"` — this session's
   checkout is the only place these writes exist until that push lands.
3. **If you are market-hours:** on an observed fill, update the affected position's
   execution-truth fields the same way Operation 1 does (same field list, same file), **then
   push** the same way — skip the push on a cycle where nothing fired, most cycles won't need one.
4. **Whoever runs last in a given session** should glance at `review_flags` added THIS run and
   make sure anything `severity: high` is going to actually reach the PM (post-market: the
   morning summary; premarket: the held-book section of the plan render) — the flag existing in
   the file is necessary but not sufficient, it has to surface somewhere a person looks.

## WHAT THIS SKILL MUST NOT DO
Compute anything itself (every operation is `tools/held_book_refresh.py` /
`tools/portfolio_metrics.py`, deterministic, no model) · invent a write path outside the table
above · suppress or soften a `review_flags` entry to make a run look cleaner · let a data-quality
flag block a write · touch `stop_live_broker` anywhere except Operation 1's fill reconciliation ·
skip Operation 3/5b's recompute to save cost — it is free, always run it · build a second archive
of rejected non-Aegis fills alongside the exclusion list — the exclusion list already is the
record, a second one is over-engineering · **write to the journal and end the session without
pushing** — a write that never reaches GitHub is indistinguishable from a write that never
happened, to every other session that reads this file.

## ON FAILURE
- Any operation errors (bad JSON, journal missing) → that IS a write failure, not a
  data-quality flag — halt the calling session's ordering rule the same as a journal validation
  failure, page.
- `review_flags` entries are idempotent per (ticker, condition) within a day's file — a re-run of
  the same operation refreshes the existing entry's detail in place rather than duplicating it, so
  the list reflects CURRENT conditions, not an ever-growing log. A flag disappears the next time
  that operation runs and no longer finds the condition (e.g. `stop_mismatch` clears once a later
  Stop update finds `stop_match: MATCH`). Since each day gets its own dated journal file, nothing
  carries across days either — a flag that matters past one day belongs in the Pipeline Ledger or
  a page, not left to accumulate here.
