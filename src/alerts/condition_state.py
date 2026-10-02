"""AQE handoff D123/R21 (2026-10-02) §6 — the condition state machine.

Per name, keyed `<run_date>:<ticker>` so a row PMA carries over several
sessions keeps its history (same "life of a trigger" idea pma_levels.py's
own fired-state already uses, just scoped to one run date here since a
fresh `conditions` block arrives each morning).

State shape per key: {"stage": "WATCHING"|"CONDITION_MET"|"FAILED_PUSH",
"emailed_today": [stage names already fired once today],
"chased": bool, "analyst_out": bool, "exit_line": bool}.

Email discipline (§6): "an email goes out only on a CHANGE of state, and
once per state per day." The primary lifecycle (WATCHING -> CONDITION_MET
-> FAILED_PUSH, and back again if conditions re-qualify) is one state
machine; CHASED/ANALYST_OUT/EXIT_LINE are independent one-shot flags that
fire their own email the first time they turn true each day, regardless
of the primary stage. `advance()` returns the list of states newly
entered THIS CALL — callers (engine.py) decide whether to actually email
them (gated by config.PMA_CONDITIONS_MODE) or just log them (shadow).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.data.paths import PROJECT_ROOT

CONDITION_STATE_PATH = PROJECT_ROOT / "aegis" / "output" / "alerts" / "pma_condition_state.json"

STAGE_WATCHING = "WATCHING"
STAGE_CONDITION_MET = "CONDITION_MET"
STAGE_FAILED_PUSH = "FAILED_PUSH"


def _key(run_date: str, ticker: str) -> str:
    return f"{run_date}:{ticker}"


def load_condition_state() -> dict:
    """Local file only — this is a NEW, shadow-mode-only artifact with no
    established Drive-sync precedent yet (handoff §7 scopes this build to
    internal logging ahead of the 15 Oct review); publishing it alongside
    the other alert state files is a fast-follow once the switch flips."""
    try:
        if CONDITION_STATE_PATH.exists():
            data = json.loads(CONDITION_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:  # noqa: BLE001
        pass
    return {}


def save_condition_state(state: dict) -> None:
    try:
        CONDITION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONDITION_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _entry(state: dict, run_date: str, ticker: str) -> dict:
    key = _key(run_date, ticker)
    return state.setdefault(key, {"stage": STAGE_WATCHING, "emailed_today": [],
                                  "chased": False, "analyst_out": False,
                                  "exit_line": False})


def advance(state: dict, run_date: str, ticker: str, eval_result: dict,
           is_held: bool = False) -> list[str]:
    """Apply one cycle's evaluate_conditions() result to this ticker's
    state, mutating `state` in place. Returns the list of state names
    newly fired THIS call (empty most cycles — nothing changed)."""
    e = _entry(state, run_date, ticker)
    fired: list[str] = []

    def _fire_once(name: str) -> None:
        if name not in e["emailed_today"]:
            e["emailed_today"].append(name)
            fired.append(name)

    buy_met = bool(eval_result.get("buy_met"))
    if e["stage"] in (STAGE_WATCHING, STAGE_FAILED_PUSH) and buy_met:
        e["stage"] = STAGE_CONDITION_MET
        _fire_once(STAGE_CONDITION_MET)
    elif e["stage"] == STAGE_CONDITION_MET and not buy_met:
        # §6: FAILED PUSH is CONDITION MET (or through the shared buy
        # level) followed by an hourly close back under it -- buy_met
        # turning false again after having been true IS that close-back-
        # under, since buy_met is itself hourly-close-based for its h1_
        # close_above/below words.
        e["stage"] = STAGE_FAILED_PUSH
        _fire_once(STAGE_FAILED_PUSH)

    if eval_result.get("chased") and not e["chased"]:
        e["chased"] = True
        _fire_once("CHASED")

    if eval_result.get("wrong_lit") and not e["analyst_out"]:
        e["analyst_out"] = True
        _fire_once("ANALYST_OUT")

    exit_fired = eval_result.get("exit_hit") or eval_result.get("exit_warn")
    if exit_fired and not e["exit_line"]:
        e["exit_line"] = True
        _fire_once("EXIT_LINE_HELD" if is_held else "EXIT_LINE_WARN")

    return fired
