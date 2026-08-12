# S6 — DELIBERATION (judgment · the committee's actual work)

This is the stage the whole kernel exists to serve. Everything before it gathers evidence;
everything after it formats a decision. **S6 is where the committee argues.**

---

## The design problem, stated honestly

A single agent reading all the nominations and emitting verdicts is not deliberation — it is
one model's synthesis wearing a committee's clothes, and the charter forbids exactly that
(§0.2/§0.3: independent voices first, consensus drawn from their conclusions, never a house
view invented in the middle). Six failure modes have to be engineered out, not hoped away:

| # | Failure mode | Structural defence |
|---|---|---|
| 1 | **Consensus theatre** — seats converge on the loudest case | Bull and Bear are spawned blind to nomination *counts*; only the JUDGE sees the tally |
| 2 | **Dissent averaged away** — a 3-2 split becomes "moderate conviction" | Dissent is preserved as a named minority report and printed on the plan line |
| 3 | **Unfalsifiable bull case** — "momentum is strong" | Every claim carries `{field, value}`; unanchored claims are struck before the judge sees them |
| 4 | **Pro-forma bear case** — written by the agent that wants approval | BEAR is a separate spawn whose only instruction is to kill the idea |
| 5 | **Regime blindness** — a pretty breakout approved into a mean-revert tape | Mandatory frame-fit test against the Crown family + momentum caveat; a contradiction must be *argued*, not ignored |
| 6 | **Data blindness** — approved on fields the seat never actually had | Each seat's `declared.not_served[]` travels into the bear packet as ammunition |

---

## The spawn graph

```
                 deliberation_set (from S4 tally)
                              │
        ┌─────────────────────┴─────────────────────┐   per name, in parallel
        │                                           │
   ┌────▼────┐                                 ┌────▼────┐
   │  BULL   │  strongest case FOR             │  BEAR   │  strongest case AGAINST
   │ (agent) │  built ONLY from the            │ (agent) │  armed with rogers challenge,
   └────┬────┘  nominating seats' own cases    └────┬────┘  frame contradictions, NOT_SERVED gaps
        │                                           │
        └─────────────────┬─────────────────────────┘
                          │  both briefs complete
                    ┌─────▼─────┐
                    │   JUDGE   │  weighs A vs B; sees tally + frame + weather
                    │  (agent)  │  → verdict, conviction, decisive_argument
                    └─────┬─────┘
                          │  all names judged
                    ┌─────▼─────┐
                    │    CIO    │  portfolio-level: coherence, concentration,
                    │ SYNTHESIS │  regime fit, what the whole day says
                    └───────────┘
```

**Cost tiering** (a real constraint, designed for rather than discovered):

