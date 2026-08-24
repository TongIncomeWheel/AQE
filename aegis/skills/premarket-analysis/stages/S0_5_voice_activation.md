# S0.5 · VOICE ACTIVATION GATE

**Runs after S0 PREFLIGHT and BEFORE S2 packets. Deterministic — no model, no judgment.**
Tool: `aegis/skills/premarket-analysis/tools/voice_preflight.py` → `data/pma/<date>/activation.json`

```
python3 voice_preflight.py \
  --export aqe_daily_export.json \
  --menus  contracts/voice_menus.json \
  --canon  aegis/canon \
  --agents-dir ~/.claude/plugins/synced/aegis-voices/agents \
  --out    data/pma/<date>/activation.json
```

Exit 0 = run. Exit 1 = a seat is benched (with `--fail-on-benched`). Exit 2 = quorum failed, STOP.

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

The canon build already marks unexecutable rules `NOT_AVAILABLE` with `fields: []`. Nobody read
them at run time. **S0.5 reads all three and reconciles them before the swarm spawns.**

---

## The four gates

| Gate | Checks | FAIL ⇒ |
|---|---|---|
| **G1 AGENT** | an installed agent `voice-<seat>` exists | BENCHED |
| **G2 CANON** | `canon.lock.yaml` exists, **parses**, and is `pm_signed` | missing/unparseable ⇒ BENCHED; unsigned ⇒ DEGRADED |
| **G3 MENU** | every menu field exists in the export and is populated ≥ `--min-coverage` (default 50%) | <50% of menu live ⇒ BENCHED; <80% ⇒ DEGRADED |
| **G4 SOURCE** | seats needing data the export does not carry must be **SERVED by the orchestrator** | self-fetch ⇒ DEGRADED + mandatory tool-use audit |

**Verdicts**
- **LIVE** — all gates pass, every recogniser can fire. Spawn normally.
- **DEGRADED** — spawns, but the prompt **must name the dead recognisers and sparse fields** so the
  seat declares up front instead of quietly proxying. Its `notes` must echo the declaration.
- **BENCHED** — does **not** spawn, does **not** count toward quorum. Fix the block or run short.

Quorum floor stays 8 of 11 voting seats and is computed on **available** seats, not nominal ones.

---

## G4 — the fabrication surface, closed

`EXTERNAL_SOURCE_SEATS` in the tool lists seats whose canon needs information the AQE export does
not carry. Today that is **lynch** (fundamentals: P/E, growth, balance sheet, payout, next-earnings).

**Standing rule, from two consecutive failures.** On 2026-08-20 and again on 2026-08-21 the lynch
seat returned a complete, confident 20-name fundamentals memo with **`tool_uses == 0`**. Both times
the orchestrator's spot-check against live FMP disproved it — 08-21 examples: CMCSA P/E claimed
7.22 vs actual 8.58, payout claimed 30% vs actual 43.4%; LLY P/E claimed 51.28 vs actual 41.73;
BRZE next-earnings claimed 09-04 vs actual 09-08; KMX claimed 09-25 vs actual 09-29. Digit-pair
clustering (.11/.22/.41/.44) across the memo. Both memos were discarded.

**The fix is not a better instruction. It is removing the fetch from the seat.**

1. The **orchestrator** fetches fundamentals (FMP `metrics-ratios-ttm`, `calendar/earnings-company`)
   for the deliberation set, and inlines the verified block into lynch's prompt.
2. Lynch is spawned with **`tools: []`** and told the figures are pre-verified and must be used as
   given — its job is the six-category judgment, not the retrieval.
3. If a seat is ever spawned with retrieval duty anyway, the orchestrator **must** record
   `tool_uses` and spot-check ≥2 figures against live source before the memo joins any packet.
   `tool_uses == 0` on a retrieval seat is an automatic discard, declared in the report header.

---

## What this found on first run (2026-08-24, against the 08-22 export)

