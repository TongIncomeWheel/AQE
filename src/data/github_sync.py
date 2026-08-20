"""GitHub as AQE's primary store — daily output and runtime state.

PM directive (2026-08-12): get off the local disk and off Google Drive, and keep
code *and* data in one place. This module is the GitHub write path. Drive stays
wired as a backup — the daily run writes both — so there is no flag day and no
window where the book lives in exactly one place.

Two destinations, and the split is not cosmetic
-----------------------------------------------

**Small text artifacts go in the repo**, committed to `aegis/output/` on the
default branch. They are a few hundred kilobytes, they diff, and having them in
git means a reader can see what changed in the book between two days without
downloading anything.

**The runtime state snapshot goes to a GitHub RELEASE asset**, never a commit.
The snapshot carries `panel_daily`, `ma_panel` (~2,000 tickers), `scores_daily`
and `aqe.db`, so it is tens to hundreds of megabytes. Git keeps every version of
every committed file forever: committing that zip daily would add its full size
to the repository permanently, every day, and `git clone` would be unusable
inside a month. A release asset is replaceable and deletable and lives outside
git history, which is exactly the property a rolling snapshot needs.

Auth
----
One secret, a fine-grained personal access token with **Contents: read+write**
on this repository:

    GITHUB_TOKEN        -- the PAT (HF Space secret + Actions secret)

Optional overrides:

    AQE_GITHUB_REPO     -- "owner/name", defaults to the pinned repo below
    AQE_GITHUB_BRANCH   -- defaults to "main"

Import-safe and configuration-safe: with no token every call returns
``{"ok": False, "reason": ...}`` rather than raising, so callers wire it
unconditionally. Per CLAUDE.md a failed fetch must be LOUD, so a reason is
always populated and never an empty dict.
"""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

import requests

API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"

# Pinned so no env var is required for the normal case, same pattern as the
# Drive folder ID.
DEFAULT_REPO = "TongIncomeWheel/AQE"
DEFAULT_BRANCH = "main"

# The one folder. Daily output lands here and nowhere else in the repo.
OUTPUT_DIR_IN_REPO = "aegis/output"

# The rolling snapshot lives on this release. A single tag that gets its asset
# replaced in place, so there is exactly one current state and no accumulation.
SNAPSHOT_TAG = "state-snapshot"

TIMEOUT = 60
_RETRY_STATUS = (409, 422, 500, 502, 503, 504)


# ── configuration ────────────────────────────────────────────────────────

def token() -> str | None:
    return (os.environ.get("GITHUB_TOKEN")
            or os.environ.get("AQE_GITHUB_TOKEN") or None)


def repo() -> str:
    return os.environ.get("AQE_GITHUB_REPO") or DEFAULT_REPO


def branch() -> str:
    return os.environ.get("AQE_GITHUB_BRANCH") or DEFAULT_BRANCH


def is_configured() -> bool:
    return bool(token())


def test_credentials() -> dict:
    """One cheap read-only call to prove the PAT is valid AND has write access
    to this repo — the two ways a token can look configured but still fail on
    the first real publish. No commit, no write, safe to click repeatedly."""
    if not is_configured():
        return {"ok": False, "reason": "GITHUB_TOKEN not set"}
    try:
        r = requests.get(f"{API}/repos/{repo()}", headers=_headers(), timeout=TIMEOUT)
        if r.status_code == 401:
            return {"ok": False, "reason": "token rejected (bad or expired PAT)"}
        if r.status_code == 404:
            return {"ok": False,
                     "reason": f"{repo()} not found, or token has no access to it"}
        r.raise_for_status()
        info = r.json()
        can_push = bool((info.get("permissions") or {}).get("push"))
        if not can_push:
            return {"ok": False,
                     "reason": f"token can read {repo()} but lacks push/write "
                               "access — needs Contents: read+write"}
        return {"ok": True, "repo": info.get("full_name"), "branch": branch(),
                "message": f"GitHub OK — write access to {info.get('full_name')} "
                           f"confirmed"}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc, "test credentials")


def _headers(accept: str = "application/vnd.github+json") -> dict:
    return {"Authorization": f"Bearer {token()}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28"}


def _not_configured() -> dict:
    return {"ok": False, "reason": "GITHUB_TOKEN not set — GitHub sync disabled"}


