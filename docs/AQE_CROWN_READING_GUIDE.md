# Reading the Crown Macro Layer

**A guide to interpreting what AQE built, anchored to Crown Institutional Process
Deployment Kernel v1.4.**

The kernel is the spec. This layer is the implementation. This document reads one
against the other, section by section, so you can tell what the kernel *asked
for*, what we actually *built*, which field carries it, **how to read it**, and —
where the two differ — **why**.

Everything here is generated fresh each run. Live figures quoted below are from
**7–10 August 2026**; they will have moved by the time you read this, and the
page will have moved with them.

---

## 1 · The problem this solves — kernel §1

> Most traders look at price first. Institutional desks look at **positioning,
> breadth and regime** first.

Price lags. The index and the average stock routinely tell different stories.
Mechanical flows (trend funds) and dealer hedging create pressure you can
anticipate. The volatility complex shows stress the index hides.

**The edge is knowing what kind of market you are in before you risk anything.**

So this layer never starts with a chart of a stock. It starts with breadth, and
it refuses to go further if breadth is unreadable.

---

## 2 · How to read it in sixty seconds

Open 🫀 **Crown Macro**. Read in this order and stop when you have what you need.

| # | What you read | Where |
|---|---|---|
| 1 | **The headline sentence** — what kind of market this is | Top of page, `plain_english.headline` |
| 2 | **Why** — four to six reasons, each with its number | `plain_english.because` |
| 3 | **So what** — the allowed family and the size multiplier | `plain_english.so_what` |
| 4 | **What would change it** — the levels and conditions to watch | `plain_english.watch_for` |
| 5 | **Status strip** — one chip per stage of the hierarchy | Below the headline |

If you read nothing else, read 1–4. Everything below that on the page is the
evidence behind those four blocks.

**Two fields to check before trusting any of it:**

- `crown_status` — `OK`, `DEGRADED` (ran, something missing or on a proxy),
  `EARLY_EXIT` (the process stopped on purpose — a *result*, not a failure), or
  `UNAVAILABLE` (nothing was computed).
- `freshness.oldest_leg` — the read is only ever as current as its oldest input.
  A run stamped today built on data from three weeks ago is a three-week-old
  read, whatever the timestamp says.

---

## 3 · The hierarchy — kernel §2.1 and §4

The order is the method, not a table of contents:

```
1. Heartbeat (RSP / SPY)             ← what kind of market is this?
2. If confidence < 0.40 → STOP.      ← the gate
3. Positioning: CTA + COT + Gamma    ← who is in, and how crowded?
4. Volatility structure              ← what is the real risk regime?
5. Divergence checks                 ← where is momentum failing behind price?
6. Only then → expression FAMILY     ← and a size multiplier
```

**Step 2 is the part most systems skip, and it is the one to understand.** A
market you cannot read is not a market you take a smaller position in. It is one
where the process *stops* and nothing downstream is even computed.

When you see `crown_status: EARLY_EXIT`, sections 2–4 of the page are empty
**because they were never run**, not because the readings came back quiet. That
distinction is enforced in code and tested.

---

## 4 · Heartbeat — kernel §2.2

> RSP / SPY ratio. Rising = broadening (average stock winning). Falling =
> narrowing (leaders carrying everything). Range position tells you when the
> current wave is tired.

### What we built

A faithful transcription of the kernel's `heartbeat_regime`, with the constants
lifted into `spec.py` so they can be audited line by line against the source.

### How to read it

| Field | Read it as |
|---|---|
| `regime` | `broadening` = the average stock is keeping up. `narrowing` = a few big names are carrying the index. `neutral` = no clear lead. |
| `range_position` | Where the ratio sits in its own **252-day** range. `top` / `mid` / `bottom`. |
| `confidence` | 0.75 = a regime **and** a range extreme (the most actionable state). 0.65 = a regime, no extreme. 0.45 = no slope. 0.30 = not enough history. |
| `passes_gate` | `false` stops the entire process. The gate is 0.40. |
| `slope_20d` | The 20-day slope of the ratio. Must exceed ±0.00015 to count as a regime at all. |

### The combination that matters most

`regime` and `range_position` **together**. Either alone is half a statement:

