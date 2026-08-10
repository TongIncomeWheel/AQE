# Nick Crown Macro Layer

Implementation of **Crown Institutional Process — Deployment Kernel v1.4**.
Built **standalone** by PM directive (2026-08-09): it reads nothing from SRM,
Macro Weather or the Thematic RRG, and nothing there reads it. Merging and
de-duplicating the four is a later, separate decision — keeping them apart now
is what makes the overlap measurable instead of assumed.

Code: `src/macro/crown/` · Page: **🫀 Crown Macro** · Tests: `tests/test_crown_macro.py`
Artifact: `output/crown_macro.json` (runtime; carried by Daily Persist, not git)

---

## The idea

Most traders look at price first. Institutional desks look at **positioning,
breadth and regime** first. Price lags; the average stock and the index often
tell different stories; mechanical flows (CTAs) and dealer hedging (gamma)
create predictable pressure; VIX structure reveals stress the index hides.

The hierarchy is not decoration — the order is the method (§2.1, §4):

```
1. Heartbeat (RSP / SPY)            ← what kind of market is this?
2. If confidence is low → STOP.     ← the conditional gate
3. Positioning (CTA + COT + Gamma)  ← who is in, and how crowded?
4. VIX structure & dispersion       ← the true volatility regime
5. Divergence checks                ← where momentum is failing behind price
6. Only then → expression FAMILY    ← and a size multiplier
```

**Step 2 is the part most systems skip.** A market you cannot read is not one you
take a smaller position in; it is one where the process stops and nothing
downstream is even computed. `test_the_gate_stops_everything_downstream_not_just_sizing`
holds that line: a CTA read handed into an early-exit run must not leak into the
answer.

---

## What it outputs

An **expression family** (one of five, from §3) and a **size multiplier**. Not a
ticker, not a position, not an order. Per CLAUDE.md, AQE exports data and
computed levels; the trade call is the PM's. The multiplier applies to the PM's
own risk budget and is capped at `SIZE_MULT_CAP = 1.15`.

| Family | Fires when |
|---|---|
| `HIDDEN_STRESS_DOWNSIDE` | dispersion spread elevated **and rising** |
| `DIVERGENCE_PAIR_SHORT` | bearish divergence + narrowing + crowded CTA |
| `MEAN_REVERSION_PREMIUM` | positive gamma + very low VIX + broadening |
| `BROADENING_CARRY` | broadening + mid-range + positive gamma + calm + clean trend |
| `NARROWING_CONCENTRATED` | narrowing + CTA risk-on + negative gamma |

Hidden stress is **first on purpose**: §2.4's point is that a rising dispersion
spread shows up *before* the index admits anything, so it must not be outranked
by a regime read that still looks healthy.

When no family matches cleanly the layer reports the **best partial match with
the conditions it failed**, because "closest family, 3 of 4 conditions" is useful
and "NONE" is not.

---

## The modules

| File | §  | What it does |
|---|---|---|
| `spec.py` | all | Every constant, each marked **transcribed** (from kernel §5) or **DERIVED** (with the reasoning). A reader must be able to tell which is which. |
| `heartbeat.py` | 2.2 | RSP/SPY regime — faithful transcription of `heartbeat_regime`. |
| `cta.py` | 2.3 | Replicated trend model + **flip levels**. |
| `cot.py` | 2.3/2.5 | CFTC Commitment of Traders, direct from cftc.gov. |
| `vol.py` | 2.4 | VIX, the dispersion spread, DSPX + implied-correlation corroboration. |
| `cboe.py` | 2.4 | The volatility complex direct from cboe.com — VIX, VIXEQ, DSPX, COR1M, VIX3M, VIX9D. |
| `gamma.py` | 2.3 | Dealer GEX, gamma flip, call/put walls. |
| `divergence.py` | 2.5 | The three accepted types, each read across every series we hold. |
| `kernel.py` | 2.1/3/5 | The hierarchy, sequenced as pure functions. |
| `data.py` | — | All network. The engines stay pure. |
| `explain.py` | — | The regime in **plain English**, generated from the finished read every run. |
| `daily.py` | 4 | One call; `crown_status` degrades loudly. |
| `export.py` | — | The **reading copy** for Drive: plain English first, series dropped, limits attached. |
| `../scenarios.py` | — | **The first merge point**: Macro Weather × Crown → ranked scenario reads. Deliberately outside `crown/`. |

