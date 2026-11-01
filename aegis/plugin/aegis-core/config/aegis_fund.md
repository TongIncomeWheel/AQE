---
strategy_tag: AEGIS
allocated_capital_usd: 75000
dyncap_usd: 66699
one_r_usd: 620
one_r_basis: "PM 2026-10-27: 1R = 1% of the $62K portfolio = $620, a FIXED dollar figure; share count = floor(620 / (entry - stop)). Supersedes parameters.yaml capital.one_r_pct_of_dyncap while set."
brokers: [tiger]
ptj_drive_folder_id: 15PR74ws_kTXTqCcEfRGga_jjHrMvbCEM
---

# Aegis Sub-Fund Config

This is the **one place** the Aegis sub-fund's capital lives (D-21). Edit the block at the top by hand, or tell the cockpit in plain English ("set my Aegis allocation to 60,000") and it updates this file and logs the change. The machine reads only the block between the `---` lines; everything below is for you.

## The fields

- **strategy_tag** — always `AEGIS`. This is the label stamped on every Aegis order (D-17) so its capital and positions are never confused with the other two strategies (Income Wheel, Protege9) sharing the same brokers. Do not change it.
- **allocated_capital_usd** — **the one number you must set.** Your capital allocation to the Aegis strategy. Until it has a value, sizing deliberately refuses (no anchor = no position sizing). Example: `allocated_capital_usd: null`.
- **dyncap_usd** — dynamic capital (D-41, mark-to-market): your allocation plus realised P&L on closed Aegis trades PLUS unrealised P&L on open Aegis positions = your **current Aegis equity**. It moves with the market and is refreshed each premarket from the Aegis PTJ, so sizing always tracks what you actually hold (and shrinks in drawdown). Leave it `null` to let the ledger maintain it; the value below is the current mark as you last stated it.
- **one_r_usd** — **THE ONE risk-per-trade figure (BUILD_PLAN Phase 1, 2026-11-01).** The PM set 1R = $620 on 27 Oct 2026 (1% of the $62K portfolio) as a fixed dollar amount. Every Aegis tool that sizes reads it from here through `tools/fund_config.py one_r_usd()`: `bracket_calc.py`, the live review (`aegis-live`), the cards. While it is set, `parameters.yaml capital.one_r_pct_of_dyncap` (1.5%) is not used. Set it to `null` to fall back to the percent rule. Three figures were in production before this line ($2,250 in AQE's alert cards — 3% of $75K, which the PM has ruled to ignore — $2,100 in CLAUDE.md, and $620 here); AQE's alert cards are AQE's own config and are not changed by this file. **Note for the PM:** `allocated_capital_usd` still reads 75,000 and `dyncap_usd` 66,699 while the 27 Oct ruling spoke of a $62K portfolio — confirm which is current; sizing uses `one_r_usd` either way.
- **brokers** — the brokers Aegis trades through. Tiger only (D-98 — IBKR retired, no residual capital there). Leave as is unless that changes.

## Why an MD file and not a hidden setting

You wanted something you can open and adjust yourself without going through code or an interface. This is that file. It is the only sub-fund config that exists — the other two strategies are deliberately not modelled here (D-21); if they are ever brought under this system they get their own sibling files (`config/income_wheel_fund.md`, `config/protege9_fund.md`), never new keys bolted onto this one.

## How it's used

Sizing, dynamic capital, and every risk gate (beta / VaR / leverage / combined-stop) compute against **this fund's** capital and the Aegis PTJ book — never the co-mingled broker account totals. That separation is what makes the numbers you see actually about Aegis.
