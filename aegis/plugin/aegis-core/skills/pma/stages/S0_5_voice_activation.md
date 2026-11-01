# S0.5 · VOICE + DATA ACTIVATION GATE

**Runs after S0 PREFLIGHT and BEFORE S2 packets. Deterministic — no model, no judgment.**

**Standing rule (PM, 2026-08-24): the voice and its data must BOTH work, or the run is
wasting time.** This stage is what enforces that, and it ends in a binary.

```
python3 aegis/skills/premarket-analysis/tools/voice_preflight.py \
  --export aegis/output/aqe_daily_export.json \
  --menus  aegis/skills/premarket-analysis/contracts/voice_menus.json \
  --canon  aegis/canon \
  --agents-dir ~/.claude/plugins/synced/aegis-voices/agents \
  --out    data/pma/<date>/activation.json --strict
```

Exit `0` ready · `1` a voice is NOT ACTIVATED · `2` quorum failed, STOP · `3` a voice is
BLOCKED on data.

---

## Why this stage exists

A seat can return fluent, confident, correctly-formatted output while half its method is
unexecutable — because nothing ever checked that the fields its canon requires are (a) on its
menu and (b) populated in today's export. The seat then silently substitutes proxies, and the
committee counts its vote as if the method had run. That is the **ghost voice**: present in the
tally, absent in the analysis.

Three artefacts already exist and were never reconciled with each other:

| Layer | File | Says |
|---|---|---|
| CANON | `aegis/canon/<seat>/canon.lock.yaml` | which **fields** each recogniser needs (`recognisers[].fields`) |
| MENU | `contracts/voice_menus.json` | which fields the seat is actually **served** |
| EXPORT | `aegis/output/aqe_daily_export.json` | which fields **exist and are populated** today |

**S0.5 reads all three and reconciles them before the swarm spawns.**

---

## Two questions. Never mixed.

**1. CAN THIS VOICE RUN?** → **ACTIVATED** / **NOT ACTIVATED**

Needs exactly two things: its agent file `voice-<seat>.md` installed in the aegis-voices
plugin, and its book `aegis/canon/<seat>/canon.lock.yaml` present and parseable. Nothing else
stops a voice speaking. A NOT ACTIVATED seat does not spawn and does not count toward quorum.

**2. CAN IT RUN ITS METHOD ON TODAY'S DATA?** → **READY** / **SERVED** / **BLOCKED**

Mixing these two is what produced ghost voices. A seat can be fully ACTIVATED and still be
missing numbers; that is a data problem with a data owner, not a reason to silence the seat.

The old vocabulary — DEGRADED, BENCHED, "capability %" — is retired. One word covering both
questions is precisely what let half-served seats vote as if their method had run.

---

## Every missing number resolves to an action

Reporting "n numbers missing" is not a fix. The tool classifies each gap into exactly one of
four outcomes and prints the action that closes it.

| Outcome | Means | Action | Blocks? |
|---|---|---|---|
| `DERIVED` | The value is fully determined by fields that ARE populated. It is a missing **label**, not missing information. | Orchestrator computes it at packet build (`tools/field_derive.py`) and tags it `<field>_source: "derived"` so the seat can see it was labelled, not measured. | No |
| `SUBSTITUTE_LIVE` | A populated fallback carries the same information and is already on this seat's menu. | Packet serves the fallback under a labelled column; the seat declares the substitution in `notes`. | No |
| `MENU_BUG` | The fallback is populated but is **not** on this seat's menu, so the seat is blind to data sitting right there. | Add one field name to `voice_menus.json`. One-line fix. | **Yes** |
| `ENGINE_TICKET` | Nothing anywhere in the export carries it. | The engine must emit it. PM ruling if it is a risk parameter. | **Yes** |

Nulls that are a **real state** are not gaps and are never counted: no thematic basket, no
pattern detected, no 200-day average on a young listing, `invalid_reason` null when the bracket
IS valid, no extension reading.

---

## The `bracket.stop_type` case — worked, because it is the pattern

`bracket.stop_type` is null on **157 of 200 rows (78%)**. Read naively that is a fleet-wide
data gap blocking six seats. It is not a gap at all.

On every one of those 157 rows, `bracket.valid` is `false`, and `bracket.atr_fallback_stop` is
populated on **100%** of rows. So the stop the seat will actually trade off is right there. The
engine simply never wrote down what kind of stop it is.

That is a labelling gap, and the orchestrator closes it today without an engine release:
`field_derive.py` writes `stop_type = "atr_fallback"` plus `stop_type_source = "derived"`, and
also emits `bracket.stop_eff` — the stop actually in force, structural if the bracket passed
its gates, else the fallback.

**What `field_derive.py` is allowed to do.** Labels, states and flags only — never a price, a
level or a score. Deterministic, inputs populated on ~100% of rows, always tagged
`_source: derived`. If a derivation would produce a number a seat trades on, it is an
`ENGINE_TICKET`, not a derivation.

---

## G4 — the fabrication surface, closed

`EXTERNAL_SOURCE_SEATS` lists seats whose canon needs information the AQE export does not
carry. Today that is **lynch** (fundamentals: P/E, growth, balance sheet, payout, next-earnings).

**Standing rule, from two consecutive failures.** On 2026-08-20 and again on 2026-08-21 the
lynch seat returned a complete, confident 20-name fundamentals memo with **`tool_uses == 0`**.
Both times the orchestrator's spot-check against live FMP disproved it — 08-21 examples: CMCSA
P/E claimed 7.22 vs actual 8.58, payout claimed 30% vs actual 43.4%; LLY P/E 51.28 vs 41.73;
BRZE next-earnings 09-04 vs actual 09-08; KMX 09-25 vs 09-29. Digit-pair clustering
(.11/.22/.41/.44) across the memo. Both memos were discarded.

