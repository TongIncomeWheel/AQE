"""Transaction cost model — Chan EC-2.

10bps slippage per side + $0.005/share commission (IBKR tiered).
Round-trip drag: ~0.10-0.30% of position value depending on price.
"""

from __future__ import annotations

SLIPPAGE_PCT = 0.0010
COMMISSION_PER_SHARE = 0.005


def entry_fill(price: float, shares: int) -> tuple[float, float]:
    """Return (fill_price, commission_cost). Buy side: price slips UP."""
    fill = price * (1 + SLIPPAGE_PCT)
    cost = shares * COMMISSION_PER_SHARE
    return fill, cost


def exit_fill(price: float, shares: int) -> tuple[float, float]:
    """Return (fill_price, commission_cost). Sell side: price slips DOWN."""
    fill = price * (1 - SLIPPAGE_PCT)
    cost = shares * COMMISSION_PER_SHARE
    return fill, cost


def round_trip_cost(entry_price: float, exit_price: float, shares: int) -> float:
    """Total transaction costs for a round-trip trade (entry + exit)."""
    _, entry_comm = entry_fill(entry_price, shares)
    _, exit_comm = exit_fill(exit_price, shares)
    slippage_entry = entry_price * SLIPPAGE_PCT * shares
    slippage_exit = exit_price * SLIPPAGE_PCT * shares
    return entry_comm + exit_comm + slippage_entry + slippage_exit
