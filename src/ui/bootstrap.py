"""Cold-start autoload — every module opens warm, from GitHub.

PM directive (2026-08-12): the app should restore itself whenever it is opened,
for every module — Scanner, Option scanner, Crown Macro — rather than leaving
the operator to notice an empty page and press a button.

Why this is gated rather than unconditional
-------------------------------------------
The state snapshot is large. Pulling it on every page view would make the app
slower the more you used it, for no gain: a container that already has today's
panel does not need a copy of today's panel. So the restore runs only when the
runtime state is genuinely **missing** — which is exactly the cold container the
directive is about — and costs one `exists()` check on every warm load.

Why it is synchronous
---------------------
Restoring in a background thread would let a page render while parquet files
were half-written, and a truncated panel does not raise — it reads short. A
page showing 40 of 900 tickers with no error is precisely the silent-empty
failure CLAUDE.md forbids. So the first caller blocks behind a spinner and
every other caller waits on the same lock. It happens once per container.

Order is GitHub first, Drive second, and the store that answered is recorded so
the status line can say which one. A restore that quietly came from the backup
while the primary was broken would hide the breakage until the backup was gone
too.
"""

from __future__ import annotations

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

_SGT = ZoneInfo("Asia/Singapore")

_lock = threading.Lock()
_done = False
_result: dict = {"state": "not_attempted"}

# The files whose absence means this container cannot answer anything useful.
# Deliberately the price/score spine plus the export, not every artifact: a
# missing Crown file is a degraded read, while a missing panel is no read.
_MARKERS = (
    ("data", "panel_daily.parquet"),
    ("data", "scores_daily.parquet"),
    ("output", "aqe_daily_export.json"),
)


def state_is_cold() -> tuple[bool, list[str]]:
    """(is the runtime state missing, which markers are absent)."""
    from src.data.paths import DATA_DIR, OUTPUT_DIR
    roots = {"data": DATA_DIR, "output": OUTPUT_DIR}
    missing = [name for root, name in _MARKERS if not (roots[root] / name).exists()]
    return bool(missing), missing


def status() -> dict:
    """What the last autoload did. Safe to call from any page."""
    return dict(_result)


# What can be salvaged from the repo folder alone when the snapshot is gone.
# Text artifacts only — the panels are far too big for the contents API and are
# the reason the snapshot exists at all.
_SALVAGE = ("aqe_daily_export.json", "aqe_crown_macro.json", "crown_macro.json",
            "macro_scenarios.json", "qs_daily.json", "held_positions.json")


def _salvage_read_only_artifacts() -> dict:
    """Fetch the day's JSON from the repo when the snapshot could not be had.

    A read-only recovery: the pages that only need the export will work, and
    anything needing the price panel will still say it cannot run. That
    distinction has to stay visible, so the result is labelled `partial`.
    """
    try:
        from src.data import github_sync as gh
        from src.data.paths import OUTPUT_DIR
        if not gh.is_configured():
            return {"ok": False, "reason": "GITHUB_TOKEN not set"}
        got = []
        for name in _SALVAGE:
            r = gh.get_file(f"{gh.OUTPUT_DIR_IN_REPO}/{name}")
            if r.get("ok"):
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                (OUTPUT_DIR / name).write_text(r["text"], encoding="utf-8")
                got.append(name)
        if not got:
            return {"ok": False, "reason": "nothing in the repo output folder either"}
        return {"ok": True, "store": "github_repo_partial", "files": got,
                "count": len(got), "partial": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def autoload_state(force: bool = False) -> dict:
    """Restore the runtime state if this container does not have it.

    Runs at most once per process unless `force` is set (the UI button). Never
    raises: the app must still open when both stores are unreachable, showing
    the reason rather than a traceback.
    """
    global _done, _result

    with _lock:
        if _done and not force:
            return dict(_result)

        try:
            cold, missing = state_is_cold()
        except Exception as exc:  # noqa: BLE001
            _done = True
            _result = {"state": "error", "reason": f"{type(exc).__name__}: {exc}"}
            return dict(_result)

        if not cold and not force:
            _done = True
            _result = {"state": "warm", "reason": "runtime state already present",
                       "checked_at": datetime.now(_SGT).strftime("%H:%M:%S SGT")}
            return dict(_result)

        try:
            from src.data.persist import load_snapshot_best
            res = load_snapshot_best()
        except Exception as exc:  # noqa: BLE001
            res = {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

        if not res.get("ok"):
            # Last resort: pull the export straight out of the repo folder. It
            # cannot rebuild the panels, so scanning stays unavailable, but the
            # committee read, the held book and the Crown page all come back.
            # This replaces the old committed root copy and is strictly better,
            # because it fetches the CURRENT file rather than whatever was
            # frozen into the repo the last time someone remembered to commit.
            salvage = _salvage_read_only_artifacts()
            if salvage.get("ok"):
                salvage["snapshot_reason"] = res.get("reason")
                res = salvage

        _done = True
        if res.get("ok"):
            _result = {
                "state": "restored",
                "store": res.get("store"),
                "partial": bool(res.get("partial")),
                "files": res.get("count") or len(res.get("files") or []),
                "saved_at": res.get("saved_at"),
                "was_missing": missing,
                "checked_at": datetime.now(_SGT).strftime("%H:%M:%S SGT"),
                # A restore that fell back is a working app AND a broken primary.
                # Both facts have to reach the status line.
                "degraded": res.get("store") in ("drive_backup", "github_repo_partial"),
                "reason": (f"primary store failed: {(res.get('tried') or {}).get('github')}"
                           if res.get("store") == "drive_backup"
                           else res.get("snapshot_reason")),
            }
        else:
            _result = {
                "state": "failed", "reason": res.get("reason"),
                "was_missing": missing,
                "checked_at": datetime.now(_SGT).strftime("%H:%M:%S SGT"),
            }
        return dict(_result)


def autoload_with_spinner(force: bool = False) -> dict:
    """`autoload_state` wrapped in a Streamlit spinner for the cold path.

    The spinner only appears when there is something to wait for, so a warm
    container shows nothing at all.
    """
    try:
        import streamlit as st
    except Exception:  # noqa: BLE001
        return autoload_state(force=force)

    if _done and not force:
        return dict(_result)
    try:
        cold, _ = state_is_cold()
    except Exception:  # noqa: BLE001
        cold = True
    if not cold and not force:
        return autoload_state(force=force)

    with st.spinner("Restoring the last run from GitHub…"):
        return autoload_state(force=force)


def render_status_line() -> None:
    """One caption under the page header. Silent when there is nothing to say."""
    try:
        import streamlit as st
    except Exception:  # noqa: BLE001
        return
    r = status()
    state = r.get("state")
    if state == "restored" and r.get("degraded"):
        st.warning(f"State restored from the Drive **backup** — the GitHub store "
                   f"did not answer. {r.get('reason')}")
    elif state == "restored" and r.get("partial"):
        st.warning("Only the day's JSON could be recovered from the repo — the "
                   "price panels are missing, so scanning and scoring will not "
                   f"run until the pipeline does. {r.get('reason') or ''}")
    elif state == "restored":
        st.caption(f"State restored from GitHub — {r.get('files')} files, "
                   f"snapshot of {r.get('saved_at') or 'unknown date'}.")
    elif state == "failed":
        st.error(f"This container has no runtime state and could not restore it: "
                 f"{r.get('reason')}. Run the pipeline, or restore a snapshot "
                 f"manually from the Scanner page.")
