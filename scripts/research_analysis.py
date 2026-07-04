"""AQE Research Panel — Exploratory Analysis

Reads research_panel.parquet and performs:
  1. Column inventory + basic stats
  2. Univariate correlation of each sub-component vs ret_t20 / tp1_hit
  3. Feature importance (Random Forest) for tp1_hit prediction
  4. K-Means clustering on sub-component score vectors
  5. Cluster-level forward-return distributions
  6. Comparison: current longlist filter vs clusters vs full universe

Usage:
    python -m scripts.research_analysis [path/to/research_panel.parquet]

Outputs HTML report + CSV summaries to output/research/
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "output" / "research"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Sub-component columns (the feature set for analysis) ────────────────
# These are the AQE engine outputs — the predictors we want to test.
SCORE_FEATURES = [
    # Aggregate engine scores
    "flow_100", "energy_100", "structure_100", "mp_100", "elder_score",
    "bq_100", "k39_value",
    # Composites
    "sc_momentum", "sc_momentum_raw", "sc_position", "sc_position_raw",
    "pipe_rank", "fip_quality",
    # Readiness + Health
    "rd_score", "rd_compression", "rd_trigger", "rd_pos_mod", "rd_rs_bonus",
    "hl_score", "hl_trend", "hl_flow", "hl_rs", "hl_risk",
    # Flow sub-components
    "flow_score", "accum_score", "volume_score", "skew_score", "ext_score",
    "mfi", "cmf", "ha_quality_count",
    # Energy sub-components
    "vp_position_score", "price_action_score", "squeeze_score",
    "exhaustion_score", "atr_score", "en_pos50", "en_trend_bars",
    # Structure sub-components
    "rs_spy_score", "rs_accel_score", "base_score", "ms_pos_score",
    "resist_score", "wk_score", "earn_score",
    "base_days", "ms_p50", "rs_vs_spy", "rs_accel",
    # MP sub-components
    "abs_mom_score", "mp_adx_score", "rel_mom_score", "trend_score",
    "roc_zscore", "excess_return", "adx_val",
    # BQ sub-components
    "bq_range_tight", "bq_vol_dry", "bq_base_dur", "bq_ema_conv",
    # Pipeline Rank sub-components
    "momentum_composite", "pr_ret_12m", "pr_adx_score", "pr_rsi_score",
    "pr_vol_score", "pr_ma_score",
    # Readiness diagnostics
    "rd_inside_bars", "rd_range_exp", "rd_vol_surge", "rd_close_str",
    # Health diagnostics
    "hl_higher_lows", "hl_trend_bars", "hl_vol_updn", "hl_atr_spike",
]

OUTCOME_COLS = ["ret_t5", "ret_t10", "ret_t20", "tp1_hit", "tp2_hit", "sl_hit"]
FLAG_COLS = ["is_longlist", "is_elder_list"]


def load_panel(path: str | Path) -> pd.DataFrame:
    """Load research panel, drop rows without forward outcomes."""
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    n_raw = len(df)
    df = df.dropna(subset=["ret_t20"])
    print(f"Loaded {n_raw:,} rows → {len(df):,} after dropping null ret_t20")
    print(f"  Tickers: {df['ticker'].nunique()}")
    print(f"  Date range: {df['date'].min().date()} → {df['date'].max().date()}")
    return df


def section_1_inventory(df: pd.DataFrame) -> pd.DataFrame:
    """Basic stats for every column."""
    print("\n" + "=" * 70)
    print("  SECTION 1: Column Inventory")
    print("=" * 70)

    present = [c for c in SCORE_FEATURES if c in df.columns]
    missing = [c for c in SCORE_FEATURES if c not in df.columns]
    if missing:
        print(f"  WARNING: {len(missing)} expected features missing: {missing[:10]}...")
    print(f"  Score features present: {len(present)} / {len(SCORE_FEATURES)}")

    stats = df[present].describe().T
    stats["non_null_pct"] = (df[present].notna().sum() / len(df) * 100).round(1)
    stats = stats[["count", "non_null_pct", "mean", "std", "min", "25%", "50%", "75%", "max"]]
    stats.to_csv(OUTPUT_DIR / "feature_stats.csv")
    print(f"  Saved feature_stats.csv")

    # Outcome summary
    print(f"\n  Outcome summary (all rows with ret_t20):")
    print(f"    N = {len(df):,}")
    for col in OUTCOME_COLS:
        if col in df.columns:
            if col.startswith("ret_"):
                print(f"    {col}: mean={df[col].mean():.3f}%, median={df[col].median():.3f}%")
            else:
                print(f"    {col}: hit_rate={df[col].mean()*100:.1f}%")

    # Baseline: longlist vs universe
    if "is_longlist" in df.columns:
        ll = df[df["is_longlist"] == True]
        print(f"\n  Baseline comparison:")
        print(f"    Full universe: N={len(df):,}, avg T20={df['ret_t20'].mean():.3f}%, "
              f"TP1={df['tp1_hit'].mean()*100:.1f}%")
        if len(ll) > 0:
            print(f"    Longlist only: N={len(ll):,}, avg T20={ll['ret_t20'].mean():.3f}%, "
                  f"TP1={ll['tp1_hit'].mean()*100:.1f}%")

    return stats


def section_2_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Univariate Spearman rank correlation of each feature vs outcomes."""
    print("\n" + "=" * 70)
    print("  SECTION 2: Univariate Correlations (Spearman)")
    print("=" * 70)

    from scipy.stats import spearmanr

    present = [c for c in SCORE_FEATURES if c in df.columns]
    results = []

    for feat in present:
        valid = df[[feat, "ret_t20", "tp1_hit"]].dropna()
        if len(valid) < 100:
            continue
        rho_t20, p_t20 = spearmanr(valid[feat], valid["ret_t20"])
        rho_tp1, p_tp1 = spearmanr(valid[feat], valid["tp1_hit"])

        # Quintile spread: top quintile avg - bottom quintile avg
        q5 = pd.qcut(valid[feat], 5, labels=False, duplicates="drop")
        if q5.nunique() >= 2:
            top_q = valid.loc[q5 == q5.max()]
            bot_q = valid.loc[q5 == q5.min()]
            spread_t20 = top_q["ret_t20"].mean() - bot_q["ret_t20"].mean()
            spread_tp1 = top_q["tp1_hit"].mean() - bot_q["tp1_hit"].mean()
        else:
            spread_t20 = spread_tp1 = np.nan

        results.append({
            "feature": feat,
            "rho_ret_t20": round(rho_t20, 4),
            "p_ret_t20": p_t20,
            "rho_tp1_hit": round(rho_tp1, 4),
            "p_tp1_hit": p_tp1,
            "q5_spread_t20_pct": round(spread_t20, 3),
            "q5_spread_tp1_pp": round(spread_tp1 * 100, 2),
            "n": len(valid),
        })

    corr_df = pd.DataFrame(results).sort_values("rho_tp1_hit", ascending=False)
    corr_df.to_csv(OUTPUT_DIR / "univariate_correlations.csv", index=False)
    print(f"  Saved univariate_correlations.csv ({len(corr_df)} features)")

    # Top 15 for TP1
    print(f"\n  Top 15 features by TP1 hit correlation:")
    print(f"  {'Feature':<25} {'rho_TP1':>8} {'Q5 spread':>10} {'rho_T20':>8} {'Q5 T20':>8}")
    print(f"  {'-'*25} {'-'*8} {'-'*10} {'-'*8} {'-'*8}")
    for _, r in corr_df.head(15).iterrows():
        print(f"  {r['feature']:<25} {r['rho_tp1_hit']:>+8.4f} {r['q5_spread_tp1_pp']:>+9.1f}pp "
              f"{r['rho_ret_t20']:>+8.4f} {r['q5_spread_t20_pct']:>+7.2f}%")

    # Bottom 15 (most negative — possible short signals or penalties)
    print(f"\n  Bottom 15 features (most negative TP1 correlation):")
    for _, r in corr_df.tail(15).iterrows():
        print(f"  {r['feature']:<25} {r['rho_tp1_hit']:>+8.4f} {r['q5_spread_tp1_pp']:>+9.1f}pp "
              f"{r['rho_ret_t20']:>+8.4f} {r['q5_spread_t20_pct']:>+7.2f}%")

    return corr_df


