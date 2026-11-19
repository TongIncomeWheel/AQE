"""Step 5/6: frozen recipe search on 2021-03..2023-12, report 2024 (validation) and 2025-01..2026-11 (test) once,
expanding walk-forward, 200x within-date permutation null, practical checks.
Usage: python recipe.py [all|bull]   (bull = search + evaluate only on SPY>200DMA days)"""
import sys, numpy as np, pandas as pd, json, time
from multiprocessing import Pool
from lib import *

MODE = sys.argv[1] if len(sys.argv) > 1 else 'all'
NPERM = int(sys.argv[2]) if len(sys.argv) > 2 else 200
K = 15                       # candidate pool: top-K features by |train IC t| (fwd10)
QS = (0.5, 0.7, 0.8, 0.9)   # gate thresholds = train pooled quantiles in the feature's IC direction
TOPN, MIN_AVG_PICKS, MIN_GAIN = 20, 15, 0.002
EMBARGO = 20

df = load(); T = df.g.max() + 1
W = pd.read_parquet(D + 'scripts/_wins.parquet')
FE = [f for f in FEATS if f != 'earn_score']
gdate = df.groupby('g').date.first()
g = df.g.to_numpy()
bull_g = (df.groupby('g').reg_trend.first() == 'SPY>200DMA').to_numpy()
X = df[FE].to_numpy(dtype='float32')
Rk = pd.read_parquet(D + 'scripts/_ranks.parquet', columns=FE + [f'fwd{h}_vs_ew' for h in H])
RX = Rk[FE].to_numpy(dtype='float32')
rng0 = np.random.default_rng(7); TIE = rng0.random(len(df)).astype('float32')
HIT = {h: (df[f'fwd{h}_vs_ew'] > 0).to_numpy().astype('float32') for h in H}
HSPY = {h: (df[f'fwd{h}_vs_spy'] > 0).to_numpy().astype('float32') for h in H}
VAL = {h: df[f'fwd{h}_vs_ew'].notna().to_numpy() for h in H}
EXW = {h: W[f'fwd{h}_vs_ew_w'].to_numpy() for h in H}
EXS = {h: W[f'fwd{h}_vs_spy_w'].to_numpy() for h in H}
RAWEX = {h: df[f'fwd{h}_vs_ew'].to_numpy() for h in H}
YR = {h: Rk[f'fwd{h}_vs_ew'].to_numpy() for h in H}
starts = np.r_[0, np.flatnonzero(np.diff(g)) + 1]
gstart = np.repeat(starts, np.diff(np.r_[starts, len(g)]))


def date_mask(lo, hi, embargo=0):
    gs = np.flatnonzero((gdate >= lo).to_numpy() & (gdate <= hi).to_numpy())
    if embargo: gs = gs[:-embargo]
    m = np.zeros(T, bool); m[gs] = True
    if MODE == 'bull': m &= bull_g
    return m


def perm_index(seed):
    """Within-date permutation of row positions (shuffles outcomes across tickers on each date)."""
    if seed is None: return None
    r = np.random.default_rng(seed)
    key = g.astype(np.float64) + r.random(len(g)) * 0.5
    return np.argsort(key, kind='stable')     # rows of each date, shuffled, in date order


def picks(order_cache, f, sign, gate):
    o = order_cache[(f, sign)]
    m = gate[o]
    cs = np.cumsum(m)
    gs = gstart[o]  # group start (positions are within-date contiguous since order keeps dates grouped)
    base = np.where(gs > 0, cs[np.maximum(gs - 1, 0)], 0)
    sel = m & ((cs - base) <= TOPN)
    return o[sel]


def get_order(f, sign):
    x = X[:, FE.index(f)].astype('float64')
    x = np.where(np.isnan(x), -np.inf if sign > 0 else np.inf, x)
    return np.lexsort((TIE, -sign * x, g))


def objective(rows, dm, hit):
    n = np.bincount(g[rows], minlength=T).astype(float)
    ok = dm & (n > 0)
    if n[dm].mean() < MIN_AVG_PICKS: return -1
    vals = []
    for h in H:
        v = VAL[h][rows]
        hh = np.bincount(g[rows][v], hit[h][rows][v], T); nn = np.bincount(g[rows][v], minlength=T)
        k = ok & (nn > 0)
        vals.append((hh[k] / nn[k]).mean())
    return float(np.mean(vals))


