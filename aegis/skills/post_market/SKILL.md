---
name: post_market
description: Aegis process skill — POST MARKET (04:00–10:00 SGT). Pulls both brokers, saves the raw payloads, runs the deterministic batch that builds and verifies the book of record, and closes on the batch's exit code. Procedure lives HERE, not in the charter. Numbers cited as RB keys from charter/rulebook.yaml.
model: sonnet  # RB:model_tiers.control — PINNED, not inherited (D-93). packaging/build_claude.py hard-fails the build if this literal ever drifts from charter/parameters.yaml.
---

# PROCESS: POST MARKET (04:00–10:00 SGT)

**NOTHING IS SCHEDULED.** No task, cron or trigger runs this. It is started by hand, every time.

**Model note (D-16, pinned D-93):** control plane — RB:model_tiers.control — pinned in this file's own frontmatter rather than inherited from whatever session happens to call it. Post-market spawns **zero** agents: everything between the broker pull and the gate stamp is deterministic (constitution law 4 — no model, no network in the data plane). There is bounded judgment here — read an exit code, decide what to tell the PM — and nothing beyond that. If you find yourself wanting a voice's opinion, you are in the wrong process.

**Desk sequence (D-26/D-32):** the Chief adopts **Operations** for the book of record, then **Engineering & Change** for the audit — independent assurance grades the day Operations recorded. Physical move to `orchestration/` = BL-033.

