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


STATE_FILENAME = "aqe_condition_state.json"
KEEP_DAYS = 5          # a key is "<run_date>:<ticker>"; older run dates are pruned
_FLAGS = ("chased", "analyst_out", "exit_line", "unr", "unr_trigger", "unr_failed")


def _drive_load() -> dict | None:
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            txt = gdrive_uploader.download_text(STATE_FILENAME)
            if txt:
                data = json.loads(txt)
                if isinstance(data, dict):
                    return data
    except Exception:  # noqa: BLE001
        pass
    return None


def _local_load() -> dict:
    try:
        if CONDITION_STATE_PATH.exists():
            data = json.loads(CONDITION_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:  # noqa: BLE001
        pass
    return {}


def merge_states(a: dict, b: dict) -> dict:
    """Per-name union of two pollers' states, so neither forgets what the
    other already emailed: `emailed_today` is a union, every one-shot flag is
    an OR, and the lifecycle stage prefers anything past WATCHING (a name the
    other poller saw MET must not be 'WATCHING' here and fire MET again)."""
    out: dict = {}
    for key in set(a) | set(b):
        x, y = a.get(key), b.get(key)
        if x is None or y is None:
            out[key] = dict(x or y)
            continue
        m = dict(y)
        m["emailed_today"] = sorted(set(x.get("emailed_today") or []) | set(y.get("emailed_today") or []))
        for f in _FLAGS:
            m[f] = bool(x.get(f)) or bool(y.get(f))
        sx, sy = x.get("stage", STAGE_WATCHING), y.get("stage", STAGE_WATCHING)
        m["stage"] = sy if sy != STAGE_WATCHING else sx
        m["unr_stop"] = y.get("unr_stop") if y.get("unr_stop") is not None else x.get("unr_stop")
        out[key] = m
    return out


def _prune(state: dict) -> dict:
    """Drop keys more than KEEP_DAYS older than the NEWEST run date present
    (relative to the data, not the wall clock, so a state file is never
    emptied by a skewed clock or a replayed date)."""
    from datetime import date, timedelta
    try:
        dates = [date.fromisoformat(k.split(":", 1)[0]) for k in state]
    except ValueError:
        return state
    if not dates:
        return state
    cutoff = (max(dates) - timedelta(days=KEEP_DAYS)).isoformat()
    return {k: v for k, v in state.items() if k.split(":", 1)[0] >= cutoff}


def load_condition_state() -> dict:
    """Drive first (the shared source of truth between the in-app poller and
    the GitHub Actions backstop -- PM 2026-10-08: the backstop starts from a
    fresh checkout every run, so a local-only state made it re-send every
    currently-true card as new), merged with the local mirror."""
    drive, local = _drive_load(), _local_load()
    if drive is None:
        return local
    return merge_states(drive, local) if local else drive


def save_condition_state(state: dict) -> None:
    """Local mirror + Drive, both best-effort. Drive is re-read and merged
    first, so two pollers writing close together keep each other's keys."""
    state = _prune(state)
    try:
        CONDITION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONDITION_STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        from src.data import gdrive_uploader
        if gdrive_uploader.is_configured():
            other = _drive_load() or {}
            merged = merge_states(other, state) if other else state
            gdrive_uploader.upload_or_replace(STATE_FILENAME, json.dumps(merged, indent=2),
                                              mime="application/json")
    except Exception:  # noqa: BLE001
        pass


def _entry(state: dict, run_date: str, ticker: str) -> dict:
    key = _key(run_date, ticker)
    return state.setdefault(key, {"stage": STAGE_WATCHING, "emailed_today": [],
                                  "chased": False, "analyst_out": False,
                                  "exit_line": False, "unr": False,
                                  "unr_trigger": False, "unr_failed": False,
                                  "unr_stop": None})


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

    # U&R (PM 2026-10-07/08/09, Valen's setup). The daily chart picks the
    # stock, the intraday chart picks the entry; the two are NOT chained.
    # Three one-shots per name per day, independent of the buy lifecycle:
    #   UNR_ARMED    the daily CANDIDATE: a support level was undercut and the
    #                reclaim day is the one to watch. The heads-up.
    #   UNR_TRIGGER  a 15-min candle closed above VWAP on an armed name -- his
    #                entry. Fires whether or not spot is back above the daily
    #                level yet. If it is true on the same cycle the name is
    #                first armed, it is the only card (no separate candidate).
    #   UNR_FAILED   after the trigger, spot trades under the low of day that
    #                was the stop at trigger time.
    stop = eval_result.get("unr_stop")
    armed_new = False
    if eval_result.get("unr_armed") and not e.get("unr"):
        e["unr"] = True
        armed_new = True
        if eval_result.get("unr_trigger"):
            e["unr_trigger"], e["unr_stop"] = True, stop
            _fire_once("UNR_TRIGGER")
        else:
            _fire_once("UNR_ARMED")
    if (eval_result.get("unr_trigger") and e.get("unr") and not e.get("unr_trigger")
            and not armed_new):
        e["unr_trigger"], e["unr_stop"] = True, stop
        _fire_once("UNR_TRIGGER")
    spot = eval_result.get("unr_spot")
    if (e.get("unr_trigger") and not e.get("unr_failed") and spot is not None
            and e.get("unr_stop") is not None and spot < e["unr_stop"]):
        e["unr_failed"] = True
        _fire_once("UNR_FAILED")

    exit_fired = eval_result.get("exit_hit") or eval_result.get("exit_warn")
    if exit_fired and not e["exit_line"]:
        e["exit_line"] = True
        _fire_once("EXIT_LINE_HELD" if is_held else "EXIT_LINE_WARN")

    return fired
