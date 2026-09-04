"""Per-voice packet files — the daily split of the master export, plus a
drift check that proves the split still matches its source.

Committee request (2026-08-25, voice_packet_file_instruction v2): a voice
reads exactly one file named for itself, holding only that voice's own
columns. Harness limitation, not a data change — nothing here computes,
scores, or decides anything. `aqe_daily_export.json` remains the one master;
these files are a pre-sliced VIEW of it and nothing else.

The 14-voice roster splits three ways, and this module writes 11 files:

  Group A (9)  elder-lens, livermore, minervini, oneil, raschke, seow,
               thorp, weis, wyckoff -> `<voice>.tsv`, columns from that
               voice's `voice_menus.json` entry (6 fields up to 38).
  Group B (2)  crown, druckenmiller -> `<voice>.json`, macro blocks only
               (date/market/regime/intermarket/srm/macro_weather/
               thematic_baskets), never the PM-only `qs_market`.
  Group C (4)  rogers, steenbarger, lynch, detect-lens -> NO FILE, by
               design, not a gap. They activate only after the Phase-4 cap,
               on the 20-name deliberation set, from a bundle compiled
               during that morning's own run (nominators' Round-1 reasoning,
               challenge write-ups, and so on). None of that exists on disk
               before the run starts, so there is nothing to pre-slice.
               Lynch does live research and is never served a file at all.

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
            write `output/packets/`. Wired into the daily orchestrator
            (Step 8a-3) so it happens once, automatically, after the export
            is written — not by hand, not remembered.
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

from src.data.paths import EXPORT_JSON, OUTPUT_DIR, PROJECT_ROOT

# The PM-ratified pipeline tool. Its directory name is hyphenated
# ("premarket-analysis"), so it is not importable as a package — load it
# from its path instead. Deliberately the same file the PMA skill runs by
# hand, so the two can never disagree about what a packet contains.
PMA_PIPELINE = (PROJECT_ROOT / "aegis" / "skills" / "premarket-analysis"
                / "tools" / "pma_pipeline.py")
VOICE_MENUS = (PROJECT_ROOT / "aegis" / "skills" / "premarket-analysis"
               / "contracts" / "voice_menus.json")

# PM ruling 2026-08-25: the packets land beside the daily export and the Crown
# file, not in a separate dated tree — one delivery destination for everything
# the committee reads. Local `output/packets/` mirrors repo
# `aegis/output/packets/`, the same local->repo mapping every other artifact
# uses. A `packets/` subfolder rather than 11 loose files because a flat
# `crown.json` would sit beside `crown_macro.json` AND `aqe_crown_macro.json`
# — three crown-ish names, two macro reads and one voice packet, which is
# exactly the kind of ambiguity a committee reader should never have to
# resolve. Overwritten in place each run like every other output; git history
# holds the prior days.
PACKETS_DIRNAME = "packets"
OUTPUT_PACKETS_IN_REPO = "aegis/output/packets"


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


def packets_dir(run_date: str | None = None) -> Path:
    """Local packet dir. `run_date` is accepted and ignored — the packets are
    a CURRENT-copy artifact like every other file in output/, not a dated
    tree. The date still identifies the run (it stamps candidate_set.json and
    seeds the shuffle); it just no longer forks the path."""
    return OUTPUT_DIR / PACKETS_DIRNAME


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
    voice looks for it. They go to `aegis/output/packets/` — the same repo,
    branch, store and token as the daily export and the Crown file, one
    delivery destination for everything the committee reads (PM ruling
    2026-08-25).
    """
    from src.data import github_sync

    outdir = packets_dir(run_date)
    if not outdir.exists():
        return {"ok": False, "reason": f"{outdir} does not exist — nothing to publish"}
    if not github_sync.is_configured():
        return {"ok": False, "reason": "GITHUB_TOKEN not set — packets stay local only"}

    # One cheap read-only call up front, so a DEFINITELY-broken token (missing,
    # rejected, repo unreachable) surfaces as ONE clear sentence instead of up
    # to 11 near-identical raw HTTPErrors. Only bail here on hard_fail: the
    # permissions.push field this call also inspects is unreliable (observed
    # 2026-09-03: same PAT read push=true on one run and push=false minutes
    # later on another, while both runs' real Contents-API writes succeeded)
    # -- a soft "ok: False" from this preflight must not block the real
    # writes below, which are self-diagnosing per file regardless.
    cred = github_sync.test_credentials()
    if not cred.get("ok") and cred.get("hard_fail"):
        return {"ok": False, "reason": f"GitHub auth check failed: {cred.get('reason')}"}

    # candidate_set.json rides along: same derived-from-master artifact, same
    # trim step, and PMA's later stages (rank) read it. But it is published
    # BESIDE packets/, never inside it — CONSUMED deliberately keeps `qs` on
    # it for the PM's S7 card, so it is not seat-safe. Everything inside
    # packets/ is a file some voice may open; keeping the one QS-carrying
    # artifact out of that folder makes "packets/ is seat-safe" a structural
    # property rather than a convention (asserted in tests).
    items: list[tuple[str, Path]] = []
    cs = outdir.parent / "candidate_set.json"
    if cs.exists():
        items.append((f"{github_sync.OUTPUT_DIR_IN_REPO}/candidate_set.json", cs))
    for p in sorted(outdir.iterdir()):
        if p.is_file():
            items.append((f"{OUTPUT_PACKETS_IN_REPO}/{p.name}", p))

    msg = f"data: voice packets {run_date}"
    failed: list[str] = []
    changed: list[str] = []
    for repo_path, local in items:
        res = github_sync.put_file(repo_path, local.read_text(encoding="utf-8"), msg)
        if not res.get("ok"):
            failed.append(f"{local.name}: {res.get('reason')}")
        elif not res.get("unchanged"):
            changed.append(local.name)
    return {"ok": not failed, "written": len(items) - len(failed),
            "total": len(items), "changed": changed, "failed": failed,
            "reason": "; ".join(failed) if failed else None}


