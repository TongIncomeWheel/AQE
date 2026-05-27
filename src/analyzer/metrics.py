"""Outcome metrics shown in the analyzer UI.

Each metric is computed on a filtered signals frame produced by recipe.apply_filter.

We now distinguish two flavours of "win":

  - `win_rate_paper` uses fwd_ret > 0. A signal can be "paper-positive" even
    if the trader was stopped out at -1R on day 3 and the underlying rallied
    on day 14. This metric is the original SC_MOM ≥ 75 → "does it go up?"
    question. It tends to *overstate* edge for trail-stopped traders.

  - `win_rate_realized` uses r_realized > 0 — the R-multiple that a trader
    who actually used the 2×ATR stop would have booked. Stops lock in -1R
    and that is final; later recoveries do NOT count.

For a discretionary trader who actually uses stops, `win_rate_realized` and
`expectancy_r` are the headline numbers; `win_rate_paper` is a diagnostic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


WINDOWS = (5, 10, 21)


@dataclass
class WindowMetrics:
    window_days: int
    n: int
    win_rate_paper: float                  # fwd_ret > 0
    win_rate_realized: float               # r_realized > 0 (stop-aware)
    win_rate_paper_ci: tuple[float, float]
    win_rate_realized_ci: tuple[float, float]
    avg_fwd_ret: float
    median_fwd_ret: float
    hit_target_rate: float
    hit_stop_rate: float
    gap_stop_rate: float
    expectancy_r: float                     # conservative R (stop-priority on ties)
    expectancy_r_optimistic: float          # target-priority on ties
    expectancy_r_ci: tuple[float, float]    # bootstrap 95% on conservative R
    paper_but_stopped_rate: float           # fwd_ret > 0 AND hit_stop — the "mirage" rate

    def as_dict(self) -> dict[str, float | int]:
        return {
            "window_days": self.window_days,
            "n": self.n,
            "win_rate_paper": self.win_rate_paper,
            "win_rate_realized": self.win_rate_realized,
            "avg_fwd_ret": self.avg_fwd_ret,
            "median_fwd_ret": self.median_fwd_ret,
            "hit_target_rate": self.hit_target_rate,
            "hit_stop_rate": self.hit_stop_rate,
            "gap_stop_rate": self.gap_stop_rate,
            "expectancy_r": self.expectancy_r,
            "expectancy_r_optimistic": self.expectancy_r_optimistic,
            "paper_but_stopped_rate": self.paper_but_stopped_rate,
        }


# ---------- statistical helpers ----------


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson 95% confidence interval for a binomial proportion.

    Returns (lo, hi) in [0, 1]. Defined for n > 0.
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    halfw = (z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))) / denom
    return (max(0.0, centre - halfw), min(1.0, centre + halfw))


def bootstrap_mean_ci(values: np.ndarray, *, iterations: int = 1000, seed: int = 7) -> tuple[float, float]:
    """95% bootstrap CI for the mean of `values`."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return (float("nan"), float("nan"))
    if arr.size == 1:
        return (float(arr[0]), float(arr[0]))
    rng = np.random.default_rng(seed)
    samples = rng.choice(arr, size=(iterations, arr.size), replace=True)
    means = samples.mean(axis=1)
    return (float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975)))


# ---------- per-window metrics ----------


