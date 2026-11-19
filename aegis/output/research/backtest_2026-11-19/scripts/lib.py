import numpy as np, pandas as pd, json
D = '/home/user/pma_run/deep_backtest/'
COLS = json.load(open(D + 'scripts/_cols.json'))
FEATS = COLS['FEATS']
H = (5, 10, 20)


def load():
    df = pd.read_parquet(D + 'scripts/_panel.parquet')
    df['g'] = df.date.factorize(sort=True)[0]
    return df


def cs_rank(df, cols):
    """Per-date percentile rank centred on 0 (NaN stays NaN)."""
    r = df.groupby('g')[cols].rank(pct=True, method='average')
    cnt = df.groupby('g')[cols].transform('count')
    return (r - 0.5 * (1 + 1 / cnt)).astype('float32')


def daily_ic(g, x, y, T):
    """Per-date Pearson of centred ranks x,y (arrays), NaN-safe."""
    m = ~(np.isnan(x) | np.isnan(y))
    gg, xx, yy = g[m], x[m], y[m]
    n = np.bincount(gg, minlength=T).astype(float)
    sx = np.bincount(gg, xx, T); sy = np.bincount(gg, yy, T)
    sxx = np.bincount(gg, xx * xx, T); syy = np.bincount(gg, yy * yy, T); sxy = np.bincount(gg, xx * yy, T)
    with np.errstate(invalid='ignore', divide='ignore'):
        cov = sxy - sx * sy / n; vx = sxx - sx ** 2 / n; vy = syy - sy ** 2 / n
        ic = cov / np.sqrt(vx * vy)
    ic[n < 30] = np.nan
    return ic


def nw_t(s, lag):
    s = s[~np.isnan(s)]
    n = len(s); mu = s.mean(); e = s - mu
    v = e @ e / n
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1)
        v += 2 * w * (e[k:] @ e[:-k]) / n
    return mu, mu / np.sqrt(v / n), n


def nonoverlap_t(s, h):
    """t-stat on every h-th date, averaged over the h possible offsets (each offset is an independent-ish sample)."""
    ts = []
    for o in range(h):
        x = s[o::h]; x = x[~np.isnan(x)]
        ts.append(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))
    return float(np.mean(ts))


def neutralise(df, R, cols):
    """Residualise centred-rank columns per date on vol rank, $vol rank, sector dummies."""
    out = np.zeros((len(df), len(cols)), dtype='float32')
    vr = R['vol_20d_ann_pit'].to_numpy(); dr = R['log_dv'].to_numpy()
    sec = pd.get_dummies(df.sector_etf_current).to_numpy(dtype='float32')
    Y = R[cols].to_numpy(dtype='float32')
    Y = np.where(np.isnan(Y), 0, Y)
    bounds = np.r_[0, np.flatnonzero(np.diff(df.g.to_numpy())) + 1, len(df)]
    for a, b in zip(bounds[:-1], bounds[1:]):
        X = np.column_stack([vr[a:b], dr[a:b], sec[a:b]])  # sector dummies span the intercept
        X = X[:, np.r_[True, True, X[:, 2:].sum(0) > 0]]   # drop empty sectors to stay full rank
        X = np.where(np.isnan(X), 0, X)
        Q, _ = np.linalg.qr(X)
        y = Y[a:b]
        out[a:b] = y - Q @ (Q.T @ y)
    res = pd.DataFrame(out, columns=cols, index=df.index)
    res[R[cols].isna().to_numpy()] = np.nan
    return res
