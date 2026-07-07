# AQE — Full Data Schematic (what ships to AIC per record)

**Purpose:** see everything AQE ships so we can cut noise. Auto-derived from the live
export (`_v21_record_fields` + the list builders + `field_schema`/`field_glossary`).
**Count today: 88 fields per record** across longlist / elder_list / held.

> **NOISE column:** ✂️ = strong cut candidate · ⚠️ = review · ✅ = keep (core).

---

## 1. Identity & rank (7)
| Field | Keep? | Note |
|---|---|---|
| `ticker`, `rank`, `source`, `pe`, `on_longlist` | ✅ | identity + list membership |
| `floor` | ⚠️ | min engine sub-score; do we read it? |
| `rank_explain` | ✅ | 1-line ranking rationale |

## 2. Engine scores (13)
| Field | Keep? | Note |
|---|---|---|
| `sc_momentum`, `sc_momentum_raw`, `ptrs`, `pipe_rank` | ✅ | the headline composites |
| `flow`, `energy`, `structure`, `mp`, `elder` | ✅ | the 5 engine reads |
| `mp_state`, `elder_5d`, `elder_pattern`, `elder_context` | ✅ | momentum/impulse context |

## 3. THE BRACKET (nested — 14 sub-fields) ✅ core
`price · price_source · stop · stop_type · stop_atr_dist · risk · risk_pct ·
targets[] · rr · rr_tp1 · rr_tp2 · rr_tp3 · valid · invalid_reason`
each `targets[]` = `{type, tp (TP1/2/3), price, r, atr_dist}`. **This is the operative
stop/target set** — keep all.

## 4. Structural level anchors (11)
| Field | Keep? | Note |
|---|---|---|
| `atr_14d` | ✅ | volatility unit |
| `fib_swing_low/high`, `fib_236/382/500/618/786` | ⚠️ | the bracket already picks the fib it uses (`stop_type`). Do we still need the full flat fib ladder on every record, or only when the stop/target IS a fib? Candidate to slim. |
| `ma_20/50/100/200` | ⚠️ | same — the alert engine uses them; AIC may not need all four raw. |

## 5. Beta / volatility (6)
| Field | Keep? | Note |
|---|---|---|
| `beta_30d`, `beta_60d` | ✅ | the two β windows |
| `beta_252d`, `vol_30d_ann` | ⚠️ | 1-yr β + annualised vol — used? |
| `beta_60d_capped`, `beta_data_error` | ✂️ | internal cleanup flags — not AIC-facing |

## 6. Sector & thematic (16)
| Field | Keep? | Note |
|---|---|---|
| `gics_sector`, `gics_sector_name`, `gics_gate` | ✅ | sector + the gate |
| `sector_trend_state`, `sector_rrg_quadrant`, `sector_rrg_direction` | ✅ | **NEW — the day's sector rotation direction (your request)** |
| `thematic_basket`, `thematic_grade`, `thematic_parent_gics`, `thematic_parent_grade` | ✅ | primary basket |
| `thematic_rrg_quadrant`, `thematic_rrg_direction` | ✅ | **NEW — thematic rotation direction (your request)** |
| `thematic_baskets` | ⚠️ | the full multi-basket list — keep or just the primary? |
| `sector_corr`, `sector_corr_class` | ⚠️ | 60d corr vs parent ETF |
| `sector_corr_flag` | ✂️ | **exact alias of `sector_corr_class`** — redundant |

## 7. Signal Radar / ledger (7) ✅ core
`runner_setup · runner_conviction · runner_conviction_label · mover_subtype ·
premove_setup · premove_conviction · premove_conviction_label` — the detection tags.

## 8. Readiness / Health — decision framework applied
**DETECT → ENTER → HOLD** (now in `field_glossary._decision_framework`). Each stage
answers a different question, so there's no "picking at random":
- **DETECT** (is a move brewing?) = Signal Radar (`runner_setup` / `premove_setup`)
- **ENTER** (buy, and where?) = the `bracket` + the live alert engine (buy/breakout/near-stop)
- **HOLD** (should an open position stay on?) = Health (`hl_score`/`hl_state`)

