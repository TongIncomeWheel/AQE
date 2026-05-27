"""Scoring v1.6.0 composites — SC_MOMENTUM + SC_POSITION.

SC_MOMENTUM (Momentum Pipeline, 1-3 week holding):
    Weights: Flow 30%, Energy 30%, Structure 20%, MP 20%.
    Gates: Elder ≥ 6.5, Flow ≥ 60, Energy ≥ 60, Structure ≥ 55, MP ≥ 55.
    If ANY gate fails → composite hard-capped at 49.0.

SC_POSITION (Base-Building Pipeline, 3-6 week holding):
    Weights: Flow 10%, Energy 30%, Structure 20%, MP 5%, BQ 35%.
    Gates: Flow ≥ 40, Energy ≥ 60, Structure ≥ 65, MP ≥ 40, BQ ≥ 60, K39 gate.
    NO Elder gate. If ANY gate fails → composite hard-capped at 49.0.

Per Design Committee Spec Appendix C — GATE MATRIX.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


GATE_CAP = 49.0

SC_M_WEIGHTS = {
    "flow": 0.30,
    "energy": 0.30,
    "structure": 0.20,
    "mp": 0.20,
}

SC_M_GATES = {
    "elder": 6.5,
    "flow": 60.0,
    "energy": 60.0,
    "structure": 55.0,
    "mp": 55.0,
}

SC_P_WEIGHTS = {
    "flow": 0.10,
    "energy": 0.30,
    "structure": 0.20,
    "mp": 0.05,
    "bq": 0.35,
}

SC_P_GATES = {
    "flow": 40.0,
    "energy": 60.0,
    "structure": 65.0,
    "mp": 40.0,
    "bq": 60.0,
}


def compute(
    flow_score: pd.Series,
    energy_score: pd.Series,
    structure_score: pd.Series,
    mp_score: pd.Series,
    elder_score: pd.Series | None = None,
) -> pd.Series:
    """Return the SC_MOMENTUM series, [0, 100], with gate enforcement.

    If elder_score is provided, full gate logic is applied: when ANY engine
    floor or the Elder gate fails, the composite is hard-capped at 49.0.
    If elder_score is None (backward compat), only engine-floor gates apply.
    """
    raw = _sc_momentum_raw(flow_score, energy_score, structure_score, mp_score)

    gates_pass = (
        (flow_score >= SC_M_GATES["flow"])
        & (energy_score >= SC_M_GATES["energy"])
        & (structure_score >= SC_M_GATES["structure"])
        & (mp_score >= SC_M_GATES["mp"])
    )
    if elder_score is not None:
        gates_pass = gates_pass & (elder_score >= SC_M_GATES["elder"])

    return raw.where(gates_pass, np.minimum(raw, GATE_CAP))


def _sc_momentum_raw(
    flow_score: pd.Series,
    energy_score: pd.Series,
    structure_score: pd.Series,
    mp_score: pd.Series,
) -> pd.Series:
    """Ungated SC_MOMENTUM — the plain weighted average (matches TradingView)."""
    return (
        flow_score * SC_M_WEIGHTS["flow"]
        + energy_score * SC_M_WEIGHTS["energy"]
        + structure_score * SC_M_WEIGHTS["structure"]
        + mp_score * SC_M_WEIGHTS["mp"]
    ).clip(lower=0.0, upper=100.0)


def _sc_position_raw(
    flow_score: pd.Series,
    energy_score: pd.Series,
    structure_score: pd.Series,
    mp_score: pd.Series,
    bq_score: pd.Series,
) -> pd.Series:
    """Ungated SC_POSITION — the plain weighted average (matches TradingView)."""
    return (
        flow_score * SC_P_WEIGHTS["flow"]
        + energy_score * SC_P_WEIGHTS["energy"]
        + structure_score * SC_P_WEIGHTS["structure"]
        + mp_score * SC_P_WEIGHTS["mp"]
        + bq_score * SC_P_WEIGHTS["bq"]
    ).clip(lower=0.0, upper=100.0)


def compute_raw(
    flow_score: pd.Series,
    energy_score: pd.Series,
    structure_score: pd.Series,
    mp_score: pd.Series,
) -> pd.Series:
    """Public access to the ungated SC_MOMENTUM weighted average."""
    return _sc_momentum_raw(flow_score, energy_score, structure_score, mp_score)


def compute_position_raw(
    flow_score: pd.Series,
    energy_score: pd.Series,
    structure_score: pd.Series,
    mp_score: pd.Series,
    bq_score: pd.Series,
) -> pd.Series:
    """Public access to the ungated SC_POSITION weighted average."""
    return _sc_position_raw(flow_score, energy_score, structure_score, mp_score, bq_score)


def compute_position(
    flow_score: pd.Series,
    energy_score: pd.Series,
    structure_score: pd.Series,
    mp_score: pd.Series,
    bq_score: pd.Series,
    k39_gate: pd.Series | None = None,
) -> pd.Series:
    """Return the SC_POSITION series, [0, 100], with gate enforcement.

    k39_gate is a boolean Series (True = gate passes). If None, K39 is ignored.
    """
    raw = _sc_position_raw(flow_score, energy_score, structure_score, mp_score, bq_score)

    gates_pass = (
        (flow_score >= SC_P_GATES["flow"])
        & (energy_score >= SC_P_GATES["energy"])
        & (structure_score >= SC_P_GATES["structure"])
        & (mp_score >= SC_P_GATES["mp"])
        & (bq_score >= SC_P_GATES["bq"])
    )
    if k39_gate is not None:
        gates_pass = gates_pass & k39_gate

    return raw.where(gates_pass, np.minimum(raw, GATE_CAP))


def is_qualified(
    sc_momentum: pd.Series,
    elder_score: pd.Series,
    *,
    momentum_min: float = 75.0,
    elder_gate: float = 6.5,
) -> pd.Series:
    """Pine-style "Qualified" gate: SC_MOM >= momentum_min AND Elder >= elder_gate."""
    return (sc_momentum >= momentum_min) & (elder_score >= elder_gate)