def section_3_feature_importance(df: pd.DataFrame) -> pd.DataFrame:
    """Random Forest feature importance for tp1_hit prediction."""
    print("\n" + "=" * 70)
    print("  SECTION 3: Feature Importance (Random Forest)")
    print("=" * 70)

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score

    present = [c for c in SCORE_FEATURES if c in df.columns]
    work = df[present + ["tp1_hit", "ret_t20"]].dropna()
    X = work[present].values
    y_tp1 = work["tp1_hit"].astype(int).values

    print(f"  Training set: {len(work):,} rows, {len(present)} features")
    print(f"  TP1 hit rate: {y_tp1.mean()*100:.1f}%")

    # RF for TP1 classification
    rf_tp1 = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=50,
        random_state=42, n_jobs=-1
    )
    cv_scores = cross_val_score(rf_tp1, X, y_tp1, cv=5, scoring="roc_auc")
    print(f"  5-fold CV AUC (TP1): {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

    rf_tp1.fit(X, y_tp1)
    imp_tp1 = pd.Series(rf_tp1.feature_importances_, index=present).sort_values(ascending=False)

    # Also fit for ret_t20 regression
    from sklearn.ensemble import RandomForestRegressor
    rf_ret = RandomForestRegressor(
        n_estimators=200, max_depth=8, min_samples_leaf=50,
        random_state=42, n_jobs=-1
    )
    y_ret = work["ret_t20"].values
    rf_ret.fit(X, y_ret)
    imp_ret = pd.Series(rf_ret.feature_importances_, index=present).sort_values(ascending=False)

    importance_df = pd.DataFrame({
        "feature": present,
        "rf_imp_tp1": [imp_tp1[f] for f in present],
        "rf_imp_ret_t20": [imp_ret[f] for f in present],
    }).sort_values("rf_imp_tp1", ascending=False)
    importance_df.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False)
    print(f"  Saved feature_importance.csv")

    print(f"\n  Top 20 features by RF importance (TP1):")
    print(f"  {'Feature':<25} {'Imp(TP1)':>10} {'Imp(T20)':>10}")
    print(f"  {'-'*25} {'-'*10} {'-'*10}")
    for _, r in importance_df.head(20).iterrows():
        print(f"  {r['feature']:<25} {r['rf_imp_tp1']:>10.4f} {r['rf_imp_ret_t20']:>10.4f}")

    return importance_df


