#!/usr/bin/env python3
"""render.py — from binding/<voice>.binding.yaml + glossary.lock.json produce:
  cards/<voice>.glossary.md   the seat's reading card: every field it is served, with definition,
                              formula, direction, null semantics and traps — engine-sourced
  voice_menus.v6.json         menus regenerated FROM the bindings (canon-bound fields only)
  menu_diff.md                what each seat loses/gains vs voice_menus.json (1.13.0)
"""
import json, glob, os, hashlib, yaml
ROOT = os.path.dirname(os.path.abspath(__file__))
_g = [p for p in (f"{ROOT}/glossary.lock.json", f"{ROOT}/glossary.lock.min.json") if os.path.exists(p)][0]
G = json.load(open(_g))["fields"]
REPO = os.environ.get("AQE_REPO") or os.path.abspath(f"{ROOT}/../../..")
_m = [p for p in ("/home/claude/build/aegis-core/skills/pma/contracts/voice_menus.json", f"{REPO}/aegis/contracts/voice_menus.json") if os.path.exists(p)]
OLD = json.load(open(_m[0])) if _m else {}
COMMON = ["ticker", "entry", "source", "held", "atr_14d", "days_to_earnings"]  # identity + risk unit, every seat
os.makedirs(f"{ROOT}/cards", exist_ok=True)
menus = {"~~CONFIG_NOTE~~": "v6 DATA CONTRACT (2026-09-09): menus are GENERATED from aegis/canon/<voice>/binding.yaml — a field is on a menu only if a PM-signed canon rule reads it (fit EXACT or PROXY) or it is in the COMMON identity block. Hand edits are overwritten by render.py. Glossary sha stamped below."}
diff = ["# Menu diff — voice_menus.json (1.13.0) -> v6 generated\n"]
BRACKET_CORE = ["bracket.valid", "bracket.invalid_reason", "bracket.stop", "bracket.stop_type", "bracket.risk_pct", "bracket.rr", "bracket.rr_tp1", "bracket.targets"]
NEVER_SERVE = {"lens.extension"}  # constant null by PM ruling (lens_consensus.py); serving it invites a fabricated read
def members(obj):
    if obj == "bracket.*": return BRACKET_CORE
    stem = obj[:-2]
    return sorted(p for p in G if p.startswith(stem) and not p.endswith("*") and p not in NEVER_SERVE)
for bf in sorted(glob.glob(f"{ROOT}/binding/*.binding.yaml")):
    b = yaml.safe_load(open(bf)); v = b["voice"]
    if v in ("crown",): continue
    served = []
    rule_of = {}
    for r in b["bindings"]:
        p = r["export_path"]
        if not p or r["fit"] not in ("EXACT", "PROXY"): continue
        ps = members(p) if p.endswith("*") else [p]
        for q in ps:
            if q.startswith(("held_positions", "qs")): continue
            served.append(q); rule_of.setdefault(q, []).extend(x["rule"] for x in r["rules"])
            if r["fit"] == "PROXY": rule_of[q].append(f"PROXY:{r['loss']}")
    menu = [c for c in COMMON if c in G] + [p for p in sorted(set(served)) if p not in COMMON and p not in NEVER_SERVE]
    menus[v] = menu
    old = set(OLD.get(v) or [])
    lost, gained = sorted(old - set(menu)), sorted(set(menu) - old)
    diff.append(f"\n## {v}: {len(old)} -> {len(menu)}  (removed {len(lost)}, added {len(gained)})\n")
    if lost: diff.append("removed (no canon rule reads them): " + ", ".join(lost) + "\n")
    if gained: diff.append("added (canon rule reads them, never served): " + ", ".join(gained) + "\n")
    # reading card
    L = [f"# {v} — reading card (v6 data contract, generated 2026-09-09)\n",
         f"canon: {b['pm_signed']} signed, diff_sha {str(b['canon_diff_sha'])[:12]} · glossary sha {b['glossary_sha']}\n",
         "Every field below is the ONLY data this seat is served. Definition, direction and null meaning come from the engine source line cited; if your reading of a number contradicts this card, the card is right and your reading is drift.\n"]
    for p in menu:
        e = G.get(p)
        if not e: L.append(f"\n## {p}\nNO GLOSSARY ENTRY — must not be served\n"); continue
        rules = sorted({str(x) for x in rule_of.get(p, []) if not str(x).startswith('PROXY')})
        prox = [x[6:] for x in rule_of.get(p, []) if str(x).startswith('PROXY')]
        L.append(f"\n## {p}  [{e['units']}, {e['granularity']}]  rules: {', '.join(rules) or 'common block'}\n")
        L.append(f"- IS: {e['definition']}\n- FORMULA: {e['formula']}  ({e['engine_source']})\n- DIRECTION: {e['direction']}\n- NULL MEANS: {e['null_means']}\n")
        if e.get("enum"): L.append(f"- VALUES: {', '.join(map(str, e['enum']))}\n")
        if e.get("known_traps") and e["known_traps"].lower() != "none found": L.append(f"- TRAP: {e['known_traps']}\n")
        if prox: L.append(f"- PROXY FOR YOUR RULE: {prox[0]}\n")
    open(f"{ROOT}/cards/{v}.glossary.md", "w").write("".join(L))
menus["_glossary_sha256"] = hashlib.sha256(open(_g, "rb").read()).hexdigest()
json.dump(menus, open(f"{ROOT}/voice_menus.v6.json", "w"), indent=1)
open(f"{ROOT}/menu_diff.md", "w").write("".join(diff))
for v in menus:
    if v.startswith(("~~", "_")): continue
    print(f"{v:14s} menu={len(menus[v]):3d}  card={os.path.getsize(f'{ROOT}/cards/{v}.glossary.md')//1024}KB")