def search(dm, seed=None):
    """Full procedure: pool selection by train IC, greedy rank+gate search. Returns recipe, objective, n_tried."""
    p = perm_index(seed)
    hit = {h: (HIT[h][p] if p is not None else HIT[h]) for h in H}
    # NB: permuting outcomes within date: row i receives outcome of row p[i]
    yr10 = YR[10][p] if p is not None else YR[10]
    rowm = dm[g]
    tstats = []
    for j, f in enumerate(FE):
        x = np.where(rowm, RX[:, j], np.nan)
        ic = daily_ic(g, x, yr10, T)
        mu, t, _ = nw_t(ic, 10)
        tstats.append((abs(t), f, np.sign(mu)))
    pool = sorted(tstats, reverse=True)[:K]
    pool = [(f, int(s)) for _, f, s in pool]
    cache = {(f, s): get_order(f, s) for f, s in pool}
    hit_l = hit
    tried = 0
    best = (-1, None)
    for f, s in pool:
        rows = picks(cache, f, s, rowm.copy())
        ob = objective(rows, dm, hit_l); tried += 1
        if ob > best[0]: best = (ob, f, s)
    rank = (best[1], best[2]); cur = best[0]
    gates = []; gate = rowm.copy()
    thr = {}
    for f, s in pool:
        x = X[rowm, FE.index(f)]; x = x[~np.isnan(x)]
        thr[f] = sorted(set(float(np.quantile(x, q if s > 0 else 1 - q)) for q in QS))
    for step in range(3):
        cand = None
        for f, s in pool:
            if any(gf == f for gf, _, _ in gates): continue
            xcol = X[:, FE.index(f)]
            for t in thr[f]:
                gm = gate & ((xcol >= t) if s > 0 else (xcol <= t))
                rows = picks(cache, rank[0], rank[1], gm)
                ob = objective(rows, dm, hit_l); tried += 1
                if cand is None or ob > cand[0]: cand = (ob, f, s, t, gm)
        if cand is None or cand[0] < cur + MIN_GAIN: break
        cur = cand[0]; gates.append((cand[1], cand[2], cand[3])); gate = cand[4]
    return dict(rank=rank, gates=gates, train_obj=cur, tried=tried, pool=pool)


def apply(rec, dm):
    rowm = dm[g].copy()
    for f, s, t in rec['gates']:
        xcol = X[:, FE.index(f)]
        rowm &= (xcol >= t) if s > 0 else (xcol <= t)
    cache = {tuple(rec['rank']): get_order(*rec['rank'])}
    return picks(cache, rec['rank'][0], rec['rank'][1], rowm)


def evaluate(rows, dm, label):
    out = []
    for h in H:
        v = VAL[h][rows]; r = rows[v]; gg = g[r]
        n = np.bincount(gg, minlength=T).astype(float)
        ok = dm & (n > 0)
        allv = VAL[h] & dm[g]
        base = np.bincount(g[allv], HIT[h][allv], T) / np.maximum(np.bincount(g[allv], minlength=T), 1)
        hr = np.bincount(gg, HIT[h][r], T) / np.maximum(n, 1)
        hs = np.bincount(gg, HSPY[h][r], T) / np.maximum(n, 1)
        ex = np.bincount(gg, EXW[h][r], T) / np.maximum(n, 1)
        exs = np.bincount(gg, EXS[h][r], T) / np.maximum(n, 1)
        lift = np.where(ok, hr - base, np.nan)
        mu, t, nd = nw_t(lift, h) if ok.sum() > 30 else (np.nan, np.nan, ok.sum())
        # block bootstrap (20-day blocks) CI for the lift
        L = lift[ok]; B = 20; rb = np.random.default_rng(1); bs = []
        if len(L) > 2 * B:
            nb = int(np.ceil(len(L) / B))
            for _ in range(1000):
                st = rb.integers(0, len(L) - B, nb)
                bs.append(np.concatenate([L[s:s + B] for s in st])[:len(L)].mean())
        lo, hi = (np.percentile(bs, [2.5, 97.5]) if bs else (np.nan, np.nan))
        out.append(dict(recipe=label, h=h, n_dates=int(ok.sum()), eff_n_indep=round(ok.sum() / h, 1), avg_picks=n[ok].mean() if ok.any() else np.nan,
                        hit_vs_ew=hr[ok].mean(), base_hit_all_names=base[ok].mean(), lift=mu, lift_ci95_lo=lo, lift_ci95_hi=hi, lift_nw_t=t,
                        hit_vs_spy=hs[ok].mean(), median_ex_ew=np.nanmedian(RAWEX[h][r][dm[gg]]) if len(r) else np.nan,
                        mean_ex_ew_wins=ex[ok].mean(), mean_ex_spy_wins=exs[ok].mean()))
    return out


def recipe_str(rec):
    s = ' AND '.join(f"{f} {'>=' if sg > 0 else '<='} {t:.4g}" for f, sg, t in rec['gates']) or '(no gate)'
    return f"gate: {s} | rank: {rec['rank'][0]} {'desc' if rec['rank'][1] > 0 else 'asc'} | top {TOPN}"


def _perm(seed):
    return search(TRAIN, seed)['train_obj']


