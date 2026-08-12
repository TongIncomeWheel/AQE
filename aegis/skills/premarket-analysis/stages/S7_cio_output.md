# S7 — THE CIO REPORT · 5 sections, plain English, delivered twice

**PM specification, 2026-08-12.** The report is written **in chat** so it is read where the PM
actually is, **and** to a fixed GitHub path so it is durable and diffable. Both, every run.

- **Chat:** the full report, plain English, simple tables.
- **File:** `aegis/reports/pma/<YYYY-MM-DD>.md` — fixed location, one file per run date, plus
  `aegis/reports/pma/latest.md` overwritten each run so there is always one path that means "today".

Deterministic render. No model runs at this stage — everything is already decided upstream, S7
only arranges it. Every sentence is a template, a number traced to a field, or a verbatim quote
attributed to a named seat.

## Style rules (all five sections)

- **Plain English.** No RB keys, no acronyms without their meaning, no internal jargon. "The
  average stock is losing to the index" — not "breadth ratio narrowing".
- **Simple tables.** Few columns. Every number carries its unit.
- **Every table earns its place with an impact line** — what it means and what to do. A table
  with no "so what" is deleted.
- **Absence is printed, never omitted.** A missing seat, a stale file, a field the committee
  needed and did not have — all appear.

---

## SECTION 1 · MACRO — what kind of day is this?

Headline in one sentence: day type + data confidence.

| Table | Columns | Impact line |
|---|---|---|
| **Market state** | Reading · Value · What it means | one sentence on what today permits |
| **The two weather reads** | Crown NOW · Druckenmiller NEXT · Agree/Differ | where they disagree, because that is the information |
| **Levels that matter today** | What · Now · Level · Distance · If it breaks | the nearest one, and what it changes |
| **Data confidence** | File · Age (trading days) · Gap · Verdict | from S0 Part B, verbatim |

Ends with **"What would change this read"** — real levels, never sentiment.

## SECTION 2 · HELD — what to do with what we already own

**Exits before entries** — this section sits above new ideas on purpose. What you free
determines what you can afford.

| Table | Columns | Impact line |
|---|---|---|
| **Position verdicts** | Ticker · Verdict (Run/Take-partial/Tighten/Exit) · Conviction · Who dissented · Why (2 numbers) | count by verdict |
| **Positions without a stop** | Ticker · Why it matters | the risk carried right now |
| **Capital freed** | From exits · From trims · Total | what Section 3–4 can afford |
| **Not reviewed** | Ticker · Why not seen | honest coverage statement |

## SECTION 3 · DELIBERATION STAGE 1 — what each voice found alone

Eleven seats, isolated, no cross-talk. This is the raw independent read.

| Table | Columns | Impact line |
|---|---|---|
| **Who nominated what** | Ticker · Seats backing · Highest conviction · Which seats | where independent agreement clustered |
| **Seat participation** | Seat · Nominated · Shortfall reason · Grounding | any seat running card-only is named here |
| **What the committee could not see** | Missing field · Seats blocked · What it disabled | the AQE change request, generated as a by-product |

Agreement here is **evidence about the seats, not about the asset** — it becomes a view only
after Stage 2.

## SECTION 4 · DELIBERATION STAGE 2 — what survived the argument

The same seats, now seeing each other, plus the two challenge functions.

| Table | Columns | Impact line |
|---|---|---|
| **Verdicts** | Ticker · Verdict · Conviction · Backed by · Opposed by · What capped it | count advancing |
| **The strongest case against each** | Ticker · The argument · Who made it · Answered? | which idea is least defended |
| **Contested** | Ticker · The disagreement · Both positions | deadlock is printed, never broken by the system |
| **Convictions that moved** | Ticker · Seat · From → To · What moved it | where the debate actually did work |
| **Watch list** | Ticker · Backed after debate by · What would promote it | |

Rogers asks whether the crowd is wrong. Steenbarger asks whether **we** are wrong about our own
certainty. Both are reported; neither blocks.

## SECTION 5 · SUMMARY AND RUN-THROUGH

The audit trail, in plain English.

| Table | Columns |
|---|---|
| **What ran** | Stage · Status · Duration · Output |
| **Voices** | Expected · Loaded · Ungrounded · Unavailable · Quorum met |
| **Completeness** | Obligations created · Discharged · Contested · Waived |
| **Where the data came from** | Input · Source · Timestamp · Age |
| **What we could not do today** | Gap · Impact on the plan |
| **Actions for the PM** | Decision needed · By when |

Ends with the status line, always last:
`DRAFT — PM approval required. Nothing is staged, nothing is armed.`
