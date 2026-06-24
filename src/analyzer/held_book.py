"""Portfolio Hedge Layer — `held_book` (Charter §4C, Field Spec v1.0, 24 Jun 2026).

Pure arithmetic on AQE's held positions (PTJ-sourced). AQE is an EOD engine, so
prices are **COB closes from FMP** (`cob_price`), not live IBKR quotes. Produces
the beta-adjusted book exposure + gap-scenario loss estimates Alfred reads to
build the §4C card. Facts only — no opinion. Alfred reads verbatim, never recomputes.
"""

from __future__ import annotations

from src.engines.srm import GICS_ETFS

GAP_PCTS = (("gap_3pct", 0.03), ("gap_5pct", 0.05),
            ("gap_7pct", 0.07), ("gap_10pct", 0.10))


def _num(v):
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def _price(p: dict):
    """COB close (FMP) preferred; fall back to PTJ live / entry."""
    return _num(p.get("cob_price")) or _num(p.get("live_px")) or _num(p.get("entry"))


def build_held_book(held_positions, as_of=None) -> dict:
    """Beta-adjusted book exposure + gap-scenario losses from held positions."""
    positions: list[dict] = []
    total_exp = 0.0
    beta_adj = 0.0
    sector_exp: dict[str, float] = {}

    for p in (held_positions or []):
        tk = p.get("ticker")
        qty = _num(p.get("qty"))
        px = _price(p)
        if not tk or qty is None or px is None:
            continue
        exp = qty * px
        beta = _num(p.get("beta_30d"))
        if beta is None:
            beta = 1.0                      # neutral when beta unknown
        bexp = exp * beta
        sec = p.get("gics_sector")
        total_exp += exp
        beta_adj += bexp
        if sec:
            sector_exp[sec] = sector_exp.get(sec, 0.0) + exp
        positions.append({
            "ticker": tk,
            "qty": int(qty) if float(qty).is_integer() else qty,
            "entry_price": _num(p.get("entry")),
            "live_price": round(px, 2),     # = COB close (AQE is EOD)
            "exposure_usd": round(exp, 2),
            "beta_30d": round(beta, 4),
            "beta_adj_exposure_usd": round(bexp, 2),
            "gics_sector": sec,
            "sector_weight_pct": 0.0,       # filled once total known
        })

    for pos in positions:
        pos["sector_weight_pct"] = (
            round(pos["exposure_usd"] / total_exp * 100, 2) if total_exp else 0.0)

    sector_weights = {etf: 0.0 for etf in GICS_ETFS}
    for sec, exp in sector_exp.items():
        sector_weights[sec] = round(exp / total_exp * 100, 2) if total_exp else 0.0

    return {
        "as_of": as_of,
        "position_count": len(positions),
        "total_exposure_usd": round(total_exp, 2),
        "beta_adj_exposure_usd": round(beta_adj, 2),
        "loss_per_1pct_gap_usd": round(beta_adj * 0.01, 2),
        "nav_weighted_beta_30d": round(beta_adj / total_exp, 4) if total_exp else 0.0,
        "sector_weights": sector_weights,
        "gap_scenarios": {
            name: {"est_book_loss_usd": round(beta_adj * pct, 2)}
            for name, pct in GAP_PCTS
        },
        "positions": positions,
    }
