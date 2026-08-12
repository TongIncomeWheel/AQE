# S3H — THE HELD BOOK · the gap, and how it closes

**Found by the PM, 2026-08-12,** while asking what the legacy `committee_read` field was. It is
the committee's verdict on a position you already own — RUN / TAKE-PARTIAL / TIGHTEN / EXIT
(decision D-34). PMA v0.4 has no equivalent. That is a real hole, and the most important one in
the design, for a reason the existing system already states plainly:

> **D-33: exits before entries.** The held book is deliberated FIRST, because what you free up
> determines what you can put on. A morning plan that lists new ideas before saying what to do
> with what you already own has the funnel backwards.

---

## Source: the AQE export (PM ruling, 2026-08-12)

**`held_positions` in the daily AQE export is the source.** An earlier draft of this card
insisted on the Aegis PTJ file and said the held track should stand down without it. Overruled,
and correctly: the PTJ has not been maintained for weeks while effort went into AQE, and AQE
scores the held book as part of its own daily process. Waiting for a file nobody is producing
would have blocked the whole track indefinitely.

Verified against the real export (2026-07-28): **12 positions, ~80 fields each.** The
analytical half is fully served — the committee can absolutely judge whether a thesis is intact.

**Served per held position** (all confirmed present, not assumed):
`sc_momentum` · `ptrs` · `pipe_rank` · `flow` · `energy` · `structure` · `mp` + `mp_state` ·
`elder` · `sc_m_gates`/`sc_p_gates` with per-gate detail · full `subcomponents` breakdown ·
`ma_20/50/100/200` · `sma_distance_pct` · `rs_spy_20d` · `structure_shift` · `choch_state` ·
`div_state` + `div_bull_count`/`div_bear_count` · `hl_state` · `pin_bar_state` · `inside_bar` ·
fib levels · `knn_prob` + `knn_tp1/2/3` + `knn_significant` · `runner_setup` / `premove_setup`
with conviction labels · `atr_14d` · `vol_30d_ann` · `beta_30d`/`beta_252d` · `rvol` ·
`bracket` · `gics_sector` + `gics_gate` · **`entry`** · **`qty`** · `held: true`.

Plus a book-level `held_book` block: total exposure, beta-adjusted exposure, NAV-weighted beta,
loss-per-1%-gap, and 3/5/7/10% gap scenarios.

---

## What is NOT served, and why it matters

In the verified export these came back `null`: `live_px` · `held_sl` · `held_tp1`/`held_tp2` ·
`trade_date` · `unreal_usd` · `exposure` · `ptj_srm_grade` · `ptj_sector: "TBD"`.

Every one of them is a **PTJ-sourced overlay field**. They are null for exactly the reason the
PM gave — the PTJ is stale. AQE's own scoring is complete; the layer that was supposed to stamp
position economics on top of it is empty. That is a clean split, and it maps directly onto what
the committee can and cannot conclude:

| The committee is asked | Needs | Status |
|---|---|---|
| **Is the thesis still intact?** | scores, gates, structure, momentum, divergence | ✅ fully served |
| **Where am I in this trade?** | live price, unrealised, R-multiple, distance to stop | ❌ not served today |

**Consequence, stated rather than fudged:** `RUN`, `TIGHTEN` and `EXIT` are thesis judgements
and are **fully supportable today**. `TAKE-PARTIAL` is not — "bank some" is meaningless without
knowing you are up and by how much. So a seat recommending TAKE-PARTIAL must declare
`unrealised: NOT_SERVED`, and the consensus rule caps conviction at 3 on any TAKE-PARTIAL until
the gap closes. Same discipline as everywhere else in PMA: the committee says what it cannot
see rather than guessing.

### The cheap unlock (recommended, small)

`entry` and `qty` **are** served. One live price per held name — via the IBKR/FMP path the wider
system already uses — yields unrealised $ and %, and exposure, for all 12 positions. The stop
does not need to come from the export at all: `trailing_stop.py` already computes the mechanical
floor, and it is the authority on that number anyway.

So the full economic picture is roughly **one price lookup plus a tool that already exists** —
not a PTJ revival. Worth doing before the held track ships, and it is the single highest-value
item in this card.

---

## The principle that keeps this honest

**PMA supplies the JUDGEMENT. It never touches the MATH.**

