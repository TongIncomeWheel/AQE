"""Pre-Trade Journal (PTJ) reader — the daily held-positions feed from git.

D-84 (2026-07-2x, PM-ratified) retired Google Drive as the PTJ store on the
write side: `aegis/data/journal/aegis_journal_YYYY-MM-DD.json`, committed to
this repo's main branch by the post-market pipeline (`aegis/tools/git_sync.py`),
is now the ONE book of record — "a second Drive copy of the same JSON had no
upside once GitHub already held it as a version-controlled backup."

This reader was never updated to match: until this fix it still polled a Drive
folder that nothing writes to anymore, so `held_positions.json` silently froze
on whatever the last real Drive upload was (2026-07-21) while the actual book
kept moving in git. Discovered 2026-08-20 when a same-day correction (adding
OXY/MRK to the Aegis book) landed on GitHub but never reached AQE's own
held-positions feed.

Fix: read the latest dated journal straight out of git via `github_sync` (the
same client AQE already uses for its own daily-output writes), instead of
Drive. AQE reads the latest journal by the date encoded in its filename — see
_JOURNAL_NAME_RE — from `aegis/data/journal/`, which the post-market pipeline
keeps to dated snapshots only (no ARCHIVE-file-style pollution risk: the
running master lives at a different path, `aegis/data/persistent/`, and is
never written into this directory).

We extract the OPEN (held) positions and cache them locally so the engine can
flag held names and the UI/Charts can show entry vs current price.

Failures degrade to the local cache, then to empty — never raise.
"""

from __future__ import annotations

import json
import os
import re

from src.data.paths import OUTPUT_DIR

PTJ_CACHE = OUTPUT_DIR / "held_positions.json"

# RETIRED (D-84, this fix) — no longer read by fetch_latest_ptj() below, which
# now reads git instead of Drive. Left defined (not deleted) only because
# scripts/cleanup_ptj_folder.py + .github/workflows/ptj-cleanup.yml still
# import it; that script tidies a Drive folder nothing writes to anymore and
# should itself be retired/disabled — flagged separately, not done here.
PTJ_FOLDER_ID = (
    os.environ.get("GDRIVE_PTJ_FOLDER_ID")
    or "15PR74ws_kTXTqCcEfRGga_jjHrMvbCEM"
)

# aegis/tools/git_sync.py's dated book-of-record filename convention.
JOURNAL_DIR_IN_REPO = "aegis/data/journal"
_JOURNAL_NAME_RE = re.compile(r"^aegis_journal_(\d{4}-\d{2}-\d{2})\.json$")


def fetch_latest_ptj() -> dict | None:
    """Download + parse the most-recent book-of-record journal from git.

    "Most recent" is decided by the DATE ENCODED IN THE FILENAME — the same
    invariant the old Drive reader enforced (a file's git commit time is not
    used as the tiebreaker key; the post-market pipeline never writes two
    same-day journals under different names, so filename-date alone is
    sufficient here, unlike the old multi-file-per-day Drive folder).
    """
    try:
        from src.data import github_sync
        if not github_sync.is_configured():
            return None
        listing = github_sync.list_dir(JOURNAL_DIR_IN_REPO)
        if not listing.get("ok"):
            return None
        candidates = []
        for f in (listing.get("files") or []):
            name = f.get("name") or ""
            m = _JOURNAL_NAME_RE.match(name)
            if m:
                candidates.append((m.group(1), name))
        if not candidates:
            return None
        candidates.sort(key=lambda c: c[0], reverse=True)
        _, latest_name = candidates[0]
        result = github_sync.get_file(f"{JOURNAL_DIR_IN_REPO}/{latest_name}")
        if not result.get("ok"):
            return None
        data = json.loads(result["text"])
        data["_ptj_file"] = latest_name
        data["_ptj_modified"] = data.get("date")
        # Journal schema names option legs "option_positions"; the PTJ cache
        # contract below (refresh_held_positions) expects "options".
        data.setdefault("options", data.get("option_positions") or [])
        return data
    except Exception:  # noqa: BLE001
        return None


def refresh_held_positions() -> list[dict]:
    """Fetch the latest PTJ, extract held positions, cache locally. Returns them.

    Falls back to the local cache when GitHub is unavailable — but NEVER lets a
    failed live fetch silently masquerade as a genuine flat book: the cache
    always carries a `status` ("live" | "cache_fallback") so downstream
    readers (the export, the Scanner UI) can tell "PTJ fetch failed this run"
    apart from "the book is actually empty". Real-money system — a silent
    empty is worse than a stale-but-labeled one.
    """
    ptj = fetch_latest_ptj()
    if not ptj:
        prior = load_ptj_cache()
        prior["status"] = "cache_fallback"
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            PTJ_CACHE.write_text(json.dumps(prior, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        return prior.get("positions") or []
    held = ptj.get("open_positions") or []
    cache = {
        "source_file": ptj.get("_ptj_file"),
        "modified": ptj.get("_ptj_modified"),
        "snapshot": ptj.get("snapshot"),
        "positions": held,
        "options": ptj.get("options") or [],
        "status": "live",
    }
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        PTJ_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return held


def load_ptj_cache() -> dict:
    """The cached PTJ snapshot ({source_file, modified, positions, options, status})."""
    try:
        if PTJ_CACHE.exists():
            return json.loads(PTJ_CACHE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return {}


def load_held_positions() -> list[dict]:
    """Held (open) positions from the local cache — no GitHub call."""
    return load_ptj_cache().get("positions") or []


def ptj_status() -> str:
    """'live' (this run fetched fresh from git), 'cache_fallback' (GitHub fetch
    failed/unreachable and we fell back to whatever was last cached — possibly
    stale or, on a freshly-restarted container, empty), or 'unknown' (no cache
    file has ever been written)."""
    cache = load_ptj_cache()
    return cache.get("status") or ("unknown" if not cache else "cache_fallback")
