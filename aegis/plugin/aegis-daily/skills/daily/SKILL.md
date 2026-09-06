---
name: daily
description: "AEGIS DAILY — the one scheduled command. Three stages, every trading day: (1) close the book — pull Tiger, run the PTJ batch for real, push the journal to GitHub; (2) print the held book on screen and prove the file is on GitHub main where the committee picks it up; (3) the portfolio journal (WTD/MTD/QTD/YTD as NAV change) and the trade journal (every fill, every round-trip with entry/exit/qty/fees/net P&L, open lots, reconciliation findings), printed and filed. Deterministic tools only. No voices, no committee, no orders. Does not trigger AQE."
model: sonnet  # sonnet [RB:model_tiers.control] — PINNED, not inherited (D-92). packaging/build_claude.py hard-fails the build if this literal ever drifts from charter/parameters.yaml.
---

# DAILY — close the book, show it, keep the portfolio journal

**Three stages, always in this order, one command, no stopping to ask.** It stops only to page.

| Stage | What it does | Done when |
|---|---|---|
| **1 — Close** | Pull Tiger, run the PTJ batch for real, push the journal to GitHub. Procedure: `skills/ptj/SKILL.md`, MODE C — the only copy; do not restate it here. | `post_market` gate stamped and the journal is on GitHub main. |
| **2 — Show** | Print the trade journal on screen as tables, then read the journal back from GitHub main to prove it is there for the committee (`/pma`) and for AQE to pick up. | The PM has the book in front of him and the file is confirmed on `main`. |
| **3 — Portfolio + trade journal** | Print what the close just filed: the portfolio stats (WTD / MTD / QTD / YTD / inception as NAV change, the week table, the last ten closes) and the trade journal — Aegis only: every trade in and out (date, qty, entry, exit, fees, net P&L, days, R), open positions, stats, reconciliation findings, then confirm both ledgers are on GitHub main. | The PM knows what the book is *doing* and can see every trade that got it there, and both series are saved. |

**Cowork is the runtime; GitHub is the filing cabinet.** The skill runs here. The tools run from a fresh clone of the repo. The files it produces are pushed to the repo so they persist and so `/pma` (a different session, its own checkout) and AQE can read them. Nothing runs *from* GitHub, and this skill never triggers a GitHub workflow — the AQE daily pipeline has its own Claude Code routine (PM decision 2026-09-06).

**Order-blind (constitution law 1).** Nothing here places, sizes or arms an order. **Data plane only (law 4).** Every step is a deterministic tool call plus GitHub reads/writes. No judgment-tier agent is ever spawned by this skill.

---

## Stage 0 — Workspace and date (every run, no memory assumed)

1. **Fresh checkout.** `git clone https://github.com/TongIncomeWheel/AQE.git` to a fresh path and `cd aegis/`. Never reuse a stale clone — the journal, the ledgers and the gate file live in git and are pushed back to git.
2. **Stamp the clock.** Run `date` live for SGT and US Eastern. Never assert a date from memory.
3. **Pick the journal date.** Read `data/persistent/phase_state.json` and `ls data/journal/`. `DATE` is the next US trading day after the most recent journal already processed (skip weekends and any date in `data/persistent/market_holidays.json`). If more than one trading day is missing, run all three stages for each missing date, oldest first.

---

## Stage 1 — Close the book

Open `skills/ptj/SKILL.md` and run **MODE C** end to end for `DATE`: the Tiger pull, `bash scripts/run_post_market.sh DATE`, and the mandatory connector push-and-verify that file's D-110/D-111 section spells out.

| PTJ MODE C ended | Do this |
|---|---|
| exit 0 — gate `ok` | Say "Book closed and pushed." Go to Stage 2. |
| exit 1 — degraded, gate `partial` | Go to Stage 2; carry every degraded line into the print, verbatim. |
| exit 2 — halted | **Stop.** Page with what failed, verbatim. No Stage 2 or 3. Lever: `/recover post-market`. |
| D-100 halt (position vanished, no matching fill) | `get_transactions(symbol=TICKER)` per vanished name, append the missing close to `tiger_filled_orders.json` with a `d100_recovery_note`, re-run Stage 1. |

Aegis membership is automatic (D-106): unrecognized equity fills auto-include, flagged `auto_included_unrecognized`. Report every such name in Stage 2; never decide, never ask. The PM's lever is `held_book_refresh.py reject`.

---

## Stage 2 — Show the book, prove it is filed

**Print, do not send a file.** Render `skills/ptj/SKILL.md` Step 3's print spec, items 1–6 and 8, as markdown tables: held book · overnight (opened / closed with realised P&L / stops that moved — say "nothing changed overnight" plainly if empty) · the day · realised P&L MTD / WTD / YTD · open risk (with any `unknown_stop` named) · capital (dynCap, 1R, gross exposure, leverage, **book beta**, **book exposure**, 1-month VaR — beta and exposure on their own line) · anything not clean (every `auto_included_unrecognized` name, every `pending_review` option leg, `no_live_stop`, `entry_date_unknown`, stop MISMATCH, any D-100 recovery).

