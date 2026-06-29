"""Aegis Quant Engine -- Math Lab.

Analytical validation page. Every section references the same Precision Edge
recipe so numbers stay in sync. Sequential sections (no expanders -- the user
hates them). Capital $70K, 3% risk per trade.

Launched as part of the multi-page Streamlit app via `run_app.bat`.
"""

from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st  # noqa: E402

st.set_page_config(page_title="AQE Math Lab", page_icon=":bar_chart:", layout="wide")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# -- project path bootstrap ------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import (
    PROJECT_ROOT as _PR,
    OUTPUT_DIR,
    DATA_DIR,
    CAPITAL,
    RISK_PCT,
    RISK_BUDGET,
    ETF_NAMES,
    file_hash,
    is_cloud_mode,
    load_active_recipe,
    load_json,
    require_login,
    run_module_streaming,
    fmt_pct,
    fmt_num,
)

# Password gate — halts with a sign-in form until authenticated (public Space).
require_login()

from src.data.panel_builder import PANEL_DAILY, SPY_DAILY
from src.scanner.score_runner import SCORES_DAILY


# ===================================================================
# Title + caption
# ===================================================================

st.title("Math Lab")

# Math Lab needs the full panel + score parquets for sections 1-5.
# In cloud mode they only exist AFTER the user has run the daily pipeline.
# Section 6 (AQE Readiness Score) pulls directly from FMP and doesn't need them.
_panels_ready = PANEL_DAILY.exists() and SCORES_DAILY.exists()
if is_cloud_mode() and not _panels_ready:
    st.info(
        "Sections 1-5 need the panel + score parquets. Open the **Scanner** page "
        "and click **Bootstrap + run daily pipeline** first (3-5 min). "
        "Section 6 (AQE Readiness Score) is available now."
    )

st.caption(
    "All validation tests reference the same Precision Edge recipe. "
    "Numbers must sync."
)


# ===================================================================
# Sections 1-5 require panel + score parquets
# ===================================================================

