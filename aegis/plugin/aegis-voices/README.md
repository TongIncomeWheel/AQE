# aegis-voices — the committee, and nothing else

**Layer: KNOWLEDGE. kernel_build `86525f9`. Plugin version 1.2.0.**

## What is in here

| Folder | What it holds |
|---|---|
| `agents/voice-*.md` | 15 isolated agents. Each is a complete standalone instruction set, spawned fresh with no session context, no other voices, `tools: []`. |
| `skills/voice-*/` | The methodology card for each seat, plus `voice-common`, the shared engine. |
| `contracts/` | `nomination.schema.json` (output contract), `field_dictionary.json`, `canon_index.json` (which principles each voice may cite). |
| `tools/voice_preflight.py` | The S0.5 gate. Run before the swarm. Says which voices can run and whether today's data is complete for each. |
| `tools/field_derive.py` | Fills the numbers the engine leaves null but that are fully determined by numbers it does emit. |
| `tools/canon_validate.py` | Runtime validator: checklist trace, principle ids, data menu. |

## The seats

**THE 30 OCT 2026 REDESIGN (RULINGS R31–R36; `docs/DECISIONS_2026-10-30.md` wins).**

**Deciders (7)** — oneil, minervini, livermore, elder-lens, seow, raschke, wyckoff. They shortlist (at most 6 each, R33),
vote blind with the case form (R36), argue on the floor (`skills/voice-deliberate`), and ratify the slate (R34).
**QA seat (1)** — steenbarger. Files the challenge document before the vote and one QA note after ratification;
may hold a ticket once; never votes.
**Independent list** — detect-lens is no longer a voice: the Cards show AQE's `lens_ranking.ranked[0:10]`.
**Bench** — weis, thorp (`archive/`). **Stood down** — rogers, lynch, crown, druckenmiller (`archive/`); the weather is
read from AQE's Crown file and the Valen dashboard.

Ratification roster is the 7 deciders; barrier 6 of 7; `ratify-count` refuses fewer than 4. All seven count on every
name — the lane tag is a label (R32). Nothing was deleted: `archive/README.md` says how to re-seat a bench voice.

## S0.5 — run this before every committee

```
python3 tools/voice_preflight.py \
  --export aegis/output/aqe_daily_export.json \
  --menus  aegis/skills/premarket-analysis/contracts/voice_menus.json \
  --canon  aegis/canon \
  --agents-dir <this plugin>/agents \
  --out    data/pma/<date>/activation.json --apply --strict
```

It answers two questions and never mixes them.

**1. Can this voice run?** Needs its agent file installed and its book (`canon.lock.yaml`)
present and parseable. Answer is **ACTIVATED** or **NOT ACTIVATED**. Nothing else stops a
voice speaking.

**2. Can it run its method on today's data?** Answer is **READY**, **SERVED** or **BLOCKED**.

Mixing those two is what produced ghost voices — a seat missing half its numbers still
returned ten confident nominations and nothing said so.

## Every missing number gets an action

The tool never reports a gap without saying what to do about it. Four outcomes:

| Outcome | Means | Action | Blocks? |
|---|---|---|---|
| `DERIVED` | The value is fully determined by fields that ARE populated. | Orchestrator computes it at packet build (`field_derive.py`) and tags it `_source: derived`. | No |
| `SUBSTITUTE_LIVE` | A populated fallback field carries the same information and is already on this seat's menu. | Serve the fallback under a labelled column; the seat declares the substitution. | No |
| `MENU_BUG` | The fallback is populated but is not on this seat's menu, so the seat never sees it. | Add one field name to `voice_menus.json`. | Yes |
| `ENGINE_TICKET` | Nothing anywhere in the export carries it. | The engine must emit it. | Yes |

Exit codes: `0` ready · `1` a voice is NOT ACTIVATED · `2` quorum failed · `3` a voice is
BLOCKED on data. `--strict` enforces them.

`activation.json` carries a `markdown` field. **§0 of the brief renders it verbatim.** Never
hand-typed. A run whose header does not carry that table has not passed S0.5.

## What `field_derive.py` is allowed to do

Labels, states and flags only — never a price, a level or a score. Every derivation must be
deterministic, must take inputs that are populated on ~100% of rows, and must write a parallel
`<field>_source: "derived"` so the seat can see the value was labelled, not measured. If you
find yourself computing a number a seat would trade on, that is an `ENGINE_TICKET`, not a
derivation.

Current derivations:

- `bracket.stop_type` — null on 78% of rows. On every one of those, `bracket.valid` is false
  and `bracket.atr_fallback_stop` is populated (100% of rows). The stop in force is the ATR
  fallback; the engine just never wrote the label. Filled as `atr_fallback`.
- `bracket.stop_eff` — the stop actually in force: structural if the bracket passed its gates,
  else the ATR fallback.

## Not in here, by design

No premarket / market-hours / post-market loops. No staging-gatekeeper and no order path. No
committee-desk. No scheduling, brackets, PTJ or recovery tooling. **Nothing in this plugin can
place, size or arm an order.** Those live in `aegis-core`.

## Version skew

`aegis-voices` and `aegis-core` are cut from one build and carry the same `kernel_build` stamp.
Different stamps on the two installed plugins means they are from different builds — re-cut both
rather than mixing, or a voice may cite a principle the orchestrator's index does not carry.

## Open PM items this package surfaces

1. **`bracket` gate calibration.** 76% of the universe fails the three gates
   (`atr≥1.0, rr≥2.0, risk%≤regime ceiling`) so most names carry an ATR fallback stop rather
   than a structural one. Risk-parameter question, PM's call, not changed unilaterally.
2. **weis book sign-off.** `aegis/canon/weis/canon.lock.yaml` has `pm_signed: null` and four
   open decisions D1–D4. The seat runs unsealed until signed.
3. **Close-location value** `(close−low)/(high−low)` — cheapest high-value field in the
   backlog. Unblocks weis R8 and also serves wyckoff, raschke, elder-lens.
4. **Impulse colour** — fast-EMA slope + MACD-Histogram slope + a three-state per-bar colour.
   Unblocks elder-lens R1/R2, the seat's primary trigger.
