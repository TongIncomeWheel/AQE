# AQE Data-Source Audit — 9 Aug 2026

Scope: the **AQE Scanner** (equity engine + export). Where an item touches the
**Option Scanner** it is named explicitly.

Every entitlement claim below was probed live against our own FMP **Starter**
plan on 2026-08-09, not read off a pricing page. Denials are quoted verbatim.

Verdicts: **HAVE** (already built) · **BUILD** (feasible, worth it) ·
**SKIP** (feasible, not worth it) · **GIVE UP** (not obtainable).

---

## 1. EMA vs SMA — HAVE (both, deliberately split)

Two helpers, `src/engines/utils.py`:

| | formula |
|---|---|
| `sma(x, n)` | `x.rolling(n, min_periods=n).mean()` |
| `ema(x, n)` | `x.ewm(span=n, adjust=False).mean()` — TradingView-equivalent |

**The rule the codebase follows:** EMA where a signal must *turn fast*
(impulse, MACD, pullback-to-mean). SMA where a level must *stay still*
(support/resistance, volume baselines, long-term trend).

### EMA — every use

| Where | Periods | Purpose |
|---|---|---|
| `elder.py:23,38` | **13** + MACD **12/26/9** | Elder Impulse — the whole engine |
| `bq.py:72` | **20** | Mode-3 "smooth pullback" (close within 1×ATR20 of a rising EMA20) |
| `bq.py:132-134` | **8 / 13 / 21** | EMA-convergence score (`bq_ema_conv`, 25 pts) |
| `energy.py:84,147` | **20**, MACD **12/26** | Trend gate + MACD line |
| `flow.py:163` | **20** | Flow trend reference |
| `structure.py:82` | **20** | Structural trend reference |
| `readiness.py:92-94,160-161` | **8 / 13 / 21**, MACD **12/26/9** | Stack + momentum |
| `health.py:42` | **21** | Health trend |
| `divergence.py:95` | MACD **12/26** | DETECT divergence oscillator |

### SMA — every use

| Where | Periods | Purpose |
|---|---|---|
| `bq.py:46-47,62` | vol **5/20**, close **50** | Volume dry-up, uptrend filter |
| `energy.py:103,136,171-172` | close **20**, vol **20**, ATR **5/20** | Bollinger basis, vol baseline, ATR compression |
| `flow.py:127-128,168` | vol **5/20**, TR **20** | Volume surge, true-range baseline |
| `structure.py:69,100` | close **50**, vol **20** | Trend + volume confirm |
| `readiness.py:81-82,123` | vol **5/20**, range **5** | Volume + range contraction |
| `health.py:84` | **weekly 10** | Weekly trend |
| `srm.py:293` | **20** | Sector-ETF trend |
| `qs_fields.py:40,94` | **200** | `trend_200` on the **equal-weight universe index** |
| `drive_sync.py:543-546` | **20 / 50 / 100 / 200** | Exported `ma_20…ma_200` — **all SIMPLE** |
| `drive_sync.py:900` | **50** | `sma_distance_pct` = distance from the 50-day SMA |

### One real inconsistency worth fixing

The export publishes **SMA** `ma_20`, but Flow / Energy / Structure / BQ all
gate on **EMA 20**. So a name can read "below `ma_20`" in the JSON while the
engine that scored it saw price *above* its EMA20. Not a bug — but an AI reader
(or the committee) can draw the wrong conclusion from it.

→ **BUILD (small):** add `ema_20` and `ema_21` alongside `ma_20` in the export,
with a glossary line naming which engines use which. ~10 lines in `drive_sync.py`.

---

## 2. RSI from FMP — HAVE in-house; do NOT source it

- `utils.py:102` — `rsi(x, n=14)`, Wilder's. Already used by
  `pipeline_rank.py:115` and `divergence.py:92`.
- FMP `technical-indicators/rsi` **is** Starter-entitled (confirmed).

**Recommendation: don't fetch it.** It would cost one API call per ticker per
day (600+) for a number we compute for free from bars we already hold, and it
would introduce a vendor dependency on a value that is currently reproducible
offline. The only sane use is a *one-off* cross-check of our implementation.

**Gap:** RSI is computed but never **exported**. The committee can't see it.

→ **BUILD (small):** add `rsi_14` (daily) and `rsi_14_w` (weekly) to
`daily_list`. Uses the existing helper, no new calls.

---

## 3. ZN / 10-year yields — BUILD (high value, low cost)

Two routes, **both verified live on our Starter key**:

**a) The actual UST curve** — `stable/treasury-rates`.
Returns 1m, 2m, 3m, 6m, 1y, 2y, 3y, 5y, 7y, 10y, 20y, 30y.
Live sample (2026-08-07): `10y 4.65 · 2y 4.19 · 30y 5.19 · 3m 3.87`.
This gives you the yield itself, plus **2s10s, 3m10y, 10s30s** curve shape —
strictly better than any futures price for correlation work.

