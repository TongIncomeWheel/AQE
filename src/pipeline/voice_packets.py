"""Per-voice packet files — the daily split of the master export, plus a
drift check that proves the split still matches its source.

Committee request (2026-08-25, voice_packet_file_instruction): each S4
nominator voice reads exactly one file named for itself, holding only that
voice's own columns. Harness limitation, not a data change — nothing here
computes, scores, or decides anything. `aqe_daily_export.json` remains the
one master; these files are a pre-sliced VIEW of it and nothing else.

Why this module is thin on purpose
----------------------------------
The slicing rules already exist, in one place, and are already PM-ratified:
`aegis/skills/premarket-analysis/tools/pma_pipeline.py`'s `trim` (export ->
candidate_set) and `packets` (candidate_set + voice_menus -> per-voice TSVs).
Those carry the rules that actually matter and must not be duplicated:

  * R3 — no seat's menu may name `qs`/`on_qs` (PM-only), asserted before any
    file is written.
  * NO-BLANK-DATA — a ticker null on every core technical field is held out
    of the nominator TSVs entirely rather than served as a wall of "null",
    and reported in `no_technical_coverage.json`.
  * dead-column and pattern-gap reporting.
  * `None` renders as the literal token "null", never a blank cell.

So this module ORCHESTRATES those functions; it does not reimplement them.
A second copy of the slicing logic would itself become the drift this module
exists to detect.

What it adds
------------
  build()   run the trim+packets pair against the finished daily export and
            write `aegis/data/pma/<run-date>/packets/`. Wired into the daily
            orchestrator (Step 8a-3) so it happens once, automatically, after
            the export is written — not by hand, not remembered.
  verify()  re-derive the packets from the CURRENT master into a scratch dir
            and compare byte-for-byte against what is on disk. Any drift is
            named per file. This is the check that the packets a voice is
            about to read still agree with the export they claim to come from.

Byte-comparison is sound because the packets build is deterministic for a
given (export, menus, date): `cmd_packets` seeds its row shuffle with
`random.Random(date)`. Verified 2026-08-25 — a same-date rerun is byte
identical; only the date changes the shuffle.

Run:
    python -m src.pipeline.voice_packets build
    python -m src.pipeline.voice_packets verify
"""

from __future__ import annotations

import argparse
import filecmp
import importlib.util
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path

from src.data.paths import EXPORT_JSON, PROJECT_ROOT

# The PM-ratified pipeline tool. Its directory name is hyphenated
# ("premarket-analysis"), so it is not importable as a package — load it
# from its path instead. Deliberately the same file the PMA skill runs by
# hand, so the two can never disagree about what a packet contains.
PMA_PIPELINE = (PROJECT_ROOT / "aegis" / "skills" / "premarket-analysis"
                / "tools" / "pma_pipeline.py")
VOICE_MENUS = (PROJECT_ROOT / "aegis" / "skills" / "premarket-analysis"
               / "contracts" / "voice_menus.json")
PMA_DATA_DIR = PROJECT_ROOT / "aegis" / "data" / "pma"


