# PMA tool defects found and fixed in-run — 2026-09-08

Three defects surfaced during the 2026-09-08 run. All three were fixed at source, verified against
the 65-test regression suite, declared on the run scoreboard, and are **not yet pushed to
`TongIncomeWheel/AQE` main**. Until they are, every fresh checkout still carries them.

---

## 1. `preflight_run.py` — `stamp` wrote a malformed scoreboard step

**Symptom.** `registrar.py commit` raised `KeyError: 'files'` on every GATHER artifact. GATHER
ticked `done` with **zero files recorded** — the run looked clean and had no provenance.

**Cause.** `stamp_tool_hashes()` did `m.setdefault("steps", {}).setdefault("GATHER", {})["tool_hashes"] = h`.
That seeds GATHER as a bare `{}`. `cmd_commit` only builds a canonical step via `_blank_step()`
when the step does not already exist, so it then indexed `step["files"]` on a step that had none.

**Fix.** `stamp_tool_hashes()` now seeds the full canonical step shape
(`status`/`files`/`tokens`/`notes`/`cost`) before writing `tool_hashes`, and back-fills any missing
key. A `setdefault` inside `cmd_commit` was rejected as the fix: that is an adapter around a
malformed step, which R6 forbids. Any tool writing a step to the scoreboard must write the whole
step shape.

**Verification.** Scoreboard re-initialised, tools re-stamped, preflight re-run PASS, all 7 GATHER
artifacts committed with digests.

---

## 2. `pma_pipeline.py r2digest` — challenge-document contract is unwritten

**Symptom.** `r2digest` refused to build the vote packet: *"challenge document 'steenbarger'
produced ZERO lines."* Three of four challenge documents were affected.

**Cause.** The reader knew `findings[] / challenges[] / catalyst_check[] / entries[] /
obligations[] / verdicts[] / reads[]`. The seats filed complete, correct documents under
`conviction_audit[]`, `process_findings[]`, `repeat_exposure[]`, `obligation_register[]`
(steenbarger), `assessments[]` (lynch) and `structures[]` (detect-lens).

**The refusal was correct** — it is the 2026-09-07 anti-silent-drop guard doing exactly its job.
The defect is upstream of it: **there is no `contracts/challenge.schema.json`.** The challenge
document shape has never been written down, so each seat guesses, and the guesses differ.

**Fix (interim).** The tolerated union in `r2digest` is now the written contract — widened to those
six key names, with field aliases so the content renders (`filed_conviction`/`supported_conviction`,
`sessions`, `score_band`, `peg`, `contradicts_technicals`, `state`, `extension_pct`,
`invalidation`, `falsifier`). No per-seat translation at the call site (R6).

**Fix (owed).** Write `contracts/challenge.schema.json` and have each challenge seat file against
it, the way Round 1 and Round 2 already do. Until that exists this class of failure recurs
whenever a seat card is reworded.

---

## 3. `registrar.py` — the R1 reject-detector punished R1 compliance

**The worst of the three.** `_bracket_as_reject()` rejected oneil's entire Round-2 form on 12 of 16
votes. Under the failure policy that is one respawn then **absent** — the run would have lost the
one seat whose whole finding was that nothing in the universe had buyers behind it.

**Cause.** The test searched the joined text for a `BRACKET_TERM` and, independently, anywhere at
all for a `REJECT_VERB`, and treated any co-occurrence as a violation. oneil's `opposing_case`
fields read *"No bracket cited"* and *"Not a bracket objection"* — the seat stating explicitly that
it was **not** using a bracket — which matched `BRACKET_TERM`, while a `fails` belonging to a volume
sentence several clauses away matched `REJECT_VERB`. **The rule punished precisely the compliance it
exists to produce.**

**Fix.** Two narrowings, neither of which loosens R1:

1. **Disclaimer-aware** — `BRACKET_DISCLAIMER` strips clauses that explicitly deny a bracket basis
   ("no bracket cited", "not a bracket objection", "bracket not relevant", "information only — R1")
   before the test runs.
2. **Sentence-local** — the bracket term and the reject verb must now occur in the **same sentence**.
   A real violation ("bracket.valid is false, so this cannot be taken") is one sentence. A bracket
   named as information in one sentence and "fails" applied to volume in another is two claims and
   was never one violation.

**Verification.** Six genuine-violation cases still REJECT (bracket-as-reject, no-valid-bracket,
risk_pct disqualifies, invalid-bracket-no-entry, R:R rules it out, stop-too-wide). Six compliance
cases now pass. 65/65 regression green. All 11 Round-2 forms then validated OK; oneil carries 14
`BRACKET_MENTION` flags, which is the correct outcome — a mention is permitted, a rejection is not.

---

## What is owed upstream

| File | Change | Priority |
|---|---|---|
| `aegis/skills/premarket-analysis/tools/preflight_run.py` | canonical step shape in `stamp_tool_hashes` | push |
| `aegis/skills/premarket-analysis/tools/pma_pipeline.py` | widened challenge-document contract in `r2digest` | push |
| `aegis/skills/premarket-analysis/tools/registrar.py` | disclaimer-aware, sentence-local `_bracket_as_reject` | **push — this one costs a seat** |
| `aegis/skills/premarket-analysis/contracts/challenge.schema.json` | **does not exist** — write it | next build |
| `aegis/skills/premarket-analysis/tests/test_pipeline.py` | add the 12 R1 cases above as fixtures so this cannot regress | next build |

A rebuilt `aegis-core` plugin should carry all three tool fixes; the versions shipped in 1.12.0 do not.