**b) Treasury futures** — `stable/quote?symbol=…`
`ZNUSD` (10y note) · `ZBUSD` (30y bond) · `ZFUSD` (5y) · `ZTUSD` (2y) ·
`ZQUSD` (30-day Fed Funds).

**What we do today:** nothing of the sort. `MACRO_INSTRUMENTS`
(`srm.py:711`) proxies rates with **TLT** — a 20y+ bond *ETF*. It is not the
10-year, it is duration-levered, and it moves with credit spread as well as
rates. That is the "sourced but not tuned to be insightful" you flagged.

→ **BUILD.** Add the treasury curve to the macro layer; keep TLT as a
*tradeable* instrument but stop using it as the rates *signal*.

---

## 4. Crude / gold / copper / silver futures — BUILD (symbols confirmed)

FMP `commodities-list` is open on Starter. Confirmed symbols:

| Asset | Symbol | Asset | Symbol |
|---|---|---|---|
| WTI crude | `CLUSD` | Gold | `GCUSD` |
| Brent crude | `BZUSD` | Silver | `SIUSD` |
| Nat gas | `NGUSD` | Copper | `HGUSD` |
| Heating oil | `HOUSD` | Platinum / Palladium | `PLUSD` / `PAUSD` |
| RBOB gasoline | `RBUSD` | **US Dollar index** | `DXUSD` |
| | | S&P / Nasdaq / Russell / Dow | `ESUSD` / `NQUSD` / `RTYUSD` / `YMUSD` |

Historical EOD works through the *same* endpoint our client already calls
(`stable/historical-price-eod/full`), so `FMPClient.get_daily_bars()` needs
**no change** — pass the commodity symbol and it works.

**What we do today** (`MACRO_INSTRUMENTS`, `srm.py:711`) — ETF proxies:
`TLT, UUP, HYG, IWM, GLD, CPER, USO`.
- **No silver at all.**
- `USO` is the worst offender — a front-month roll vehicle whose long-horizon
  return diverges badly from spot crude. Correlations computed against USO are
  measuring contango as much as oil.
- `UUP` vs `DXUSD`: same index, one has an expense drag and an ETF wrapper.

→ **BUILD.** Swap the proxies for the futures series where the proxy is worse
than the thing itself (`USO→CLUSD` first, `UUP→DXUSD` second), add silver.

**Caveat to carry:** these are continuous front-month series with roll gaps.
Fine for correlation and rate-of-change. **Never** use them for a level-based
stop or a price target.

---

## 5. Intraday VWAP on demand — HAVE (two of them, already wired)

| Which | Where | Bars | Surfaced |
|---|---|---|---|
| **5-day rolling VWAP** | `elder_context.py:118-129` | hourly, last 40 | Export `vwap_5d` {value, ABOVE/BELOW, slope_5d}; Scanner filter columns `ecx_vwap_pos`, `ecx_vwap_slope` |
| **Session VWAP** | `intraday/bracket.py:57,73-74` | 5-min | **Pricer page**, on demand — candidate stop `vwap − 0.5 × intraday_ATR` |

Feed: `FMPClient.get_intraday_bars(ticker, interval)` — 1min/5min/15min/30min/
1hour/4hour, Starter-entitled, already in production.

→ **HAVE. Nothing to build.**
Optional extra if you want it: **anchored VWAP** (from an earnings date, a
pivot low, or a BOS bar) — same bars, ~30 lines, would slot into the Pricer
next to the existing candidate stops.

---

## 6. CFTC Commitment of Traders — BLOCKED on FMP; free direct from CFTC

FMP has it. Our key does not. Probed live, verbatim:

> ACCESS DENIED: This tool ("commitmentOfTraders") requires the Premium,
> Ultimate, or Enterprise plan. The user is currently on the **Starter** plan.

**But COT is a public government dataset.** CFTC publishes the report itself
every Friday 15:30 ET as CSV/XLS on cftc.gov — no key, no plan, no vendor.
One file a week, self-parsed.

→ **BUILD via cftc.gov direct, or SKIP.**
My call: build it **only if** you would actually act on positioning extremes.
COT is weekly, reports Tuesday's book on Friday (3-day lag), and is a slow
context dial — it is not a signal, and it will never be timely enough to move a
2-day-max-age scan. Upgrading FMP for it would be paying for something that is
free upstream.

---

## 7. Goldman prime brokerage report — GIVE UP

Proprietary GS Prime Services client research. Not on FMP, not on Alpaca, not
on IBKR, not on Tiger, not public. The only lawful routes are being a GS Prime
brokerage client or a licensed redistributor. Second-hand summaries circulate
on X and in press coverage — unciteable, usually partial, often distorted.

→ **GIVE UP.** Do not build a scraper for it.

