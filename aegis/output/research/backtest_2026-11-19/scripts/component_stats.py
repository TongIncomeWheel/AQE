"""Component review, step 1: the numbers. Read-only on the AQE repo.
Writes scripts/_cr_*.parquet/csv intermediates consumed by component_table.py.

  - pipe_tier (dropped from the earlier screen) is rebuilt from the extract and screened with the SAME lib functions
  - per-year Newey-West t of the daily rank-IC, raw + neutral, h=5/10/20 (from _daily_ic.pkl)
  - share of cross-sectional rank variance explained by vol alone, $vol alone, sector alone, and all three
  - mean per-date Spearman matrix over >=150 randomly sampled dates
  - distinct-value count and modal share on the raw values
"""
import numpy as np, pandas as pd
from lib import *

rng = np.random.default_rng(20261119)
df = load(); T = df.g.max() + 1; g = df.g.to_numpy()
yr_of_g = df.groupby('g').year.first().to_numpy()
years = sorted(df.year.unique())
R = pd.read_parquet(D + 'scripts/_ranks.parquet')
N = pd.read_parquet(D + 'scripts/_ranks_neut.parquet')
daily = pd.read_pickle(D + 'scripts/_daily_ic.pkl')

# ---- pipe_tier: rebuild and screen ----
x = pd.read_parquet(D + 'data/aqe_research_extract_2026-11-19.parquet', columns=['date', 'ticker', 'pipe_tier'])
x['pipe_tier'] = x.pipe_tier.map({'D-SKIP': 0, 'C-WATCH': 1, 'B-STRONG': 2, 'A-TIER': 3}).astype('float32')
df = df.merge(x, on=['date', 'ticker'], how='left', validate='1:1')
assert (df.g.diff().fillna(0) >= 0).all()
rpt = cs_rank(df, ['pipe_tier'])
R['pipe_tier'] = rpt['pipe_tier']
N['pipe_tier'] = neutralise(df, R, ['pipe_tier'])['pipe_tier']
rows = []
for mode, M in (('raw', R), ('neutral', N)):
    for h in H:
        ic = daily_ic(g, M['pipe_tier'].to_numpy(), M[f'fwd{h}_vs_ew'].to_numpy(), T)
        daily[(mode, h, 'pipe_tier')] = ic
FE = FEATS + ['pipe_tier']

# ---- per-year stats for every feature ----
yrows = []
for (mode, h, f), ic in daily.items():
    if f not in FE:
        continue
    mu, t, n = nw_t(ic, h) if np.isfinite(ic).sum() > 30 else (np.nan, np.nan, 0)
    rec = dict(feature=f, mode=mode, h=h, mean_ic=mu, nw_t=t, n_dates=n)
    for Y in years:
        s = ic[yr_of_g == Y]
        if np.isfinite(s).sum() > 30:
            m_, t_, n_ = nw_t(s, h)
        else:
            m_, t_, n_ = np.nan, np.nan, 0
        rec[f'ic_{Y}'] = m_; rec[f't_{Y}'] = t_; rec[f'n_{Y}'] = n_
    yrows.append(rec)
pd.DataFrame(yrows).to_csv(D + 'scripts/_cr_ic_by_year.csv', index=False)
print('per-year IC done')

# ---- variance explained: vol alone, $vol alone, sector alone, all ----
vr = R['vol_20d_ann_pit'].to_numpy(); dr = R['log_dv'].to_numpy()
sec = pd.get_dummies(df.sector_etf_current).to_numpy(dtype='float32')
Y = R[FE].to_numpy(dtype='float32'); Ymask = ~np.isnan(Y)
bounds = np.r_[0, np.flatnonzero(np.diff(g)) + 1, len(df)]
ss_tot = np.zeros(len(FE)); ss_res = {k: np.zeros(len(FE)) for k in ('vol', 'dv', 'sector', 'all')}
for a, b in zip(bounds[:-1], bounds[1:]):
    y = Y[a:b]; m = Ymask[a:b]
    one = np.ones((b - a, 1), dtype='float32')
    S = sec[a:b]; S = S[:, S.sum(0) > 0]
    designs = {'vol': np.column_stack([one, vr[a:b]]), 'dv': np.column_stack([one, dr[a:b]]), 'sector': S,
               'all': np.column_stack([vr[a:b], dr[a:b], S])}
    for j in range(len(FE)):
        mj = m[:, j]
        if mj.sum() < 30:
            continue
        yj = y[mj, j].astype('float64')
        yc = yj - yj.mean()
        ss_tot[j] += yc @ yc
        for k, X in designs.items():
            Xj = np.nan_to_num(X[mj].astype('float64'))
            beta, *_ = np.linalg.lstsq(Xj, yj, rcond=None)
            r = yj - Xj @ beta
            ss_res[k][j] += r @ r
ex = pd.DataFrame({'feature': FE, **{f'r2_{k}': 1 - ss_res[k] / ss_tot for k in ss_res}})
ex.to_csv(D + 'scripts/_cr_exposure.csv', index=False)
print(ex.round(3).sort_values('r2_all').tail(12).to_string())

# ---- mean per-date Spearman over sampled dates ----
valid_g = np.flatnonzero(np.bincount(g, minlength=T) >= 200)
samp = np.sort(rng.choice(valid_g, size=200, replace=False))
acc = np.zeros((len(FE), len(FE))); cnt = np.zeros_like(acc)
RR = R[FE]
for gg in samp:
    a, b = bounds[gg], bounds[gg + 1]
    c = RR.iloc[a:b].corr(min_periods=50).to_numpy()   # Pearson of per-date ranks == Spearman
    ok = np.isfinite(c)
    acc[ok] += c[ok]; cnt[ok] += 1
C = pd.DataFrame(acc / np.where(cnt == 0, np.nan, cnt), index=FE, columns=FE)
C.to_csv(D + 'scripts/_cr_spearman.csv')
pd.Series(df.date.drop_duplicates().sort_values().to_numpy()[samp]).to_csv(D + 'scripts/_cr_spearman_dates.csv', index=False, header=['date'])
pd.DataFrame({'feature': FE, 'n_dates_in_corr': [int(np.nanmax(cnt[i])) for i in range(len(FE))]}).to_csv(D + 'scripts/_cr_corr_n.csv', index=False)

# ---- distinctness ----
dv = []
for f in FE:
    s = df[f].dropna()
    vc = s.value_counts(normalize=True)
    dv.append(dict(feature=f, n_distinct=int(s.nunique()), modal_value=float(vc.index[0]) if len(vc) else np.nan,
                   modal_share=float(vc.iloc[0]) if len(vc) else np.nan, coverage=float(df[f].notna().mean()),
                   n_dates_present=int(df.loc[df[f].notna(), 'g'].nunique())))
pd.DataFrame(dv).to_csv(D + 'scripts/_cr_distinct.csv', index=False)
print('done')
