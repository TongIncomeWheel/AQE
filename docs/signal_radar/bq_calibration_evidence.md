# BQ Calibration -- Evidence Pack (committee decision required)

QUAL pond v1.8.0, n=7040 episodes, outcomes = % touch from open(t0+1), 20 trading days.
Pond base detection +20%/20d = 15.7% (test era 21.0%). Every % below is a
DETECTION rate (price path only), never a win rate.

## The problem, in one table

bq_100 decile (1 = lowest quality, 10 = highest) -> +20%/20d detection:
```
 decile  feat_median  detection_+20pct_20d
      1         15.0                  33.5
      2         18.0                  17.9
      3         20.0                  24.0
      4         24.0                  12.6
      5         25.0                  22.2
      6         29.0                  12.6
      7         32.0                   9.8
      8         35.0                   8.2
      9         40.0                   7.7
     10         48.0                   8.4
```
Detection FALLS as Base Quality rises. The score's heaviest component (35%) points at
the slowest-moving names. Same shape for the BQ sub-scores (see bq_decile_curves.csv).

## What re-weighting does (fixed candidate weights, no fitting, era-split)
```
                  variant  top_decile_det20_all  ic_all  top_decile_det20_train_era  ic_train_era  top_decile_det20_test_era  ic_test_era
         BQ=35% (current)                   8.5  -0.133                         7.0        -0.141                       11.7       -0.115
                   BQ=25%                  10.1  -0.110                         7.2        -0.120                       15.8       -0.090
                   BQ=15%                  11.6  -0.076                         9.6        -0.088                       15.4       -0.055
                    BQ=5%                  14.5  -0.030                        11.1        -0.045                       20.6       -0.008
                    BQ=0%                  16.3  -0.004                        12.9        -0.020                       22.7        0.017
BQ->mover_base swap (35%)                  37.6   0.364                        33.4         0.343                       43.7        0.392
```
Reading: lowering the BQ weight raises how well SC_POSITION ranks forward movers, in
BOTH eras; the swap variant (BQ replaced by a short-base score) does best. The gap is
consistent, not a one-era artifact.

## Governance (non-negotiable)
- SC_POSITION is a DEPLOYED indicator. Any re-weight is a versioned variant:
  duplicate-indicator prompt to the PM, committee ruling, and a backtest sign-off
  BEFORE deploy (Charter v2.3 pending-amendment rule). Nothing was changed here.
- Note the mandate boundary: SC_POSITION is a POSITION score, not the momentum radar.
  If the committee wants it to keep rewarding stable bases for position entries,
  the alternative is to leave SC_POSITION alone and let the radar tags (runner_setup /
  premove_setup) carry the move-detection job. Both paths are on the table; the
  evidence above says only: as a MOVER-ranker, the current BQ weight is backwards.

Caveats: single regime 2020-2026, survivorship-tainted, in-sample; detection rates are
upper bounds.