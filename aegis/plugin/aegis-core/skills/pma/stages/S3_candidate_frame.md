# S3 — CANDIDATE FRAME (deterministic)

**Job.** Answer "what is on the table today?" — the pool the voices nominate from, framed,
not analysed. No opinions, no per-ticker judgement; that belongs to S4/S6.

**Reads.** From the export: `daily_list[]` (the scan's served per-ticker rows),
`lens_ranking`, `signal_radar`, `_radar_pool`, `held_positions` (ONLY to tag names as
already-held — v0.1 does no position work but voices must know what the book already owns so
they don't "discover" it).

**Output.** `data/pma/DATE/candidate_set.json` (contract: `contracts/pma/candidate_set.schema.json`):

- `universe[]`: one row per candidate, carrying the SERVED fields verbatim (rank, composites,
  lens block, momentum/structure/flow/energy, brackets if present, sector) — the voices' raw
  material, unfiltered and un-reordered (anti-anchoring: no pipeline tags, no ordering hints)
- `frame`: counts by tier, sector distribution, lens-strength distribution, how many carry a
  valid bracket, how many are flagged held
- `near_misses[]`: surfaced, never nominated (D-37)

**Rule.** S3 never drops a name the export served and never adds one it didn't. The screen
is AQE's; the committee's job starts from what AQE served.