def section_4_clustering(df: pd.DataFrame, n_clusters: int = 8) -> pd.DataFrame:
    """K-Means clustering on sub-component score vectors."""
    print("\n" + "=" * 70)
    print(f"  SECTION 4: K-Means Clustering (k={n_clusters})")
    print("=" * 70)

    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    present = [c for c in SCORE_FEATURES if c in df.columns]
    work = df[["date", "ticker"] + present + OUTCOME_COLS].dropna(subset=present + ["ret_t20"])
    print(f"  Working set: {len(work):,} rows, {len(present)} features")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(work[present].values)

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    work = work.copy()
    work["cluster"] = km.fit_predict(X_scaled)

    # Cluster profiles
    print(f"\n  Cluster forward-return profiles:")
    print(f"  {'Cluster':>8} {'N':>8} {'%':>6} {'avg_T5':>8} {'avg_T10':>9} {'avg_T20':>9} "
          f"{'TP1%':>6} {'TP2%':>6} {'SL%':>6} {'%pos_T20':>9}")
    print(f"  {'-'*8} {'-'*8} {'-'*6} {'-'*8} {'-'*9} {'-'*9} {'-'*6} {'-'*6} {'-'*6} {'-'*9}")

    cluster_stats = []
    for c in sorted(work["cluster"].unique()):
        cl = work[work["cluster"] == c]
        stat = {
            "cluster": c,
            "n": len(cl),
            "pct": len(cl) / len(work) * 100,
            "avg_ret_t5": cl["ret_t5"].mean(),
            "avg_ret_t10": cl["ret_t10"].mean(),
            "avg_ret_t20": cl["ret_t20"].mean(),
            "tp1_hit_rate": cl["tp1_hit"].mean() * 100,
            "tp2_hit_rate": cl["tp2_hit"].mean() * 100,
            "sl_hit_rate": cl["sl_hit"].mean() * 100,
            "pct_positive_t20": (cl["ret_t20"] > 0).mean() * 100,
        }
        cluster_stats.append(stat)
        print(f"  {stat['cluster']:>8} {stat['n']:>8,} {stat['pct']:>5.1f}% "
              f"{stat['avg_ret_t5']:>+7.2f}% {stat['avg_ret_t10']:>+8.2f}% "
              f"{stat['avg_ret_t20']:>+8.2f}% {stat['tp1_hit_rate']:>5.1f}% "
              f"{stat['tp2_hit_rate']:>5.1f}% {stat['sl_hit_rate']:>5.1f}% "
              f"{stat['pct_positive_t20']:>8.1f}%")

    cs_df = pd.DataFrame(cluster_stats)
    cs_df.to_csv(OUTPUT_DIR / "cluster_profiles.csv", index=False)

    # Cluster centroids — which features define each cluster
    centroids = pd.DataFrame(km.cluster_centers_, columns=present)
    centroids.index.name = "cluster"
    centroids.to_csv(OUTPUT_DIR / "cluster_centroids_scaled.csv")

    # Top distinguishing features per cluster (highest centroid values)
    print(f"\n  Top 5 distinguishing features per cluster (scaled centroid):")
    for c in range(n_clusters):
        top5 = centroids.iloc[c].sort_values(ascending=False).head(5)
        feats = ", ".join(f"{f}={v:+.2f}" for f, v in top5.items())
        cl_stat = cs_df[cs_df["cluster"] == c].iloc[0]
        tag = ""
        if cl_stat["tp1_hit_rate"] > cs_df["tp1_hit_rate"].mean() + 3:
            tag = " *** HIGH TP1 ***"
        elif cl_stat["avg_ret_t20"] > cs_df["avg_ret_t20"].mean() * 1.5:
            tag = " ** HIGH RET **"
        print(f"  C{c}: {feats}{tag}")

    # Compare best cluster vs longlist
    best_cluster = cs_df.sort_values("tp1_hit_rate", ascending=False).iloc[0]["cluster"]
    best_cl = work[work["cluster"] == int(best_cluster)]
    if "is_longlist" in df.columns:
        ll = df[df["is_longlist"] == True].dropna(subset=["ret_t20"])
        print(f"\n  Best cluster (C{int(best_cluster)}) vs Longlist baseline:")
        print(f"    Best cluster: N={len(best_cl):,}, TP1={best_cl['tp1_hit'].mean()*100:.1f}%, "
              f"T20={best_cl['ret_t20'].mean():+.2f}%, SL={best_cl['sl_hit'].mean()*100:.1f}%")
        if len(ll) > 0:
            print(f"    Longlist:     N={len(ll):,}, TP1={ll['tp1_hit'].mean()*100:.1f}%, "
                  f"T20={ll['ret_t20'].mean():+.2f}%, SL={ll['sl_hit'].mean()*100:.1f}%")

    return work


