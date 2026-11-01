# Committee scorecard — as of 2026-10-30 close

Horizon 5 sessions (shorter windows are marked partial). Benchmark SPY. base = last close before the run (checked against ledger ref_price, 0.5% tolerance); universe = equal-weight AQE daily list for that run over the same window; beta_adj = return - beta_30d x SPY return.

## 1 · The list vs the market

| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |
|---|---|---|---|---|---|
| 2026-10-15 | 2026-10-14 → 2026-10-21 | 5 | +0.45% | +3.50% | 148/172 |
| 2026-10-19 | 2026-10-16 → 2026-10-23 | 5 | -0.43% | +2.74% | 217/246 |
| 2026-10-20 | 2026-10-19 → 2026-10-26 | 5 | -0.14% | +3.06% | 171/199 |
| 2026-10-21 | 2026-10-20 → 2026-10-27 | 5 | +0.08% | +0.77% | 178/291 |
| 2026-10-22 | 2026-10-21 → 2026-10-28 | 5 | -0.10% | +0.79% | 165/260 |
| 2026-10-23 | 2026-10-22 → 2026-10-29 | 5 | +0.71% | +0.10% | 155/342 |
| 2026-10-26 | 2026-10-23 → 2026-10-30 | 5 | -0.56% | +0.33% | 187/288 |
| 2026-10-27 | 2026-10-26 → 2026-10-30 | 4 (partial) | -1.26% | +0.41% | 188/255 |
| 2026-10-28 | 2026-10-27 → 2026-10-30 | 3 (partial) | -1.81% | +0.31% | 171/215 |
| 2026-10-29 | 2026-10-28 → 2026-10-30 | 2 (partial) | -2.15% | -0.21% | 142/188 |

## 2 · Every graded call, pooled

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 83 | +0.32% | +0.31% | +0.68 / +0.51 | 49/83 | -0.82 | +0.55 | 0.38 |
| Hold | 259 | +0.05% | +0.46% | +0.68 / +1.18 | 172/259 | -1.00 | +0.55 | 0.41 |
| Pass | 93 | -0.15% | +1.12% | +0.61 / +1.40 | 58/93 | -0.50 | +0.49 | 0.53 |
| Near-miss | 992 | +0.33% | +0.72% | +0.84 / +1.17 | 636/992 | -0.03 | +0.44 | 0.17 |

## 3 · Full-horizon calls only

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 62 | +0.91% | +0.78% | +0.83 / +0.60 | 38/62 | -0.54 | +0.89 | 0.31 |
| Hold | 173 | +1.09% | +1.06% | +1.15 / +1.22 | 119/173 | -0.42 | +1.15 | 0.25 |
| Pass | 50 | +0.67% | +1.21% | +0.58 / +1.14 | 30/50 | +0.21 | +0.69 | 0.33 |
| Near-miss | 662 | +0.11% | +0.60% | +0.05 / +0.46 | 368/662 | -0.32 | +0.10 | 0.17 |

## 4 · Advances split at beta 2.5

| Group | n | Mean | vs SPY | Beat SPY | vs list |
|---|---|---|---|---|---|
| beta < 2.5 | 83 | +0.32% | +0.68 | 49/83 | -0.82 |

Worst advances: TEAM (10-27) -12.93 β1.31, MTCH (10-23) -7.83 β0.82, ESTC (10-27) -7.22 β1.9

Not graded: 54 rows (reasons in the JSON).
