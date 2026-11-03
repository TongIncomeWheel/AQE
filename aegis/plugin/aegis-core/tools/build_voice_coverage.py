#!/usr/bin/env python3
"""build_voice_coverage.py -- regenerate the machine-readable half of contracts/voice_coverage.json.

The per-voice data-coverage check (daily-check/check.py coverage, PM 2026-11-03) compares what each voice's
CHARTER reads against what its packet serves. "What the charter reads" is the `fields:` list on every recogniser
in aegis-voices/canon/<voice>/canon.lock.yaml. check.py is stdlib-only and cannot read that YAML, so this script
extracts it into contracts/voice_coverage.json["required_fields"]. The hand-reviewed sections (`conditional_blank`,
`known_gaps`) are kept as they are; a test (tests/test_voice_coverage.py) fails if the extracted half drifts from
the canon locks, so a changed canon can never leave the check reading a stale requirement list.

  python3 tools/build_voice_coverage.py            # rewrite required_fields in place
  python3 tools/build_voice_coverage.py --check    # exit 1 if it would change (drift)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = os.path.dirname(HERE)
CONTRACT = os.path.join(CORE, "contracts", "voice_coverage.json")
CANON = os.path.abspath(os.path.join(CORE, "..", "aegis-voices", "canon"))
DECIDERS = ["oneil", "minervini", "livermore", "elder-lens", "seow", "raschke", "wyckoff"]


def required_fields(voice):
    import yaml
    lock = yaml.safe_load(open(os.path.join(CANON, voice, "canon.lock.yaml"), encoding="utf-8"))
    out = set()

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("fields"), list):
                out.update(str(x) for x in o["fields"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(lock)
    return sorted(out)


def declared_unavailable(voice):
    """Recognisers whose own `if:` begins NOT_AVAILABLE: - the canon says the data to run them does not exist.
    They carry an empty `fields:` list, which is why a fields-only check could not see them (3 Nov: elder-lens
    R5 "fitted channel"). -> [{"id", "needs"}], needs = the `if:` text after the marker."""
    import yaml
    lock = yaml.safe_load(open(os.path.join(CANON, voice, "canon.lock.yaml"), encoding="utf-8"))
    out = []

    def walk(o):
        if isinstance(o, dict):
            cond = str(o.get("if", ""))
            if "id" in o and cond.startswith("NOT_AVAILABLE"):
                out.append({"id": str(o["id"]), "needs": " ".join(cond.split(":", 1)[1].split())[:200]})
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(lock)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    cur = json.load(open(CONTRACT, encoding="utf-8")) if os.path.exists(CONTRACT) else {}
    new = dict(cur)
    new["required_fields"] = {v: required_fields(v) for v in DECIDERS}
    new["declared_unavailable"] = {v: declared_unavailable(v) for v in DECIDERS if declared_unavailable(v)}
    if a.check:
        if (cur.get("required_fields") != new["required_fields"]
                or cur.get("declared_unavailable") != new["declared_unavailable"]):
            print("voice_coverage.json required_fields have DRIFTED from the canon locks -- run build_voice_coverage.py")
            return 1
        print("voice_coverage.json: required_fields match the canon locks")
        return 0
    json.dump(new, open(CONTRACT, "w", encoding="utf-8"), indent=1, sort_keys=False)
    print(f"wrote {CONTRACT}: " + ", ".join(f"{v} {len(f)}" for v, f in new["required_fields"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
