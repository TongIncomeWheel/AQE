"""Run the portfolio simulation on existing signal+outcome data.

Usage: python -m src.backtest.run_sim
Output: data/portfolio_sim_results.json + console summary

Reads the active recipe from data/active_recipe.json if it exists.
Otherwise falls back to SC_MOMENTUM >= 55 with no engine filters.
The active recipe is written by the Streamlit UI when you click "Re-run simulation".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.backtest.portfolio_sim import simulate_portfolio, example_100k_scenario, monte_carlo_equity


def main():
    data_dir = ROOT / "data"
    panel_path = data_dir / "panel_daily.parquet"
    scores_path = data_dir / "scores_daily.parquet"

    if not panel_path.exists():
        print(f"[ERROR] {panel_path} not found. Run build_panel.bat first.")
        return
    if not scores_path.exists():
        print(f"[ERROR] {scores_path} not found. Run build_scores.bat first.")
        return

    recipe = _load_active_recipe(data_dir)
    subcomp = recipe.get("subcomp_filters", {})
    recipe_name = recipe.get("recipe_name", "Custom")
    if subcomp:
        fstr = ", ".join(f"{k}>={v}" for k, v in subcomp.items())
        print(f"[sim] {recipe_name}: {fstr}")
    else:
        print(f"[sim] Recipe: SC>={recipe['sc_mom_min']:.0f}, Flow>={recipe['flow_min']:.0f}, "
              f"Energy>={recipe['energy_min']:.0f}, Struct>={recipe['structure_min']:.0f}, "
              f"MP>={recipe['mp_min']:.0f}")

    print("[sim] Loading data...")
    panel = pd.read_parquet(panel_path)
    scores = pd.read_parquet(scores_path)

    print("[sim] Detecting signals from score data...")
    signals = _detect_entry_signals(scores, recipe)
    print(f"[sim] Found {len(signals)} entry signals")

    if signals.empty:
        print("[sim] No signals found. Cannot simulate.")
        return

    # Merge ATR for sizing
    from src.engines.utils import atr as compute_atr
    atr_values = []
    for ticker, grp in panel.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        a = compute_atr(grp["high"], grp["low"], grp["close"], 14)
        df_a = grp[["ticker", "date"]].copy()
        df_a["atr14"] = a.values
        atr_values.append(df_a)
    atr_df = pd.concat(atr_values, ignore_index=True)
    atr_df["date"] = pd.to_datetime(atr_df["date"]).dt.normalize()

    signals["date"] = pd.to_datetime(signals["date"]).dt.normalize()
    signals = signals.merge(atr_df[["ticker", "date", "atr14"]], on=["ticker", "date"], how="left")
    signals = signals.dropna(subset=["atr14"])
    signals = signals.rename(columns={"atr14": "atr14_at_entry"})

    print(f"[sim] {len(signals)} signals with valid ATR. Running simulation...")
    result = simulate_portfolio(signals, panel, initial_capital=70_000.0)

    # Attach recipe metadata to results
    result["recipe"] = recipe

    # Print summary
    s = result["summary"]
    mc = result["monte_carlo"]
    print("\n" + "=" * 70)
    print("  PORTFOLIO SIMULATION - $70,000 STARTING CAPITAL")
    if subcomp:
        print(f"  Recipe: {recipe_name}")
        fstr = " & ".join(f"{k}>={v}" for k, v in subcomp.items())
        print(f"  Filters: {fstr}")
    else:
        print(f"  Recipe: SC>={recipe['sc_mom_min']:.0f} | Flow>={recipe['flow_min']:.0f} | "
              f"Energy>={recipe['energy_min']:.0f} | Struct>={recipe['structure_min']:.0f} | "
              f"MP>={recipe['mp_min']:.0f}")
    print("=" * 70)
    print(f"  Total trades:          {s.get('total_trades', 0)}")
    print(f"  Win rate:              {s.get('win_rate_pct', 0):.1f}%")
    print(f"  Average R:             {s.get('avg_r', 0):+.2f}R")
    print(f"  Median R:              {s.get('median_r', 0):+.2f}R")
    print(f"  Total P&L:             ${s.get('total_pnl', 0):,.2f}")
    print(f"  Total costs:           ${s.get('total_costs', 0):,.2f} ({s.get('cost_drag_pct', 0):.2f}% drag)")
    print(f"  Gross return:          {s.get('gross_return_pct', 0):+.2f}%")
    print(f"  Annual return:         {s.get('annual_return_pct', 0):+.2f}%")
    print(f"  Adj annual (-2% bias): {s.get('adjusted_annual_pct', 0):+.2f}%")
    print(f"  Max drawdown:          {s.get('max_drawdown_pct', 0):.2f}%")
    print(f"  Sharpe (approx):       {s.get('sharpe_approx', 0):.2f}")
    print(f"  Avg hold period:       {s.get('avg_hold_bars', 0):.1f} bars")
    print(f"  Final equity:          ${s.get('final_equity', 0):,.2f}")
    print()
    print("  Trail tier distribution:")
    for tier, count in s.get("peak_tier_distribution", {}).items():
        print(f"    {tier}: {count} trades")
    print()
    print("  Monte Carlo (2000 permutations):")
    print(f"    Median return:       {mc['median_return_pct']:+.2f}%")
    print(f"    5th pctile return:   {mc['p5_return_pct']:+.2f}%")
    print(f"    95th pctile return:  {mc['p95_return_pct']:+.2f}%")
    print(f"    Median max DD:       {mc['median_max_dd_pct']:.2f}%")
    print(f"    95th pctile DD:      {mc['p95_max_dd_pct']:.2f}%")
    print(f"    Risk of ruin (>25%): {mc['risk_of_ruin_pct']:.1f}%")
    print(f"    Original sequence:   {mc['original_percentile']:.0f}th percentile")
    print()

    # Correlated loss stress test
    stress = result.get("stress_test", {})
    if stress:
        from src.backtest.correlation_stress import format_stress_report, StressResult
        # Reconstruct dataclass for formatting
        sr = StressResult(**stress)
        print(format_stress_report(sr, capital=70_000.0))

    print("=" * 70)

    # Save results
    output_path = data_dir / "portfolio_sim_results.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n[sim] Results saved to {output_path}")

    # Save example scenario to file
    scenario_path = data_dir / "portfolio_sizing_example.txt"
    with open(scenario_path, "w", encoding="utf-8") as f:
        f.write(example_100k_scenario())
    print(f"[sim] Sizing walkthrough saved to {scenario_path}")


def _load_active_recipe(data_dir: Path) -> dict:
    """Load active recipe from JSON, or use defaults.

    Supports both:
      - Legacy flat format: {sc_mom_min, flow_min, ...}
      - Dual format: {longlist: {...}, precision: {...}}

    For simulation, uses precision recipe if available (better WR).
    """
    recipe_path = data_dir / "active_recipe.json"
    default = {
        "sc_mom_min": 55.0,
        "flow_min": 0.0,
        "energy_min": 0.0,
        "structure_min": 0.0,
        "mp_min": 0.0,
        "elder_min": 0.0,
        "subcomp_filters": {},
    }
    if recipe_path.exists():
        try:
            with open(recipe_path) as f:
                raw = json.load(f)

            # Dual format: prefer precision recipe for simulation
            if "precision" in raw:
                prec = raw["precision"]
                default["sc_mom_min"] = float(prec.get("sc_mom_min", 50.0))
                # Extract thresholds from rich sub-component specs
                subcomp = {}
                for col, spec in prec.get("subcomp_filters", {}).items():
                    if isinstance(spec, dict):
                        subcomp[col] = spec["threshold"]
                    else:
                        subcomp[col] = spec
                default["subcomp_filters"] = subcomp
                default["recipe_name"] = prec.get("name", "Precision Edge")
                return default

            # Legacy flat format
            for k in default:
                if k == "subcomp_filters":
                    default[k] = raw.get("subcomp_filters", {})
                elif k in raw:
                    default[k] = float(raw[k])
            return default
        except (json.JSONDecodeError, ValueError):
            pass
    return default


def _detect_entry_signals(scores: pd.DataFrame, recipe: dict) -> pd.DataFrame:
    """Crossup with full recipe filter applied (aggregate + sub-component)."""
    sc_min = recipe.get("sc_mom_min", 55.0)
    flow_min = recipe.get("flow_min", 0.0)
    energy_min = recipe.get("energy_min", 0.0)
    structure_min = recipe.get("structure_min", 0.0)
    mp_min = recipe.get("mp_min", 0.0)
    elder_min = recipe.get("elder_min", 0.0)
    subcomp = recipe.get("subcomp_filters", {})

    signals = []
    scores_sorted = scores.sort_values(["ticker", "date"]).reset_index(drop=True)

    for ticker, grp in scores_sorted.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        if "sc_momentum" not in grp.columns:
            continue
        sc = grp["sc_momentum"].values
        for i in range(1, len(sc)):
            if sc[i] >= 50.0 and sc[i - 1] < 50.0:
                row = grp.iloc[i]
                # Apply aggregate recipe filters
                if sc[i] < sc_min:
                    continue
                if flow_min > 0 and "flow_100" in row.index:
                    if pd.notna(row["flow_100"]) and row["flow_100"] < flow_min:
                        continue
                if energy_min > 0 and "energy_100" in row.index:
                    if pd.notna(row["energy_100"]) and row["energy_100"] < energy_min:
                        continue
                if structure_min > 0 and "structure_100" in row.index:
                    if pd.notna(row["structure_100"]) and row["structure_100"] < structure_min:
                        continue
                if mp_min > 0 and "mp_100" in row.index:
                    if pd.notna(row["mp_100"]) and row["mp_100"] < mp_min:
                        continue
                if elder_min > 0 and "elder_score" in row.index:
                    if pd.notna(row["elder_score"]) and row["elder_score"] < elder_min:
                        continue

                # Apply sub-component filters (from deep search)
                skip = False
                for col, thresh in subcomp.items():
                    if col in row.index and pd.notna(row[col]):
                        if isinstance(thresh, bool):
                            if row[col] != thresh:
                                skip = True
                                break
                        else:
                            if row[col] < thresh:
                                skip = True
                                break
                    elif col in row.index:
                        # NaN value — can't pass filter
                        skip = True
                        break
                if skip:
                    continue

                signals.append({
                    "ticker": ticker,
                    "date": row["date"],
                    "sc_momentum": float(sc[i]),
                    "ptrs_disposition": "FULL" if sc[i] >= 65 else "HALF" if sc[i] >= 55 else "QUARTER",
                })

    return pd.DataFrame(signals)


if __name__ == "__main__":
    main()
