---
strategy_tag: AEGIS
allocated_capital_usd: null
dyncap_usd: null
brokers: [tiger, ibkr]
---

# Aegis Sub-Fund Config

This is the **one place** the Aegis sub-fund's capital lives (D-21). Edit the block at the top by hand, or tell the cockpit in plain English ("set my Aegis allocation to 60,000") and it updates this file and logs the change. The machine reads only the block between the `---` lines; everything below is for you.

## The fields

- **strategy_tag** — always `AEGIS`. This is the label stamped on every Aegis order (D-17) so its capital and positions are never confused with the other two strategies (Income Wheel, Protege9) sharing the same brokers. Do not change it.
- **allocated_capital_usd** — **the one number you must set.** Your capital allocation to the Aegis strategy. Until it has a value, sizing deliberately refuses (no anchor = no position sizing). Example: `allocated_capital_usd: 60000`.
- **dyncap_usd** — dynamic capital: your allocation plus realised profit/loss from closed Aegis trades only. Leave it `null` and the system seeds it to your allocation on day one, then maintains it from the Aegis PTJ. You normally never touch this.
- **brokers** — the brokers Aegis trades through. Leave as is unless that changes.

## Why an MD file and not a hidden setting

You wanted something you can open and adjust yourself without going through code or an interface. This is that file. It is the only sub-fund config that exists — the other two strategies are deliberately not modelled here (D-21); if they are ever brought under this system they get their own sibling files (`config/income_wheel_fund.md`, `config/protege9_fund.md`), never new keys bolted onto this one.

## How it's used

Sizing, dynamic capital, and every risk gate (beta / VaR / leverage / combined-stop) compute against **this fund's** capital and the Aegis PTJ book — never the co-mingled broker account totals. That separation is what makes the numbers you see actually about Aegis.
