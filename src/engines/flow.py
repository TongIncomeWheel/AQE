"""Flow v1.3 — port of `sources/Flow_v1_3 (1).pine`.

Output:
    flow_100        ∈ [0, 100]
    flow_score, accum_score, volume_score, skew_score, ext (diagnostics)

Components (per Pine):
    flow_score    — MFI + CMF + Heikin-Ashi quality (max 17)
    accum_score   — A/D rolling-sum linreg short vs long (max 7.5)
    volume_score  — volume trend + spike (max 7.5)
    skew_score    — up/down volume ratio over 10 bars (max 3.5)
    ext           — extension ranging from −8 to +5

Composite (Pine 90-91):
    raw = clip(flow + accum + volume + skew + ext, 0, 38)
    flow_100 = raw / 38 * 100
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import utils as U


def compute(
    daily: pd.DataFrame,
    *,
    flow_length: int = 10,
    ha_lookback: int = 10,
    vol_period: int = 20,
) -> pd.DataFrame:
    d = daily.reset_index(drop=True).copy()
    open_ = d["open"].astype(float)
    high = d["high"].astype(float)
    low = d["low"].astype(float)
    close = d["close"].astype(float)
    volume = d["volume"].astype(float)
    hlc3 = (high + low + close) / 3.0
    n = len(close)

    # ---- Component 1: MFI + CMF + HA quality (Pine 12-40) ----
    # MFI: rolling sum over flow_length bars of v*hlc3, partitioned by hlc3 vs prev hlc3.
    p = hlc3.diff()  # hlc3[i] - hlc3[i+1] in Pine = current - previous
    # Pine: for i = 0 to flow_length - 1 → looks at the most recent `flow_length` bars
    #       where i=0 is current bar. Within each, compares hlc3[i] vs hlc3[i+1].
    # In pandas, that's a rolling window of `flow_length` bars on (v*hlc3, sign-of-p).
    mfi_up_contrib = (volume * hlc3).where(p > 0, 0.0)
    mfi_dn_contrib = (volume * hlc3).where(p <= 0, 0.0)
    mfi_sum_upper = mfi_up_contrib.rolling(flow_length, min_periods=flow_length).sum()
    mfi_sum_lower = mfi_dn_contrib.rolling(flow_length, min_periods=flow_length).sum()
    mfi = pd.Series(50.0, index=close.index)
    nz = mfi_sum_lower != 0
    mfi = mfi.where(~nz, 100.0 - (100.0 / (1.0 + mfi_sum_upper / mfi_sum_lower.replace(0.0, np.nan))))
    mfi = mfi.fillna(50.0)

    # CMF: rolling sum over flow_length bars of money-flow-volume / volume.
    rng = (high - low).replace(0.0, np.nan)
    mfv = ((close - low) - (high - close)) / rng * volume
    mfv = mfv.fillna(0.0)
    # Pine only sums volume for bars where high != low (non-zero range).
    vol_nonzero = volume.where(rng.notna(), 0.0)
    vol_in_window = vol_nonzero.rolling(flow_length, min_periods=flow_length).sum()
    cmf = mfv.rolling(flow_length, min_periods=flow_length).sum() / vol_in_window.replace(0.0, np.nan)
    cmf = cmf.fillna(0.0)

    # Pine line 31
    fl_fb = pd.Series(0.0, index=close.index)
    fl_fb = fl_fb.where(~((mfi > 38) | (cmf > -0.05)), 2.5)
    fl_fb = fl_fb.where(~((mfi > 42) & (cmf > 0)), 5.0)
    fl_fb = fl_fb.where(~((mfi > 48) & (cmf > 0.02)), 8.0)
    fl_fb = fl_fb.where(~((mfi > 55) & (cmf > 0.05)), 11.0)

    # HA quality (Pine 32-39). For each bar t, count bars k ∈ [t-ha_lookback+1, t] where
    #   |hc[k] − ho_k| < 0.5 * atr20[t]
    # with ho_k = (O[k] + C[k])/2 when k == t (i=0 case in Pine), else (O[k-1] + C[k-1])/2.
    # The ATR threshold uses bar t's ATR for the whole inner loop → per-bar threshold means
    # a regular rolling-sum doesn't work cleanly. Loop in numpy.
    atr_v = U.atr(high, low, close, n=20).to_numpy()
    hc_arr = ((open_ + high + low + close) / 4.0).to_numpy()
    o_arr = open_.to_numpy()
    c_arr = close.to_numpy()
    diff_current = np.abs(hc_arr - (o_arr + c_arr) / 2.0)               # for k == t branch
    ho_lagged = (np.roll(o_arr, 1) + np.roll(c_arr, 1)) / 2.0
    ho_lagged[0] = np.nan
    diff_lagged = np.abs(hc_arr - ho_lagged)                            # for k < t branch
    hac_arr = np.zeros(n, dtype=float)
    for t in range(ha_lookback - 1, n):
        thr = 0.5 * atr_v[t]
        if np.isnan(thr):
            continue
        count = 0
        # i = 0: current bar uses diff_current.
        if not np.isnan(diff_current[t]) and diff_current[t] < thr:
            count += 1
        # i = 1 .. ha_lookback-1: earlier bars use diff_lagged.
        for i in range(1, ha_lookback):
            k = t - i
            d_val = diff_lagged[k]
            if not np.isnan(d_val) and d_val < thr:
                count += 1
        hac_arr[t] = count
    hac = pd.Series(hac_arr, index=close.index)
    ha_b = pd.Series(0.0, index=close.index)
    ha_b = ha_b.where(~(hac >= 2), 2.0)
    ha_b = ha_b.where(~(hac >= 3), 4.0)
    ha_b = ha_b.where(~(hac >= 5), 6.0)

    flow_score = (fl_fb + ha_b).clip(upper=17.0)

    # ---- Component 2: Accumulation A/D linreg (Pine 42-50) ----
    ad_raw = pd.Series(0.0, index=close.index)
    nonzero_rng = (high != low) & ~((close == high) & (close == low))
    ad_raw = (((2.0 * close - low - high) / (high - low).replace(0.0, np.nan)) * volume).where(nonzero_rng, 0.0)
    ad_raw = ad_raw.fillna(0.0)
    ad = ad_raw.rolling(60, min_periods=60).sum()
    ad_s = U.linreg_endpoint(ad, 10)
    ad_l = U.linreg_endpoint(ad, 20)
    accum_score = pd.Series(0.0, index=close.index)
    accum_score = accum_score.where(~(ad_s > 0), 1.5)
    accum_score = accum_score.where(~((ad_l != 0) & (ad_s > ad_l * 0.85)), 3.0)
    accum_score = accum_score.where(~((ad_l != 0) & (ad_s > ad_l)), 5.5)
    accum_score = accum_score.where(~((ad_l != 0) & (ad_s > ad_l * 1.1)), 7.5)

    # ---- Component 3: Volume trend + spike (Pine 52-59) ----
    v5 = U.sma(volume, 5)
    v20 = U.sma(volume, vol_period)
    vtr = (v5 / v20.replace(0.0, np.nan)).fillna(1.0)
    spk = (volume / v20.replace(0.0, np.nan)).fillna(1.0)
    spk_b = pd.Series(0.0, index=close.index)
    spk_b = spk_b.where(~(spk > 1.5), 1.0)
    spk_b = spk_b.where(~(spk > 2.0), 2.0)
    vt_b = pd.Series(0.0, index=close.index)
    vt_b = vt_b.where(~(vtr > 0.9), 2.0)
    vt_b = vt_b.where(~(vtr > 1.05), 4.0)
    vt_b = vt_b.where(~(vtr > 1.2), 5.5)
    volume_score = (vt_b + spk_b).clip(upper=7.5)

    # ---- Component 4: Volume Skew (Pine 61-70) ----
    # uv = sum of volume[i] for i in 0..9 where close[i] > close[i+1]; else dv.
    close_diff = close.diff()
    uv_contrib = volume.where(close_diff > 0, 0.0)
    dv_contrib = volume.where(close_diff <= 0, 0.0)
    uv = uv_contrib.rolling(10, min_periods=10).sum()
    dv = dv_contrib.rolling(10, min_periods=10).sum()
    udr = (uv / dv.replace(0.0, np.nan)).fillna(1.0)
    skew_score = pd.Series(0.0, index=close.index)
    skew_score = skew_score.where(~(udr >= 0.8), 1.5)
    skew_score = skew_score.where(~(udr > 1.2), 2.5)
    skew_score = skew_score.where(~(udr > 1.5), 3.5)

    # ---- Extension (Pine 72-87) ----
    h20 = U.highest(high, 20)
    h20p = U.highest(high.shift(1), 20)
    is_nh = high >= h20p
    l20 = U.lowest(low, 20)
    rng20 = h20 - l20
    pp = pd.Series(50.0, index=close.index)
    nz_rng = rng20 != 0
    pp = pp.where(~nz_rng, (close - l20) / rng20.replace(0.0, np.nan) * 100.0)
    pp = pp.fillna(50.0)
    ema20 = U.ema(close, 20)
    de = ((close - ema20) / ema20.replace(0.0, np.nan) * 100.0).fillna(0.0)
    cr = ((close - low) / (high - low).replace(0.0, np.nan)).fillna(0.5)
    vr = (volume / v20.replace(0.0, np.nan)).fillna(1.0)
    r5 = U.highest(high, 5) - U.lowest(low, 5)
    tra = U.sma(U.true_range(high, low, close), 20)
    ra20 = tra * 5.0
    isc = (r5 / ra20.replace(0.0, np.nan)) < 0.6
    isc = isc.fillna(False)

    # Pine ternary: ext = is_nh and vr>1.5 and cr>0.6 ? 5.0 :
    #               pp>85 and vr>1.2 and cr>0.5 ? 3.0 :
    #               de>12 and vr>2.0 and cr<0.4 ? -8.0 :
    #               de>8 and not isc and cr<0.4 ? -5.0 :
    #               pp<25 ? 3.0 : 0.0
    ext = pd.Series(0.0, index=close.index)
    # Build top-down (later assignments win the spot if the prior branch hadn't yet matched).
    # Iterate from last branch upward.
    cond_pp_low = pp < 25
    ext = ext.where(~cond_pp_low, 3.0)
    cond_de_med_neg = (de > 8) & ~isc & (cr < 0.4)
    ext = ext.where(~cond_de_med_neg, -5.0)
    cond_de_hi_neg = (de > 12) & (vr > 2.0) & (cr < 0.4)
    ext = ext.where(~cond_de_hi_neg, -8.0)
    cond_pp_hi = (pp > 85) & (vr > 1.2) & (cr > 0.5)
    ext = ext.where(~cond_pp_hi, 3.0)
    cond_new_high = is_nh & (vr > 1.5) & (cr > 0.6)
    ext = ext.where(~cond_new_high, 5.0)

    # ---- Composite (Pine 89-91) ----
    raw = (flow_score + accum_score + volume_score + skew_score + ext).clip(lower=0.0, upper=38.0)
    flow_100 = raw / 38.0 * 100.0
    # Warmup: 60-bar rolling sum for A/D needs 60 bars, plus 20-bar linreg on it = 80 bars.
    warm = ad_l.notna() & v20.notna() & mfi_sum_lower.notna()
    flow_100 = flow_100.where(warm, np.nan)

    return pd.DataFrame({
        "date": d["date"],
        "flow_100": flow_100,
        "flow_score": flow_score,
        "accum_score": accum_score,
        "volume_score": volume_score,
        "skew_score": skew_score,
        "ext_score": ext,
        "mfi": mfi,
        "cmf": cmf,
        "ha_quality_count": hac,
    })
