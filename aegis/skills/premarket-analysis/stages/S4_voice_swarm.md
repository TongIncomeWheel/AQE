# S4 — VOICE SWARM (judgment · N isolated agents in parallel)

The committee's first act. Every nominating seat reads the same day through its own canon,
blind to every other seat, and returns a structured opinion. This stage is where independence
is manufactured — everything downstream depends on these opinions being genuinely uncorrelated.

## Roster

Nominators (11 locked seats): `lynch · oneil · wyckoff · raschke · steenbarger · thorp · seow ·
minervini · livermore · elder-lens · detect-lens`. Authoritative list = the packaged
`agents/voice-*.md` set with `seat_kind: nominator`.

NOT here: `rogers` (challenge — S5a), `crown` + `druckenmiller` (weather — S5b/c). They run
after the tally by design, so weather and challenge can never steer the nominations they are
supposed to be reacting to.

## The packet — content inline, never a path

```yaml
voice_packet:
  run:          {date, staleness_days, pm_ack, degraded_flags}   # the honesty header, first
  market_frame: <market_frame.json inline>       # same for every seat
  candidates:   <candidate rows, menu-sliced, ORDER RANDOMISED per seat>
  menu:         <this voice's VOICE_MENUS entry> # the fields it may cite
  memory:       <tools/voice_memory.py render <voice>>  # rolling stats, open picks, STANDING LESSONS
```

**Hard rule, from finding F1 (2026-08-11).** Compiled voice agents are toolless by design. A
toolless agent handed a *file path* cannot read it — and in test, four separate seats
**fabricated** plausible file listings and market values rather than reporting failure. The
orchestrator MUST inline packet content into the spawn prompt. Passing a path is a
correctness bug, not a style choice.

**Menu slicing** is what makes 11 seats affordable: ~215 KB/seat sliced vs ~987 KB raw. It is
also a discipline — a seat can only cite what its canon entitles it to see.

**Order randomisation** per seat: candidate rows are shuffled with a per-seat seed so no seat
inherits AQE's ranking as an implicit hint. Anti-anchoring is not only about hiding other
voices; it is about hiding the pipeline's own opinion.

## What a seat returns

`contracts/nomination.schema.json` (existing contract, reused unchanged) — up to 10 names,
each with:

- `conviction` 1–5 **with the rule that conviction is a claim about evidence, not enthusiasm**
- `reasons[]` — every reason carries `{field, value}` drawn from the packet. A reason without a
  field+value is struck at validation, not politely ignored.
- `lesson_applied` — which STANDING LESSON from its memory governs today (D-14). A seat that
  cannot name one has not read its own record.
- `declared.not_served[]` — what its canon needed and the packet did not carry. **This is a
  first-class output, not an apology.** It is the raw material for the AQE change request.
- `shortfall_reason` if fewer than 10 — a short honest list beats a padded one.

Validation on receipt; one re-spawn on invalid; still invalid → empty seat recorded in
`tally.json.shortfalls`, run continues at ≥8 seats, S8 flags it.

## The tally (deterministic — no model touches this)

1. Count nominations per name across seats.
2. Stamp `price_at_nomination` and `field_values` for every cited field — a dictionary lookup
   against the day's data, never a model recollection.
3. Write `data/pma/<date>/voices/<voice>.json` + `tally.json`.
4. Record every nomination to the ledger (`tools/nomination_ledger.py record`) — this is what
   eventually proves or kills each seat at d1/d3/d5/d10/d15.

## Deliberation set (RB:committee.deliberation_threshold)

`nomination_count ≥ 2` **OR** lens top tier **OR** a single seat at conviction ≥
`solo_high_conviction_min`. Everything else → watch table carrying its counts, its seats and
2–3 anchor values — never a bare ticker.

**Consensus is evidence about the seats, not about the asset.** The tally counts votes; it
does not rank by them. Ranking happens in S6, after the bear case.
