---
name: recover
description: The PM's manual self-heal levers (D-45) — re-run a critical step on demand, or let the system attempt a bounded automatic fix after a failure. Triggers on "/recover", "/heal", "/repull", "/reseed". Owned by Engineering & Change (operational self-heal + data utilities). Every lever re-runs only READ / COMPUTE / DATA / PLAN work; NONE places, sizes, or arms an order (constitution law 1). A recovered loop that reaches execution still produces only a gatekeeper PREVIEW that waits for the PM. Reuses the D-40 historical-store self-heal and the existing loop skills — never re-implements them.
---

# Manual self-heal — fix-first, PM's hand on the levers

When something fails, the flow is: detect → attempt a safe automatic fix →
if it can't heal, page the PM with the exact command below. These are those
commands — the PM's manual levers for the same recovery paths.

**Inviolable boundary (the "adhered to" condition, constitution law 1):** every
lever here re-runs only reading, computing, data, or planning. Nothing in this
skill places, sizes, or arms an order. A re-run that reaches execution still
stops at a gatekeeper **preview** the PM must stage. Self-heal proposes; the
gatekeeper and PM dispose.

## The levers

- **`/recover [loop]`** → re-run a failed loop fresh (a fresh session reads
  state from disk and re-runs — idempotent). Loop ∈ premarket · market-hours ·
  post-market · eod-audit. Produces the loop's normal output (a plan still needs
  PM approval at premarket step 11).
- **`/heal [loop] --failure <type>`** → invoke the automatic recovery protocol
  for a classified failure: `python3 tools/self_heal.py <loop> --failure <type>`.
  Transient (feed/ptj/store) → bounded retry / reseed and report "healed".
  Structural (schema/config) → escalate with the fix. Gate/tripwire → **stand
  down, never auto-heal** — the PM clears or overrides (recorded).
- **`/repull`** → re-fetch today's AQE export, revalidate against the schema,
  re-run `tools/tripwires.py`. **`/repull ptj`** → re-pull both brokers and
  refresh dynCap (`tools/dyncap_ledger.py update <ptj>`).
- **`/reseed [tickers|universe]`** → force a historical-store seed via the D-40
  path (`tools/historical_store.py check` + `seed`) for missing/stale names.

## Doctrine

- **Reuse, not clone.** `/reseed` calls `historical_store.py` (D-40); `/repull`
  calls the existing feed + PTJ + tripwire tools; `/recover` re-runs the existing
  loop skills. This skill adds no new data logic.
- **Bounded + logged (law 3 / Failure rule).** Retries are capped
  (`self_heal.max_retries`); every action writes to
  `data/eod/<date>/self_heal_<date>.jsonl`; exhaustion escalates, never fabricates.
- **A gate is never healed.** A tripwire block or hard-gate breach stands the
  process down and pages — the PM is the only override, and it is recorded.
