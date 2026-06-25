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
    """Beta-adjusted book exposure + gap-scenario losses from held positions.

    Carries BOTH beta windows (no gate opinion): AQE provides β30d- and β60d-based
    exposure/loss; Alfred selects per the governing charter (v2.1 §6.4 gate = β60d;
    PHL Field Spec = β30d). Unsuffixed fields are the β30d basis (PHL schema names);
    `*_60d` parallels are the β60d basis.
    """
    positions: list[dict] = []
    total_exp = 0.0
    beta_adj30 = 0.0
    beta_adj60 = 0.0
    sector_exp: dict[str, float] = {}

    for p in (held_positions or []):
        tk = p.get("ticker")
        qty = _num(p.get("qty"))
        px = _price(p)
        if not tk or qty is None or px is None:
            continue
        exp = qty * px
        b30 = _num(p.get("beta_30d"))
        b60 = _num(p.get("beta_60d"))
        if b30 is None:
            b30 = 1.0                       # neutral when beta unknown
        if b60 is None:
            b60 = b30                        # fall back to the other window
        bexp30 = exp * b30
        bexp60 = exp * b60
        sec = p.get("gics_sector")
        total_exp += exp
        beta_adj30 += bexp30
        beta_adj60 += bexp60
        if sec:
            sector_exp[sec] = sector_exp.get(sec, 0.0) + exp
        positions.append({
            "ticker": tk,
            "qty": int(qty) if float(qty).is_integer() else qty,
            "entry_price": _num(p.get("entry")),
            "live_price": round(px, 2),     # = COB close (AQE is EOD)
            "exposure_usd": round(exp, 2),
            "beta_30d": round(b30, 4),
            "beta_60d": round(b60, 4),
            "beta_adj_exposure_usd": round(bexp30, 2),        # β30d basis
            "beta_adj_exposure_usd_60d": round(bexp60, 2),    # β60d basis
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
        # β30d basis (PHL Field Spec schema names)
        "beta_adj_exposure_usd": round(beta_adj30, 2),
        "loss_per_1pct_gap_usd": round(beta_adj30 * 0.01, 2),
        "nav_weighted_beta_30d": round(beta_adj30 / total_exp, 4) if total_exp else 0.0,
        "gap_scenarios": {
            name: {"est_book_loss_usd": round(beta_adj30 * pct, 2)}
            for name, pct in GAP_PCTS},
        # β60d basis (Charter v2.1 §6.4 gate window) — parallel set
        "beta_adj_exposure_usd_60d": round(beta_adj60, 2),
        "loss_per_1pct_gap_usd_60d": round(beta_adj60 * 0.01, 2),
        "nav_weighted_beta_60d": round(beta_adj60 / total_exp, 4) if total_exp else 0.0,
        "gap_scenarios_60d": {
            name: {"est_book_loss_usd": round(beta_adj60 * pct, 2)}
            for name, pct in GAP_PCTS},
        "beta_basis": ("Both windows provided; AQE makes NO gate call. "
                       "Charter v2.1 §6.4 portfolio gate = β60d (use *_60d); "
                       "PHL Field Spec = β30d (unsuffixed)."),
        "sector_weights": sector_weights,
        "positions": positions,
    }
