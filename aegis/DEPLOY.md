# DEPLOY — how this kernel becomes a running system on Claude and on Kimi
Plain steps, actual paths. The kernel never runs directly; you install what the packagers generate.
**Topology per D-15 (18 Jul): two cloud engines + one cockpit + a narrowed PC.** The Claude cloud workspace and KimiClaw each run the full scheduled phases; the PC only runs AQE and the intraday alert watcher and pushes everything to GitHub the moment it's written; every approval, arm and steer happens in ONE place — the Claude app chat.

---

# ⚠️ PM ACTION BOX — the only things that need YOUR hands. Do them whenever ready; nobody will ask again.

> **PM-1 · GitHub token (unlocks: kernel push, and now the ENTIRE PC-to-cloud data flow — this is the load-bearing one)**
> github.com → your avatar → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token → Resource owner: you · Repository access: **Only select repositories → TongIncomeWheel/AQE** · Permissions: **Contents → Read and write** (nothing else) · Expiration: 90 days → Generate → copy.
> Then either: (a) paste it into any working session and say **/push** — the prepared commit goes up in seconds; or (b) skip the token entirely and run on your PC:
> `git pull` → unzip the latest kernel so `aegis/` sits at the repo root → `git add aegis && git commit -m "aegis kernel" && git push`
> *(Optional while you're there: Settings → General → Danger Zone → Change visibility → **Private**.)*
> Under D-15 the repo is no longer just resilience — it is how the fresh AQE export and intraday alerts reach both cloud engines (BL-022). The token lives on the PC AND in both cloud workspaces.

> **PM-2 · PC scheduler — NARROWED by D-15 (unlocks: the feed only)**
> The PC no longer runs the phases. It needs exactly TWO Task Scheduler entries: (1) run AQE + push the export to GitHub immediately after; (2) start the alert watcher before the US open with its 21:25 SGT heartbeat. Confirm the PC is Windows and stays on 24/7, then say **/schedule pc** in any working session — the two entries are generated for import.

> **PM-3 · Claude scheduled tasks (unlocks: the standing clock — premarket build, post-market, design & review, weekly, janitor)**
> Say **/schedule cloud** in the Claude workspace — I create the scheduled tasks on the app's own scheduler (they fire fresh cloud sessions on the SGT clock and push a notification to your phone when a run finishes with something you need to see). Nothing to install. One thing we verify in the practice week: that scheduled headless runs reach the Tiger connector; if they don't, the packaged `.mcp.json` with the Tiger URL (PM-4) is the fallback and it's one line.

> **PM-4 · Tiger URL + auth (unlocks: Kimi's read-only broker data, and the fallback for scheduled Claude runs)**
> claude.ai → Settings → Connectors → Tiger MCPv7 → copy the server URL → paste one line into `aegis/config/endpoints.json` (`tiger_mcp.url`).
> ⚠️ For Kimi this is gated by **BL-023**: the current token can place orders, so it does NOT go into the Kimi cloud as-is. First ask whether the Tiger MCP can mint a second READ-ONLY token/endpoint; if it can't, that becomes a DECIDE — policy-level allowlist (Kimi package ships zero write tools) or no broker data on the Kimi side.

> **PM-5 · Env keys (unlocks: universe screen, ledger price feed)**
> Copy `aegis/config/env.example` → `.env` and fill `FMP_API_KEY=` (from your FMP account) — on the PC and in each cloud workspace. Alpaca read-only keys are already embedded (your ruling); IBKR only if you chose the gateway.

> **PM-6 · Kimi side (unlocks: the parallel engine)**
> Subscribe Allegretto → open kimi.com → enable Kimi Claw (the chat workspace tab). Then say **/kimi smoke** in any working session and I run BL-021: can it execute our Python tools, reach the Tiger URL, fire a scheduled task on our clock, and load one skill. The Kimi engine goes live ONLY after that passes; until then Kimi CLI on the PC remains the tested fallback. No Telegram bridge — the browser/app chat tab is the surface, per your ruling.

Everything else in this file is my work or automatic.

---

## A. The Claude side (primary — engine AND cockpit in one workspace)

**A1. Platform boundary, corrected 18 Jul and now working FOR us:** your account connectors (Tiger MCPv7, FMP, Drive) work in claude.ai app / project / Cowork sessions — which is exactly where the engines now live under D-15. The old problem (connectors not reaching the PC's CLI) mostly evaporates because the PC no longer runs phases. The one residue: scheduled headless firings may not carry interactively-authenticated connectors — verified in the practice week, with the packaged `.mcp.json` (PM-4) as the one-line fallback.

**A2. The cloud workspace (this one) — the engine:**
1. Kernel lives in the workspace + GitHub (`aegis/` at the repo root). `python3 aegis/packaging/build_claude.py` generates the plugin; its 21 skills and command registry are what the sessions run.
2. Data shelves (`data/sod`, `intraday`, `eod`, `persistent`, `archive`) live in the workspace and sync through the repo: every phase run starts with a pull (fresh AQE export from the PC per BL-022) and ends with a commit.
3. The standing clock runs on the app's scheduled tasks (PM-3): premarket build 13:00 SGT · market-hours watch session from 21:25 SGT (self-paced alert polling against the repo per BL-022) · post-market 04:05 · design & review after it · Sunday weekly · nightly janitor.
4. Smoke test: `/fa` (book from state) · `tools/tripwires.py` on the latest export · one SUPERVISED `/pm` end-to-end — watching run time (voices in parallel, not serial) and token burn to size the plan week.
5. Plan guidance (platform review): the daily 10-voice cycle points at **Claude Max $200 (20x)**; the $100 tier may hit the weekly ceiling — confirm on the usage dashboard after the practice week.

**A3. The cockpit — the same workspace, from your phone:**
1. This chat IS the cockpit: `/plan`, `/approve`, `/arm`, `/ap`, `/fa`, `/watch`, `/steer` from your phone, any time. Project knowledge carries `CONTEXT.md` + the four charter files; instructions: "Load CONTEXT.md first; obey the charter; procedures are the installed skills; commands per commands.md."
2. **Sole command surface (D-15).** Approvals, arming and steering happen here and nowhere else. The 4pm plan, the 10am summary (with the Kimi diff), and pages arrive here as app pushes.

---

## B. The Kimi side (parallel engine — KimiClaw first, CLI as fallback)

1. **KimiClaw (primary path, gated by BL-021):** enable per PM-6 → run the smoke test → `python3 aegis/packaging/build_kimi.py` (a Claw-format adapter variant is cut if the smoke test shows ClawHub skill format differs from Kimi CLI's) → install skills into the Claw workspace → set its scheduled tasks to the same SGT clock → GitHub token so it pulls the same repo/feed and commits its outputs under `data/.../kimi/`.
2. **Scope (D-15):** full parallel — same universe file, same voices, same phases — plus read-only broker data ONCE BL-023 resolves the credential scoping. **No order path exists on this side:** no staging-gatekeeper skill, no write tools in the package, `/arm` unknown to it by construction.
3. **Surface:** the kimi.com Claw chat tab (browser or app). Read it like a second analyst's desk; you never approve anything there. No Telegram bridge.
4. **Shadow protocol:** runs the same week as the Claude practice week; each day the 10am summary diffs Kimi's committee output and plan against Claude's. The diff being boring is the acceptance signal; where they disagree, that's free adversarial review of the committee itself.
5. **Fallback:** if the smoke test fails, Kimi CLI on the PC (the already-built `dist/kimi/` package) runs the same shadow — it just loses the chat surface until KimiClaw matures.

---

## C. What "deployed" means — the acceptance checklist
- [ ] `/pm` produces a schema-valid plan by 16:00 with all 10 nomination files present — fired by the cloud scheduler, not by hand
- [ ] Fresh AQE export reaches both clouds via the repo before the premarket build (BL-022 latency measured)
- [ ] Tripwires pass on today's export; a forced failure blocks and a page reaches your phone as an app push
- [ ] `/arm` → `/ap` shows armed till next 05:30 SGT → `/disarm` works — in the Claude cockpit only; the Kimi side has no such command
- [ ] Gatekeeper refuses a name missing consensus (dummy request) and logs it
- [ ] Post-market writes journal + metrics + audit; both engines' archive commits appear on GitHub
- [ ] Morning summary arrives at 10:00 with ledger update, backlog asks, AND the Claude-vs-Kimi plan diff