def section_5_interaction_effects(df: pd.DataFrame, corr_df: pd.DataFrame) -> pd.DataFrame:
    """Test top feature combinations — 2-way and 3-way conditional slices."""
    print("\n" + "=" * 70)
    print("  SECTION 5: Interaction Effects — Conditional Slicing")
    print("=" * 70)

    # Get top features by absolute TP1 correlation
    top_feats = corr_df.head(20)["feature"].tolist()
    present_top = [f for f in top_feats if f in df.columns][:12]

    results = []
    baseline_tp1 = df["tp1_hit"].mean()
    baseline_t20 = df["ret_t20"].mean()

    # 2-way: for each pair of top features, split at median and compare quadrants
    print(f"\n  2-way interactions (top feature pairs, split at median):")
    print(f"  Baseline: TP1={baseline_tp1*100:.1f}%, T20={baseline_t20:.2f}%")
    print(f"\n  {'Feat_A':<20} {'Feat_B':<20} {'Hi-Hi N':>8} {'TP1%':>6} {'T20%':>7} {'Lift_TP1':>9}")
    print(f"  {'-'*20} {'-'*20} {'-'*8} {'-'*6} {'-'*7} {'-'*9}")

    for i, fa in enumerate(present_top):
        med_a = df[fa].median()
        for fb in present_top[i+1:]:
            med_b = df[fb].median()
            hi_hi = df[(df[fa] >= med_a) & (df[fb] >= med_b)]
            if len(hi_hi) < 500:
                continue
            tp1 = hi_hi["tp1_hit"].mean()
            t20 = hi_hi["ret_t20"].mean()
            lift = (tp1 - baseline_tp1) * 100
            results.append({
                "feat_a": fa, "feat_b": fb,
                "n": len(hi_hi), "tp1_hit_rate": tp1 * 100,
                "avg_ret_t20": t20, "lift_tp1_pp": lift,
            })

    res_df = pd.DataFrame(results).sort_values("lift_tp1_pp", ascending=False)
    if len(res_df) > 0:
        for _, r in res_df.head(20).iterrows():
            print(f"  {r['feat_a']:<20} {r['feat_b']:<20} {r['n']:>8,} "
                  f"{r['tp1_hit_rate']:>5.1f}% {r['avg_ret_t20']:>+6.2f}% "
                  f"{r['lift_tp1_pp']:>+8.1f}pp")
        res_df.to_csv(OUTPUT_DIR / "interaction_effects.csv", index=False)
        print(f"\n  Saved interaction_effects.csv ({len(res_df)} pairs)")

    # 3-way: top triple by TP1 lift
    print(f"\n  Top 3-way interactions (above-median on all 3):")
    triples = []
    for i, fa in enumerate(present_top[:8]):
        med_a = df[fa].median()
        for j, fb in enumerate(present_top[i+1:9], i+1):
            med_b = df[fb].median()
            for fc in present_top[j+1:10]:
                med_c = df[fc].median()
                hi3 = df[(df[fa] >= med_a) & (df[fb] >= med_b) & (df[fc] >= med_c)]
                if len(hi3) < 200:
                    continue
                tp1 = hi3["tp1_hit"].mean()
                t20 = hi3["ret_t20"].mean()
                triples.append({
                    "feats": f"{fa} + {fb} + {fc}",
                    "n": len(hi3), "tp1_pct": tp1 * 100,
                    "t20_pct": t20, "lift_tp1": (tp1 - baseline_tp1) * 100,
                })

    if triples:
        tri_df = pd.DataFrame(triples).sort_values("lift_tp1", ascending=False)
        print(f"  {'Features':<55} {'N':>6} {'TP1%':>6} {'T20%':>7} {'Lift':>7}")
        print(f"  {'-'*55} {'-'*6} {'-'*6} {'-'*7} {'-'*7}")
        for _, r in tri_df.head(15).iterrows():
            print(f"  {r['feats']:<55} {r['n']:>6,} {r['tp1_pct']:>5.1f}% "
                  f"{r['t20_pct']:>+6.2f}% {r['lift_tp1']:>+6.1f}pp")
        tri_df.to_csv(OUTPUT_DIR / "triple_interactions.csv", index=False)

    return res_df