No LangGraph dependency. §6 states the intelligence lives in the pure functions
and orchestration "only sequences" them — so it is a plain sequence, and every
step is inspectable in a debugger.

---

## Data sources, and what each one cost

| Input | Source | Status |
|---|---|---|
| RSP / SPY | FMP daily bars (SPY from the local panel when present) | ✅ |
| 18 futures markets | FMP continuous front-month (`ESUSD`, `ZNUSD`, `CLUSD`, `GCUSD`, `SIUSD`, `HGUSD`, `DXUSD`…) | ✅ |
| VIX | **cboe.com direct** (FMP `^VIX` as fallback) | ✅ |
| VIXEQ / DSPX / COR1M / VIX3M / VIX9D | **cboe.com direct** | ✅ free, no key — FMP gates these above Starter |
| CFTC COT | **cftc.gov direct** — weekly flat file + annual zips | ✅ 2,176 rows / 16 contracts / 136 weeks |
| Option chains (gamma) | Alpaca snapshots, **both rights, with open interest** | ⚠️ needs a feed that returns OI |

**COT and the whole volatility complex are the same lesson.** FMP gates COT
behind Premium and gates VIXEQ / VIX3M / VIX9D / COR1M above Starter. In both
cases the *publisher* — the CFTC, and Cboe — puts the data online free. Paying a
reseller for a public file would have been the wrong call, so the layer takes
both from the source. History is
backfilled from the annual archives (closed years fetched once) and extended
weekly, cached to `data/crown_cot.parquet` and carried by Daily Persist —
without that the percentile window resets to one row on every container recycle,
and every market reads "no history" instead of "crowded long".

---

## Three honesty rules built into the code

**1. A realised proxy never passes as an implied reading.**
The implied spread is now the primary reading (Cboe VIXEQ, 3,052 sessions back
to 2014-06-19). The realised proxy survives only as a last resort for when Cboe
itself is unreachable:

```
mean(30d realised vol across the universe) − 30d realised vol of SPY
```

It asks the same question — is single-stock vol rising while the index stays
calm? — but it is **realised, not implied**: it lags and carries none of the
forward-looking volatility risk premium that makes the implied version
tradeable. `basis` says which produced the reading, the realised one always
carries a `caveat`, and the page renders a warning banner.

Two independent instruments cross-check the spread, because agreeing is
evidence and disagreeing is a warning. **DSPX** is Cboe's purpose-built
dispersion index — the same question, constructed by the people who define the
inputs. **COR1M** is implied correlation, which is the mechanical other side:
index variance is constituent variance times correlation, so a collapsing
correlation *is* a widening spread and it must move opposite (measured −0.61
against the spread over the common history). When they stop agreeing, the layer
says so in `degraded` rather than quietly reporting the spread anyway.

**2. A gamma map without open interest is UNAVAILABLE, not flat.**
Exchange feeds publish OI; they never publish who is long and who is short. The
standard convention — customers long calls and puts, dealers long call gamma and
short put gamma — is an **assumption**, and it ships in the `assumption` field of
every reading. When OI is missing the profile is refused outright, because a
zeroed map reads as "dealers are neutral", which is a completely different claim
from "we could not get the data".

**3. The CTA note cannot be bought; the method can be rebuilt.**
Moskowitz–Ooi–Pedersen time-series momentum at 2/6/12 months plus Faber's
10-month average, each vol-normalised so a 5% move in ZN and a 5% move in NG are
not treated as the same signal. **Our positioning estimate will not match
Goldman's** — the AUM weighting is a guess and GS surveys real books. The **flip
levels will be close**, because a flip level is arithmetic, not anyone's book.
That is the column worth reading: *"CTAs turn seller of ES below X"* — this
computes X, by bisection, at 1 / 5 / 20 sessions ahead.

---

## Choices that differ from a naive reading

