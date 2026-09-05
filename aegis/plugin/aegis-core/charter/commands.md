# COMMAND REGISTRY — one word, one action. No sentences needed.
| Command | Does | Needs confirm? |
|---|---|---|
| **/premarket** | **THE MORNING COMMAND.** Closes the book for real (broker pull, batch, push to git, clean the book, archive) then prepares the AQE data. Prints the report on screen. Spawns no voices, builds no plan | no |
| **/committee-pm** | **THE SECOND COMMAND.** The committee looks at the data the premarket command just put on disk — swarm, tally, deliberation, plan. Switch to opus first. Stands down at its gate if premarket has not run | no |
| **/plan** | Show today's Executive Action Plan | no |
| **/approve** | Approve the plan as-is (edits: `/approve except TICKER`) | it IS the confirm |
| **/arm** | Arm autopilot → auto-expires next 05:30 SGT. Gatekeeper may auto-place approved preauthorised names within caps | no — arming is the consent |
| **/disarm** | Kill autopilot instantly | no |
| **/ap** | Autopilot status (armed? expires? orders used?) | no |
| **/ptj fa** | The same book view read straight off disk — no broker pull, no batch, instant and token-cheap. Says the file's write time so a stale array cannot pass as live | no |
| **/watch** | Market-hours status: alerts armed, fires so far | no |
| **/bracket T** | **Queue levels for ticker T — callable any time, repeated any number of times.** Entry zone, stop (AQE structural default, alternatives shown as suggestions), TP ladder, R:R, size off PTJ dynCap, sector impact. No committee guard — PM discretion is a valid reason on its own. No verdict, no gate, no record kept | no |
| **/param X Y** | Set parameter X to Y (validated, logged, committed) | shows old→new, then yes |
| **/backlog** | Show open backlog items awaiting your tap | per item |
| **/killed** | Show today's gatekeeper refusals and why | no |
| **/why T [date]** | Two modes (D-20 tiered): for a name ON the plan → expand its FULL data anchor (every field the voices cited + values, the committee bear case + dissent); for a name NOT on the plan → why it didn't advance (committee PASS, event filter, gatekeeper refusal, any stage) | no |
| **/reject** | Reject today's plan outright (plan stands down) | it IS the confirm |
| **/pause** | Suspend the whole system: no scheduled runs, no alert wakes, autopilot disarmed. `/resume` restarts | no |
| **/flatten** | EMERGENCY: gatekeeper emits exit previews for ALL held names for you to execute | previews only — you execute |
| **/srm** | Sector scorecard — feed's end-of-day sector block; during market hours ALSO runs the live pulse (srm_live) | no |
| **/ptj** | **Live portfolio view, any hour.** Pulls both brokers now and renders the full journal — positions, P&L, dynCap, metrics — using the real batch in rehearsal mode. Stamps nothing, pushes nothing, writes no book of record. Run it as often as you like; `/premarket` still does the real close | no |
| **/hedge** | Run the hedge check on demand (coverage matrix; candidates if cover is short) — same as the old /hedge | no |
| **/later** | Defer a backlog item to tomorrow's summary | no |
| **/steer** | Show the pending steer file: FYI · DECIDE (your one-tap items, with days-pending) · PRE-FIX notices · POST-FIX results | per DECIDE item |
| **/findings** | Raw findings from the last review before bench triage | no |
| **/recover [loop]** | Re-run a failed loop fresh (premarket · market-hours · post-market · eod-audit). Read/compute/plan only — a re-run that reaches execution still previews at the gate (D-45) | no |
| **/heal [loop] --failure T** | Run the auto self-heal protocol for a classified failure (transient→retry/reseed; structural→escalate; gate→stand down). Never places an order | no |
| **/repull [ptj]** | Re-fetch today's AQE export (revalidate + tripwires); `/repull ptj` re-pulls both brokers and refreshes dynCap | no |
| **/reseed [names]** | Force a historical-store seed (D-40) for missing/stale names | no |
**The daily chain is two commands: `/premarket`, then `/committee-pm`.** `/ptj` and `/ptj fa` are the look — run them any hour, as often as you like; they change nothing. Everything else on this list is a lever or a recovery path. **Nothing on this list is scheduled — every run starts because you typed it.**

Anything not on this list can still be said in plain English — commands are the fast path, not the only path.
