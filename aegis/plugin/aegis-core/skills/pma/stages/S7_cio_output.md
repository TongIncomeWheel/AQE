# S7 — THE CIO REPORT · 5 sections, plain English, delivered twice

**PM specification, 2026-08-12. Ordering rule added 2026-08-14.** The report is written **in chat**
so it is read where the PM actually is, **and** to a fixed GitHub path so it is durable and diffable.
Both, every run.

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

## THE ORDERING RULE — sector and theme come first, everywhere

**PM ruling, 2026-08-14.** Sector rotation and thematic participation are the macro headwind that
sits on top of every single-name decision. No voice owns them as a nomination test, so the
**orchestrator** owns them as a **presentation rule**, applied to every name-bearing table in
Sections 2, 3 and 4:

1. **Group by sector strength first.** Names are bucketed by their sector's standing in the
   rotation model — `srm[].grade` (DEPLOY / HOLD / TURNING / WATCH / AVOID), refined by
   `srm[].rrg_quadrant` (LEADING / IMPROVING / WEAKENING / LAGGING) and `rrg_direction`.
   Strongest bucket printed first. A name in an AVOID or LAGGING sector is never printed above a
   name in a DEPLOY or LEADING one, regardless of its own score.
2. **Then by theme inside each bucket.** Within a sector group, order by
   `thematic_grade` / `thematic_parent_grade`, then `thematic_rrg_quadrant`. A name with no
   thematic membership prints last inside its sector group, labelled **"no theme"** — printed,
   never hidden.
3. **Then by whatever that table's own ranking is** (nomination count, conviction, verdict).

Each sector group carries a **one-line header** in plain English before its names:

> **Energy — deploy, leading and improving. Headwind: none flagged.**
> **Utilities — avoid, lagging. Headwind: flagged (score 0.7). Anything here is swimming upstream.**

The headwind line reads `srm[].macro_headwind_flag` and `macro_headwind_score`. Where the flag is
set, the header says so in words, and every name inside that group inherits the caveat without it
being restated per row.

**This is presentation, not a gate.** Nothing is filtered, demoted, capped or blocked by sector or
theme. A strong name in a weak sector still advances if the committee advanced it — it just
appears under a header that tells the PM what it is fighting. If a future PM ruling wants sector
to actually bind a decision, that belongs in a voice canon or the consensus rule, not here.

**Where the data comes from:** `srm[]` and `macro_weather` (top-level blocks, carried verbatim into
`universe.json`), and the per-name `sector_trend_state`, `sector_rrg_quadrant`,
`sector_rrg_direction`, `thematic_basket`, `thematic_grade`, `thematic_parent_gics`,
`thematic_parent_grade`, `thematic_rrg_quadrant`, `thematic_rrg_direction`. If a run arrives
without `srm[]`, S7 prints the tables ungrouped and says so in Section 5's gap table — it does not
guess an ordering.

---

## SECTION 1 · MACRO — what kind of day is this?

Headline in one sentence: day type + data confidence.

| Table | Columns | Impact line |
|---|---|---|
| **Where the strength is** | Sector · Grade · Rotation quadrant · Direction · Headwind flagged? | the two sectors to be in and the two to avoid today — this table sets the order of every table below |
| **Themes running** | Theme · Grade · Parent sector · Participation · Quadrant | which themes are actually being bought, not just which are talked about |
| **Market state** | Reading · Value · What it means | one sentence on what today permits |
| **The two weather reads** | Crown NOW · Druckenmiller NEXT · Agree/Differ | where they disagree, because that is the information |
| **Levels that matter today** | What · Now · Level · Distance · If it breaks | the nearest one, and what it changes |
| **Data confidence** | File · Age (trading days) · Gap · Verdict | from S0 Part B, verbatim |

Ends with **"What would change this read"** — real levels, never sentiment.

## SECTION 2 · HELD — what to do with what we already own

**Exits before entries** — this section sits above new ideas on purpose. What you free
determines what you can afford.

Grouped by sector strength, then theme, per the ordering rule. A held position sitting in an
AVOID / LAGGING sector is a fact the PM should see before the verdict, not after.

| Table | Columns | Impact line |
|---|---|---|
| **Position verdicts** | Ticker · Verdict (Run/Take-partial/Tighten/Exit) · Conviction · Who dissented · Why (2 numbers) | count by verdict |
| **Positions without a stop** | Ticker · Why it matters | the risk carried right now |
| **Capital freed** | From exits · From trims · Total | what Section 3–4 can afford |
| **Not reviewed** | Ticker · Why not seen | honest coverage statement |

## SECTION 3 · DELIBERATION STAGE 1 — what each voice found alone

Eleven seats, isolated, no cross-talk. This is the raw independent read.

Name tables grouped by sector strength, then theme.

| Table | Columns | Impact line |
|---|---|---|
| **Who nominated what** | Ticker · Seats backing · Highest conviction · Which seats | where independent agreement clustered — and whether it clustered inside one sector, which is a concentration warning, not a confirmation |
| **Seat participation** | Seat · Nominated · Shortfall reason · Grounding | any seat running card-only is named here |
| **What the committee could not see** | Missing field · Seats blocked · What it disabled | the AQE change request, generated as a by-product |

Agreement here is **evidence about the seats, not about the asset** — it becomes a view only
after Stage 2.

## SECTION 4 · DELIBERATION STAGE 2 — what survived the argument

The same seats, now seeing each other, plus the two challenge functions.

Name tables grouped by sector strength, then theme.

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