`trailing_stop.py` owns the stop floor — it ratchets, never lowers, and protects the position
regardless of what anybody thinks. PMA does not move a stop, size a trim, or place anything. It
produces the committee's *read*; the read plus the floor is what the PM decides from. D-34 says
exactly this: the trail is the mechanical floor, take-profit fractions are a *suggested default*,
and **the PM decides partial-vs-run from the committee read, never auto-scaled.**

---

## The population

Every open Aegis position — all 12, every morning. Not a screen, not a selection. A position the
committee does not discuss is a position nobody is watching.

---

## It flows through the SAME machinery

No new pipeline, no new agents, no second deliberation engine.

| Stage | New ideas | Held book |
|---|---|---|
| **S4 Round 1** | nominate up to 10 from the universe | **a read on EVERY position** — the book is not optional |
| **S5** | rogers challenges the tally · weather | same weather; rogers may challenge a *hold* as easily as a buy |
| **S6 Round 2** | stance on every narrowed name | stance on every held position |
| **S6 Round 3** | rebuttal on open O7 | same |
| **S6b consensus** | ADVANCE / HOLD-FOR-CONDITIONS / PASS | **RUN / TAKE-PARTIAL / TIGHTEN / EXIT** |
| **S7** | ideas section | **held actions section — FIRST, per D-33** |

Only the **stance vocabulary** differs. Obligations, coverage matrix, rebuttal trigger,
completeness certificate, conviction caps, the no-generated-prose rule — all identical, all reused.

### Stance vocabulary

| Stance | Means | Supportable today? |
|---|---|---|
| `RUN` | thesis intact, momentum intact — let it work | ✅ |
| `TIGHTEN` | thesis weakening — reduce the room, not the position | ✅ |
| `EXIT` | thesis broken | ✅ |
| `TAKE-PARTIAL` | bank some, keep the rest working | ⚠️ needs unrealised — conviction capped at 3 until served |

Same mandatory fields as a new-idea stance: reasons carrying `{field, value}`, a falsifier
(`what_would_make_me_wrong`), an `opposing_argument` on any EXIT and on any RUN at conviction ≥4
(a seat holding hard through weakness must show it has looked), and `abstain_reason` where a
position sits outside a seat's canon.

### The two standing briefs, pointed at the book

- **rogers — is the CROWD wrong?** A position every seat wants to RUN is evidence about the
  seats. Consensus to hold is as much a warning as consensus to buy.
- **steenbarger — is the COMMITTEE wrong about its own certainty?** This is where its canon
  earns most. The named failure modes are the held-book ones: **attachment** to a name carried
  from a prior day, **ego** holding a loser to be proven right, **revenge** sizing after a loss —
  and the trap its own canon names outright: *holding a loser back to breakeven is economically
  identical to putting the same capital into a fresh setup, minus the attachment.* A TIGHTEN or
  EXIT the committee resists is exactly what its `conviction_audit` is for.

---

## What the CIO page gains (S7, revised order)

```
1  HEADLINE            day type + data quality
2  WHAT CHANGED
3  WEATHER PAIR        crown NOW · druckenmiller NEXT
4  CIO SYNTHESIS
5  HELD ACTIONS   ←    NEW. Per position: verdict, conviction, dissent, the bear case,
                       the mechanical stop floor alongside it, what would change the verdict
6  CAPITAL FREED  ←    NEW. What EXIT and TAKE-PARTIAL release — the number that makes
                       the next section affordable
7  ACTIONABLE IDEAS
8  WATCH TABLE
9  KEY LEVELS
10 WHAT WOULD CHANGE THIS PLAN
11 DECLARED GAPS       includes the unrealised/stop gap above, named
```

Section 6 is what makes the funnel real rather than rhetorical: you cannot judge whether a new
idea is affordable until you know what the book is giving back. **Note:** while `unrealised` is
NOT_SERVED, section 6 can only report exposure released (`entry × qty`), not profit banked —
and it says so. The price lookup above closes that too.

---

## Hard limits (unchanged)

PMA produces a READ. It does not move a stop, compute a trim size, place an order, or override
the mechanical floor. `trailing_stop.py` keeps the floor; the gatekeeper keeps the orders; the
PM keeps the decision. Constitution law 1 untouched.

## Build status

**DESIGN ONLY.** Not built, not wired, no runner support. One dependency worth clearing first:
the live-price lookup that turns `entry` + `qty` into unrealised — small, and it upgrades
TAKE-PARTIAL from capped to fully supportable.
