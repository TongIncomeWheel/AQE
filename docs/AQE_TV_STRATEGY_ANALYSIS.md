# AQE ⟷ TradingView Community Strategies — Coverage Analysis

**Purpose:** map 22 open-source TradingView strategies (volume + momentum family)
against AQE's existing engine suite, decide what to **surface to the AIC**, and
identify genuine **additive** signals worth building. Reference for the committee.

**Legend:** ✅ **HAVE** (already computed) · 🟡 **PARTIAL** (concept present, a
specific twist missing) · 🔴 **GAP** (not in AQE).

---

## TL;DR (three findings)

1. **~15 of the 22 are already *inside* AQE — the AIC just can't see them.** AQE
   computes **~60 subcomponent scores every pre-market run** and persists them to
   `scores_daily.parquet`, but the export only ships the 5 aggregate engine scores.
   Squeeze, money-flow, exhaustion, ADX, relative strength, inside-bars, range
   expansion — all already scored, all hidden. **Surfacing them is a pure export
   change, zero new compute/FMP load** (your instinct is exactly right).
2. **Two genuine gaps**, both on data AQE *already has*: **price-vs-oscillator
   divergence** (3 strategies, #1 gap) and **SMC structure** — liquidity sweeps /
   order blocks / BOS-CHoCH (3 strategies, #2 gap).
3. **Minor adds:** momentum *acceleration* (2nd derivative), volume-validated
   pivots + CVD, pin-bar geometry.

---

## Family-by-family mapping (all 22)

### A. Squeeze / volatility compression — ✅ HAVE
| Strategy | What it does | AQE coverage |
|---|---|---|
| Squeeze Momentum [LazyBear] | The classic TTM squeeze: BB inside Keltner + linreg momentum histogram | ✅ `Energy.squeeze_score` (BB/KC squeeze) |
| Bollinger Squeeze Breakout + Volume | BB width < 0.8× its 50-avg → breakout on band close + volume | ✅ `Energy.squeeze_score` + `Flow.volume_score` |
| Cluster Breakout v8 | Tight range (`range10 ≤ 2×ATR`) + contracting vol → breakout | ✅ `Energy.squeeze_score` + `Readiness.rd_compression` / `rd_range_exp` |

**Verdict:** fully covered. The squeeze *concept* is `Energy.squeeze_score`;
compression/expansion is also in Readiness.

### B. Momentum oscillators — ✅ HAVE (accel = 🟡)
| Strategy | What it does | AQE coverage |
|---|---|---|
| Momentum Index [BigBeluga] | Sign-accumulation oscillator (bespoke TMI) | ✅ `MP` family (`abs_mom_score`, `roc_zscore`) |
| Momentum Shift [BigBeluga] | HMA of price-change, crossover → regime shift | ✅ `MP` + `mp_state` (BUILDING/FADING = "shift") |
| Momentum Acceleration [DGT] | velocity−acceleration (2nd deriv of ROC), price or OBV | 🟡 AQE has ROC **level** (`roc_zscore`), not its **rate-of-change** |

**Verdict:** momentum level & regime covered by MP. **Acceleration (2nd
derivative) is a small genuine add** — see §Adds.

### C. Fibonacci / OTE — ✅ HAVE
| Strategy | What it does | AQE coverage |
|---|---|---|
| Smart Money Fib OTE [ChartPrime] | Auto-fib on swings; highlights the 0.618–0.786 "OTE zone" + BOS lines | ✅ `bracket.fib_618`/`fib_786` **literally = the OTE zone**; 🟡 BOS flag missing |
| SamoAlgo AutoFib + EMA MTF | Fib retrace entry (0.7) / extension target (1.618) + MTF-EMA + ADX gate | ✅ `bracket` fib ladder + `pr_ma_score` + `MP.adx_val` |

**Verdict:** AQE already computes the full flat fib ladder
(`fib_236/382/500/618/786` + swing anchors) in the bracket engine. The "OTE zone"
is `fib_618`→`fib_786`.

### C-2. Pivot / swing S-R zones — 🟡 PARTIAL
| Strategy | What it does | AQE coverage |
|---|---|---|
| High Volume Pivot S/R [BigBeluga] | Pivots **validated by volume** (>1.2× avg) → ATR-padded zones + CVD | 🟡 `bracket` has swing pivots (`swing_low_1/2/3`, resistance); **volume-validation + CVD missing** |
| RSI Core Levels Heatmap [BigBeluga] | RSI-cross draws S/R at recent opposite candle | ✅ `bracket` structural levels + `pr_rsi_score` |
| Momentum-based ZigZag | Zigzag pivots flipped by MACD/MA/QQE + RSI exhaustion filter | ✅ `bracket` swing pivots + `MP` (direction) |

**Verdict:** pivots/levels covered; **volume-weighting the pivots** is a nice
enrichment (a level defended on high volume is a stronger level).

### D. Trend / MA-stack / HTF bias — ✅ HAVE
| Strategy | What it does | AQE coverage |
|---|---|---|
| Clean Trend System (HTF) | Triple-EMA stack + HTF bias + RSI + pullback/breakout | ✅ `pr_ma_score` (MA alignment) + `Structure.wk_score` (weekly trend) + `K39` (weekly gate = HTF bias) |
| Inside Bar Breakout + EMA | Inside bar → mother-bar breakout, EMA200 gate | ✅ `Readiness.rd_inside_bars` + `bracket` + MA |
| ATR Trailing Stop + EMA | Chandelier ATR trail + EMA200 gate | ✅ `bracket` structural stop (the retired DSL was the ATR-trail) |

**Verdict:** HTF bias = your K39 weekly gate + Structure weekly trend. (Note: two
of these TV scripts repaint via `lookahead_on` — AQE's weekly gate does not.)

### E. Exhaustion — ✅ HAVE
| Strategy | What it does | AQE coverage |
|---|---|---|
| EWO RSI Exhaustion | Elliott Wave Osc (SMA5−SMA34) + RSI + MFI + oversold-exhaustion latch | ✅ `Energy.exhaustion_score` + `Flow.ext_score` + `Flow.mfi` + Elder-context `exhaustion_check` |

**Verdict:** exhaustion is triple-covered. The EWO oscillator itself is just
another momentum lens (MP family).

### F. Candlestick patterns — 🟡 PARTIAL
| Strategy | What it does | AQE coverage |
|---|---|---|
| P.I.B. Pin Bar / Inside Bar | Pin-bar wick geometry + inside bar | 🟡 `Readiness.rd_inside_bars` ✅ inside bars; **pin-bar geometry missing** (adjacent: `Flow.ha_quality_count`) |

**Verdict:** inside bars already a Readiness subcomponent; pin-bar geometry is a
minor, low-value add.

### G. Divergence — 🔴 GAP (#1)
| Strategy | What it does | AQE coverage |
|---|---|---|
| RSI Momentum Divergence [ChartPrime] | RSI-of-momentum; price LL vs RSI HL (regular div) → zones | 🔴 **no divergence detector** |
| Multi-Divergence [GainzAlgo] | **7 oscillators** (RSI, MFI, Stoch, Zscore, ADX, MACD, OBV) each pivot-tested for regular divergence; self-grades which works | 🔴 **no divergence detector** (but **every input already exists** in AQE) |
| Multi-Asset Cross-TF Divergence | Asset-A vs Asset-B RSI-direction disagreement across TFs | 🟡 `Structure.rs_vs_spy` is the asset-vs-benchmark analog |

**Verdict:** **This is the clearest gap.** AQE has no price-vs-oscillator
divergence anywhere — yet it already computes RSI, `mfi`, `cmf`, `adx_val`,
MACD-equivalent momentum, and OBV-equivalent flow. A divergence layer is cheap
(pivots on price vs a scored oscillator) and genuinely new. **Top additive.**

### H. SMC — liquidity sweeps / order blocks / CHoCH — 🔴 GAP (#2)
| Strategy | What it does | AQE coverage |
|---|---|---|
| Mirage Liquidity Sweep | Wick through a swing low + reclaim → scored sweep; optional CHoCH confirm; wick-anchored stop | 🔴 no sweep/CHoCH detection |
| ML Smart Money [GainzAlgo] | CHoCH (trend flip on swing break) + **real kNN** (3 features, self-labeled outcomes) → directional probability | 🔴 no CHoCH; `Signal Radar` is the deterministic analog |
| Volume-Trend Order Block [BigBeluga] | Custom SuperTrend + order blocks split by buy/sell volume | 🔴 no order blocks |

**Verdict:** genuine gap, **but philosophically different** (SMC is
discretionary/contested; the "ML" here is honest but shallow kNN). AQE's swing
pivots are the foundation. The **cheapest, least-controversial slice = a BOS/CHoCH
flag** (trend flip when price breaks the last confirmed swing) — it complements the
bracket. Full sweep/order-block modeling is a Phase-2 call, not a slam-dunk.

---

## What AQE already computes but hides (the subcomponent goldmine)

`scores_daily.parquet` already carries these every run — surfacing them to the AIC
is a **pure export change** (structured, once-daily, ~0 load), the same pattern as
the `sc_m_gate_detail` breakdown already shipping:

| Engine | Subcomponents already scored (hidden from AIC) |
|---|---|
| **Flow** | `accum_score, volume_score, skew_score, ext_score, mfi, cmf, ha_quality_count` |
| **Energy** | `vp_position_score, price_action_score, squeeze_score, exhaustion_score, atr_score, en_pos50, en_trend_bars` |
| **Structure** | `rs_spy_score, rs_accel_score, base_score, ms_pos_score, resist_score, wk_score, earn_score, rs_vs_spy, rs_accel` |
| **MP** | `abs_mom_score, mp_adx_score, rel_mom_score, trend_score, roc_zscore, excess_return, adx_val, di_bullish` |
| **BQ** | `bq_range_tight, bq_vol_dry, bq_base_dur, bq_ema_conv, bq_base_days` |
| **Pipeline Rank** | `pr_ret_12m, pr_adx_score, pr_rsi_score, pr_vol_score, pr_ma_score` |
| **Readiness** | `rd_compression, rd_trigger, rd_inside_bars, rd_range_exp, rd_vol_surge, rd_close_str` |
| **Health** (held) | `hl_trend, hl_flow, hl_rs, hl_risk, hl_higher_lows, hl_atr_spike` |

**Each row shows how much of the TV set it already answers:** `squeeze_score`
(squeeze family), `mfi`/`cmf`/`volume_score` (volume family), `abs_mom_score`/
`adx_val`/`roc_zscore` (momentum family), `exhaustion_score`/`ext_score`
(exhaustion), `rd_inside_bars`/`rd_range_exp` (inside-bar/cluster), `rs_vs_spy`
(relative strength). The committee is flying blind on all of it today.

---

## Recommendations (priority order)

1. **Surface the subcomponents to the AIC** (do this first — highest value/effort).
   Add a per-record `subcomponents` block (nested by engine, like `bracket`) to the
   daily_list + held rows, sourced straight from `scores_daily`. Document each in
   `field_glossary`. Result: the AIC sees *why* an engine scored what it did — and
   ~15 of these 22 strategies become directly readable. **Zero new compute.**
2. **Build a divergence layer** (#1 real gap, deterministic, cheap). Per record:
   `divergence = {state: bullish/bearish/none, oscillators: [rsi, mfi, cmf, macd,
   obv], count, strength}`, computed as regular (and optionally hidden) divergence
   = price pivot vs oscillator pivot, on oscillators AQE already computes. Pure
   panel math, no new FMP. Grade it against forward outcomes the way Signal Radar
   is validated.
3. **Momentum acceleration** (small MP add). Add `mp_accel` = rate-of-change of
   `roc_zscore` (or velocity−acceleration à la DGT) — complements Signal Radar's
   pre-move by flagging momentum *inflecting* before the level confirms.
4. **Volume-validated pivots + CVD** (bracket enrichment). Tag each
   `structural_level` with the volume at its pivot bar (defended-on-volume = higher
   conviction) — makes the bracket's stop/target selection smarter.
5. **BOS/CHoCH flag** (cheapest SMC slice, optional). A `structure_shift` flag when
   price breaks the last confirmed swing — the transparent part of the SMC family.
   Defer full liquidity-sweep / order-block modeling (contested, heavier).
6. **Skip:** pin-bar geometry (low value), the "ML" kNN (AQE's deterministic Signal
   Radar is the philosophy-aligned analog), and anything requiring intraday
   repaint/lookahead (several TV scripts do — AQE is EOD-clean).

**Net:** you already own the substance of most of these. The leverage is
**(1) show the committee what you compute** and **(2) add divergence** — both on
data that's already in the nightly parquet.