| Tier | Trigger | Passes | Agents |
|---|---|---|---|
| **FULL** | ≥3 nominations, OR any conviction ≥4, OR rogers filed a `flag` | BULL → BEAR → JUDGE | 3 |
| **LEAN** | everything else in the deliberation set | BEAR → JUDGE (bull case = the nominating seats' verbatim cases) | 2 |

A typical set of 8 names with 3 at FULL runs 3×3 + 5×2 + 1 = 20 agents. Watch-table names get
zero — they were never claimed to deserve argument.

---

## Pass A · BULL

**Sees:** the candidate's full data row · every nominating seat's case verbatim with its
`field_values` · the seat convictions · the bracket if served.
**Blind to:** how many seats nominated it (count is withheld — popularity is not an argument),
the rogers challenge, the bear brief.

**Job:** assemble the strongest *defensible* case. Not advocacy — construction. Every claim
must name its field and value. Claims that cannot be anchored are dropped by the BULL itself
and listed under `dropped_claims[]`, which is itself a signal to the judge.

**Returns** `bull.<TICKER>.json`: `thesis` (one paragraph) · `claims[]` each
`{statement, field, value, from_seat}` · `entry_frame` (bracket verbatim or `NOT_SERVED`) ·
`dropped_claims[]` · `strongest_single_claim`.

## Pass B · BEAR

**Sees:** the same data row · the rogers challenge entries for this name · the market frame
(regime, momentum caveat, Crown family + `conditions_not_met`) · the union of every nominating
seat's `declared.not_served[]` · the sector's SRM grade/quadrant/headwind.
**Blind to:** the bull brief (so it attacks the *idea*, not the wording), and to nomination counts.

**Job:** kill it. Default posture is refutation. Specifically hunt:
- the **crowding** read — is agreement here evidence about the seats rather than the asset?
- the **frame contradiction** — does this setup require a tape we are not in?
- the **data hole** — which decisive test could not be run because a field is NOT_SERVED?
- the **timing** — extended, late-stage base, volume already spiked?
- the **falsifier** — what observable would prove this wrong, and is it already visible?

**Returns** `bear.<TICKER>.json`: `kill_thesis` · `attacks[]` each
`{statement, field, value, severity: fatal|serious|note}` · `unanswerable_gaps[]` ·
`what_would_have_to_be_true` (the conditions under which the bear withdraws).

**A bear that finds nothing must say so explicitly** (`kill_thesis: "no fatal objection found"`),
with what it looked for. Silence is not a clean bill of health.

## Pass C · JUDGE

**Sees:** bull brief · bear brief · the tally (counts and seats — *now* it matters) · market
frame · weather (Crown NOW + Druckenmiller NEXT) · the name's data row.

**Returns** one entry in `committee_read.json`:

- `verdict` — `ADVANCE` · `HOLD-FOR-CONDITIONS` · `PASS`
- `conviction` 1–5, **earned under a rule, not felt**:
  - **5** — ≥3 independent seats, bear found no `fatal` or `serious` attack, frame-fit positive, every decisive claim anchored
  - **4** — ≥2 seats, no `fatal`, frame-fit neutral-or-positive
  - **3** — survives the bear with `serious` attacks answered on data
  - **≤2** — advances only as HOLD-FOR-CONDITIONS
  - *Conviction cannot exceed 3 if any decisive claim rests on a NOT_SERVED field.*
- `decisive_argument` — **mandatory**: the single bull or bear claim that determined the
  verdict, quoted. This is what makes a verdict auditable six weeks later.
- `bear_case` — mandatory on every ADVANCE, carried forward verbatim onto the plan line
- `dissent` — named minority position where seats disagreed, preserved not averaged
- `challenge_response` — how each rogers entry was weighed. Ignoring one is not permitted;
  "noted and outweighed because X" is.
- `frame_fit` — `aligned` / `neutral` / `contradicts`, with the reason. **A contradiction does
  not kill an idea** — Crown is weather, not a gate — but it must be argued in the verdict text.
- `data_anchors[]` — the 3–5 decisive numbers. No verdict ships on prose alone.
- `conditions[]` — for HOLD-FOR-CONDITIONS, the observable that would promote it

## Pass D · CIO SYNTHESIS (one agent, after all verdicts)

The per-name passes cannot see the portfolio. This one can, and answers what a CIO actually
asks *after* reading a list of ideas:

- **Coherence** — do these ideas express one view of the day, or five contradictory ones?
- **Concentration** — sector/factor clustering across the ADVANCE set (flag, never block:
  position-level risk gates live in the existing machinery, not here)
- **Regime consistency** — is the set as a whole expressing the Crown family, or fighting it?
- **The strongest thing we are ignoring** — the highest-conviction name that did NOT advance, and why
- **What the committee could not see today** — the blind spots that mattered, from the union of
  `unanswerable_gaps[]` and the ingest receipt's degraded flags

**Returns** `cio_synthesis.json`. This is the block the PM reads first in S7.

---

## Hard limits (v0.1)

No sizes, no orders, no dollar amounts, no position management. Conviction and frame-fit are
as far as this stage goes; capital allocation is the PM's and lives behind the existing gates.
Constitution law 1 is untouched — nothing here places, sizes or arms anything.
