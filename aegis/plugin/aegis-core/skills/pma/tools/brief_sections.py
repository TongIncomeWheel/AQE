#!/usr/bin/env python3
"""brief_sections.py -- the daily brief as a CORE plus self-contained code-built MODULES (PM 2026-11-10).

A module has its own inputs, its own on/off flag (contracts/brief_sections.json, overridable per run by AEGIS_BRIEF_MODULES) and its own gate rules.
A failed or missing module shows ONE loud degraded line in the brief and never blocks anything else; the core gate rules never see a module's text
(strip_modules), and a module's own rules only run when it rendered ok.

    brief_sections.py assemble --brief pma_brief_<date>.md --run-dir . --date <date> [--status brief_sections_status.json]
    brief_sections.py check    --brief pma_brief_<date>.md --run-dir . --date <date>
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REG_PATH = os.path.join(HERE, "..", "contracts", "brief_sections.json")
BEGIN = re.compile(r"<!-- module:(\w+) status:(\w+) -->")
VERDICTS = ("ADVANCE", "HOLD-FOR-CONDITIONS")


def load_registry(path=None):
    return json.load(open(path or REG_PATH))


def enabled(mod, env=None):
    """The registry flag, overridable per run: AEGIS_BRIEF_MODULES='sweep_B,indicators_C' (an explicit list) or 'none'."""
    env = os.environ.get("AEGIS_BRIEF_MODULES") if env is None else env
    if env is None or env == "":
        return bool(mod.get("enabled", True))
    if env.strip().lower() == "none":
        return False
    return mod["id"] in {x.strip() for x in env.split(",")}


def _block_re(mid):
    return re.compile(rf"<!-- module:{mid} status:\w+ -->.*?<!-- /module:{mid} -->\n\n", re.S)


def strip_modules(text):
    """The CORE brief: every module block removed, so the core gate rules (verdict table first, QX2/QX3/QX4, Q9D, ...) never see module text."""
    return re.sub(r"<!-- module:(\w+) status:\w+ -->.*?<!-- /module:\1 -->\n\n", "", text, flags=re.S)


def module_blocks(text):
    """{id: (status, body)} for every module block present."""
    out = {}
    for m in BEGIN.finditer(text):
        mid = m.group(1)
        end = text.find(f"<!-- /module:{mid} -->", m.end())
        if end >= 0:
            out[mid] = (m.group(2), text[m.end():end].strip("\n"))
    return out


def _load(path):
    return json.load(open(path)) if os.path.exists(path) else None


def _run_dirs(run_dir, suffix):
    """A run dir 'aegis/output/pma/run/2026-11-10' has siblings '<date>-B' and '<date>-C' (the non-live report runs)."""
    base = os.path.abspath(run_dir).rstrip("/")
    return base + "-" + suffix


def _counts(cons):
    d = len(cons)
    adv = sum(1 for c in cons if c.get("verdict") == "ADVANCE")
    hold = sum(1 for c in cons if c.get("verdict") == "HOLD-FOR-CONDITIONS")
    return d, adv, hold, d - adv - hold


def _render_report_module(mod, run_dir, date):
    """Sections B and C share one shape: the report's own ADVANCE / HOLD names, a count line, 'also in A', never a trade row."""
    rdir = _run_dirs(run_dir, mod["run_dir_suffix"])
    cons = _load(os.path.join(rdir, "consensus.json"))
    if cons is None:
        raise FileNotFoundError(f"{os.path.basename(rdir)}/consensus.json not found: report {mod['run_dir_suffix']} has not run for {date}")
    a_cons = {c["ticker"]: c for c in (_load(os.path.join(run_dir, "consensus.json")) or [])}
    sets = _load(os.path.join(rdir, "seat_sets.json")) or {}
    passed_in = {}
    for seat, rows in ((sets.get("seats") or {}).items()):
        for r in rows:
            passed_in[r["ticker"]] = passed_in.get(r["ticker"], 0) + 1
    deliberated, adv, hold, passed = _counts(cons)
    reused = _load(os.path.join(rdir, "reused_from_a.json")) or {}
    reused_names = [t for t in (reused.get("tickers") or []) if t in a_cons]
    rows = [c for c in cons if c.get("verdict") in VERDICTS]
    rows.sort(key=lambda c: (c["verdict"] != "ADVANCE", -(c.get("conviction") or 0), c["ticker"]))
    word = {"ADVANCE": "Advance", "HOLD-FOR-CONDITIONS": "Hold for conditions"}
    L = [f"### {mod['anchor']} {mod['title']}", "",
         f"{deliberated + len(reused_names)} names deliberated ({deliberated} new, {len(reused_names)} reused from the main list): {adv} advance, {hold} hold for conditions, "
         f"{passed} passed. Scored only: no levels, not a trade row.", ""]
    if rows or reused_names:
        L += ["| Ticker | Verdict | Conviction | On the main list |", "|---|---|---|---|"]
        for c in rows:
            ina = a_cons.get(c["ticker"])
            L.append(f"| {c['ticker']} | {word[c['verdict']]} | {c.get('conviction') if c.get('conviction') is not None else 'n/a'} | "
                     f"{word.get(ina['verdict'], 'Passed') if ina else 'Not on the list'} |")
        for t in reused_names:
            v = a_cons[t]["verdict"]
            if v in VERDICTS and t not in {c["ticker"] for c in rows}:
                L.append(f"| {t} | {word[v]} (main list's verdict) | {a_cons[t].get('conviction') if a_cons[t].get('conviction') is not None else 'n/a'} | {word[v]} |")
    else:
        L.append("No name reached an advance or hold verdict.")
    return "\n".join(L)


