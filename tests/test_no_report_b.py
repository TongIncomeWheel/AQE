"""PM 2026-11-17 ("List B should be gone"): report B is removed completely. No B code path, module, command or branch remains in the committee tooling.
Run dirs under aegis/output/pma/run/*-B and old ledger rows stay as history only (this test never reads them)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PMA = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "pma"
TOOLS = PMA / "tools"
CHECK = ROOT / "aegis" / "plugin" / "aegis-core" / "skills" / "daily-check" / "check.py"

BANNED = [r"sweep_B", r"reuse_a\b", r"reuse-a", r"report_b", r"[Rr]eport B", r"REPORT B", r"== \"B\"", r"\(\"B\", \"C\"\)", r"\[\"B\", \"C\"\]", r"\"A\", \"B\", \"C\"",
          r"--report B", r"AEGIS_REPORT=B", r"<\|B\|C>", r"-B/-C", r"\"B\": \"Report B"]
ALLOW = re.compile(r"removed|REMOVED|no report B|is gone|history only", re.I)


def _files():
    fs = [p for p in TOOLS.glob("*.py")] + [CHECK, PMA / "RUN.yaml", PMA / "SKILL.md", PMA / "contracts" / "brief_sections.json",
                                            ROOT / "src" / "pipeline" / "committee_topup.py", ROOT / "src" / "pipeline" / "committee_data.py",
                                            ROOT / ".github" / "workflows" / "committee-topup.yml", ROOT / "docs" / "AQE_STANDARD_SCAN.md"]
    return [f for f in fs if f.exists()]


def test_no_report_b_text_or_branch_remains_in_the_committee_tooling():
    bad = []
    for f in _files():
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
            if ALLOW.search(line):
                continue
            for pat in BANNED:
                if re.search(pat, line):
                    bad.append(f"{f.relative_to(ROOT)}:{n}: {line.strip()[:110]}")
                    break
    assert not bad, "\n".join(bad[:15])


def _run(args, env_extra=None):
    env = dict(os.environ); env.pop("AEGIS_REPORT", None); env.update(env_extra or {})
    return subprocess.run([sys.executable] + [str(a) for a in args], capture_output=True, text=True, env=env)


def test_report_b_is_refused_everywhere_it_used_to_be_accepted(tmp_path):
    for tool in ("registrar.py", "pma_pipeline.py"):
        r = _run([TOOLS / tool, "--help"], {"AEGIS_REPORT": "B"})
        assert r.returncode != 0 and "report B was removed" in r.stderr + r.stdout, tool
    r = _run([TOOLS / "registrar.py", "--manifest", tmp_path / "m.json", "init", "--date", "2026-11-17", "--report", "B"], {"AEGIS_REPORT": "A"})
    assert r.returncode != 0 and not (tmp_path / "m.json").exists()
    for gone in ("reuse-a", "cset", "quant-screen"):
        r = _run([TOOLS / "pma_pipeline.py", gone], {"AEGIS_REPORT": "A"})
        assert r.returncode != 0 and gone in r.stdout + r.stderr, gone
    r = _run([TOOLS / "pma_cards_report.py", "--report", "B", "--date", "2026-11-17"])
    assert r.returncode != 0


def test_the_brief_registry_and_report_compare_carry_only_a_and_c():
    reg = json.loads((PMA / "contracts" / "brief_sections.json").read_text(encoding="utf-8"))
    assert [m["id"] for m in reg["modules"]] == ["indicators_C"]
    sys.path.insert(0, str(TOOLS))
    import report_compare as RC
    assert RC.REPORTS == ("A", "C") and "B" not in RC.DISPLAY and "B" not in RC.ORDER
    import importlib
    import registrar as REG
    assert REG.SHORTLIST_CAP == 6
    importlib.reload(RC)