| Field | Keep? | Note |
|---|---|---|
| `rd_score`, `rd_state`, `rd_compression`, `rd_trigger`, `rd_pos_mod`, `rd_rs_bonus` | ✂️ **CUT from feed** | Readiness overlapped `premove_setup` + the alert levels (DETECT + ENTER already cover entry timing). **Engine kept + still persisted to `scores_daily`** — just hidden from the AIC feed. |
| `hl_score`, `hl_state` | ✅ **held_positions ONLY** | Health = the HOLD decision; only meaningful once you're in a trade. Stripped off the daily list. |
| `hl_trend`, `hl_flow`, `hl_rs`, `hl_risk` | ✂️ | the 4 sub-scores dropped everywhere (AIC reads the composite + state). |

## 9. Enrichment flags (12)
| Field | Keep? | Note |
|---|---|---|
| `setup_state`, `rs_leadership`, `rs_down_day_20d` | ⚠️ | context signals — used? |
| `breakout_conviction`, `breakout_grade`, `breakout_pattern`, `breakout_bar_date` | ⚠️ | breakout enrichment — 4 fields, overlaps Signal Radar? |
| `atr_caution`, `malformed_bracket` | ⚠️ | quality flags |
| `dsl_atr_ratio_floored` | ✂️🔴 | **DEAD — references the retired `dsl_atr_ratio`. Remove.** |

## 10. Misc (4)
| Field | Keep? | Note |
|---|---|---|
| `rvol`, `rs_spy_20d`, `sma_distance_pct` | ✅ | vol / RS / MA distance |
| `held` | ✅ | held flag |

---

## Quick-win noise cuts (my recommendation)
Immediate ✂️ (dead / pure-alias / internal): **`dsl_atr_ratio_floored`** (dead),
**`sector_corr_flag`** (alias), **`beta_60d_capped` + `beta_data_error`** (internal flags).
Then a decision on the **8 rd_/hl_ sub-scores** (keep composite+state only?) and the
**flat fib/MA ladders** (slim to what the bracket actually uses). That alone takes 88 → ~72,
and the rd/hl + fib/MA calls take it under ~60.

**Tell me which groups to cut and I'll do it in one pass.**

---

## The daily-list collapse (your request: one list, ledger↔watchlist correspondence)

**Today:** three separate structures — `longlist` (the watchlist/screen), `elder_list`,
and the standalone `signal_radar` block. **Proposed collapse → one `daily_list`**, every
row flagged so AIC reads membership + correspondence in one place:

```jsonc
"daily_list": [
  { "ticker": "APP",
    "on_watchlist": true,      // = passed the longlist screen (SC_MOM/PTRS/Elder)
    "on_elder": true,          // Elder ≥ 8
    "runner_setup": true,      // signal ledger — continuation
    "premove_setup": false,    // signal ledger — pre-move
    "runner_conviction_label": "HIGH (3/4)",
    "in_ledger": true,         // = runner_setup OR premove_setup
    "sc_momentum": 88, "ptrs": 64, "bracket": {…}, …   // full record
  },
  { "ticker": "SNDK",
    "on_watchlist": false, "on_elder": false,          // NOT on the watchlist…
    "premove_setup": true, "in_ledger": true,          // …a fresh signal-ledger pre-mover
    "premove_conviction_label": "MODERATE (2/4)", … }
]
```

- **Union** of the watchlist (longlist) ∪ elder ∪ signal-ledger names, de-duped by ticker.
- Each row's flags answer *"is this on the watchlist? in the ledger? both?"* — the
  correspondence you asked for, in one list.
- `summary` keeps the counts (`watchlist_count`, `ledger_count`, `both`, `elder_count`).

This is a schema change (consumers currently read `longlist`/`elder_list`), so it's the one
piece I want your ✅ before I collapse — additive first (add `daily_list`, keep the old keys
one cycle) or hard cut. **Say which and I'll build it.**
