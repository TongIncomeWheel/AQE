#!/usr/bin/env python3
"""Package the kernel for Kimi Code CLI. GENERATED OUTPUT — never hand-edit.
Emits: dist/kimi/ with Agent Skills (same compiled skills as Claude — the formats are compatible
markdown+frontmatter), agents/ (voice subagent definitions for swarm mode), and mcp.json pointing at
the reused Tiger/Alpaca cloud MCPs + the local IBKR server + FMP.
"""
import json, os, shutil, sys, yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "kimi")

def main():
    # reuse the Claude build for skills (formats compatible), then add Kimi-specific config
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_claude
    build_claude.main()
    shutil.rmtree(DIST, ignore_errors=True)
    SRC = os.path.join(ROOT, "dist", "claude-plugin", "aegis-v4")
    for d in ("contracts", "tools", "charter"):
        shutil.copytree(os.path.join(SRC, d), os.path.join(DIST, d))
    # K3: Kimi skill names must be [a-z0-9-]; K7: voice skills stay OUT of Kimi skills (agents ARE the swarm)
    os.makedirs(os.path.join(DIST, "skills"), exist_ok=True)
    for name in sorted(os.listdir(os.path.join(SRC, "skills"))):
        if name.startswith("voice-"):
            continue
        if name == "staging-gatekeeper":
            continue   # D-30: Kimi is read-only until explicit production migration — NO order path ships
        kname = name.replace("_", "-")
        sdst = os.path.join(DIST, "skills", kname); os.makedirs(sdst, exist_ok=True)
        for f in os.listdir(os.path.join(SRC, "skills", name)):
            body = open(os.path.join(SRC, "skills", name, f)).read()
            body = body.replace(f"name: {name}", f"name: {kname}")
            open(os.path.join(sdst, f), "w").write(body)
    shutil.copy(os.path.join(SRC, "CONTEXT.md"), os.path.join(DIST, "CONTEXT.md"))
    # K4: Kimi auto-loads AGENTS.md, not CONTEXT.md
    open(os.path.join(DIST, "AGENTS.md"), "w").write(
        "# AEGIS — load-first\nRead CONTEXT.md in this directory before anything else; it is the system context document. "
        "Then obey charter/constitution.md; procedures are the installed skills; commands per charter/commands.md.\n")
    # K1: Kimi subagents are YAML agent-files, not markdown frontmatter. Emit system-prompt files + one agent-file.
    # D-16: judgment-tier pin attempted via "model:" key — UNVERIFIED against current kimi-cli schema (BL-026).
    rb = yaml.safe_load(open(os.path.join(ROOT, "charter", "rulebook.yaml")))
    pp_ = yaml.safe_load(open(os.path.join(ROOT, "charter", "parameters.yaml")))
    kimi_judgment_model = pp_.get("model_tiers", {}).get("kimi_judgment", "kimi-for-coding-highspeed")
    os.makedirs(os.path.join(DIST, "agents"), exist_ok=True)
    subagents = {}
    for f in sorted(os.listdir(os.path.join(SRC, "agents"))):
        if f.startswith("staging-gatekeeper"):
            continue   # D-30/HIGH-2: Kimi is read-only — the order-capable agent never ships to the Kimi package
        body = open(os.path.join(SRC, "agents", f)).read()
        body = body.split("---", 2)[2] if body.startswith("---") else body   # strip Claude frontmatter
        vname = f.replace(".md", "").replace("_", "-")
        pp = os.path.join(DIST, "agents", vname + ".txt")
        open(pp, "w").write(body.strip() + "\n")
        # BL-026: "model" key here is a best-effort D-16 pin, not a confirmed kimi-cli field — verify at deploy.
        subagents[vname] = {"extend": "default", "system_prompt_path": "./agents/" + vname + ".txt",
                             "model": kimi_judgment_model, "tools": []}
    agentfile = {"version": 1,
                 "agent": {"name": "aegis", "extend": "default", "system_prompt_path": "./AGENTS.md"},
                 "subagents": subagents}
    open(os.path.join(DIST, "aegis-agent.yaml"), "w").write(
        "# GENERATED — Kimi agent-file. Launch: kimi --agent-file aegis-agent.yaml (verify schema vs current kimi-cli docs at deploy)\n"
        + yaml.dump(agentfile, sort_keys=False))
    # HIGH-2 / D-30: Kimi is read-only until production migration. The Tiger cloud MCP exposes
    # order-placement tools (place_stock_order/cancel_order/...), so it is DELIBERATELY NOT wired
    # into the Kimi package — no order-capable endpoint enters the Kimi cloud, enforced by construction
    # (not by hoping the PM supplies a read-only token). Kimi reads market data via FMP (read-only REST)
    # and the local read-only IBKR MCP below (no order tools by construction).
    mcp = {"mcpServers": {
        "ibkr":   {"transport": "stdio", "command": "python3",
                    "args": [os.path.join(os.path.abspath(DIST), "tools", "mcp", "ibkr_mcp", "server.py")]},   # K5: absolute path; read-only
    }, "_note": "Tiger write-capable MCP intentionally EXCLUDED from Kimi (D-30 read-only, HIGH-2). FMP + Alpaca are read-only REST via tools (keys in .env). Re-add a Tiger endpoint ONLY with a read-only-scoped token on explicit production migration (BL-023)."}
    json.dump(mcp, open(os.path.join(DIST, "mcp.json"), "w"), indent=1)
    open(os.path.join(DIST, "README.md"), "w").write(
        "# Aegis on Kimi Code CLI (generated)\n"
        "1. Install kimi-cli; log in with your Kimi subscription.\n"
        "2. Copy skills/ into your Kimi agent skills directory; agents/voices into subagent definitions.\n"
        "3. Merge mcp.json into Kimi's MCP config; fill endpoints in kernel config/endpoints.json first and rebuild.\n"
        "3b. Launch every run with: kimi --agent-file aegis-agent.yaml (registers the 10 voice subagents; K1).\n"
        "4. Swarm mode: premarket step 5 targets the voice-* subagents from aegis-agent.yaml — fresh context, no tools.\n"
        "5. Install kimi-cli via the OFFICIAL install script/package (see moonshotai.github.io/kimi-cli — the old npm name in earlier docs was wrong).\n"
        "6. Plan guidance (platform review 18 Jul): Allegretto tier fits the daily cycle; Moderato weekly ceiling is too small.\n"
        "7. Model tiering (D-16, BL-026 UNVERIFIED): aegis-agent.yaml pins each voice subagent's \"model\" key to "
        f"{kimi_judgment_model} — confirm this field name against current kimi-cli docs before trusting it; if unsupported, "
        "every subagent silently runs whatever the top-level session model is, which defeats the cost-tiering intent.\n")
    print(f"built {DIST}")

if __name__ == "__main__":
    main()
