"""Alfred orchestrator -- pure Python gate, PTRS, regime, universe-cap logic.

Per Charter v1.8.2:
  §3B: Alfred orchestrates, enforces, executes, flags gaps. Alfred does NOT
       analyse, opine, or vote.
  §6:  PTRS = SC_MOMENTUM + (SH + RA + RL). >=65 -> qualified, <65 -> rejected.
  §8:  Regime tiers GREEN/YELLOW/ORANGE/RED from VIX.
  §9B: 8-gate sequence on every candidate before deliberation runs.

Zero LLM calls in this module. All computations are deterministic Python so
they can be unit-tested without API credentials. The LLM-driven Alfred
narration lives in `committee.deliberation_cell` (the cell runner uses Alfred
purely for orchestration text, not analysis).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Regime (Charter §8)
# ---------------------------------------------------------------------------

RegimeLevel = Literal["GREEN", "YELLOW", "ORANGE", "RED"]
GREEN, YELLOW, ORANGE, RED = "GREEN", "YELLOW", "ORANGE", "RED"

# RL component (Regime Level) from Charter §6.
RL_FROM_LEVEL: dict[RegimeLevel, int] = {
    "GREEN": 2,
    "YELLOW": -3,
    "ORANGE": -5,
    "RED": 0,           # RED short-circuits PTRS entirely (HARD STOP).
}


def classify_regime(vix: float) -> RegimeLevel:
    if vix > 30:
        return "RED"
    if vix > 25:
        return "ORANGE"
    if vix >= 18:
        return "YELLOW"
    return "GREEN"


# ---------------------------------------------------------------------------
# Sector Health (Charter §6)
# ---------------------------------------------------------------------------

def compute_sh(sma_distance_pct: float, sector_grade: str | None = None) -> int:
    """SH component from price-vs-SMA20 distance (in %).

    Charter §6:
      >2% above SMA20    -> +3
      at/near SMA20      ->  0   (treat -2% .. +2% as 'near')
      below SMA20        -> -5
      >5% below SMA20    -> -8

    `sector_grade` is accepted for parity with the spec's mention but does not
    change SH directly -- that lookup belongs to DSG-11 sector-gate logic.
    Argument retained so callers don't have to know the internals.
    """
    _ = sector_grade
    if sma_distance_pct > 2:
        return 3
    if sma_distance_pct < -5:
        return -8
    if sma_distance_pct < -2:
        return -5
    return 0


# ---------------------------------------------------------------------------
# Regime Alignment (Charter §6, owned by Dalio voice)
# ---------------------------------------------------------------------------

RAStatus = Literal["ALIGNED", "NEUTRAL", "MISALIGNED"]

RA_FROM_STATUS: dict[RAStatus, int] = {
    "ALIGNED":   5,
    "NEUTRAL":   0,
    "MISALIGNED": -10,
}


# ---------------------------------------------------------------------------
# PTRS — the quality gate
# ---------------------------------------------------------------------------

@dataclass
class PTRSResult:
    sc_momentum: float
    sh: int
    ra: int
    rl: int
    cm: int                  # SH + RA + RL
    ptrs: float
    qualified: bool          # PTRS >= 65 (quality gate)
    regime: RegimeLevel
    notes: list[str] = field(default_factory=list)


def compute_ptrs(
    sc_momentum: float,
    sma_distance_pct: float,
    ra_status: RAStatus,
    vix: float,
    sector_grade: str | None = None,
) -> PTRSResult:
    """Compute PTRS per Charter §6.

    Returns a PTRSResult with the qualification verdict. RED regime is a hard
    stop -- regardless of the arithmetic, the candidate cannot proceed.
    """
    regime = classify_regime(vix)
    notes: list[str] = []

    sh = compute_sh(sma_distance_pct, sector_grade)
    ra = RA_FROM_STATUS[ra_status]
    rl = RL_FROM_LEVEL[regime]
    cm = sh + ra + rl
    ptrs = float(sc_momentum) + cm

    if regime == "RED":
        notes.append("Regime RED: hard stop. Charter §8 -- PTRS computed but no eval proceeds.")
        return PTRSResult(
            sc_momentum=sc_momentum, sh=sh, ra=ra, rl=rl, cm=cm,
            ptrs=ptrs, qualified=False, regime=regime, notes=notes,
        )

    qualified = ptrs >= 65
    if not qualified:
        notes.append(
            f"PTRS {ptrs:.1f} below gate (65). Gap = {65 - ptrs:+.1f}. "
            f"Components: SC_MOM {sc_momentum:.1f}, SH {sh:+d}, RA {ra:+d}, RL {rl:+d}."
        )
    return PTRSResult(
        sc_momentum=sc_momentum, sh=sh, ra=ra, rl=rl, cm=cm,
        ptrs=ptrs, qualified=qualified, regime=regime, notes=notes,
    )


# ---------------------------------------------------------------------------
# Sector gate with DSG-11 correlation override (Charter §4B.4)
# ---------------------------------------------------------------------------

SectorGateTreatment = Literal[
    "standard", "idiosyncratic_override",
    "mixed_gate_hold", "sector_dependent_no_override",
]


@dataclass
class SectorGateResult:
    passes: bool
    treatment: SectorGateTreatment
    note: str = ""


def sector_gate_check(
    sector_grade: str,
    sector_corr: float | None,
    ptrs: float,
) -> SectorGateResult:
    """Charter §4B.4 sector gate with DSG-11 correlation override.

    DEPLOY/HOLD always pass (standard).
    Otherwise the sector_corr classifies idiosyncrasy:
      corr < 0.3:  idiosyncratic -- gate -> SH penalty only, pass iff PTRS >=65.
      0.3 <= corr <= 0.7: mixed -- binary gate holds (committee 4/8 override possible).
      corr > 0.7:  sector-dependent -- no override.
    """
    if sector_grade in ("DEPLOY", "HOLD"):
        return SectorGateResult(passes=True, treatment="standard")

    if sector_corr is None:
        return SectorGateResult(
            passes=False, treatment="mixed_gate_hold",
            note="sector_corr unavailable -- defaulting to gate-hold.",
        )

    if sector_corr < 0.3:
        return SectorGateResult(
            passes=(ptrs >= 65),
            treatment="idiosyncratic_override",
            note=f"sector_corr={sector_corr:.2f} -- DSG-11 override applied.",
        )
    if sector_corr <= 0.7:
        return SectorGateResult(
            passes=False, treatment="mixed_gate_hold",
            note=f"sector_corr={sector_corr:.2f} -- mixed; PM override = 4/8 committee + rationale.",
        )
    return SectorGateResult(
        passes=False, treatment="sector_dependent_no_override",
        note=f"sector_corr={sector_corr:.2f} -- sector-dependent; no override.",
    )


# ---------------------------------------------------------------------------
# Charter §9B gate sequence
# ---------------------------------------------------------------------------

@dataclass
class GateCheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class GateSequenceResult:
    candidate_ticker: str
    qualified: bool
    failed_gate: str | None
    gates: list[GateCheckResult]
    ptrs: PTRSResult | None = None


def run_gate_sequence(
    *,
    ticker: str,
    sc_momentum: float,
    elder_score: float,
    flow_100: float,
    energy_100: float,
    structure_100: float,
    mp_100: float,
    sector_grade: str,
    sector_corr: float | None,
    rr_to_committee_target: float,
    sma_distance_pct: float,
    ra_status: RAStatus,
    vix: float,
    pipeline_count: int,
    universe_cap: int = 10,
) -> GateSequenceResult:
    """Execute the 8 gates of Charter §9B in order. Stops at first failure.

    Pure deterministic logic -- no LLM, no I/O. Callers feed AQE data in;
    `GateSequenceResult` tells you which gate failed (if any) and the PTRS
    breakdown when the candidate reached gate 6.
    """
    gates: list[GateCheckResult] = []

    def add(name: str, passed: bool, detail: str = "") -> bool:
        gates.append(GateCheckResult(name=name, passed=passed, detail=detail))
        return passed

    if not add("1.sc_momentum>=55", sc_momentum >= 55,
               f"sc_momentum={sc_momentum:.1f}"):
        return GateSequenceResult(ticker, False, "1.sc_momentum>=55", gates)
    if not add("2.elder>=6.5", elder_score >= 6.5,
               f"elder={elder_score:.2f}"):
        return GateSequenceResult(ticker, False, "2.elder>=6.5", gates)
    floors_ok = (flow_100 >= 60 and energy_100 >= 60
                 and structure_100 >= 55 and mp_100 >= 55)
    if not add("3.engine_floors",
               floors_ok,
               f"flow={flow_100:.1f} energy={energy_100:.1f} "
               f"struct={structure_100:.1f} mp={mp_100:.1f}"):
        return GateSequenceResult(ticker, False, "3.engine_floors", gates)

    sg = sector_gate_check(sector_grade, sector_corr, ptrs=sc_momentum)
    if not add("4.sector>=HOLD", sg.passes,
               f"grade={sector_grade} ({sg.treatment}): {sg.note}"):
        return GateSequenceResult(ticker, False, "4.sector>=HOLD", gates)

    if not add("5.rr>=2:1", rr_to_committee_target >= 2.0,
               f"rr={rr_to_committee_target:.2f}"):
        return GateSequenceResult(ticker, False, "5.rr>=2:1", gates)

    ptrs = compute_ptrs(sc_momentum, sma_distance_pct, ra_status, vix, sector_grade)
    if not add("6.ptrs>=65", ptrs.qualified,
               f"ptrs={ptrs.ptrs:.1f} (sc_mom={sc_momentum:.1f} + "
               f"SH{ptrs.sh:+d} + RA{ptrs.ra:+d} + RL{ptrs.rl:+d})"):
        return GateSequenceResult(
            ticker, False, "6.ptrs>=65", gates, ptrs=ptrs,
        )

    if not add("7.universe_cap<=10",
               pipeline_count < universe_cap,
               f"pipeline={pipeline_count}/{universe_cap}"):
        return GateSequenceResult(ticker, False, "7.universe_cap<=10", gates, ptrs=ptrs)

    if not add("8.regime!=RED",
               ptrs.regime != "RED",
               f"regime={ptrs.regime} vix={vix:.2f}"):
        return GateSequenceResult(ticker, False, "8.regime!=RED", gates, ptrs=ptrs)

    return GateSequenceResult(ticker, True, None, gates, ptrs=ptrs)


# ---------------------------------------------------------------------------
# Universe cap helper (Alfred enforces hard)
# ---------------------------------------------------------------------------

@dataclass
class UniverseCapStatus:
    count: int
    cap: int
    at_cap: bool
    warning: bool                 # within 2 slots
    message: str


def check_universe_cap(pipeline_count: int, cap: int = 10) -> UniverseCapStatus:
    at_cap = pipeline_count >= cap
    warning = pipeline_count >= max(0, cap - 2)
    if at_cap:
        msg = (f"Universe cap reached ({pipeline_count}/{cap}). "
               "No new name advances to deliberation until a name is bracketed or killed.")
    elif warning:
        msg = f"Pipeline {pipeline_count}/{cap} -- approaching cap."
    else:
        msg = f"Pipeline {pipeline_count}/{cap}."
    return UniverseCapStatus(
        count=pipeline_count, cap=cap, at_cap=at_cap,
        warning=warning, message=msg,
    )


# ---------------------------------------------------------------------------
# Combined stop-out risk (Elder hard-block trigger, Charter §6A)
# ---------------------------------------------------------------------------

@dataclass
class StopOutAssessment:
    existing_risk_usd: float
    proposed_risk_usd: float
    combined_usd: float
    capital_usd: float
    combined_pct: float
    breaches_5pct: bool


def assess_combined_stopout(
    open_positions: list[dict],
    proposed_entry: float,
    proposed_stop: float,
    proposed_shares: int,
    dynamic_capital_usd: float,
) -> StopOutAssessment:
    """Sum (entry - stop) * shares across open + proposed; check vs 5% cap.

    `open_positions` items: {"entry": float, "stop": float, "shares": int}.
    Positions with missing entry/stop/shares (e.g. option rows in the PTJ) are
    skipped -- their dollar risk is tracked separately by the options book.
    """
    def _num(x) -> float:
        try:
            return float(x) if x is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    existing = sum(
        max(0.0, _num(p.get("entry")) - _num(p.get("stop")))
        * _num(p.get("shares"))
        for p in open_positions
    )
    proposed = max(0.0, _num(proposed_entry) - _num(proposed_stop)) * _num(proposed_shares)
    combined = existing + proposed
    pct = (combined / dynamic_capital_usd * 100.0) if dynamic_capital_usd > 0 else 0.0
    return StopOutAssessment(
        existing_risk_usd=round(existing, 2),
        proposed_risk_usd=round(proposed, 2),
        combined_usd=round(combined, 2),
        capital_usd=dynamic_capital_usd,
        combined_pct=round(pct, 2),
        breaches_5pct=combined > (dynamic_capital_usd * 0.05),
    )
