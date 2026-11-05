# Swing-structure test case, 2026-11-05 slate (indicative; bars transcribed by hand from FMP, windows shortened)
Method: swing high/low = strict fractal, 3 bars each side (daily, hourly), 2 each side (weekly, partial week excluded). Class = last vs previous swing high AND swing low.
SH/SL = last / previous.

| Ticker | Weekly | Daily | Hourly | Close vs latest daily SH |
|---|---|---|---|---|
| KO | LH but HL | HH/HL (SH 95.37/94.10; SL 90.58/85.13) | HH/HL | +0.45% |
| ABBV | LH but HL | HH/HL (298.74/291.40; 281.23/278.01) | HH but LL | -1.31% |
| CAH | LH/LL | HH/HL (259.21/241.96; 243.49/216.70) | HH but LL | +1.05% |
| GLBE | LH but HL | HH but LL | HH but LL | +5.77% |
| MFC | LH/LL | LH but HL | HH/HL | +1.06% |
| CCEP | LH/LL | HH but LL | HH/HL | +1.13% |
| BBY | HH/HL (96.53/91.27; 83.65/76.70) | LH but HL | LH/LL | +0.87% |
| DG | HH but LL | HH/HL (139.12/125.78; 124.62/117.31) | HH but LL | +1.81% |
| BALL | LH/LL | HH/HL | LH/LL | +1.91% |
| USFD | HH but LL | HH/HL | HH but LL | +5.50% |
| KDP | HH/HL (33.17/33.14; 30.06/28.66) | LH but HL | HH/HL | +14.47% |
| WCN | LH/LL | HH/HL (187.36/157.49; 177.48/152.33) | HH/HL | +2.38% |

Counts of 12: weekly HH/HL 2 (BBY, KDP); daily 7 (KO ABBV CAH DG BALL USFD WCN); weekly+daily 0; all three 0.
Contrast: mtf.json hh_hl_3 (3 consecutive bars, strictly rising highs and lows) reads "mixed" on daily for 11 of 12 -- it is not a swing test.
