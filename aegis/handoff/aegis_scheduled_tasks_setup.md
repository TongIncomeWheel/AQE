# Aegis — Scheduled Tasks (create these in the Cowork app's own scheduler)

**Why native, not API:** the versions I created via the API run but don't surface a visible
child thread in your app. Tasks you create through the app's **Scheduled** feature do (you
confirmed you see those on both desktop and mobile). So we recreate them there.

**How to use:** in the Cowork app → Scheduled → New task. For each block below, paste the
**Prompt** and set the **When**. Turn **push notification ON** for each.

**Confirm first, then I clean up:** watch the FIRST premarket native run produce a visible
child thread. Once it does, tell me — I'll delete my invisible API duplicates so nothing
double-fires. Until you confirm, mine keep running as a backstop (invisible, but the work still
lands in git, so no trading day is missed).

**Days note:** if the app only offers "Weekdays" or "Daily" (no per-day picker), use **Daily**
for Post-market and Design & Review — that guarantees Saturday runs (which processes Friday's US
close); the harmless cost is one extra Monday run that simply finds no new session and no-ops.

**Token note:** each Prompt contains your GitHub token inline (a fresh scheduled session has no
credential otherwise). It's the same token already in your current tasks — still worth rotating
to a fine-grained, repo-scoped, contents-only PAT when you have a moment.

---

## 1 · Premarket build  ·  When: **10:00 SGT, Mon–Fri**

```
Aegis scheduled PREMARKET. You are a FRESH session with no workspace and no git credential. Reconstruct first (D-64), then run the phase.

STEP 0 — BOOTSTRAP. Run in bash exactly:
export AEGIS_PAT=<YOUR_GITHUB_PAT>
rm -rf /home/claude/AQE
git clone --depth 1 https://x-access-token:$AEGIS_PAT@github.com/TongIncomeWheel/AQE.git /home/claude/AQE
mkdir -p /home/claude/AQE/aegis/config
printf 'GITHUB_PAT=%s\n' "$AEGIS_PAT" > /home/claude/AQE/aegis/config/.env
cd /home/claude/AQE
git -C /home/claude/AQE config user.name Claude; git -C /home/claude/AQE config user.email noreply@anthropic.com
Confirm /home/claude/AQE/aegis/CONTEXT.md exists. If the clone failed, tell me it failed at bootstrap and STOP.

STEP 1 — Tiger MCP often reports "still connecting" on the first call; ToolSearch for Tiger and retry once before declaring it unavailable.

STEP 2 — Run the premarket process from /home/claude/AQE: read aegis/CONTEXT.md + the four aegis/charter/* files, run aegis/tools/preflight.py, then follow the premarket skill (universe, AQE pull with retry, held book, the 11-voice swarm, tally, event filter, deliberation, plan). Produce the Executive Action Plan. Place NO orders — previews only.

STEP 3 — Run aegis/tools/git_sync.py to commit + push today's SOD state. Then, as your FINAL chat message here, give me the plan headline in plain language: posture, dynCap, exits/adds, VaR/gate state, and "approve by 21:00 SGT." That closing message is what I actually see — do not end on a silent tool call.
```

---

## 2 · Plan approval checkpoint (NEW)  ·  When: **21:00 SGT, Mon–Fri**

```
Aegis 21:00 SGT APPROVAL CHECKPOINT. A short reminder run — reconstruct, read today's plan, nudge me to approve if I haven't.

STEP 0 — BOOTSTRAP. Run in bash exactly:
export AEGIS_PAT=<YOUR_GITHUB_PAT>
rm -rf /home/claude/AQE
git clone --depth 1 https://x-access-token:$AEGIS_PAT@github.com/TongIncomeWheel/AQE.git /home/claude/AQE
cd /home/claude/AQE
Confirm /home/claude/AQE/aegis/CONTEXT.md exists; if the clone failed, tell me and STOP.

STEP 1 — Read aegis/data/sod/<TODAY>/plan.json (today's date, SGT). 
- If it does NOT exist: tell me plainly "no plan generated today — premarket may have stood down; nothing to approve" and stop.
- If it exists: as your FINAL chat message, remind me clearly: "9pm checkpoint — today's Aegis plan is awaiting your approval. Under the missed-approval rule it stands down as DRAFT at 21:00 if not approved. If you've reviewed it and want it live, approve now." Then restate the plan headline in one or two lines (posture, the exits, the top ADVANCE names) so I can act straight from this reminder. If I've already approved earlier today, tell me to ignore this. Place nothing.
```

---

## 3 · Market-hours liveness  ·  When: **21:25 SGT, Mon–Fri**

```
Aegis scheduled MARKET-HOURS LIVENESS. Fresh session — reconstruct first, then confirm the alert engine is alive and sweep the inbox once.

STEP 0 — BOOTSTRAP. Run in bash exactly:
export AEGIS_PAT=<YOUR_GITHUB_PAT>
rm -rf /home/claude/AQE
git clone --depth 1 https://x-access-token:$AEGIS_PAT@github.com/TongIncomeWheel/AQE.git /home/claude/AQE
mkdir -p /home/claude/AQE/aegis/config
printf 'GITHUB_PAT=%s\n' "$AEGIS_PAT" > /home/claude/AQE/aegis/config/.env
cd /home/claude/AQE
Confirm /home/claude/AQE/aegis/CONTEXT.md exists; if the clone failed, tell me and STOP.

STEP 1 — Run the market_hours process (read aegis/CONTEXT.md + charter first): confirm liveness (alert engine reachable, held book loads), then sweep aegis/data/alerts/<TODAY>/inbox.jsonl with tools/alert_inbox.py — held-book stop/approach alerts page me immediately; opportunity survivors go to the 3-lens pod and page me only on a CONFIRM that clears the concentration gate; the rest is logged. Place nothing unless autopilot is armed within caps. As your FINAL chat message, tell me the liveness result and anything that paged.
```

