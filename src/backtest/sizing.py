"""Position sizing — 3% risk per trade, scaled by disposition.

Rules:
    - Base risk: 3% of equity per FULL position
    - Disposition scales: FULL=1.0, HALF=0.5, QUARTER=0.25
    - Max positions: 6
    - Max sector exposure: 35%
"""

from __future__ import annotations

import numpy as np

RISK_PER_TRADE_PCT = 0.03
MAX_POSITIONS = 6
MAX_SECTOR_EXPOSURE = 0.35


def compute_position_size(
    equity: float,
    entry_price: float,
    risk_per_share: float,
    disposition: str,
) -> dict:
    """Compute shares and dollar risk for a trade.

    Returns: shares, dollar_risk, risk_pct.
    """
    disp_mult = {"FULL": 1.0, "HALF": 0.5, "QUARTER": 0.25}.get(disposition, 0.0)
    if disp_mult == 0.0 or risk_per_share <= 0 or entry_price <= 0:
        return {"shares": 0, "dollar_risk": 0.0, "risk_pct": 0.0}

    base_risk_budget = equity * RISK_PER_TRADE_PCT * disp_mult

    shares = int(base_risk_budget / risk_per_share)
    shares = max(shares, 0)
    dollar_risk = shares * risk_per_share
    risk_pct = dollar_risk / equity if equity > 0 else 0.0

    return {
        "shares": shares,
        "dollar_risk": dollar_risk,
        "risk_pct": risk_pct,
    }