| Finding | Severity | Status |
|---|---|---|
| `raschke/canon.lock.yaml` would not parse — a single unescaped apostrophe in C7 (`the seat's` inside a single-quoted scalar). The seat had **no machine-readable canon at all**. | BENCHING | **FIXED** — `seat''s` |
| `weis` had **no `canon.lock.yaml` and no installed agent**. Running since 2026-08-17 as an unsealed `general-purpose` spawn with canon hand-inlined by the orchestrator every run — unversioned, unauditable, and different each time. | BENCHING | **FIXED** — lock scaffolded (`pm_signed: null`, 4 open PM decisions) + `AGENT_voice-weis.md` written; needs plugin install + PM sign-off |
| `elder-lens`: **6 of 12 recognisers `NOT_AVAILABLE`** at canon build. R1/R2 are the Impulse-colour rules — the seat's *primary* trigger (a red bar giving way is its buy-permission event). Neither can fire: no fast-EMA slope, no MACD-Histogram slope, no per-bar colour field. The seat has been voting on `mp_state` alone. | DEGRADE | declared; engine ask below |
| `bracket.*` populated on only **22%** of rows — 76% fail the 3 gates (`atr≥1.0, rr≥2.0, risk%≤regime ceiling`), 2.5% have no resistance above price. **Degrades 11 of 14 seats.** Every bracket-reading seat falls back to `atr_fallback_stop` ~4 times in 5. | DEGRADE (fleet-wide) | **PM decision — see below** |
| `thorp` at **70% capability** — worst in the fleet. `sc_m_gate_detail` populated on **0%** of rows on the 08-22 export (it was populated on 08-21). Thorp's five momentum gates are its ranking spine. | DEGRADE | intermittent; engine ask |
| `lynch` needs served fundamentals (G4). | DEGRADE | orchestrator-served from now on |

**Roster after fixes: 11/11 voting seats available, 0 benched, 1 LIVE, 12 DEGRADED.**

That "1 LIVE" is the honest headline. The committee has been reporting 11 confident seats while
running, on average, at ~89% of method — and two seats were structurally incapable of speaking
with their own canon at all.

---

## Engine asks this stage generates, ranked

1. **`bracket.*` gate calibration (PM decision, highest leverage).** 76% of the universe returns no
   structural bracket. Either the three gates are mis-calibrated for this regime, or the export
   should emit a second, looser bracket tier alongside the strict one. This single item degrades
   11 of 14 seats and forces most ADVANCE names to carry FB stops. **Not changed unilaterally —
   it is a risk-parameter question and it is the PM's call.**
2. **Close-location value `(close−low)/(high−low)`.** Cheapest high-value field in the backlog.
   Unblocks weis R8 (upthrust confirmation — Weis's single most-used primitive) and also serves
   wyckoff, raschke and elder-lens.
3. **Impulse colour** — fast-EMA slope + MACD-Histogram slope + a three-state per-bar colour, plus
   one bar of history. Unblocks elder-lens R1/R2, i.e. the seat's actual primary trigger. The
   `elder` 0–10 score cannot substitute: a mid-range value cannot say which component fell.
4. **`sc_m_gate_detail` stability** — present 08-21, absent 08-22. Intermittent fields are worse
   than absent ones because they make capability non-reproducible between runs.

---

## Round-2 packets must be menu-sliced too

**Defect found in the 2026-08-21 run and fixed here.** Round-1 packets are menu-sliced by
`pma_pipeline.py packets` (correct). The Round-2 deliberation packet was **hand-assembled prose**
and carried no seat menus at all. Consequence: `elder-lens` voted on all 20 names without
`elder`, `elder_5d` or `elder_pattern` — its entire 6-field menu minus two — and correctly
declared *"DATA GAP: my primary trigger is unobservable, so I voted on mp/mp_state only and capped
every SUPPORT at 3."* That was an **orchestrator defect, not a seat failure**, and it silently
capped a seat's whole ballot.

**Rule: every Round-2 packet carries each seat's own menu row for every deliberation-set name,
sliced by the same tool that builds Round 1.** Challenge documents and Round-1 reasons are
*additional* context, never a replacement for the seat's fields.

---

## Report contract

`activation.json` carries a `markdown` field. **§0 of the brief renders it verbatim, above the
macro section, before any nomination exists.** Never hand-typed. A run whose header does not
carry the activation table has not passed S0.5.

The S7Q quality gate adds **Q0A**: `activation.json` exists for this run, every seat that returned
output has verdict ≠ BENCHED, and the header table is the tool's own `markdown`.
