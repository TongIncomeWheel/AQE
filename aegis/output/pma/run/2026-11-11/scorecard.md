# Committee scorecard — as of 2026-11-10 close

Horizon 5 sessions (shorter windows are marked partial). Benchmark SPY. base = last close before the run (checked against ledger ref_price, 0.5% tolerance); universe = equal-weight AQE daily list for that run over the same window; beta_adj = return - beta_30d x SPY return.

## 1 · The list vs the market

| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |
|---|---|---|---|---|---|
| 2026-11-10 | 2026-11-09 → 2026-11-10 | 1 (partial) | -0.37% | -0.44% | 157/279 |

## 2 · Every graded call, pooled

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 5 | +0.21% | +0.66% | +0.58 / +1.02 | 4/5 | +0.65 | +0.38 | 0.44 |
| Hold | 3 | -1.82% | -1.79% | -1.45 / -1.42 | 0/3 | -1.38 | -1.86 | -0.1 |
| Pass | 38 | -0.52% | -0.09% | -0.15 / +0.28 | 20/38 | -0.08 | -0.24 | 0.74 |
| Near-miss | 114 | -0.47% | -0.15% | -0.10 / +0.22 | 64/114 | -0.03 | -0.27 | 0.53 |

## 3 · Full-horizon calls only

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|

## 4 · Advances split at beta 2.5

| Group | n | Mean | vs SPY | Beat SPY | vs list |
|---|---|---|---|---|---|
| beta < 2.5 | 5 | +0.21% | +0.58 | 4/5 | +0.65 |

Worst advances: SWK (11-10) -1.04 β0.95, SJM (11-10) +0.62 β-0.15, PG (11-10) +1.02 β-0.03

**Refused (ledger price does not match the close):** 26 rows.

Not graded: 1643 rows (reasons in the JSON).
