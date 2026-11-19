"""Component review, step 3: the readable summary COMPONENT_REVIEW.md (evidence only)."""
import json, pandas as pd
from collections import Counter, defaultdict

D = '/home/user/pma_run/deep_backtest/'
T = pd.read_csv(D + 'tables/component_review_table.csv')
CL = json.load(open(D + 'scripts/_cr_clusters.json'))
FLAGS = ['DUPLICATE', 'VOL_PROXY', 'SECTOR_PROXY', 'LIQUIDITY_PROXY', 'SIGN_FLIPS', 'DEAD', 'CONSTANT_OR_DISCRETE', 'NEEDS_REVIEW']
anyc = Counter(x for s in T.all_flags for x in s.split(';'))
pri = Counter(T.primary_flag)

# blast radius inverted: composite/gate -> flagged rows that feed it
GATES = ['sc_momentum', 'sc_position', 'sc_m_gates', 'sc_p_gates', 'Longlist gate', 'Watchlist gate', 'Elder list', 'Precision Edge',
         'shortlist gate', 'Pipeline Rank screen', 'pipe_rank', 'flow_100', 'energy_100', 'structure_100', 'mp_100', 'bq_100', 'elder_score',
         'k39_gate', 'rd_score', 'hl_score', 'held_positions export', 'QS lens_total / calibration', 'QS recipes', 'QS vetoes', 'QS why-text',
         'Signal Radar', 'lens_consensus', 'signal_ledger']
inv = defaultdict(list)
for _, r in T[T.primary_flag != 'NONE'].iterrows():
    br = [b.strip() for b in str(r.blast_radius).split(';')]
    for gname in GATES:
        if any(b == gname or b.startswith(gname + ' ') or b.startswith(gname + '(') for b in br):
            inv[gname].append(f"{r['name']}[{r.primary_flag}]")

L = []
L.append('# AQE component review - evidence table (2026-11-19)\n')
L.append('Evidence for the expert review only. No recipe is proposed and nothing is tuned. '
         'Full table: `tables/component_review_table.csv` (79 rows = 10 aggregates + 69 sub-scores, 62 columns). '
         'Scripts: `scripts/component_stats.py`, `component_meta.py`, `component_table.py`, `component_md.py`.\n')
L.append('## Data and definitions\n')
L.append('- Panel: `scripts/_panel.parquet` (from the 2026-11-19 extract), 2021-03-15 to 2026-11-18, PIT tradeability filter close>=$5 and 20d dollar volume>=$10M, 1,928,693 rows, ~1,424 signal dates. '
         'Universe and sector map are NOT point-in-time (today\'s screen applied backwards: survivorship).')
L.append('- Target: forward excess return vs the equal-weight mean of names scored that date, close to close, h = 5/10/20 sessions (`fwd{h}_vs_ew`).')
L.append('- Rank-IC: per-date Pearson of centred cross-sectional ranks (= Spearman), averaged over dates; t = Newey-West with lag h. '
         '"Neutral" = both the feature rank and the target rank residualised per date on vol rank, log dollar-volume rank and GICS-sector dummies (lib.neutralise).')
L.append('- Years: 2021 (from 15 Mar) to 2026 (to 18 Nov, partial). `years_pos_*` = years with mean IC > 0, out of `years_with_data_*`. Per-year NW t computed for 36 cells (6 years x 3 horizons x raw/neutral).')
L.append('- Variance shares: share of each feature\'s per-date cross-sectional rank variance explained by (a) vol rank alone, (b) log dollar-volume rank alone, (c) sector dummies alone, (d) all three; pooled over all dates.')
L.append('- Redundancy: mean over 200 randomly sampled dates (seed 20261119) of the per-date Spearman matrix over the 79 columns. '
         'Tight cluster = complete linkage on 1-|rho| cut at 0.2, so every pair inside has |rho|>=0.8. `chain_group` = connected components of the |rho|>=0.8 graph (shows chaining). Negative rho counts (an inverted copy is still a copy).')
L.append('- Categorical labels are coded ordinally for ranking (mp_state FADING<BUILDING<STRONG, impulse RED<NEUTRAL<GREEN, rd_state, hl_state, mp_accel_state, pipe_tier D<C<B<A); bd_mode is NOT ordinal (see NEEDS_REVIEW).\n')
L.append('## Flag rules (fixed before looking at the result)\n')
L.append('- DUPLICATE: nearest twin |rho| >= 0.80.')
L.append('- VOL_PROXY / LIQUIDITY_PROXY / SECTOR_PROXY: variance share explained by vol alone / dollar volume alone / sector alone > 50%.')
L.append('- DEAD: no full-sample |NW t| >= 2 in any of the 6 tests (raw and neutral, 5/10/20d) AND no single year-cell with |t| >= 3 (a stricter per-year bar because 36 cells are tested).')
L.append('- SIGN_FLIPS: some year significantly positive (t>=2) and another significantly negative (t<=-2) on the same horizon and mode, OR (not DEAD and at its best test fewer than 5 of 6 years share the full-sample sign).')
L.append('- CONSTANT_OR_DISCRETE: <= 5 distinct values, or one value on >= 80% of rows.')
L.append('- NEEDS_REVIEW: a data-validity problem (see flag_note).')
L.append('- `primary_flag` = first of NEEDS_REVIEW > DUPLICATE > VOL/SECTOR/LIQUIDITY_PROXY > DEAD > SIGN_FLIPS > CONSTANT_OR_DISCRETE; `all_flags` lists every flag; NONE = no rule fired.\n')
L.append('## Flag counts (79 rows)\n')
L.append('| flag | rows carrying it (all_flags) | rows where it is primary |')
L.append('|---|---|---|')
for f in FLAGS + ['NONE']:
    L.append(f'| {f} | {anyc.get(f, 0)} | {pri.get(f, 0)} |')
