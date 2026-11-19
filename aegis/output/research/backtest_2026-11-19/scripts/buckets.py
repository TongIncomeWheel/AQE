"""Step 2b/4: top-quintile hit-rate lift (single, pairs, triples) and regime splits.
Hit = stock beats the equal-weight universe (fwd_vs_ew>0). Lift = picks' hit rate minus the hit rate of ALL eligible
names that same date. Inference: Newey-West on the daily lift series with lag = horizon."""
import numpy as np, pandas as pd, itertools
from lib import *

df = load(); T = df.g.max() + 1; g = df.g.to_numpy()
yr_of_g = df.groupby('g').year.first().to_numpy()
ic = pd.read_csv(D + 'tables/ic_raw_vs_neutral.csv', index_col=0)
FE = [f for f in FEATS if f != 'earn_score']   # earn_score varies only Oct-Nov 2026: no history
AGG = ['flow_100', 'energy_100', 'structure_100', 'mp_100', 'elder_score', 'bq_100', 'k39_value', 'k39_gate', 'mp_state', 'impulse_state']
top_sub = ic.loc[[f for f in ic.index if f in FE and f not in AGG]].assign(a=lambda x: x.nw_t_raw_10.abs()).sort_values('a', ascending=False).index[:8].tolist()
SET = AGG + top_sub

# winsorise forward excess returns per date at 1/99 pct for means (bad prints exist, e.g. 9x 5-day moves)
for h in H:
    for b in ('ew', 'spy'):
        c = f'fwd{h}_vs_{b}'
        lo = df.groupby('g')[c].transform(lambda s: s.quantile(.01)); hi = df.groupby('g')[c].transform(lambda s: s.quantile(.99))
        df[c + '_w'] = df[c].clip(lo, hi)
df[[c for c in df.columns if c.endswith('_w')] + ['g']].to_parquet(D + 'scripts/_wins.parquet')

# top-quintile flags (designed direction: high = good) and bottom-quintile flags
flags = {}
for f in FE:
    q80 = df.groupby('g')[f].transform(lambda s: s.quantile(.8)); q20 = df.groupby('g')[f].transform(lambda s: s.quantile(.2))
    flags[(f, 'top')] = (df[f] >= q80).to_numpy()
    flags[(f, 'bot')] = (df[f] <= q20).to_numpy()
pd.to_pickle(flags, D + 'scripts/_flags.pkl')

hit = {h: (df[f'fwd{h}_vs_ew'] > 0).to_numpy().astype(float) for h in H}
hitspy = {h: (df[f'fwd{h}_vs_spy'] > 0).to_numpy().astype(float) for h in H}
valid = {h: df[f'fwd{h}_vs_ew'].notna().to_numpy() for h in H}
base = {h: np.bincount(g[valid[h]], hit[h][valid[h]], T) / np.bincount(g[valid[h]], minlength=T) for h in H}
exw = {h: df[f'fwd{h}_vs_ew_w'].to_numpy() for h in H}
regs = {c: df.groupby('g')[c].first().to_numpy() for c in ('reg_trend', 'reg_vol', 'reg_mom')}


def evaluate(mask, label, h, dmask=None):
    m = mask & valid[h]
    n = np.bincount(g[m], minlength=T).astype(float)
    hr = np.bincount(g[m], hit[h][m], T) / np.where(n > 0, n, np.nan)
    hs = np.bincount(g[m], hitspy[h][m], T) / np.where(n > 0, n, np.nan)
    ex = np.bincount(g[m], exw[h][m], T) / np.where(n > 0, n, np.nan)
    ok = n >= 5
    if dmask is not None: ok &= dmask
    lift = np.where(ok, hr - base[h], np.nan)
    if np.sum(ok) < 60: return None
    mu, t, nd = nw_t(lift, h)
    _, tex, _ = nw_t(np.where(ok, ex, np.nan), h)
    yl = {int(Y): np.nanmean(lift[yr_of_g == Y]) if np.any(ok & (yr_of_g == Y)) else np.nan for Y in range(2021, 2027)}
    return dict(rule=label, h=h, avg_names=np.nanmean(np.where(ok, n, np.nan)), n_dates=int(nd), hit_rate=np.nanmean(np.where(ok, hr, np.nan)),
                base_rate=np.nanmean(np.where(ok, base[h], np.nan)), lift=mu, lift_nw_t=t, hit_vs_spy=np.nanmean(np.where(ok, hs, np.nan)),
                mean_ex_ew_wins=np.nanmean(np.where(ok, ex, np.nan)), ex_nw_t=tex,
                years_lift_pos=sum(v > 0 for v in yl.values() if not np.isnan(v)), **{f'lift_{k}': v for k, v in yl.items()})