- **Dispersion is reported as level AND direction, and the tactical flag needs
  both.** §2.4 gives two framings — the narrative cites an *elevated* spread ahead
  of 5–7% drawdowns, the practical rule says a *rising* spread is hidden stress.
  They are not the same state, and on 2026-08-07 they disagreed outright: the
  spread sat at the **98th percentile of its entire history** while having
  **fallen 9.2 points in twenty sessions**. So `band` carries the level, `direction`
  carries the move, `state` combines them (`ELEVATED_EASING` vs `ELEVATED_RISING`),
  and `hidden_stress` requires both — buying downside into an unwinding spread is
  buying the end of the move. The elevated *level* stays visible either way.
- **`DIV_LOOKBACK = 120`, not 60.** A quarter frequently holds only *one*
  confirmed swing high at index level, and a divergence needs two. Too short a
  window does not report "no divergence" — it reports "no second pivot", and the
  two read identically downstream.
- **The divergence comparison pivot is the prior *extreme*, not the previous
  one.** §2.5 says "price makes a **new high**", which is a claim against the
  prior significant high. Comparing blindly to the last pivot lets a minor bump
  inside the second leg stand in for the real one, silently turning a genuine
  divergence into `NONE`.
- **A gamma wall must beat its own even share.** With 30 strikes an evenly-spread
  ladder gives each 3.3%, which clears any fixed floor and would crown an
  arbitrary strike. The test is `GAMMA_WALL_DOMINANCE = 2.5×` the even share, and
  the fixed floor is only the backstop.
- **`CTA_SIGNAL_SCALE_SIGMA = 2.0`.** At 1 sigma nearly every drifting market
  reads "extreme" and Crown's 0.75 threshold fires constantly. At 2 sigma, 0.75
  means about 1.5 sigma over the lookback — a real trend.
- **Tactical families cap size rather than compounding it.** Multiplying two
  independent size opinions understates by design rather than by evidence.
- **COT joins on contract code, not name.** Names get re-spelled between years
  ("CRUDE OIL, LIGHT SWEET" vs "WTI …"); codes do not, and a name join silently
  drops a market for a whole year.
- **Crude maps to ICE Europe WTI (`067411`).** It carries ~875k open interest in
  the futures-only report; the NYMEX flagship is not published there at all.
- **Russell maps to the MICRO contract (`239747`).** It is the only Russell 2000
  contract in that report.

---

## Running it

- **Page** — 🫀 Crown Macro → *Run Crown layer*. Gamma is an opt-in checkbox
  (slower, needs an OI-bearing options feed).
- **Daily** — Step 6f of `daily_orchestrator`, gamma off, wrapped like QS so a
  Crown failure can never take down the export that Longlist / Elder / held ride
  on.
- **Code** — `from src.macro.crown.daily import run_crown; run_crown()`

`crown_status`: `OK` · `DEGRADED` (ran, something is missing or on a proxy) ·
`EARLY_EXIT` (the gate stopped it — a **result**, not a failure) · `UNAVAILABLE`
(the Heartbeat itself could not be built). `degraded` lists what is missing in
plain words.

---

## Divergence reads everything, not one series

§2.5 accepts exactly three types, so the taxonomy stays at three — but each type
now uses the whole data set rather than SPY plus two proxies:

| Type | Reads |
|---|---|
| 1 · Classic RSI | a **matrix**: SPY, QQQ, RSP and all 18 CTA markets |
| 2 · Cross-asset / intermarket | copper, oil, breadth, **the dollar (inverted)**, **VIX**, **the dispersion spread** |
| 3 · Positioning vs price | a sweep of **all 16 COT contracts**, not just ES |

Type 1 ships in **two forms**, because they answer different questions:

- **Pivot form** (`rsi_divergence`) — the textbook one. A higher confirmed swing
  high on a lower RSI high, over a 120-session lookback. Strict, and rare.
- **Slope readout** (`rsi_trend_readout`) — the everyday one. Price direction
  against RSI direction at **5 and 20 sessions**, with both series returned so it
  can be charted. This is "SPY grinding up while RSI heads down", computed
  exactly that way.

**Why the slope form is a readout first and a warning second — measured, not
asserted.** RSI is bounded and mean-reverting: in a sustained uptrend it
saturates and then drifts back toward its plateau, so "price up 20d, RSI down
20d" is the *normal* state of a healthy trend. On trending random walks carrying
no divergence structure at all:

