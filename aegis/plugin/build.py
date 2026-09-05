#!/usr/bin/env python3
"""Zip the two plugin trees into installable .plugin files. Copies aegis/skills/premarket-analysis into
aegis-core/skills/pma first so the editable original wins. Output: aegis/plugin/dist/*.plugin"""
import os, shutil, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
src = os.path.join(ROOT, "skills", "premarket-analysis"); dst = os.path.join(HERE, "aegis-core", "skills", "pma")
for name in ("SKILL.md",):
    shutil.copy(os.path.join(src, name), os.path.join(dst, name))
for sub in ("tools", "contracts", "stages"):
    s, d = os.path.join(src, sub), os.path.join(dst, sub)
    if os.path.isdir(s):
        if os.path.isdir(d): shutil.rmtree(d)
        shutil.copytree(s, d, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
shutil.copy(os.path.join(src, "agents", "brief-writer.md"), os.path.join(HERE, "aegis-core", "agents", "brief-writer.md"))
for t in ("preflight.py", "aqe_coverage.py"):
    p = os.path.join(ROOT, "tools", t)
    if os.path.exists(p): shutil.copy(p, os.path.join(HERE, "aegis-core", "tools", t))
os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
for plug in ("aegis-core", "aegis-voices"):
    out = os.path.join(HERE, "dist", plug + ".plugin"); base = os.path.join(HERE, plug)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fn in os.walk(base):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for f in fn:
                if f.endswith(".pyc") or f == ".DS_Store": continue
                full = os.path.join(dp, f); z.write(full, os.path.relpath(full, base))
    print(out, os.path.getsize(out), "bytes")