def _fail(exc: Exception, what: str) -> dict:
    return {"ok": False, "reason": f"{what}: {type(exc).__name__}: {str(exc)[:200]}"}


# ── contents API — the small text artifacts ──────────────────────────────

def get_file(path: str) -> dict:
    """Read a file from the repo. Returns {ok, text, sha} or {ok: False, reason}.

    A missing file is reported as ``missing: True`` rather than an error, because
    "not there yet" and "could not reach GitHub" are different answers and a
    caller deciding whether to create the file needs to tell them apart.
    """
    if not is_configured():
        return _not_configured()
    try:
        r = requests.get(f"{API}/repos/{repo()}/contents/{path}",
                         headers=_headers(), params={"ref": branch()},
                         timeout=TIMEOUT)
        if r.status_code == 404:
            return {"ok": False, "missing": True, "reason": f"{path} not in {repo()}"}
        r.raise_for_status()
        payload = r.json()
        raw = base64.b64decode(payload.get("content", "")).decode("utf-8", "replace")
        return {"ok": True, "text": raw, "sha": payload.get("sha"), "path": path}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc, f"read {path}")


def put_file(path: str, content: str | bytes, message: str) -> dict:
    """Create or update one file on the default branch.

    The Contents API needs the *current* blob sha to update an existing file, and
    two writers racing produce a 409. We re-read the sha and retry once, which is
    enough for our case: the only concurrent writers are the in-app scheduler and
    the Actions backstop, and they are already deduped against each other.
    """
    if not is_configured():
        return _not_configured()
    body = content.encode("utf-8") if isinstance(content, str) else content
    b64 = base64.b64encode(body).decode("ascii")

    for attempt in (1, 2):
        try:
            existing = get_file(path)
            payload: dict[str, Any] = {"message": message, "content": b64,
                                       "branch": branch()}
            if existing.get("ok") and existing.get("sha"):
                # Identical content: GitHub rejects a commit that changes
                # nothing. Report it as a success with a note, so a caller never
                # reads "unchanged" as "failed to write".
                if existing.get("text") == body.decode("utf-8", "replace"):
                    return {"ok": True, "unchanged": True, "path": path,
                            "bytes": len(body)}
                payload["sha"] = existing["sha"]
            elif not existing.get("ok") and not existing.get("missing"):
                return existing        # a real read failure, surfaced as-is

            r = requests.put(f"{API}/repos/{repo()}/contents/{path}",
                             headers=_headers(), json=payload, timeout=TIMEOUT)
            if r.status_code in _RETRY_STATUS and attempt == 1:
                time.sleep(1.5)
                continue
            r.raise_for_status()
            commit = (r.json().get("commit") or {})
            return {"ok": True, "path": path, "bytes": len(body),
                    "commit": commit.get("sha"),
                    "url": (r.json().get("content") or {}).get("html_url")}
        except Exception as exc:  # noqa: BLE001
            if attempt == 1:
                time.sleep(1.5)
                continue
            return _fail(exc, f"write {path}")
    return {"ok": False, "reason": f"write {path}: exhausted retries"}


def put_output(filename: str, content: str | bytes, message: str | None = None) -> dict:
    """Publish one daily artifact into the single output folder."""
    return put_file(f"{OUTPUT_DIR_IN_REPO}/{filename}", content,
                    message or f"data: {filename}")


def list_dir(path: str) -> dict:
    """What is currently in an arbitrary repo directory. {ok, files:[{name, sha, size}]}.

    Generic form of list_output() — same contract, any path in the repo (not just
    OUTPUT_DIR_IN_REPO). Added for readers outside the daily-output folder, e.g.
    src/data/ptj.py listing aegis/data/journal/ (D-84: git is the PTJ store now).
    """
    if not is_configured():
        return _not_configured()
    try:
        r = requests.get(f"{API}/repos/{repo()}/contents/{path}",
                         headers=_headers(), params={"ref": branch()},
                         timeout=TIMEOUT)
        if r.status_code == 404:
            return {"ok": True, "files": []}
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list):
            return {"ok": False, "reason": f"{path} is not a directory"}
        return {"ok": True, "files": [{"name": f.get("name"), "sha": f.get("sha"),
                                       "size": f.get("size")}
                                      for f in rows if f.get("type") == "file"]}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc, f"list {path}")