| formulation | fires on a plain uptrend |
|---|---|
| 5-day window alone | 2.5% of days |
| **20-day window alone** | **14.1%** — unusable as a trigger |
| **both windows agreeing** | **0.6%** — the warning threshold |

So both horizons are always shown (that is the thing worth looking at), a single
window reads `MIXED` and is explicitly never acted on, and only agreement
between them counts. A 20-day window also cannot hold two comparable swing
highs, which is why the strict form needs 120 sessions — the two are not
substitutes.

Breadth gets the same two-form treatment: the **regime label** (which only flips
once the 20-day slope turns) and **`heartbeat_ma_divergence`**, which catches the
deterioration earlier — the index making ground while RSP/SPY rolls toward its
own 20-day average. That one fires on the **ratio's own move**, not on the change
in its distance to the average: the gap is self-damping, because the average
chases the ratio and stabilises even while breadth deteriorates outright. The gap
level is reported as context. Note the ratio is a price ratio, not a bounded
oscillator, so a slope comparison is valid there in a way it is not on RSI.

The four type-2 additions are all non-confirmations — an intermarket series
refusing to agree with price — so none of them is a fourth type smuggled in:

- **VIX** — a grind to new highs normally bleeds implied vol. When the index
  makes a high and protection gets *more* expensive at the same time, someone is
  paying up into strength.
- **Breadth** — the index at a new high while the RSP/SPY heartbeat is
  *narrowing*. The purest form of the idea, and it reuses the Heartbeat rather
  than recomputing breadth, so the two can never disagree about the same ratio.
- **Dispersion** — a new high while single-stock vol pulls away from index vol.
- **The dollar is inverted.** A bid dollar is a drag on risk, so DX at a new high
  is the *warning*. Treating it like copper would read a dollar squeeze as a
  healthy tape.

`coverage` reports exactly what was evaluated, because a check that was
**skipped** must never look like a check that **passed**. `weight` counts how
many independent warnings are lit — §2.5's point is that divergence earns its
weight when several agree, and the count is how a reader tells one straw from a
pile of them.

---

## Macro scenarios — the first merge point

`src/macro/scenarios.py`, deliberately **outside** `crown/`.

Macro Weather has been capturing TLT / UUP / HYG / IWM / GLD / CPER / USO daily
for a long time and using it for one thing: a per-sector headwind score. The raw
cross-asset state those seven instruments describe was never assembled into a
reading. This does that, and folds in what only Crown can see — dispersion,
implied correlation, CTA sector bias, the breadth regime.

Seven scenarios, each a set of weighted conditions: `REFLATION`, `GROWTH_SCARE`,
`INFLATION_SHOCK`, `DISINFLATION_GOLDILOCKS`, `LIQUIDITY_STRESS`,
`DISPERSION_REGIME`, `DOLLAR_SQUEEZE`.

**Why it lives outside `crown/`.** The directive is that Crown is built
standalone and merged later so the overlap stays measurable. Importing SRM into a
Crown module would quietly pre-empt that decision — and a test forbids it. So
Crown stays pure and this module reads *both finished outputs*. That is what a
merge point is: a named place where two independent readings meet, not a
dependency buried inside one of them.

**A score is the share of conditions met. It is NOT a probability.** Nothing was
fitted, nothing was backtested, no base rate was measured. Saying "seven of nine
things this story needs are true right now" is a genuinely weaker claim than
"70% likely", and the value is in the evidence and **falsifier** lists — what is
*not* true is what would have to change for the story to become the read.

Three disciplines it enforces:

- **A thin scenario cannot lead.** A score from two of seven conditions is not
  comparable to one from seven of seven; ranking them together lets a scenario
  lead on the strength of the data we happen to be *missing*. Below 60% coverage
  a scenario is reported with its evidence but is ineligible.
- **Two stories fitting one tape is reported as contested**, not as a call.
- **An unavailable input is skipped, never counted as evidence against.**

Runs at step 6g of the daily, writes `output/macro_scenarios.json`.

---

## The plain-English read

Every other module produces numbers. `explain.py` produces the sentence a person
actually wants: **what kind of market is this, why, what does the process say to
do, and what would change the answer.** It is a pure function over the finished
Crown dict, regenerated on every run and shipped in the artifact as
`plain_english`, so the committee reads the same words the page shows and
neither can go stale.