if _panels_ready:

    # ===================================================================
    # Recipe Consistency Check
    # ===================================================================

    active_recipe = load_active_recipe()
    walkforward_data = load_json("precision_walkforward.json") or load_json("walkforward_results.json")
    validation_data = load_json("precision_validation.json") or load_json("independent_validation.json")
    sim_data = load_json("portfolio_sim_results.json")


    def _extract_recipe_name(obj: dict | list | None, key: str = "recipe_name") -> str | None:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(key)
        return None


    names = {
        "active_recipe": active_recipe.get("precision", {}).get("name") if isinstance(active_recipe, dict) else None,
        "walkforward": _extract_recipe_name(walkforward_data),
        "validation": _extract_recipe_name(validation_data),
        "simulation": _extract_recipe_name(sim_data),
    }

    found_names = {v for v in names.values() if v}
    if len(found_names) <= 1 and found_names:
        st.success(f"Recipe consistency: all files reference **{found_names.pop()}**.")
    elif len(found_names) == 0:
        st.info("No recipe files found yet. Run the pipeline to generate validation data.")
    else:
        parts = [f"{source}: {name}" for source, name in names.items() if name]
        st.warning("Recipe divergence detected -- " + " | ".join(parts))


    # ===================================================================
    # Section 1: Active Recipe
    # ===================================================================

    st.header("Section 1: Active Recipe")

    precision = active_recipe.get("precision", {}) if isinstance(active_recipe, dict) else {}
    prec_filters = precision.get("subcomp_filters", {})
    prec_backtest = precision.get("_backtest", {})

    if prec_filters:
        st.subheader("Precision Edge Voices")
        voice_items = list(prec_filters.items())
        voice_cols = st.columns(max(len(voice_items), 1))
        for i, (col_name, spec) in enumerate(voice_items):
            if isinstance(spec, dict):
                with voice_cols[i]:
                    st.metric(spec.get("label", col_name), f">= {spec['threshold']}")
                    st.caption(
                        f"_{spec.get('engine', '')}_ -- {spec.get('meaning', '')}"
                    )

        if prec_backtest:
            st.subheader("Backtest Stats")
            b1, b2, b3, b4, b5 = st.columns(5)
            with b1:
                st.metric("Win rate", f"{prec_backtest.get('win_rate', 0)}%")
            with b2:
                st.metric("Trades", f"{prec_backtest.get('trades', 0):,}")
            with b3:
                st.metric("Per week", f"{prec_backtest.get('per_week', 0):.1f}")
            with b4:
                st.metric("Expectancy", f"+{prec_backtest.get('expectancy_r', 0):.2f}R")
            with b5:
                st.metric("Period", prec_backtest.get("period", "?"))

        st.divider()

        # Aggregate Longlist thresholds
        longlist = active_recipe.get("longlist", {}) if isinstance(active_recipe, dict) else {}
        if longlist:
            st.subheader("Aggregate Longlist Thresholds")
            ll_map = [
                ("sc_mom_min", "Momentum"), ("flow_min", "Flow"), ("energy_min", "Energy"),
                ("structure_min", "Structure"), ("mp_min", "MP"), ("elder_min", "Elder"),
            ]
            active_ll = [(k, lbl) for k, lbl in ll_map if longlist.get(k, 0) > 0]
            if active_ll:
                ll_cols = st.columns(len(active_ll))
                for i, (k, lbl) in enumerate(active_ll):
                    with ll_cols[i]:
                        st.metric(f"{lbl} >=", f"{longlist[k]:.0f}")
    else:
        st.info("No Precision Edge recipe in active_recipe.json. Run the sub-component optimizer first.")


    # ===================================================================
    # Section 2: Recipe Optimizer
    # ===================================================================

    st.header("Section 2: Recipe Optimizer")
    st.caption(
        "Auto-maximises win rate + avg R across all threshold combinations. "
        "Set **min trades/week** in the sidebar (your frequency floor), then click Search."
    )

    _opt_run_mode = st.session_state.pop("_opt_run", None)
    _opt_tpw_pending = st.session_state.pop("_opt_tpw", None)

    if _opt_run_mode:
        import json as _json
        import subprocess as _sp
        _tgt_path = DATA_DIR / "optimizer_targets.json"
        _tgt_path.write_text(_json.dumps({
            "non_loss_rate": 0.99,
            "avg_r": 1.0,
            "trades_per_week": float(_opt_tpw_pending or 10),
        }, indent=2))
        _args = [sys.executable, "-u", "-m", "src.calibration.run_optimizer"]
        if _opt_run_mode == "quick":
            _args.append("--quick")
        _log_ph = st.empty()
        _status_ph = st.empty()
        with st.spinner(f"Running {'quick' if _opt_run_mode == 'quick' else 'full'} optimizer search…"):
            try:
                _proc = _sp.Popen(
                    _args, cwd=str(PROJECT_ROOT),
                    stdout=_sp.PIPE, stderr=_sp.STDOUT, text=True, bufsize=1,
                )
                _buf: list[str] = []
                assert _proc.stdout is not None
                for _line in _proc.stdout:
                    _buf.append(_line.rstrip())
                    _log_ph.code("\n".join(_buf[-25:]))
                _rc = _proc.wait()
                if _rc == 0:
                    _status_ph.success("Optimizer finished — results below.")
                else:
                    _status_ph.error(
                        f"Optimizer exited with code {_rc}. Full output:\n\n"
                        + "\n".join(_buf)
                    )
            except Exception as _ex:
                _status_ph.error(f"Failed to launch optimizer: {_ex}")
        st.rerun()

    opt_results = load_json("optimizer_results.json")
    opt_sensitivity = load_json("engine_sensitivity.json")
    _opt_tgt = load_json("optimizer_targets.json") or {}
    _min_tpw_used = float(_opt_tgt.get("trades_per_week", 0))

    if opt_results:
        # Apply trades/week floor and re-sort by win_rate × avg_r (highest first).
        # The score field from the optimizer is target-distance based; re-ranking here
        # ensures the display always shows "best by win rate and R" regardless of
        # what targets were written at run time.
        _filtered = [r for r in opt_results if r.get("trades_per_week", 0) >= _min_tpw_used]
        if not _filtered:
            _filtered = opt_results  # floor too tight — show all
        _filtered.sort(key=lambda r: r.get("win_rate", 0) * max(r.get("avg_r", 0), 0), reverse=True)

        if _min_tpw_used > 0:
            st.caption(f"Results filtered to ≥ {_min_tpw_used:.0f} trades/week · "
                       f"{len(_filtered)} of {len(opt_results)} recipes qualify · "
                       "ranked by win rate × avg R")

        # Engine sensitivity table
        if opt_sensitivity:
            st.subheader("Engine Sensitivity")
            st.caption("Which engines actually predict trade outcomes? Lift = top-25% avg R minus bottom-25% avg R.")
            sens_df = pd.DataFrame(opt_sensitivity)
            sens_df["lift"] = sens_df["lift"].apply(lambda x: f"{x:+.4f}")
            sens_df["correlation"] = sens_df["correlation"].apply(lambda x: f"{x:+.3f}")
            sens_df["avg_r_top_quartile"] = sens_df["avg_r_top_quartile"].apply(lambda x: f"{x:+.4f}")
            sens_df["avg_r_bottom_quartile"] = sens_df["avg_r_bottom_quartile"].apply(lambda x: f"{x:+.4f}")
            st.dataframe(sens_df, use_container_width=True, hide_index=True)
            st.divider()

        # Achievable ranges (within the trades/week floor)
        all_wr = [r["win_rate"] for r in _filtered]
        all_nlr = [r["non_loss_rate"] for r in _filtered]
        all_r = [r["avg_r"] for r in _filtered]
        all_tpw = [r["trades_per_week"] for r in _filtered]
        ra1, ra2, ra3, ra4 = st.columns(4)
        ra1.metric("Win rate range", f"{min(all_wr)*100:.0f}% – {max(all_wr)*100:.0f}%")
        ra2.metric("Non-loss range", f"{min(all_nlr)*100:.0f}% – {max(all_nlr)*100:.0f}%")
        ra3.metric("Avg R range", f"{min(all_r):+.2f} – {max(all_r):+.2f}")
        ra4.metric("Trades/wk range", f"{min(all_tpw):.1f} – {max(all_tpw):.1f}")

        # Top-20 table sorted by win_rate × avg_r
        st.subheader(f"Top recipes — ranked by win rate × avg R")
        cols_wanted = ["sc_mom_min", "flow_min", "energy_min", "structure_min", "mp_min",
                       "elder_min", "phase_filter", "n_trades", "trades_per_week",
                       "win_rate", "non_loss_rate", "avg_r", "oos_avg_r", "wfer", "dsr_pass"]
        _top20_df = pd.DataFrame(_filtered[:20])
        _top20_df = _top20_df[[c for c in cols_wanted if c in _top20_df.columns]].copy()
        _top20_df["win_rate"] = (_top20_df["win_rate"] * 100).round(1).astype(str) + "%"
        _top20_df["non_loss_rate"] = (_top20_df["non_loss_rate"] * 100).round(1).astype(str) + "%"
        st.dataframe(_top20_df, use_container_width=True, hide_index=True)

        # Recommended recipe — highest win_rate × avg_r that also passes WFER, else just top
        _validated = [r for r in _filtered if r.get("wfer", 0) >= 0.30 and r.get("oos_avg_r", 0) > 0]
        best_opt = _validated[0] if _validated else _filtered[0]
        st.subheader("Recommended recipe")
        _wfer_ok = best_opt.get("wfer", 0) >= 0.30
        if _wfer_ok:
            st.success(
                f"Win {best_opt['win_rate']*100:.1f}% | "
                f"Non-loss {best_opt['non_loss_rate']*100:.1f}% | "
                f"Avg R {best_opt['avg_r']:+.3f} | OOS R {best_opt.get('oos_avg_r',0):+.3f} | "
                f"{best_opt['n_trades']} trades ({best_opt['trades_per_week']:.1f}/wk) | "
                f"WFER {best_opt['wfer']:.2f} ✓"
            )
        else:
            st.warning(
                f"Win {best_opt['win_rate']*100:.1f}% | Avg R {best_opt['avg_r']:+.3f} | "
                f"WFER {best_opt.get('wfer',0):.2f} < 0.30 — weak OOS validation. "
                "Trade with caution until walk-forward passes."
            )

        bc1, bc2 = st.columns(2)
        with bc1:
            thresholds_text = (
                f"SC≥{best_opt['sc_mom_min']:.0f} | Flow≥{best_opt['flow_min']:.0f} | "
                f"Energy≥{best_opt['energy_min']:.0f} | Structure≥{best_opt['structure_min']:.0f} | "
                f"MP≥{best_opt['mp_min']:.0f} | Elder≥{best_opt['elder_min']:.0f} | "
                f"Phase={best_opt.get('phase_filter','ANY')}"
            )
            st.caption(thresholds_text)
            if st.button("📥 Load into sliders", key="ml_opt_load_sliders", use_container_width=True):
                st.session_state["ml_sl_sc_mom"] = float(best_opt["sc_mom_min"])
                st.session_state["ml_sl_flow"] = float(best_opt["flow_min"])
                st.session_state["ml_sl_energy"] = float(best_opt["energy_min"])
                st.session_state["ml_sl_structure"] = float(best_opt["structure_min"])
                st.session_state["ml_sl_mp"] = float(best_opt["mp_min"])
                st.session_state["ml_sl_elder"] = float(best_opt["elder_min"])
                st.rerun()
        with bc2:
            if st.button("💾 Promote to active recipe (longlist)", key="ml_opt_promote",
                         use_container_width=True,
                         help="Writes this recipe into active_recipe.json's 'longlist' key. "
                              "The daily pipeline reads this on next run."):
                _ar_path = DATA_DIR / "active_recipe.json"
                import json as _json
                _ar = {}
                if _ar_path.exists():
                    try:
                        _ar = _json.loads(_ar_path.read_text())
                    except Exception:
                        _ar = {}
                _ar["longlist"] = {
                    "name": f"Optimizer pick (Win {best_opt['win_rate']*100:.0f}% "
                            f"AvgR {best_opt['avg_r']:+.2f} WFER {best_opt.get('wfer',0):.2f})",
                    "sc_mom_min": best_opt["sc_mom_min"],
                    "flow_min": best_opt["flow_min"],
                    "energy_min": best_opt["energy_min"],
                    "structure_min": best_opt["structure_min"],
                    "mp_min": best_opt["mp_min"],
                    "elder_min": best_opt["elder_min"],
                    "fip_min": best_opt.get("fip_min", 0),
                    "phase_filter": best_opt.get("phase_filter", "ANY"),
                    "squeeze_min": best_opt.get("squeeze_min", 0),
                }
                _ar_path.write_text(_json.dumps(_ar, indent=2))
                st.success("Promoted to active_recipe.json → longlist. Reload Section 1 to confirm.")
                st.rerun()
    else:
        st.info(
            "No optimizer results yet. Set your targets in the sidebar and click "
            "**Quick search** (~30s) or **Full search** (~2 min)."
        )

    st.divider()


    # ===================================================================
    # Section 3: Walk-Forward Analysis
    # ===================================================================

    st.header("Section 3: Walk-Forward Analysis")
    st.caption("Does the Precision Edge recipe from Section 1 survive on data it was never trained on?")

    wf_raw = walkforward_data
    if wf_raw is not None:
        # Show which recipe was tested
        if isinstance(wf_raw, dict):
            wf_recipe_name = wf_raw.get("recipe_name", "")
            wf_subcomp = wf_raw.get("subcomp_filters", {})
            if wf_recipe_name:
                st.markdown(f"**Testing: {wf_recipe_name}**")
                if wf_subcomp:
                    fstr = " & ".join(f"{k}>={v}" for k, v in wf_subcomp.items())
                    st.caption(f"Filters: {fstr}")

        # Support both dict-with-fixed_recipe and old list format
        if isinstance(wf_raw, dict) and "fixed_recipe" in wf_raw:
            wf_section = wf_raw["fixed_recipe"]
            wf_windows = wf_section.get("windows", [])
            wf_summary = wf_section.get("summary", {})
        elif isinstance(wf_raw, list):
            wf_windows = wf_raw
            wf_summary = {}
        else:
            wf_windows = []
            wf_summary = {}

        if wf_windows:
            wf_df = pd.DataFrame(wf_windows)

            # Metrics from summary or compute
            if wf_summary:
                median_wfer = wf_summary.get("median_wfer", 0)
                pass_rate = wf_summary.get("pass_rate", 0)
                n_robust = wf_summary.get("n_robust", 0)
                n_ok = wf_summary.get("n_ok", 0)
                n_fragile = wf_summary.get("n_fragile", 0)
                n_broken = wf_summary.get("n_broken", 0)
                recent_med = wf_summary.get("recent_half_median", 0)
            else:
                median_wfer = float(wf_df["wfer"].median())
                passing = (wf_df["wfer"] >= 0.30).sum()
                pass_rate = passing / len(wf_df)
                n_robust = int((wf_df["wfer"] >= 0.50).sum())
                n_ok = int(((wf_df["wfer"] >= 0.30) & (wf_df["wfer"] < 0.50)).sum())
                n_fragile = int(((wf_df["wfer"] >= 0) & (wf_df["wfer"] < 0.30)).sum())
                n_broken = int((wf_df["wfer"] < 0).sum())
                recent_med = median_wfer

            # Verdict
            if median_wfer >= 0.50:
                verdict = "ROBUST"
            elif median_wfer >= 0.30:
                verdict = "ACCEPTABLE"
            elif median_wfer >= 0:
                verdict = "FRAGILE"
            else:
                verdict = "BROKEN"

            w1, w2, w3, w4 = st.columns(4)
            with w1:
                st.metric("Median WFER", f"{median_wfer:.3f}")
            with w2:
                st.metric("Pass rate", f"{pass_rate * 100:.0f}%")
            with w3:
                st.metric("Verdict", verdict)
            with w4:
                st.metric("Recent half", f"{recent_med:.3f}")

            st.markdown(
                f"**Window health:** {n_robust} ROBUST | {n_ok} OK | "
                f"{n_fragile} FRAGILE | {n_broken} BROKEN  ({len(wf_df)} total)"
            )

            # --- Trader narrative ---
            st.markdown("---")
            st.markdown(
                "**What is WFER?** Walk-Forward Efficiency Ratio measures how much "
                "of the recipe's in-sample edge survives when tested on *new, unseen "
                "data*. A WFER of 1.0 means 100% of the edge carried over; 0.50 "
                "means half survived; 0 means the edge vanished out-of-sample. "
                "This is the single most important robustness test -- if a recipe "
                "can't pass walk-forward, it's curve-fitted noise."
            )
            if verdict == "ROBUST":
                st.success(
                    "**Your recipe is ROBUST.** The edge consistently survives on "
                    "data it was never trained on. This is the strongest possible "
                    "confirmation that the patterns are real, not fitted. "
                    "Trade this recipe with full conviction."
                )
            elif verdict == "ACCEPTABLE":
                st.info(
                    "**Your recipe is ACCEPTABLE.** The edge survives out-of-sample "
                    "more often than not, but there are windows where it weakens. "
                    "Trade it, but be ready to re-optimise if consecutive windows degrade."
                )
            elif verdict == "FRAGILE":
                st.warning(
                    "**Your recipe is FRAGILE.** The median WFER is near zero, "
                    "meaning the in-sample edge mostly evaporates on new data. "
                    "Some windows may be strong, but the overall track record "
                    "suggests the recipe is sensitive to market conditions. "
                    "Trade with smaller size or tighter stops until you see improvement."
                )
            else:
                st.error(
                    "**Your recipe is BROKEN.** The edge is negative out-of-sample, "
                    "meaning it performs worse than random on new data. "
                    "Do not trade this recipe. Return to the optimizer and find "
                    "new thresholds."
                )

            if recent_med > median_wfer + 0.10:
                st.markdown(
                    f"**Trend:** The recent half of windows (median "
                    f"{recent_med:.3f}) is *stronger* than the full series "
                    f"({median_wfer:.3f}). The recipe is adapting well to current "
                    f"market conditions -- a positive sign."
                )
            elif recent_med < median_wfer - 0.10:
                st.markdown(
                    f"**Trend:** The recent half of windows (median "
                    f"{recent_med:.3f}) is *weaker* than the full series "
                    f"({median_wfer:.3f}). The edge may be fading in current "
                    f"conditions. Watch the next few weeks closely."
                )

            # Window table
            if "status" not in wf_df.columns:
                wf_df["status"] = wf_df["wfer"].apply(
                    lambda w: "ROBUST" if w >= 0.50 else (
                        "OK" if w >= 0.30 else ("FRAGILE" if w >= 0 else "BROKEN")
                    )
                )
            display_cols = [c for c in [
                "window_id", "train_start", "test_start", "test_end",
                "is_avg_r", "oos_avg_r", "oos_n_trades", "oos_win_rate",
                "wfer", "status",
            ] if c in wf_df.columns]
            st.dataframe(wf_df[display_cols], use_container_width=True, hide_index=True)

            # WFER bar chart
            fig_wf, ax_wf = plt.subplots(figsize=(8, 3))
            colors = [
                "green" if w >= 0.30 else ("orange" if w >= 0 else "red")
                for w in wf_df["wfer"]
            ]
            ax_wf.bar(wf_df["window_id"], wf_df["wfer"], color=colors, width=0.8)
            ax_wf.axhline(0.30, color="green", linewidth=0.7, linestyle="--", label="Pass (0.30)")
            ax_wf.axhline(0, color="gray", linewidth=0.5)
            ax_wf.set_ylabel("WFER")
            ax_wf.set_xlabel("Window #")
            ax_wf.set_title("Walk-Forward -- Precision Edge Across Time")
            ax_wf.legend(loc="upper left", fontsize=8)
            ax_wf.set_ylim(
                min(wf_df["wfer"].min() - 0.5, -1),
                max(wf_df["wfer"].max() + 0.5, 2),
            )
            st.pyplot(fig_wf, clear_figure=True)
        else:
            st.info("Walk-forward completed but no windows passed minimum trade count.")
    else:
        st.info("No walk-forward results yet. Run `run_pe_validation.bat` to generate.")


    # ===================================================================
    # Section 3: Independent Validation
    # ===================================================================

    st.header("Section 4: Independent Validation")
    st.caption(
        "3 statistical proofs (Jim Simons-grade rigour). Each answers a different question."
    )

    val_data = validation_data
    if val_data is not None and isinstance(val_data, dict):
        # Show which recipe was tested
        val_recipe_name = val_data.get("recipe_name", "")
        val_subcomp = val_data.get("subcomp_filters", {})
        if val_recipe_name:
            st.markdown(f"**Testing: {val_recipe_name}**")
            if val_subcomp:
                fstr = " & ".join(f"{k}>={v}" for k, v in val_subcomp.items())
                st.caption(f"Filters: {fstr}")

        # ---- Permutation Test ----
        st.subheader("Permutation Test")
        st.caption("Randomly select the same number of trades 5000 times. "
                   "If the recipe beats >95% of random picks, the edge is genuine.")
        perm = val_data.get("permutation", {})
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            st.metric("p-value (avg R)", f"{perm.get('p_value_avg_r', 1):.4f}")
        with pc2:
            st.metric("Percentile", f"{perm.get('percentile_avg_r', 0):.0f}th")
        with pc3:
            perm_pass = perm.get("is_significant", False)
            st.metric("Verdict", "PASS" if perm_pass else "FAIL")

        p_val = perm.get("p_value_avg_r", 1)
        pctl = perm.get("percentile_avg_r", 0)
        if perm_pass:
            st.markdown(
                f"The recipe's average R beats **{pctl:.0f}%** of randomly-selected "
                f"trade groups (p={p_val:.4f}). There is less than a "
                f"{p_val * 100:.1f}% chance the edge is due to luck. "
                f"**The edge is statistically genuine.**"
            )
        else:
            st.markdown(
                f"The recipe only beats **{pctl:.0f}%** of random selections "
                f"(p={p_val:.4f}). To pass, it needs to beat 95%. "
                f"This means the edge *could* be explained by chance alone. "
                f"It doesn't prove the recipe is bad, but it lacks statistical "
                f"proof that it's good."
            )

        # ---- MinTRL ----
        st.subheader("Minimum Track Record Length (MinTRL)")
        st.caption("Bailey & Lopez de Prado (2012): minimum trades needed to confirm the Sharpe is real.")
        mtrl = val_data.get("min_trl", {})
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.metric("Annualised Sharpe", f"{mtrl.get('observed_sharpe_annual', 0):.3f}")
        with mc2:
            needed = mtrl.get("min_trades_needed", 0)
            avail = mtrl.get("trades_available", 0)
            st.metric("Trades needed / available", f"{needed:.0f} / {avail}")
        with mc3:
            mtrl_pass = mtrl.get("sufficient", False)
            st.metric("Verdict", "PASS" if mtrl_pass else "FAIL")

        if mtrl_pass:
            st.markdown(
                f"With **{avail:,}** trades available and only **{needed:,.0f}** "
                f"needed, the track record is long enough to confirm the Sharpe "
                f"ratio is statistically real. **You have enough data to trust "
                f"the numbers.**"
            )
        else:
            st.markdown(
                f"You need at least **{needed:,.0f}** trades to confirm the "
                f"Sharpe ratio is real, but only have **{avail:,}**. The "
                f"performance *might* be genuine, but the sample is too small "
                f"to be certain. More data will accumulate over time."
            )

        # ---- Regime-Conditional ----
        st.subheader("Regime-Conditional Validation")
        st.caption("Split trades by SPY regime (bull/sideways/bear). "
                   "A real edge works across conditions.")
        regime = val_data.get("regime", {})
        slices = regime.get("slices", [])
        if slices:
            reg_df = pd.DataFrame(slices)
            if "win_rate" in reg_df.columns:
                reg_df["win_rate"] = (reg_df["win_rate"] * 100).round(1).astype(str) + "%"
            if "profitable" in reg_df.columns:
                reg_df["profitable"] = reg_df["profitable"].map({True: "PROFIT", False: "LOSS"})
            show_cols = [c for c in ["regime", "n_trades", "avg_r", "win_rate", "sharpe", "profitable"]
                         if c in reg_df.columns]
            st.dataframe(reg_df[show_cols], use_container_width=True, hide_index=True)

        rc1, rc2 = st.columns(2)
        with rc1:
            st.metric(
                "Profitable regimes",
                f"{regime.get('n_profitable_regimes', 0)}/{regime.get('n_total_regimes', 0)}",
            )
        with rc2:
            reg_pass = regime.get("all_regimes_profitable", False)
            n_prof = regime.get("n_profitable_regimes", 0)
            st.metric(
                "Verdict",
                "PASS" if reg_pass else ("PARTIAL" if n_prof > 0 else "FAIL"),
            )

        n_total_reg = regime.get("n_total_regimes", 0)
        if reg_pass:
            st.markdown(
                "The recipe makes money in bull, sideways, *and* bear markets. "
                "This is the gold standard -- an edge that works regardless of "
                "conditions. You won't need to turn it off when markets get rough."
            )
        elif n_prof > 0:
            st.markdown(
                f"The recipe is profitable in **{n_prof}** out of "
                f"**{n_total_reg}** market regimes. It has blind spots -- "
                f"certain conditions where it loses money. Know which regimes "
                f"hurt and consider reducing size during those periods."
            )
        else:
            st.markdown(
                "The recipe loses money across all market regimes tested. "
                "This is a strong signal the edge doesn't generalise. "
                "Do not trade this recipe in its current form."
            )

        # ---- Overall ----
        passing_count = sum([
            perm.get("is_significant", False),
            mtrl.get("sufficient", False),
            regime.get("all_regimes_profitable", False),
        ])
        st.subheader(f"Overall: {passing_count}/3 PASS")
        if passing_count == 3:
            st.success("Strong independent evidence that this recipe has genuine predictive power.")
        elif passing_count >= 2:
            st.warning("Majority of evidence supports genuine edge. Monitor the failing test.")
        else:
            st.error("Insufficient independent evidence. Use with caution.")

        st.markdown("---")
        if passing_count == 3:
            st.markdown(
                "**Bottom line:** All three independent tests confirm a genuine "
                "edge. The recipe has statistical proof (permutation), enough "
                "data to trust (MinTRL), and works across market conditions "
                "(regime). **Trade with full confidence.**"
            )
        elif passing_count == 2:
            st.markdown(
                "**Bottom line:** Two out of three tests pass, which is solid "
                "but not perfect. The failing test tells you where the recipe "
                "has a weakness. Address it if you can, or accept the limitation "
                "and trade accordingly."
            )
        elif passing_count == 1:
            st.markdown(
                "**Bottom line:** Only one test passes. The evidence for a "
                "genuine edge is weak. Consider this recipe experimental -- "
                "trade with reduced size and tight risk management until more "
                "data accumulates."
            )
        else:
            st.markdown(
                "**Bottom line:** No tests pass. There is no statistical evidence "
                "that this recipe has a genuine edge. Return to the optimizer "
                "and find better thresholds."
            )
    else:
        st.info("No validation results yet. Run `run_pe_validation.bat` to generate.")


    # ===================================================================
    # Section 4: Portfolio Simulation
    # ===================================================================

    st.header("Section 5: Portfolio Simulation")

    if sim_data is not None and isinstance(sim_data, dict):
        sim_recipe = sim_data.get("recipe", {})
        if sim_recipe:
            rname = sim_recipe.get("recipe_name", "")
            subcomp = sim_recipe.get("subcomp_filters", {})
            if rname and subcomp:
                fstr = " & ".join(f"{k}>={v}" for k, v in subcomp.items())
                st.info(f"Results for: **{rname}** ({fstr})")
            else:
                parts = []
                if sim_recipe.get("sc_mom_min", 0) > 0:
                    parts.append(f"SC>={sim_recipe['sc_mom_min']:.0f}")
                if sim_recipe.get("flow_min", 0) > 0:
                    parts.append(f"Flow>={sim_recipe['flow_min']:.0f}")
                if sim_recipe.get("energy_min", 0) > 0:
                    parts.append(f"Energy>={sim_recipe['energy_min']:.0f}")
                if sim_recipe.get("structure_min", 0) > 0:
                    parts.append(f"Struct>={sim_recipe['structure_min']:.0f}")
                if sim_recipe.get("mp_min", 0) > 0:
                    parts.append(f"MP>={sim_recipe['mp_min']:.0f}")
                if parts:
                    st.info(f"Results for recipe: **{' | '.join(parts)}**")

        s = sim_data.get("summary", {})
        mc = sim_data.get("monte_carlo", {})

        # Primary metrics
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.metric("Total trades", s.get("total_trades", 0))
        with s2:
            st.metric("Win rate", f"{s.get('win_rate_pct', 0):.1f}%")
        with s3:
            st.metric("Total P&L", f"${s.get('total_pnl', 0):,.0f}")
        with s4:
            st.metric("Final equity", f"${s.get('final_equity', 0):,.0f}")

        # Secondary metrics
        s5, s6, s7, s8 = st.columns(4)
        with s5:
            st.metric("Avg R", f"{s.get('avg_r', 0):+.2f}")
        with s6:
            st.metric("Max drawdown", f"{s.get('max_drawdown_pct', 0):.1f}%")
        with s7:
            st.metric("Annual return", f"{s.get('annual_return_pct', 0):+.1f}%")
        with s8:
            st.metric("Adj (-2% bias)", f"{s.get('adjusted_annual_pct', 0):+.1f}%")

        # Transaction costs + trail tiers
        st.markdown(
            f"**Transaction costs:** ${s.get('total_costs', 0):,.0f} total "
            f"({s.get('cost_drag_pct', 0):.2f}% of capital)"
        )
        tier_dist = s.get("peak_tier_distribution", {})
        if tier_dist:
            st.markdown(
                "**Trail tier distribution:** "
                + " | ".join(f"{k}: {v}" for k, v in tier_dist.items())
            )

        # Monte Carlo
        if mc:
            st.markdown("**Monte Carlo (2000 permutations):**")
            st.markdown(
                f"- Median max drawdown: {mc.get('median_max_dd_pct', 0):.1f}%\n"
                f"- 95th percentile DD: {mc.get('p95_max_dd_pct', 0):.1f}%\n"
                f"- Risk of ruin (>25% DD): {mc.get('risk_of_ruin_pct', 0):.1f}%\n"
                f"- Original sequence: {mc.get('original_percentile', 50):.0f}th percentile"
            )

        # Equity curve
        eq_data = sim_data.get("equity_curve", [])
        if eq_data:
            eq_df = pd.DataFrame(eq_data)
            eq_df["date"] = pd.to_datetime(eq_df["date"])
            fig_eq, ax_eq = plt.subplots(figsize=(8, 3))
            ax_eq.plot(eq_df["date"], eq_df["equity"], color="steelblue", linewidth=1)
            ax_eq.axhline(CAPITAL, color="gray", linewidth=0.7, linestyle=":")
            ax_eq.set_ylabel("Equity ($)")
            ax_eq.set_title("Portfolio Equity Curve")
            st.pyplot(fig_eq, clear_figure=True)

        # Stress test
        stress = sim_data.get("stress_test", {})
        if stress:
            st.subheader("Correlated Loss Stress Test")
            st.caption(
                "Monte Carlo shuffles trade order, hiding the fact that market drops "
                "stop out multiple positions at once. This test uses actual concurrent exposure."
            )
            grade = stress.get("stress_grade", "?")
            sc1, sc2, sc3, sc4 = st.columns(4)
            with sc1:
                st.metric("Stress Grade", grade)
            with sc2:
                st.metric("Peak concurrent", f"{stress.get('max_concurrent_positions', 0)} positions")
            with sc3:
                st.metric("Worst week", f"{stress.get('worst_week_loss_pct', 0):+.1f}%")
            with sc4:
                st.metric("Max stop-all", f"{stress.get('max_simultaneous_stop_pct', 0):.0f}%")

            sc5, sc6, sc7, sc8 = st.columns(4)
            with sc5:
                cluster_pct = stress.get("loss_cluster_ratio", 0)
                st.metric("Losses clustered", f"{cluster_pct * 100:.0f}%")
            with sc6:
                st.metric(
                    "Worst cluster",
                    f"{stress.get('worst_cluster_n', 0)} losses / "
                    f"{stress.get('worst_cluster_r', 0):+.1f}R",
                )
            with sc7:
                st.metric("Max underwater", f"~{stress.get('max_underwater_days', 0)}d")
            with sc8:
                st.metric("Longest loss streak", f"{stress.get('longest_losing_streak', 0)} trades")

            if not stress.get("survives_max_stress", True):
                st.error(
                    "WARNING: Max stress scenario exceeds 50% of capital. "
                    "Consider reducing position count or risk%."
                )

            # Stress narrative
            st.markdown("---")
            st.markdown(
                "**What this test does:** Monte Carlo simulations randomise trade "
                "order, which hides the fact that market crashes stop out multiple "
                "positions *simultaneously*. This stress test preserves the actual "
                "timing -- if 4 trades were open during a crash, it measures the "
                "damage of all 4 stopping out together."
            )
            _max_conc = stress.get("max_concurrent_positions", 0)
            _worst_wk = stress.get("worst_week_loss_pct", 0)
            _cluster_r = stress.get("loss_cluster_ratio", 0)
            _max_uw = stress.get("max_underwater_days", 0)
            _max_stop = stress.get("max_simultaneous_stop_pct", 0)
            st.markdown(
                f"- **Peak concurrent exposure:** {_max_conc} positions open at "
                f"the same time. If all hit stops simultaneously, you lose "
                f"{_max_stop:.0f}% of capital.\n"
                f"- **Worst single week:** {_worst_wk:+.1f}% -- the biggest "
                f"weekly drawdown with correlated exits.\n"
                f"- **Loss clustering:** {_cluster_r * 100:.0f}% of losses came "
                f"in clusters (3+ losses within 5 days). High clustering means "
                f"losses pile up during stress, not spread evenly.\n"
                f"- **Max underwater period:** ~{_max_uw} days before recovering "
                f"to a new equity high."
            )
            if grade in ("A", "B"):
                st.success(
                    f"**Grade {grade} -- Low correlated risk.** Losses don't "
                    f"pile up dangerously. The worst-case scenarios are survivable "
                    f"at your current position sizing."
                )
            elif grade == "C":
                st.warning(
                    f"**Grade {grade} -- Moderate correlated risk.** Some loss "
                    f"clustering is present. Manageable, but a severe market shock "
                    f"could temporarily push drawdown beyond comfort levels."
                )
            else:
                st.error(
                    f"**Grade {grade} -- High correlated risk.** Losses cluster "
                    f"heavily during market stress. Consider reducing max "
                    f"concurrent positions or tightening sector diversification "
                    f"rules."
                )

        # Re-run button
        if st.button("Re-run simulation", key="math_lab_rerun_sim"):
            log = st.empty()
            status = st.empty()
            with st.spinner("Running portfolio simulation..."):
                run_module_streaming("src.backtest.run_sim", "Portfolio simulation", log, status)
            st.rerun()
    else:
        st.info(
            "No simulation results yet. Click 'Re-run simulation' above "
            "or double-click `run_portfolio_sim.bat`."
        )


