# M16 — Winner Fingerprint: Synthesis

**Assembled from three independent hunts** (`m16a` rule-in-R, `m16b` trajectory, `m16c` sub-types),
each verdict written before this synthesis read it. Outcome in **R** (risk = 1.5×ATR14 at signal),
open(t0+1), no stop. QUAL pond N=7,040, OOS 65/35, single-version v1.8.0. R base rates +2R/20d 39.2%,
+3R/20d 22.5% (match M11 — clean).

---

## THE WINNER FINGERPRINT (plain committee English)

> **A risk-adjusted winner is a name breaking from a SHORT, YOUNG BASE, on a STRONG 3–5 DAY
> MOMENTUM THRUST, with CLEAR OVERHEAD above it — ideally out of a COILED / SQUEEZE structure, and
> already in motion (not pre-breakout). Add relative strength and a readiness trigger and the
> signature sharpens.**

This is the first fingerprint in the program that is stated in R, survives out-of-sample, holds in
every regime, and beats the single-feature floor — because it is a **conjunction**, not one feature.

## What it delivers (in R, out-of-sample)

| Signature | +2R/20d winner rate | +3R/20d runner rate | Effect size |
|---|---|---|---|
| Pond base | 39.2% (test 42.4%) | 22.5% (test 27.3%) | — |
| **Rule: short base + 5d thrust + clear overhead** | **49.4% test (+7 pp)** | **36.0% test (+8.7 pp)** | continuous d **0.35** |
| …within the **squeeze / coiled** sub-type | +1.9 pp OOS (most consistent) | — | mild tilt |

**The runner (+3R) is where it pays most** — the rule catches big R-winners at 36% vs 27% base OOS
(1.3×), 35% vs 22.5% all (1.55×). Regime-robust (GREEN/YELLOW/ORANGE all elevated).

## CONFIRMED (survives R + OOS + regime)

1. **The short-base × 5-day-momentum × clear-overhead conjunction pays in R** — +7 pp (+2R) / +8.7 pp
   (+3R) OOS, continuous d 0.35, all regimes. Modest but real, above the ~0.13–0.24 floor.
2. **Winners are momentum-and-strength from a short base** — the surviving trajectory component is
   short-window momentum (ret_3d/5d, ~0.10 OOS); within the rule, winners add relative strength
   (rs_vs_spy, pr_ret_12m) and a readiness trigger.
3. **The squeeze / coiled sub-type is the best risk-adjusted winner** (only one above base in both
   splits; strong in ORANGE). Trend is a secondary OOS-only candidate.

## NULL / CANDIDATE (does NOT survive the R discipline)

1. **Early-catch is null in R.** The "expanding-from-low, room-above" configuration (M14 Cluster 2)
   wins at/below base in R (early group −4.1 pp OOS). Winners are **continuation** — recognised while
   already moving, not before. **Confirms M12**; the trajectory frame does not rescue early detection.
2. **Ascending ATR / volume expansion is a volatility echo.** Strong on fixed-% (M14 d 0.25–0.33),
   it collapses to ~0.01 OOS in R. It marks *movers* (fixed-%), not *winners* (R).
3. **The "explosive / already-igniting" archetype — the fixed-% champion (30% on +20%) — is not a
   risk-adjusted winner** (at/below base in R). Its dominance was volatility. **tight-base**
   underperforms in R too.

## Reconciliation with M11 / M13 — consistent, and it lifts above the floor

M11 and M13 established the floor: single features carry ~0.13–0.24 in R (short base, relative
strength). M16 confirms that floor (trajectory features alone ~0.10 OOS) **and shows the conjunction
lifts above it** — the M15 rule reaches continuous d 0.35 / +7–8.7 pp OOS. **The winner edge is
multivariate: no single score is the fingerprint; the short-base × momentum × clear-overhead
combination is.** This is the payoff of the whole descriptive arc — a real, R-verified, OOS-robust
signature that beats any single component.

## For the committee — CONFIRMED vs CANDIDATE

- **CONFIRMED (in-sample-window, R + OOS + regime):** the short-base + 5d-momentum + clear-overhead
  conjunction as a **runner-catch signature** (+3R, its strongest expression); the squeeze sub-type
  as its best home.
- **CANDIDATE (needs forward paper-track before sizing):** everything above is in-sample on a
  single-regime 2020–2026, survivorship-tainted window — the R effect (d 0.35, +7–8.7 pp) is real in
  this data but unproven live. Base rates are upper bounds.
- **Design note:** the rule can be **sharpened** (rule-positive winners carry extra momentum / RS /
  trigger — the rule is not the whole story) and is best deployed as a **runner-conviction tag**, not
  a binary gate. Committee to design the conversion; forward-track first.

---

*Deliverables: this synthesis + `m16a_rule_in_R.md`, `m16b_trajectory_fingerprint.md`,
`m16c_subtype_fingerprints.md`, `m16a/b/c` CSVs, `m16_feature_matrix_R.parquet`. Reproducible via
`scripts/m16_winner_fingerprint.py`. Registries `run_20260706r/s/t_m16a/b/c`. Halt at synthesis per
spec — await PM review.*
