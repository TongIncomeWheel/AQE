# S4 — VOICE SWARM (judgment; 10 isolated agents in parallel)

**Job.** Every nominating seat reads the day through its own canon and returns its view as
JSON. This is where the committee actually thinks — in parallel, blind to each other.

**Nominating seats (10):** lynch, oneil, wyckoff, raschke, steenbarger, thorp, seow,
minervini, livermore, elder-lens, detect-lens minus rogers (challenge, S5) and minus
crown/druckenmiller (weather, S5). *(Exact roster is the packaged `agents/voice-*.md` set —
the card list is authoritative, not this sentence.)*

**The packet (the JSON bridge, per voice):**
```
voice_packet = {
  market_frame:   market_frame.json            (same for all — the weather they wake up to),
  candidates:     candidate_set.json.universe  (same for all, un-ordered),
  menu:           the voice's own field menu   (VOICE_MENUS — what it may cite),
  memory:         tools/voice_memory.py render <voice>  (its rolling stats + standing lessons)
}
```
Spawn: fresh agent, no tools, no session context, prompt = its `agents/voice-<v>.md` card +
the packet. Return: `nomination.json` per `contracts/nomination.schema.json` (unchanged —
the existing contract IS the bridge). Schema-validate on receipt; one re-spawn on failure.

**Tally (deterministic close of stage).** Count nominations across seats; stamp
`price_at_nomination` and `field_values` (the actual numbers behind every cited field — a
dictionary lookup, not judgement); write `data/pma/DATE/voices/<voice>.json` and `tally.json`.
Record all nominations to the ledger (`tools/nomination_ledger.py record`) — the scorecard
that proves or kills seats runs off this.

**Deliberation set rule (RB:committee.deliberation_threshold):** ≥2 nominations OR lens top
tier OR a single seat at conviction ≥ solo_high_conviction_min. Everything else → watch table
with its counts and anchors.
