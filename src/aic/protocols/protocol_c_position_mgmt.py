"""Protocol C -- Position management (continuous + 03:55 SGT trail-tier sweep).

Reads each open position, computes DSG-10 trail tier from current R-multiple,
and proposes new stop levels per the DSG-10 ladder:

  Tier 0 (Entry -> +0.5R):  Fixed at structural SL
  Tier 1 (+0.5R -> +1R):    Raise stop to breakeven
  Tier 2 (+1R -> +2R):      Trail at -0.5R from highest close
  Tier 3 (+2R -> +3R):      Trail at -0.75R from highest close
  Tier 4 (+3R+):            Weekly mode -- prior week's low

This is informational -- it proposes the new stop. The PM enters the change
in IBKR; the AIC layer does not place orders. Stub for now: position close /
peak-close history needs the AQE panel; left as TODO for the deeper build.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class TrailRecommendation:
    ticker: str
    current_tier: Literal[0, 1, 2, 3, 4]
    current_stop: float
    proposed_stop: float
    r_multiple: float
    action: str                  # "RAISE_TO_BE", "TRAIL_-0.5R", etc.
    rationale: str


def compute_trail(
    entry: float,
    current_stop: float,
    risk: float,
    last_close: float,
    highest_close_since_entry: float,
    prior_week_low: float | None = None,
) -> TrailRecommendation:
    """Map a position's current R-multiple to a DSG-10 tier + proposed stop."""
    if risk <= 0:
        raise ValueError("risk must be > 0")
    r = (last_close - entry) / risk
    peak_r = (highest_close_since_entry - entry) / risk

    if peak_r >= 3.0 and prior_week_low is not None:
        tier = 4
        proposed = prior_week_low
        action = "TRAIL_PRIOR_WEEK_LOW"
        rationale = "DSG-10 tier 4 -- weekly mode trail."
    elif peak_r >= 2.0:
        tier = 3
        proposed = highest_close_since_entry - 0.75 * risk
        action = "TRAIL_-0.75R"
        rationale = "DSG-10 tier 3 -- trail at -0.75R from highest close."
    elif peak_r >= 1.0:
        tier = 2
        proposed = highest_close_since_entry - 0.5 * risk
        action = "TRAIL_-0.5R"
        rationale = "DSG-10 tier 2 -- trail at -0.5R from highest close."
    elif peak_r >= 0.5:
        tier = 1
        proposed = entry
        action = "RAISE_TO_BE"
        rationale = "DSG-10 tier 1 -- raise stop to breakeven."
    else:
        tier = 0
        proposed = current_stop
        action = "HOLD"
        rationale = "DSG-10 tier 0 -- structural stop held."

    # Stops only ratchet upward
    proposed = max(proposed, current_stop)

    return TrailRecommendation(
        ticker="?",
        current_tier=tier,
        current_stop=current_stop,
        proposed_stop=round(proposed, 2),
        r_multiple=round(r, 2),
        action=action,
        rationale=rationale,
    )


# TODO(deeper-build):
#   - Read open_positions.json + the AQE price panel.
#   - For each position, look up its peak close since entry from panel_daily.
#   - Look up prior-week low for tier-4 trailing.
#   - Persist trail recommendations to AIC state (new table) for the UI.