def section_6_lasso_selection(df: pd.DataFrame) -> pd.DataFrame:
    """Lasso logistic regression for sparse feature selection."""
    print("\n" + "=" * 70)
    print("  SECTION 6: Lasso Logistic Regression (sparse selection)")
    print("=" * 70)

    from sklearn.linear_model import LogisticRegressionCV
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import cross_val_score

    present = [c for c in SCORE_FEATURES if c in df.columns]
    work = df[present + ["tp1_hit"]].dropna()
    X = StandardScaler().fit_transform(work[present].values)
    y = work["tp1_hit"].astype(int).values

    lasso = LogisticRegressionCV(
        Cs=20, penalty="l1", solver="saga", cv=5, scoring="roc_auc",
        random_state=42, max_iter=2000, n_jobs=-1,
    )
    lasso.fit(X, y)

    coefs = pd.Series(lasso.coef_[0], index=present).sort_values(ascending=False)
    nonzero = coefs[coefs.abs() > 1e-6]
    print(f"  Regularization: C={lasso.C_[0]:.4f}")
    print(f"  Non-zero coefficients: {len(nonzero)} / {len(present)}")

    cv = cross_val_score(lasso, X, y, cv=5, scoring="roc_auc")
    print(f"  5-fold AUC: {cv.mean():.4f} ± {cv.std():.4f}")

    print(f"\n  Selected features (non-zero Lasso coefficients):")
    print(f"  {'Feature':<25} {'Coef':>10} {'Direction':>10}")
    print(f"  {'-'*25} {'-'*10} {'-'*10}")
    for feat, coef in nonzero.items():
        direction = "POSITIVE" if coef > 0 else "NEGATIVE"
        print(f"  {feat:<25} {coef:>+10.4f} {direction:>10}")

    lasso_df = pd.DataFrame({
        "feature": present,
        "lasso_coef": [coefs[f] for f in present],
    }).sort_values("lasso_coef", ascending=False)
    lasso_df.to_csv(OUTPUT_DIR / "lasso_selection.csv", index=False)

    return lasso_df


