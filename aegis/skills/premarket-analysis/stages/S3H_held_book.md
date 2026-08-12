# S3H — THE HELD BOOK · the gap, and how it closes

**Found by the PM, 2026-08-12,** while asking what the legacy `committee_read` field was. It is
the committee's verdict on a position you already own — RUN / TAKE-PARTIAL / TIGHTEN / EXIT
(decision D-34). PMA v0.4 has no equivalent. That is a real hole, and it is the single most
important one in the design, for a reason the existing system already states plainly:

> **D-33: exits before entries.** The held book is deliberated FIRST, because what you free up
> determines what you can put on. A morning plan that lists new ideas before saying what to do
> with what you already own has the funnel backwards.

PMA was scoped away from the held book deliberately (PM, 2026-08-11: *"we don't need to look at
specific tickers or held book at the moment at position level"*). That scoping was right for
getting the frame built. It is now the thing standing between PMA and being the actual morning
kernel.

---

## The principle that keeps this honest

**PMA supplies the JUDGEMENT. It never touches the MATH.**

The existing machinery already owns the mechanical side and keeps it: `trailing_stop.py`
computes the stop FLOOR, which ratchets and never lowers, and protects the position regardless
of what anybody thinks. PMA does not move a stop, does not size a trim, does not place
anything. It produces the committee's *read* — and the read plus the floor is what the PM
decides from.

D-34 says exactly this: the trailing stop is the mechanical floor; take-profit fractions are a
*suggested default*; **the PM decides partial-vs-run from the committee read, never auto-scaled.**
PMA fills in the "committee read" half that PMA v0.4 currently leaves blank.

---

## ⚠ The data trap — read before building

The held book must come from the **Aegis PTJ file**, NOT from the AQE export's `held_positions`.

The export carries a `held_book` block and it is tempting to use, but it is the wrong source and
has already burned this system once: on 18 Jul the export's held_positions **mismatched the live
account** (BL-024), which is why D-17/D-21 made the PTJ file the one source already filtered to
the Aegis sub-fund. Yesterday's dry run reproduced the same smell from the other side — the scan
did not serve 9 names the held book contains.

So S3H adds a **third input** to PMA, and S1 must land it in the repo alongside the other two:

```
data/aqe/<date>/  aqe_daily_export.json.gz · aqe_crown_macro.json · manifest.json
data/ptj/<date>/  held_book.json          ← NEW: the authoritative Aegis book
```

If the PTJ file is absent or stale, **the held track stands down and says so.** It does not
silently fall back to the export. Wrong-book verdicts are worse than no verdicts.

---

## The population

Every open Aegis position. Not a screen, not a selection — the whole book, every morning.
A position the committee does not discuss is a position nobody is watching.

**Per-position row** (from the PTJ file, marked to price):
ticker · entry price · current price · unrealised % and $ · **R-multiple** · days held ·
current stop and its distance · sector · the mechanical trail's latest floor · and the same AQE
fields the name carries in the candidate frame (composites, lens block, structure, momentum)
so a seat can read it with the same eyes it reads a new idea.

---

## It flows through the SAME machinery

This is the point — no new pipeline, no new agents, no second deliberation engine.

| Stage | New ideas | Held book |
|---|---|---|
| **S4 Round 1** | nominate up to 10 from the universe | **a read on EVERY position** — the book is not optional |
| **S5** | rogers challenges the tally · weather | same weather; rogers may challenge a *hold* as easily as a buy |
| **S6 Round 2** | stance on every narrowed name | stance on every held position |
| **S6 Round 3** | rebuttal on open O7 | same |
| **S6b consensus** | ADVANCE / HOLD-FOR-CONDITIONS / PASS | **RUN / TAKE-PARTIAL / TIGHTEN / EXIT** |
| **S7** | ideas section | **held actions section — FIRST, per D-33** |

Only the **stance vocabulary** differs. Obligations, coverage matrix, rebuttal trigger,
completeness certificate, conviction caps, the no-generated-prose rule — all identical and all
reused.

### Stance vocabulary for held positions

| Stance | Means |
|---|---|
| `RUN` | thesis intact, momentum intact — let it work |
| `TAKE-PARTIAL` | bank some, keep the rest working |
| `TIGHTEN` | thesis weakening — reduce the room, not the position |
| `EXIT` | thesis broken |

Same mandatory fields as a new-idea stance: a reason carrying `{field, value}`, a falsifier
(`what_would_make_me_wrong`), an `opposing_argument` on any EXIT and on any RUN at conviction ≥4
(a seat holding hard through weakness must show it has looked), and `abstain_reason` where a
position sits outside a seat's canon.

### Two seats carry the same standing briefs, pointed at the book

- **rogers — is the CROWD wrong?** A position every seat wants to RUN is evidence about the
  seats. Crowding cuts both ways: consensus to hold is as much a warning as consensus to buy.
- **steenbarger — is the COMMITTEE wrong about its own certainty?** This is where its canon
  earns the most. The named failure modes are exactly the held-book ones: **attachment** to a
  name carried from a prior day, **ego** holding a loser to be proven right, **revenge** sizing
  after a loss, and the specific trap its own canon names — *holding a loser back to breakeven
  is economically identical to putting the same capital in a fresh setup, minus the attachment.*
  A `TIGHTEN`/`EXIT` recommendation that the committee resists is precisely what its
  `conviction_audit` is for.

---

## What the CIO page gains (S7, revised order)

The held section moves **above** new ideas, per D-33:

```
1 HEADLINE            day type + data quality
2 WHAT CHANGED
3 WEATHER PAIR        crown NOW · druckenmiller NEXT
4 CIO SYNTHESIS
5 HELD ACTIONS   ←    NEW. Per position: verdict, conviction, who dissented,
                      the bear case, the mechanical stop floor alongside it,
                      and what would change the verdict
6 CAPITAL FREED  ←    NEW. What EXIT and TAKE-PARTIAL release — the number that
                      makes the next section affordable
7 ACTIONABLE IDEAS    unchanged
8 WATCH TABLE
9 KEY LEVELS
10 WHAT WOULD CHANGE THIS PLAN
11 DECLARED GAPS
```

Section 6 is what makes the funnel real rather than rhetorical: you cannot judge whether a new
idea is affordable until you know what the book is giving back.

---

## Hard limits (unchanged)

PMA produces a READ. It does not move a stop, compute a trim size, place an order, or override
the mechanical floor. `trailing_stop.py` keeps the floor; the gatekeeper keeps the orders;
the PM keeps the decision. Constitution law 1 untouched.

## Build status

**DESIGN ONLY.** Not built, not wired, no runner support. Sequenced behind the PTJ ingest
dependency above — the held track cannot be trusted until it reads the right book.
