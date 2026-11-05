# Momentum universe: swing structure for all 395 export names (5 Nov 2026)

Read-only scan, same path as the nightly grid (`committee_data.build_grid`), FMP daily + hourly bars through the 4 Nov session, 395 of 395 names served and complete, 790 FMP calls, 0 errors (Actions run 41985256315, `scripts/mtf_universe_scan.py`). `aegis/output/committee_data/mtf_grid.json` was not touched. Information only: no gate, no vote.

## Counts over 395

| Structure | Names |
|---|---|
| Weekly higher highs and higher lows | 86 |
| Daily higher highs and higher lows | 211 |
| Weekly and daily | 51 |
| Weekly, daily and hourly | 31 |

## Distance from the latest confirmed daily swing high, in daily ranges (ATR)

Distance = (daily close - latest confirmed daily swing high) / `atr_14d` from the export; positive = above. Edges: within 1 ATR either side = at the pivot; 1 to 3 above = extended; over 3 above = far extended; more than 1 under = below. The edges are constants (`ATR_NEAR`, `ATR_FAR`) in `card_extras.py`; the PM picks the final numbers.

| Band | Names | On the room (46) | On Longlist | On Elder |
|---|---|---|---|---|
| at the pivot | 20 | 0 | 15 | 15 |
| extended | 20 | 2 | 19 | 20 |
| far extended | 7 | 3 | 7 | 7 |
| below | 4 | 0 | 2 | 1 |
| **All weekly+daily HH/HL** | **51** | **5** | **43** | **43** |

Room names in this set: HRB +2.9 (extended), PRU +3.0 (extended), ABT +3.0 (far extended), GPK +5.4 (far extended), SWK +6.5 (far extended). Rounding note: a name shown as 3.0 can sit either side of the 3.00 edge (PRU, STGW just under = extended; ABT just over = far extended).

### At the pivot (20)

| Ticker | ATR from swing high | % from swing high | Swing high | Sessions since it | Under the 20-day high % | AQE rank | Sector | Room | Longlist | Elder | Hourly |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M | +1.0 | +3.6% | 24.8 (2026-10-26) | 7 | 0.12 | 196 | Consumer Discretionary |  | yes | yes | HH but LL |
| AFL | +1.0 | +1.6% | 123.28 (2026-10-22) | 9 | 0.7 | 19 | Financials |  | yes |  | HH/HL |
| EL | +0.8 | +3.1% | 108.72 (2026-10-16) | 13 | 1.31 | 125 | Consumer Staples |  | yes | yes | HH/HL |
| GDDY | +0.7 | +3.1% | 114.77 (2026-10-23) | 8 | 2.6 | 145 | Technology |  | yes | yes | LH but HL |
| CRBG | +0.6 | +1.7% | 35.64 (2026-10-22) | 9 | 1.35 | 323 | Financials |  |  | yes | HH/HL |
| BOX | +0.4 | +1.1% | 43.57 (2026-10-26) | 7 | 1.27 | 218 | Technology |  | yes |  | HH/HL |
| BMY | +0.3 | +0.9% | 63.59 (2026-10-22) | 9 | 0.08 | 350 | Healthcare |  |  | yes | HH but LL |
| KR | +0.2 | +0.6% | 68.56 (2026-10-23) | 8 | 0.68 | 209 | Consumer Staples |  | yes | yes | HH but LL |
| LTH | +0.0 | +0.1% | 47.32 (2026-10-29) | 4 | 1.17 | 28 | Consumer Discretionary |  | yes | yes | HH/HL |
| NCNO | -0.1 | -0.3% | 23.5 (2026-10-23) | 8 | 1.35 | 192 | Technology |  | yes | yes | HH/HL |
| ORLY | -0.1 | -0.3% | 92.59 (2026-10-29) | 4 | 0.82 | 272 | Consumer Discretionary |  | yes | yes | HH/HL |
| PAYX | -0.2 | -0.6% | 119.47 (2026-10-23) | 8 | 1.13 | 312 | Industrials |  |  | yes | HH/HL |
| TAK | -0.4 | -0.8% | 21.22 (2026-10-30) | 3 | 0.75 | 286 | Healthcare |  | yes | yes | HH but LL |
| CFG | -0.4 | -0.9% | 66.5 (2026-10-29) | 4 | 1.8 | 380 | Financials |  |  | yes | HH/HL |
| PK | -0.4 | -1.1% | 17.14 (2026-10-22) | 9 | 1.05 | 252 | Real Estate |  | yes |  | LH but HL |
| SJM | -0.5 | -1.2% | 134.0 (2026-10-23) | 8 | 1.17 | 157 | Consumer Staples |  | yes | yes | HH/HL |
| ABNB | -0.5 | -1.5% | 179.13 (2026-10-20) | 11 | 2.03 | 364 | Consumer Discretionary |  |  | yes | HH/HL |
| LLY | -0.7 | -2.2% | 1449.68 (2026-10-30) | 3 | 2.2 | 122 | Healthcare |  | yes |  | HH/HL |
| SONY | -0.7 | -1.4% | 26.31 (2026-10-22) | 9 | 1.37 | 92 | Technology |  | yes |  | HH but LL |
| ADP | -0.8 | -1.9% | 309.4 (2026-10-23) | 8 | 1.89 | 16 | Industrials |  | yes | yes | HH/HL |