---

## 4 · Post-market  ·  When: **05:05 SGT, Tue–Sat (or Daily — see days note)**

```
Aegis scheduled POST-MARKET. Fresh session — reconstruct first, then run the phase and push state.

STEP 0 — BOOTSTRAP. Run in bash exactly:
export AEGIS_PAT=<YOUR_GITHUB_PAT>
rm -rf /home/claude/AQE
git clone --depth 1 https://x-access-token:$AEGIS_PAT@github.com/TongIncomeWheel/AQE.git /home/claude/AQE
mkdir -p /home/claude/AQE/aegis/config
printf 'GITHUB_PAT=%s\n' "$AEGIS_PAT" > /home/claude/AQE/aegis/config/.env
cd /home/claude/AQE
git -C /home/claude/AQE config user.name Claude; git -C /home/claude/AQE config user.email noreply@anthropic.com
Confirm /home/claude/AQE/aegis/CONTEXT.md exists; if the clone failed, page me (run_fail) and STOP.

STEP 1 — Tiger MCP may need a ToolSearch retry before it's up. Then run the post_market process from /home/claude/AQE: read aegis/CONTEXT.md + charter, run aegis/tools/preflight.py, follow the post_market skill (journal + PTJ to Drive, metrics, archive-ledger, audit, Drive-PTJ check, flow audit). Place nothing.

STEP 2 — Run aegis/tools/git_sync.py to commit + push. Then, as your FINAL chat message, give me the day's headline: dynCap, realised/unrealised P&L, journal status, any exceptions or pages. Do not end on a silent tool call.

NOTE: this fires 05:05 SGT, not 04:05, on purpose — it stays after the US close in BOTH daylight-saving states, so it never needs changing twice a year.
```

---

## 5 · Design & Review  ·  When: **08:00 SGT, Tue–Sat (or Daily — see days note)**

```
Aegis scheduled DESIGN & REVIEW. Fresh session — reconstruct first, then run the review.

STEP 0 — BOOTSTRAP. Run in bash exactly:
export AEGIS_PAT=<YOUR_GITHUB_PAT>
rm -rf /home/claude/AQE
git clone --depth 1 https://x-access-token:$AEGIS_PAT@github.com/TongIncomeWheel/AQE.git /home/claude/AQE
mkdir -p /home/claude/AQE/aegis/config
printf 'GITHUB_PAT=%s\n' "$AEGIS_PAT" > /home/claude/AQE/aegis/config/.env
cd /home/claude/AQE
git -C /home/claude/AQE config user.name Claude; git -C /home/claude/AQE config user.email noreply@anthropic.com
Confirm /home/claude/AQE/aegis/CONTEXT.md exists; if the clone failed, tell me and STOP.

STEP 1 — Run the design_review process: read aegis/CONTEXT.md + charter, review the day's processes and health, land any change proposals in the STEER file for my approval. Change nothing without my nod. Push any state with aegis/tools/git_sync.py. As your FINAL chat message, summarise what you reviewed and any proposals awaiting my decision.
```

---

## 6 · Weekly review + janitor  ·  When: **06:00 SGT, Sunday**

```
Aegis scheduled WEEKLY. Fresh session — reconstruct first, then run the weekly process.

STEP 0 — BOOTSTRAP. Run in bash exactly:
export AEGIS_PAT=<YOUR_GITHUB_PAT>
rm -rf /home/claude/AQE
git clone --depth 1 https://x-access-token:$AEGIS_PAT@github.com/TongIncomeWheel/AQE.git /home/claude/AQE
mkdir -p /home/claude/AQE/aegis/config
printf 'GITHUB_PAT=%s\n' "$AEGIS_PAT" > /home/claude/AQE/aegis/config/.env
cd /home/claude/AQE
git -C /home/claude/AQE config user.name Claude; git -C /home/claude/AQE config user.email noreply@anthropic.com
Confirm /home/claude/AQE/aegis/CONTEXT.md exists; if the clone failed, tell me and STOP.

STEP 1 — Run the weekly process (parameter/criteria review, AQE contract review, historical-layer maintenance + hygiene janitor). Proposals to the STEER file; change nothing without my nod. Push with aegis/tools/git_sync.py. As your FINAL chat message, give me the weekly summary + anything awaiting my decision.
```

---

### After you confirm the first native run surfaces a child thread
Tell me and I'll delete these API-created duplicates so nothing double-fires:
premarket v3, post-market v3, design & review v1, market-hours liveness v1, weekly+janitor v1.
(The two non-Aegis ones — "IBKR 30-Day Holding Countdown" and "Active Pot Daily CSP Scan" — are
yours from before this project; I won't touch them.)