- **broadening + top** → "Broadening tired — prepare rotation into leaders."
- **narrowing + bottom** → "Narrowing exhausted — hunt breadth trades."

Both score 0.75 because *a tired wave is a more actionable statement than a live
one*. A trend that has just begun tells you to go with it; a trend at the end of
its range tells you to prepare for the turn, which is worth more.

### Read the chart, not the label

"Range position: TOP" is not interpretable without the range it refers to. The
page draws the ratio against its own 252-day high/low and its 20-day average.
**Look at the picture before you read the word.**

---

## 5 · Positioning — kernel §2.3

Three separate things the kernel groups together. They operate on different
clocks and you should read them differently.

### 5a · CTA — the medium-term directional force

> Systematic trend-followers with hundreds of billions. When their signals reach
> extremes, correlated multi-asset pressure becomes likely.

**The proprietary weekly note cannot be bought through any feed we have. The
method behind it is public, so we replicate it**: Moskowitz–Ooi–Pedersen
time-series momentum at 2/6/12 months plus Faber's 10-month average, each
vol-normalised so a 5% move in the 10-year note and a 5% move in natural gas are
not treated as the same signal.

| Field | Read it as |
|---|---|
| `cta.overall_bias` | `risk_on` / `risk_off` / `mixed` / `neutral` across all markets. |
| `cta.flip_risk` | The **share of markets sitting at a trend extreme**. High is *dangerous*, not bullish — crowded trends unwind fast. |
| `cta.size_adjustment` | 0.60 when crowded, 1.15 when the trend is clean and uncrowded, 1.00 otherwise. |
| `cta_markets[X].signal` | −1 (max short) to +1 (max long). ±0.75 counts as an extreme. |
| `cta_markets[X].flips` | **The column worth reading.** The price at which that market's signal crosses zero, at 1, 5 and 20 sessions ahead. |

**Read `flip_risk` as fragility, not conviction.** A reading of 0.67 means two
thirds of the complex is stretched. That is when the process *cuts* size even
though the bias looks clean and directional.

**The flip levels are the tradeable output.** "Trend funds turn seller of the S&P
below 7,240" is arithmetic — a deterministic function of the model, not of
anyone's book. That is why it will be close to what the banks publish even
though our positioning estimate will not be.

> **Honest limit.** Our estimate of *how much* CTAs hold will not match Goldman's.
> The AUM weighting is a guess and they survey real books. The **direction** and
> the **flip levels** are the parts that travel.

### 5b · COT — the slow context dial

> Price rising while COT large-spec positioning is already extreme.

Straight from **cftc.gov**, not a vendor. Published Friday 15:30 ET, reporting
*Tuesday's* book.

| Field | Read it as |
|---|---|
| `cot.markets[X].percentile` | Where net large-spec positioning sits in its own 3-year range. **This is the number that carries the meaning.** |
| `cot.markets[X].net_spec` | Raw contracts. Nearly meaningless on its own. |
| `cot.markets[X].percentile_reliable` | `false` = not enough weeks yet. Ignore the percentile. |
| `cot.crowded_long` / `crowded_short` | ≥85th or ≤15th percentile. |

**"+180,000 contracts" says nothing** without knowing whether that is the biggest
long in three years or an ordinary Tuesday. Always read the percentile.

**It can time nothing.** Three days stale at best, ten at worst. Use it for one
job only: *is the crowd already positioned the way price is moving?*

Live, 4 Aug 2026: crowded long the **dollar, gold, copper**; crowded short the
**10-year note, Nasdaq, natural gas, silver, long bond**.

### 5c · Gamma — the short-term structural force

> Positive gamma → dealers sell rallies / buy dips → dampens moves, pins price.
> Negative gamma → dealers buy rallies / sell dips → amplifies moves.

| Field | Read it as |
|---|---|
| `gamma.regime` | `POSITIVE` = moves get damped, price pins. `NEGATIVE` = moves get amplified. |
| `gamma.underlyings[X].gamma_flip` | The **regime boundary** — the price where the sign changes. |
| `call_wall` / `put_wall` | Magnets and acceleration zones. |
| `assumption` | Read this every time. See below. |

