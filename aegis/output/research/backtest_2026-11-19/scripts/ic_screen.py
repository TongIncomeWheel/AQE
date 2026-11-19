"""Step 2+3: single-feature rank-IC screen, raw and vol/sector/$vol-neutralised. Writes tables/ic_screen_*.csv"""
import numpy as np, pandas as pd
from lib import *

df = load(); T = df.g.max() + 1; g = df.g.to_numpy()
years = sorted(df.year.unique())
REFS = COLS['REF'] + ['vol_20d_ann_pit', 'log_dv']
tg = [f'fwd{h}_vs_ew' for h in H]
allc = FEATS + REFS + tg
R = cs_rank(df, allc)
R.to_parquet(D + 'scripts/_ranks.parquet')
N = neutralise(df, R, FEATS + COLS['REF'] + tg)
N.to_parquet(D + 'scripts/_ranks_neut.parquet')
yr_of_g = df.groupby('g').year.first().to_numpy()

rows = []; daily = {}
for mode, M, feats in (('raw', R, FEATS + REFS), ('neutral', N, FEATS + COLS['REF'])):
    for h in H:
        y = M[f'fwd{h}_vs_ew'].to_numpy()
        for f in feats:
            ic = daily_ic(g, M[f].to_numpy(), y, T)
            daily[(mode, h, f)] = ic
            mu, t, n = nw_t(ic, h)
            yr = {int(Y): np.nanmean(ic[yr_of_g == Y]) for Y in years}
            same = sum(np.sign(v) == np.sign(mu) for v in yr.values())
            rows.append(dict(mode=mode, h=h, feature=f, kind=('REFERENCE' if f in REFS else 'allowed'),
                             mean_ic=mu, nw_t=t, nonoverlap_t=nonoverlap_t(ic, h), n_dates=n, eff_n=n / h,
                             ic_pos_share=np.nanmean(ic > 0), years_same_sign=same,
                             **{f'ic_{k}': v for k, v in yr.items()}))
res = pd.DataFrame(rows)
res['passes'] = (res.years_same_sign >= 5) & (res.nw_t.abs() >= 2) & (res.nonoverlap_t.abs() >= 2)
for mode in ('raw', 'neutral'):
    out = res[res['mode'] == mode].sort_values(['h', 'nw_t'], key=lambda s: s if s.name == 'h' else -s.abs())
    out.round(4).to_csv(D + f'tables/ic_screen_{mode}.csv', index=False)
# side by side at fwd10/fwd20
w = res.pivot_table(index='feature', columns=['mode', 'h'], values=['mean_ic', 'nw_t', 'years_same_sign', 'passes'], aggfunc='first')
w.columns = [f'{a}_{b}_{c}' for a, b, c in w.columns]
w = w.sort_values('nw_t_raw_20', key=abs, ascending=False)
w.round(4).to_csv(D + 'tables/ic_raw_vs_neutral.csv')
pd.to_pickle(daily, D + 'scripts/_daily_ic.pkl')
pd.set_option('display.width', 250, 'display.max_rows', 300)
print(w[[c for c in w.columns if c.endswith('_20') or c.endswith('_5')]].round(3).to_string())