RENDERERS = {"sweep_B": _render_report_module, "indicators_C": _render_report_module}


def render_all(run_dir, date, registry=None, env=None):
    """{id: {status, title, md|reason}} for every module. A module that raises is 'degraded'; one that is off is 'off'. Never raises."""
    reg = registry or load_registry()
    out = {}
    for mod in reg["modules"]:
        if not enabled(mod, env):
            out[mod["id"]] = {"status": "off", "title": mod["title"]}
            continue
        try:
            out[mod["id"]] = {"status": "ok", "title": mod["title"], "md": RENDERERS[mod["id"]](mod, run_dir, date)}
        except Exception as exc:  # noqa: BLE001 -- a module must never take the brief down
            out[mod["id"]] = {"status": "degraded", "title": mod["title"], "reason": str(exc)[:200] or type(exc).__name__}
    return out


def _wrap(mid, res, registry):
    title = res["title"]
    if res["status"] == "ok":
        body = res["md"]
    else:
        body = registry["degraded_line"].format(title=title, reason=res.get("reason", "failed"))
    return f"<!-- module:{mid} status:{res['status']} -->\n{body}\n<!-- /module:{mid} -->\n\n"


def assemble(brief, results, registry=None):
    """Insert every non-off module block before the macro heading (idempotent: existing blocks are removed first). Returns the new brief."""
    reg = registry or load_registry()
    core = strip_modules(brief)
    blocks = "".join(_wrap(m["id"], results[m["id"]], reg) for m in reg["modules"] if results.get(m["id"], {}).get("status") != "off")
    if not blocks:
        return core
    m1 = re.search(r"^#+\s*(§?\s*1\b|1\.|.*MACRO)", core, re.M | re.I)
    at = m1.start() if m1 else (core.find("APPENDIX A") if "APPENDIX A" in core else len(core))
    return core[:at] + blocks + core[at:]


def check(brief, run_dir, date, registry=None):
    """Module-level gate. Returns (fails, notes). A module that is present and ok is held to its own rules; a degraded one must carry its one-line note
    (the assembler always writes it, so a missing note means the block was edited); an off module is skipped."""
    reg = registry or load_registry()
    fails, notes = [], []
    blocks = module_blocks(brief)
    a_adv = {c["ticker"] for c in (_load(os.path.join(run_dir, "consensus.json")) or []) if c.get("verdict") == "ADVANCE"}
    core = strip_modules(brief)
    trade = ""
    if "§9B" in core and "§9C" in core:
        trade = core.split("§9B")[1].split("§9C")[0]
    for mod in reg["modules"]:
        mid = mod["id"]
        if mid not in blocks:
            notes.append(f"{mod['title']}: not in the brief (off or not assembled)")
            continue
        status, body = blocks[mid]
        if status == "degraded":
            ok = body.lstrip().startswith("> Section ") and "unavailable" in body
            (notes if ok else fails).append(f"{mod['title']}: degraded -- {body.strip()[:160]}" if ok else f"{mid}: degraded block lacks its one-line note")
            continue
        if status != "ok":
            continue
        rdir = _run_dirs(run_dir, mod["run_dir_suffix"])
        cons = _load(os.path.join(rdir, "consensus.json")) or []
        known = {c["ticker"]: c for c in cons}
        a_known = {c["ticker"] for c in (_load(os.path.join(run_dir, "consensus.json")) or [])}
        if not re.search(r"\d+ names deliberated", body):
            fails.append(f"{mid}: the 'N names deliberated' count line is missing")
        rows = re.findall(r"^\|\s*([A-Z][A-Z0-9.\-]{0,7})\s*\|", body, re.M)
        for t in rows:
            if t not in known and t not in a_known:
                fails.append(f"{mid}: {t} is not in the {mod['run_dir_suffix']} run's consensus nor the main list's")
            if t in known and known[t].get("verdict") not in VERDICTS:
                fails.append(f"{mid}: {t} is listed but did not advance or hold")
            if t not in a_adv and re.search(rf"(?m)^\s*\|\s*\*{{0,2}}{re.escape(t)}\*{{0,2}}\s*\|", trade):
                fails.append(f"{mid}: {t} is a trade row (9B) but is not an ADVANCE on the main list")
    return fails, notes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("assemble", "check"):
        s = sub.add_parser(name); s.add_argument("--brief", required=True); s.add_argument("--run-dir", default="."); s.add_argument("--date", required=True)
    sub.choices["assemble"].add_argument("--status", default="brief_sections_status.json")
    a = p.parse_args(argv)
    brief = open(a.brief).read()
    if a.cmd == "assemble":
        res = render_all(a.run_dir, a.date)
        open(a.brief, "w").write(assemble(brief, res))
        json.dump({k: {kk: vv for kk, vv in v.items() if kk != "md"} for k, v in res.items()}, open(a.status, "w"), indent=1)
        for k, v in res.items():
            print(f"module {k}: {v['status']}" + (f" -- {v['reason']}" if v.get("reason") else ""))
        return 0
    fails, notes = check(brief, a.run_dir, a.date)
    for n in notes: print(f"note  {n}")
    for f in fails: print(f"FAIL  {f}")
    print(f"RESULT: {len(fails)} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
