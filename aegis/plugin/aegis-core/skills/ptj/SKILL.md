---
name: ptj
description: "Aegis process skill — PTJ. Pulls the broker, runs the deterministic batch, prints the book on screen. Three modes: VIEW (default, changes nothing), FA (read what is already on disk, instant), CLOSE (the real book of record — called by /premarket, not typed). Procedure lives HERE, not in the charter. Nothing here is scheduled."
model: sonnet  # sonnet [RB:model_tiers.control] — PINNED, not inherited (D-93). packaging/build_claude.py hard-fails the build if this literal ever drifts from charter/parameters.yaml.
---

# PROCESS: PTJ — the book, on screen

**This is the ONE place the broker pull and the batch are described.** Nothing else in the kernel restates them. `/premarket` does not have its own copy of this procedure — it calls MODE C below. If you ever find a second description of pulling Tiger anywhere in this repo, that copy is the bug.

**IBKR RETIRED (D-98).** The PM no longer holds any capital or positions at IBKR — the account is fully wound down. Tiger is now the sole broker this kernel pulls. Older material in this repo (decision log entries, historical fixtures) still refers to IBKR because that was true at the time; it is kept as an audit trail, not restated as current practice. If you find a live code path or an active doctrine line still assuming a second broker, that is a regression — flag it.

**NOTHING IS SCHEDULED.** No task, cron or trigger runs this. It is started by hand, every time.

---

## WHY THIS SKILL NEEDS AQE DATA AT ALL — AND WHY IT IS NEVER FRESH HERE

**The one-line answer: PTJ needs AQE for exactly one thing — knowing what SECTOR each position is in, so it can compute sector concentration (a real risk limit, 35% cap per sector).** Tiger's broker pull gives ticker, quantity, price, and P&L — it does not know or say that AMPL is "Technology." That classification exists nowhere except AQE's daily export. Nothing else PTJ prints — price, P&L, dynCap, stops — touches AQE at all; it all comes straight off the broker pull.

**PTJ never pulls AQE itself.** It only touches the field it needs (`aqe_snapshot.gics_sector`) two narrow ways:

1. **Carry-forward (job 6, `held_book_refresh.py carry-forward`).** Each open position's `aqe_snapshot` is copied over from whatever the PRIOR day's journal already had attached to that ticker — never fetched, never refreshed. A brand-new position that was never held before starts with no snapshot at all.
2. **Portfolio metrics (job 9, `portfolio_metrics.py compute`).** Sector concentration is computed off that carried-forward snapshot's `gics_sector` field. A position with no `aqe_snapshot` is EXCLUDED from every metric and named in the output, never defaulted to zero.

**Why it's never today's data — this is just ordering, not a defect.** PTJ CLOSE mode is Step 0 of `/premarket` — it runs and stamps the gate *before* `/premarket` goes on to pull the day's fresh AQE export (that happens at `/premarket` Step 4 onward). Today's AQE export doesn't exist yet when PTJ runs, so PTJ literally cannot ask for it — it's stuck reading whatever sector tag is already sitting in yesterday's journal. The journal carries `computed_from_aqe_dated` so you can see exactly which date the sector read reflects (frequently NOT today's), and `mixed_vintage: true` fires if held names carry snapshots from different dates.

**What actually refreshes it:** `/premarket`'s own Operation 4 (`held_book_refresh.py refresh`), which runs after PTJ has already closed the book and pushed. If you want today's sector read, ask after `/premarket` finishes, not after PTJ alone.

---

## THE THREE MODES — same code, one flag apart

| Mode | Command | Pulls brokers | Runs the batch | Writes the book of record | Archive + janitor | Stamps the gate | Pushes to git |
|---|---|---|---|---|---|---|---|
| **A — VIEW** | `/ptj` | **yes, fresh** | yes, `--rehearsal` | no → `data/eod/DATE/rehearsal/` | no | **never** | no (dry-run) |
| **B — FA** (full array) | `/ptj fa` | **no** | no | no | no | never | no |
| **C — CLOSE** | *not typed — `/premarket` step 0 calls it* | yes, fresh | yes, for real | **yes** → `data/journal/` | **yes** | yes | yes, twice |

**A and C are the same run with one flag different.** That is the point: the number you look at during the session is produced by the same arithmetic that writes tonight's book. There is no second implementation to drift.