# ===================================================================
# Section 6: AQE Readiness Score
# ===================================================================

st.header("Section 6: AQE Readiness Score")
st.caption(
    "Progressive daily score (0-100) per ticker — tells the PM WHEN to enter. "
    "Builds over days as conditions accumulate (coil evidence, VWAP positioning, "
    "structure proximity). Tests trigger thresholds (50-90) vs random-entry "
    "baseline. Validates VSCO/BROS/CAT reference cases. Component importance "
    "analysis identifies which parts of the score drive edge."
)

_rd_result_path = OUTPUT_DIR / "mathlab_readiness.json"
_rd_run = st.session_state.pop("_rd_run", None)

if _rd_run:
    _rd_log = st.empty()
    _rd_status = st.empty()
    _rd_args = [sys.executable, "-u", "-m", "src.mathlab.backtest_readiness"]
    if _rd_run == "dry":
        _rd_args.append("--dry-run")
    if _rd_run == "refresh":
        _rd_args.append("--refresh")
    if _rd_run == "reference":
        _rd_args.append("--reference-only")
    with st.spinner("Running readiness backtest..."):
        try:
            _rd_proc = __import__("subprocess").Popen(
                _rd_args, cwd=str(PROJECT_ROOT),
                stdout=__import__("subprocess").PIPE,
                stderr=__import__("subprocess").STDOUT, text=True, bufsize=1,
            )
            _rd_buf: list[str] = []
            assert _rd_proc.stdout is not None
            for _rd_line in _rd_proc.stdout:
                _rd_buf.append(_rd_line.rstrip())
                _rd_log.code("\n".join(_rd_buf[-30:]))
            _rd_rc = _rd_proc.wait()
            if _rd_rc == 0:
                _rd_status.success("Readiness backtest complete.")
            else:
                _rd_status.error(f"Backtest exited with code {_rd_rc}")
        except Exception as _rd_ex:
            _rd_status.error(f"Failed to run: {_rd_ex}")
    st.rerun()

