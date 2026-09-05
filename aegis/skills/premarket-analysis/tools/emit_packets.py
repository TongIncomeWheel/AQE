#!/usr/bin/env python3
"""emit_packets.py — AQE-side nightly packet emitter (v5 ruling #4, PM-approved 2026-08-28).

RULING: AQE ships the Round-1 voice packets; the morning PMA run VERIFIES them
instead of building them. This script is the shipping half. It runs at the END
of the nightly AQE export job — after aqe_daily_export.json is written — and
produces, in ONE pass from ONE source, committed together in ONE commit:

  aegis/output/voice_packets/candidate_set.json     (the universe file)
  aegis/output/voice_packets/<voice>.tsv            (one per nominator seat)
  aegis/output/voice_packets/crown_packet.json
  aegis/output/voice_packets/druckenmiller_packet.json
  aegis/output/voice_packets/packet_stamp.json      (THE STAMP — see below)

The STAMP is what makes pre-slicing safe (v5 guard condition i): a manifest
carrying the sha256 of every emitted file, the sha256 of the menus file used to
slice, the sha256 of the export sliced from, and the generation timestamp.
Files born together and stamped together cannot drift. The morning run's
PREPARE step re-hashes what it fetched against this stamp and re-hashes the
CURRENT menus file against menus_sha256 — any mismatch and it falls back to
slicing locally from the canonical export (guard condition iii), declares the
degradation, and continues.

R3 is asserted twice: pma_pipeline.py packets fails loudly if qs_market leaks
into a seat packet (build-time), and this script independently scans every
emitted packet for the byte-pattern as a second lock before stamping.

Chart-pattern fields (pattern*) get the identical two-lock treatment (PM
ruling 2026-09-05): pma_pipeline.py packets refuses a menu naming one at
build time, and this script's byte-scan below is the second lock.

INVARIANT (PM clarification 2026-08-28): packets are spawn-time inputs only,
consumed once, never read again. Everything downstream reads the canonical
export + saved forms. If a packet and the export disagree, the export wins and
the stamp check has failed.

Slicing logic is NOT reimplemented here — this calls pma_pipeline.py trim +
packets via subprocess, so there is exactly one slicer in the codebase.

Integration: nightly job calls
  python3 aegis/skills/premarket-analysis/tools/emit_packets.py \
      --export aegis/output/aqe_daily_export.json \
      --menus  aegis/skills/premarket-analysis/contracts/voice_menus.json \
      --pipeline aegis/skills/premarket-analysis/tools/pma_pipeline.py \
      --outdir aegis/output/voice_packets --date <SGT date>
then commits aegis/output/ in the same commit as the export itself.
"""
import argparse, datetime, glob, hashlib, json, os, shutil, subprocess, sys, tempfile

R3_FORBIDDEN = (b"qs_market",)

# Chart-pattern lens fields (PM ruling 2026-09-05) -- checked as EXACT column
# names in a TSV header, never a raw substring: "pattern" alone is a
# substring of the legitimate field "elder_pattern", so a naive byte-scan
# would false-positive on every seat packet that carries it.
PATTERN_FIELDS_FORBIDDEN = {
    "pattern", "pattern_direction", "pattern_stage", "pattern_trigger",
    "pattern_invalidation", "pattern_days", "pattern_fit", "pattern_start",
    "pattern_alt", "pattern_w", "pattern_w_dir", "pattern_w_stage",
    "pattern_w_trigger",
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--export", required=True, help="aqe_daily_export.json (already written by the nightly job)")
    p.add_argument("--menus", required=True, help="contracts/voice_menus.json (slicing contract)")
    p.add_argument("--pipeline", required=True, help="path to pma_pipeline.py (the ONE slicer)")
    p.add_argument("--outdir", required=True, help="e.g. aegis/output/voice_packets")
    p.add_argument("--date", required=True, help="run date (SGT calendar date)")
    a = p.parse_args()

    for f in (a.export, a.menus, a.pipeline):
        if not os.path.exists(f):
            print(f"FATAL: input missing: {f}", file=sys.stderr)
            return 2

    with tempfile.TemporaryDirectory() as td:
        cs = os.path.join(td, "candidate_set.json")
        pk = os.path.join(td, "packets")
        run([sys.executable, a.pipeline, "trim", "--export", a.export, "--date", a.date, "--out", cs])
        run([sys.executable, a.pipeline, "packets", "--candidates", cs, "--export", a.export,
             "--menus", a.menus, "--date", a.date, "--outdir", pk])

        # Second lock, independent of pma_pipeline.py's own build-time checks:
        # R3 (qs_market) as a raw byte-scan -- that string never legitimately
        # appears in a seat packet, substring or not. Chart-pattern fields
        # (PM ruling 2026-09-05) as an EXACT column-name check against each
        # TSV's own header row, since "pattern" is a substring of the
        # legitimate field "elder_pattern".
        breaches = []
        for path in sorted(glob.glob(os.path.join(pk, "*"))):
            if os.path.basename(path).startswith(("crown", "druck")):
                continue  # macro packets are allowed macro fields; R3 governs SEAT packets
            with open(path, "rb") as f:
                blob = f.read()
            for pat in R3_FORBIDDEN:
                if pat in blob:
                    breaches.append(f"{os.path.basename(path)}: contains {pat.decode()}")
            if path.endswith(".tsv"):
                header = blob.decode("utf-8", "replace").splitlines()[0] if blob else ""
                cols = set(header.split("\t"))
                pat_breach = cols & PATTERN_FIELDS_FORBIDDEN
                if pat_breach:
                    breaches.append(f"{os.path.basename(path)}: pattern field(s) {sorted(pat_breach)}")
        if breaches:
            print("FATAL R3 BREACH — refusing to stamp:", *breaches, sep="\n  ", file=sys.stderr)
            return 1

        # Publish atomically: clear-and-replace outdir, then stamp.
        if os.path.isdir(a.outdir):
            shutil.rmtree(a.outdir)
        os.makedirs(a.outdir)
        shutil.copy2(cs, os.path.join(a.outdir, "candidate_set.json"))
        for path in sorted(glob.glob(os.path.join(pk, "*"))):
            shutil.copy2(path, os.path.join(a.outdir, os.path.basename(path)))

        files = {}
        for path in sorted(glob.glob(os.path.join(a.outdir, "*"))):
            name = os.path.basename(path)
            if name == "packet_stamp.json":
                continue
            files[name] = sha256_file(path)

        stamp = {
            "stamp_version": 1,
            "date": a.date,
            "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "export_sha256": sha256_file(a.export),
            "menus_sha256": sha256_file(a.menus),
            "files": files,
            "r3_scan": "clean",
            "note": ("Round-1 seat packets pre-sliced by the nightly AQE job (v5 ruling #4). "
                     "Spawn-time inputs only — consumed once, never read downstream. "
                     "PREPARE must verify every hash here AND menus_sha256 against the current "
                     "menus file; on any mismatch, slice locally from the canonical export and "
                     "declare the degradation."),
        }
        with open(os.path.join(a.outdir, "packet_stamp.json"), "w") as f:
            json.dump(stamp, f, indent=1, sort_keys=True)

    print(f"emitted {len(files)} files to {a.outdir}, stamped "
          f"(export {stamp['export_sha256'][:12]}…, menus {stamp['menus_sha256'][:12]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
