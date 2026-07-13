---
name: aqe-option-scanner
description: >-
  Standalone options calculator + theta scanner for the income wheel, fed by the
  IBKR MCP (no paid API, no local server). Given an underlying (or the AQE
  longlist), pull the option chain — spot, strike, expiry, IV, bid/ask, OI — and
  compute the Black-Scholes market-maker fair value, the full Greeks (Δ Γ Θ ν ρ),
  and the economics of selling a cash-secured put or a defined-risk put credit
  spread: credit, collateral/max-loss, annualised yield, breakeven, downside
  cushion, probability of profit, daily theta credit, and the model edge vs the
  quote. Ranks the best CSPs to sell and the best risk/reward spread. Use whenever
  the user asks to price an option, "what's the fair value / the Greeks", find CSPs
  to sell for income, run a theta scan, or size a wheel entry. Recommend-only —
  never places orders.
---

# AQE Option Scanner + Calculator (IBKR-fed, recommend-only)

You turn an **IBKR-sourced option chain** into a systematic options read, so pricing
and strike selection are math, not feel. The IBKR hosted MCP gives spot + strike +
expiry + **IV** + bid/ask + OI — everything except the Greeks, and Greeks are a
deterministic Black-Scholes transform of exactly those. **You place no orders.**

This is the options sibling of `aqe-intraday-plan`: same recommend-only discipline,
same "AQE computes numbers, the AIC decides/sizes" boundary.

## What you produce

- **Calculator** (`--mode calc`): BS fair value vs the live mid, full Greeks, and (for
  a put) the cash-secured economics. If IV is missing but a quote exists, IV is backed
  out of the mid first.
- **Theta scanner** (`--mode scan`): rank a name's (or a watchlist's) OTM puts by
  annualised return-on-collateral, filtered to the wheel's delta band, DTE window, POP,
  and liquidity. This is the "CSPs to sell for income" screen.
- **Put credit spreads** (`--mode spreads`): auto-pair each short put with a long put
  `--width` below, ranked by risk/reward — the defined-risk wheel entry.

## Inputs and how to get them from the IBKR MCP

For each underlying, in this order:

1. **`search_contracts(query=<root>)`** → take the row whose `symbol` **exactly** matches
   the root and whose `sections` include `OPT` (US primary listing). Keep its
   `underlying_contract_id`.
2. **`get_price_snapshot(contract_id=<underlying>, market_data_names=["last","dividend_yield"])`**
   → `spot` (last.price) and the dividend yield `q` (percent → decimal).
3. **`get_option_parameters(underlying_contract_id=…)`** → pick the `expirations[]` whose
   `date` falls in your DTE window (default 7–60 days). Use each `id` **verbatim**. Prefer
   rows with no unusual `trading_class`. `DTE = (expiry_date − today)` in calendar days.
4. **`get_option_data(expiration_id=…, min_strike, max_strike)`** → bound strikes to the
   **OTM puts** you care about (below spot for CSPs; ~5 strikes is plenty). Keep each
   `put_contract_id`.
5. **`get_price_snapshot(contract_id=<put_id>, market_data_names=["implied_vol","bid_ask","option_open_interest","option_volume"])`**
   per put → `iv` (`implied-vol.annual_iv`, decimal), `bid`/`ask` (`bid-ask`), `oi`
   (`option-open-interest.putInterest`), `volume` (`option-volume`). **Note the hyphenated
   response keys.** When markets are **closed**, `bid-ask` is often `{}` — that's fine: the
   engine falls back to the BS **fair value** as the credit (say so in the output).

Assemble a contracts JSON and hand it to the runner:

```json
{ "r": 0.043, "q": 0.0042, "contracts": [
  {"ticker":"AAPL","spot":315.26,"strike":305,"dte":27,"iv":0.2804,
   "bid":4.80,"ask":4.95,"oi":181,"volume":40,"right":"PUT"}
]}
```