def list_output() -> dict:
    """What is currently in the output folder. {ok, files:[{name, sha, size}]}."""
    return list_dir(OUTPUT_DIR_IN_REPO)


def delete_file(path: str, message: str, sha: str | None = None) -> dict:
    """Remove a file from the repo. Needs the blob sha; reads it if not given."""
    if not is_configured():
        return _not_configured()
    try:
        if not sha:
            cur = get_file(path)
            if cur.get("missing"):
                return {"ok": True, "already_absent": True, "path": path}
            if not cur.get("ok"):
                return cur
            sha = cur["sha"]
        r = requests.delete(f"{API}/repos/{repo()}/contents/{path}",
                            headers=_headers(),
                            json={"message": message, "sha": sha,
                                  "branch": branch()}, timeout=TIMEOUT)
        r.raise_for_status()
        return {"ok": True, "path": path}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc, f"delete {path}")


# ── releases API — the heavy binary snapshot ─────────────────────────────

def _get_release(tag: str) -> dict:
    r = requests.get(f"{API}/repos/{repo()}/releases/tags/{tag}",
                     headers=_headers(), timeout=TIMEOUT)
    if r.status_code == 404:
        return {"ok": False, "missing": True}
    r.raise_for_status()
    return {"ok": True, "release": r.json()}


def _ensure_release(tag: str) -> dict:
    got = _get_release(tag)
    if got.get("ok"):
        return got
    if not got.get("missing"):
        return got
    r = requests.post(
        f"{API}/repos/{repo()}/releases", headers=_headers(),
        json={"tag_name": tag, "name": "AQE runtime state",
              "body": ("Rolling snapshot of AQE runtime state — panels, scores, "
                       "aqe.db and the day's outputs. The asset is REPLACED on "
                       "every run, so there is exactly one current state and "
                       "nothing accumulates. Kept out of git history on purpose: "
                       "a daily binary of this size committed to the repo would "
                       "grow it permanently."),
              "prerelease": True, "target_commitish": branch()},
        timeout=TIMEOUT)
    r.raise_for_status()
    return {"ok": True, "release": r.json(), "created": True}


def upload_asset(filename: str, blob: bytes, tag: str = SNAPSHOT_TAG,
                 content_type: str = "application/zip") -> dict:
    """Replace a release asset in place. This is the snapshot write path."""
    if not is_configured():
        return _not_configured()
    try:
        rel = _ensure_release(tag)
        if not rel.get("ok"):
            return {"ok": False, "reason": f"release {tag}: {rel.get('reason')}"}
        release = rel["release"]

        # Delete the old asset first — GitHub refuses a duplicate name rather
        # than overwriting, so "upload failed" would otherwise mean "yesterday's
        # state is still what you would restore", which is the silent-stale
        # failure CLAUDE.md forbids.
        for asset in (release.get("assets") or []):
            if asset.get("name") == filename:
                requests.delete(f"{API}/repos/{repo()}/releases/assets/{asset['id']}",
                                headers=_headers(), timeout=TIMEOUT)

        up = requests.post(
            f"{UPLOADS}/repos/{repo()}/releases/{release['id']}/assets",
            headers={**_headers(), "Content-Type": content_type},
            params={"name": filename}, data=blob, timeout=TIMEOUT * 5)
        up.raise_for_status()
        return {"ok": True, "name": filename, "bytes": len(blob), "tag": tag,
                "url": up.json().get("browser_download_url")}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc, f"upload asset {filename}")


def download_asset(filename: str, tag: str = SNAPSHOT_TAG) -> dict:
    """Fetch a release asset. Returns {ok, blob, bytes} or a stated reason."""
    if not is_configured():
        return _not_configured()
    try:
        rel = _get_release(tag)
        if rel.get("missing"):
            return {"ok": False, "missing": True,
                    "reason": f"no release tagged {tag} yet"}
        if not rel.get("ok"):
            return rel
        for asset in (rel["release"].get("assets") or []):
            if asset.get("name") == filename:
                r = requests.get(f"{API}/repos/{repo()}/releases/assets/{asset['id']}",
                                 headers=_headers("application/octet-stream"),
                                 timeout=TIMEOUT * 5)
                r.raise_for_status()
                return {"ok": True, "blob": r.content, "bytes": len(r.content),
                        "updated_at": asset.get("updated_at")}
        return {"ok": False, "missing": True,
                "reason": f"{filename} is not on release {tag}"}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc, f"download asset {filename}")