def sync(export_path: Path | None = None) -> dict:
    """Make the published packets match the published export — repairing
    them if they do not.

    Exists because Step 8a-3 only runs if the process running the pipeline
    HAS it. 2026-08-25: the HF Space ran the daily 140 seconds after the step
    landed on main, so its image predated the code entirely — the export
    updated, the packets did not, and AIC read a day-old set. Nothing threw;
    there was nothing to throw.

    This is the backstop, and it is deliberately driven by GitHub Actions,
    which checks out main fresh on every run and therefore cannot execute a
    stale image. It does not care which path produced the export or what code
    that path was running: it rebuilds the packets from whatever export is
    currently published and pushes any file whose content actually differs.
    Identical content is a no-op (github_sync.put_file reports `unchanged`),
    so a healthy day costs nothing and writes no commit.
    """
    export_path = Path(export_path or EXPORT_JSON)
    if not export_path.exists():
        return {"ok": False, "reason": f"{export_path} not found — nothing to sync against"}

    before = verify(export_path)
    built = build(export_path)
    if not built.get("ok"):
        return {"ok": False, "reason": built.get("reason")}

    pub = publish(built["run_date"])
    if not pub.get("ok"):
        return {"ok": False, "run_date": built["run_date"],
                "reason": pub.get("reason")}

    return {"ok": True, "run_date": built["run_date"],
            "was_in_sync": bool(before.get("ok")),
            "changed": pub.get("changed") or [],
            "drift_found": before.get("drift") or []}


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # `sync` is the default with no subcommand: it is the only one that both
    # rebuilds AND publishes, so it is what "run the voice packets" means to
    # anyone who is not reasoning about internals. Also what lets the Scanner
    # button and the .bat work — both invoke `python -m <module>` bare.
    sub = p.add_subparsers(dest="cmd", required=False)
    for name in ("build", "verify", "sync"):
        s = sub.add_parser(name)
        s.add_argument("--export", default=None)
        s.add_argument("--date", default=None)
    a = p.parse_args()
    if not a.cmd:
        a = argparse.Namespace(cmd="sync", export=None, date=None)

    if a.cmd == "sync":
        res = sync(a.export)
        if not res.get("ok"):
            print(f"[voice-packets] SYNC FAILED: {res.get('reason')}", file=sys.stderr)
            return 1
        if res["was_in_sync"] and not res["changed"]:
            print(f"[voice-packets] already current ({res['run_date']}) — nothing to do")
        else:
            print(f"[voice-packets] REPAIRED ({res['run_date']}): "
                  f"{len(res['changed'])} file(s) republished")
            for d in res["drift_found"]:
                print(f"  was: {d}")
            for c in res["changed"]:
                print(f"  now: {c}")
        return 0

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
