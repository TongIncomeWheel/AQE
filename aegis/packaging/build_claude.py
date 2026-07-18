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
    # Arch-F2/A-B3: a package must be self-sufficient — ship contracts, charter yamls, CONTEXT, tools
    for d in ("contracts", "tools"):
        shutil.copytree(os.path.join(ROOT, d), os.path.join(DIST, d), ignore=shutil.ignore_patterns("__pycache__"))
    os.makedirs(os.path.join(DIST, "charter"), exist_ok=True)
    for f in ("rulebook.yaml", "parameters.yaml", "commands.md", "constitution.md", "decisions_log.md"):
        shutil.copy(os.path.join(ROOT, "charter", f), os.path.join(DIST, "charter", f))
    shutil.copy(os.path.join(ROOT, "CONTEXT.md"), os.path.join(DIST, "CONTEXT.md"))
    shutil.copytree(os.path.join(ROOT, "config"), os.path.join(DIST, "config"))
    for shelf in ("data/sod", "data/intraday", "data/eod", "data/persistent/cs_weekly", "data/archive"):
        os.makedirs(os.path.join(DIST, shelf), exist_ok=True)
        open(os.path.join(DIST, shelf, ".keep"), "w").write("")
    shutil.copy(os.path.join(ROOT, "data", "README.md"), os.path.join(DIST, "data", "README.md"))
    open(os.path.join(DIST, "README.md"), "w").write("# aegis-v4 plugin (GENERATED)\nSkills in skills/; contracts, tools, charter and CONTEXT.md ship IN-PACKAGE so the install is self-sufficient. Commands: skills/premarket/commands.md.\n")
    # Claude-expert fix #9/#10: claude.ai account connectors do NOT reach Claude Code CLI.
    # The plugin must carry its own MCP config; values flow from config/endpoints.json (PM fills once, rebuilds).
    ep = json.load(open(os.path.join(ROOT, "config", "endpoints.json")))
    json.dump({"mcpServers": {
        "tiger": {"type": "http", "url": ep["tiger_mcp"]["url"],
                   "headers": {"Authorization": "REPLACE-with-your-Tiger-auth (or leave for claude.ai-session-only use)"}}
    }, "_note": "FMP + Alpaca are plain REST via tools/ with keys in .env — no MCP needed in CLI. "
                "This file only matters for scheduled Claude Code runs on the PC; claude.ai app sessions use account connectors."},
        open(os.path.join(DIST, ".mcp.json"), "w"), indent=1)
    compile_voice_agents()
    print(f"built {DIST}")

# Data taxonomy per voice: the EXACT AQE fields each voice may read (its data menu, made explicit).
VOICE_MENUS = {
 "lynch":        ["ticker","gics_sector_name","sc_momentum","flow","structure","rvol","rs_spy_20d","bracket.stop","bracket.risk_pct","bracket.rr","close","above_ema","vol_vs_30d"],
 "oneil":        ["ticker","sc_momentum","structure","elder","elder_5d","rvol","rs_spy_20d","rs_leadership","mp_state","bracket.stop","bracket.rr","sma_distance_pct"],
 "wyckoff":      ["ticker","flow","energy","mp_state","mp_accel_state","choch_state","rvol","bracket.stop","bracket.rr"],
 "raschke":      ["ticker","elder","elder_5d","energy","atr_14d","mp_accel_state","structure_shift","bracket.stop","bracket.risk_pct"],
 "steenbarger":  ["ticker","gics_sector_name","sc_momentum","lens_warnings","rvol"],
 "thorp":        ["ticker","sc_momentum","bracket.rr","bracket.rr_tp1","bracket.rr_tp2","knn_prob","knn_significant","sc_m_gate_detail","sc_p_gate_detail","beta_30d"],
 "seow":         ["ticker","ma_20","ma_50","ma_100","ma_200","sma_distance_pct","mp_state","sector_trend_state","close","above_ema","bracket.stop"],
 "minervini":    ["ticker","structure","elder","rs_spy_20d","rs_leadership","mp_state","bracket.stop","bracket.risk_pct","sma_distance_pct"],
 "druckenmiller":["ticker","gics_sector_name","sc_momentum","beta_30d","sector_trend_state","thematic_basket","thematic_grade"],
 "detect_lens":  ["ticker","lens","lens_positive","lens_warnings","runner_setup","runner_conviction","premove_setup","premove_conviction"],
}

def _field_meanings_block(menu):
    """BL-034 / D-29: for a voice's menu, render each field's meaning + how AQE computes it
    from contracts/field_dictionary.json, so the voice reads understanding, not a bare label."""
    try:
        fd = json.load(open(os.path.join(ROOT, "contracts", "field_dictionary.json")))["fields"]
    except Exception:
        return ""
    lines = []
    seen_keys = set()
    for m in menu:
        key = m.split(".")[0]
        if "." in m and key in seen_keys:
            lines.append(f"- `{m}` — sub-field of `{key}` (see above)")
            continue
        e = fd.get(m) or fd.get(key) or {}
        defn = (e.get("definition") or "").strip()
        how = (e.get("how_computed") or "").strip()
        if defn or how:
            seen_keys.add(key)
            bits = []
            if defn: bits.append(defn)
            if how: bits.append("HOW: " + how)
            lines.append(f"- `{m}` — " + " · ".join(bits))
    if not lines:
        return ""
    return ("\n\n## 2b · WHAT MY FIELDS MEAN (from AQE's own glossary + engine methods — I apply, never blind-read; D-29)\n"
            + "\n".join(lines)
            + "\nIf a field's meaning above is empty or unclear, I say so and do not invent analysis over it.")


