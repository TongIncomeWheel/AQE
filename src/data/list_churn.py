"""List size and churn: what entered and left `daily_list` since the previous export, and WHY each leaver left (PM/conductor 2026-11-05).

Why: on 5 Nov the list went 260 -> 395 names and 23 left it (BRZE, TMO, LHX, CNP ...). Nothing said which gate removed a name, and a name that is on the
committee book or in the alert universe can leave the list overnight with nobody told. This module explains it, and prints it.

What it is NOT: a rule. It measures membership against the two EXISTING gates and decides nothing:
  Longlist   = raw SC_MOM >= `longlist_screen.MIN_SC` AND Elder >= `longlist_screen.MIN_ELDER`   (src/longlist_screen.py, the one definition)
  Elder list = Elder (rounded) >= 8                                                              (drive_sync, sole criterion)
A name stays on `daily_list` if it clears either gate, or is a ledger (runner/pre-move) or QS name. A leaver therefore failed BOTH gates, or was not scored.

Pure functions over plain dicts, so it is testable without pandas or a run. Never raises into the export: `attach` returns an error block instead.
"""
from __future__ import annotations

import json
from pathlib import Path

from src.longlist_screen import MIN_ELDER as LL_MIN_ELDER, MIN_SC as LL_MIN_SC

ELDER_LIST_MIN = 8


def _num(v):
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def explain_drop(ticker: str, score_row, prev_row: dict | None = None) -> dict:
    """Why `ticker` is no longer on the list. `score_row` = today's scores_daily row (dict / Series) or None when the name was not scored today."""
    prev_row = prev_row or {}
    prev_flags = {k: bool(prev_row.get(k)) for k in ("on_longlist", "on_elder", "in_ledger", "on_qs")}
    base = {"ticker": ticker, "was": [k for k, v in prev_flags.items() if v], "prev_sc_momentum": prev_row.get("sc_momentum"), "prev_elder": prev_row.get("elder")}
    if score_row is None:
        return {**base, "status": "NOT_SCORED", "sc_momentum_raw": None, "elder": None,
                "reasons": ["not in today's scores (no price history today, or removed from the scored universe)"]}
    g = score_row.get if hasattr(score_row, "get") else (lambda k, d=None: d)
    raw = _num(g("sc_momentum_raw"))
    if raw is None:
        raw = _num(g("sc_momentum"))
    elder = _num(g("elder_score"))
    reasons = []
    if raw is None:
        reasons.append("SC_MOM is blank today")
    elif raw < LL_MIN_SC:
        reasons.append(f"SC_MOM {raw:.1f} is under the Longlist floor {LL_MIN_SC}")
    if elder is None:
        reasons.append("Elder is blank today")
    else:
        if round(elder, 1) < LL_MIN_ELDER:
            reasons.append(f"Elder {elder:.1f} is under the Longlist floor {LL_MIN_ELDER}")
        if round(elder) < ELDER_LIST_MIN:
            reasons.append(f"Elder {elder:.1f} is under the Elder-list floor {ELDER_LIST_MIN}")
    if not reasons:        # clears a gate on today's score yet is absent: say so, never invent a reason
        return {**base, "status": "CLEARS_GATES_BUT_ABSENT", "sc_momentum_raw": raw, "elder": elder,
                "reasons": ["clears a list gate on today's score but is not in the list: check the export build (a real fault, not a rule)"]}
    return {**base, "status": "BELOW_GATES", "sc_momentum_raw": raw, "elder": elder, "reasons": reasons}


def compute(prev_export: dict | None, daily_list: list[dict], sc_by_tk: dict, today_iso: str | None = None) -> dict:
    """The churn block for `export["list_churn"]`."""
    now = {r.get("ticker"): r for r in (daily_list or []) if r.get("ticker")}
    if not prev_export or not isinstance(prev_export.get("daily_list"), list):
        return {"status": "no_previous", "reason": "no earlier export to compare with (first run, or the previous file was unreadable)",
                "date": today_iso, "prev_date": None, "n_now": len(now), "n_prev": None, "added": [], "removed": []}
    prev = {r.get("ticker"): r for r in prev_export["daily_list"] if r.get("ticker")}
    added = sorted(set(now) - set(prev))
    removed = [explain_drop(t, (sc_by_tk or {}).get(t), prev[t]) for t in sorted(set(prev) - set(now))]
    return {"status": "ok", "date": today_iso, "prev_date": prev_export.get("date"), "n_prev": len(prev), "n_now": len(now),
            "n_added": len(added), "n_removed": len(removed), "added": added, "removed": removed,
            "gates": {"longlist": f"SC_MOM >= {LL_MIN_SC} and Elder >= {LL_MIN_ELDER}", "elder_list": f"Elder >= {ELDER_LIST_MIN}"}}


def line(churn: dict) -> str:
    """The one run-marker line (the marker reads the stdout line that starts with 'List churn:')."""
    if not isinstance(churn, dict) or churn.get("status") != "ok":
        why = (churn or {}).get("reason") or (churn or {}).get("error") or "not computed"
        return f"List churn: NOT COMPUTED - {why}"
    rem = [r["ticker"] for r in churn["removed"]]
    return (f"List churn: {churn['n_prev']} -> {churn['n_now']} names vs {churn['prev_date']} (+{churn['n_added']} / -{churn['n_removed']}) | "
            f"added: {', '.join(churn['added']) or 'none'} | left: {', '.join(rem) or 'none'}")


def detail_lines(churn: dict, limit: int = 60) -> list[str]:
    """One printed line per leaver: ticker + the gate that removed it."""
    if not isinstance(churn, dict) or churn.get("status") != "ok":
        return []
    out = [f"    left {r['ticker']:6s} [{r['status']}] " + "; ".join(r["reasons"]) + (f" (was {'/'.join(r['was'])})" if r["was"] else "")
           for r in churn["removed"][:limit]]
    if len(churn["removed"]) > limit:
        out.append(f"    ... and {len(churn['removed']) - limit} more leavers (all are in export['list_churn']['removed'])")
    return out


def load_previous(today_iso: str, candidates: list[Path | str]) -> dict | None:
    """The newest readable earlier export among `candidates` whose date is BEFORE today (a rerun of today must not compare with itself)."""
    best, best_date = None, ""
    for p in candidates:
        try:
            p = Path(p)
            if not p.exists():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            dd = str(d.get("date") or "")[:10]
            if dd and dd < str(today_iso)[:10] and dd > best_date and isinstance(d.get("daily_list"), list):
                best, best_date = d, dd
        except Exception:  # noqa: BLE001 - an unreadable candidate is skipped, never fatal
            continue
    return best


def attach(export: dict, sc_by_tk: dict, candidates: list[Path | str]) -> dict:
    """Compute, attach `export["list_churn"]` and print the marker line + one line per leaver. Never raises."""
    try:
        today = str(export.get("date") or "")[:10]
        ch = compute(load_previous(today, candidates), export.get("daily_list") or [], sc_by_tk, today)
    except Exception as e:  # noqa: BLE001
        ch = {"status": "error", "error": f"{e.__class__.__name__}: {str(e)[:160]}", "date": export.get("date"), "added": [], "removed": []}
    export["list_churn"] = ch
    try:
        print("  " + line(ch))
        for ln in detail_lines(ch):
            print(ln)
    except Exception:  # noqa: BLE001
        pass
    return ch