### Extended (20)

| Ticker | ATR from swing high | % from swing high | Swing high | Sessions since it | Under the 20-day high % | AQE rank | Sector | Room | Longlist | Elder | Hourly |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PRU | +3.0 | +7.1% | 118.2 (2026-10-22) | 9 | 0.91 | 158 | Financials | yes | yes | yes | HH/HL |
| STGW | +3.0 | +14.1% | 9.64 (2026-10-13) | 16 | 3.08 | 37 | Communication Services |  | yes | yes | HH/HL |
| MA | +2.9 | +6.2% | 633.29 (2026-10-22) | 9 | 0.12 | 40 | Financials |  | yes | yes | HH/HL |
| HRB | +2.9 | +9.8% | 50.54 (2026-10-26) | 7 | 0.0 | 127 | Consumer Discretionary | yes | yes | yes | HH/HL |
| HNGE | +2.8 | +13.0% | 107.0 (2026-10-13) | 16 | 3.25 | 159 | Healthcare |  | yes | yes | HH/HL |
| SN | +2.5 | +9.4% | 200.39 (2026-10-21) | 10 | 2.37 | 44 | Consumer Discretionary |  | yes | yes | HH but LL |
| PRCH | +2.4 | +15.0% | 18.75 (2026-10-21) | 10 | 1.82 | 247 | Technology |  | yes | yes | HH/HL |
| NVS | +2.4 | +5.0% | 157.1 (2026-10-22) | 9 | 0.04 | 109 | Healthcare |  | yes | yes | LH/LL |
| AMGN | +2.4 | +6.1% | 450.98 (2026-10-22) | 9 | 0.83 | 135 | Healthcare |  | yes | yes | LH/LL |
| DRI | +2.1 | +5.3% | 218.93 (2026-10-16) | 13 | 0.32 | 242 | Consumer Discretionary |  | yes | yes | LH/LL |
| BDX | +2.0 | +4.3% | 200.47 (2026-10-22) | 9 | 0.31 | 64 | Healthcare |  | yes | yes | HH/HL |
| LYFT | +1.7 | +6.8% | 17.54 (2026-10-22) | 9 | 0.53 | 184 | Technology |  | yes | yes | HH/HL |
| HIW | +1.6 | +4.5% | 30.82 (2026-10-26) | 7 | 0.09 | 320 | Real Estate |  |  | yes | HH but LL |
| SHW | +1.6 | +5.0% | 346.19 (2026-10-22) | 9 | 0.56 | 181 | Materials |  | yes | yes | HH/HL |
| SPOT | +1.5 | +5.7% | 593.8 (2026-10-23) | 8 | 0.76 | 143 | Communication Services |  | yes | yes | HH/HL |
| TOST | +1.4 | +5.8% | 33.44 (2026-10-22) | 9 | 1.79 | 106 | Technology |  | yes | yes | HH/HL |
| CHD | +1.3 | +2.8% | 108.93 (2026-10-22) | 9 | 1.07 | 101 | Consumer Staples |  | yes | yes | HH/HL |
| ASB | +1.2 | +2.5% | 30.6 (2026-10-23) | 8 | 2.31 | 241 | Financials |  | yes | yes | HH but LL |
| CAG | +1.1 | +3.9% | 14.7 (2026-10-15) | 14 | 1.29 | 169 | Consumer Staples |  | yes | yes | HH/HL |
| EXPE | +1.0 | +4.7% | 301.81 (2026-10-20) | 11 | 3.22 | 129 | Consumer Discretionary |  | yes | yes | LH but HL |