**The fix is not a better instruction. It is removing the fetch from the seat.**

1. The **orchestrator** fetches fundamentals (FMP `metrics-ratios-ttm`,
   `calendar/earnings-company`) for the deliberation set and inlines the verified block.
2. Lynch is spawned with **`tools: []`** and told the figures are pre-verified and must be used
   as given — its job is the six-category judgment, not the retrieval.
3. If a seat is ever spawned with retrieval duty anyway, the orchestrator **must** record
   `tool_uses` and spot-check ≥2 figures against live source before the memo joins any packet.
   `tool_uses == 0` on a retrieval seat is an automatic discard, declared in the report header.

---

## Findings and their status

| Finding | Status |
|---|---|
| `raschke/canon.lock.yaml` would not parse — one unescaped apostrophe in C7 (`the seat's` inside a single-quoted scalar). The seat had **no machine-readable canon at all**, so R1–R10 including R6's hard `bracket.valid` reject were invisible to every tool. | **FIXED** — `seat''s`, pushed 2026-08-24 |
| `weis` had **no `canon.lock.yaml` and no installed agent**. Running since 2026-08-17 as an unsealed `general-purpose` spawn with its canon hand-inlined every run — unversioned, unauditable, different each time. | **FIXED** — lock scaffolded + `agents/voice-weis.md` shipped in aegis-voices 1.2.0. Lock is `pm_signed: null` pending D1–D4. |
| `bracket.stop_type` null on 78% of rows, reading as a blocker for six seats. | **FIXED** — `DERIVED`, see above. Not an engine ask. |
| `elder-lens`: **6 of 12 recognisers `NOT_AVAILABLE`** at canon build. R1/R2 are the Impulse-colour rules — the seat's *primary* trigger. Neither can fire: no fast-EMA slope, no MACD-Histogram slope, no per-bar colour field. | **OPEN — engine ask #3** |
| `bracket.stop` structural on only 22% of rows: 76% fail the three gates (`atr≥1.0, rr≥2.0, risk%≤regime ceiling`), 2.5% have no resistance above price. Every bracket-reading seat carries an FB stop roughly four times in five. | **OPEN — PM decision, engine ask #1** |
| `lynch` needs served fundamentals. | **FIXED** — orchestrator-served, G4 above |

**Retracted — these were bugs in this tool, not gaps in the data.** The first version of this
file reported *"thorp at 70% capability, `sc_m_gate_detail` populated on 0% of rows"* and
*"`lens` MISSING"*. Both wrong. `sc_m_gate_detail` is a dict of five booleans populated on
**88%** of rows and `lens` is a populated dict on **100%** — the flattener was not counting
dict containers as present in their own right. Fixed in `flatten()`. Recorded here because a
false data gap costs the desk exactly as much as a real one.

**Status against the live export, 2026-08-24: 11/11 voting seats ACTIVATED, zero blockers,
READY TO RUN: YES.**

---

## Engine asks this stage generates, ranked

1. **`bracket` gate calibration (PM decision, highest leverage).** 76% of the universe returns
   no structural bracket. Either the three gates are mis-calibrated for this regime, or the
   export should emit a second, looser bracket tier alongside the strict one. **Not changed
   unilaterally — it is a risk-parameter question and it is the PM's call.**
2. **Close-location value `(close−low)/(high−low)`.** Cheapest high-value field in the backlog.
   Unblocks weis R8 (upthrust confirmation — Weis's single most-used primitive) and also serves
   wyckoff, raschke and elder-lens.
3. **Impulse colour** — fast-EMA slope + MACD-Histogram slope + a three-state per-bar colour,
   plus one bar of history. Unblocks elder-lens R1/R2, the seat's actual primary trigger. The
   `elder` 0–10 score cannot substitute: a mid-range value cannot say which component fell.
4. **Field stability.** An intermittent field is worse than an absent one, because it makes
   capability non-reproducible between runs. Any field that appears one session and not the
   next gets a ticket, not a shrug.

---

## Round-2 packets must be menu-sliced too

**Defect found in the 2026-08-21 run and fixed here.** Round-1 packets are menu-sliced by
`pma_pipeline.py packets` (correct). The Round-2 deliberation packet was **hand-assembled prose**
and carried no seat menus at all. Consequence: `elder-lens` voted on all 20 names without
`elder`, `elder_5d` or `elder_pattern` — its entire 6-field menu minus two — and correctly
declared *"DATA GAP: my primary trigger is unobservable, so I voted on mp/mp_state only and
capped every SUPPORT at 3."* That was an **orchestrator defect, not a seat failure**, and it
silently capped a seat's whole ballot.

**Rule: every Round-2 packet carries each seat's own menu row for every deliberation-set name,
sliced by the same tool that builds Round 1.** Challenge documents and Round-1 reasons are
*additional* context, never a replacement for the seat's fields.

---

## Report contract

`activation.json` carries a `markdown` field. **§0 of the brief renders it verbatim, above the
macro section, before any nomination exists.** Never hand-typed. A run whose header does not
carry the activation table has not passed S0.5.

The S7Q quality gate adds **Q0A**: `activation.json` exists for this run, every seat that
returned output has status `ACTIVATED`, `roster.ready_to_run` is true (or the exception is
declared in the header with the PM's reason), and the header table is the tool's own `markdown`.
