---
strategy_tag: AEGIS
allocated_capital_usd: 75000
dyncap_usd: 64000
brokers: [tiger, ibkr]
---

# Aegis Sub-Fund Config

This is the **one place** the Aegis sub-fund's capital lives (D-21). Edit the block at the top by hand, or tell the cockpit in plain English ("set my Aegis allocation to 60,000") and it updates this file and logs the change. The machine reads only the block between the `---` lines; everything below is for you.

## The fields

- **strategy_tag** — always `AEGIS`. This is the label stamped on every Aegis order (D-17) so its capital and positions are never confused with the other two strategies (Income Wheel, Protege9) sharing the same brokers. Do not change it.
- **allocated_capital_usd** — **the one number you must set.** Your capital allocation to the Aegis strategy. Until it has a value, sizing deliberately refuses (no anchor = no position sizing). Example: `allocated_capital_usd: null`.
- **dyncap_usd** — dynamic capital (D-41, mark-to-market): your allocation plus realised P&L on closed Aegis trades PLUS unrealised P&L on open Aegis positions = your **current Aegis equity**. It moves with the market and is refreshed each premarket from the Aegis PTJ, so sizing always tracks what you actually hold (and shrinks in drawdown). Leave it `null` to let the ledger maintain it; the value below is the current mark as you last stated it.
- **brokers** — the brokers Aegis trades through. Leave as is unless that changes.

## Why an MD file and not a hidden setting

You wanted something you can open and adjust yourself without going through code or an interface. This is that file. It is the only sub-fund config that exists — the other two strategies are deliberately not modelled here (D-21); if they are ever brought under this system they get their own sibling files (`config/income_wheel_fund.md`, `config/protege9_fund.md`), never new keys bolted onto this one.

## How it's used

Sizing, dynamic capital, and every risk gate (beta / VaR / leverage / combined-stop) compute against **this fund's** capital and the Aegis PTJ book — never the co-mingled broker account totals. That separation is what makes the numbers you see actually about Aegis.
