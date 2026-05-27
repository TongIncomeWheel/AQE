"""Protocol F -- Emergency handlers.

Three triggers (spec §15 + §11):

  - RED regime  (VIX > 30)           -> deliberation locked; PM alert.
  - Combined stop-out > 5% of capital -> Elder hard-block; PM alert.
  - FMP data unavailable             -> all prices stale; deliberation suspended.

Each handler returns an EmergencyAlert which the delivery layer pushes via
Telegram with HIGH priority + bypass quiet hours.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


EmergencyKind = Literal["RED_REGIME", "STOPOUT_BREACH", "FMP_OUTAGE", "API_OVERLOADED"]


@dataclass
class EmergencyAlert:
    kind: EmergencyKind
    timestamp_sgt: str
    severity: Literal["HIGH", "CRITICAL"]
    headline: str
    body: str
    actions_required: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def red_regime_alert(vix: float, positions: list[dict]) -> EmergencyAlert:
    return EmergencyAlert(
        kind="RED_REGIME",
        timestamp_sgt=datetime.now().isoformat(timespec="seconds"),
        severity="CRITICAL",
        headline=f"RED REGIME -- VIX {vix:.2f} > 30",
        body=(
            "Charter §8: RED regime -- HARD STOP. All new entries and add-ons "
            "suspended immediately. Deliberation locked. Pipeline frozen. "
            "Existing positions managed only -- review structural stops."
        ),
        actions_required=[
            "Acknowledge restrictions in dashboard before any action.",
            "Review each open position's structural stop for tightening.",
            "Do not add to any position until regime returns to ORANGE or lower.",
        ],
        metadata={"vix": vix, "open_position_count": len(positions)},
    )


def stopout_breach_alert(
    combined_usd: float,
    combined_pct: float,
    capital_usd: float,
) -> EmergencyAlert:
    return EmergencyAlert(
        kind="STOPOUT_BREACH",
        timestamp_sgt=datetime.now().isoformat(timespec="seconds"),
        severity="HIGH",
        headline=f"Stop-out breach: {combined_pct:.2f}% > 5%",
        body=(
            f"Combined stop-out risk USD {combined_usd:.0f} = {combined_pct:.2f}% "
            f"of dynamic capital USD {capital_usd:.0f}. Charter §6A: Elder "
            "hard-block triggered. No new bracket until existing positions are "
            "reduced or killed."
        ),
        actions_required=[
            "Review positions for sizing reduction or kill.",
            "Re-run Risk Cell at QUARTER size after reducing exposure.",
        ],
        metadata={
            "combined_usd": combined_usd,
            "combined_pct": combined_pct,
            "capital_usd": capital_usd,
        },
    )


def fmp_outage_alert(last_successful_iso: str, attempt: int) -> EmergencyAlert:
    return EmergencyAlert(
        kind="FMP_OUTAGE",
        timestamp_sgt=datetime.now().isoformat(timespec="seconds"),
        severity="HIGH",
        headline="FMP data unavailable",
        body=(
            f"FMP API not responding. Last successful pull: {last_successful_iso}. "
            "All prices flagged as STALE. Deliberation SUSPENDED -- cannot pull "
            "live candidate data. Portfolio prices showing stale values -- do not "
            "trade on these."
        ),
        actions_required=[
            "Wait for FMP recovery (retrying every 60s).",
            "Do not place new orders using stale prices.",
        ],
        metadata={"attempt": attempt, "last_successful": last_successful_iso},
    )


def api_overloaded_alert(ticker: str, retries_used: int) -> EmergencyAlert:
    return EmergencyAlert(
        kind="API_OVERLOADED",
        timestamp_sgt=datetime.now().isoformat(timespec="seconds"),
        severity="HIGH",
        headline=f"Anthropic API overloaded -- {ticker} parked",
        body=(
            f"Deliberation for {ticker} suspended after {retries_used} retries. "
            "{ticker} parked as WATCH. No votes recorded. Manual retry required."
        ).replace("{ticker}", ticker),
        actions_required=[
            f"Retry deliberation for {ticker} later.",
            "Or kill the candidate if no longer relevant.",
        ],
        metadata={"ticker": ticker, "retries_used": retries_used},
    )