def section_7_cross_method_agreement(
    corr_df: pd.DataFrame,
    importance_df: pd.DataFrame,
    lasso_df: pd.DataFrame,
) -> pd.DataFrame:
    """Cross-method agreement — which features survive multiple methods."""
    print("\n" + "=" * 70)
    print("  SECTION 7: Cross-Method Agreement")
    print("=" * 70)

    # Top 15 by each method
    top_corr = set(corr_df.head(15)["feature"])
    top_rf = set(importance_df.sort_values("rf_imp_tp1", ascending=False).head(15)["feature"])
    top_lasso = set(lasso_df[lasso_df["lasso_coef"].abs() > 1e-6].sort_values(
        "lasso_coef", ascending=False).head(15)["feature"])

    all_feats = top_corr | top_rf | top_lasso
    agreement = []
    for f in all_feats:
        methods = []
        if f in top_corr:
            methods.append("Spearman")
        if f in top_rf:
            methods.append("RF")
        if f in top_lasso:
            methods.append("Lasso")
        agreement.append({
            "feature": f,
            "methods": " + ".join(methods),
            "n_methods": len(methods),
        })

    agree_df = pd.DataFrame(agreement).sort_values("n_methods", ascending=False)
    agree_df.to_csv(OUTPUT_DIR / "cross_method_agreement.csv", index=False)

    print(f"\n  Features surviving 3/3 methods:")
    three = agree_df[agree_df["n_methods"] == 3]
    if len(three) > 0:
        for _, r in three.iterrows():
            print(f"    {r['feature']}")
    else:
        print(f"    (none)")

    print(f"\n  Features surviving 2/3 methods:")
    two = agree_df[agree_df["n_methods"] == 2]
    for _, r in two.iterrows():
        print(f"    {r['feature']} ({r['methods']})")

    return agree_df


def section_8_hierarchical_clustering(df: pd.DataFrame) -> None:
    """Hierarchical clustering to find natural feature groupings."""
    print("\n" + "=" * 70)
    print("  SECTION 8: Feature Correlation Heatmap (Hierarchical)")
    print("=" * 70)

    present = [c for c in SCORE_FEATURES if c in df.columns]
    corr_matrix = df[present].corr(method="spearman")

    # Find highly correlated pairs (redundant features)
    redundant = []
    for i, fa in enumerate(present):
        for fb in present[i+1:]:
            r = corr_matrix.loc[fa, fb]
            if abs(r) > 0.8:
                redundant.append({"feat_a": fa, "feat_b": fb, "corr": round(r, 3)})

    if redundant:
        red_df = pd.DataFrame(redundant).sort_values("corr", ascending=False)
        print(f"  Highly correlated pairs (|r| > 0.8) — potential redundancy:")
        for _, r in red_df.iterrows():
            print(f"    {r['feat_a']:<25} ↔ {r['feat_b']:<25} r={r['corr']:+.3f}")
        red_df.to_csv(OUTPUT_DIR / "redundant_features.csv", index=False)
    else:
        print(f"  No feature pairs with |r| > 0.8")

    corr_matrix.to_csv(OUTPUT_DIR / "feature_correlation_matrix.csv")
    print(f"  Saved feature_correlation_matrix.csv")


def main():
    if len(sys.argv) > 1:
        panel_path = Path(sys.argv[1])
    else:
        panel_path = Path("data/research_panel.parquet")
        if not panel_path.exists():
            print(f"ERROR: {panel_path} not found.")
            print(f"Usage: python -m scripts.research_analysis path/to/research_panel.parquet")
            sys.exit(1)

    print("=" * 70)
    print("  AQE Research Panel — Exploratory Analysis")
    print("=" * 70)

    df = load_panel(panel_path)

    stats = section_1_inventory(df)
    corr_df = section_2_correlations(df)
    importance_df = section_3_feature_importance(df)
    clustered = section_4_clustering(df)
    interactions = section_5_interaction_effects(df, corr_df)
    lasso_df = section_6_lasso_selection(df)
    agreement = section_7_cross_method_agreement(corr_df, importance_df, lasso_df)
    section_8_hierarchical_clustering(df)

    print("\n" + "=" * 70)
    print("  ANALYSIS COMPLETE")
    print("=" * 70)
    print(f"  All outputs saved to: {OUTPUT_DIR}")
    print(f"  Files:")
    for f in sorted(OUTPUT_DIR.glob("*.csv")):
        print(f"    {f.name}")
    print("=" * 70)


if __name__ == "__main__":
    main()
