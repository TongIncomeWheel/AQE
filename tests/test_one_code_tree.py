"""One code tree (BUILD_PLAN Phase 1, PM 2026-10-30).

aegis/plugin/ holds the live Aegis plugins and is the truth. The nightly run
reads a handful of plugin files at fixed runtime paths (pma_pipeline.py, the
voice menus, every canon.lock.yaml); those are GENERATED copies. Before this
test existed AQE ran plugin 1.24.1 / voices 1.8.0 while the live plugin was
1.31.0 / 1.9.0 and nobody noticed. A drift here is a real-money data bug: the
packets every seat reads are sliced by the stale copy.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "aegis" / "plugin" / "sync_runtime.py"


def _load_sync():
    spec = importlib.util.spec_from_file_location("sync_runtime", SYNC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_generated_runtime_copies_match_the_plugin_tree():
    probs = _load_sync().check()
    assert probs == [], "\n".join(probs)


def test_the_pairs_cover_what_the_nightly_run_actually_reads():
    """voice_packets.py imports these two by path; deploy-hf.yml re-adds
    pma_pipeline.py and aegis/canon into the HF mirror. If either path moves,
    this test must move with it -- and so must deploy-hf.yml."""
    gen = {p[1].relative_to(ROOT).as_posix() for p in _load_sync().PAIRS}
    assert "aegis/skills/premarket-analysis/tools/pma_pipeline.py" in gen
    assert "aegis/skills/premarket-analysis/contracts/voice_menus.json" in gen
    assert any(g.startswith("aegis/canon/") and g.endswith("canon.lock.yaml") for g in gen)
    vp = (ROOT / "src/pipeline/voice_packets.py").read_text(encoding="utf-8")
    assert '"premarket-analysis"' in vp and "pma_pipeline.py" in vp
    wf = (ROOT / ".github/workflows/deploy-hf.yml").read_text(encoding="utf-8")
    assert "aegis/skills/premarket-analysis/tools/pma_pipeline.py" in wf


def test_plugin_versions_are_the_live_ones_not_the_stale_vendored_pair():
    man = json.loads((ROOT / "aegis/skills/premarket-analysis/GENERATED.json").read_text(encoding="utf-8"))
    v = man["plugin_versions"]
    assert tuple(int(x) for x in v["aegis-core"].split(".")) >= (1, 31, 0), v
    assert tuple(int(x) for x in v["aegis-voices"].split(".")) >= (1, 9, 0), v


def test_no_stray_caches_shipped_in_the_plugin_tree():
    """Checks TRACKED files only: running the plugin self-test writes
    __pycache__ locally, which aegis/.gitignore keeps out of the commit."""
    import subprocess
    out = subprocess.run(["git", "ls-files", "aegis/plugin"], cwd=ROOT,
                         capture_output=True, text=True, check=True).stdout.split()
    bad = [f for f in out if f.endswith((".pyc", ".bak"))
           or any(seg in f.split("/") for seg in (".in_use", ".pytest_cache", "__pycache__"))]
    assert bad == [], bad
