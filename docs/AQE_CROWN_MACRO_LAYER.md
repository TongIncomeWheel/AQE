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
| `HIDDEN_STRESS_DOWNSIDE` | dispersion spread elevated |
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
| `vol.py` | 2.4 | VIX + the dispersion spread, implied or realised. |
| `gamma.py` | 2.3 | Dealer GEX, gamma flip, call/put walls. |
| `divergence.py` | 2.5 | The three accepted divergence types. |
| `kernel.py` | 2.1/3/5 | The hierarchy, sequenced as pure functions. |
| `data.py` | — | All network. The engines stay pure. |
| `daily.py` | 4 | One call; `crown_status` degrades loudly. |

No LangGraph dependency. §6 states the intelligence lives in the pure functions
and orchestration "only sequences" them — so it is a plain sequence, and every
step is inspectable in a debugger.

---

## Data sources, and what each one cost

| Input | Source | Status |
|---|---|---|
| RSP / SPY | FMP daily bars (SPY from the local panel when present) | ✅ |
| 18 futures markets | FMP continuous front-month (`ESUSD`, `ZNUSD`, `CLUSD`, `GCUSD`, `SIUSD`, `HGUSD`, `DXUSD`…) | ✅ |
| `^VIX` | FMP index EOD | ✅ verified on Starter |
| `^VIXEQ`, `^VIX3M`, `^VIX9D` | FMP index EOD | ❌ **not on Starter** — attempted, reported, never swallowed |
| CFTC COT | **cftc.gov direct** — weekly flat file + annual zips | ✅ 2,176 rows / 16 contracts / 136 weeks |
| Option chains (gamma) | Alpaca snapshots, **both rights, with open interest** | ⚠️ needs a feed that returns OI |

**COT is the case worth noting.** FMP gates it behind Premium — but the CFTC is
the publisher and puts it online free. Paying a vendor for a public file would
have been the wrong call, so the layer takes it from the source. History is
backfilled from the annual archives (closed years fetched once) and extended
weekly, cached to `data/crown_cot.parquet` and carried by Daily Persist —
without that the percentile window resets to one row on every container recycle,
and every market reads "no history" instead of "crowded long".

---

## Three honesty rules built into the code

**1. A realised proxy never passes as an implied reading.**
`^VIXEQ` is unavailable on our plan, so when the implied VIXEQ − VIX spread
cannot be built the layer falls back to

```
mean(30d realised vol across the universe) − 30d realised vol of SPY
```

It asks the same question — is single-stock vol rising while the index stays
calm? — but it is **realised, not implied**: it lags and carries none of the
forward-looking volatility risk premium that makes the implied version
tradeable. `basis` says which produced the reading, the realised one always
carries a `caveat`, and the page renders a warning banner.

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

## Not yet built

- **True implied VIXEQ** — buildable from Alpaca chains as an equal-weighted
  average 30-day ATM IV across S&P constituents (~100–500 chain calls). Would
  replace the realised proxy and is the single biggest upgrade to §2.4.
- **Gamma in the daily run** — currently on-demand only, pending a confirmed
  open-interest feed (Alpaca snapshots, or IBKR `get_option_data` / Tiger
  `get_option_briefs`).
- **The merge with SRM / Macro Weather / Thematic RRG** — deliberately deferred.
  Both layers now produce a sector/regime view; measuring where they agree and
  where they contradict is the next decision, and it needs both running side by
  side first.
