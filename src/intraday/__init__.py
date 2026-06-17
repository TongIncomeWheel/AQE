"""Intraday Momentum & Bracket (IMB) — a recommend-only execution-prep layer.

Consumes AQE's EOD export record + live intraday bars (from the financial MCP
`chart` tool, or an IBKR feed later) and produces a deterministic per-ticker
trade plan: an intraday momentum read, an operative stop anchored to real
intraday support (3-gate validated), a momentum-conditioned entry zone, a TP
ladder, size, and an IBKR-ready bracket spec.

This is a SEPARATE layer from the AQE scanner — it makes no change to the EOD
export and places no orders (v1). See `.claude/skills/intraday-plan`.
"""

from .momentum import intraday_momentum, normalize_bars
from .bracket import build_bracket, operative_stop, entry_zone, candidate_stops
from .plan import intraday_plan, rank_plans

__all__ = [
    "intraday_momentum", "normalize_bars",
    "build_bracket", "operative_stop", "entry_zone", "candidate_stops",
    "intraday_plan", "rank_plans",
]