def asset_status(filename: str, tag: str = SNAPSHOT_TAG) -> dict:
    """When was the snapshot last written, without downloading it."""
    if not is_configured():
        return _not_configured()
    try:
        rel = _get_release(tag)
        if not rel.get("ok"):
            return {"ok": False, "reason": rel.get("reason") or f"no release {tag}"}
        for asset in (rel["release"].get("assets") or []):
            if asset.get("name") == filename:
                return {"ok": True, "bytes": asset.get("size"),
                        "updated_at": asset.get("updated_at"),
                        "url": asset.get("browser_download_url")}
        return {"ok": False, "reason": f"{filename} not on release {tag}"}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc, "asset status")


# ── convenience for the daily run ────────────────────────────────────────

def publish_outputs(files: dict[str, str | bytes], stamp: str | None = None) -> dict:
    """Publish the day's artifacts in one call.

    `files` is {filename: content}. Returns a per-file result plus a summary, so
    a partial failure is visible rather than averaged into a single boolean.
    """
    if not is_configured():
        return {"ok": False, **_not_configured(), "results": {}}
    msg = f"data: daily output {stamp}" if stamp else "data: daily output"
    results = {name: put_output(name, content, msg)
               for name, content in files.items()}
    failed = [n for n, r in results.items() if not r.get("ok")]
    return {"ok": not failed, "results": results, "written": len(results) - len(failed),
            "failed": failed,
            "reason": (f"{len(failed)} of {len(results)} failed: "
                       + ", ".join(failed)) if failed else None}


# Every text artifact the daily run produces. One folder, one copy each,
# overwritten in place — the folder must not accumulate dated files, because a
# reader that has to pick the newest of several is the bug that produced a
# wrong-file held book once already (see the PTJ note in CLAUDE.md).
DAILY_ARTIFACTS = (
    "aqe_daily_export.json",      # the committee's read
    "aqe_crown_macro.json",       # Crown reading copy, plain English first
    "crown_macro.json",           # Crown runtime record, carries the series
    "macro_scenarios.json",       # the Crown x Macro Weather merge point
    "aqe_macro_pack.json",        # Crown+MacroWeather+SRM+Thematic, one door
    "qs_daily.json",              # QS standalone artifact
    "shortlist.json",
    "held_positions.json",
    "aqe_sector_map.json",
    "options_scan.json",          # universe CSP theta sweep
    "aqe_last_run.json",          # the run marker the status bar reads
)


def publish_daily_outputs(stamp: str | None = None,
                          names: tuple | list | None = None) -> dict:
    """Publish the day's artifacts from OUTPUT_DIR into the repo.

    Only files that actually exist on disk are sent. A missing artifact is
    reported in `absent` rather than skipped quietly, so a run that failed to
    produce Crown or QS is visible in the result instead of just being a shorter
    list of successes.
    """
    if not is_configured():
        return {"ok": False, **_not_configured(), "results": {}, "absent": []}
    from src.data.paths import OUTPUT_DIR

    payload, absent = {}, []
    for name in (names or DAILY_ARTIFACTS):
        p = OUTPUT_DIR / name
        if p.exists():
            try:
                payload[name] = p.read_text(encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                absent.append(f"{name} (unreadable: {type(exc).__name__})")
        else:
            absent.append(name)
    if not payload:
        return {"ok": False, "reason": "no output artifacts on disk to publish",
                "results": {}, "absent": absent}
    res = publish_outputs(payload, stamp=stamp)
    res["absent"] = absent
    return res


def status() -> dict:
    """One dict for the UI status bar."""
    if not is_configured():
        return {"configured": False,
                "reason": "GITHUB_TOKEN not set", "repo": repo(),
                "branch": branch(), "folder": OUTPUT_DIR_IN_REPO}
    out = list_output()
    snap = asset_status("aqe_state_snapshot.zip")
    return {"configured": True, "repo": repo(), "branch": branch(),
            "folder": OUTPUT_DIR_IN_REPO,
            "files": out.get("files") if out.get("ok") else [],
            "files_reason": out.get("reason"),
            "snapshot": snap}