# Buttons
_rdc1, _rdc2, _rdc3, _rdc4 = st.columns(4)
with _rdc1:
    if st.button("Run readiness backtest", key="rd_bt_full", type="primary",
                  use_container_width=True,
                  help="Full universe, 7 thresholds (50-90), baseline, trajectory, "
                       "component importance, reference cases. Uses cached bars."):
        st.session_state["_rd_run"] = "full"
        st.rerun()
with _rdc2:
    if st.button("Fresh pull + run", key="rd_bt_refresh",
                  use_container_width=True,
                  help="Clear bar cache and re-pull from FMP, then full backtest."):
        st.session_state["_rd_run"] = "refresh"
        st.rerun()
with _rdc3:
    if st.button("Reference cases only", key="rd_bt_ref",
                  use_container_width=True,
                  help="VSCO/BROS/CAT only — validates the score against known cases."):
        st.session_state["_rd_run"] = "reference"
        st.rerun()
with _rdc4:
    if st.button("Dry run (6 tickers)", key="rd_bt_dry",
                  use_container_width=True,
                  help="Quick logic check."):
        st.session_state["_rd_run"] = "dry"
        st.rerun()

# Display results
if _rd_result_path.exists():
    import json as _json_rd
    _rd = _json_rd.loads(_rd_result_path.read_text(encoding="utf-8"))
    if _rd:
        _rd_mode = _rd.get("mode", "full")
        _rd_run_date = _rd.get("run_date", "?")
        _rd_usize = _rd.get("universe_size", 0)
        _rd_total_dates = _rd.get("total_dates_scanned", 0)
        _rd_total_bk = _rd.get("total_brackets", 0)
        _rd_best_t = _rd.get("best_threshold")

        st.markdown(
            f"**Last run:** {_rd_run_date} | **Mode:** {_rd_mode} | "
            f"**Universe:** {_rd_usize} tickers | **Dates scanned:** "
            f"{_rd_total_dates:,} | **Brackets:** {_rd_total_bk:,}"
        )

        # ── Baseline metrics ──
        _rd_bl = _rd.get("baseline", {})
        if _rd_bl:
            _rd_blc = st.columns(5)
            with _rd_blc[0]:
                st.metric("Baseline TP1 Win", f"{_rd_bl.get('tp1_win_rate',0)*100:.1f}%")
            with _rd_blc[1]:
                st.metric("Baseline SL Hit", f"{_rd_bl.get('sl_hit_rate',0)*100:.1f}%")
            with _rd_blc[2]:
                st.metric("Baseline DD", f"{_rd_bl.get('avg_dd_pct',0):+.2f}%")
            with _rd_blc[3]:
                st.metric("Baseline T+5", f"{_rd_bl.get('avg_return_T5_pct',0):+.2f}%")
            with _rd_blc[4]:
                st.metric("Baseline T+10", f"{_rd_bl.get('avg_return_T10_pct',0):+.2f}%")

        # ── Pass / Fail verdicts ──
        _rd_pf = _rd.get("pass_fail", {})
        if _rd_pf:
            st.subheader("Pass / Fail Verdicts")
            _rd_pf_keys = [
                ("readiness_signal", "Readiness Signal"),
                ("trajectory_filter", "Trajectory Filter"),
            ]
            _rd_vcols = st.columns(len(_rd_pf_keys))
            for _rd_col, (_rd_key, _rd_label) in zip(_rd_vcols, _rd_pf_keys):
                with _rd_col:
                    _rd_entry = _rd_pf.get(_rd_key, {})
                    _rd_v = _rd_entry.get("verdict", "?")
                    st.metric(_rd_label, _rd_v)
                    _rd_crit = _rd_entry.get("criterion", "")
                    if _rd_crit:
                        st.caption(_rd_crit)

            if _rd_best_t is not None:
                st.info(f"Best threshold: **{_rd_best_t}** (edge: "
                        f"{_rd_pf.get('readiness_signal',{}).get('edge',0)*100:+.1f}pp, "
                        f"n={_rd_pf.get('readiness_signal',{}).get('n',0):,})")

        # ── Threshold comparison table ──
        _rd_thresholds = _rd.get("thresholds", {})
        if _rd_thresholds:
            st.subheader("Threshold Comparison")
            _rd_t_rows = []
            for t in (50, 60, 70, 75, 80, 85, 90):
                ts = _rd_thresholds.get(str(t), {}).get("stats", {})
                if not ts:
                    continue
                marker = " **" if t == _rd_best_t else ""
                _rd_t_rows.append({
                    "Threshold": f"{t}{marker}",
                    "N": ts.get("n", 0),
                    "TP1 Win %": f"{ts.get('tp1_win_rate',0)*100:.1f}%",
                    "Edge pp": f"{ts.get('edge_vs_baseline',0)*100:+.1f}",
                    "SL Hit %": f"{ts.get('sl_hit_rate',0)*100:.1f}%",
                    "Avg DD %": f"{ts.get('avg_dd_pct',0):+.2f}%",
                    "Avg Days→TP1": f"{ts.get('avg_days_to_tp1',0):.1f}",
                    "Med Days→TP1": f"{ts.get('median_days_to_tp1',0):.1f}",
                    "TP1→TP2 %": f"{ts.get('tp1_then_tp2_rate',0)*100:.1f}%",
                })
            if _rd_t_rows:
                st.dataframe(pd.DataFrame(_rd_t_rows), use_container_width=True, hide_index=True)

        # ── Trajectory cross-test (best threshold) ──
        if _rd_best_t is not None:
            _rd_traj = _rd_thresholds.get(str(_rd_best_t), {}).get("trajectory", {})
            if _rd_traj:
                st.subheader(f"Trajectory Cross-Test (Threshold {_rd_best_t})")
                _rd_tj_rows = []
                for tj in ("BUILDING", "STABLE", "CHOPPY", "DEGRADING"):
                    ts = _rd_traj.get(tj, {})
                    _rd_tj_rows.append({
                        "Trajectory": tj,
                        "N": ts.get("n", 0),
                        "TP1 Win %": f"{ts.get('tp1_win_rate',0)*100:.1f}%",
                        "Edge pp": f"{ts.get('edge_vs_baseline',0)*100:+.1f}",
                        "SL Hit %": f"{ts.get('sl_hit_rate',0)*100:.1f}%",
                        "Avg DD %": f"{ts.get('avg_dd_pct',0):+.2f}%",
                        "Avg Days→TP1": f"{ts.get('avg_days_to_tp1',0):.1f}",
                    })
                st.dataframe(pd.DataFrame(_rd_tj_rows), use_container_width=True, hide_index=True)

        # ── Time profile (best threshold vs baseline) ──
        if _rd_best_t is not None:
            _rd_tp = _rd_thresholds.get(str(_rd_best_t), {}).get("time_profile", {})
            _rd_bl_tp = _rd.get("baseline_time_profile", {})
            if _rd_tp:
                st.subheader(f"Time Profile (Threshold {_rd_best_t} vs Baseline)")
                _rd_tp_rows = []
                for label, src in [("Signal", _rd_tp), ("Baseline", _rd_bl_tp)]:
                    row = {"": label}
                    for h in (1, 2, 3, 5, 7, 10):
                        k = f"T+{h}"
                        val = src.get(k, {}).get("avg_return_pct", 0)
                        prof = src.get(k, {}).get("pct_profitable", 0) * 100
                        row[k] = f"{val:+.2f}% ({prof:.0f}%)"
                    _rd_tp_rows.append(row)
                st.dataframe(pd.DataFrame(_rd_tp_rows), use_container_width=True, hide_index=True)

        # ── Component importance ──
        _rd_imp = _rd.get("component_importance", {})
        if _rd_imp:
            st.subheader("Component Importance")
            _rd_imp_sorted = sorted(_rd_imp.items(),
                                     key=lambda x: abs(x[1].get("correlation", 0) or 0),
                                     reverse=True)
            _rd_imp_rows = []
            for comp, data in _rd_imp_sorted:
                corr = data.get("correlation", 0) or 0
                edge = data.get("edge_when_high", 0) or 0
                p75 = data.get("p75_threshold")
                _rd_imp_rows.append({
                    "Component": comp,
                    "N": data.get("n", 0),
                    "Correlation": f"{corr:+.4f}",
                    "TP1% when High": f"{data.get('tp1_rate_when_high',0)*100:.1f}%" if data.get("tp1_rate_when_high") is not None else "—",
                    "TP1% when Low": f"{data.get('tp1_rate_when_low',0)*100:.1f}%" if data.get("tp1_rate_when_low") is not None else "—",
                    "Edge (High-Low)": f"{edge*100:+.1f}pp",
                    "P75 Threshold": f"{p75:.1f}" if p75 is not None else "—",
                })
            st.dataframe(pd.DataFrame(_rd_imp_rows), use_container_width=True, hide_index=True)

        # ── Reference cases ──
        _rd_refs = _rd.get("reference_cases", {})
        if _rd_refs:
            st.subheader("Reference Cases (VSCO / BROS / CAT)")
            for _rd_tk in ("VSCO", "BROS", "CAT"):
                _rd_ref = _rd_refs.get(_rd_tk, {})
                _rd_ref_status = _rd_ref.get("status", "?")
                with st.expander(f"{_rd_tk} — {_rd_ref_status}", expanded=(_rd_ref_status == "OK")):
                    if _rd_ref_status == "OK":
                        _rd_daily = _rd_ref.get("daily", [])
                        _rd_checks = _rd_ref.get("checks", {})
                        _rd_traj_label = _rd_ref.get("trajectory", "?")

                        # Score trajectory chart
                        if _rd_daily:
                            _rd_dates = [d["date"] for d in _rd_daily]
                            _rd_scores = [d["score"] for d in _rd_daily]
                            _rd_fig, _rd_ax = plt.subplots(figsize=(8, 2.5))
                            _rd_ax.plot(_rd_dates, _rd_scores, marker="o", markersize=3,
                                        linewidth=1.5, color="steelblue")
                            _rd_ax.axhline(75, color="green", linestyle=":", linewidth=0.7, label="READY (75)")
                            _rd_ax.axhline(60, color="orange", linestyle=":", linewidth=0.7, label="APPROACHING (60)")
                            _rd_ax.set_ylim(0, 100)
                            _rd_ax.set_ylabel("Readiness")
                            _rd_ax.set_title(f"{_rd_tk} — {_rd_traj_label}")
                            _rd_ax.legend(fontsize=7, loc="upper left")
                            _rd_ax.tick_params(axis="x", rotation=45, labelsize=7)
                            _rd_ax.grid(alpha=0.2)
                            st.pyplot(_rd_fig, clear_figure=True)

                        # Daily detail table
                        if _rd_daily:
                            _rd_d_rows = []
                            for d in _rd_daily:
                                row = {
                                    "Date": d["date"],
                                    "Score": d["score"],
                                    "Stage": d["stage"],
                                    "Failed BO": "Y" if d.get("failed_breakout") else "",
                                }
                                comps = d.get("components", {})
                                for ck in ("vol_coil", "range_coil", "vwap", "proximity",
                                           "close_quality", "ma_stack", "trigger", "base_len"):
                                    row[ck] = comps.get(ck, 0)
                                _rd_d_rows.append(row)
                            st.dataframe(pd.DataFrame(_rd_d_rows), use_container_width=True, hide_index=True)

                        # Validation checks
                        if _rd_checks:
                            st.markdown("**Checks:**")
                            for ck, cv in _rd_checks.items():
                                icon = "✓" if cv is True else ("✗" if cv is False else "—")
                                st.markdown(f"- {icon} `{ck}` = `{cv}`")
                    else:
                        st.warning(f"Status: {_rd_ref_status}")

        # ── Weights used ──
        _rd_weights = _rd.get("weights", {})
        if _rd_weights:
            with st.expander("Score weights used"):
                st.json(_rd_weights)

        # ── Download ──
        st.download_button(
            "Download readiness results JSON",
            data=_rd_result_path.read_text(),
            file_name="mathlab_readiness.json",
            mime="application/json",
            key="rd_dl_json",
        )
