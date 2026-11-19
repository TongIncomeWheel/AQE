"""Is the bull-regime recipe (rank bq_ema_conv asc, SPY>200DMA) just a volatility/sector tilt? Compare picks' vol vs
universe, and re-run with the vol/$vol/sector-neutralised rank of bq_ema_conv."""
import numpy as np, pandas as pd, sys
sys.argv = ['x', 'bull']
import recipe as R
ex = pd.read_csv(R.D + 'tables/feature_exposures.csv').set_index('feature').loc['bq_ema_conv']
N = pd.read_parquet(R.D + 'scripts/_ranks_neut.parquet', columns=['bq_ema_conv'])['bq_ema_conv'].to_numpy('float64')
df = R.df; out = []
P = pd.read_csv(R.D + 'tables/recipe_picks_bull.csv')
vol_pick = df.set_index(['date', 'ticker']).loc[pd.MultiIndex.from_frame(P[['date', 'ticker']].assign(date=pd.to_datetime(P.date)))].vol_20d_ann_pit
print('median vol picks', vol_pick.median(), 'universe', df.vol_20d_ann_pit.median(), 'rank corr w vol', ex.rankcorr_vol)
o = np.lexsort((R.TIE, np.where(np.isnan(N), np.inf, N), R.g))
for lab, dm in (('train', R.TRAIN), ('validation 2024', R.VALD), ('test 2025-26', R.TEST)):
    rows = R.picks({('n', 1): o}, 'n', 1, dm[R.g].copy())
    for e in R.evaluate(rows, dm, lab): e['rule'] = 'SPY>200DMA only: rank vol/$vol/sector-NEUTRALISED bq_ema_conv asc, top20'; out.append(e)
    # also: low-vol-matched alternative = rank by vol itself (pure vol tilt) for comparison
    v = df.vol_20d_ann_pit.to_numpy('float64'); ov = np.lexsort((R.TIE, -np.nan_to_num(v, nan=-1), R.g))
    for e in R.evaluate(R.picks({('v', 1): ov}, 'v', 1, dm[R.g].copy()), dm, lab): e['rule'] = 'SPY>200DMA only: top20 highest 20d vol (pure vol tilt, comparison)'; out.append(e)
o2 = pd.DataFrame(out); o2.round(4).to_csv(R.D + 'tables/bull_recipe_vol_check.csv', index=False)
pd.set_option('display.width', 250); print(o2.drop(columns='rule').round(4).to_string()); print(o2.rule.unique())