def compile_voice_agents():
    """B1 fix: emit ONE self-contained agent definition per voice — the file a harness actually
    spawns as an isolated subagent. Compiled from: voice card + shared engine + data menu +
    field meanings (BL-034) + output contract example. All ten from one template => structural consistency."""
    import glob
    common = open(os.path.join(ROOT, "skills", "voice-common", "SKILL.md")).read()
    common_body = common.split("---", 2)[2] if common.startswith("---") else common
    example = json.dumps({"voice": "<me>", "date": "<YYYY-MM-DD>", "universe_file": "<path>",
        "nominations": [{"ticker": "PYPL", "reason": "one line, MY framework language", "fields_cited": ["elder_5d","bracket.stop"], "conviction": 4, "price_at_nomination": None}],
        "held_review": [{"ticker": "IBM", "verdict": "EXIT-CASE", "line": "one line"}],
        "shortfall_reason": "only if fewer than 10 — fewer is VALID, padding is the breach"}, indent=1)
    judgment_model = rb_lookup("model_tiers.judgment")  # D-16: pinned at build time, never inherited
    adir = os.path.join(DIST, "agents"); os.makedirs(adir, exist_ok=True)
    for bpath in sorted(glob.glob(os.path.join(ROOT, "skills", "eng-*", "SKILL.md"))):
        bname = os.path.basename(os.path.dirname(bpath))
        body = open(bpath).read()
        body = body.split("---", 2)[2] if body.startswith("---") else body
        open(os.path.join(adir, f"{bname}.md"), "w").write(
            f"---\nname: {bname}\ndescription: Engineering Bench seat — spawned isolated for Design & Review triage and the Weekly engineering session. Read-only.\nmodel: {judgment_model}\ntools: []\n---\n" + body.strip() + "\n")
    # D-16: committee-desk — the deliberation step, pulled out of "the orchestrator's own session"
    # into its own pinned judgment-tier agent, same reasoning as the voice swarm's isolation.
    cd_path = os.path.join(ROOT, "skills", "committee-desk", "SKILL.md")
    if os.path.isfile(cd_path):
        body = open(cd_path).read()
        body = body.split("---", 2)[2] if body.startswith("---") else body
        open(os.path.join(adir, "committee-desk.md"), "w").write(inline_rb(
            f"---\nname: committee-desk\ndescription: Isolated deliberation agent — turns the tallied, event-filter-cleared nomination set into verdicts (ADVANCE/HOLD-FOR-CONDITIONS/PASS) with a mandatory bear case on every entry. Spawned once per premarket run by the orchestrator. Model pinned to RB:model_tiers.judgment (D-16).\nmodel: {judgment_model}\ntools: []\n---\n" + body.strip() + "\n"))
    for path in sorted(glob.glob(os.path.join(ROOT, "skills", "voice-*", "SKILL.md"))):
        name = os.path.basename(os.path.dirname(path))
        if name == "voice-common": continue
        vkey = name.replace("voice-", "")
        card = open(path).read()
        card_body = card.split("---", 2)[2] if card.startswith("---") else card
        menu = VOICE_MENUS.get(vkey, [])
        agent = f"""---
name: {name}
description: Isolated nominator agent — {vkey}. Spawned fresh each premarket by the orchestrator; sees ONLY this file + the universe file + its own ledger report. No tools, no session context, no other voices.
model: {judgment_model}
tools: []
---
# AGENT: {name.upper()} — complete standalone instruction set (GENERATED; edit the kernel card, not this)

## 1 · WHO I AM (identity + canon)
{card_body.strip()}

## 2 · MY DATA TAXONOMY (the ONLY fields I read — my data menu, enforced)
{", ".join("`"+m+"`" for m in menu)}
Reading any field not on this menu — especially composites for detect_lens, or lens fields for framework voices — is a breach the auditor checks.{_field_meanings_block(menu)}

## 3 · MY PROCESS (identical machinery for all ten — the shared engine)
{common_body.strip()}

## 4 · MY MEMORY (injected, never fetched)
The orchestrator pastes the OUTPUT of `nomination_ledger.py report --voice {vkey}` below my prompt — my own last-15-day hit rates and open nominations only. I never see the ledger file (it contains other voices' picks).

## 5 · MY OUTPUT (contract + example — return EXACTLY this shape)
contracts/nomination.schema.json. Example:
```json
{example}
```

## 6 · FORBIDDEN
Other voices' outputs or existence in-context · the tally · macro/SRM before nominating · computing scores · fetching prices (orchestrator stamps price_at_nomination at tally) · padding to 10 · EVENT-DRIVEN checks (not my job — filter runs after tally).
"""
        open(os.path.join(adir, f"{name}.md"), "w").write(inline_rb(agent))

if __name__ == "__main__":
    main()