else:
    st.info(
        "No readiness backtest results yet. Click **Run readiness backtest** above. "
        "First run pulls daily bars from FMP (~5-10 min, cached after)."
    )


# ===================================================================
# Divider: Historical Exploration (needs parquets)
# ===================================================================

if _panels_ready:
    st.divider()
    st.info(
        "**Historical Exploration** -- Set recipe thresholds in the sidebar, "
        "then click **Run scan** to generate historical signal analysis below."
    )


    # ===================================================================
    # Sidebar: recipe sliders + actions
    # ===================================================================

    with st.sidebar:
        st.header("Recipe Sliders")
        st.caption("Set thresholds for historical scan. These do NOT modify active_recipe.json.")

        sc_mom_min = st.slider(
            "Momentum composite >=", 0.0, 100.0, 75.0, step=1.0,
            key="ml_sl_sc_mom",
            help="SC_MOMENTUM (0-100). The headline score blending Flow, Energy, Structure, MP.",
        )
        flow_min = st.slider(
            "Money Flow >=", 0.0, 100.0, 0.0, step=1.0,
            key="ml_sl_flow",
            help="Flow v1.3 (0-100). Higher = institutional flow + accumulation favourable.",
        )
        energy_min = st.slider(
            "Trend Energy >=", 0.0, 100.0, 0.0, step=1.0,
            key="ml_sl_energy",
            help="Energy v1.3 (0-100). Higher = volatility coiled, price tight.",
        )
        structure_min = st.slider(
            "Price Structure >=", 0.0, 100.0, 0.0, step=1.0,
            key="ml_sl_structure",
            help="Structure v1.5 (0-100). Higher = strong RS, good base, weekly trend up.",
        )
        mp_min = st.slider(
            "Market Posture >=", 0.0, 100.0, 0.0, step=1.0,
            key="ml_sl_mp",
            help="Momentum Persistence v1.2 (0-100). Higher = ADX strong, MA stack intact.",
        )
        elder_min = st.slider(
            "Elder Impulse >=", 0.0, 10.0, 0.0, step=0.5,
            key="ml_sl_elder",
            help="Elder Impulse (0-10). Higher = green impulse bars, rising EMA.",
        )

        st.divider()

        # Load saved recipe
        from src.analyzer.recipe import Recipe, load_recipes, save_recipes, upsert_recipe

        saved_recipes = load_recipes()
        recipe_names = ["<custom>"] + [r.name for r in saved_recipes]
        chosen_recipe_name = st.selectbox(
            "Load saved recipe", recipe_names, index=0, key="ml_recipe_select",
        )
        if chosen_recipe_name != "<custom>":
            base = next((r for r in saved_recipes if r.name == chosen_recipe_name), None)
            if base and st.session_state.get("_ml_last_recipe") != chosen_recipe_name:
                st.session_state["ml_sl_sc_mom"] = float(base.sc_mom_min)
                st.session_state["ml_sl_flow"] = float(base.flow_min)
                st.session_state["ml_sl_energy"] = float(base.energy_min)
                st.session_state["ml_sl_structure"] = float(base.structure_min)
                st.session_state["ml_sl_mp"] = float(base.mp_min)
                st.session_state["ml_sl_elder"] = float(base.elder_min)
                st.session_state["_ml_last_recipe"] = chosen_recipe_name
                st.rerun()
        st.session_state["_ml_last_recipe"] = chosen_recipe_name

        # Compare against
        compare_names = ["<none>"] + [r.name for r in saved_recipes if r.name != chosen_recipe_name]
        baseline_recipe_name = st.selectbox(
            "Compare against", compare_names, index=0, key="ml_compare",
        )

        st.divider()

        # Save recipe
        save_name = st.text_input("Save recipe as", value="", key="ml_save_name")
        existing_names = {r.name for r in saved_recipes}
        confirm_overwrite = False
        if save_name.strip() and save_name.strip() in existing_names:
            confirm_overwrite = st.checkbox("Overwrite existing?", value=False, key="ml_overwrite")
        if st.button("Save recipe", key="ml_save_btn") and save_name.strip():
            name = save_name.strip()
            if name in existing_names and not confirm_overwrite:
                st.warning("Name already exists. Tick overwrite box.")
            else:
                new_recipe = Recipe(
                    name=name,
                    sc_mom_min=sc_mom_min,
                    flow_min=flow_min,
                    energy_min=energy_min,
                    structure_min=structure_min,
                    mp_min=mp_min,
                    elder_min=elder_min,
                )
                updated = upsert_recipe(saved_recipes, new_recipe)
                save_recipes(updated)
                st.success(f"Saved recipe '{name}'.")
                st.rerun()

        st.divider()

        # ── Optimizer ─────────────────────────────────────────────────
        st.subheader("Find optimal recipe")
        st.caption(
            "One input: minimum signals per week (your liquidity floor). "
            "The optimizer auto-maximises win rate + avg R across all threshold combos."
        )
        min_tpw = st.slider(
            "Min trades/week", 2, 20, 10, step=1, key="ml_min_tpw",
            help="Recipes with fewer signals than this are ignored. "
                 "Lower = tighter filters, fewer but higher-quality signals.",
        )
        if st.button("⚡ Quick search (~30s)", use_container_width=True, key="ml_opt_quick",
                     help="Reduced grid ~500 combos. Good for a first pass."):
            st.session_state["_opt_run"] = "quick"
            st.session_state["_opt_tpw"] = float(min_tpw)
            st.rerun()
        if st.button("🔍 Full search (~2 min)", use_container_width=True, key="ml_opt_full",
                     help="All ~7,800 combinations. Use after Quick to confirm."):
            st.session_state["_opt_run"] = "full"
            st.session_state["_opt_tpw"] = float(min_tpw)
            st.rerun()

        st.divider()

        # Run scan button
        run_scan = st.button("Run scan", type="primary", use_container_width=True, key="ml_run_scan")

        # Run PE validation button
        run_pe_val = st.button(
            "Run PE validation", use_container_width=True, key="ml_run_pe_val",
            help="Runs walk-forward + independent validation for Precision Edge recipe.",
        )

        if run_pe_val:
            log = st.empty()
            status = st.empty()
            with st.spinner("Running Precision Edge validation..."):
                run_module_streaming(
                    "src.calibration.run_pe_validation",
                    "PE validation",
                    log,
                    status,
                )
            st.rerun()


    # ===================================================================
    # Historical Scan Section (only if Run scan was clicked)
    # ===================================================================

    if not run_scan:
        st.stop()

    # ---- Imports for scanning ----
    from src.scanner.signal_detector import detect_crossups
    from src.scanner.outcome_tracker import attach_signal_context, compute_outcomes
    from src.scanner.dsl import compute_dsl_outcomes
    from src.analyzer.recipe import Recipe, apply_filter, load_recipes, save_recipes, upsert_recipe
    from src.analyzer import metrics as M
    from src.analyzer.baselines import random_baseline, spy_baseline


    # ---- Cached data loaders ----

    @st.cache_data(show_spinner=False)
    def _load_panel(mtime_key: str) -> pd.DataFrame:  # noqa: ARG001
        if not PANEL_DAILY.exists():
            return pd.DataFrame()
        df = pd.read_parquet(PANEL_DAILY)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df


    @st.cache_data(show_spinner=False)
    def _load_scores(mtime_key: str) -> pd.DataFrame:  # noqa: ARG001
        if not SCORES_DAILY.exists():
            return pd.DataFrame()
        df = pd.read_parquet(SCORES_DAILY)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df


    @st.cache_data(show_spinner=False)
    def _load_spy(mtime_key: str) -> pd.DataFrame:  # noqa: ARG001
        if not SPY_DAILY.exists():
            return pd.DataFrame()
        df = pd.read_parquet(SPY_DAILY)
        df["date"] = pd.to_datetime(df["date"]).dt.normalize()
        return df


    @st.cache_data(show_spinner=False)
    def scan_and_attach(
        scores_hash: str,
        panel_hash: str,
        threshold: float,
        cooldown_days: int,
        date_start: pd.Timestamp,
        date_end: pd.Timestamp,
        tickers: tuple[str, ...] | None,
    ) -> pd.DataFrame:
        """Run signal detection + outcome computation. Cached on input parameters."""
        scores = _load_scores(scores_hash)
        if scores.empty:
            return scores
        if tickers:
            scores = scores.loc[scores["ticker"].isin(tickers)]
        scores = scores.loc[(scores["date"] >= date_start) & (scores["date"] <= date_end)]
        if scores.empty:
            return scores
        panel = _load_panel(panel_hash)
        if panel.empty:
            return panel
        events = detect_crossups(scores, threshold=threshold, cooldown_days=cooldown_days)
        if events.empty:
            return events
        with_ctx = attach_signal_context(events, scores)
        return compute_outcomes(with_ctx, panel)


    @st.cache_data(show_spinner=False)
    def compute_baselines(
        scores_hash: str,
        panel_hash: str,
        spy_hash: str,
        signals: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Compute random and SPY baselines. Cached on file mtimes."""
        if signals.empty:
            return signals.copy(), signals.copy()
        scores = _load_scores(scores_hash)
        panel = _load_panel(panel_hash)
        spy = _load_spy(spy_hash)
        rand = random_baseline(signals, panel, scores)
        spy_ret = spy_baseline(signals, spy)
        return rand, spy_ret


    # ---- Execute scan ----

    scores_hash = file_hash(SCORES_DAILY)
    panel_hash = file_hash(PANEL_DAILY)
    spy_hash = file_hash(SPY_DAILY)

    scores = _load_scores(scores_hash)
    panel = _load_panel(panel_hash)

    if scores.empty or panel.empty:
        st.warning("Missing price or score data. Build the data first from the main page.")
        st.stop()

    min_date = scores["date"].min().date()
    max_date = scores["date"].max().date()

    recipe = Recipe(
        name="Math Lab ad-hoc",
        sc_mom_min=sc_mom_min,
        flow_min=flow_min,
        energy_min=energy_min,
        structure_min=structure_min,
        mp_min=mp_min,
        elder_min=elder_min,
    )
    baseline_recipe = (
        next((r for r in saved_recipes if r.name == baseline_recipe_name), None)
        if baseline_recipe_name != "<none>"
        else None
    )

    detect_threshold = (
        sc_mom_min if baseline_recipe is None
        else min(sc_mom_min, baseline_recipe.sc_mom_min)
    )
    detect_cooldown = (
        recipe.cooldown_days if baseline_recipe is None
        else min(recipe.cooldown_days, baseline_recipe.cooldown_days)
    )

    with st.spinner("Scanning..."):
        outcomes = scan_and_attach(
            scores_hash=scores_hash,
            panel_hash=panel_hash,
            threshold=detect_threshold,
            cooldown_days=detect_cooldown,
            date_start=pd.Timestamp(min_date),
            date_end=pd.Timestamp(max_date),
            tickers=None,
        )

    if outcomes.empty:
        st.warning(
            f"No cross-up signals at Momentum >= {detect_threshold:.0f} "
            f"with cooldown {detect_cooldown}d. Try lowering the threshold."
        )
        st.stop()

    filtered = apply_filter(outcomes, recipe)
    baseline_filtered = (
        apply_filter(outcomes, baseline_recipe)
        if baseline_recipe is not None
        else None
    )

    if filtered.empty:
        st.warning(
            f"{len(outcomes):,} cross-ups found but engine filters eliminated all of them. "
            "Try relaxing the sliders."
        )
        st.stop()


    # ---- Headline metrics ----

    st.header("Historical Scan Results")

    _recipe_parts = [f"SC>={sc_mom_min:.0f}"]
    if flow_min > 0:
        _recipe_parts.append(f"Flow>={flow_min:.0f}")
    if energy_min > 0:
        _recipe_parts.append(f"Energy>={energy_min:.0f}")
    if structure_min > 0:
        _recipe_parts.append(f"Struct>={structure_min:.0f}")
    if mp_min > 0:
        _recipe_parts.append(f"MP>={mp_min:.0f}")
    if elder_min > 0:
        _recipe_parts.append(f"Elder>={elder_min:.1f}")
    _recipe_label = " | ".join(_recipe_parts)

    st.markdown(f"**Recipe: {_recipe_label}**")

    cur_all = M.compute_all_windows(filtered)
    cur_21 = next((m for m in cur_all if m.window_days == 21), None)

    h1, h2, h3, h4 = st.columns(4)
    with h1:
        st.metric("Signal count", f"{cur_21.n:,}" if cur_21 else "---")
    with h2:
        if cur_21:
            st.metric("Avg R (21d)", f"{cur_21.expectancy_r:+.2f}")
        else:
            st.metric("Avg R (21d)", "---")
    with h3:
        if cur_21:
            st.metric("Win rate", fmt_pct(cur_21.win_rate_realized))
        else:
            st.metric("Win rate", "---")
    with h4:
        if cur_21:
            st.metric("Stop rate", fmt_pct(cur_21.hit_stop_rate))
        else:
            st.metric("Stop rate", "---")

    if cur_21 and cur_21.n < 50:
        st.warning(f"N = {cur_21.n} -- too few for stable conclusions. Loosen the recipe or expand the date range.")


    # ---- Side-by-side comparison ----

    if baseline_recipe is not None:
        with st.spinner("Computing baselines..."):
            random_outcomes, spy_returns = compute_baselines(
                scores_hash, panel_hash, spy_hash, filtered,
            )
        rand_all = M.compute_all_windows(random_outcomes) if not random_outcomes.empty else None
        base_all = (
            M.compute_all_windows(baseline_filtered)
            if baseline_filtered is not None and not baseline_filtered.empty
            else None
        )

        if base_all or rand_all:
            st.subheader("Side-by-side comparison")
            rows = []
            for m in cur_all:
                rows.append({
                    "cohort": recipe.name, "window": f"{m.window_days}d", "N": m.n,
                    "win_realised": fmt_pct(m.win_rate_realized),
                    "expectancy_R": f"{m.expectancy_r:+.2f}",
                    "hit_stop": fmt_pct(m.hit_stop_rate),
                })
            if base_all:
                for m in base_all:
                    rows.append({
                        "cohort": f"baseline: {baseline_recipe.name}",
                        "window": f"{m.window_days}d", "N": m.n,
                        "win_realised": fmt_pct(m.win_rate_realized),
                        "expectancy_R": f"{m.expectancy_r:+.2f}",
                        "hit_stop": fmt_pct(m.hit_stop_rate),
                    })
            if rand_all:
                for m in rand_all:
                    rows.append({
                        "cohort": "random entry (null)",
                        "window": f"{m.window_days}d", "N": m.n,
                        "win_realised": fmt_pct(m.win_rate_realized),
                        "expectancy_R": f"{m.expectancy_r:+.2f}",
                        "hit_stop": fmt_pct(m.hit_stop_rate),
                    })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


    # ---- DSL trailing stop outcomes ----

    st.subheader("DSL Trailing Stop Outcomes")
    st.caption("R-tiered trailing stop. T1=tight, T2=medium, T3=wide weekly, T4=widest.")

    with st.spinner("Computing DSL outcomes..."):
        dsl_outcomes = compute_dsl_outcomes(filtered, _load_panel(panel_hash), max_bars=63)

    if "dsl_r_realized" in dsl_outcomes.columns:
        dsl_valid = dsl_outcomes["dsl_r_realized"].dropna()
        if not dsl_valid.empty:
            dsl_cols = [c for c in [
                "date", "ticker", "sc_momentum", "entry_close",
                "dsl_initial_stop", "dsl_risk", "dsl_exit_bar", "dsl_exit_type",
                "dsl_peak_tier", "dsl_r_realized", "dsl_peak_r",
            ] if c in dsl_outcomes.columns]
            st.dataframe(dsl_outcomes[dsl_cols], use_container_width=True, hide_index=True)

            d1, d2, d3 = st.columns(3)
            with d1:
                st.metric("DSL avg R", f"{dsl_valid.mean():+.2f}")
            with d2:
                st.metric("DSL median R", f"{dsl_valid.median():+.2f}")
            with d3:
                peak_tiers = dsl_outcomes["dsl_peak_tier"].dropna()
                if not peak_tiers.empty:
                    st.metric("Avg peak tier", f"T{peak_tiers.mean():.1f}")
        else:
            st.info("No DSL outcomes computed -- insufficient forward data.")


    # ---- Signal table with drill-down ----

    st.subheader(f"Signal Table -- {len(filtered):,} crossup signals")
    st.caption(
        "Moments a stock crossed above the threshold. The dates show WHEN "
        "the entry signal fired, not what is happening today."
    )

    display_cols = [c for c in [
        "date", "ticker", "sc_momentum", "sc_position",
        "flow_100", "energy_100", "structure_100", "mp_100", "elder_score", "bq_100",
        "mp_state", "entry_close", "stop_price", "target_price",
        "fwd_ret_5d", "fwd_ret_10d", "fwd_ret_21d",
        "hit_target_21d", "hit_stop_21d", "gap_stop_21d",
        "r_realized_21d", "r_realized_optimistic_21d", "days_to_outcome_21d",
    ] if c in filtered.columns]
    st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

    # Drill-down
    st.subheader("Signal Drill-Down")
    if not filtered.empty:
        drill_df = filtered.sort_values("date", ascending=False).head(200).copy()
        drill_df["_label"] = (
            drill_df["date"].dt.strftime("%Y-%m-%d") + "  " + drill_df["ticker"].astype(str)
        )
        options = drill_df["_label"].tolist()
        choice = st.selectbox(
            "Pick a signal:", options, index=None, key="ml_drill_signal",
            placeholder="Click here and choose a signal...",
        )
        if choice is not None:
            idx = options.index(choice)
            sig = drill_df.iloc[idx]
            ticker = sig["ticker"]
            sig_date = pd.Timestamp(sig["date"])

            sc_p = sig.get("sc_position", float("nan"))
            sc_p_text = f" | SC_POS **{sc_p:.1f}**" if np.isfinite(sc_p) else ""
            sc_m_gated = sig.get("sc_momentum", float("nan"))
            sc_m_raw = sig.get("sc_momentum_raw", float("nan"))
            sc_m_text = f"SC_MOM **{sc_m_gated:.1f}**"
            if np.isfinite(sc_m_raw) and abs(sc_m_raw - sc_m_gated) > 0.1:
                sc_m_text += f" (raw {sc_m_raw:.1f})"
            st.markdown(
                f"**{ticker}** -- {sig_date.date()} -- "
                f"{sc_m_text}{sc_p_text}"
            )

            engines = [
                ("Flow", sig.get("flow_100", float("nan")), 100.0),
                ("Energy", sig.get("energy_100", float("nan")), 100.0),
                ("Structure", sig.get("structure_100", float("nan")), 100.0),
                ("Posture", sig.get("mp_100", float("nan")), 100.0),
                ("Elder", sig.get("elder_score", float("nan")) * 10.0, 100.0),
                ("BQ", sig.get("bq_100", float("nan")), 100.0),
            ]
            eng_cols = st.columns(len(engines))
            for col, (name, val, top) in zip(eng_cols, engines):
                with col:
                    ratio = float(val) / top if np.isfinite(val) and top > 0 else 0.0
                    st.progress(min(max(ratio, 0.0), 1.0), text=f"{name}  {val:.1f}")

            # Mini chart
            bars = panel.loc[panel["ticker"] == ticker].sort_values("date")
            sc = _load_scores(scores_hash)
            sc = sc.loc[sc["ticker"] == ticker].sort_values("date")
            cutoff_end = sig_date + pd.Timedelta(days=25)
            cutoff_start = sig_date - pd.Timedelta(days=90)
            bars = bars.loc[(bars["date"] >= cutoff_start) & (bars["date"] <= cutoff_end)]
            sc = sc.loc[(sc["date"] >= cutoff_start) & (sc["date"] <= cutoff_end)]

            if not bars.empty and not sc.empty:
                fig, (ax_price, ax_score) = plt.subplots(
                    2, 1, figsize=(9, 4.5), sharex=True,
                    gridspec_kw={"height_ratios": [2, 1]},
                )
                ax_price.plot(bars["date"], bars["close"], color="black", linewidth=1)
                ax_price.axvline(sig_date, color="green", linestyle="--", linewidth=1, label="signal")
                stop_price = sig.get("stop_price", float("nan"))
                target_price = sig.get("target_price", float("nan"))
                if np.isfinite(stop_price):
                    ax_price.axhline(
                        stop_price, color="red", linestyle=":", linewidth=0.8,
                        label=f"stop {stop_price:.2f}",
                    )
                if np.isfinite(target_price):
                    ax_price.axhline(
                        target_price, color="green", linestyle=":", linewidth=0.8,
                        label=f"target {target_price:.2f}",
                    )
                ax_price.set_ylabel("Close")
                ax_price.legend(loc="best", fontsize=7)
                ax_price.grid(alpha=0.2)

                ax_score.plot(
                    sc["date"], sc["sc_momentum"], color="steelblue",
                    linewidth=1, label="Momentum composite",
                )
                ax_score.axhline(75, color="orange", linestyle=":", linewidth=0.7)
                ax_score.axvline(sig_date, color="green", linestyle="--", linewidth=1)
                ax_score.set_ylabel("Momentum")
                ax_score.set_ylim(0, 100)
                ax_score.grid(alpha=0.2)
                st.pyplot(fig, clear_figure=True)
            else:
                st.info("Not enough surrounding price/score data to plot.")


    # ---- R-distribution chart ----

    st.subheader("Realised-R Distribution (21-day, stop-aware)")
    fig_r, ax_r = plt.subplots(figsize=(8, 3))
    r_vals = filtered["r_realized_21d"].dropna().to_numpy() if "r_realized_21d" in filtered.columns else np.array([])
    if r_vals.size > 0:
        ax_r.hist(r_vals, bins=30, color="steelblue", edgecolor="white")
        ax_r.axvline(0, color="black", linewidth=0.7)
        ax_r.axvline(-1.0, color="red", linewidth=0.8, linestyle=":", label="-1R (stop)")
        ax_r.axvline(2.0, color="green", linewidth=0.8, linestyle=":", label="+2R (target)")
        ax_r.axvline(r_vals.mean(), color="red", linestyle="--", linewidth=1, label=f"mean = {r_vals.mean():+.2f}R")
        ax_r.set_xlabel("Realised R-multiple at 21 days")
        ax_r.set_ylabel("Signal count")
        ax_r.legend(loc="upper right", fontsize=8)
    st.pyplot(fig_r, clear_figure=True)


    # ---- Export ----

    csv_buf = io.StringIO()
    filtered.to_csv(csv_buf, index=False)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    st.download_button(
        label="Export signal table CSV",
        data=csv_buf.getvalue(),
        file_name=f"mathlab_signals_{timestamp}.csv",
        mime="text/csv",
        key="ml_export_csv",
    )