TRAIN = date_mask('2021-03-01', '2023-12-31', EMBARGO)
VALD = date_mask('2024-01-01', '2024-12-31')
TEST = date_mask('2025-01-01', '2026-11-30')
if __name__ == '__main__':
    t0 = time.time()
    rec = search(TRAIN)
    print('FROZEN', MODE, recipe_str(rec), 'train obj', round(rec['train_obj'], 4), 'tried', rec['tried'], f'{time.time()-t0:.0f}s')
    print('pool', rec['pool'])
    res = []
    for lab, dm in (('train 2021-03..2023-12', TRAIN), ('validation 2024', VALD), ('test 2025-01..2026-11', TEST)):
        for r in evaluate(apply(rec, dm), dm, lab): r['rule'] = recipe_str(rec); res.append(r)
    # reference: composite sc_momentum top20 (REFERENCE ONLY, not an allowed input) and a pure flow_100 rank
    for lab, dm in (('train 2021-03..2023-12', TRAIN), ('validation 2024', VALD), ('test 2025-01..2026-11', TEST)):
        for f, rule in (('sc_momentum', 'REFERENCE composite: top20 by sc_momentum'),):
            x = df[f].to_numpy('float64'); o = np.lexsort((TIE, -x, g))
            rows = picks({(f, 1): o}, f, 1, dm[g].copy())
            for r in evaluate(rows, dm, lab): r['rule'] = rule; res.append(r)
    pd.DataFrame(res).round(4).to_csv(D + f'tables/recipe_frozen_{MODE}.csv', index=False)
    json.dump({**rec, 'rule': recipe_str(rec)}, open(D + f'tables/recipe_frozen_{MODE}.json', 'w'), indent=1, default=float)

    # expanding walk-forward: retrain on everything before year Y (20-session embargo), apply to year Y
    wf = []; wf_rows = []
    for Y in range(2022, 2027):
        trm = date_mask('2021-03-01', f'{Y-1}-12-31', EMBARGO); tsm = date_mask(f'{Y}-01-01', f'{Y}-12-31')
        r = search(trm)
        rows = apply(r, tsm); wf_rows.append(rows)
        for e in evaluate(rows, tsm, f'WF {Y}'): e['rule'] = recipe_str(r); wf.append(e)
        print('WF', Y, recipe_str(r))
    allm = date_mask('2022-01-01', '2026-11-30')
    for e in evaluate(np.concatenate(wf_rows), allm, 'WF pooled 2022-2026'): e['rule'] = 'retrained yearly'; wf.append(e)
    pd.DataFrame(wf).round(4).to_csv(D + f'tables/walkforward_{MODE}.csv', index=False)

    # practical checks on the frozen recipe, full period
    full = date_mask('2021-03-01', '2026-11-30')
    rows = apply(rec, full)
    P = df.iloc[rows][['date', 'ticker', 'sector_etf_current', 'year', 'g']]
    P.to_csv(D + f'tables/recipe_picks_{MODE}.csv', index=False)
    sets = P.groupby('g').ticker.apply(set)
    ov = [len(sets.iloc[i] & sets.iloc[i - 1]) for i in range(1, len(sets)) if sets.index[i] == sets.index[i - 1] + 1]
    sec = P.groupby(['g', 'sector_etf_current']).size().groupby(level=0).apply(lambda s: s.max() / s.sum())
    prac = dict(avg_names_same_as_prior_day=np.mean(ov), daily_turnover_share=1 - np.mean(ov) / TOPN,
                avg_top_sector_share=sec.mean(), share_days_top_sector_over_50pct=(sec > 0.5).mean(),
                distinct_tickers_picked=P.ticker.nunique())
    pd.Series(prac).round(4).to_csv(D + f'tables/recipe_practical_{MODE}.csv')
    P.sector_etf_current.value_counts(normalize=True).round(4).to_csv(D + f'tables/recipe_sector_mix_{MODE}.csv')
    yrs = []
    for Y in range(2021, 2027):
        dm = full & (gdate.dt.year == Y).to_numpy()
        for e in evaluate(apply(rec, dm), dm, f'{Y}'): yrs.append(e)
    pd.DataFrame(yrs).round(4).to_csv(D + f'tables/recipe_by_year_{MODE}.csv', index=False)
    print(pd.Series(prac).round(3).to_string())

    # permutation null: same full procedure on within-date shuffled outcomes
    t0 = time.time()
    with Pool(4) as pool:
        null = pool.map(_perm, range(1000, 1000 + NPERM))
    null = np.array(null)
    nd = dict(real_train_obj=rec['train_obj'], null_mean=null.mean(), null_p95=np.percentile(null, 95), null_max=null.max(),
              p_value=(1 + (null >= rec['train_obj']).sum()) / (1 + len(null)), n_perm=len(null), recipes_tried_per_search=rec['tried'],
              features_screened_for_pool=len(FE))
    pd.Series(nd).to_csv(D + f'tables/permutation_null_{MODE}.csv')
    pd.Series(null).to_csv(D + f'tables/permutation_null_draws_{MODE}.csv', index=False)
    print(pd.Series(nd).to_string(), f'{time.time()-t0:.0f}s')
    pd.set_option('display.width', 250)
    print(pd.DataFrame(res).round(4).drop(columns='rule').to_string())
    print(pd.DataFrame(wf).round(4).drop(columns='rule').to_string())
