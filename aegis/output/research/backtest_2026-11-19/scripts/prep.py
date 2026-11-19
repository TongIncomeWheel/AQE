"""Build the research panel: allowed features only, numeric encodings, PIT tradeability filter, SPY regimes."""
import numpy as np, pandas as pd, json
D = '/home/user/pma_run/deep_backtest/'
meta = json.load(open(D + 'data/extract_meta.json'))
AGG = meta['columns']['aggregate']
SUB = [c for c in meta['columns']['sub'] if c != 'pipe_tier']   # pipe_tier ruled out (composite tier, universe-relative)
FWD = [f'fwd{h}_vs_{b}' for h in (5, 10, 20) for b in ('ew', 'spy')] + ['fwd5', 'fwd10', 'fwd20']
REF = ['sc_momentum', 'sc_position', 'pipe_rank']                  # reference only, never an input
MKT = ['close_panel', 'vol_20d_ann_pit', 'dollar_vol_20d_pit', 'sector_etf_current']

df = pd.read_parquet(D + 'data/aqe_research_extract_2026-11-19.parquet', columns=['date', 'ticker'] + AGG + SUB + REF + MKT + FWD)
ORD = {
    'mp_state': {'FADING': 0, 'BUILDING': 1, 'STRONG': 2},
    'impulse_state': {'RED': 0, 'NEUTRAL': 1, 'GREEN': 2},
    'rd_state': {'NOT_READY': 0, 'NEUTRAL': 1, 'WATCH': 2, 'READY': 3},
    'hl_state': {'EXIT': 0, 'TIGHTEN': 1, 'HOLD': 2, 'HOLD_ADD': 3},
    'mp_accel_state': {'DECELERATING': 0, 'FLAT': 1, 'ACCELERATING': 2},
}
for c, m in ORD.items():
    df[c] = df[c].map(m).astype('float32')
for c in ['k39_gate', 'di_bullish']:
    df[c] = df[c].astype('float32')
FEATS = AGG + SUB
for c in FEATS:
    df[c] = df[c].astype('float32')
# drop constant columns
FEATS = [c for c in FEATS if df[c].nunique() > 1]
n0 = len(df)
elig = (df.close_panel >= 5) & (df.dollar_vol_20d_pit >= 10e6) & df.vol_20d_ann_pit.notna() & df.sector_etf_current.notna()
df = df[elig].copy()
print('rows', n0, '->', len(df), 'after PIT filter (close>=$5, 20d $vol>=$10M)')
df['year'] = df.date.dt.year.astype('int16')
df['log_dv'] = np.log(df.dollar_vol_20d_pit).astype('float32')
df = df.sort_values(['date', 'ticker']).reset_index(drop=True)

# SPY regimes, point in time (all from closes up to and including the signal date)
spy = pd.read_csv(D + 'data/aqe_research_spy_2026-11-19.csv', parse_dates=['date']).sort_values('date')
spy['ma200'] = spy.spy_close.rolling(200, min_periods=150).mean()
spy['r'] = spy.spy_close.pct_change()
spy['rv20'] = spy.r.rolling(20).std() * np.sqrt(252)
spy['rv_med'] = spy.rv20.expanding(120).median()          # expanding median: causal
spy['ret63'] = spy.spy_close.pct_change(63)
spy['reg_trend'] = np.where(spy.spy_close > spy.ma200, 'SPY>200DMA', 'SPY<200DMA')
spy['reg_vol'] = np.where(spy.rv20 > spy.rv_med, 'HighVol', 'LowVol')
spy['reg_mom'] = np.where(spy.ret63 > 0, 'Rising63d', 'Falling63d')
df = df.merge(spy[['date', 'reg_trend', 'reg_vol', 'reg_mom']], on='date', how='left')
print(df[['reg_trend', 'reg_vol', 'reg_mom']].isna().mean())
df.to_parquet(D + 'scripts/_panel.parquet', index=False)
json.dump({'FEATS': FEATS, 'FWD': FWD, 'REF': REF}, open(D + 'scripts/_cols.json', 'w'), indent=1)
print(len(FEATS), 'features:', FEATS)
