#!/usr/bin/env python3
"""The REPORT step's one command (PM 2026-11-04: promote the v3 Cards, with a safety net). It runs the renderer that RUN.yaml
parameters.cards_renderer names (v3 = pma_cards_v3.py, v2 = pma_cards.py render) and NEVER leaves the PM without a page and NEVER falls
back silently:

  v3 chosen -> render to a temp file -> the plain-words gate (daily-check/check.py: no raw field name or token in any text node, the same
  gate the v2 page passes) -> if the renderer errors OR the gate FAILS, the v2 renderer publishes instead, the reason is printed with the
  word CARDS FALLBACK, appended to run_notes.md, and written to cards_renderer.json for the DONE push. If v2 also fails the command
  exits non-zero (loud). Exit 0 only when a page was written.

Usage (run from the run dir):
  pma_cards_publish.py --date 2026-11-05 [--run-dir .] [--refresh-dir <repo>/aegis/output] [--out pma_cards_<date>.html]
"""
import argparse, datetime, importlib.util, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
V3_NEEDS = ["cards_text.json", "consensus.json", "committee_position.json", "pma_levels.json", "cards.json", "decision.json", "phase4.json",
            "aqe_daily_export.json", "aqe_valen_dashboard.json", "aqe_crown_macro.json", "aqe_last_run.json", "scorecard.md"]


def param(name, default):
    for rel in ("..", "../skills/pma", "../../pma", "../../../skills/pma", "../../skills/pma", "../pma"):
        p = os.path.join(HERE, rel, "RUN.yaml")
        if os.path.exists(p):
            m = re.search(rf"^\s*{re.escape(name)}:\s*([A-Za-z0-9_\-]+)", open(p, encoding="utf-8").read(), re.M)
            if m:
                return m.group(1)
    return default


def load_check():
    for rel in ("../../daily-check/check.py", "../../../skills/daily-check/check.py", "../daily-check/check.py"):
        p = os.path.abspath(os.path.join(HERE, rel))
        if os.path.exists(p):
            spec = importlib.util.spec_from_file_location("daily_check_for_cards", p)
            m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            return m
    return None


def note(run_dir, line):
    print(line, flush=True)
    try:
        with open(os.path.join(run_dir, "run_notes.md"), "a", encoding="utf-8") as f:
            f.write("\n" + line + "\n")
    except OSError:
        pass


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=isinstance(cmd, str))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True); ap.add_argument("--run-dir", default=".")
    ap.add_argument("--refresh-dir", default=None); ap.add_argument("--out", default=None)
    ap.add_argument("--renderer", default=None, help="override parameters.cards_renderer (v2|v3)")
    ap.add_argument("--v2-command", default=None, help="test hook: replaces the v2 command (a shell command that writes {out})")
    a = ap.parse_args()
    run_dir = os.path.abspath(a.run_dir)
    out = os.path.abspath(a.out or os.path.join(run_dir, f"pma_cards_{a.date}.html"))
    which = (a.renderer or os.environ.get("AEGIS_CARDS_RENDERER") or param("cards_renderer", "v2")).lower()
    rec = {"date": a.date, "renderer_chosen": which, "renderer_published": None, "fallback": False, "reason": None, "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    reason = None
    if which == "v3":
        missing = [f for f in V3_NEEDS if not os.path.exists(os.path.join(run_dir, f))]
        tmp = out + ".v3.tmp"
        if missing:
            reason = f"the run dir lacks {', '.join(missing)}"
        else:
            cmd = [sys.executable, os.path.join(HERE, "pma_cards_v3.py"), "--run-dir", run_dir, "--out", tmp]
            if a.refresh_dir:
                cmd += ["--refresh-dir", a.refresh_dir]
            rc, log = run(cmd, run_dir)
            if rc != 0:
                reason = "pma_cards_v3.py exited %d: %s" % (rc, " ".join(log.strip().splitlines()[-2:])[:300])
            else:
                ck = load_check()
                if ck is None:
                    reason = "the plain-words gate (daily-check/check.py) could not be loaded"
                else:
                    fails, _ = ck.check_cards_html(tmp)
                    tf, _n = ck.check_cards_text(os.path.join(run_dir, "cards_text.json"))
                    fails = list(fails) + list(tf)
                    if fails:
                        reason = "the plain-words gate FAILED on the v3 page or its words file: " + "; ".join(fails)[:300]
        if reason is None:
            for ln in (log or "").splitlines():
                if ln.startswith("CARDS LINES FALLBACK") or ln.startswith("cards lines:") and "file absent" in ln:
                    note(run_dir, ln.replace("cards lines:", "CARDS LINES:", 1))          # PM 2026-11-05: a writer line that broke the gate is named, never silent
            shutil.move(tmp, out)
            rec["renderer_published"] = "v3"
            print(f"cards: v3 page published -> {out}")
        else:
            if os.path.exists(tmp):
                os.replace(tmp, out + ".v3.rejected.html")            # kept for the post-mortem, never published
            rec["fallback"], rec["reason"] = True, reason
            note(run_dir, f"CARDS FALLBACK: the v3 page was NOT published ({reason}). The v2 page was published instead.")
            which = "v2"
    if which == "v2":
        if a.v2_command:
            rc, log = run(a.v2_command.replace("{out}", out), run_dir)
        else:
            cmd = [sys.executable, os.path.join(HERE, "pma_cards.py"), "render", "--text", "cards_text.json", "--position", "committee_position.json", "--out", out]
            rc, log = run(cmd, run_dir)
        if rc != 0 or not os.path.exists(out):
            rec["renderer_published"] = None
            json.dump(rec, open(os.path.join(run_dir, "cards_renderer.json"), "w"), indent=1)
            note(run_dir, f"CARDS FAILED: no page was written (v2 exited {rc}): " + " ".join(log.strip().splitlines()[-3:])[:300])
            sys.exit(2)
        rec["renderer_published"] = "v2"
        print(f"cards: v2 page published -> {out}")
    json.dump(rec, open(os.path.join(run_dir, "cards_renderer.json"), "w"), indent=1)
    sys.exit(0)


if __name__ == "__main__":
    main()
