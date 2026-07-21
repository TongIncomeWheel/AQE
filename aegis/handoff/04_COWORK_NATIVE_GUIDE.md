# AEGIS — RUNNING ON CLAUDE COWORK NATIVELY (THE BASELINE OPERATING GUIDE)
**How to operate Aegis today, on Cowork, honestly · 21 Jul 2026**

This is the baseline for running Aegis on Claude Cowork **as it is** — not fully automated, but
workable for a live book — while the persistent-runtime sourcing (`02_RUNTIME_INFRA_REQUIREMENTS.md`)
proceeds in parallel. It is written to be honest about what works, what doesn't, and the one experiment
worth trying (a loop with conversation state).

---

## 1. THE HONEST BASELINE (what Cowork can and cannot do)

Verified against Anthropic's own documentation (21 Jul):

**Works:**
- Scheduled tasks (cron) fire fresh sessions that bootstrap, run a loop, and **push real state to
  git**. Compute and persistence are solid.
- Scheduled-task output appears in the **"Scheduled" section of the sidebar** — each run is its own
  session you click into. (Reliable on desktop; mobile visibility of scheduled results is undocumented
  and has been unreliable in practice.)
- Any fresh chat with the plugin can **pull** the latest state from git and render it (`/status`,
  `/ops`, `/plan`) — correct in any window because it reads files, not chat memory.

**Cannot do (documented limitations):**
- **No session-binding:** a scheduled loop cannot post into one fixed conversation — every fire is a
  separate session.
- **No persistent interactive cockpit:** a chat is finite and fragments across days; a dashboard
  artifact is display-only (cannot take your input back to the agent).
- **No documented "cockpit" pattern.** So a single always-there, two-way, proactive thread is not
  natively available.

**Implication:** on Cowork today you operate a **pull cockpit + scheduled compute**, with a small set
of scheduled threads you check. It is not the one-thread agentic cockpit — that needs the sourced
runtime.

---

## 2. THE DAILY OPERATING RHYTHM (native, practical)

Times are SGT. Treat **desktop Cowork as the reliable surface**, especially for approvals.

| When | You do | Where |
|---|---|---|
| Morning (after 10:00 premarket fires) | Open the **Premarket** scheduled run in the Scheduled sidebar → read the plan | Scheduled thread (desktop) |
| Any time | In a chat, ask `/status` (book), `/ops` (machine), `/plan`, or "why did X advance" | Any Cowork chat (pull) |
| By 21:00 | **Approve/edit/reject** the plan — reply in the premarket run thread, or state it in your control chat | Scheduled thread / control chat |
| 21:00 | **Approval checkpoint** reminder fires (native task) — nudges if unapproved | Scheduled thread |
| 21:30–04:00 | Intraday: held-book risk pages + pod-confirmed runner pages arrive from the market-hours loop | Scheduled thread / push |
| Next morning 05:05 | Post-market has journaled + pushed; read the EOD summary on demand | Pull via `/status` or the post-market run |

**Set up the schedule natively (for visible threads):** create the loops through the Cowork app's own
"Scheduled" feature (not only via the API), because API-created tasks have surfaced unreliably. The
ready-to-paste prompts + times for all loops **and the 21:00 approval checkpoint** are in
`aegis_scheduled_tasks_setup.md` (delivered separately; also summarised in `SCHEDULERS.md`). Turn push
notifications ON for each.

---

## 3. THE CONTROL-CHAT PATTERN (your interactive surface today)

Keep ONE Cowork chat open as your "control desk." Because every command reads git, this chat is a full
cockpit on demand:
- `/status` — the book (positions, P&L, armed state, plan headline)
- `/ops` (or `/ops --render` for the HTML flight-recorder) — did the loops fire, is state fresh
- `/plan` — today's plan; ask follow-ups ("show the bear case on FBP", "the 56-name alert universe")
- `/recover [loop]` — re-run a loop on demand; `/repull` — re-pull the AQE feed
- `/cockpit arm` — (experimental, see §4) route loop outputs into this chat via send_later

This chat compacts in place when full (it stays one thread), so it is durable within a session; it does
NOT survive being closed and replaced. When you start a fresh chat, it reconstitutes full state from
git instantly — you lose only the conversational thread, never the book.

---

## 4. THE EXPERIMENT WORTH TRYING — A LOOP WITH CONVERSATION STATE

The one way to approximate a persistent interactive cockpit on Cowork *within a session* is the
`send_later` self-perpetuation pattern (`/cockpit arm`, D-76):

**Mechanism.** `send_later` delivers a message back into THIS session at a future time — it is the only
Cowork primitive that targets the current conversation (proven: the check-in messages landed here). So
`/cockpit arm`:
1. Renders current state now.
2. Schedules a `send_later` a few minutes after each loop's cron pushes (post-market 05:25, D&R 08:20,
   premarket 10:40 SGT).
3. When each fires INTO this session, it pulls fresh git state, renders the result HERE, and re-arms
   tomorrow's — self-perpetuating.

**What it buys you.** Within one living session, loop results appear in your one chat instead of only
in separate scheduled threads.

**The honest limit.** A `send_later` chain is bound to its session. It survives the session compacting
("getting full") but NOT the session being truly closed/replaced. There is no API to inject into a
session that doesn't exist yet. So: **within a session it works; across a brand-new chat you re-run
`/cockpit arm` once.** Because compute+git are durable, nothing is lost in the gap.

**If you can crack a genuinely durable loop-with-state on Cowork** (e.g. one session kept alive
indefinitely via `ScheduleWakeup`, surviving compaction across days), that is the closest Cowork gets
to the sourced runtime — worth testing empirically before relying on it. Do not assume it holds across
a true session boundary until observed.

---

## 5. GUARDRAILS WHILE OPERATING NATIVELY

- **Approvals on desktop.** Given mobile scheduled-thread visibility is unreliable, do the 21:00
  approval where you can see the plan for certain — desktop.
- **Silence = stood down.** If you see no plan by 21:00, it stands down as DRAFT and nothing trades
  (UX-F3). Absence of a notification is itself a signal — pull `/ops` to check the machine ran.
- **The book is never at risk from the cockpit gap.** Held positions are protected by broker-side stops
  and the post-market journal regardless of whether you saw a thread. The gap is *visibility*, not
  *safety*.
- **Rotate the git PAT.** It currently rides inline in trigger prompts (the only channel a fresh
  container reads). Move to a fine-grained, repo-scoped, contents-only PAT; and this is a reason to
  prioritise the sourced runtime's secret vault (T2).
- **Watch the usage cap.** On a Max-5x plan the daily 11-opus swarm is heavy; a mid-swarm cap hit is
  detected (D-72) but the real fix is metered API billing on the sourced runtime (O1).

---

## 6. WHAT TO REVISIT ONCE THE RUNTIME IS SOURCED

When the persistent runtime lands, this native mode is retired in favour of the one-thread cockpit.
Until then: **scheduled compute runs the book, git holds the truth, and you pull/approve from a control
chat + the scheduled threads.** That is a workable baseline for a live book — imperfect on visibility,
sound on safety and correctness.
