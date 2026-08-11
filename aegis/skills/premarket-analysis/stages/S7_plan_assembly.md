# S7 — PLAN ASSEMBLY (deterministic render)

**Job.** One page the PM can act on from a phone. Deterministic: everything here is already
decided upstream; S7 only arranges it. Fixed order, always:

1. **Headline** — one sentence: what kind of day + data-quality flags. (e.g. "AMBER,
   mean-revert tape — momentum needs tighter proof today; Crown: stock-picker's market,
   BROADENING_CARRY at 1.0x. Crown ran DEGRADED — economic calendar absent.")
2. **The weather pair** — Crown NOW (verbatim four blocks, compressed) then Druckenmiller
   NEXT (the brief's so-what). Explicitly labelled context, not gate.
3. **Actionable ideas** — every ADVANCE, one line each: name, verdict conviction, the entry
   frame (bracket verbatim from AQE where served), "why (data):" with the 3–5 anchors in
   plain labels, the bear case in one clause, any rogers flag in plain words.
4. **Watch table** — HOLD-FOR-CONDITIONS + high-interest non-advanced names, collapsed:
   name, count, seats, the condition that would promote it.
5. **Key levels to watch today** — the nearest crown `key_levels` + any AQE regime levels,
   each with its "if it breaks" sentence.
6. **What would change this plan** — the falsifiers, verbatim from crown
   `what_would_change_it` + any deliberation conditions.
7. **Declared gaps** — what today's run could not see (from S8's preliminary pass): absent
   files, empty seats, NOT_SERVED fields that mattered.

**Output.** `data/pma/DATE/premarket_plan.json` (contract:
`contracts/pma/premarket_plan.schema.json`) + `plan.md` (the phone render — plain words,
numbers always shown, no acronyms without meaning).

**Status line, always last:** `DRAFT — PM approval required. Nothing is staged, nothing is armed.`
