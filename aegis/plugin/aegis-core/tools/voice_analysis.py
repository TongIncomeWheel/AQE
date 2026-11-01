#!/usr/bin/env python3
"""voice_analysis.py — render the human-readable reasoning artefact per voice.

CRITICAL PROPERTY: this file is rendered BY THE ORCHESTRATOR FROM THE RETURNED JSON.
It is never written by the voice itself. A self-reported narrative is a story the model
tells about its own work; this is a projection of the contract it was actually held to.
The two diverge exactly when it matters, which is why the rendering direction is fixed.

    python3 tools/voice_analysis.py render 2026-08-04            # all voices
    python3 tools/voice_analysis.py render 2026-08-04 --voice wyckoff

Writes data/sod/<DATE>/voice_analysis/<voice>.md
"""
import argparse
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MARK = {"pass": "PASS", "fail": "FAIL", "partial": "PART", "no_data": "----"}


def _canon_text(idx_voice, lock_cache, vkey, cid):
    if vkey not in lock_cache:
        p = os.path.join(ROOT, "canon", vkey, "canon.lock.yaml")
        if os.path.isfile(p):
            import yaml
            lock_cache[vkey] = {p_["id"]: p_ for p_ in yaml.safe_load(open(p))["principles"]}
        else:
            lock_cache[vkey] = {}
    pr = lock_cache[vkey].get(cid)
    if not pr:
        return None
    cites = pr.get("cite") or []
    tag = " · ".join(f"{c['code']} p.{c['page']}" for c in cites) or "UNSOURCED"
    return f"{pr['text']}  [{tag}]"


def render(date, only=None):
    nd = os.path.join(ROOT, "data", "sod", date, "nominations")
    if not os.path.isdir(nd):
        raise SystemExit(f"no nominations for {date}")
    out = os.path.join(ROOT, "data", "sod", date, "voice_analysis")
    os.makedirs(out, exist_ok=True)
    idxp = os.path.join(ROOT, "contracts", "canon_index.json")
    idx = json.load(open(idxp)) if os.path.isfile(idxp) else {"voices": {}}
    lock_cache = {}
    n = 0

    for f in sorted(glob.glob(os.path.join(nd, "*.json"))):
        doc = json.load(open(f))
        vkey = doc.get("voice") or os.path.basename(f)[:-5]
        if only and vkey != only:
            continue
        vi = (idx.get("voices") or {}).get(vkey, {})
        L = []
        L.append(f"# {vkey.upper()} — {date}")
        L.append("")
        if vi.get("grounded"):
            L.append(f"Grounded: {', '.join(vi.get('sources') or [])} · "
                     f"{len(vi.get('principles') or [])} principles · signed {vi.get('pm_signed')}")
        else:
            L.append("**UNGROUNDED** — this voice has no locked canon. Its reasoning below is its "
                     "own framework, not a sourced text. Weigh accordingly.")
        L.append("")
        L.append(f"Nominated {len(doc.get('nominations') or [])}"
                 + (f" · shortfall: {doc['shortfall_reason']}" if doc.get("shortfall_reason") else ""))
        L.append("")

        for nom in doc.get("nominations") or []:
            L.append(f"## {nom['ticker']} — conviction {nom.get('conviction')}")
            L.append("")
            L.append(f"> {nom.get('reason','')}")
            L.append("")
            tr = nom.get("checklist_trace") or []
            if not tr:
                L.append("*No checklist trace returned. This nomination is an assertion — "
                         "there is no record that the checklist was walked.*")
                L.append("")
                continue
            L.append("| step | verdict | what it saw | fields | canon |")
            L.append("|---|---|---|---|---|")
            for t in tr:
                fl = ", ".join(f"`{x}`" for x in (t.get("fields") or [])) or "—"
                cr = ", ".join(t.get("canon_ref") or [])
                L.append(f"| {t.get('step')} | {MARK.get(t.get('verdict'), '?')} | "
                         f"{t.get('observed','')} | {fl} | {cr} |")
            L.append("")
            refs = []
            for t in tr:
                for cid in (t.get("canon_ref") or []):
                    if cid not in refs:
                        refs.append(cid)
            shown = [(cid, _canon_text(vi, lock_cache, vkey, cid)) for cid in refs]
            shown = [(c, t) for c, t in shown if t]
            if shown:
                L.append("The canon this rested on:")
                L.append("")
                for cid, txt in shown:
                    L.append(f"- **{cid}** — {txt}")
                L.append("")
            fv = nom.get("field_values") or {}
            if fv:
                L.append("Stamped values: " + " · ".join(f"`{k}` = {v}" for k, v in fv.items()))
                L.append("")

        held = doc.get("held_review") or []
        if held:
            L.append("## Held book")
            L.append("")
            for h in held:
                L.append(f"- **{h['ticker']}** — {h.get('verdict')} — {h.get('line','')}")
            L.append("")
        gaps = doc.get("data_gaps") or []
        if gaps:
            L.append("## Declared data gaps")
            L.append("")
            L.append("The voice hit these holes and said so rather than working around them (D-55).")
            L.append("")
            for g in gaps:
                L.append(f"- `{g.get('field')}` — {g.get('impact','')}")
            L.append("")

        open(os.path.join(out, f"{vkey}.md"), "w").write("\n".join(L) + "\n")
        n += 1
    print(f"rendered {n} voice analysis file(s) → data/sod/{date}/voice_analysis/")
    return n


def main():
    ap = argparse.ArgumentParser(prog="voice_analysis.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["render"])
    ap.add_argument("date")
    ap.add_argument("--voice")
    a = ap.parse_args()
    render(a.date, a.voice)


if __name__ == "__main__":
    main()
