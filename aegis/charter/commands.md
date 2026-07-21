# COMMAND REGISTRY — one word, one action. No sentences needed.
| Command | Does | Needs confirm? |
|---|---|---|
| **/pm** | Run the premarket process now (plan lands when done) | no |
| **/plan** | Show today's Executive Action Plan | no |
| **/approve** | Approve the plan as-is (edits: `/approve except TICKER`) | it IS the confirm |
| **/arm** | Arm autopilot → auto-expires next 05:30 SGT. Gatekeeper may auto-place approved preauthorised names within caps | no — arming is the consent |
| **/disarm** | Kill autopilot instantly | no |
| **/ap** | Autopilot status (armed? expires? orders used?) | no |
| **/fa** | Quick book view, plain text, read from today's workspace files (not chat memory — G3) — token-cheap | no |
| **/status** | Rendered status card (D-22, skills/status): open Aegis positions + P&L, armed state + expiry, alerts armed/fired, plan headline — the union of /fa + /ap + /watch in one glance, read from the persistent workspace so it works in any fresh chat | no |
| **/watch** | Market-hours status: alerts armed, fires so far | no |
| **/bracket T** | Bracket card for ticker T (AQE verbatim + live distance) | no |
| **/close** | Run post-market now (journal, metrics, audit) | no |
| **/review** | Run design & review now | no |
| **/weekly** | Run the weekly process now | no |
| **/param X Y** | Set parameter X to Y (validated, logged, committed) | shows old→new, then yes |
| **/backlog** | Show open backlog items awaiting your tap | per item |
| **/killed** | Show today's gatekeeper refusals and why | no |
| **/why T [date]** | Two modes (D-20 tiered): for a name ON the plan → expand its FULL data anchor (every field the voices cited + values, the committee bear case + dissent); for a name NOT on the plan → why it didn't advance (committee PASS, event filter, gatekeeper refusal, any stage) | no |
| **/reject** | Reject today's plan outright (plan stands down) | it IS the confirm |
| **/pause** | Suspend the whole system: no scheduled runs, no alert wakes, autopilot disarmed. `/resume` restarts | no |
| **/flatten** | EMERGENCY: gatekeeper emits exit previews for ALL held names for you to execute | previews only — you execute |
| **/eod** | Alias of /close (post-market run) | no |
| **/srm** | Sector scorecard — feed's end-of-day sector block; during market hours ALSO runs the live pulse (srm_live) | no |
| **/ptj** | Print the trade journal in TODAY'S format — same fields, same scope (open + closed + metrics + broker sync). Heavy path, exact command only, exactly as before | no |
| **/hedge** | Run the hedge check on demand (coverage matrix; candidates if cover is short) — same as the old /hedge | no |
| **/later** | Defer a backlog item to tomorrow's summary | no |
| **/steer** | Show the pending steer file: FYI · DECIDE (your one-tap items, with days-pending) · PRE-FIX notices · POST-FIX results | per DECIDE item |
| **/findings** | Raw findings from the last review before bench triage | no |
| **/ops** | System liveness card (skills/ops-status): are the loops firing, is state fresh, are alert channels up — the SYSTEM sibling of /status. `/ops --render` writes the full dashboard. Read-only, places nothing | no |
| **/cockpit arm** | Make THIS session the live cockpit (skills/cockpit, D-76): render current state now + schedule `send_later` deliveries so each loop's result appears HERE, in the chat you're reading, instead of in an invisible fresh session. Self-perpetuates day to day; re-run once in any brand-new chat to re-establish. Display only, places nothing | no |
| **/cockpit status** | Is delivery currently covered? Reads data/cockpit/armed.json — which deliveries are pending today, and the standing across-session limitation stated plainly | no |
| **/recover [loop]** | Re-run a failed loop fresh (premarket · market-hours · post-market · eod-audit). Read/compute/plan only — a re-run that reaches execution still previews at the gate (D-45) | no |
| **/heal [loop] --failure T** | Run the auto self-heal protocol for a classified failure (transient→retry/reseed; structural→escalate; gate→stand down). Never places an order | no |
| **/repull [ptj]** | Re-fetch today's AQE export (revalidate + tripwires); `/repull ptj` re-pulls both brokers and refreshes dynCap | no |
| **/reseed [names]** | Force a historical-store seed (D-40) for missing/stale names | no |
Anything not on this list can still be said in plain English — commands are the fast path, not the only path.
