# Committee scorecard — as of 2026-11-02 close

Horizon 5 sessions (shorter windows are marked partial). Benchmark SPY. base = last close before the run (checked against ledger ref_price, 0.5% tolerance); universe = equal-weight AQE daily list for that run over the same window; beta_adj = return - beta_30d x SPY return.

## 1 · The list vs the market

| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |
|---|---|---|---|---|---|
| 2026-10-15 | 2026-10-14 → 2026-10-21 | 5 | +0.45% | +3.19% | 161/194 |
| 2026-10-19 | 2026-10-16 → 2026-10-23 | 5 | -0.43% | +2.53% | 238/274 |
| 2026-10-20 | 2026-10-19 → 2026-10-26 | 5 | -0.14% | +2.78% | 182/218 |
| 2026-10-21 | 2026-10-20 → 2026-10-27 | 5 | +0.08% | +0.59% | 183/316 |
| 2026-10-22 | 2026-10-21 → 2026-10-28 | 5 | -0.10% | +0.74% | 166/265 |
| 2026-10-23 | 2026-10-22 → 2026-10-29 | 5 | +0.71% | -0.12% | 159/366 |
| 2026-10-26 | 2026-10-23 → 2026-10-30 | 5 | -0.56% | +0.27% | 190/297 |
| 2026-10-27 | 2026-10-26 → 2026-11-02 | 5 | -1.73% | +1.08% | 203/262 |
| 2026-10-28 | 2026-10-27 → 2026-11-02 | 4 (partial) | -2.28% | +0.61% | 168/219 |
| 2026-10-29 | 2026-10-28 → 2026-11-02 | 3 (partial) | -2.62% | -0.01% | 147/195 |
| 2026-11-02 | 2026-10-30 → 2026-11-02 | 1 (partial) | -0.48% | +1.27% | 198/252 |

## 2 · Every graded call, pooled

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 95 | +0.18% | +0.31% | +0.66 / +0.60 | 55/95 | -0.96 | +0.43 | 0.3 |
| Hold | 271 | -0.18% | +0.63% | +0.58 / +1.26 | 180/271 | -1.30 | +0.40 | 0.38 |
| Pass | 120 | -0.17% | +0.99% | +0.68 / +1.38 | 70/120 | -0.78 | +0.49 | 0.5 |
| Near-miss | 1133 | +0.57% | +0.90% | +1.20 / +1.49 | 740/1133 | +0.05 | +0.69 | 0.15 |

## 3 · Full-horizon calls only

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 72 | +0.35% | +0.36% | +0.50 / +0.59 | 42/72 | -0.90 | +0.43 | 0.32 |
| Hold | 210 | +0.80% | +1.05% | +1.09 / +1.24 | 143/210 | -0.56 | +0.94 | 0.24 |
| Pass | 65 | +0.67% | +1.13% | +0.92 / +1.36 | 41/65 | +0.20 | +0.96 | 0.44 |
| Near-miss | 820 | +0.33% | +0.72% | +0.58 / +0.91 | 490/820 | -0.12 | +0.34 | 0.15 |

## 4 · Advances split at beta 2.5

| Group | n | Mean | vs SPY | Beat SPY | vs list |
|---|---|---|---|---|---|
| beta < 2.5 | 95 | +0.18% | +0.66 | 55/95 | -0.96 |

Worst advances: TEAM (10-27) -14.53 β1.31, ESTC (10-27) -12.33 β1.9, ESTC (10-28) -11.16 β1.81

Not graded: 259 rows (reasons in the JSON).
