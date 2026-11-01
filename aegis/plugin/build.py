#!/usr/bin/env python3
"""Zip the plugin trees under aegis/plugin/ into installable .plugin files.

ONE CODE TREE (PM 2026-10-30): the trees HERE are the editable originals. This
script no longer copies aegis/skills/premarket-analysis in first -- that
direction is reversed: sync_runtime.py generates the runtime copies FROM the
plugin tree. Run sync_runtime.py before building so the drift test is green.

Output: aegis/plugin/dist/<plugin>.plugin (dist/ is gitignored).
"""
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGINS = ("aegis-core", "aegis-voices", "aegis-daily", "aegis-stops", "aegis-live")
SKIP_DIRS = {"__pycache__", ".pytest_cache", ".in_use", "dist"}
SKIP_FILES = {".DS_Store"}

rc = subprocess.call([sys.executable, os.path.join(HERE, "sync_runtime.py"), "--check"])
if rc != 0:
    sys.exit("runtime copies drift from the plugin tree -- run sync_runtime.py first")

os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
for plug in PLUGINS:
    base = os.path.join(HERE, plug)
    if not os.path.isdir(base):
        print("skip (missing):", plug)
        continue
    out = os.path.join(HERE, "dist", plug + ".plugin")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fn in os.walk(base):
            dn[:] = [x for x in dn if x not in SKIP_DIRS]
            for f in fn:
                if f.endswith((".pyc", ".bak")) or f in SKIP_FILES:
                    continue
                full = os.path.join(dp, f)
                z.write(full, os.path.relpath(full, base))
    print(out, os.path.getsize(out), "bytes")
