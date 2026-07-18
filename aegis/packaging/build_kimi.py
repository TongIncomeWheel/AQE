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
    SRC = os.path.join(ROOT, "dist", "claude-plugin", "aegis-v4")
    for d in ("skills", "contracts", "tools", "charter"):
        shutil.copytree(os.path.join(SRC, d), os.path.join(DIST, d))
    shutil.copy(os.path.join(SRC, "CONTEXT.md"), os.path.join(DIST, "CONTEXT.md"))
    shutil.copytree(os.path.join(SRC, "agents"), os.path.join(DIST, "agents"))   # compiled standalone voice agents
    ep = json.load(open(os.path.join(ROOT, "config", "endpoints.json")))
    mcp = {"mcpServers": {
        "tiger":  {"transport": "http", "url": ep["tiger_mcp"]["url"], "headers": {"Authorization": "${TIGER_MCP_AUTH}"}},
        "ibkr":   {"transport": "stdio", "command": "python3",
                    "args": ["./tools/mcp/ibkr_mcp/server.py"]},
    }, "_note": "FMP + Alpaca are plain REST via tools (keys in .env) — no MCP needed (F10). Relative ibkr path: run kimi from the dist folder."}
    json.dump(mcp, open(os.path.join(DIST, "mcp.json"), "w"), indent=1)
    open(os.path.join(DIST, "README.md"), "w").write(
        "# Aegis on Kimi Code CLI (generated)\n"
        "1. Install kimi-cli; log in with your Kimi subscription.\n"
        "2. Copy skills/ into your Kimi agent skills directory; agents/voices into subagent definitions.\n"
        "3. Merge mcp.json into Kimi's MCP config; fill endpoints in kernel config/endpoints.json first and rebuild.\n"
        "4. Swarm mode: premarket step 5 spawns each agents/voice-*.md as an isolated subagent (fresh context, no tools).\n")
    print(f"built {DIST}")

if __name__ == "__main__":
    main()
