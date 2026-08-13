# One Macro Pack — a proposal, not a build

Answers the second question from the 2026-08-13 taxonomy exercise: *how can
Macro Weather, SRM and Thematic Rotation combine with Crown into one macro
pack?* This is a design document. Nothing described here has been built —
Crown's standing directive is that its merge with the other three is a
**later, separate PM decision**, kept apart deliberately so the overlap stays
measurable instead of assumed. This proposal is the measurement.

---

## 1 · The finding: three of the four links already exist

The premise "four separate systems that need combining" turned out to be
wrong. Tracing every actual code path (not the module boundaries, the real
`import`/function-call graph):

```
Macro Weather ──────► SRM            ALREADY MERGED
  (7 instruments)       (sector grade)   via compute_macro_headwind:
                                          every sector's entry gate already
                                          reads a macro-weighted score built
                                          from the 7 instruments.

SRM ─────────────────► Thematic       ALREADY MERGED
  (grade + RRG)          Rotation        Thematic reuses grade_sector_etf's
                                          exact ladder and the exact same RRG
                                          quadrant/direction functions, on a
                                          basket's own equal-weight index, and
                                          rolls up to a parent GICS sector.

Macro Weather ◄──────► Crown          ALREADY MERGED
  (7 instruments)        (dispersion,     via macro/scenarios.py — the
                          CTA, breadth)    sanctioned "first merge point",
                                           built exactly for this.

Crown ────────X───────► SRM/Thematic  THE ONE GAP
  (regime, family)       (sector grade)   Crown reads nothing sector-level;
                                           SRM/Thematic read nothing from
                                           Crown or the scenario layer.
```

Three of the four pairings already talk to each other, in code that already
ships. The fourth pairing — Crown's regime-and-family read never reaching the
sector/theme layer, and vice versa — is the only real gap. "Combine four
systems into one" is the wrong frame; **close one link, then give the whole
chain one door.**

## 2 · The chain this reveals

Read top-to-bottom, what already exists is a hierarchy, not four peers:

```
Crown              what kind of market is this, and what's it doing?
  ↓ (via scenarios.py)
Scenario           which of 7 cross-asset stories fits, and how well?
  ↓ (THE GAP — does not exist today)
SRM sector grade   which sectors are positioned for that story?
  ↓ (already exists)
Thematic basket    which themes inside a sector are actually running?
  ↓ (already exists — daily_list projection)
Individual name    is this specific ticker part of that story?
```

Everything below the gap already flows correctly. Everything above it
already flows correctly. The gap is the one place a reader currently has to
do the cross-checking by hand: *"the leading scenario says X — do the sector
grades agree with that, or is something about to change?"*

## 3 · What "one macro pack" should actually be

**Not** a rewrite of Crown, SRM, Macro Weather or Thematic. Every one of
those stays exactly as it is, including Crown's standalone status — nothing
here asks Crown to import SRM or vice versa. **A new, read-only assembly
layer**, in the same spirit as `scenarios.py`: it reads finished outputs
from all four, adds exactly one new piece of analysis, and produces one
artifact a reader opens instead of stitching four together by hand.

### 3.1 What it reads (unchanged, no new coupling)

- Crown's finished dict (`crown_macro.json` / `aqe_crown_macro.json`)
- The scenario read (`macro_scenarios.json`)
- SRM's sector grades (`srm[]`, already in the daily export)
- Thematic Rotation's basket grades (`thematic_baskets[]`, already there)

### 3.2 The one new thing it adds: scenario-sector coherence

For the **leading scenario** (already computed by `scenarios.py`), each
scenario's condition list already names which cross-asset reads it needs
(`SCENARIOS[name]["conditions"]`, `scenarios.py:36+`). The new piece: map
each sector ETF's known macro sensitivity (`SENSITIVITY`, already computed
per-sector in `srm.py` for `compute_macro_headwind`) against what the
leading scenario implies, and report which sectors' **current grade
agrees**, which **disagree**, and which are **untested** (no clear
sensitivity read either way).

This is not a new gate and not a new score. It follows the same rule
`lens_consensus.py` and the scenario layer already established: **AQE prints
what agrees and what doesn't; it does not decide what that means.** A
sector graded DEPLOY while the leading scenario implies headwind for it is
not "wrong" — it is a fact worth a committee's five seconds, surfaced
instead of requiring someone to notice it by hand.

### 3.3 The artifact

`aqe_macro_pack.json`, plain-English-first like Crown's own reading copy, and
opening with the same two-field trust check the Committee Card puts first —
**check these before you trust any of it** applies to the pack exactly as it
applies to Crown alone, so the pack surfaces them at its own top level
rather than making a reader open the nested `crown` block to find them:

```
pack_status           OK / DEGRADED / PARTIAL — see §3.5. Read this FIRST.
crown_status          Crown's own status, copied to the top level, verbatim
oldest_leg            Crown's freshness.oldest_leg, copied to the top level
read_me_first         one paragraph: regime, leading scenario, headline coherence
crown                 Crown's own plain_english block, verbatim (no re-narration)
scenario              the leading scenario + its runner-up + falsifiers, verbatim
sector_read           every sector's grade/gate, tagged AGREES / DISAGREES /
                      UNTESTED against the leading scenario, sorted by
                      disagreement first (the most useful row is on top).
                      Absent entirely — not empty — when pack_status is
                      PARTIAL for the reason in §3.5.
thematic_read          same tagging, one level down, grouped by parent sector.
                       Same absent-not-empty rule.
what_changed           diff vs the previous run, reusing Crown's own changes.py
                       pattern — silence is a real answer
limits                 every standing caveat from Crown + scenarios, carried
                      forward verbatim, never re-derived
```