### Far extended (7)

| Ticker | ATR from swing high | % from swing high | Swing high | Sessions since it | Under the 20-day high % | AQE rank | Sector | Room | Longlist | Elder | Hourly |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SWK | +6.5 | +28.1% | 92.35 (2026-09-29) | 26 | 3.55 | 35 | Industrials | yes | yes | yes | HH/HL |
| GEHC | +5.8 | +20.3% | 71.32 (2026-10-16) | 13 | 2.0 | 10 | Healthcare |  | yes | yes | HH/HL |
| GPK | +5.4 | +30.1% | 9.05 (2026-10-22) | 9 | 3.05 | 228 | Consumer Discretionary | yes | yes | yes | HH/HL |
| VIA | +5.0 | +27.5% | 30.74 (2026-09-24) | 29 | 3.17 | 87 | Technology |  | yes | yes | HH but LL |
| BAM | +4.2 | +13.3% | 47.76 (2026-10-22) | 9 | 1.02 | 239 | Financials |  | yes | yes | HH/HL |
| MDT | +3.1 | +8.3% | 96.89 (2026-10-23) | 8 | 0.72 | 225 | Healthcare |  | yes | yes | HH/HL |
| ABT | +3.0 | +8.6% | 106.35 (2026-10-21) | 10 | 0.59 | 185 | Healthcare | yes | yes | yes | HH but LL |

### Below (4)

| Ticker | ATR from swing high | % from swing high | Swing high | Sessions since it | Under the 20-day high % | AQE rank | Sector | Room | Longlist | Elder | Hourly |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PAYO | -1.0 | -0.4% | 7.19 (2026-09-25) | 28 | 0.83 | 351 | Technology |  |  | yes | n/a |
| KBR | -1.1 | -3.7% | 41.16 (2026-10-29) | 4 | 3.69 | 110 | Industrials |  | yes |  | LH but HL |
| GPN | -1.5 | -5.2% | 101.32 (2026-10-30) | 3 | 5.16 | 72 | Financials |  | yes |  | LH but HL |
| TEAM | -4.0 | -17.4% | 229.96 (2026-10-22) | 9 | 17.43 | 395 | Technology |  |  |  | LH but HL |

## Proposal (not merged until the PM says): the card flag

The earlier flag (weekly and daily HH/HL and the daily close within 2% of the daily swing high) mixed two different pictures. The PM rejected the fixed 2% as arbitrary; ATR scales the distance to each stock's own range (the same 4% above a swing high is 0.8 ATR on a calm name, 4.4 ATR on a fast one). Built and approved as the card change: the flag is now the structure (weekly and daily HH/HL) shown with its ATR distance and band as data, e.g. `Uptrend, extended (+2.9 ATR)`, plus the stop's risk in ATR on the same line. Reading: *at the pivot* is the coiling picture (price sitting on the swing high); *extended* and *far extended* are trending names that have already run from it, and the card shows how far. No gate, no vote (R1). The 1 and 3 edges are placeholders until the PM picks.