**Storage note (D-84).** Google Drive is RETIRED as a store for the journal/PTJ/archive. GitHub is the ONE book of record: `data/journal/aegis_journal_YYYY-MM-DD.json` and `data/persistent/aegis_trade_journal_ARCHIVE_master.json` are plain files in this repo, committed and pushed by `tools/git_sync.py`. There is no second copy to keep in sync and no folder-ID to remember. **This does NOT touch the AQE feed** — AQE is an external engine we do not control, publishing to its own Drive "AQE" folder (premarket's job, not this one).

**Pipeline Ledger note (D-84).** Post-market does not touch the Pipeline Ledger. Filing and end-of-day sweep both happen in premarket — one place, one tool, one push.

---

## What changed (D-93): the middle of this process is now ONE call

Everything between "the broker payloads are on disk" and "the gate is stamped" used to be eleven tool invocations chained by the prose in this file, re-read and re-interpreted by a model every night, with the order of operations depending on the model getting it right again. **That whole span is now `scripts/run_post_market.sh`.** The script IS the order. It cannot drift, it cannot skip a step because a context ran long, and it returns one exit code.

Two things the script deliberately does NOT do, because a shell script cannot cross those seams:

- **It does not call Tiger or IBKR.** Those are MCP connectors, not CLIs. This session pulls both brokers and saves the raw payloads first — see step 1. Saving them is also new: until D-93 nothing in the book of record could be re-derived or audited after the fact.
- **It does not notify.** The phone message is this session's own final reply (D-75). A printed line is a draft, not a delivery.

It is also not order-capable. Nothing here places, sizes or arms anything — only staging-gatekeeper ever does (constitution law 1).

---

## Step 1 — Pull both brokers, save every payload

Resolve the live connector prefixes first. **Kernel-portability discipline: never hardcode `mcp__Tiger_MCPv7__` / `mcp__Interactive_Brokers_IBKR__` as gospel** — this kernel is meant to be transferable, and a connector can register under a different prefix (even a UUID) in another environment or account. Discover the live prefix the way `ibkr_connector_self_heal_protocol.md` documents, then call under the resolved name. If discovery finds no IBKR tools under ANY prefix, that is a session-wide hydration failure, not a retryable error — stop and escalate with the documented text; do not loop.

Save each response **verbatim** to `data/eod/<DATE>/broker_pull/` under these exact filenames. The batch reads this directory and nothing else:

| File | Call | Notes |
|---|---|---|
| `tiger_stock_positions.json` | `get_stock_positions` | current equity book |
| `tiger_option_positions.json` | `get_option_positions` | current option book (D-89 — this call existed on the connector but was never made by any loop, which is why the hedge was invisible) |
| `tiger_filled_orders.json` | `get_filled_orders` | **this is the day's fills list.** `days=2` covers a session that straddles the date line |
| `tiger_account_summary.json` | `get_account_summary` | balances / NAV |
| `ibkr_account_positions.json` | `get_account_positions` | equities AND options in the same payload — see below |
| `ibkr_account_trades.json` | `get_account_trades` | `period=TODAY` |
| `ibkr_account_summary.json` | `get_account_summary` | balances / NAV |

**`tiger_order_transactions.json` is optional and normally absent.** `get_order_transactions` is a **per-order** call — it requires an `order_id` and errors without one. It is NOT a daily fills list; `get_filled_orders` is. The batch treats the file as absent and carries on. Only save it if you pulled specific orders for a reason.

**IBKR ships no structured strike / right / expiry.** One `contract_description` string is the whole contract — `"AEHR Jul31'26 80 PUT @AMEX"` for an option, a bare `"CHYM"` for an equity, `"992 @SEHK"` for the HKD sleeve. `journal_build.py` parses that string; it returns nothing rather than a partial guess, and an unparseable row halts the run by name instead of being written as a half-position. Do not reshape the payload before saving it — save what the connector returned.

**Known IBKR weakness (Charter §0.5): `get_account_orders` under-reports.** Cross-check against Tiger before treating an IBKR-only order gap as a breach; never alarm off IBKR alone.

**Greeks and IV are NOT pulled here (D-90, PM ruling).** They are not book-of-record data. The journal records what is held — underlying, right, strike, expiry, signed size, entry, and the broker's own mark and unrealised — all of which come from the pull itself. Greeks are analytics: **Alpaca is the only contract-level source (15-min delayed, Charter §0.5 — neither Tiger nor IBKR provides them)** and they are consumed in exactly one place, premarket's hedge-coverage assessment, so they are pulled there, on the handful of legs that need them. A leg arriving here without Greeks is the normal case, not an exception to flag.

**Both pulls return every strategy on these accounts, not just Aegis.** Income Wheel and Protege9 share the same two brokers (RB:identity.doctrine: "must never assume a broker account's totals belong to it alone"). There is no broker-native tag to filter by (RB:identity.order_tagging.broker_native is blocked on both connectors), which is why membership classification runs inside the batch before anything trusts the book. USD only, PTJ-intersected (Charter §0.6).

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

---

## Step 3 — Read the exit code and close

| Exit | Gate | What it means | What you do |
|---|---|---|---|
| **0** | `ok` | every job passed | Relay the checklist. `run_ok`. |
| **1** | `partial` | the book of record is sound but the run is degraded — one broker only, a push that did not land, a later job that failed | Relay the checklist naming the failing lines. **PAGE.** |
| **2** | `fail` | halt — the journal could not be built or does not satisfy its contract, so nothing downstream may run | Relay the halt reason. **PAGE.** |

The script prints a flat pass/fail line per job and writes the same thing to `data/eod/<DATE>/post_market_run.json`, with the full transcript at `post_market_run.log`.

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

## ON FAILURE (RB:exceptions; records to `data/eod/DATE/exceptions/`)

- **One broker pull fails** → retry once → still down: save the payload you did get, run the batch anyway. `journal_build` reconciles from the other broker and marks the journal `PARTIAL_SOURCES`, exit 1. PAGE.
- **Both pulls fail** → the batch marks the journal **PROVISIONAL**, exit 2, halts everything downstream. Engine reuses the last GOOD journal. PAGE.
- **A connector hydration failure** (tool-discovery finds no Tiger or IBKR tools under any prefix — a different failure from a call erroring) is environment-level, not data-level. Don't retry it as a transient API error. Treat it as that broker's pull failing per the lines above, and say in the page that it was a hydration failure specifically (per `ibkr_connector_self_heal_protocol.md`), so the PM checks the connector, not the broker.
- **Option pull fails** → save nothing for it; the batch carries the prior legs forward rather than emptying the book, and flags it high. Retry once; PAGE if still down. A missing Greek is NOT a failure here — post-market never pulls them (D-90).
- **Option pull returns nothing while the journal previously carried a hedge** → an empty pull and a genuinely closed hedge are indistinguishable from the data, so this is NOT treated as a closed hedge. `derive-hedge` enforces this itself: with an empty `option_positions` and a prior record on file it KEEPS the prior record, marks it `stale`, and flags `hedge_book_empty` HIGH. Retry the pull once; if still empty, PAGE. (A book that HAS legs and confirms none of them is unambiguous and does null.) **Saving an empty file is not the same as saving nothing** — the batch distinguishes an absent payload from a present-and-empty one, and so must you.
- **Journal fails validation or its read-back verification** → the batch halts at exit 2 by itself. PAGE.
- **GitHub push fails** (`git_sync.py` reports `pushed: false`) → **this is the only copy, so treat it as seriously as a journal failure**, not a soft flag. The commit is retained locally and git_sync retries next loop; PAGE with the reason. A missing `GITHUB_PAT` is reported explicitly as committed-not-pushed, never silently swallowed — fix `config/.env`.
- **The batch itself cannot start** (payload directory empty or missing) → it exits 2 without stamping anything it cannot honestly stamp. Fix the pull and re-run; the batch is idempotent.
