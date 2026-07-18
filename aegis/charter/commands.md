# COMMAND REGISTRY — one word, one action. No sentences needed.
| Command | Does | Needs confirm? |
|---|---|---|
| **/pm** | Run the premarket process now (plan lands when done) | no |
| **/plan** | Show today's Executive Action Plan | no |
| **/approve** | Approve the plan as-is (edits: `/approve except TICKER`) | it IS the confirm |
| **/arm** | Arm autopilot → auto-expires next 05:30 SGT. Gatekeeper may auto-place approved preauthorised names within caps | no — arming is the consent |
| **/disarm** | Kill autopilot instantly | no |
| **/ap** | Autopilot status (armed? expires? orders used?) | no |
| **/fa** | Quick book view from state — token-cheap | no |
| **/watch** | Market-hours status: alerts armed, fires so far | no |
| **/bracket T** | Bracket card for ticker T (AQE verbatim + live distance) | no |
| **/close** | Run post-market now (journal, metrics, audit) | no |
| **/review** | Run design & review now | no |
| **/weekly** | Run the weekly process now | no |
| **/param X Y** | Set parameter X to Y (validated, logged, committed) | shows old→new, then yes |
| **/backlog** | Show open backlog items awaiting your tap | per item |
| **/killed** | Show today's gatekeeper refusals and why | no |
| **/why T [date]** | Why did ticker T not advance — covers committee PASS, event filter, gatekeeper refusal, any stage | no |
| **/reject** | Reject today's plan outright (plan stands down) | it IS the confirm |
| **/pause** | Suspend the whole system: no scheduled runs, no alert wakes, autopilot disarmed. `/resume` restarts | no |
| **/flatten** | EMERGENCY: gatekeeper emits exit previews for ALL held names for you to execute | previews only — you execute |
| **/eod** | Alias of /close (post-market run) | no |
| **/srm** | Sector scorecard — feed's end-of-day sector block; during market hours ALSO runs the live pulse (srm_live) | no |
| **/ptj** | Print the trade journal in TODAY'S format — same fields, same scope (open + closed + metrics + broker sync). Heavy path, exact command only, exactly as before | no |
| **/hedge** | Run the hedge check on demand (coverage matrix; candidates if cover is short) — same as the old /hedge | no |
| **/later** | Defer a backlog item to tomorrow's summary | no |
Anything not on this list can still be said in plain English — commands are the fast path, not the only path.