**B costs nothing.** No network, no pull, no batch — it reads the most recent journal already on disk and prints it. Use it to glance at the book without moving anything. It is honest about its age: it says what date and time the file it read was written, so a stale array can never be mistaken for a live one.

---

## Step 0 — Stamp the clock, pick the mode

Run `date` live for **SGT and US Eastern** — never assert a date or a session state from memory (Charter §0.1, §0.5). `DATE` is today's SGT calendar date.

In MODE A, say in the first line which of three worlds the numbers are in, because it changes what they mean:

| US session | Say it as |
|---|---|
| open | "live, session open — these are moving while you read them" |
| closed (after 16:00 ET) | "at the close" |
| pre-open / weekend / holiday | "last close, market shut" |

**MODE B skips everything below except Step 3.**

---

## Step 1 — Pull the broker, save every payload

**MODE A saves to `data/eod/<DATE>/ptj_view/`. MODE C saves to `data/eod/<DATE>/broker_pull/`.** A view must never overwrite the official close payload. Everything else about the pull is identical.

**Tiger is the sole broker (D-98 — IBKR retired, PM confirmed no residual capital there).**

Resolve the live connector prefix first. **Kernel-portability discipline: never hardcode `mcp__Tiger_MCPv7__` as gospel** — this kernel is meant to be transferable, and a connector can register under a different prefix (even a UUID) in another environment or account. Discover the live prefix, then call under the resolved name. If discovery finds no Tiger tools under ANY prefix, that is a session-wide hydration failure, not a retryable error — stop and escalate with the documented text; do not loop.

Save each response **verbatim** to `data/eod/<DATE>/broker_pull/` under these exact filenames. The batch reads this directory and nothing else:

| File | Call | Notes |
|---|---|---|
| `tiger_stock_positions.json` | `get_stock_positions` | current equity book |
| `tiger_option_positions.json` | `get_option_positions` | current option book (D-89 — this call existed on the connector but was never made by any loop, which is why the hedge was invisible) |
| `tiger_filled_orders.json` | `get_filled_orders` | **this is the day's fills list.** `days=2` covers a session that straddles the date line |
| `tiger_account_summary.json` | `get_account_summary` | balances / NAV |

**`tiger_order_transactions.json` is optional and normally absent.** `get_order_transactions` is a **per-order** call — it requires an `order_id` and errors without one. It is NOT a daily fills list; `get_filled_orders` is. The batch treats the file as absent and carries on. Only save it if you pulled specific orders for a reason.

**Greeks and IV are NOT pulled here (D-90, PM ruling).** They are not book-of-record data. The journal records what is held — underlying, right, strike, expiry, signed size, entry, and the broker's own mark and unrealised — all of which come from the pull itself. Greeks are analytics: **Alpaca is the only contract-level source (15-min delayed, Charter §0.5 — Tiger does not provide them)** and they are consumed in exactly one place, premarket's hedge-coverage assessment, so they are pulled there, on the handful of legs that need them. A leg arriving here without Greeks is the normal case, not an exception to flag.