Two rules the writing follows, both enforced by tests:

1. **No jargon without its meaning.** "Dispersion at the 98th percentile" is not
   English. "Single stocks are far more volatile than the index — wider than 98%
   of the last two years" is. A test asserts the raw vocabulary (`percentile`,
   `dispersion`, `gex`, `vixeq`, `flip_risk`, `heartbeat`) never reaches the
   output.
2. **No claim without its number, and no number without its claim.** "Breadth is
   weak" cannot be checked; "0.328" cannot be understood.

The output is `headline` / `because` / `so_what` / `watch_for` / `caveats`.
`watch_for` is the part with teeth — it names the actual CTA flip levels ("if the
S&P trades below 7,240, trend funds start selling"), the condition that would
turn an easing spread back into a building one, and the leading scenario's own
falsifiers.

A worked example, from live volatility and COT data:

> **A market with no clear breadth lead, calm on the surface but with single
> stocks moving very differently underneath.** Best fit: a stock-picker's market
> — the index tells you very little about the average name.
>
> - Single stocks are far more volatile than the index — wider than 88% of the
>   last two years. But the gap has been shrinking for a month (down 9.2 points),
>   so this stress is draining away rather than building. Buying downside into
>   that is buying the end of the move. The index itself is calm: VIX at 14.9,
>   lower than 91% of the last two years.
> - Big speculators are unusually long the dollar, gold, copper and 4 others;
>   unusually short natural gas, the Nasdaq, silver and 2 others.

---

## Freshness — "as of when?", per source

The legs come from four publishers on four clocks (FMP, Cboe, the CFTC, the
local panel), so a single "generated at" timestamp hides the one that quietly
stopped updating. Every source now carries `as_of` and `days_stale`, and the
run reports its **oldest leg** — because the read is only ever as current as
that.

This exists because of a real defect, found 2026-08-10. `heartbeat_bars`
preferred the local panel over a live fetch — correct, it is free and already
built — but guarded it with a **length** check (`len < 252`). A panel that
stopped updating in June still has thousands of rows, so it sailed past the
guard, displaced the live fetch, and the Heartbeat reported **June** while every
other source reported August. Nothing was empty, so nothing complained.

Stale-but-present is the sneakier half of *"a failed data fetch must be LOUD"*
(CLAUDE.md). The guard is now recency, not row count, and a stale local file
loses to the network rather than beating it on size.

### The CTA universe, corrected

Verified against FMP's own `commodities-list` on 2026-08-10. Three symbols were
simply wrong on the first pass, and one whole complex is plan-gated:

- Corn, soybeans and wheat are quoted in **cents** and carry a `USX` suffix.
  There is no `ZWUSD` at all — FMP's wheat is `KEUSX`. So `ZCUSD/ZSUSD/ZWUSD`
  became `ZCUSX/ZSUSX/KEUSX`.
- **`ZNUSD` returns ACCESS DENIED on our Starter plan**, and the rest of the
  treasury complex is at risk with it.

Every market therefore carries a duration- or exposure-matched **ETF fallback**
(ZN→IEF, ZB→TLT, ZF→IEI, ZT→SHY, CL→USO, DX→UUP …). A market that cannot source
its future is **proxied and labelled**, never dropped — because `flip_risk` is
extremes ÷ n_markets, and losing the whole rates complex silently shrinks the
denominator and re-rates every reading. `freshness.cta_markets[k].via` says
`futures` or `etf_fallback` for every one, so a proxy is never mistaken for the
contract: the trend direction holds, the absolute levels are not the future's.

---

## Not yet built

- **Gamma in the daily run** — currently on-demand only, pending a confirmed
  open-interest feed (Alpaca snapshots, or IBKR `get_option_data` / Tiger
  `get_option_briefs`). It is also the largest hole in the scenario layer: no
  scenario currently reads dealer positioning.
- **Scenario base rates.** Today a score is a share of conditions. Measuring what
  actually followed each scenario historically would turn it into something
  closer to QS's calibrated probability — a different and stronger claim, and it
  needs a labelled history first.
- **The merge with SRM / Macro Weather / Thematic RRG** — deliberately deferred.
  Both layers now produce a sector/regime view; measuring where they agree and
  where they contradict is the next decision, and it needs both running side by
  side first.