def _load_pma_pipeline():
    """Import pma_pipeline.py by path. Raises if it is missing — a silent
    fallback here would mean shipping packets built by unknown rules."""
    if not PMA_PIPELINE.exists():
        raise FileNotFoundError(
            f"pma_pipeline.py not found at {PMA_PIPELINE} — the packet build "
            f"has no slicing rules to run and must not guess them")
    spec = importlib.util.spec_from_file_location("pma_pipeline", PMA_PIPELINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def packets_dir(run_date: str) -> Path:
    return PMA_DATA_DIR / run_date / "packets"


def _run_date_of(export_path: Path) -> str:
    """The packets are stamped with the EXPORT's own date, never today's
    wall clock — a re-run on a later day must reproduce the same packets for
    that export, and the date also seeds the shuffle."""
    d = json.loads(export_path.read_text(encoding="utf-8")).get("date")
    if not d:
        raise ValueError(f"{export_path} has no `date` field — cannot stamp packets")
    return str(d)


def _build_into(pma, export_path: Path, run_date: str, outdir: Path,
                quiet: bool = False) -> None:
    """trim -> packets, into `outdir`. Shared by build() and verify() so the
    two can never diverge in how they derive a packet set."""
    outdir.mkdir(parents=True, exist_ok=True)
    candidates = outdir.parent / "candidate_set.json"

    real_stdout = sys.stdout
    if quiet:
        sys.stdout = open("/dev/null", "w")          # noqa: SIM115
    try:
        pma.cmd_trim(types.SimpleNamespace(
            export=str(export_path), date=run_date, out=str(candidates)))
        pma.cmd_packets(types.SimpleNamespace(
            candidates=str(candidates), export=str(export_path),
            menus=str(VOICE_MENUS), date=run_date, outdir=str(outdir)))
    finally:
        if quiet:
            sys.stdout.close()
            sys.stdout = real_stdout


def build(export_path: Path | None = None, run_date: str | None = None) -> dict:
    """Split the finished daily export into per-voice packet files."""
    export_path = Path(export_path or EXPORT_JSON)
    if not export_path.exists():
        return {"ok": False, "reason": f"{export_path} not found — nothing to split"}
    pma = _load_pma_pipeline()
    run_date = run_date or _run_date_of(export_path)
    outdir = packets_dir(run_date)

    _build_into(pma, export_path, run_date, outdir)

    files = sorted(p.name for p in outdir.iterdir() if p.is_file())
    return {"ok": True, "run_date": run_date, "dir": str(outdir), "files": files}


def verify(export_path: Path | None = None, run_date: str | None = None) -> dict:
    """Re-derive the packets from the CURRENT master and compare to disk.

    Returns {ok, drift: [...]}. `ok` is False if anything on disk disagrees
    with what the current export would produce — missing file, changed
    content, or a stale extra file. Never raises on drift: the whole point is
    to report it, and a caller that cannot see the report learns nothing.
    """
    export_path = Path(export_path or EXPORT_JSON)
    if not export_path.exists():
        return {"ok": False, "drift": [f"master export {export_path} not found"]}
    pma = _load_pma_pipeline()
    run_date = run_date or _run_date_of(export_path)
    outdir = packets_dir(run_date)

    if not outdir.exists():
        return {"ok": False, "run_date": run_date,
                "drift": [f"packets dir {outdir} does not exist — never built for this run"]}

    tmp = Path(tempfile.mkdtemp(prefix="aqe_packet_verify_"))
    try:
        expected_dir = tmp / run_date / "packets"
        _build_into(pma, export_path, run_date, expected_dir, quiet=True)

        expected = {p.name for p in expected_dir.iterdir() if p.is_file()}
        actual = {p.name for p in outdir.iterdir() if p.is_file()}

        drift: list[str] = []
        for name in sorted(expected - actual):
            drift.append(f"{name}: MISSING on disk (the export produces it)")
        for name in sorted(actual - expected):
            drift.append(f"{name}: STALE on disk (the export no longer produces it)")
        for name in sorted(expected & actual):
            if not filecmp.cmp(expected_dir / name, outdir / name, shallow=False):
                drift.append(f"{name}: CONTENT DIFFERS from the current export")

        return {"ok": not drift, "run_date": run_date, "dir": str(outdir),
                "checked": len(expected | actual), "drift": drift}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def publish(run_date: str) -> dict:
    """Push the day's packet files into the repo.

    The daily run happens on an ephemeral container (GitHub Actions runner /
    HF Space), so a packet written only to local disk is gone by the time any
    voice looks for it. `aegis/data/pma/` is already a tracked path, and the
    committee reads the repo — so the packets go there, same store and same
    token as the Step 8a-2 output publish.
    """
    from src.data import github_sync

    outdir = packets_dir(run_date)
    if not outdir.exists():
        return {"ok": False, "reason": f"{outdir} does not exist — nothing to publish"}
    if not github_sync.is_configured():
        return {"ok": False, "reason": "GITHUB_TOKEN not set — packets stay local only"}

    # candidate_set.json rides along: it is the same derived-from-master
    # artifact, written by the same trim step, and PMA's later stages (rank)
    # read it. Publishing packets without it would strand them.
    items: list[tuple[str, Path]] = []
    cs = outdir.parent / "candidate_set.json"
    if cs.exists():
        items.append((f"aegis/data/pma/{run_date}/candidate_set.json", cs))
    for p in sorted(outdir.iterdir()):
        if p.is_file():
            items.append((f"aegis/data/pma/{run_date}/packets/{p.name}", p))

    msg = f"data: voice packets {run_date}"
    failed: list[str] = []
    for repo_path, local in items:
        res = github_sync.put_file(repo_path, local.read_text(encoding="utf-8"), msg)
        if not res.get("ok"):
            failed.append(f"{local.name}: {res.get('reason')}")
    return {"ok": not failed, "written": len(items) - len(failed),
            "total": len(items), "failed": failed,
            "reason": "; ".join(failed) if failed else None}


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("build", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--export", default=None)
        s.add_argument("--date", default=None)
    a = p.parse_args()

    if a.cmd == "build":
        res = build(a.export, a.date)
        if not res.get("ok"):
            print(f"[voice-packets] FAILED: {res.get('reason')}", file=sys.stderr)
            return 1
        print(f"[voice-packets] {len(res['files'])} file(s) -> {res['dir']}")
        return 0

    res = verify(a.export, a.date)
    if res.get("ok"):
        print(f"[voice-packets] IN SYNC — {res['checked']} file(s) match the "
              f"current export ({res['run_date']})")
        return 0
    print(f"[voice-packets] OUT OF SYNC ({res.get('run_date')}):", file=sys.stderr)
    for d in res["drift"]:
        print(f"  {d}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
