# AEGIS — KICKOFF (paste-once, zero manual loading)

**The model, plainly:** you INSTALL once (the plugin — done). After that, every new
session already HAS the whole system — skills, agents, commands, tools, and the
charter files — because they live inside the installed plugin. There is **no
per-session install and no manual file-loading**. A session becomes "Aegis" the
moment it reads the context below, and these kickoffs do that for you in one paste.

**One-time, to make it truly zero-touch (recommended):** in the workspace, add
`aegis/CONTEXT.md` + the four `aegis/charter/*` files as **Project Knowledge**.
Then every session has them automatically and the kickoff gets even shorter. This
is a one-time click, not a per-session step.

---

## KICKOFF A — DRY RUN (paste into a fresh installed session)
> You are the Aegis orchestrator in the installed `aegis-v4` workspace. Do NOT wait for me to load anything — read these yourself, they are all in the plugin:
> `aegis/CONTEXT.md` (load first), then `aegis/charter/constitution.md`, `aegis/charter/rulebook.yaml`, `aegis/charter/parameters.yaml`, `aegis/charter/decisions_log.md`.
> Then run `python3 aegis/tools/preflight.py` — if `GITHUB_PAT` is missing, ask me for it and save it to `aegis/config/.env`.
> Then run `python3 aegis/tools/dryrun.py` and show me the GREEN/RED result.
> Then execute `aegis/DRYRUN.md` Parts B and C step by step, reporting PASS/FAIL for each.
> Place NO orders — previews only. Autopilot stays OFF. Report anything that fails, don't work around it.

## KICKOFF B — DAILY OPERATION (a manual session, before the clock is set)
> You are the Aegis orchestrator in the installed `aegis-v4` workspace. Read `aegis/CONTEXT.md` + the four `aegis/charter/*` files, run `aegis/tools/preflight.py`, then run `/pm`.
> Produce the Executive Action Plan for my approval by 16:00 SGT. Place nothing — I approve the picks and stage the orders. Everything else is autonomous.

*(Once the Phase-6 scheduled tasks are created, you never paste B — the clock fires premarket / watch / post-market on its own. Kickoff B is only for an ad-hoc manual run.)*

---

## WHAT IS AUTOMATED vs WHERE YOU STEP IN (the whole truth)

| Layer | Automated? | Your intervention |
|---|---|---|
| Premarket build (universe, 10 voices, committee, risk, gates, plan) | **Yes** | — |
| **The daily plan / picks** | Assembled automatically | **You approve / discuss by 21:00 SGT** ← touchpoint 1 |
| **Placing orders** | Previews only | **You stage & place** ← touchpoint 2 (removed only when you `/arm`) |
| Market-hours watch (distance-to-stop, trails) | **Yes** (code watches, no AI polling) | — |
| Post-market (journal, metrics, audit, git push, Drive) | **Yes** | — |
| Data pulls, historical self-heal, notifications, `/ops` | **Yes** | — |
| System CHANGES / improvements | Proposed automatically | You approve via the STEER file (governance, not daily trading) |

**So in production, before you arm: your ONLY daily trading interventions are (1) approving the picks and (2) placing the orders.** Everything else runs itself.

**If you're asleep and have NOT armed:** the plan is built and waits; with no approval by 21:00 it **stands down as draft — nothing trades** (law: silence never trades). That is safe, not autonomous trading. To have it trade while you sleep, you `/arm` autopilot within its caps (≤1R/order, ≤3/session, preauthorised names only, auto-expires 05:30 SGT, auto-off on any breach) — that is the switch that removes touchpoint 2 for approved names.

**Full autonomy needs the clock:** the autonomous cadence only fires once the Phase-6 scheduled tasks are created (`create_trigger`). Until then, runs are manual (Kickoff B).
