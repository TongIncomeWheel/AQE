# M17 — Real-R Winner Fingerprint: Synthesis (the tradeable answer)

**Frozen spec `run_20260706u_m17`.** Re-measures the M16 winner fingerprint against the system's
**real structural risk unit** — R = entry(open t0+1) − `optimal_stop`, where `optimal_stop` is the
tightest structural candidate passing the live 3 gates (ATR≥1.0, R:R-TP2≥2.0, risk%≤regime ceiling).
**STEP 1 conformance: PASS 100%** (597/597 dsl_stop AND optimal_stop) vs the live code — the replay
imports and calls the actual live v2.1 functions (zero port drift; PM-ruled live-code reference).
Naive-R (1.5×ATR) and fixed-% shown only as reference. No stop-exit simulation. OOS 65/35, regime cut.

---

## Bottom line

Two decisive results, one tradeable and one sobering:

1. **The fingerprint is REAL in the units we trade.** Re-scored against structural R, the M15/M16
   rule (`base_days ≤ 15 AND ret_5d > 14.5% AND resist_score ≤ 8.5`) still pays: continuous
   `real_R_reached` **d = 0.32** (naive-R was 0.35 — barely shrank), **+2R/20d test lift +14.6 pp**,
   +3R/20d +8.6 pp, holds every regime. **It is not an ATR artifact — it survives the real ruler.**

2. **But 71% of the winning setups can't be bracketed.** Rule-positive names fail the live 3 gates
   **71.1% of the time** (vs 19.5% pond) — the strong-momentum pattern that "wins" is too *extended*
   to stop at acceptable risk. The tradeable rule-positive cohort collapses from 433 (naive) to
   **124 over 5.5 years (~22/year)**. **The deployable edge is far narrower than M16 implied.**

**The tradeable winner fingerprint:** a **squeeze / coiled setup that is bracketable** (structural
support within the regime risk ceiling), from a short base with clear overhead. Modest (~+3.5–5.6 pp
in R), small-N, **CANDIDATE** — forward-paper-track before sizing.

---

## 1. The fingerprint's real-R magnitude (the honest number)

| Outcome | rule+ (all, n=124) | base | lift | rule+ (test, n=43) | base | **OOS lift** |
|---|---|---|---|---|---|---|
| +2R/20d | 40.3% | 31.9% | +8.4 pp | 48.8% | 34.2% | **+14.6 pp** |
| +3R/20d | 28.2% | 18.0% | +10.2 pp | 30.2% | 21.6% | **+8.6 pp** |

Continuous `real_R_reached` **d = 0.32**; regime GREEN 40.4% / YELLOW 41.7% / ORANGE 33.3%. The
real-R base rates are lower than naive (real R is ~21% wider — median real_R $2.71 vs naive $2.19),
which makes the target harder, yet the rule's *lift* holds. **On the bracketable cohort, the edge is
genuine and, if anything, cleaner than naive-R suggested** (OOS n=43 — small, flag).

## 2. What survived the real ruler vs what was ATR artifact

- **Survived:** the rule's edge — driven by its **structural** components (short base + clear
  overhead). d 0.35 → 0.32. This is the genuine, ruler-independent signature.
- **Was ATR artifact (now vanished):** the **trajectory / momentum** component. On real R every 3–5
  day feature collapses to ~0 (ret_5d −0.01, ret_3d +0.01, ascending-ATR −0.05, all |d|<0.11).
  Momentum helped clear a *volatility-scaled* target; against a *structural* target it does nothing.
  M16 stripped fixed-% volatility; **M17 strips the residual ATR-scaling — and the momentum residual
  goes with it.** The durable winner signal is structure (short base, clear overhead, coil), not thrust.
- **Early-catch:** still null on real R (early 33% ≈ base; extended 34% ≈ base). Continuation, but
  the continuation "signal" was mostly the ATR echo — confirmed 4× now (M12/M13/M16/M17).

## 3. Bracketability — the critical design finding (§3)

| Cohort | no-valid-bracket rate |
|---|---|
| Pond (QUAL) | 19.5% |
| **Rule-positive (the "winner" setups)** | **71.1%** |

