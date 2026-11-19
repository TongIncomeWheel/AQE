"""Component review, step 2: assemble tables/component_review_table.csv + blast radius + cluster list.
Evidence only: no recipe, no tuning. Flag rules are fixed here and written into the summary verbatim."""
import json, numpy as np, pandas as pd
from component_meta import META, UP, DERIVED

D = '/home/user/pma_run/deep_backtest/'
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]
H = (5, 10, 20)
RHO = 0.80

yb = pd.read_csv(D + 'scripts/_cr_ic_by_year.csv')
ex = pd.read_csv(D + 'scripts/_cr_exposure.csv').set_index('feature')
C = pd.read_csv(D + 'scripts/_cr_spearman.csv', index_col=0)
dist = pd.read_csv(D + 'scripts/_cr_distinct.csv').set_index('feature')
ncorr = pd.read_csv(D + 'scripts/_cr_corr_n.csv').set_index('feature')
names = [m[0] for m in META]
meta = {m[0]: m for m in META}

# ---------- clusters ----------
# (1) tight clusters: complete linkage on distance 1-|mean Spearman|, cut at 0.2, so EVERY pair inside has |rho| >= 0.8
# (2) chain groups: connected components of the |rho|>=0.8 graph (single linkage) - shows how far links chain
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform
Dm = 1 - C.abs().fillna(0).to_numpy(); np.fill_diagonal(Dm, 0); Dm = (Dm + Dm.T) / 2
lab = fcluster(linkage(squareform(Dm, checks=False), 'complete'), 1 - RHO, 'distance')
cl = pd.Series(lab, index=C.index)
def _stats(mem):
    sub = C.loc[mem, mem].to_numpy(); iu = np.triu_indices(len(mem), 1)
    return dict(members=mem, size=len(mem), mean_abs_rho=float(np.nanmean(np.abs(sub[iu]))),
                min_abs_rho=float(np.nanmin(np.abs(sub[iu]))), any_negative=bool((sub[iu] < 0).any()))
clusters = [_stats(list(v.index)) for _, v in cl.groupby(cl) if len(v) > 1]
clusters = sorted(clusters, key=lambda c: (-c['size'], -c['mean_abs_rho']))
cname = {m: f'C{i:02d}' for i, c in enumerate(clusters, 1) for m in c['members']}
A = np.nan_to_num(C.abs().to_numpy()); np.fill_diagonal(A, 0)
comp = -np.ones(len(C), int); k = 0
for i in range(len(C)):
    if comp[i] >= 0: continue
    stack = [i]; comp[i] = k
    while stack:
        j = stack.pop()
        for n in np.flatnonzero(A[j] >= RHO):
            if comp[n] < 0: comp[n] = k; stack.append(n)
    k += 1
comp = pd.Series(comp, index=C.index); csz = comp.value_counts()
chain = {f: (f'G{comp[f]:02d} ({csz[comp[f]]} cols)' if csz[comp[f]] > 1 else 'none') for f in C.index}

# ---------- per-feature evidence ----------
def g(f, mode, h, col):
    r = yb[(yb.feature == f) & (yb['mode'] == mode) & (yb.h == h)]
    return r[col].iloc[0] if len(r) else np.nan

rows = []
for f in names:
    _, level, parent, calc, scoring, weight, cons, src, gstat = meta[f]
    rec = dict(name=f, level=level, parent=parent, what_it_calculates=calc, what_high_value_should_show=scoring,
               weight_in_parent=weight, source=src, glossary_status=gstat)
    tmax = 0; ysig2 = 0; ysig3 = 0; flip_sig = False
    for mode in ('raw', 'neutral'):
        for h in H:
            rec[f'ic_{mode}_{h}d'] = g(f, mode, h, 'mean_ic')
            rec[f't_{mode}_{h}d'] = g(f, mode, h, 'nw_t')
            ics = np.array([g(f, mode, h, f'ic_{y}') for y in YEARS], float)
            ts = np.array([g(f, mode, h, f't_{y}') for y in YEARS], float)
            rec[f'years_pos_{mode}_{h}d'] = int(np.sum(ics > 0)) if np.isfinite(ics).any() else np.nan
            rec[f'years_with_data_{mode}_{h}d'] = int(np.isfinite(ics).sum())
            ysig2 += int(np.nansum(np.abs(ts) >= 2)); ysig3 += int(np.nansum(np.abs(ts) >= 3))
            if np.nanmax(ts, initial=-np.inf) >= 2 and np.nanmin(ts, initial=np.inf) <= -2:
                flip_sig = True
            t = rec[f't_{mode}_{h}d']
            if np.isfinite(t) and abs(t) > abs(tmax):
                tmax = t; rec['best_test'] = f'{mode} {h}d'
    for y in YEARS:
        rec[f'ic_neutral_10d_{y}'] = g(f, 'neutral', 10, f'ic_{y}')
    rec['max_abs_full_sample_t'] = abs(tmax)
    rec['year_cells_abs_t_ge2_of36'] = ysig2
    rec['year_cells_abs_t_ge3_of36'] = ysig3
    rec['n_dates_with_data'] = int(dist.loc[f, 'n_dates_present'])
    for kk in ('vol', 'dv', 'sector', 'all'):
        rec[f'var_share_{kk}'] = ex.loc[f, f'r2_{kk}']
    rec['n_distinct_values'] = int(dist.loc[f, 'n_distinct'])
    rec['modal_value'] = dist.loc[f, 'modal_value']; rec['modal_share'] = dist.loc[f, 'modal_share']
    rec['coverage_rows'] = dist.loc[f, 'coverage']
    # redundancy
    rr = C.loc[f].drop(f).abs()
    if rr.notna().any():
        tw = rr.idxmax(); rec['nearest_twin'] = tw; rec['nearest_twin_rho'] = float(C.loc[f, tw])
    rec['redundancy_cluster'] = cname.get(f, 'none')
    rec['cluster_members'] = ' | '.join(next((c['members'] for c in clusters if f in c['members']), []))
    rec['chain_group'] = chain[f]
    rec['corr_dates_used'] = int(ncorr.loc[f, 'n_dates_in_corr'])
    rec['_flip_sig'] = flip_sig
    rec['_cons'] = cons
    rows.append(rec)