### 3.5 The EARLY_EXIT case — the one place this needed tightening

The Committee Card's central rule: *"a market you cannot read is not one you
take a smaller position in"* — on `crown_status: EARLY_EXIT` or
`UNAVAILABLE`, Crown's own downstream sections are empty **because they
never ran**, not because they came back quiet, and that distinction is
enforced in code and tested.

The pack inherits this exactly, because `sector_read`/`thematic_read` are
*derived from* the leading scenario, and there is no leading scenario to
derive from when Crown never produced a regime read. So:

- `crown_status` is `EARLY_EXIT`/`UNAVAILABLE` → `pack_status: PARTIAL`,
  `sector_read`/`thematic_read` are **absent from the JSON entirely**, and
  `read_me_first` states the reason in one sentence ("Crown's own gate
  stopped the process this run — no regime read, so no sector coherence
  either.") — never a coherence tag computed against nothing.
- `crown_status: DEGRADED` (ran, something missing or on a proxy) →
  `pack_status: DEGRADED`, sections still populate, and `limits` carries
  Crown's own `degraded` list forward unchanged.
- Two close scenarios (`scenarios.py`'s own `contested: true`) → coherence
  still computes against the leading one, but `read_me_first` states the
  contest exists, so a reader isn't shown false confidence in what "the"
  leading scenario implies.

### 3.4 What it explicitly does not do

- Does not change what `gics_gate`/`sector_entry_gate` compute. A sector
  disagreeing with the leading scenario does not change its own gate.
- Does not feed back into Crown, SRM, Macro Weather or Thematic — read-only,
  same non-invasive pattern `scenarios.py` already uses for Crown.
- Does not size or gate anything. Same four standing refusals as Crown
  itself (see `aegis/canon/crown/CROWN_VOICE_CHARTER.md` §7).
- Does not merge the underlying calculations. `en_pos50`/`ms_pos_score` stay
  two implementations of one idea (per the integrity findings doc, §5) —
  this pack reads both finished scores, it does not go in and fix the
  engines.

## 4 · Why this shape, not a bigger merge

The standing directive says the merge point should be **named**, not
buried inside one of the four systems (`scenarios.py`'s own docstring:
*"a named place where two independent readings meet, not a dependency
buried in one of them"*). A macro pack that imported SRM into Crown, or
Crown into SRM, would violate that on day one. Keeping it a **fifth,
external, read-only module** — `src/macro/pack.py`, next to `scenarios.py`,
not inside `crown/` — is what keeps every existing system's own tests and
own standalone guarantees intact while still giving a reader the single door
they're asking for.

The alternative — literally merging the four into one computation — would
also throw away the thing CLAUDE.md says this separation is *for*:
"measuring where they agree and where they contradict is the next decision,
and it needs both running side by side first" (per `AQE_CROWN_MACRO_LAYER.md`,
"Not yet built"). A pack that reports agreement and disagreement *preserves*
that measurement. A pack that silently merges the numbers destroys it.

## 5 · Consistency check against the Committee Card — 2026-08-13

Checked directly against `docs/AQE_CROWN_COMMITTEE_CARD.md` (the PM asked for
this before signing off). Clean on all four standing refusals — the pack
sizes nothing, names no ticker, places nothing, and the coherence tag is a
category, never a number, so it can't drift into reading like QS's
calibrated probability sitting next to it.

Two real gaps found, both versions of the card's central rule — *"a market
you cannot read is not one you take a smaller position in"* / *"on
`EARLY_EXIT` the sections below are empty because they never ran, not
because they came back quiet"*:

1. The original draft never stated what the pack does on
   `crown_status: EARLY_EXIT`/`UNAVAILABLE`. Left unstated, a coherence tag
   could have silently computed against a scenario that was never produced —
   exactly the failure the card exists to prevent. Closed in §3.5.
2. The card puts `crown_status`/`freshness.oldest_leg` first, before
   trusting anything else. The original draft buried Crown's status inside
   a nested block. Closed in §3.3 — the pack now surfaces its own
   `pack_status`/`crown_status`/`oldest_leg` at the top level, so the
   "check these two first" rule applies to the pack exactly as it applies
   to Crown alone.

## 6 · What this needs from the PM before it's built

1. **Confirm the shape** — one new read-only module, one new artifact,
   no changes to Crown/SRM/Macro Weather/Thematic's own code or tests.
2. **Confirm the one new metric** — scenario-sector coherence (agree/
   disagree/untested) is the only genuinely new computation. Everything
   else in the pack is a verbatim read of an existing finished output.
3. **A name.** `aqe_macro_pack.json` is a placeholder — Crown's own naming
   convention (`aqe_crown_macro.json` = plain-English reading copy,
   `crown_macro.json` = runtime record with series) suggests this wants the
   same two-artifact split if it grows chart series later; for a v1 with no
   series, one artifact is enough.
4. **Where it runs.** Natural slot is a new daily-orchestrator step, after
   Crown (6f), scenarios (6g) and the SRM/thematic grading steps have all
   already run — reading their outputs, adding nothing to the critical
   path's own runtime beyond one more read-only pass.

Not implemented in this pass. Say the word and it's the next piece of work.