**The chart matters here more than anywhere.** The flip *is* the zero-crossing of
cumulative gamma, so the cumulative line is where you read it — the per-strike
bars alone will not show you.

> **This is a model, not a measurement.** Exchanges publish open interest. They
> never publish who is long and who is short. The standard convention — customers
> long options, dealers short — is an **assumption**, and when it is wrong the map
> points the wrong way. It ships in the `assumption` field of every reading.

**If gamma is unavailable it says `UNAVAILABLE`, never a flat map.** A profile of
zeros would read as "dealers are neutral", which is a completely different claim
from "we could not get the data."

---

## 6 · Volatility structure — kernel §2.4

> Crown does **not** treat VIX as a fear gauge or an automatic sell signal.

This is the most misread section, so start with what VIX is: the options market's
price of 30-day S&P volatility. **A spike means protection got expensive.** A high
level often means it is *already* expensive — which is the opposite of an entry.

### The tool Crown actually trades: VIXEQ − VIX

Single-stock volatility minus index volatility. When that gap widens, the index
can look calm while the average stock comes apart underneath.

We take VIXEQ, DSPX and implied correlation **directly from cboe.com** — free,
full history, no vendor. (FMP gates them above our plan.)

### Level and direction are different questions — read both

The kernel gives two framings and they disagree in practice:

- the narrative — *"an **elevated** spread has predicted 5–7% drawdowns"*
- the practical rule — *"a **rising** spread → hidden stress"*

On **7 Aug 2026** they disagreed outright: the spread sat at the **98th percentile
of its entire history** while having **fallen 9.2 points in twenty sessions**.

| Field | Read it as |
|---|---|
| `dispersion.band` | The **level** — `ELEVATED` / `NORMAL` / `CALM`. |
| `dispersion.direction` | The **move** — `RISING` / `FALLING` / `FLAT` over 20 sessions. |
| `dispersion.state` | The two combined: **`ELEVATED_RISING`** vs **`ELEVATED_EASING`**. |
| `rules.hidden_stress` | `true` only when elevated **and** rising. |
| `rules.dispersion_elevated` | The level alone, kept visible so an easing tape is never invisible. |

**`ELEVATED_EASING` is not a buy-downside signal.** Stress is leaving the market.
Buying protection into an unwinding spread is buying the end of the move. Only
`ELEVATED_RISING` routes to the tactical downside family.

### Two cross-checks

