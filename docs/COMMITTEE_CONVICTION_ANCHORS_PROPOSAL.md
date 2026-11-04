# Committee conviction 1-5 — written anchors (PROPOSAL for PM sign-off, 4 Nov 2026)

**Status: DRAFT. Not wired into any seat card or form until the PM signs.** The PM said YES to written anchors (relayed by the
conductor, 4 Nov). This file is the whole change; on sign-off it goes into `contracts/ratification.schema.json` (`x_note` on
`conviction`) and each decider's card as one short paragraph.

## What the number is

Each decider scores every slated ticket 1-5 when it ratifies. The committee figure is the **median** of the deciders' scores
(ties to the lower), with a quorum of 4. Without anchors the first live run reported 3/5 on 13 of 14 tickets (a later reading of the same
run showed 2-5), so the number ordered little.

The score answers one question, **in the voice's own method**: *"How completely does this ticket, exactly as written — the
name, the trigger and the wrong-if — meet what my method requires?"* It is a statement about the ticket. It is **not** a
size, not a confidence in the market, not a probability, and never a reason to act or to stand aside: the verdict is the
R34 objection count, and conviction is an ordering readout beside it (R42).

## The anchors (same words for every seat)

| Score | Means | Test the voice applies to itself |
|---|---|---|
| **5** | Textbook. Every condition my method requires is present and confirmed on this ticket, nothing I treat as a veto is in play, and the trigger is the one I would have written. | Can I name anything I would still want to see first? If yes, it is not a 5. |
| **4** | Strong. All required conditions are present; one *supporting* condition is missing, unconfirmed or mixed, and I can name it. It does not touch a veto. | I name the one thing; the ticket works without it. |
| **3** | Qualified. The setup is real, but a required condition is unconfirmed or the context does not help; I support it only **if a named condition holds** (usually the trigger itself). | The ticket is a conditional yes: "yes, once X". |
| **2** | Marginal. The name is a fair candidate, but a required condition is failing or a veto-adjacent flag is present, or the trigger/wrong-if as written is not the one my method would use. I am on the slate only because I did not object. | I would not have nominated it on my own method. |
| **1** | Weak as written. The ticket fails what my method requires (a veto condition is in play, or the trigger/wrong-if is wrong for my method). A 1 is normally paired with OBJECT and the one thing that would clear it. | I am scoring the ticket, not the name; a better-written ticket on the same name could score higher. |

Rules that go with the table (proposed, small):
1. Score the **ticket as written**. If the name is good but the trigger is wrong for my method, that is a 2 or a 1 with the objection saying why.
2. A score of **4 or 5 may not carry an OBJECT**; a score of **1 should carry one** (the registrar can check both; this is the only machine rule proposed).
3. No score may be justified by sizing, position count, P&L, or the Chair's view. Data gaps are declared, not scored: a field the seat cannot see lowers the score only as "unconfirmed condition" (a 3 or below), and the reservation names the field.
4. Anchors carry **no** "use at least two levels" rule. (That would change what the number means; it is separate and the PM has not asked for it.)

## How each seat reads the anchors in its own terms

This is a reading aid so the same word means the same thing across methods. Terms are the ones already in each canon
(`canon.lock.yaml` recognisers); the canon owner signs the exact wording.

| Seat | A **5** looks like | A **1** looks like |
|---|---|---|
| **oneil** | Market gate shown as a Confirmed Uptrend; `rs_leadership` LEADER at the top of its group; a completed base with the pivot within 5%; day volume at least 1.4x its 20-day average; stop inside what he would defend (7-8%) | Gate not a Confirmed Uptrend, or not a group leader, or no completed base, or price well above the pivot |
| **minervini** | Passes the Trend Template; a clean base with an identifiable pivot; volume dry at the base and expanding on the pivot | Fails the Trend Template, or a broken trend, or price far above its pivot with no clean base |
| **livermore** | A pivotal point with the line of least resistance up; volume confirms the move; momentum state supports | No pivotal point or the line of least resistance is against it |
| **elder-lens** | Weekly trend UP, impulse colour not RED, force index zones agree, price not above the upper channel wall | Impulse RED, or weekly trend not UP, or price above the upper channel wall |
| **seow** | Pullback setup met (20 above 40, 20-day average rising, CCI under -100, close above the 40) and the trigger bar defined; stock outperforming the index | Setup not met, or stock below the index over 63 days |
| **raschke** | The named pattern (Turtle Soup, Holy Grail, ADX Gapper, NR4/NR7 breakout, etc.) is complete with its stop defined | Pattern incomplete or its gating (ADX, stochastic) fails |
| **wyckoff** | Break of structure with price above value and the point of control, volume and close-location agree | No break of structure, price below value, or an exhausted move (more than about 1 ATR above the broken level and the value-area high) |

## What changes if signed

- `ratification.schema.json`: the `conviction` note carries the table above.
- Each decider card: one paragraph = the "Test the voice applies to itself" column plus its row of the reading table.
- `registrar.py validate --kind ratify`: optional check of rule 2 (4/5 with OBJECT refused; 1 without OBJECT warned).
- No change to the median, the quorum, the verdict rule (R34) or what the number gates (nothing).

## Decisions for the PM

1. Sign the five anchors as written, or mark the words to change.
2. Rule 2 (4-5 may not OBJECT; 1 should): yes / no.
3. Whether the per-seat reading table goes onto each card as is, or each canon owner rewrites its row first.
