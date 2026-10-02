"""AQE handoff D123/R21 (2026-10-02) §7 — the shadow-mode log.

Every cycle, one line per name to
`aegis/output/alerts/condition_ledger/<date>.jsonl` — the record the 15 Oct
review and PMA's own scorecard both read, independent of whether anything
was actually emailed (shadow mode never emails at all). A daily summary
file sits alongside it for a quick read without parsing the whole JSONL.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.data.paths import PROJECT_ROOT

LEDGER_DIR = PROJECT_ROOT / "aegis" / "output" / "alerts" / "condition_ledger"
_SGT = ZoneInfo("Asia/Singapore")


def _jsonl_path(date_str: str) -> Path:
    return LEDGER_DIR / f"{date_str}.jsonl"


def _summary_path(date_str: str) -> Path:
    return LEDGER_DIR / f"{date_str}.summary.json"


def build_ledger_line(ticker: str, eval_result: dict, fired_states: list[str], *,
                      vol_x: dict | None = None, session_vwap: dict | None = None,
                      rs_today: float | None = None, legacy_vol_pace: float | None = None,
                      old_trigger: dict | None = None,
                      now: datetime | None = None) -> dict:
    """One line's worth of fact, independent of whether anything fired —
    a quiet cycle is logged too, so "nothing happened" is a recorded
    answer, not a gap in the file."""
    now = now or datetime.now(_SGT)
    return {
        "ts": now.isoformat(timespec="seconds"),
        "ticker": ticker,
        "fired_states": fired_states,
        "buy_met": eval_result.get("buy_met"),
        "lit": eval_result.get("lit"),
        "wrong_lit": eval_result.get("wrong_lit"),
        "chased": eval_result.get("chased"),
        "exit_warn": eval_result.get("exit_warn"),
        "exit_hit": eval_result.get("exit_hit"),
        "unknown_words": eval_result.get("unknown_words") or [],
        "vol_x": vol_x,
        # §8.1: the old linear-clock figure, kept alongside the new vol_x
        # for two weeks of side-by-side comparison -- never retrofitted
        # into the currently-live trigger path itself.
        "legacy_vol_pace": legacy_vol_pace,
        "session_vwap": session_vwap,
        "rs_today": rs_today,
        "old_trigger": old_trigger,
    }


def append_line(date_str: str, line: dict) -> None:
    """Best-effort append — a logging failure must never break a live
    alert cycle that has ~50 other names still to get through."""
    try:
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        with _jsonl_path(date_str).open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, default=str) + "\n")
    except Exception:  # noqa: BLE001
        pass


def load_lines(date_str: str) -> list[dict]:
    path = _jsonl_path(date_str)
    if not path.exists():
        return []
    out = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    except Exception:  # noqa: BLE001
        pass
    return out


def write_summary(date_str: str, lines: list[dict] | None = None) -> dict:
    """A daily digest built from the day's own ledger lines — PMA's
    scorecard reads this to grade "condition met" against the next close
    and the next 5 sessions (§7), without parsing the full JSONL."""
    lines = lines if lines is not None else load_lines(date_str)
    by_ticker: dict[str, list[str]] = {}
    for line in lines:
        tk = line.get("ticker")
        if not tk:
            continue
        by_ticker.setdefault(tk, [])
        for s in (line.get("fired_states") or []):
            if s not in by_ticker[tk]:
                by_ticker[tk].append(s)
    summary = {
        "date": date_str,
        "n_cycles_logged": len(lines),
        "tickers": sorted(by_ticker),
        "states_by_ticker": by_ticker,
        "condition_met_tickers": sorted(
            tk for tk, states in by_ticker.items() if "CONDITION_MET" in states),
    }
    try:
        LEDGER_DIR.mkdir(parents=True, exist_ok=True)
        _summary_path(date_str).write_text(json.dumps(summary, indent=2, default=str),
                                           encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return summary