`corroboration.dspx` (Cboe's purpose-built dispersion index) and
`corroboration.implied_correlation` must move **opposite** the spread — index
variance is constituent variance × correlation, so a collapsing correlation *is* a
widening spread. Measured −0.61 over the common history. **If `agrees` is `false`,
distrust the spread**, and the run says so in `degraded`.

Live: DSPX 36.74 (77th pctl), implied correlation **7.38 — the 1.7th percentile**,
near a record low. Single names are moving almost independently of each other.

### The three rules, as flags

- `hidden_stress` — elevated and rising → favour defined-risk downside, cut risk.
- `very_low_vix` — VIX < 15. With positive gamma this is a premium-selling tape.
- `already_priced` — VIX ≥ 25. Protection is expensive; **not** a fresh sell.

### Term structure

`term_structure.shape` — upward sloping (contango) is normal. Inverted means the
market is paying up for protection *right now*, which accompanies stress rather
than predicting it.

---

## 7 · Divergence — kernel §2.5

> Crown ranks pure RSI as C-tier because price can stay overbought for weeks. He
> uses RSI **primarily for divergence**.

**Three accepted types, and only three.** We widened what each one *reads*, not
the taxonomy.

### Type 1 — classic RSI divergence, in two forms

Both ship, because they answer different questions:

| Form | What it is | When it fires |
|---|---|---|
| **Pivot** (`rsi`) | A higher confirmed swing high on a lower RSI high, over 120 sessions. The textbook definition. | Rarely — it needs two confirmed pivots. |
| **Slope readout** (`rsi_slope`) | Price direction vs RSI direction at **5 and 20 sessions**. "Price climbing while momentum falls." | Often — it is the everyday read. |

> **Why the slope form is a readout first and a warning second.** RSI is bounded
> and mean-reverting. In a sustained uptrend it saturates and then drifts back
> toward its plateau, so "price up 20d, RSI down 20d" is the *normal* state of a
> healthy trend. Measured on trending random walks carrying **no divergence
> structure at all**:
>
> | | fires on a plain uptrend |
> |---|---|
> | 5-day window alone | 2.5% of days |
> | 20-day window alone | **14.1%** — unusable as a trigger |
> | **both windows agreeing** | **0.6%** |
>
> So both horizons always display, a single window reads `MIXED` **and is
> explicitly never acted on**, and only agreement between them warns.

**How to read it:** look at the 5d/20d table and the chart. If both rows say
`PRICE UP RSI DOWN`, that is a warning. If one does, that is information.

### Type 2 — cross-asset / intermarket non-confirmation

Equities at a new high while something else refuses to confirm. We read six:

| Check | Fires when |
|---|---|
| `cross_asset` | Index at a 60-day high while copper / oil / breadth are not. |
| `vix` | Index at a new high while **VIX is rising** — someone is paying up into strength. |
| `breadth` | Index at a new high while the heartbeat regime is `narrowing`. |
| `breadth_ma` | Index gaining while RSP/SPY **rolls over toward its own 20-day average** — catches it earlier than the regime label. |
| `dispersion` | Index at a new high while the volatility gap widens. |
| (the dollar) | **Inverted.** A *rising* dollar is the non-confirmation. |

**The dollar is inverted on purpose.** A bid dollar is a drag on risk, so DX at a
new high is the *warning*. Treating it like copper would read a dollar squeeze as
a healthy tape.

### Type 3 — positioning vs price

Price rising while large specs are already at an extreme. Swept across all 16 COT
contracts, not just the S&P — a crowded long in copper diverging from a falling
copper price is a different trade from the same thing in gold.

### Reading the whole block

| Field | Read it as |
|---|---|
| `weight` | How many **independent** warnings are lit. This is the number that matters. |
| `types_fired` | Which named checks fired. |
| `coverage` | What was actually evaluated. **A skipped check must never read as a passed one.** |

> **The rule that governs all three types:** divergence is a warning or
> confirmation filter, **never a standalone entry trigger**. One lit warning is a
> straw. Four lit warnings that line up with the breadth read is a pile.

---

## 8 · From regime to expression — kernel §3

The layer outputs an **allowed family** and a **multiplier**. Never a ticker,
never a position, never an order.

| Family | Fires when | In plain words |
|---|---|---|
| `HIDDEN_STRESS_DOWNSIDE` | Volatility gap elevated **and rising** | Buy cheap index downside. Small size — tactical. |
| `DIVERGENCE_PAIR_SHORT` | Bearish divergence + narrowing + crowded CTA | Short the stretched leader against the average stock. |
| `MEAN_REVERSION_PREMIUM` | Positive gamma + very low VIX + broadening | Fade extremes. Sell premium, don't chase breakouts. |
| `BROADENING_CARRY` | Broadening + mid-range + positive gamma + calm + clean trend | Own the average stock. Collect premium against it. |
| `NARROWING_CONCENTRATED` | Narrowing + CTA risk-on + negative gamma | Stay with the leaders. Keep risk defined. |

**Hidden stress is checked first on purpose.** §2.4's whole point is that the
spread shows up *before* the index admits anything, so it must not be outranked
by a regime read that still looks healthy.

### When nothing fits cleanly

`expression.match` reads `exact` or `partial`. On `partial`, read
`conditions_unmet` — "closest family, 3 of 4 conditions" is useful information;
"NONE" is not. `candidates` shows every family scored.

### The size multiplier

`decision.size_multiplier` is a **multiplier on your own risk budget**. AQE does
not size. `size_derivation` shows the arithmetic:

```
CTA dial 0.60 -> x0.70 (flip risk 0.67 > 0.45) -> capped at 0.65 (DIVERGENCE_PAIR_SHORT)
```

Tactical families **cap** rather than multiply, because compounding two
independent size opinions understates by design rather than by evidence.

---

## 9 · The daily rhythm — kernel §4

1. Read the **headline sentence**. If it says the market is not readable, stop.
2. Read the four to six **reasons**. Each carries its own number — check the one
   that surprises you.
3. Read **so what** — the family and the multiplier.
4. Read **what would change it** — the flip levels and the conditions.
5. Only now open the sections below for the evidence.
6. Apply the multiplier to *your* risk budget and pick the setup yourself.

**Step 6 is yours, not the layer's.** The regime dictates the allowed *family*.
The individual setup — the pullback, the breakout, the confirmation — comes after
and is not this layer's job.

---

## 10 · Where we deviated from the kernel, and why

Everything here is a deliberate, tested departure. Nothing was changed for
convenience.

| Kernel | What we did instead | Why |
|---|---|---|
| §5 ships a LangGraph | Plain sequenced pure functions | §6 says orchestration "only sequences the pure functions". No new dependency, every step inspectable. |
| §2.4 gives one dispersion framing | `band` **and** `direction`, combined into `state` | The two framings disagreed in live data. Buying downside into an unwinding spread buys the end of the move. |
| §2.5 implies pivot divergence | Pivot form **and** a 5d/20d slope readout | The pivot form is rare; the slope form is the everyday read. Measured false-positive rates decide which one warns. |
| §2.3 names CTA but gives no model | Moskowitz–Ooi–Pedersen + Faber, vol-normalised | The note is unbuyable; the method is public. Flip levels are arithmetic. |
| COT via a data vendor | **cftc.gov direct** | FMP gates it at Premium. The CFTC publishes it free. |
| VIX complex via a data vendor | **cboe.com direct** | Same lesson. Cboe *computes* these indices and publishes the history. |
| — | Every source carries `as_of` + `days_stale` | A stale panel once displaced a live fetch and the Heartbeat read June while everything else read August. |

---

## 11 · What this layer deliberately does **not** do

- **It does not size.** It emits a multiplier on your budget. Risk per trade stays
  your decision and your rule.
- **It does not name a ticker.** It emits a family.
- **It does not place anything.**
- **It emits no probabilities.** The scenario scores are a *share of conditions
  met* — nothing fitted, nothing backtested, no base rate measured. QS ships a
  calibrated probability; this does not, and the two must never be read as the
  same kind of number.
- **It does not read SRM, Macro Weather or the Thematic RRG**, and they do not
  read it. That merge is a later decision, kept separate so the overlap stays
  measurable. The one place they meet is the scenario layer, which reads both
  *finished outputs* and is named as the merge point.

---

## 12 · Known gaps — read these as limits on the whole page

1. **Gamma is off in the daily run.** It needs an options feed carrying open
   interest. Nothing on the page currently accounts for dealer hedging flows
   unless you tick the box and run it on demand.
2. **No scenario reads dealer positioning**, for the same reason.
3. **Treasury futures are plan-gated on FMP.** `ZNUSD` returns access denied, so
   the rates complex runs on duration-matched ETF proxies (IEF, TLT, IEI, SHY).
   Trend direction holds; the **flip levels are not quotable in contract terms**.
   Check `freshness.cta_markets[X].via` — `futures` or `etf_fallback`.
4. **Scenario scores have no base rates.** Measuring what actually followed each
   scenario historically would make them a stronger claim. That needs a labelled
   history first.
5. **COT is three to ten days stale by construction.** It cannot time anything.

---

## 13 · Field quick reference

| Kernel § | Module | Artifact block |
|---|---|---|
| §2.2 | `heartbeat.py` | `heartbeat` |
| §2.3 CTA | `cta.py` | `cta`, `cta_markets` |
| §2.3 COT | `cot.py` | `cot` |
| §2.3 Gamma | `gamma.py` | `gamma` |
| §2.4 | `vol.py`, `cboe.py` | `volatility` |
| §2.5 | `divergence.py` | `divergence` |
| §2.1 / §3 / §5 | `kernel.py` | `decision` |
| §4 | `daily.py` | `crown_status`, `degraded`, `freshness` |
| — | `explain.py` | `plain_english` |
| — | `../scenarios.py` | `output/macro_scenarios.json` |

**Artifacts:** `output/crown_macro.json` · `output/macro_scenarios.json`
**Page:** 🫀 Crown Macro · **Daily:** steps 6f and 6g
**Deep reference:** `docs/AQE_CROWN_MACRO_LAYER.md`
