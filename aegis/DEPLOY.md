# DEPLOY — how this kernel becomes a running system on Claude and on Kimi
Plain steps, actual paths. The kernel never runs directly; you install what the packagers generate.
---

# ⚠️ PM ACTION BOX — the only things that need YOUR hands. Do them whenever ready; nobody will ask again.

> **PM-1 · GitHub token (unlocks: kernel push finalisation, daily archive commits from sessions)**
> github.com → your avatar → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token → Resource owner: you · Repository access: **Only select repositories → TongIncomeWheel/AQE** · Permissions: **Contents → Read and write** (nothing else) · Expiration: 90 days → Generate → copy.
> Then either: (a) paste it into any working session and say **/push** — the prepared commit goes up in seconds; or (b) skip the token entirely and run on your PC:
> `git pull` → unzip the latest kernel so `aegis/` sits at the repo root → `git add aegis && git commit -m "aegis kernel v4.9" && git push`
> *(Optional while you're there: Settings → General → Danger Zone → Change visibility → **Private**.)*

> **PM-2 · Windows scheduler (unlocks: the standing clock — premarket build, post-market, weekly, janitor)**
> Confirm the PC is Windows and stays on 24/7, then in any working session say **/schedule** — the Task Scheduler XML entries are generated for import (Task Scheduler → Import Task…), one per clock entry from RB:schedule. Nothing else needed.

> **PM-3 · Tiger URL (unlocks: Kimi harness ONLY — skip until/unless you deploy Kimi)**
> claude.ai → Settings → Connectors → Tiger MCPv7 → copy the server URL → paste one line into `aegis/config/endpoints.json` (`tiger_mcp.url`).

> **PM-4 · PC env file (unlocks: universe screen live run, ledger price feed)**
> Copy `aegis/config/env.example` → `.env` in the repo folder on the PC; fill `FMP_API_KEY=` (from your FMP account). Alpaca keys are already embedded (your ruling); IBKR only if you chose the gateway.

Everything else in this file is my work or automatic.


---

## A. Deploy into Claude (primary today)

**A1. What already works with ZERO setup:** the Tiger MCPv7 and FMP connectors are attached to your claude.ai account — verified live 18 Jul (Tiger account summary + FMP quote answered from a working session). Any Claude session, including a fresh project, can call them immediately. Alpaca is a plain script (keys inside, PM-approved read-only). Nothing to configure for data access.

**A2. Claude Code / Cowork on your PC (the runtime that can run schedules and touch files):**
1. On the PC: `git clone` the (private) AQE repo → you have `aegis/` inside it.
2. `python3 aegis/packaging/build_claude.py` → generates `aegis/dist/claude-plugin/aegis-v4/`.
3. Copy that folder to `~/.claude/plugins/aegis-v4/` (or point Claude Code at it as a local plugin). Restart Claude Code — the 21 skills appear, commands (`/pm`, `/arm`, `/plan`…) live in the registry file shipped with them.
4. Create `data/` next to the repo per `data/README.md`; copy `config/env.example` → `.env`, fill FMP key (Tiger/FMP not needed — connectors; Alpaca keys embedded).
5. Schedule the standing clock (Windows Task Scheduler): 13:00 SGT premarket build · 04:05 post-market · then design&review · Sunday weekly · nightly janitor. Each entry = `claude -p "/pm"` style headless invocations (exact commands in the generated plugin README).
6. Smoke test: `/fa` (book from state) · run `tools/tripwires.py` on the latest AQE export · `/pm` once supervised end-to-end.

**A3. New claude.ai Project (phone/chat surface — the one you talk to):**
1. Create the project. Upload FOUR files to project knowledge: `CONTEXT.md`, `charter/constitution.md`, `charter/rulebook.yaml`, `charter/parameters.yaml` (+ `charter/commands.md`).
2. Project instructions = one line: "Load CONTEXT.md first; obey the charter; procedures are the installed skills; commands per commands.md."
3. Connectors (Tiger MCPv7, FMP, Drive if kept) are account-level — already attached.
4. This project is your UX: `/plan`, `/approve`, `/arm`, `/ap`, `/fa` from your phone. The heavy scheduled runs happen in A2 on the PC; both read/write the same data/ shelves synced through the repo.

---

## B. Deploy into Kimi Code CLI (the alternative harness)

1. On the PC: install Kimi CLI (`npm i -g @moonshot/kimi-cli` or per current vendor doc), log in with your Kimi subscription.
2. `python3 aegis/packaging/build_kimi.py` → generates `aegis/dist/kimi/`.
3. Copy `dist/kimi/skills/*` into Kimi's Agent Skills directory (`~/.kimi/skills/` per its config); copy `dist/kimi/agents/voices/*` into its subagent definitions — the premarket skill's step 6 spawns them as the swarm.
4. Fill `config/endpoints.json`: paste the Tiger connector URL (claude.ai → Settings → Connectors → Tiger MCPv7 → copy URL) — the ONE manual line; FMP key from `.env`; IBKR stdio entry already written. Re-run build_kimi so `mcp.json` regenerates; merge it into Kimi's MCP config.
5. Same `.env`, same `data/` shelves, same repo — the two harnesses are interchangeable by construction; artifacts diff cleanly because they follow the same contracts.
6. Shadow protocol: run Kimi in parallel for a week; each day diff `data/sod/DATE/committee_*.json` and the plan against the Claude run; cut over (or keep as warm standby) when the diff is boring.

---

## C. What "deployed" means — the acceptance checklist
- [ ] `/pm` produces a schema-valid plan by 16:00 with all 10 nomination files present
- [ ] Tripwires pass on today's export; a forced failure blocks and pages
- [ ] `/arm` → `/ap` shows armed till next 05:30 SGT → `/disarm` works
- [ ] Gatekeeper refuses a name missing consensus (test with a dummy request) and logs it
- [ ] Post-market writes journal + metrics + audit; GitHub daily archive commit appears
- [ ] Morning summary arrives at 10:00 with ledger update and any backlog asks
