# Committee scorecard — as of 2026-11-09 close

Horizon 5 sessions (shorter windows are marked partial). Benchmark SPY. base = last close before the run (checked against ledger ref_price, 0.5% tolerance); universe = equal-weight AQE daily list for that run over the same window; beta_adj = return - beta_30d x SPY return.

## 1 · The list vs the market

| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |
|---|---|---|---|---|---|
| 2026-10-15 | 2026-10-14 → 2026-10-21 | 5 | +0.45% | +2.75% | 168/213 |
| 2026-10-19 | 2026-10-16 → 2026-10-23 | 5 | -0.43% | +2.30% | 241/288 |
| 2026-10-20 | 2026-10-19 → 2026-10-26 | 5 | -0.14% | +2.55% | 186/228 |
| 2026-10-21 | 2026-10-20 → 2026-10-27 | 5 | +0.08% | +0.43% | 185/326 |
| 2026-10-22 | 2026-10-21 → 2026-10-28 | 5 | -0.10% | +0.52% | 169/276 |
| 2026-10-23 | 2026-10-22 → 2026-10-29 | 5 | +0.71% | -0.26% | 159/372 |
| 2026-10-26 | 2026-10-23 → 2026-10-30 | 5 | -0.56% | +0.19% | 190/301 |
| 2026-10-27 | 2026-10-26 → 2026-11-02 | 5 | -1.73% | +0.93% | 203/266 |
| 2026-10-28 | 2026-10-27 → 2026-11-03 | 5 | -1.99% | -0.27% | 162/229 |

## 2 · Every graded call, pooled

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 79 | +0.11% | +0.17% | +0.42 / +0.58 | 45/79 | -0.83 | +0.35 | 0.38 |
| Hold | 229 | +0.44% | +0.96% | +0.87 / +1.22 | 152/229 | -0.61 | +0.76 | 0.32 |
| Pass | 87 | -0.35% | +1.13% | +0.34 / +1.40 | 53/87 | -0.52 | +0.16 | 0.47 |
| Near-miss | 919 | +0.37% | +0.72% | +0.81 / +1.06 | 571/919 | +0.13 | +0.40 | 0.15 |

## 3 · Full-horizon calls only

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 79 | +0.11% | +0.17% | +0.42 / +0.58 | 45/79 | -0.83 | +0.35 | 0.38 |
| Hold | 229 | +0.44% | +0.96% | +0.87 / +1.22 | 152/229 | -0.61 | +0.76 | 0.32 |
| Pass | 87 | -0.35% | +1.13% | +0.34 / +1.40 | 53/87 | -0.52 | +0.16 | 0.47 |
| Near-miss | 919 | +0.37% | +0.72% | +0.81 / +1.06 | 571/919 | +0.13 | +0.40 | 0.15 |

## 4 · Advances split at beta 2.5

| Group | n | Mean | vs SPY | Beat SPY | vs list |
|---|---|---|---|---|---|
| beta < 2.5 | 79 | +0.11% | +0.42 | 45/79 | -0.83 |

Worst advances: TEAM (10-27) -14.53 β1.31, ESTC (10-27) -12.33 β1.9, ESTC (10-28) -12.27 β1.81

Not graded: 218 rows (reasons in the JSON).