**Nearest thing we can legitimately build:** the *questions* the GS note answers
are "what is the crowd positioned in, and where does it break". We already
answer half of that with SRM sector grades + thematic **constituent breadth**.
The institutional-ownership half (13F) is also out of reach — FMP's `form13F`
was probed and requires **Ultimate or Enterprise**.

---

## 8. Options open interest + gamma maps — BUILD (medium), scoped

This is an **Option Scanner** item, not the AQE Scanner.

**What we already have:**
- `src/options/greeks.py:81` — Black-Scholes **gamma** is already computed.
- Alpaca `/v1beta1/options/snapshots` — full chain, IV + greeks + quotes, one
  call per underlying.

**What is missing — two things, both small:**
1. **Open interest.** Our adapter deliberately skips it — `alpaca.py:5-7`:
   *"Open interest is deliberately NOT fetched — liquidity is implicit."*
   That was the right call for a CSP sweep and the wrong one for a gamma map.
2. **The call side.** `fetch_put_chain()` requests `type=put` only. A gamma map
   needs both.

Alternative OI sources already live in this session: **IBKR** `get_option_data`
and **Tiger** `get_option_briefs` both carry open interest.

**Cost:** roughly 2× the chain calls. For SPY/QQQ + held + longlist (~50 names)
that is trivial. For the full 600-name universe it is ~1,200 snapshot calls —
doable on Alpaca's per-underlying endpoint, impossible on a per-contract API.

→ **BUILD, scoped to index + held + longlist.** Not the full universe.

**Caveat that must ship with it:** dealer gamma (GEX) is a *positioning model*,
not a measurement. It assumes dealers are short customer gamma across the
board. That assumption is sometimes wrong, and when it is wrong the map points
the wrong way. Label it as a model, the way we label `pattern` as a visual flag.

---

## 9. CTA / systematic trend models — BUILD (medium-large). Highest value here.

The specific proprietary weekly (GS / Nomura / UBS style) is not purchasable
through any feed we have → **the report itself: GIVE UP.**

**But the method is fully public and genuinely simple**, and this is the one
item on the list where replication is a real substitute rather than a
consolation prize:

- **Moskowitz–Ooi–Pedersen (2012), time-series momentum** — sign of the
  trailing 12-month excess return per market, vol-scaled to a constant target.
- **Faber (2007), GTAA** — price vs the 10-month SMA.
- **Industry-standard proxy blend** — 2 / 6 / 12-month lookbacks, equal
  weighted, vol-targeted around 10% annualised.

All of it runs on **daily bars we can already pull**, and §4 above gives us the
liquid futures universe those models actually trade: `ZN ZB ZF ZT` (rates),
`CL BZ NG HO RB` (energy), `GC SI HG PL PA` (metals), `ZC ZS ZW ZM ZL`
(ags), `ES NQ YM RTY` (equity index), `DX` (dollar).

**The output worth having is not the positioning estimate — it is the flip
levels.** "CTAs turn seller of ES below 6,240" is what people actually trade off
those notes, and it is a deterministic function of the model, not of GS's book.

→ **BUILD.** Suggested shape: a weekly job, one signal per market, an aggregate
long/short reading, and a **trigger table** of the prices at which each market
flips sign over the next 1 / 5 / 20 sessions.

**Honest caveat:** our estimate will not match GS's. The direction and the flip
levels will be close (the models are near-identical); the AUM weighting is a
guess, and GS has a survey of actual books that we do not.

---

## Summary

| # | Item | Verdict | Effort |
|---|---|---|---|
| 1 | EMA vs SMA usage | **HAVE** — both, split by design | — |
| 1b | Export `ema_20/21` next to `ma_20` | **BUILD** | small |
| 2 | RSI | **HAVE** in-house — don't source from FMP | — |
| 2b | Export `rsi_14`, `rsi_14_w` | **BUILD** | small |
| 3 | 10-year yield / UST curve (`treasury-rates`) | **BUILD** — Starter-entitled, verified | small |
| 3b | ZN/ZB/ZF/ZT futures | **BUILD** | small |
| 4 | Crude / gold / copper / **silver** / dollar futures | **BUILD** — replaces bad ETF proxies | small |
| 5 | Intraday VWAP on demand | **HAVE** — 5-day hourly + session, both live | — |
| 5b | Anchored VWAP | **BUILD** (optional) | small |
| 6 | CFTC COT | FMP **blocked** (Starter). Free direct from cftc.gov | medium / **SKIP** |
| 7 | Goldman prime brokerage report | **GIVE UP** — proprietary | — |
| 7b | 13F institutional ownership | **GIVE UP** on FMP (Ultimate+) | — |
| 8 | Options OI + gamma map (**Option Scanner**) | **BUILD**, scoped | medium |
| 9 | CTA trend model replication + flip levels | **BUILD** — best value on this list | medium-large |

**If only three get built:** §3 (real yields + curve), §4 (real futures instead
of USO/UUP/no-silver), §9 (CTA flip levels). Those three turn the macro layer
from decoration into something with a level you can trade against.
