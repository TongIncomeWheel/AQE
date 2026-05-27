"""Targeted NOW engine diagnostic — compare AQE Python vs TradingView."""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.panel_builder import SPY_DAILY
from src.engines import flow, energy, structure, mp, elder, scoring
from src.data.earnings import load_earnings

# Load updated panel data for NOW
panel = pd.read_parquet(PROJECT_ROOT / "data" / "panel_daily.parquet")
panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
now_df = panel[panel["ticker"] == "NOW"].sort_values("date").reset_index(drop=True)
print(f"NOW bars: {len(now_df)}, through: {now_df.date.max().date()}")
print("Last 4 bars:")
print(now_df[["date", "open", "high", "low", "close", "volume"]].tail(4).to_string(index=False))
print()

# Weekly
weekly_panel = pd.read_parquet(PROJECT_ROOT / "data" / "panel_weekly.parquet")
weekly_panel["date"] = pd.to_datetime(weekly_panel["date"]).dt.normalize()
now_wk = weekly_panel[weekly_panel["ticker"] == "NOW"].sort_values("date").reset_index(drop=True)

spy = pd.read_parquet(SPY_DAILY)
spy["date"] = pd.to_datetime(spy["date"]).dt.normalize()
earnings_cal = load_earnings()

# Run engines
fl = flow.compute(now_df)
en = energy.compute(now_df)
st_df = structure.compute(now_df, spy_daily=spy, weekly=now_wk, earnings_cal=earnings_cal, ticker="NOW")
mp_df = mp.compute(now_df, spy_daily=spy)
el = elder.compute(now_df)
sc_m = scoring.compute(fl["flow_100"], en["energy_100"], st_df["structure_100"], mp_df["mp_score"], el["elder_score"])


def v(series):
    return series.iloc[-1]


print("=" * 70)
dt = now_df.date.iloc[-1].date()
cl = now_df.close.iloc[-1]
print(f"NOW ENGINE REPORT -- {dt} (close ${cl:.2f})")
print("=" * 70)

# TV values from user's chart (May 19)
tv = {"Flow": 83, "Energy": 58, "Structure": 44, "MP": 27, "Elder": 10.0, "SC_MOM": 56.5}
aqe = {
    "Flow": v(fl["flow_100"]),
    "Energy": v(en["energy_100"]),
    "Structure": v(st_df["structure_100"]),
    "MP": v(mp_df["mp_score"]),
    "Elder": v(el["elder_score"]),
    "SC_MOM": v(sc_m),
}

hdr = f"{'Engine':<12} {'TV May19':>10} {'AQE':>10} {'Gap':>8} {'Status':>10}"
print(f"\n{hdr}")
print("-" * 52)
for k in tv:
    gap = aqe[k] - tv[k]
    status = "MATCH" if abs(gap) < 1 else ("CLOSE" if abs(gap) < 5 else "GAP")
    tag = "  OK" if status == "MATCH" else (" ~OK" if status == "CLOSE" else " !!!")
    print(f"{k:<12} {tv[k]:>10.1f} {aqe[k]:>10.1f} {gap:>+8.1f} {tag:>10}")

raw_sc = (
    v(fl["flow_100"]) * 0.30
    + v(en["energy_100"]) * 0.30
    + v(st_df["structure_100"]) * 0.20
    + v(mp_df["mp_score"]) * 0.20
)
print(f"\nSC_MOM raw (no gates): {raw_sc:.1f}")
print(f"SC_MOM gated:          {v(sc_m):.1f}")
print(f"TV SC_MOM:             {tv['SC_MOM']:.1f} (TV = raw weighted avg, no gate logic)")

# Sub-component breakdown
fl_last = fl.iloc[-1]
en_last = en.iloc[-1]
st_last = st_df.iloc[-1]
mp_last = mp_df.iloc[-1]