**The pull returns every strategy on this account, not just Aegis.** Income Wheel and Protege9 share the same broker (Aegis is ONE of THREE strategies sharing co-mingled capital on Tiger (D-17, amended D-98 — single broker since IBKR's retirement). The other two (Income Wheel, Protege9) are out of scope for this kernel entirely — Aegis must never read, size against, or risk-gate their positions, and must never assume a broker account's totals belong to it alone. [RB:identity.doctrine]: "must never assume a broker account's totals belong to it alone"). There is no broker-native tag to filter by (BLOCKED as of 18 Jul — the current Tiger MCP tool wrappers (place_stock_order, create_order_instruction) expose no client-order-tag, remark, or reference field; the underlying broker API likely supports one but the MCP surface Aegis is required to reuse (PM ruling: do not rebuild Tiger/Alpaca MCPs) does not pass it through. Interim (Phase 1 only, PM stages personally per RB:orders.phase_1): the staging preview MUST instruct the PM to add an AEGIS tag/memo manually in the broker's own app at submission. Real fix is BL-028 (MCP passthrough param — needs the PM, as owner of that hosting relationship, to request it) or Phase 2 auto-staging simply cannot claim broker-native tagging until it ships. [RB:identity.order_tagging.broker_native] is blocked on the connector), which is why membership classification runs inside the batch before anything trusts the book. USD only, PTJ-intersected (Charter §0.6).

---

## Step 2 — Run the batch


```
bash scripts/run_post_market.sh <YYYY-MM-DD>
```

Optional: `--pull DIR` if the payloads are somewhere other than `data/eod/<DATE>/broker_pull`. `--rehearsal` runs every step for real against the real payloads but writes the journal and all run artefacts to `data/eod/<DATE>/rehearsal/`, leaves the archive untouched, turns both pushes into `git_sync --dry-run`, and **never stamps the gate** — use it before the close, and the first time you run the batch after changing anything.

The thirteen jobs it runs, in this order:

| # | Job | Fatal? |
|---|---|---|
| 0 | payload-dir contract — is there anything to build from | yes |
| 1 | `preflight.py` — can this session save its own work | no |
| 2 | `journal_build.py build` — reconcile both brokers into one journal, roll dynCap | **yes** |
| 3 | `held_book_refresh.py classify` — Aegis equity membership | **yes** |
| 4 | `option_book.py classify` — option membership by contract | **yes** |
| 5 | `option_book.py derive-hedge` — rebuild the hedge from confirmed legs | **yes** |
| 6 | `held_book_refresh.py carry-forward` — prior snapshots, stop references | **yes** |
| 7 | `journal_build.py verify` — read the file back off disk and re-validate | **yes** |
| 8 | `git_sync.py` — **push #1, the book of record** | no |
| 9 | `portfolio_metrics.py compute` — metrics written into the journal | no |
| 10 | `archive_ledger.py merge` — append today's closed trades | no |
| 11 | `daily_flow_audit.py --render` — the flight recorder | no |
| 12 | `git_sync.py` — **push #2, metrics + archive + audit** | no |
| 13 | `phase_gate.py stamp` — the only thing tomorrow's Phase 0 reads | — |

**Why two pushes.** The single push used to sit at job 8 only, before metrics, the archive append and the audit existed. A fresh clone therefore read a journal with an empty `metrics` key until the following day's run overwrote it. The first push protects the book the moment it is verified; the second ships the rest of the same run.

**Ordering rule Arch-F9 is enforced by the script, not by prose:** if the journal build, its read-back verification, or schema validation fails, the run halts at exit 2 — no membership pass, no hedge derivation, no held-list emit, no archive append.

**The gate is stamped on every exit path, including the halts.** A run that dies without stamping leaves Phase 0 in NOT_READY forever, retrying against a run that already failed — which reads as "AQE is late" when the truth is "post-market is dead."


**MODE A adds `--rehearsal` and points `--pull` at the view directory:**

```
bash scripts/run_post_market.sh <DATE> --pull data/eod/<DATE>/ptj_view --rehearsal
```

**MODE C is the bare call above — no flags.** Jobs 8 and 12 (the two pushes), job 10 (the archive append) and job 13 (the gate stamp) are exactly the "print it to git, janitor the book, append the history file" work that separates a close from a look. They are not a different process; they are four jobs the rehearsal flag turns off.

Do not re-derive positions, P&L, dynCap or metrics by hand in any mode, and do not "sanity-adjust" what the batch returns. If a number looks wrong, that is a finding about the kernel, and it is reported as one — see Step 3.

---

## Step 3 — Print it, then read the exit code

**MODE A and MODE B print the same thing; MODE C prints it and then it is also the book of record.**

### What to print — tables, phone-readable

Read the journal (MODE A: `data/eod/DATE/rehearsal/` · MODE B: the latest file in `data/journal/` · MODE C: `data/journal/`) and show, in **markdown tables** (PM standing instruction: "show me in tabular form pls else hard to read"):

1. **Held book** — ticker · qty · avg cost · mark · unrealised · % of book. Sorted by weight, biggest first.
2. **The day** — day P&L, and P&L since entry per name where the journal carries it.
3. **Capital** — dynCap, 1R, gross exposure, leverage, net beta, 1-month VaR.
4. **Anything not clean** — every `pending_review` name (real capital, excluded from every metric until confirmed), the hedge record or its absence, `mixed_vintage` if it fired, any position excluded for want of an AQE snapshot.

Then one plain closing line: what the book is worth, what is at risk, and anything genuinely needing a decision.

**MODE A closes with:** "View only — nothing stamped, nothing pushed, no journal written."
**MODE B closes with:** "Read off disk, written <date time>. No pull, nothing touched."

**Report a bad number, never absorb it.** A **negative dynCap** (which makes 1R negative, which would size positions backwards), a leverage figure that disagrees with the broker, a metric computed over positions that are not Aegis's — say it plainly at the top and stop treating it as a display problem. It is a kernel defect and the PM decides whether to trade around it.

### The exit code (MODES A and C)


| Exit | Gate | What it means | What you do |
|---|---|---|---|
| **0** | `ok` | every job passed | Relay the checklist. `run_ok`. |
| **1** | `partial` | the book of record is sound but the run is degraded — a push that did not land, a later job that failed | Relay the checklist naming the failing lines. **PAGE.** |
| **2** | `fail` | halt — the journal could not be built or does not satisfy its contract, so nothing downstream may run | Relay the halt reason. **PAGE.** |

The script prints a flat pass/fail line per job and writes the same thing to `data/eod/<DATE>/post_market_run.json`, with the full transcript at `post_market_run.log`.

**v5.3 (2026-09-05) — exit 1 caused ONLY by the two git pushes is not a degraded close.** On Cowork the sandbox git proxy returns 403 for this repo, so jobs 8 and 12 report `pushed: false` every day. The conductor pushes the same files via the GitHub connector (`push_files`), verifies blob SHAs, then re-stamps the gate `ok` with the connector commit SHA in the note. Relay it as "Book closed and pushed (connector)". Page only if a job OTHER than the two pushes failed.

Check in with the external dead-man's-switch (`tools/notify.py --checkin ok`) so the ABSENCE of a check-in becomes the alarm if the box ever dies mid-run.

**CLOSE WITH A REAL CHAT MESSAGE (D-75).** `notify.py`'s print is a draft, not delivery — the Cowork push comes from the session's actual final reply. The LAST thing this session does must be that checklist, said in plain language, as the session's actual final message.


---

## Doctrine the batch's tools implement


This section explains *why* the jobs above do what they do. It is reference, not a sequence to re-execute — the script already runs all of it.

**Aegis equity membership (job 3).** The PM runs other books on the same brokers, so not every fill is Aegis's. A fill matching a staged order is `confirmed` silently; a fill matching the persistent exclusion list (a ticker the PM has already rejected) is dropped from the journal entirely and never re-flagged; anything matching neither is pulled in as `pending_review` — real capital, so it still gets stops and carry-forward — and flagged once for the PM at the next premarket approval. See `print-trade-journal` for the full logic. **With no staged-orders list on disk, every unmatched fill lands as `pending_review`. That is the designed behaviour, not a fault.**

**Option membership is by CONTRACT, not by ticker (job 4).** Underlying + right + strike + expiry is the identity. SPY can carry an Income Wheel short put and an Aegis macro put spread on the same day: a ticker-keyed rule would let a rejected wheel leg permanently suppress every future Aegis SPY hedge. The equity exclusion list is never consulted here. A leg belonging to a structure the gatekeeper actually staged is `confirmed` silently; a contract already ruled on in `data/persistent/option_membership.json` is honoured silently forever, which is what stops a hand-placed or rolled hedge being re-asked every morning; anything else is `pending_review`, kept in the book, flagged ONCE. A staged structure only partially present has its missing legs flagged HIGH — half a spread has nothing like the spread's payoff.

**The hedge is DERIVED, never hand-written and never carried forward blind (job 5)** — so the structure in the journal cannot quietly disagree with the broker. No confirmed structure → `hedge: null`, honestly. Two live structures → nearest expiry becomes the record and the others are flagged HIGH. **What this fixes: `hedge` was an unconstrained schema stub with no writer anywhere in the kernel, so it was null every day by construction — which made premarket's Phase 1 conclude "no hedge on record" every morning and Phase 2 propose a fresh structure over one the book already held.** A prior hedge record that does not satisfy the contract is quarantined verbatim under `hedge_quarantined` rather than propagated or discarded, flagged high, and left for derive-hedge to rebuild from the actual legs.

**Metrics are computed for real and written INTO the journal (job 9)** — PM: "the portfolio check figures should be inside the journal so that's a proper snapshot of the portfolio, not just list of positions." Gross exposure, leverage, net-beta-dollar, NAV-β (gate window RB:risk.gates.portfolio_beta), sector concentration, and 1-month parametric VaR (reusing `tools/calculators/var_parametric.py`, not a second implementation). **One consistent data source:** per-position beta and annualised volatility come from FMP price history via `tools/historical_store.py` — the same source and method as the market-factor volatility inside the VaR calc — NOT from the AQE snapshot. AQE is read only for `sector`, a classification, not a computed statistic. **Confirmed positions only:** anything still `pending_review` is excluded from every number and named in `excluded_pending_review`, never blended in until the PM confirms it. A position with no `aqe_snapshot` is EXCLUDED and named, never defaulted to zero; `computed_from_aqe_dated` states which AQE date the sector data reflects (frequently NOT today's — post-market always runs before premarket refreshes it), and `mixed_vintage: true` fires if held names carry different AQE dates. **No stop audit here** — that comparison is only fresh right after premarket's stop-update step. Recomputed unconditionally every run: it is a deterministic call against a pre-seeded local store, so skipping it would only ever risk a stale number for zero benefit.

**Archive integrity gate (job 10).** `archive_ledger.py merge` raises if `sum(by_trading_day) != YTD`; on that error nothing is written and the run degrades — an archive that fails its own arithmetic is never shipped. Zero closed trades is a legitimate no-op and writes nothing. **Closed trades with no archive file to file them into is a real gap, and the batch reports it as a failure rather than a quiet skip.**


---

## WHAT THIS SKILL MUST NOT DO

Stamp a gate, push, or write to `data/journal/` in MODE A or B · pull anything in MODE B · spawn a voice, the committee-desk or any judgment-tier agent · produce an order preview or touch the staging-gatekeeper · decide RUN / TRIM / EXIT on a held name · recompute a figure the batch already produces · present a view as a close, or a disk read as a live pull · reshape a broker payload before saving it.

## ON FAILURE (RB:exceptions; records to `data/eod/DATE/exceptions/`)

- **MODE A or B failing breaks nothing downstream** — neither stamps anything, by construction. That is exactly why they are safe to run casually. Say what failed and stop.
- **MODE B finds no journal on disk** → say so and offer MODE A. Do not silently pull.


- **The broker pull fails** → retry once → still down: save whatever you did get, run the batch anyway. With one broker, a failed pull means `journal_build` cannot reconcile anything — the journal is marked **PROVISIONAL**, exit 2, halts everything downstream. Engine reuses the last GOOD journal. PAGE.
- **A connector hydration failure** (tool-discovery finds no Tiger tools under any prefix — a different failure from a call erroring) is environment-level, not data-level. Don't retry it as a transient API error. Treat it as the broker pull failing per the line above, and say in the page that it was a hydration failure specifically, so the PM checks the connector, not the broker.
- **Option pull fails** → save nothing for it; the batch carries the prior legs forward rather than emptying the book, and flags it high. Retry once; PAGE if still down. A missing Greek is NOT a failure here — post-market never pulls them (D-90).
- **Option pull returns nothing while the journal previously carried a hedge** → an empty pull and a genuinely closed hedge are indistinguishable from the data, so this is NOT treated as a closed hedge. `derive-hedge` enforces this itself: with an empty `option_positions` and a prior record on file it KEEPS the prior record, marks it `stale`, and flags `hedge_book_empty` HIGH. Retry the pull once; if still empty, PAGE. (A book that HAS legs and confirms none of them is unambiguous and does null.) **Saving an empty file is not the same as saving nothing** — the batch distinguishes an absent payload from a present-and-empty one, and so must you.
- **Journal fails validation or its read-back verification** → the batch halts at exit 2 by itself. PAGE.
- **GitHub push fails** (`git_sync.py` reports `pushed: false`) → **this is the only copy, so treat it as seriously as a journal failure**, not a soft flag. The commit is retained locally and git_sync retries next loop; PAGE with the reason. A missing `GITHUB_PAT` is reported explicitly as committed-not-pushed, never silently swallowed — fix `config/.env`.
- **The batch itself cannot start** (payload directory empty or missing) → it exits 2 without stamping anything it cannot honestly stamp. Fix the pull and re-run; the batch is idempotent.