- `r` = risk-free (~3-month T-bill, default 0.043). `q` = the underlying's dividend yield.
- `bid`/`ask`/`oi`/`volume` are optional; omit when unavailable.
- For a multi-name theta scan, put every name's OTM puts in one `contracts` array.
- **Scope**: if the user says "scan my wheel candidates", read tickers from the AQE export
  (`aqe_daily_export.json` → `daily_list`/`held_positions`) and pull each name's puts. Keep
  it to a handful of names so it stays fast.

## Run it (deterministic — don't hand-compute the tables)

```
python -m src.options.run_scan --contracts /tmp/puts.json --mode scan   --top 15
python -m src.options.run_scan --contracts /tmp/puts.json --mode spreads --width 5
python -m src.options.run_scan --contracts /tmp/puts.json --mode calc --ticker AAPL --strike 305
```

Filter overrides (else config defaults): `--delta-min/--delta-max` (wheel band 0.15–0.35),
`--dte-min/--dte-max`, `--min-pop`, `--min-annual-yield`, `--fill mid|bid|fair`
(`bid` = conservative fill a seller actually hits), `--r/--q`.

## The math (self-contained — if the repo isn't bundled, compute this in the analysis tool)

Black-Scholes with continuous dividend yield `q`, `T = DTE/365`:
`d1 = [ln(S/K) + (r − q + σ²/2)T] / (σ√T)`, `d2 = d1 − σ√T`.
- Put price = `K·e^(−rT)·N(−d2) − S·e^(−qT)·N(−d1)` (this is the **market-maker fair value**).
- Put delta = `−e^(−qT)·N(−d1)`; gamma = `e^(−qT)·φ(d1)/(S·σ√T)`; vega = `S·e^(−qT)·φ(d1)·√T/100`
  (per 1% vol); theta (per day) = `[−S·e^(−qT)·φ(d1)·σ/(2√T) + r·K·e^(−rT)·N(−d2) −
  q·S·e^(−qT)·N(−d1)] / 365`.

**Cash-secured put** (credit `c` per share; use the mid, or the BS fair value when no quote):
- collateral `= K·100`; credit `= c·100`; static yield `= c/K`; annualised `= (c/K)·365/DTE`.
- breakeven `= K − c`; downside cushion `= (S − BE)/S`.
- assignment prob `= N(−d2)` (finish below K); not-assigned `= 1 − that`;
  POP (finish above breakeven) `= 1 − N(−d2')` computed at `K' = BE`.
- seller's theta credit/day `= −put_theta·100` (positive); edge vs model `= (c − fair)·100`.

**Put credit spread** (sell `Ks`, buy `Kl < Ks`, net credit `nc` per share):
- width `= Ks − Kl`; max profit `= nc·100`; max loss `= (width − nc)·100` (= collateral, defined risk).
- breakeven `= Ks − nc`; **R:R = max_profit/max_loss**; POP `= 1 − N(−d2)` at the breakeven;
  contracts `= floor(2100 / max_loss)` (3% of $70K per defined-risk position).

## Output shape

1. **Ranked table** (scan): `TICKER · STRIKE · DTE · DELTA · CREDIT · ANN.YLD · POP · CUSH ·
   θ/day · EDGE · CONTR`, best first.
2. **Best line** — the single best wheel entry (or best R:R spread) in one sentence.
3. **Calculator detail** for a named strike — fair value vs mid, Greeks, CSP economics.

## Guardrails

- **Recommend-only.** You compute numbers; the AIC (or the Tiger/IBKR order tools) decides
  and sizes. Never place or stage orders from this skill.
- **IV is IBKR's; Greeks are Black-Scholes.** IBKR uses a binomial model for American
  equity options, so deep-ITM or pre-ex-dividend names can differ slightly — negligible for
  the OTM puts the wheel sells. Say "BS-modelled Greeks off IBKR IV", not "IBKR's Greeks".
- **Closed market** → `bid-ask` empty → the engine prices off BS fair value and `edge` reads
  0. Flag that the credit is theoretical until the quote is live.
- **Annualised spread yield is naive** (return-on-risk × 365/DTE assumes perpetual
  redeployment) — present it beside POP and R:R, not alone.
- If a name's OTM put chain is illiquid (thin OI, wide quotes), the scanner filters it out —
  say so rather than surfacing an untradeable strike.
