# Committee scorecard — as of 2026-11-12 close

Horizon 5 sessions (shorter windows are marked partial). Benchmark SPY. base = last close before the run (checked against ledger ref_price, 0.5% tolerance); universe = equal-weight AQE daily list for that run over the same window; beta_adj = return - beta_30d x SPY return.

## 1 · The list vs the market

| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |
|---|---|---|---|---|---|
| 2026-11-10 | 2026-11-09 → 2026-11-12 | 3 (partial) | +0.59% | -2.48% | 37/286 |
| 2026-11-11 | 2026-11-10 → 2026-11-12 | 2 (partial) | +0.96% | -1.67% | 57/446 |
| 2026-11-12 | 2026-11-11 → 2026-11-12 | 1 (partial) | -0.35% | -1.73% | 111/454 |

## 2 · Every graded call, pooled

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 8 | -1.18% | -0.66% | -1.81 / -1.25 | 2/8 | +1.20 | -1.60 | 0.62 |
| Hold | 17 | -2.11% | -0.59% | -2.37 / -0.49 | 5/17 | -0.23 | -2.03 | 0.33 |
| Pass | 131 | -2.19% | -1.51% | -2.55 / -1.90 | 33/131 | -0.25 | -2.58 | 0.65 |
| Near-miss | 619 | -1.82% | -1.67% | -2.20 / -1.93 | 105/619 | +0.05 | -2.09 | 0.74 |

## 3 · Full-horizon calls only

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|

## 4 · Advances split at beta 2.5

| Group | n | Mean | vs SPY | Beat SPY | vs list |
|---|---|---|---|---|---|
| beta < 2.5 | 8 | -1.18% | -1.81 | 2/8 | +1.20 |

Worst advances: SWK (11-10) -4.89 β0.95, EMBJ (11-11) -4.62 β1.3, TMO (11-10) -3.66 β1.09

Not graded: 1511 rows (reasons in the JSON).
