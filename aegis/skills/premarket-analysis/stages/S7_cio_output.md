# S7 — CIO OUTPUT (deterministic render)

Everything is already decided upstream. S7 arranges it for one reader making one decision:
**what do I do with today?** Deterministic — no model runs here, so the plan can never say
something the committee did not conclude.

## Design premise

A CIO does not need a research report at 08:00. They need, in this order: *what kind of day is
this · what changed · what am I being asked to do · what is the best argument against it · what
would change my mind · what am I blind to.* Fixed order every day, so a two-minute read on a
phone builds the same mental model every time.

## The page — fixed order, always

**1 · HEADLINE** — one sentence: day type + data quality.
> "YELLOW, trending tape (hurst 0.603, VIX 18.7) — momentum favoured. Crown: stock-picker's
> market, BROADENING_CARRY at 1.0×, partial match. Crown ran DEGRADED — economic calendar absent."

**2 · WHAT CHANGED** — diff against yesterday's `premarket_plan.json`: regime flips, Crown
family changes, names entering/leaving the deliberation set, verdict reversals. *An empty list
says "today continues yesterday" — which is itself information.*

**3 · THE WEATHER PAIR** — Crown NOW (four blocks, compressed) then Druckenmiller NEXT (the
so-what). Explicitly labelled context, never gate. Their `differs_on[]` is printed — the
disagreement is the information.

**4 · CIO SYNTHESIS** — from S6 Pass D: coherence, concentration, regime consistency, the
strongest thing not advancing, the blind spots. **This sits above the ideas on purpose** — the
shape of the day frames how you read the list, not the other way round.

**5 · ACTIONABLE IDEAS** — every ADVANCE, one block each:
> **HBAN** — conviction 4 · 4 seats (lynch, oneil, minervini, wyckoff)
> Buy over 18.40, stop 17.82 · frame-fit: aligned
> **Why (data):** relative-volume 1.4× · risk 2.4% · reward:risk 2.8 · 5/6 lenses strong
> **Against it:** "Extended 12% over the 50-day with volume already spiked — the move may be
> late" (rogers, TIMING flag; judge: outweighed because base structure reset on 08-04)
> **Decisive:** the bull's volume-dry-up claim survived the bear's timing attack on data
> **Dissent:** thorp abstained — volatility rank top-quartile

Every line carries its numbers in plain labels. Bear case is mandatory and never softened.

**6 · WATCH TABLE** (collapsed) — HOLD-FOR-CONDITIONS + high-interest non-advanced names:
name · count · seats · **the specific observable that would promote it**.

**7 · KEY LEVELS TODAY** — nearest Crown `key_levels` + AQE regime levels, each with its "if it
breaks" sentence. Most are not prices — a breadth ratio, a vol gap, a correlation percentile
all have levels that change the regime when they break.

**8 · WHAT WOULD CHANGE THIS PLAN** — falsifiers, verbatim from Crown's
`what_would_change_it` plus every HOLD condition. The block with teeth: real levels, never sentiment.

**9 · DECLARED GAPS** — what today's run could not see: absent files, empty seats, NOT_SERVED
fields that mattered, staleness acks reprinted verbatim.

**Status line, always last:**
`DRAFT — PM approval required. Nothing is staged, nothing is armed.`

## Outputs

- `data/pma/<date>/premarket_plan.json` — machine record (`contracts/pma/premarket_plan.schema.json`)
- `data/pma/<date>/plan.md` — the phone render: plain words, numbers always shown, no acronym
  without its meaning, no RB keys

## Rules

- **No number without provenance.** Every value traces to a field in the day's data; S8
  re-checks this and flags any that does not resolve.
- **No idea without its bear case.** A one-sided line is a rendering bug.
- **Absence is printed, not omitted.** A missing seat, a degraded input, a NOT_SERVED field that
  mattered — all appear. The plan's honesty is the product.