def compute_window_metrics(filtered: pd.DataFrame, window: int) -> WindowMetrics:
    n = len(filtered)
    nan_tuple = (float("nan"), float("nan"))
    if n == 0:
        return WindowMetrics(
            window_days=window, n=0,
            win_rate_paper=float("nan"), win_rate_realized=float("nan"),
            win_rate_paper_ci=nan_tuple, win_rate_realized_ci=nan_tuple,
            avg_fwd_ret=float("nan"), median_fwd_ret=float("nan"),
            hit_target_rate=float("nan"), hit_stop_rate=float("nan"),
            gap_stop_rate=float("nan"),
            expectancy_r=float("nan"), expectancy_r_optimistic=float("nan"),
            expectancy_r_ci=nan_tuple, paper_but_stopped_rate=float("nan"),
        )

    fwd = filtered[f"fwd_ret_{window}d"]
    r = filtered[f"r_realized_{window}d"]
    r_opt = filtered.get(f"r_realized_optimistic_{window}d", r)
    hit_target = filtered[f"hit_target_{window}d"]
    hit_stop = filtered[f"hit_stop_{window}d"]
    gap_stop = filtered.get(f"gap_stop_{window}d", pd.Series(False, index=filtered.index))

    paper_wins = int(((fwd > 0) & fwd.notna()).sum())
    real_wins = int(((r > 0) & r.notna()).sum())
    n_paper = int(fwd.notna().sum())
    n_real = int(r.notna().sum())

    paper_but_stopped = int(((fwd > 0) & hit_stop.fillna(False)).sum())

    return WindowMetrics(
        window_days=window,
        n=n,
        win_rate_paper=paper_wins / n_paper if n_paper else float("nan"),
        win_rate_realized=real_wins / n_real if n_real else float("nan"),
        win_rate_paper_ci=wilson_ci(paper_wins, n_paper),
        win_rate_realized_ci=wilson_ci(real_wins, n_real),
        avg_fwd_ret=float(fwd.mean()),
        median_fwd_ret=float(fwd.median()),
        hit_target_rate=float(hit_target.mean()) if hit_target.notna().any() else float("nan"),
        hit_stop_rate=float(hit_stop.mean()) if hit_stop.notna().any() else float("nan"),
        gap_stop_rate=float(gap_stop.mean()) if gap_stop.notna().any() else float("nan"),
        expectancy_r=float(r.mean()) if r.notna().any() else float("nan"),
        expectancy_r_optimistic=float(r_opt.mean()) if r_opt.notna().any() else float("nan"),
        expectancy_r_ci=bootstrap_mean_ci(r.to_numpy()),
        paper_but_stopped_rate=paper_but_stopped / n_paper if n_paper else float("nan"),
    )


def compute_all_windows(filtered: pd.DataFrame, windows: tuple[int, ...] = WINDOWS) -> list[WindowMetrics]:
    return [compute_window_metrics(filtered, w) for w in windows]


# ---------- comparison helpers ----------


def edge_vs(treatment: WindowMetrics, control: WindowMetrics) -> dict[str, float]:
    """Return Δ-vs-baseline for the headline metrics. NaN-safe."""
    def _sub(a: float, b: float) -> float:
        if not (math.isfinite(a) and math.isfinite(b)):
            return float("nan")
        return a - b
    return {
        "n": int(treatment.n),
        "n_control": int(control.n),
        "win_rate_realized_edge": _sub(treatment.win_rate_realized, control.win_rate_realized),
        "expectancy_r_edge": _sub(treatment.expectancy_r, control.expectancy_r),
        "hit_stop_edge": _sub(treatment.hit_stop_rate, control.hit_stop_rate),
        "hit_target_edge": _sub(treatment.hit_target_rate, control.hit_target_rate),
    }


def spy_edge(filtered: pd.DataFrame, spy_returns: pd.DataFrame, window: int) -> dict[str, float]:
    """Headline edge vs SPY same-window. Returns mean signal fwd_ret minus mean SPY fwd_ret."""
    sig_col = f"fwd_ret_{window}d"
    spy_col = f"spy_fwd_ret_{window}d"
    if sig_col not in filtered.columns or spy_col not in spy_returns.columns:
        return {"n": int(len(filtered)), "fwd_ret_edge_vs_spy": float("nan")}
    sig_mean = float(filtered[sig_col].mean()) if filtered[sig_col].notna().any() else float("nan")
    spy_mean = float(spy_returns[spy_col].mean()) if spy_returns[spy_col].notna().any() else float("nan")
    edge = sig_mean - spy_mean if math.isfinite(sig_mean) and math.isfinite(spy_mean) else float("nan")
    return {"n": int(len(filtered)), "fwd_ret_edge_vs_spy": edge}
