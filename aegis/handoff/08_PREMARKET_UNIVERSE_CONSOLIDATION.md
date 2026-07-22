# Premarket Universe → AQE → Lens → Alert-Universe — Consolidation Spec

**Status:** LOCKED design (PM sign-off 2026-07-22). Anti-spaghetti: this RETIRES and
SINGLE-SOURCES existing pieces. It builds nothing new except one shared lane module that
replaces two duplicated copies.

**PM decisions that set this scope:**
1. *Alert universe* = "the same view as the daily deliberation list (data + detect)."
   One data+detect object feeds both. (Q1)
2. *Universe build* = one AQE-sourced builder. FMP already feeds AQE upstream; the kernel's
   second FMP screen is redundant. (Q2 — PM: "if we're relying on AQE, doesn't it rely on
   FMP pull + AQE engines?" — yes, exactly, so we don't pull FMP twice.)
3. *AQE JSON trim* = both sides — kernel-side de-dup now + a slim-emit spec for the AQE engine. (Q3)

---

## The one-line truth the current design obscures

`FMP  →  AQE engine (external box)  →  aqe_daily_export.json  →  kernel`

The AQE export is ALREADY the fully-scored universe. There is no separate "build universe,
then run AQE" — it is one artifact. Every kernel screen/derivation is downstream *shaping*
of that one file. The mess is that the kernel pretends otherwise in three places.

---

## Lane 1 — UNIVERSE BUILD (single source)

**Now (broken):** `skills/premarket/SKILL.md` step 2 calls `tools/universe_screen.py` (a
second FMP screen). It is **dead in the scheduled container** (no `FMP_API_KEY`), so the live
`universe.json` is hand-assembled from the AQE export ad hoc → **3 incompatible shapes in 3
days**; `near_misses` silently lost; `contracts/universe.schema.json` too loose to catch it.

**Target:**
- **Retire** `tools/universe_screen.py` from the premarket path (keep the file, mark DEPRECATED —
  it is a valid standalone FMP screen, just not the production universe source).
- **New owning builder** `tools/universe_build.py` (single responsibility): read
  `output/aqe_daily_export.json`, emit `data/sod/DATE/universe.json` in **one fixed shape**
  (top-level `date, source, count, names[], near_misses[]`; each name = the AQE record,
  trimmed per Lane 4). Near-misses come from AQE's own just-below-floor band (documented),
  not a second FMP EMA screen.
- **Tighten** `contracts/universe.schema.json`: require `date, source, count, names[]` and,
  per name, the consumed field set (Lane 4). Reject the drifted shapes.
- SKILL step 2 rewrites to: "build the universe from today's AQE export via
  `tools/universe_build.py` (the AQE export IS the scored universe, D-66; FMP feeds AQE upstream —
  the kernel does not re-screen FMP)."

## Lane 2 — ONE DATA+DETECT VIEW (dedupe the two lane functions)

**Now (broken):** `alert_universe.lanes_for` and `conviction_funnel._lane_count` re-implement
the identical 8-lane logic in two files; neither reads `parameters.yaml` (config is ignored,
only CLI flags apply).

**Target:**
- **New shared module** `tools/lanes.py`: the single definition of the 8 detection lanes
  (`sc_m_gates, choch BULLISH, knn_significant, detect≥N, rs LEADER, structure≥N, flow≥N,
  mp not DECEL`) + a `load_params()` that reads `charter/parameters.yaml`. One source of truth
  for the lane logic AND the thresholds.
- `alert_universe.py` and `conviction_funnel.py` both import `tools/lanes.py`. Delete the two
  local copies. Both now actually honour `parameters.yaml` (fixes the "PM tunes but nothing
  changes" bug).
- **Conceptual model made explicit:** the data+detect view is ONE object.
  - *Deliberation shortlist* = data+detect view **+ consensus overlay** (voices advisory, D-80).
    Produced by `conviction_funnel.py`. Landing: `data/sod/DATE/conviction_funnel.json`.
  - *Alert universe* = the **same** data+detect view, **tiered by lane depth**, no consensus
    axis (intraday has no votes). Produced by `alert_universe.py`. Same lanes, same floor,
    same thresholds — guaranteed by the shared module.

## Lane 3 — LANDING + WIRING (one canonical artifact, actually wired)

**Now (broken):** `alert_universe.py` is **orphaned — no skill calls it**; the only file on
disk is a hand-made `alert_universe_castingmat.json` nothing reads. Premarket step 11 still
says "all voice top-10s + held book" (the pre-D-77 hand-pick D-77 retired). Intraday actually
consumes AQE's `inbox.jsonl` at a *different* floor (65 vs 70).

**Target:**
- **Wire** `alert_universe.py` into `skills/premarket/SKILL.md` at plan-assembly: after the
  committee, build the alert universe from the approved/deliberated set's underlying AQE
  records and **write one artifact**: `data/alerts/DATE/alert_universe.json` (retire the
  `_castingmat` hand-name).
- **Retire** the step-11 "voice top-10s + held book" language → "the intraday alert universe
  is the data+detect view (`alert_universe.json`) + the held book; it is the same mechanical
  set the deliberation list was built from."
- **Scope AQE's intraday `inbox.jsonl` to that membership** and **align the floor to 70**
  (`alert_inbox.py` `STRONG_UNIVERSE_FLOOR 65 → 70`, or gate the inbox sweep to the
  `alert_universe.json` ticker set). One floor, one set, one landing.
- `skills/market_hours/SKILL.md` step 1: read `data/alerts/DATE/alert_universe.json` as the
  authoritative membership; `inbox.jsonl` is the *event stream on that set*, not a separate
  definition.

## Lane 4 — AQE OUTPUT JSON (both sides)

**Now (broken):** export = 97 fields/name + ~42 KB/day of self-describing blocks no code reads;
`universe.json` byte-duplicates the export; 11 per-voice copies (~540 KB); `subcomponents`
ships empty `{}` though voice cards point at it.

**Target — KERNEL side (in-repo, safe, now):**
- `universe_build.py` trims each name to the **consumed field set** (the ~40 code-read fields +
  the D-53 voice-menu fields). Never copy the whole 97-field record.
- **Drop the 11 `universe_<voice>.json` files.** Hand each voice the one `universe.json` + its
  menu key-list (menu lives in `charter/` once, not baked 11×). Removes 11 files + ~540 KB/day.
- Prune the never-consumed fields (the ~30 in the audit) from what the kernel persists.

**Target — CONTRACT side:**
- Tighten `contracts/aqe_export.schema.json` to the consumed set; move self-describing blocks
  (`field_schema, field_schema_enums, field_glossary`) to `additionalProperties: allowed but
  not required` and OUT of the daily payload expectation.

**Target — AQE ENGINE spec (external, for the AQE engineer):**
- Stop emitting `field_schema, field_schema_enums, field_glossary, thematic_baskets (top-level),
  data_quality` in the daily export (they duplicate repo docs; ~42 KB/day, zero readers).
- Prune the ~30 never-consumed `daily_list` fields OR move them into `subcomponents`.
- **Populate `subcomponents`** (currently `{}`) with the sub-scores the voice taxonomy cards
  require (`ext_score, accum_score, base_score, squeeze_score, k39, …`) — the one real
  *consumption gap*, not just noise.
- Reconcile field NAMES to the live schema (`rs_vs_spy`→`rs_spy_20d`, etc.).

---

## What is explicitly NOT changing (guardrails)
- Voice isolation, committee doctrine, the D-80 selection doctrine (data leads · lens seconds ·
  voices corroborate) — unchanged; we are only removing duplicate machinery beneath it.
- No order path touched (constitution law 1).
- `universe_screen.py` kept on disk (deprecated), not deleted — it is a working FMP screen.

## Acceptance
- One `universe.json` shape, schema-enforced, from one builder.
- One `tools/lanes.py`; zero duplicated lane logic; both tools honour `parameters.yaml`.
- `alert_universe.json` written by a skill and read by market-hours; one floor (70) everywhere.
- Export/universe field count materially down; `subcomponents` populated (or carded-out).
- All tool selftests pass; end-to-end on 2026-07-21 SOD data produces valid
  universe → deliberation shortlist → alert universe.
