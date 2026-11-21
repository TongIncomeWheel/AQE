"""The score-version switch (PM 2026-11-21 "Yes to 2": cut the live scores over to the corrected calculations).

ONE switch decides which calculation the live score columns carry:
    v1  the old (pre-fix) calculation. Live columns hold the old values.
    v2  the corrected calculation (the shadow `_v2` columns shipped in #134-#141). Live columns hold the corrected values.
Either way every twin field also ships as `<field>_legacy` (the OLD value) so the change can be compared and rolled back, and every scores row carries
`score_version` so a reader can tell which scale it holds. Both calculations are always computed in the same pass; the switch only chooses which one the live
column name points at, which is why flipping it back is a rollback and not a rebuild of logic.

Where the switch lives (first hit wins): the env var AQE_SCORE_VERSION, then data/score_version.json (tracked in git, so a flip is a reviewed one-line PR), then
the default. An unknown value is a loud error, never a silent default. The default stays "v1" until the cutover PR flips it.
"""
from __future__ import annotations

import functools
import json
import os

import pandas as pd

from src.data.paths import PROJECT_ROOT

ENV_VAR = "AQE_SCORE_VERSION"
CONFIG_PATH = PROJECT_ROOT / "data" / "score_version.json"       # tracked in git, deliberately NOT under AQE_DATA_DIR (a scratch run must read the same switch)
VERSIONS = ("v1", "v2")
DEFAULT = "v1"
LEGACY = "_legacy"
VERSION_COLUMN = "score_version"


class ScoreVersionError(RuntimeError):
    """An unknown score version, or a scores cache that holds more than one: loud by design, never a silent default."""


def _config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    except Exception as exc:  # noqa: BLE001
        raise ScoreVersionError(f"{CONFIG_PATH.name} is unreadable ({exc}); refusing to guess the score version") from exc


def active() -> str:
    v = os.environ.get(ENV_VAR) or _config().get("version") or DEFAULT
    if v not in VERSIONS:
        raise ScoreVersionError(f"unknown score version {v!r} (from {ENV_VAR} or {CONFIG_PATH.name}); expected one of {VERSIONS}")
    return v


def cutover_date() -> str | None:
    return _config().get("cutover_date")


def source() -> str:
    """Where the active version came from (for the export and the log): env | config | default."""
    return "env" if os.environ.get(ENV_VAR) else ("config" if _config().get("version") else "default")


def apply(df: pd.DataFrame, pairs: list[tuple[str, str]]) -> pd.DataFrame:
    """For each (live, v2) twin: `<live>_legacy` takes the OLD value; under v2 the live column takes the corrected value. Returns df (modified in place).
    An engine frame with neither column (a too-short series) is skipped; exactly one of the two is an engine bug and raises."""
    if df is None or len(df.columns) == 0:
        return df
    v2 = active() == "v2"
    for live, new in pairs:
        has_live, has_new = live in df.columns, new in df.columns
        if not has_live and not has_new:
            continue
        if has_live != has_new:
            raise ScoreVersionError(f"engine frame has {'only ' + live if has_live else 'only ' + new}: a twin is missing its pair ({live} / {new})")
        df[live + LEGACY] = df[live]
        if v2:
            df[live] = df[new]
    return df


def twins(pairs: list[tuple[str, str]]):
    """Decorator for an engine's compute(): apply the version switch to its output frame."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*a, **k):
            return apply(fn(*a, **k), pairs)
        return wrapper
    return deco


def legacy_view(df: pd.DataFrame) -> pd.DataFrame:
    """A copy of a scores frame in which every live column that has a `<col>_legacy` twin holds the LEGACY value. QS's frozen recipe/calibration tables and Signal
    Radar's fitted kNN parameters were fitted on the old scale and must not silently read the new one until a PM-signed re-freeze."""
    out = df.copy()
    for c in [c for c in df.columns if c.endswith(LEGACY) and c[:-len(LEGACY)] in df.columns]:
        out[c[:-len(LEGACY)]] = df[c]
    return out


def versions_in(df: pd.DataFrame) -> set:
    if VERSION_COLUMN not in df.columns:
        return set()
    return set(df[VERSION_COLUMN].dropna().astype(str).unique())


def cache_problem(df: pd.DataFrame) -> str | None:
    """None when the scores cache holds exactly the active version; else the reason it must not be read as current. Missing column (a cache built before the
    switch existed) counts as unknown, not as v1: an unstamped cache is rebuilt rather than trusted."""
    have = versions_in(df)
    want = active()
    if not have:
        return f"scores cache carries no {VERSION_COLUMN} stamp (built before the switch); expected {want}"
    if len(have) > 1:
        return f"scores cache is MIXED ({sorted(have)}); expected {want} only"
    if have != {want}:
        return f"scores cache holds {sorted(have)[0]} but the active version is {want}"
    return None


# Score-version switch (PM 2026-11-21): every twin field also ships as `<field>_legacy` (the OLD calculation), next to the live column, and every row carries
# `score_version`. (scores column, engine frame, engine column): the legacy value is read from that engine frame's `<engine column>_legacy`.
LEGACY_FROM = [
    ("flow_100", "flow", "flow_100"), ("flow_score", "flow", "flow_score"), ("accum_score", "flow", "accum_score"),
    ("atr_score", "energy", "atr_score"), ("energy_100", "energy", "energy_100"),
    ("mp_100", "mp", "mp_score"), ("abs_mom_score", "mp", "abs_mom_score"), ("rel_mom_score", "mp", "rel_mom_score"),
    ("resist_score", "structure", "resist_score"), ("structure_100", "structure", "structure_100"), ("rs_spy_score", "structure", "rs_spy_score"),
    ("rs_accel_score", "structure", "rs_accel_score"), ("wk_score", "structure", "wk_score"), ("earn_score", "structure", "earn_score"),
    ("base_days", "structure", "base_days"), ("base_score", "structure", "base_score"),
    ("elder_score", "elder", "elder_score"),
    ("bq_100", "bq", "bq_100"), ("bq_base_dur", "bq", "bq_base_dur"), ("bq_base_days", "bq", "bq_base_days"),
    ("pr_ret_12m", "pr", "ret_12m_score"), ("pr_adx_score", "pr", "adx_score"), ("momentum_composite", "pr", "momentum_composite"),
    ("fip_quality", "pr", "fip_quality"), ("fip_raw", "pr", "fip_raw"), ("fip_spike_excluded", "pr", "fip_spike_excluded"),
    ("pipe_rank", "pr", "pipe_rank"), ("pipe_tier", "pr", "pipe_tier"),
    ("rd_score", "rd", "rd_score"), ("rd_rs_bonus", "rd", "rd_rs_bonus"),
    ("hl_score", "hl", "hl_score"), ("hl_rs", "hl", "hl_rs"), ("hl_trend", "hl", "hl_trend"),
]
# legacy fields computed in this module rather than read from one engine frame (the composites, the gates, the weekly K39 gate)
LEGACY_LOCAL = ["sc_momentum", "sc_momentum_raw", "sc_position", "sc_position_raw", "sc_m_gates", "sc_p_gates", "k39_value", "k39_gate"]
LEGACY_COLUMNS = [c + LEGACY for c in [a for a, _, _ in LEGACY_FROM] + LEGACY_LOCAL]
