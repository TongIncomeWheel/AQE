"""AQE export reader -- the *read* interface from AQE into the committee layer.

Per AEGIS_POC_BUILD_SPEC_v2.md "BUILD CONSTRAINT -- AQE PRESERVATION":
the AQE daily export JSON is the read interface between AQE and the new
committee layer. AQE writes it. Alfred (and this module) reads it.
ZERO modification to AQE's write side.

The current export shape (see src/data/drive_sync.py) does not exactly match
the spec's Appendix B; this reader adapts. If/when AQE's export schema is
later aligned to Appendix B, only this file needs updating -- callers see a
single stable interface (`load_export`, `iter_candidates`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EXPORT_PATH = PROJECT_ROOT / "output" / "aqe_daily_export.json"


@dataclass
class CandidateBrief:
    """One row passed from AQE to the committee layer.

    Field names follow what the committee needs, not the AQE export's internal
    column names. The reader handles the translation.
    """
    ticker: str
    source: str                     # "top_picks" | "longlist" | "watchlist" | "edge_list"
    sc_momentum: float
    sc_momentum_raw: float | None
    flow_100: float
    energy_100: float
    structure_100: float
    mp_100: float
    elder_score: float
    bq_100: float | None
    pipe_rank: float | None

    # Levels (existing AQE DSL + Fib + R-R bundle)
    entry: float | None
    stop: float | None
    tp_1r: float | None
    tp_2r: float | None
    tp_3r: float | None
    rr_pct: float | None
    rr_est: float | None             # estimated R/R to 1.618 Fib ext
    shares: int | None

    # Trend
    elder_5d: list | None

    # Risk
    beta_30d: float | None
    beta_60d: float | None

    # DSG-13 (populated by dsg13_extender after AQE export is written)
    sector_corr: float | None = None
    breakout_stop: float | None = None
    gics_sector: str | None = None
    sma_distance_pct: float | None = None
    held: bool | None = None

    # Sector context (already in AQE export)
    sector_grade: str | None = None
    fib: dict | None = None

    # Raw row for anything downstream might need
    raw: dict | None = None


def load_export(path: Path | str | None = None) -> dict:
    """Load the AQE daily export JSON. Raises FileNotFoundError if absent."""
    path = Path(path) if path else DEFAULT_EXPORT_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"AQE export not found at {path}. Run the daily pipeline first."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def iter_candidates(
    export: dict,
    source: str = "longlist",
) -> Iterator[CandidateBrief]:
    """Iterate candidate briefs from a section of the export.

    `source` -- one of "top_picks", "edge_list", "longlist", "watchlist".
    """
    rows = export.get(source, []) or []
    sector_grade_by_etf = {
        r.get("etf"): r.get("grade")
        for r in (export.get("srm") or [])
        if isinstance(r, dict)
    }
    for r in rows:
        gics = r.get("gics_sector")
        yield CandidateBrief(
            ticker=str(r.get("ticker", "?")),
            source=source,
            sc_momentum=float(r.get("sc_momentum", 0) or 0),
            sc_momentum_raw=_f(r.get("sc_momentum_raw")),
            flow_100=float(r.get("flow", r.get("flow_100", 0)) or 0),
            energy_100=float(r.get("energy", r.get("energy_100", 0)) or 0),
            structure_100=float(r.get("structure", r.get("structure_100", 0)) or 0),
            mp_100=float(r.get("mp", r.get("mp_100", 0)) or 0),
            elder_score=float(r.get("elder", r.get("elder_score", 0)) or 0),
            bq_100=_f(r.get("bq")),
            pipe_rank=_f(r.get("pipe_rank")),
            entry=_f(r.get("entry") or r.get("dsl_entry")),
            stop=_f(r.get("dsl_stop") or r.get("stop")),
            tp_1r=_f(r.get("dsl_tp_1r")),
            tp_2r=_f(r.get("dsl_tp_2r")),
            tp_3r=_f(r.get("dsl_tp_3r")),
            rr_pct=_f(r.get("dsl_rr_pct")),
            rr_est=_f(r.get("rr_est")),
            shares=_i(r.get("dsl_shares")),
            elder_5d=r.get("elder_5d"),
            beta_30d=_f(r.get("beta_30d")),
            beta_60d=_f(r.get("beta_60d")),
            sector_corr=_f(r.get("sector_corr")),
            breakout_stop=_f(r.get("breakout_stop")),
            gics_sector=gics,
            sma_distance_pct=_f(r.get("sma_distance_pct")),
            held=r.get("held"),
            sector_grade=sector_grade_by_etf.get(gics) if gics else None,
            fib=r.get("fib"),
            raw=r,
        )


def _f(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
