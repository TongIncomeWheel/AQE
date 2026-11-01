# The Aegis book and its stops — one source of truth (plan for PM review, 2 Nov 2026)

**Status (later on 2 Nov): BUILT on branch `claude/aegis-engineering` after the PM's ruling** — "Stop from Tiger is correct ... ask for the stops then, both from the trade report and also during the AQE run ... if there are new names traded, let it be picked up anyway; I will say so when reviewing the PMA report." COIN: picked up automatically, the PM excludes on review. No-stop: WARN (default kept). What was built: `docs/BUILD_STATE.md` → "The book and its stops".

## What is actually wrong (verified against code and files, not the summary)

1. **The 05:30 book close never asks Tiger for working orders.** The close saves four Tiger files (positions, options, fills, account). It does not save `get_open_orders`. Every journal since at least 26 Oct carries the flag `open_orders_pull_absent`, and `stop_live_broker` is blank on MP and V every night.
2. **The code to read the stops is already written and already on main.** The batch the close runs (`aegis/scripts/run_post_market.sh` → `aegis/tools/journal_build.py`) reads `tiger_open_orders.json` when it is present, writes each held name's live stop into the journal, and flags a name with no working stop as UNPROTECTED. It has simply never been fed the file.
3. **AQE already reads the journal's stop.** The export's `held_sl` = the journal's `stop_live_broker`. So once the file is fed, `held_sl` stops being blank with no AQE change. (`held_tp1/tp2` are AQE's own bracket targets by your 29 Jul ruling — untouched.)
4. **Tiger now returns the stop trigger.** Checked live just now, read-only: V stop-limit 391.80 / 390.80 × 38, MP stop-limit 36.66 / 36.66 × 300, both GTC. (An old `/stops` note said Tiger hid the trigger; that is no longer true.)
5. **The committee's stops today depend on one session having the Tiger connector.** GATHER re-pulls Tiger itself. Nothing checks it, nothing compares it with the book.
6. **Who is Aegis is decided by code, not judgment** (`held_book_refresh.py classify`): the membership list (24 names incl. MP, V) and the exclusion list (MARA, CRCL, NVDA, MCD, KO, CRDO, GLW, CPER, TTMI). Anything Tiger holds that is on neither list is **auto-included as Aegis** (your 25 Aug ruling).

## The plan

| | |
|---|---|
| **The file** | The dated journal we already have: `aegis/data/journal/aegis_journal_<close date>.json` on main. No second file. Each held name gains its stop order in full (type, stop, limit, shares covered, time in force), plus a top-level `stops_pulled: true/false`. |
| **Who writes it** | The 05:30 close, as today, with one extra Tiger call: `get_open_orders`, saved verbatim as `tiger_open_orders.json`. A missing orders file makes the close report **degraded** (loud), never silently blank. |
| **Who reads it** | (a) AQE's 06:30 export — `held_sl` filled, plus a new `held_stop_order` block and `held_stop_as_of` (the journal date) on each held row. (b) The committee's GATHER — `pma_levels.py stops --journal` builds `broker_stops.json` from the journal, so the committee no longer needs the Tiger connector. If the conductor does have Tiger, its live pull is a cross-check, not the source. |
| **What the gate checks** (`check.py data`) | FAIL if the journal is missing; FAIL if it is not for the last US close; FAIL if the orders were not pulled; FAIL if the export's held names or stops differ from the journal's; FAIL if a live broker read at GATHER disagrees with the journal (stop price or shares). A held name with **no** stop order is printed as a WARN line (see decision 2). |
| **05:30 task prompt** | One line added: "also call `get_open_orders` and save it verbatim as `tiger_open_orders.json` — required." And the stale "08:30" AQE wording corrected to 06:30. |

**The fast part:** because the reader is already on main, the prompt line alone fills the stops from **Tuesday's 05:30 close** — no release needed. The rest (export block, GATHER from the journal, the gate) is built on the branch with tests and goes to main only on your word, after the 18:00 gate.

## What you must decide

1. **COIN — act before Tuesday 05:30.** Tiger now holds **100 COIN at 177.50** (the 30 Oct 177.5 put was assigned). COIN is on neither list, so Tuesday's close will **auto-include it as an Aegis position**, unprotected, and it will count in dynCap and 1R. Is COIN Aegis? If not, I add it to the exclusion list (one-line data change) — your word only.
2. **A held name with no stop order:** WARN (committee runs, the card says UNPROTECTED) — my default — or FAIL (committee does not start until it is fixed)?
3. **Approve the 05:30 prompt change** (it touches a live scheduled task).
4. Carried: the capital line. The 30 Oct journal computes **1R = $928.50** (1.5% of dynCap $61,900) while the Aegis rule is the fixed **$620**, and `aegis_fund.md` still says allocated $75,000. dynCap $61,900 matches your "$62K portfolio". Which number is 1R in the journal? (Sizing — your call only.)

## Found on the way (not in this change-set)
- The book-close tools exist in two diverged copies: `aegis/tools/` (what actually runs at 05:30) and `aegis/plugin/aegis-core/tools/` (the "one code tree"). 22 files differ; the plugin copy of `journal_build.py` **lacks the stop reader entirely**. If the close is ever switched to the plugin copy, the stops go blank again. Needs its own change-set.