L.append('')
L.append('## Headline facts\n')
best = T.sort_values('max_abs_full_sample_t', ascending=False).head(6)
L.append('- No component (earn_score excluded, see NEEDS_REVIEW) clears |NW t| >= 2 at 10d or 20d after neutralisation (max |t| %.2f at 10d, %.2f at 20d). The largest full-sample |t| anywhere: ' % (T[T.name != 'earn_score'].t_neutral_10d.abs().max(), T[T.name != 'earn_score'].t_neutral_20d.abs().max()) +
         '; '.join(f"{r['name']} {r.best_test} t={r.max_abs_full_sample_t:.2f}" for _, r in best.iterrows()) + '. '
         'All are 5-10 day effects with |IC| of 0.012 or less.')
agg = ['flow_100', 'energy_100', 'structure_100', 'mp_100', 'elder_score', 'bq_100', 'k39_value', 'k39_gate', 'mp_state', 'impulse_state']
A = T[T.name.isin(agg)]
L.append('- All 10 aggregates carry DEAD: max |neutral IC| over 5/10/20d is %.3f (k39_value 20d), max full-sample |t| %.2f.' % (A[['ic_neutral_5d', 'ic_neutral_10d', 'ic_neutral_20d']].abs().max().max(), A.max_abs_full_sample_t.max()))
L.append('- Volatility/sector/liquidity explain little of most components (median all-three share %.0f%%); the one >50%% proxy is base_days (vol alone %.0f%%: longer bases = lower-vol names). Dollar volume explains <2%% of every column.'
         % (100 * T.var_share_all.median(), 100 * T.loc[T.name == 'base_days', 'var_share_vol'].iloc[0]))
L.append('- en_pos50 and ms_p50 are the same number (rho 1.000), as the glossary already notes. en_trend_bars vs hl_trend_bars rho 0.984 (EMA20 vs EMA21 run counts).')
L.append('- earn_score varies across names on only 15 dates (2026-10-29 onward); before that it is the constant 10.0 default, so it cannot be evaluated here.\n')
L.append('## (b) Five most redundant clusters (by size, then mean |rho|)\n')
for i, c in enumerate(CL[:5], 1):
    neg = ' (contains inverted pairs)' if c['any_negative'] else ''
    L.append(f"{i}. {' / '.join(c['members'])}: {c['size']} columns, mean |rho| {c['mean_abs_rho']:.2f}, min {c['min_abs_rho']:.2f}{neg}.")
L.append('\nOther tight pairs: ' + '; '.join(f"{'/'.join(c['members'])} {c['mean_abs_rho']:.2f}" for c in CL[5:]) + '.')
ch = T.chain_group.value_counts()
big = ch[ch.index != 'none'].index[0]
L.append(f'\nChaining: following |rho|>=0.8 links, {big} connects {int(big.split("(")[1].split()[0])} columns (range position, 20d relative momentum, trend age, MA stack, Health), so these groups are not independent of each other either.\n')
L.append('## (a) Blast radius: composites and gates that read a flagged row\n')
L.append('Each line: the composite/gate, then every flagged row it depends on directly or through its parents ([primary flag]). Removing a row changes every item it reaches; the per-row chain is in the `blast_radius` column.\n')
for gname in GATES:
    if inv.get(gname):
        L.append(f"- **{gname}** ({len(inv[gname])}): {', '.join(inv[gname])}")
L.append('\n## Glossary gaps\n')
gg = T[T.glossary_status.str.startswith('glossary gap')]
L.append(f'{len(gg)} rows have no glossary row under the extract\'s name; their description was read from source (cited in the `source` column): ' + ', '.join(gg.name) + '.')
L.append('The 7 engine totals are documented in the glossary under short names (flow, energy, structure, mp, elder, bq) rather than the extract name; k39_value has no row at all. '
         'Readiness (rd_*) and the hl_ sub-scores/diagnostics are absent from the glossary entirely (both are stripped from the export, drive_sync.py:3186-3188). '
         'pr_ret_12m: glossary (as ret_12m_score) says the 12-month return skips the latest month; the code (pipeline_rank.py:95) is close/close[231]-1, which does not skip it.\n')
L.append('## Rows with no flag\n')
L.append(', '.join(f"{r['name']} (best {r.best_test}, t={r.max_abs_full_sample_t:.2f})" for _, r in T[T.primary_flag == 'NONE'].iterrows()) + '.\n')
L.append('## Caveats\n')
L.append('- Survivorship (today\'s universe applied backwards) and a current sector map bias the level of IC; they do not obviously bias the redundancy or exposure columns.')
L.append('- 2026 is a partial year (Jan to 18 Nov; 20d targets end ~20 sessions earlier).')
L.append('- Step scores with few levels produce many tied ranks; rank-IC still works but resolution is low (see n_distinct_values).')
L.append('- The research panel is the scores_daily history as stored; nothing was recomputed.')
open(D + 'COMPONENT_REVIEW.md', 'w').write('\n'.join(L) + '\n')
print('\n'.join(L))
