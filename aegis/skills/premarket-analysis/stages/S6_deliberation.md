# S6 — DELIBERATION (judgment; ONE isolated committee-desk agent)

**Job.** Turn the deliberation set into verdicts a PM can act on. Spawned once, isolated,
judgment-tier — never run inline in the orchestrator's context (D-16).

**The packet:** every nominating voice's case VERBATIM (with its `field_values`), the tally,
`challenge.json`, `weather.json` (crown NOW + druck NEXT), `market_frame.json`.

**Returns** `data/pma/DATE/committee_read.json` (contract:
`contracts/pma/committee_read.schema.json`): per deliberation-set name —

- `verdict`: ADVANCE / HOLD-FOR-CONDITIONS / PASS
- `conviction` (1–5), a MANDATORY `bear_case`, and `dissent` where seats disagreed
- `data_anchors[]`: the 3–5 decisive numbers behind the verdict (field + value — no verdict
  ships on prose alone)
- `challenge_response`: how the rogers entries on this name were weighed (answered, not ignored)
- `frame_consistency`: does this idea fit the allowed crown family and the momentum caveat?
  A contradiction doesn't kill the idea — it must be ARGUED in the verdict text.

**Hard rule.** v0.1 emits no sizes and no orders. Conviction and family-fit are as far as
this stage goes; capital is the PM's.
