# Committee scorecard — as of 2026-11-11 close

Horizon 5 sessions (shorter windows are marked partial). Benchmark SPY. base = last close before the run (checked against ledger ref_price, 0.5% tolerance); universe = equal-weight AQE daily list for that run over the same window; beta_adj = return - beta_30d x SPY return.

## 1 · The list vs the market

| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |
|---|---|---|---|---|---|
| 2026-11-10 | 2026-11-09 → 2026-11-11 | 2 (partial) | +0.95% | -0.76% | 57/286 |
| 2026-11-11 | 2026-11-10 → 2026-11-11 | 1 (partial) | +1.32% | +0.22% | 81/446 |

## 2 · Every graded call, pooled

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 8 | -0.20% | -0.27% | -1.19 / -1.36 | 2/8 | +0.44 | -0.85 | 0.62 |
| Hold | 9 | -0.20% | +0.21% | -1.35 / -1.11 | 2/9 | +0.02 | -0.26 | 0.02 |
| Pass | 82 | -0.52% | -0.39% | -1.66 / -1.53 | 14/82 | -0.27 | -1.31 | 0.7 |
| Near-miss | 384 | +0.04% | -0.07% | -1.14 / -1.32 | 81/384 | +0.17 | -0.82 | 0.71 |

## 3 · Full-horizon calls only

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|

## 4 · Advances split at beta 2.5

| Group | n | Mean | vs SPY | Beat SPY | vs list |
|---|---|---|---|---|---|
| beta < 2.5 | 8 | -0.20% | -1.19 | 2/8 | +0.44 |

Worst advances: SWK (11-10) -3.05 β0.95, JNJ (11-10) -1.55 β0.35, TMO (11-10) -1.49 β1.09

Not graded: 1623 rows (reasons in the JSON).
