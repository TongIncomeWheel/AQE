# Committee scorecard — as of 2026-11-06 close

Horizon 5 sessions (shorter windows are marked partial). Benchmark SPY. base = last close before the run (checked against ledger ref_price, 0.5% tolerance); universe = equal-weight AQE daily list for that run over the same window; beta_adj = return - beta_30d x SPY return.

## 1 · The list vs the market

| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |
|---|---|---|---|---|---|
| 2026-10-15 | 2026-10-14 → 2026-10-21 | 5 | +0.45% | +2.72% | 163/208 |
| 2026-10-19 | 2026-10-16 → 2026-10-23 | 5 | -0.43% | +2.28% | 234/279 |
| 2026-10-20 | 2026-10-19 → 2026-10-26 | 5 | -0.14% | +2.51% | 177/219 |
| 2026-10-21 | 2026-10-20 → 2026-10-27 | 5 | +0.08% | +0.46% | 180/318 |
| 2026-10-22 | 2026-10-21 → 2026-10-28 | 5 | -0.10% | +0.55% | 162/265 |
| 2026-10-23 | 2026-10-22 → 2026-10-29 | 5 | +0.71% | -0.22% | 155/361 |
| 2026-10-26 | 2026-10-23 → 2026-10-30 | 5 | -0.56% | +0.33% | 186/288 |
| 2026-10-27 | 2026-10-26 → 2026-11-02 | 5 | -1.73% | +1.05% | 200/259 |
| 2026-10-28 | 2026-10-27 → 2026-11-03 | 5 | -1.99% | -0.18% | 157/220 |

## 2 · Every graded call, pooled

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 78 | +0.08% | +0.14% | +0.40 / +0.54 | 44/78 | -0.92 | +0.31 | 0.39 |
| Hold | 223 | +0.45% | +0.96% | +0.89 / +1.22 | 147/223 | -0.64 | +0.77 | 0.33 |
| Pass | 85 | -0.16% | +1.30% | +0.53 / +1.40 | 53/85 | -0.42 | +0.32 | 0.47 |
| Near-miss | 891 | +0.46% | +0.77% | +0.90 / +1.15 | 560/891 | +0.15 | +0.49 | 0.15 |

## 3 · Full-horizon calls only

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 78 | +0.08% | +0.14% | +0.40 / +0.54 | 44/78 | -0.92 | +0.31 | 0.39 |
| Hold | 223 | +0.45% | +0.96% | +0.89 / +1.22 | 147/223 | -0.64 | +0.77 | 0.33 |
| Pass | 85 | -0.16% | +1.30% | +0.53 / +1.40 | 53/85 | -0.42 | +0.32 | 0.47 |
| Near-miss | 891 | +0.46% | +0.77% | +0.90 / +1.15 | 560/891 | +0.15 | +0.49 | 0.15 |

## 4 · Advances split at beta 2.5

| Group | n | Mean | vs SPY | Beat SPY | vs list |
|---|---|---|---|---|---|
| beta < 2.5 | 78 | +0.08% | +0.40 | 44/78 | -0.92 |

Worst advances: TEAM (10-27) -14.53 β1.31, ESTC (10-27) -12.33 β1.9, ESTC (10-28) -12.27 β1.81

Not graded: 227 rows (reasons in the JSON).