flow_raw = fl_last["flow_score"] + fl_last["accum_score"] + fl_last["volume_score"] + fl_last["skew_score"] + fl_last["ext_score"]
print(f"""
--- FLOW SUB-COMPONENTS (AQE: {v(fl['flow_100']):.1f} vs TV: 83) ---
  flow_score (MFI+CMF+HA): {fl_last['flow_score']:.1f}/17
    MFI: {fl_last['mfi']:.1f}  CMF: {fl_last['cmf']:.4f}  HA count: {fl_last['ha_quality_count']:.0f}
  accum_score (A/D linreg): {fl_last['accum_score']:.1f}/7.5
  volume_score (trend+spike): {fl_last['volume_score']:.1f}/7.5
  skew_score (up/dn vol): {fl_last['skew_score']:.1f}/3.5
  ext (extension): {fl_last['ext_score']:.1f}/5
  raw: {flow_raw:.1f}/38""")

en_raw = en_last["vp_position_score"] + en_last["price_action_score"] + en_last["squeeze_score"] + en_last["exhaustion_score"] + en_last["atr_score"]
print(f"""--- ENERGY SUB-COMPONENTS (AQE: {v(en['energy_100']):.1f} vs TV: 58) ---
  vp_position: {en_last['vp_position_score']:.1f}/17.5 (pos50: {en_last['en_pos50']:.1f})
  price_action: {en_last['price_action_score']:.1f}
  squeeze: {en_last['squeeze_score']:.1f}/12.5
  exhaustion: {en_last['exhaustion_score']:.1f}/10 (trend_bars: {en_last['en_trend_bars']:.0f})
  atr: {en_last['atr_score']:.1f}/7
  raw: {en_raw:.1f}/59.5""")

st_raw = st_last["rs_spy_score"] + st_last["rs_accel_score"] + st_last["base_score"] + st_last["ms_pos_score"] + st_last["resist_score"] + st_last["wk_score"] + st_last["earn_score"]
print(f"""--- STRUCTURE SUB-COMPONENTS (AQE: {v(st_df['structure_100']):.1f} vs TV: 44) ---
  rs_spy: {st_last['rs_spy_score']:.1f}/15  (vs_spy: {st_last['rs_vs_spy']:.1f}%)
  rs_accel: {st_last['rs_accel_score']:.1f}/15  (accel: {st_last['rs_accel']:.1f}%)
  base: {st_last['base_score']:.1f}/15  (days: {st_last['base_days']:.0f}, mode: {st_last['bd_mode']:.0f})
  ms_pos: {st_last['ms_pos_score']:.1f}/15  (p50: {st_last['ms_p50']:.1f})
  resist: {st_last['resist_score']:.1f}/10
  weekly: {st_last['wk_score']:.1f}/15
  earnings: {st_last['earn_score']:.1f}/10
  raw: {st_raw:.1f}/95""")

print(f"""--- MP SUB-COMPONENTS (AQE: {v(mp_df['mp_score']):.1f} vs TV: 27) ---
  abs_mom: {mp_last['abs_mom_score']:.1f}/30  (roc_z: {mp_last['roc_zscore']:.2f})
  adx: {mp_last['adx_score']:.1f}/25  (val: {mp_last['adx_val']:.1f}, DI+>DI-: {mp_last['di_bullish']})
  rel_mom: {mp_last['rel_mom_score']:.1f}/25  (excess: {mp_last['excess_return']:.1f}%)
  trend: {mp_last['trend_score']:.1f}/20""")

print(f"""--- ELDER (AQE: {v(el['elder_score']):.1f} vs TV: 10) ---
  State: {el.iloc[-1]['impulse_state']}
  MP State: {mp_last['mp_state']}""")

# Gate analysis
print("\n--- SC_MOMENTUM GATE ANALYSIS ---")
gates = {
    "Elder >= 6.5": (v(el["elder_score"]), 6.5),
    "Flow >= 60": (v(fl["flow_100"]), 60.0),
    "Energy >= 60": (v(en["energy_100"]), 60.0),
    "Structure >= 55": (v(st_df["structure_100"]), 55.0),
    "MP >= 55": (v(mp_df["mp_score"]), 55.0),
}
for label, (val, thresh) in gates.items():
    status = "PASS" if val >= thresh else "FAIL"
    print(f"  {label}: {val:.1f} -> {status}")
