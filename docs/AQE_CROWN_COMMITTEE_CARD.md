# Crown Macro — Committee Card

**One page. What the layer says, how to read it, what it will not tell you.**
Full reference: `AQE_CROWN_READING_GUIDE.md`.

---

## Read it in this order. Stop when you have enough.

| | | |
|---|---|---|
| **1** | **The headline** | What kind of market this is, in one sentence. |
| **2** | **Why** | Four to six reasons. Every one carries its number. |
| **3** | **So what** | The allowed *family* and the size multiplier. |
| **4** | **What would change it** | The actual levels and conditions to watch. |

Everything below that on the page is the evidence behind those four blocks.

---

## Check these two before you trust any of it

**`crown_status`**

| | |
|---|---|
| `OK` | Every leg sourced. |
| `DEGRADED` | It ran, but something is missing or on a proxy. **Read `degraded`.** |
| `EARLY_EXIT` | The process stopped on purpose. **A result, not a failure.** |
| `UNAVAILABLE` | Nothing was computed. |

**`freshness.oldest_leg`** — the read is only as current as its oldest input. A run
stamped today built on three-week-old data is a three-week-old read.

---

## The hierarchy, and the one rule that matters

```
Heartbeat → if unreadable, STOP → Positioning → Volatility → Divergence → Family + size
```

**A market you cannot read is not one you take a smaller position in.** Below 0.40
confidence the process stops and nothing downstream is computed. On `EARLY_EXIT`
the sections below are empty *because they never ran*, not because they came back
quiet.

---

## How to read each number

| Read | Not as |
|---|---|
| **Heartbeat** — the chart, then the label | "Range position: TOP" means nothing without the range |
| **`flip_risk`** — fragility | not conviction. 0.67 = two-thirds of the complex is stretched → *cut* size |
| **CTA `flips`** — the tradeable output | the positioning estimate is the weak half |
| **COT `percentile`** — always | never the raw contract count |
| **Gamma** — the cumulative line | the flip *is* its zero-crossing; the bars won't show it |
| **Volatility** — `band` **and** `direction` | either alone is half a statement |
| **Divergence `weight`** — how many *independent* warnings | one is a straw, four is a pile |

---

## The volatility trap

`ELEVATED_EASING` is **not** a buy-downside signal.

The gap can sit at the 98th percentile of its whole history *while falling*. That
is stress **leaving** the market. Buying protection into an unwinding spread buys
the end of the move. Only `ELEVATED_RISING` routes to the tactical downside
family.

And a high VIX is **not** a sell. It means protection is already expensive.

---

## The five families

| Family | Fires when | In plain words |
|---|---|---|
| `HIDDEN_STRESS_DOWNSIDE` | vol gap elevated **and rising** | Buy cheap index downside. Small size. |
| `DIVERGENCE_PAIR_SHORT` | bearish divergence + narrowing + crowded CTA | Short the stretched leader vs the average stock. |
| `MEAN_REVERSION_PREMIUM` | positive gamma + very low VIX + broadening | Fade extremes. Sell premium. |
| `BROADENING_CARRY` | broadening + mid-range + positive gamma + calm | Own the average stock. |
| `NARROWING_CONCENTRATED` | narrowing + CTA risk-on + negative gamma | Stay with the leaders. Defined risk. |

`match: partial` → read `conditions_unmet`. "Closest family, 3 of 4 conditions" is
useful; "NONE" is not.

---

## What it will not tell you

- **It does not size.** It gives a *multiplier on your own risk budget*.
- **It does not name a ticker.** It gives a *family*. The setup is yours.
- **It places nothing.**
- **It emits no probabilities.** Scenario scores are a **share of conditions met** —
  nothing fitted, nothing backtested, no base rate. QS ships a calibrated
  probability; this does not. Never read them as the same kind of number.

---

## Live limits — read as caveats on the whole page

1. **Gamma is off in the daily run.** Nothing accounts for dealer hedging unless
   you run it on demand with an options feed that returns open interest.
2. **14 of 18 CTA markets run on ETF proxies.** FMP's plan gates the futures
   symbols; only ES, BZ, GC and SI come through as contracts. **Trend direction
   holds. Flip levels are in ETF units and are not quotable as contract prices.**
   Check `freshness.cta_markets[X].via`.
3. **COT is 3–10 days stale by construction.** It cannot time anything. Use it for
   one question: *is the crowd already positioned the way price is moving?*
4. **Scenario scores have no base rates.**

---

## The daily rhythm

1. Read the headline. If the market is unreadable, stop.
2. Read the reasons. Check the one that surprises you.
3. Read the family and the multiplier.
4. Read what would change it.
5. Open the sections below only for evidence.
6. **Apply the multiplier to your budget and pick the setup yourself.**

Step 6 is yours. The regime dictates the allowed *family*; the individual setup
comes after and is not this layer's job.
