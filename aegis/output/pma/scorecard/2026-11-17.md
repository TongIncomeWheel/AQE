# Committee scorecard — as of 2026-11-16 close

Horizon 5 sessions (shorter windows are marked partial). Benchmark SPY. base = last close before the run (checked against ledger ref_price, 0.5% tolerance); universe = equal-weight AQE daily list for that run over the same window; beta_adj = return - beta_30d x SPY return.

## 1 · The list vs the market

| Run | Base → end | Sessions | SPY | AQE list (EW) | List names beating SPY |
|---|---|---|---|---|---|
| 2026-11-10 | 2026-11-09 → 2026-11-16 | 5 | -1.69% | -2.72% | 138/286 |
| 2026-11-11 | 2026-11-10 → 2026-11-16 | 4 (partial) | -1.33% | -2.73% | 198/446 |
| 2026-11-12 | 2026-11-11 → 2026-11-16 | 3 (partial) | -2.61% | -3.09% | 258/454 |
| 2026-11-13 | 2026-11-12 → 2026-11-16 | 2 (partial) | -2.27% | -1.68% | 206/304 |
| 2026-11-16 | 2026-11-13 → 2026-11-16 | 1 (partial) | -1.91% | -1.03% | 221/302 |

## 2 · Every graded call, pooled

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 11 | -0.36% | -0.34% | +1.51 / +1.85 | 8/11 | +1.92 | +0.62 | 0.54 |
| Hold | 24 | -1.27% | -0.77% | +0.76 / +1.23 | 16/24 | +1.17 | -0.32 | 0.45 |
| Pass | 200 | -2.02% | -1.25% | -0.03 / +0.90 | 121/200 | +0.34 | -0.94 | 0.62 |
| Near-miss | 765 | -2.46% | -1.62% | -0.50 / +0.32 | 410/765 | +0.15 | -0.98 | 0.76 |

## 3 · Full-horizon calls only

| Verdict | n | Mean | Median | vs SPY (mean / median) | Beat SPY | vs list | Beta-adj | Avg beta |
|---|---|---|---|---|---|---|---|---|
| Advance | 7 | -0.20% | +0.16% | +1.49 / +1.85 | 5/7 | +2.52 | +0.68 | 0.52 |
| Hold | 4 | -2.66% | -0.46% | -0.97 / +1.23 | 3/4 | +0.06 | -3.10 | -0.26 |
| Pass | 39 | -3.97% | -2.85% | -2.28 / -1.16 | 16/39 | -1.25 | -2.72 | 0.74 |
| Near-miss | 136 | -2.61% | -1.98% | -0.91 / -0.28 | 65/136 | +0.11 | -1.68 | 0.55 |

## 4 · Advances split at beta 2.5

| Group | n | Mean | vs SPY | Beat SPY | vs list |
|---|---|---|---|---|---|
| beta < 2.5 | 11 | -0.36% | +1.51 | 8/11 | +1.92 |

Worst advances: SWK (11-10) -2.69 β0.95, TMO (11-10) -2.51 β1.09, CDW (11-16) -1.48 β1.91

## 5 · By method (the Standard Scan started 2026-11-16)

| Method | Verdict | n | Mean | vs SPY | Beat SPY | vs AQE list |
|---|---|---|---|---|---|---|
| AQE doors (before the change) | Advance | 10 | -0.05% | +1.81 | 8/10 | +2.35 |
| AQE doors (before the change) | Hold | 20 | -1.46% | +0.60 | 12/20 | +1.26 |
| AQE doors (before the change) | Pass | 172 | -2.14% | -0.14 | 102/172 | +0.44 |
| AQE doors (before the change) | Near-miss | 734 | -2.56% | -0.61 | 387/734 | +0.12 |
| Standard Scan, whole market | Advance | 1 | -3.40% | -1.48 | 0/1 | -2.37 |
| Standard Scan, whole market | Hold | 4 | -0.34% | +1.58 | 4/4 | +0.70 |
| Standard Scan, whole market | Pass | 28 | -1.25% | +0.66 | 19/28 | -0.22 |
| Standard Scan, whole market | Near-miss | 31 | -0.00% | +1.91 | 23/31 | +1.03 |

## 6 · Standard Scan picks: AQE-listed or not

| Group | Verdict | n | Mean | vs SPY | Beat SPY | vs AQE list |
|---|---|---|---|---|---|---|
| AQE-listed | Advance | 1 | -3.40% | -1.48 | 0/1 | -2.37 |
| AQE-listed | Hold | 3 | -0.72% | +1.19 | 3/3 | +0.31 |
| AQE-listed | Pass | 12 | -0.78% | +1.13 | 9/12 | +0.25 |
| AQE-listed | Near-miss | 28 | +0.00% | +1.91 | 20/28 | +1.03 |
| not AQE-listed | Hold | 1 | +0.81% | +2.72 | 1/1 | +1.84 |
| not AQE-listed | Pass | 16 | -1.60% | +0.31 | 10/16 | -0.57 |
| not AQE-listed | Near-miss | 3 | -0.07% | +1.84 | 3/3 | +0.96 |

**Refused (ledger price does not match the close):** 4 rows.

Not graded: 1 rows (reasons in the JSON).
