#!/usr/bin/env python3
"""Package the kernel into a Claude plugin. GENERATED OUTPUT — never hand-edit adapters.
Reads: charter/ process/ voices/ tools/catalog.md config/
Emits: dist/claude-plugin/aegis-v4/ with .claude-plugin/plugin.json + skills/ (one skill per process,
rulebook values inlined at build time so skills neither restate rules from memory nor dereference at runtime).
"""
import json, os, shutil, yaml, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "claude-plugin", "aegis-v4")
RB = yaml.safe_load(open(os.path.join(ROOT, "charter", "rulebook.yaml")))
_P = yaml.safe_load(open(os.path.join(ROOT, "charter", "parameters.yaml")))
def _merge(a, b):
    for k, v in b.items():
        if k in a and isinstance(a[k], dict) and isinstance(v, dict): _merge(a[k], v)
        else: a[k] = v
    return a
RB = _merge(dict(_P), RB)  # law wins on collision; params fill numbers

def rb_lookup(path):
    node = RB
    for part in path.split("."):
        node = node[part]
    return node

def inline_rb(text):
    """Replace RB:<dotted.path> citations with '<value> [RB:<path>]' so the number travels WITH its source key."""
    def sub(m):
        try:
            val = rb_lookup(m.group(1))
            if isinstance(val, (dict, list)):
                return m.group(0)  # structured rules stay as citations; agent reads rulebook.yaml
            return f"{val} [RB:{m.group(1)}]"
        except Exception:
            return m.group(0)
    return re.sub(r"RB:([a-z0-9_.]+)", sub, text)

def main():
    shutil.rmtree(DIST, ignore_errors=True)
    os.makedirs(os.path.join(DIST, ".claude-plugin"), exist_ok=True)
    json.dump({"name": "aegis-v4", "version": RB["meta"]["version"],
               "description": "Aegis v4 — generated from the kernel; do not hand-edit. Rulebook " + RB["meta"]["version"]},
              open(os.path.join(DIST, ".claude-plugin", "plugin.json"), "w"), indent=1)
    src = os.path.join(ROOT, "skills")
    for name in sorted(os.listdir(src)):
        skill_md = os.path.join(src, name, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        sk = os.path.join(DIST, "skills", name)
        os.makedirs(sk, exist_ok=True)
        open(os.path.join(sk, "SKILL.md"), "w").write(inline_rb(open(skill_md).read()))
    shutil.copy(os.path.join(ROOT, "charter", "commands.md"), os.path.join(DIST, "skills", "premarket", "commands.md"))
    print(f"built {DIST}")

if __name__ == "__main__":
    main()
