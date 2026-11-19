"""How much of each feature is volatility / liquidity / sector: mean per-date rank correlation with vol and $vol, and
share of cross-sectional rank variance explained by vol+$vol+sector."""
import numpy as np, pandas as pd
from lib import *
df = load(); T = df.g.max() + 1; g = df.g.to_numpy()
R = pd.read_parquet(D + 'scripts/_ranks.parquet'); N = pd.read_parquet(D + 'scripts/_ranks_neut.parquet')
FE = [f for f in FEATS if f != 'earn_score']
ic = pd.read_csv(D + 'tables/ic_raw_vs_neutral.csv', index_col=0)
rows = []
for f in FE:
    cv = np.nanmean(daily_ic(g, R[f].to_numpy(), R['vol_20d_ann_pit'].to_numpy(), T))
    cd = np.nanmean(daily_ic(g, R[f].to_numpy(), R['log_dv'].to_numpy(), T))
    x = R[f].to_numpy(); r = N[f].to_numpy(); m = ~np.isnan(x)
    r2 = 1 - np.nansum(r[m] ** 2) / np.nansum(x[m] ** 2)
    rows.append(dict(feature=f, rankcorr_vol=cv, rankcorr_dollarvol=cd, r2_vol_dv_sector=r2,
                     ic10_raw=ic.loc[f, 'mean_ic_raw_10'], t10_raw=ic.loc[f, 'nw_t_raw_10'], ic10_neutral=ic.loc[f, 'mean_ic_neutral_10'], t10_neutral=ic.loc[f, 'nw_t_neutral_10'],
                     ic20_raw=ic.loc[f, 'mean_ic_raw_20'], t20_raw=ic.loc[f, 'nw_t_raw_20'], ic20_neutral=ic.loc[f, 'mean_ic_neutral_20'], t20_neutral=ic.loc[f, 'nw_t_neutral_20']))
out = pd.DataFrame(rows).sort_values('r2_vol_dv_sector', ascending=False)
out.round(3).to_csv(D + 'tables/feature_exposures.csv', index=False)
pd.set_option('display.width', 250); print(out.round(3).head(25).to_string())