# A. single features, both tails
rows = []
for f in FE:
    for side in ('top', 'bot'):
        for h in H:
            r = evaluate(flags[(f, side)], f'{f}:{side}20%', h)
            if r: rows.append(r)
single = pd.DataFrame(rows).sort_values(['h', 'lift_nw_t'], ascending=[True, False])
single.round(4).to_csv(D + 'tables/quintile_single.csv', index=False)

# B. conjunctions of top quintiles among SET (pairs + triples)
rows = []
for k in (2, 3):
    for combo in itertools.combinations(SET, k):
        m = np.logical_and.reduce([flags[(f, 'top')] for f in combo])
        for h in (10, 20):
            r = evaluate(m, ' & '.join(f'{f}:top20%' for f in combo), h)
            if r: rows.append(r)
conj = pd.DataFrame(rows).sort_values('lift_nw_t', ascending=False)
conj.round(4).to_csv(D + 'tables/conjunctions_top_quintile.csv', index=False)
print('conjunctions tested:', len(conj), ' |t|>=3:', (conj.lift_nw_t.abs() >= 3).sum(), ' t>=3 and >=5/6 yrs pos:', ((conj.lift_nw_t >= 3) & (conj.years_lift_pos >= 5)).sum())

# C. regimes: IC and top-quintile lift for every feature within each regime half
daily = pd.read_pickle(D + 'scripts/_daily_ic.pkl')
rows = []
for rc, rv in regs.items():
    for lab in np.unique(rv):
        dm = rv == lab
        for f in FE:
            for h in (10, 20):
                s = np.where(dm, daily[('raw', h, f)], np.nan)
                mu, t, nd = nw_t(s, h)
                yrs = [np.nanmean(s[yr_of_g == Y]) for Y in range(2021, 2027) if np.any(dm & (yr_of_g == Y))]
                r = evaluate(flags[(f, 'top')], f, h, dm)
                rows.append(dict(regime=rc, state=lab, feature=f, h=h, n_dates=nd, mean_ic=mu, ic_nw_t=t,
                                 ic_years_same_sign=f'{sum(np.sign(y) == np.sign(mu) for y in yrs if not np.isnan(y))}/{len(yrs)}',
                                 top20_hit=r and r['hit_rate'], top20_lift=r and r['lift'], top20_lift_t=r and r['lift_nw_t']))
reg = pd.DataFrame(rows)
reg.round(4).to_csv(D + 'tables/regime_ic.csv', index=False)
pd.set_option('display.width', 250, 'display.max_rows', 200)
print(single[single.h == 10].head(15)[['rule', 'avg_names', 'hit_rate', 'base_rate', 'lift', 'lift_nw_t', 'mean_ex_ew_wins', 'years_lift_pos']].round(4).to_string())
print(single[single.h == 20].head(10)[['rule', 'avg_names', 'hit_rate', 'base_rate', 'lift', 'lift_nw_t', 'mean_ex_ew_wins', 'years_lift_pos']].round(4).to_string())
print(conj.head(15)[['rule', 'h', 'avg_names', 'hit_rate', 'base_rate', 'lift', 'lift_nw_t', 'mean_ex_ew_wins', 'years_lift_pos']].round(4).to_string())
print(conj.tail(5)[['rule', 'h', 'avg_names', 'hit_rate', 'lift', 'lift_nw_t', 'years_lift_pos']].round(4).to_string())
rr = reg.assign(a=reg.ic_nw_t.abs()).sort_values('a', ascending=False)
print('regime cells:', len(reg), ' |IC t|>=3:', (reg.ic_nw_t.abs() >= 3).sum())
print(rr.head(25).drop(columns='a').round(4).to_string())
