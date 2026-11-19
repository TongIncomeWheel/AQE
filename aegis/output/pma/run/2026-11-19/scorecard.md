# Committee scorecard — as of 2026-11-18 close

Horizon 5 sessions (shorter windows are marked partial). Benchmark SPY. base = last close before the run (checked against ledger ref_price, 0.5% tolerance); universe = equal-weight AQE daily list for that run over the same window; beta_adj = return - beta_30d x SPY return.

## 1 · The list vs the market

| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |
|---|---|---|---|---|---|
| 2026-11-10 | 2026-11-09 → 2026-11-16 | 5 | -1.69% | -2.72% | 138/286 |
| 2026-11-11 | 2026-11-10 → 2026-11-17 | 5 | -2.33% | -4.25% | 185/446 |
| 2026-11-12 | 2026-11-11 → 2026-11-18 | 5 | -3.90% | -4.41% | 260/454 |
| 2026-11-13 | 2026-11-12 → 2026-11-18 | 4 (partial) | -3.56% | -2.65% | 201/304 |
| 2026-11-16 | 2026-11-13 → 2026-11-18 | 3 (partial) | -3.20% | -2.35% | 209/302 |
| 2026-11-17 | 2026-11-16 → 2026-11-18 | 2 (partial) | -1.32% | -1.24% | 167/334 |
| 2026-11-18 | 2026-11-17 → 2026-11-18 | 1 (partial) | -0.31% | +0.31% | 117/201 |

## 2 · Every graded call, pooled

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 12 | -0.89% | -0.73% | +1.36 / +1.76 | 8/12 | +1.66 | +0.25 | 0.49 |
| Hold | 27 | -2.68% | -1.46% | +0.13 / +1.10 | 19/27 | +0.54 | -1.11 | 0.54 |
| Pass | 249 | -2.68% | -1.71% | -0.14 / +0.60 | 139/249 | +0.15 | -1.21 | 0.58 |
| Near-miss | 806 | -3.44% | -2.44% | -0.62 / +0.29 | 418/806 | +0.11 | -1.31 | 0.74 |

## 3 · Full-horizon calls only

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 7 | -0.20% | +0.16% | +1.49 / +1.85 | 5/7 | +2.52 | +0.68 | 0.52 |
| Hold | 17 | -3.05% | -0.86% | -0.14 / +1.58 | 12/17 | +0.91 | -1.73 | 0.33 |
| Pass | 131 | -3.68% | -2.62% | -0.95 / +0.28 | 69/131 | +0.18 | -2.14 | 0.65 |
| Near-miss | 618 | -3.78% | -2.73% | -0.99 / -0.13 | 299/618 | +0.20 | -1.66 | 0.74 |

## 4 · Advances split at beta 2.5

| Group | n | Mean | vs SPY | Beat SPY | vs list |
|---|---|---|---|---|---|
| beta < 2.5 | 12 | -0.89% | +1.36 | 8/12 | +1.66 |

Worst advances: SWK (11-10) -2.69 β0.95, TMO (11-10) -2.51 β1.09, CHD (11-17) -1.19 β-0.01

## 5 · By method (the Standard Scan started 2026-11-16)

| Method | Verdict | n | Mean | vs SPY | Beat SPY | vs AQE list |
|---|---|---|---|---|---|---|
| AQE doors (before the change) | Advance | 10 | -0.67% | +1.58 | 7/10 | +2.03 |
| AQE doors (before the change) | Hold | 20 | -2.78% | +0.24 | 15/20 | +0.99 |
| AQE doors (before the change) | Pass | 172 | -3.20% | -0.28 | 101/172 | +0.36 |
| AQE doors (before the change) | Near-miss | 734 | -3.58% | -0.67 | 376/734 | +0.19 |
| Standard Scan, whole market | Advance | 2 | -2.02% | +0.24 | 1/2 | -0.23 |
| Standard Scan, whole market | Hold | 7 | -2.42% | -0.16 | 4/7 | -0.76 |
| Standard Scan, whole market | Pass | 77 | -1.52% | +0.18 | 38/77 | -0.34 |
| Standard Scan, whole market | Near-miss | 72 | -2.00% | -0.10 | 42/72 | -0.64 |

## 6 · Standard Scan picks: AQE-listed or not

| Group | Verdict | n | Mean | vs SPY | Beat SPY | vs AQE list |
|---|---|---|---|---|---|---|
| AQE-listed | Advance | 2 | -2.02% | +0.24 | 1/2 | -0.23 |
| AQE-listed | Hold | 6 | -2.43% | -0.33 | 3/6 | -0.89 |
| AQE-listed | Pass | 42 | -1.23% | +0.27 | 19/42 | -0.22 |
| AQE-listed | Near-miss | 60 | -2.35% | -0.36 | 32/60 | -0.90 |
| not AQE-listed | Hold | 1 | -2.36% | +0.85 | 1/1 | -0.01 |
| not AQE-listed | Pass | 35 | -1.87% | +0.09 | 19/35 | -0.47 |
| not AQE-listed | Near-miss | 12 | -0.21% | +1.15 | 10/12 | +0.66 |

**Refused (ledger price does not match the close):** 4 rows.

Not graded: 1389 rows (reasons in the JSON).