T = pd.DataFrame(rows)

# ---------- flags (rules are fixed and documented) ----------
NEEDS = {
 'earn_score': 'history: varies across names on only 15 dates (2026-10-29 to 2026-11-18); constant 10.0 (the no-earnings-data default) on every earlier date, so IC/year tests are not computable',
 'pipe_tier': 'not point-in-time: tier of pipe_rank whose inputs are ranked inside TODAY\'s universe; was excluded from the earlier screen',
 'bd_mode': 'categorical (base type 0-4); rank-IC and rank correlation treat it as ordered, which it is not',
}
flags_all, primary = [], []
for _, r in T.iterrows():
    fl = []
    f = r['name']
    if f in NEEDS:
        fl.append('NEEDS_REVIEW')
    if abs(r.nearest_twin_rho) >= RHO if pd.notna(r.nearest_twin_rho) else False:
        fl.append('DUPLICATE')
    if r.var_share_vol > 0.5: fl.append('VOL_PROXY')
    if r.var_share_sector > 0.5: fl.append('SECTOR_PROXY')
    if r.var_share_dv > 0.5: fl.append('LIQUIDITY_PROXY')
    measurable = (r.max_abs_full_sample_t >= 2) or (r.year_cells_abs_t_ge3_of36 > 0)
    if f != 'earn_score':
        if not measurable:
            fl.append('DEAD')
        if r._flip_sig:
            fl.append('SIGN_FLIPS')
        elif measurable:
            mode, h = r.best_test.split(' ')
            pos = r[f'years_pos_{mode}_{h}']; n = r[f'years_with_data_{mode}_{h}']
            same = pos if r[f't_{mode}_{h}'] > 0 else n - pos
            if same <= n - 2:
                fl.append('SIGN_FLIPS')
    if r.n_distinct_values <= 5 or r.modal_share >= 0.80:
        fl.append('CONSTANT_OR_DISCRETE')
    order = ['NEEDS_REVIEW', 'DUPLICATE', 'VOL_PROXY', 'SECTOR_PROXY', 'LIQUIDITY_PROXY', 'DEAD', 'SIGN_FLIPS', 'CONSTANT_OR_DISCRETE']
    fl = [o for o in order if o in fl]
    flags_all.append(';'.join(fl) if fl else 'NONE')
    primary.append(fl[0] if fl else 'NONE')
T['primary_flag'] = primary; T['all_flags'] = flags_all
T['flag_note'] = [ (NEEDS[n] % T.loc[T.name == n, 'n_dates_with_data'].iloc[0] if '%d' in NEEDS[n] else NEEDS[n]) if n in NEEDS else '' for n in T.name]

# ---------- downstream + blast radius ----------
def parents_of(f):
    if f in DERIVED:
        return []
    p = meta[f][2].split(' ')[0]
    return [p] if (p in meta or p in UP) else []
def ancestors(f):
    seen, order, stack = set(), [], [f]
    while stack:
        x = stack.pop()
        nxt = []
        if x in meta:
            nxt += parents_of(x) + list(meta[x][6])
        nxt += UP.get(x, [])
        for y in nxt:
            key = y.split(' (')[0] if y not in UP and y not in meta else y
            if y not in seen:
                seen.add(y); order.append(y); stack.append(key if key in UP or key in meta else y)
    return order
T['used_downstream'] = [' ; '.join(parents_of(f) + list(meta[f][6])) or 'none found' for f in T.name]
def _dedupe(xs):
    out, seen = [], set()
    for x in xs:
        b = x.split(' (')[0]
        if b not in seen:
            seen.add(b); out.append(x)
    return out
T['blast_radius'] = [' ; '.join(_dedupe(ancestors(f))) or 'nothing downstream' for f in T.name]
T = T.drop(columns=['_flip_sig', '_cons'])

lead = ['name', 'level', 'parent', 'what_it_calculates', 'what_high_value_should_show', 'weight_in_parent', 'used_downstream',
        'primary_flag', 'all_flags', 'flag_note', 'redundancy_cluster', 'nearest_twin', 'nearest_twin_rho']
num = [c for c in T.columns if c not in lead and c not in ('cluster_members', 'chain_group', 'blast_radius', 'source', 'glossary_status')]
T = T[lead + num + ['cluster_members', 'chain_group', 'blast_radius', 'source', 'glossary_status']]
T.round(4).to_csv(D + 'tables/component_review_table.csv', index=False)
json.dump(clusters, open(D + 'scripts/_cr_clusters.json', 'w'), indent=1)
pd.set_option('display.width', 250, 'display.max_rows', 200, 'display.max_colwidth', 60)
print(T[['name', 'primary_flag', 'all_flags', 'max_abs_full_sample_t', 'year_cells_abs_t_ge3_of36', 'var_share_vol', 'var_share_dv', 'var_share_sector', 'n_distinct_values', 'modal_share', 'redundancy_cluster', 'nearest_twin', 'nearest_twin_rho']].round(3).to_string())
for c in clusters:
    print(c['size'], round(c['mean_abs_rho'], 3), round(c['min_abs_rho'], 3), c['members'])
from collections import Counter
print('primary', Counter(primary)); print('any', Counter(x for s in flags_all for x in s.split(';')))
