#!/usr/bin/env python3
"""Package the kernel for Kimi Code CLI. GENERATED OUTPUT — never hand-edit.
Emits: dist/kimi/ with Agent Skills (same compiled skills as Claude — the formats are compatible
markdown+frontmatter), agents/ (voice subagent definitions for swarm mode), and mcp.json pointing at
the reused Tiger/Alpaca cloud MCPs + the local IBKR server + FMP.
"""
import json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "kimi")

def main():
    # reuse the Claude build for skills (formats compatible), then add Kimi-specific config
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_claude
    build_claude.main()
    shutil.rmtree(DIST, ignore_errors=True)
    shutil.copytree(os.path.join(ROOT, "dist", "claude-plugin", "aegis-v4", "skills"), os.path.join(DIST, "skills"))
    vdst = os.path.join(DIST, "agents", "voices"); os.makedirs(vdst, exist_ok=True)
    for name in sorted(os.listdir(os.path.join(ROOT, "skills"))):
        if name.startswith("voice-"):
            shutil.copy(os.path.join(ROOT, "skills", name, "SKILL.md"), os.path.join(vdst, name + ".md"))
    ep = json.load(open(os.path.join(ROOT, "config", "endpoints.json")))
    mcp = {"mcpServers": {
        "tiger":  {"transport": "http", "url": ep["tiger_mcp"]["url"]},
        "alpaca": {"transport": "http", "url": ep["alpaca_mcp"]["url"]},
        "ibkr":   {"transport": "stdio", "command": "python3",
                    "args": [os.path.join(ROOT, "tools", "mcp", "ibkr_mcp", "server.py")]},
    }}
    json.dump(mcp, open(os.path.join(DIST, "mcp.json"), "w"), indent=1)
    open(os.path.join(DIST, "README.md"), "w").write(
        "# Aegis on Kimi Code CLI (generated)\n"
        "1. Install kimi-cli; log in with your Kimi subscription.\n"
        "2. Copy skills/ into your Kimi agent skills directory; agents/voices into subagent definitions.\n"
        "3. Merge mcp.json into Kimi's MCP config; fill endpoints in kernel config/endpoints.json first and rebuild.\n"
        "4. Swarm mode: the premarket skill step 6 spawns each voices/*.md as an isolated subagent.\n")
    print(f"built {DIST}")

if __name__ == "__main__":
    main()