**Then prove the filing.** Read `aegis/data/journal/aegis_journal_DATE.json` back from GitHub `main` via the connector (`get_file_contents`), `json.loads()` it, confirm its `date` is `DATE`. Print: "Journal for DATE on GitHub main (commit SHA)." If it is not there, Stage 1's push did not land — finish D-110's push-and-verify before going on. `/pma` and AQE both read this file from `main`; a journal that only exists on this container was never filed.

---

## Stage 3 — The portfolio journal and the trade journal

Stage 1's batch already appended today's close to two persistent ledgers and rendered both: `data/persistent/portfolio_ledger.json` → `data/eod/DATE/portfolio_stats_DATE.md` (job 10.6-10.7, D-114) and `data/persistent/trade_journal.json` → `data/eod/DATE/trade_journal_DATE.md` (job 10.8-10.9, D-115). This stage puts them in front of the PM and confirms they are filed.

1. **Portfolio — print the file's tables, do not recompute anything.** From `portfolio_stats_DATE.md`, in order: the headline line (Aegis NAV, day P&L, realised cum, unrealised, open count) · the **periods** table (WTD · MTD · QTD · YTD · inception — start NAV, end NAV, total P&L, return, realised, unrealised change, trades W/L, max drawdown) · the note under it if a period's start NAV is the allocation · the **weeks** table · the **last ten closes** · any flags. The whole-account Tiger line is reference only — print it as the file labels it, never as Aegis performance.
2. **Trade journal — print the file's tables, do not recompute anything.** From `trade_journal_DATE.md`: the Aegis stats line (trades, W/L, win rate, net P&L, profit factor, expectancy, avg hold, avg R) · **closed trades since the last run**, every column (out, in, ticker, qty, entry, exit, gross, fees, net, %, days, R, notes) — and the last ten in any case · the **open positions** table · **every line under "Reconciliation" and "Flags", verbatim.** A reconciliation line is a finding about the book of record (a fill missing from the saved pulls, an archive entry booked off the wrong cost) — it is the PM's call, never yours, and never swallowed.
3. **One-line read.** After the tables, one plain sentence: the week so far, the month so far, the worst drawdown in the period, and how many trades closed since the last run with their net — numbers from the tables, no adjectives. If a day P&L shows "—" the series just started; say that.
4. **Prove the filing.** Read `aegis/data/persistent/portfolio_ledger.json` and `aegis/data/persistent/trade_journal.json` back from GitHub `main` via the connector, `json.loads()` both, and confirm the portfolio ledger's `latest_close` and the trade journal's `latest_fill_utc` match what the files printed. Print: "Portfolio ledger through <close> and trade journal through <fill time> on GitHub main." If either is not there, push #2 did not land — finish D-110's push-and-verify.

**What the numbers are.** Aegis NAV = dynCap = allocation + cumulative realised + unrealised on Aegis-confirmed positions (D-41/D-99) — never the co-mingled Tiger account NAV. Period figures are NAV change with realised split out and the baseline named. Trade P&L is FIFO, net of all fees — the same basis as the broker's own realised figure; the archive ledger books off average cost gross of the sell commission, which is why small differences are fees and only large ones are findings. If a number looks wrong, print the wrong number and say it looks wrong (`portfolio_ledger.py selftest`, `trade_journal.py selftest` and the files' flags are the diagnostics); never quietly correct it on screen.

## Closing report — the whole thing, on screen, every run

State which `DATE`(s) were processed, then Stage 2's tables, then Stage 3's portfolio and trade-journal tables with the reconciliation lines and the one-line read, then three status lines:

| | |
|---|---|
| **Book** | closed / degraded (which lines) / halted — and the `post_market` gate status as stamped |
| **Filed** | journal for DATE, portfolio ledger through <close>, trade journal through <fill time> — all confirmed on `main` (commit SHA) — or which is not, and why |
| **Next** | "`/premarket` (data prep) and then `/pma` are unblocked once AQE has published today's export" — or what is blocking them |

**Never report a stage as done that you did not see finish.** A file you did not read back from `main` is not filed. An honest "couldn't confirm" beats a fabricated pass every time (D-111).

---

## What this skill must not do

Trigger, dispatch, poll or wait on the AQE daily pipeline or any GitHub workflow · spawn a voice, the committee desk, or any judgment-tier agent · run `/premarket`'s export pull or coverage checks (they run later, from `/premarket`, once AQE has published) · recompute any portfolio number by hand instead of printing the file · place, stage, or modify a broker order · restate the broker pull or the batch here instead of calling `skills/ptj/SKILL.md` MODE C · report success it has not read back from GitHub.