**The winner fingerprint systematically produces un-tradeable setups.** A name with strong 5-day
momentum has run far from its structural support, so its tightest valid stop exceeds the regime
risk-% ceiling — the live system would not bracket it. This is the single most important thing the
naive-R and fixed-% studies (Mover-Profile, M14, M15, M16) completely missed, because they never
measured against the real stop. **The pattern that wins is largely the pattern you can't put on.**

## 4. Sub-types on real R — squeeze is the deployable animal

| Sub-type | +2R/20d (all) | +2R/20d (test) | no-bracket % | Verdict |
|---|---|---|---|---|
| **squeeze** (coiled) | **35.4%** (+3.5) | **39.8%** (+5.6) | **14.3%** | ✅ best winner AND bracketable |
| tight-base | 32.4% (+0.5) | 34.3% (+0.1) | 11.5% | most bracketable, only base-rate winner |
| explosive (already igniting) | 31.4% (−0.5) | 31.0% (−3.2) | **36.7%** | weak winner AND least bracketable — avoid |
| trend | 28.4% (−3.5) | 31.0% (−3.2) | 15.8% | worst real-R winner |

**Squeeze is the intersection of "wins in real R" and "can actually be traded"** (+3.5/+5.6 pp both
splits, low 14.3% un-bracketable). The **explosive** archetype — champion on fixed-% (30%), already
demoted in M16 — is now doubly disqualified: weak real-R winner *and* 37% un-bracketable (the
extended-momentum names). The coil, not the thrust, is the tradeable winner.

## 5. CONFIRMED-REAL vs CANDIDATE

- **CONFIRMED-REAL** (survives fixed-% → naive-R → structural-R, OOS, regime): the winner edge is a
  **bracketable, short-base, clear-overhead, coiled (squeeze) structure**; d≈0.32 on the tradeable
  cohort; ~+3.5–5.6 pp in R for the squeeze sub-type.
- **CANDIDATE** (needs forward paper-track): single-regime 2020–2026, survivorship-tainted,
  in-sample; small tradeable N (~22 rule-positive/year, ~1,500 squeeze episodes). Real-R fixes the
  ruler, not the window.

## 6. Deploy recommendation

- **Deploy a modest, bracketability-GATED, squeeze-weighted runner-conviction tag** — flag a name
  only when it (a) is a squeeze/coiled setup, (b) has a valid bracket (passes the live 3 gates), and
  (c) fits short-base + clear-overhead. Weight it **small** — the edge is ~+3.5–5.6 pp in R, and the
  honest tradeable population is a few hundred episodes.
- **Do NOT chase the explosive / extended-momentum "winners"** — 37% are un-bracketable and, when
  bracketable, they underperform base in real R. The fixed-% "movers" were a volatility mirage; the
  extended ones are also a bracketability trap.
- **Forward paper-track on the real-R (optimal_stop) outcome** before any capital. The whole point of
  M17 was to measure in the units we trade — sizing waits on live confirmation of this number.

## 7. Reconciliation with the arc (merged)

fixed-% (Mover/M14/M15: d 0.85, rule 52%) → naive-R (M16: d 0.35, +7 pp) → **structural-R (M17: d
0.32, +8–15 pp, but 71% un-bracketable)**. Each ruler stripped a layer of volatility; the signature
that survived all three is **structure, not momentum** — short base, clear overhead, coil — and the
real ruler added the decisive constraint the others couldn't see: **bracketability.** M11/M13's
~0.13–0.24 single-feature floor stands; the conjunction lifts to ~0.32 on the tradeable cohort. This
is the program's final, real-ruler answer.

---

*Deliverables: this synthesis + `m17a_rule_realR.csv`, `m17b_trajectory_realR.csv`,
`m17b_position_split_realR.csv`, `m17c_subtype_realR.csv`, `m17_real_R_labels.parquet`.
Reproducible via `scripts/m17_step1_replay.py` (conformance-gated) + `m17_step3_hunts.py`.
Registry `run_20260706u_m17`. Halt at synthesis per spec — await PM review before deploy/size.*
