# AEGIS — SCHEDULED TASKS (the clock)

Five scheduled tasks run the daily cycle. Each fires a fresh cloud session, so every prompt
starts with the same workspace-setup step, then runs one process skill, pushes state, and sends
one notification. Cron is written in UTC (SGT = UTC+8). Push notifications are ON for all tasks.

## Live schedule

| Task | SGT | Cron (UTC) | Trigger ID |
|---|---|---|---|
| Post-market | 05:05 Tue–Sat | `5 21 * * 1-5` | `trig_01FWqohNLAnML72pnYCgvdc6` |
| Design & Review | 08:00 Tue–Sat | `0 0 * * 2-6` | `trig_013Qq5WzkyrzSY29BNthWYbq` |
| Premarket build | 10:00 wkdays | `0 2 * * 1-5` | `trig_01CNrP3NWF5EqNyyuRyViy2U` |
| Market-hours watch | 21:25 wkdays | `25 13 * * 1-5` | `trig_01MjvFDC4Yd94cdk6U5rAu7S` |
| Weekly + janitor | Sun 06:00 | `0 22 * * 6` | `trig_01XTADWmyCZSbT4C4qtSz9eu` |

Daily order: post-market 05:05 → design & review 08:00 → premarket 10:00 → PM approves the plan
by 21:00 → market-hours watch fires 21:25 and self-rearms every 30 min (ScheduleWakeup) until the
04:00 SGT close → post-market next morning.

Post-market is pinned at 05:05 SGT because that sits after the US close in both DST states
(close = 04:00 SGT under EDT, 05:00 SGT under EST). Do not move it earlier.

The market-hours task is the session host: one fire at 21:25 SGT for liveness, then ScheduleWakeup
re-fires the sweep every 30 min until 04:00 SGT. The 15-min intraday polling itself is the AQE
alert engine's job (it writes `data/alerts/DATE/inbox.jsonl`); sessions sweep the inbox, they do
not poll prices (RB:schedule.market_watch_mode).

## Prompt template

Every trigger prompt follows this shape. `<GITHUB_PAT>` is the real fine-grained PAT
(Contents: Read+Write on TongIncomeWheel/AQE); it lives only in the trigger prompts and
`config/.env`, never in this repo.

```
Aegis <PROCESS>.

1. Workspace setup — scheduled sessions start empty. Run in bash:
export AEGIS_PAT=<GITHUB_PAT>
rm -rf /home/claude/AQE
git clone --depth 1 https://x-access-token:$AEGIS_PAT@github.com/TongIncomeWheel/AQE.git /home/claude/AQE
mkdir -p /home/claude/AQE/aegis/config
printf 'GITHUB_PAT=%s\n' "$AEGIS_PAT" > /home/claude/AQE/aegis/config/.env
cd /home/claude/AQE
git config user.name Claude; git config user.email noreply@anthropic.com
Verify aegis/CONTEXT.md exists. If the clone failed, send a run_fail notification and stop.

2. If Tiger MCP shows as still connecting, load it via ToolSearch and retry once before
treating it as unavailable.

3. Read aegis/CONTEXT.md and the aegis/charter/ files, then run the <process> skill.
Read, compute, propose only — no orders, no unapproved changes.

4. Push with aegis/tools/git_sync.py, then send one notification with the run summary
(run_fail if the run could not complete).
```

## Per-task specifics (step 3 of each prompt)

- **Premarket** — first pull `aqe_daily_export.json` from the Drive folder "AQE"
  (id `1CJMoI19Zf_ZFeU5_5uhW9l92IB8fVger`) into `aegis/output/`; verify its `date` is today or
  T-1; if stale, retry at ~5/10/10 min (3 attempts) then run_fail and stop — never run the voices
  on a stale or thin universe. Then run preflight + the premarket skill in full: universe,
  held-book review (exits first), all 11 voices in isolation, tally + event filter + weather,
  committee-desk deliberation, Executive Action Plan. The swarm always runs — a portfolio breach
  caps verdicts, never skips the voices. Notify with the plan headline (ready 16:00 SGT,
  approval due 21:00 SGT).
- **Market-hours watch** — confirm liveness, sweep the alert inbox via `tools/alert_inbox.py`;
  held-book stop/approach alerts page immediately; pod CONFIRMs that clear the concentration gate
  page; everything else logs. Before 04:00 SGT, rearm via ScheduleWakeup (1800s, same prompt);
  at/after 04:00 send the end-of-session summary and stop.
- **Post-market** — preflight, then the post_market skill: broker pulls, journal, dynCap roll,
  SL audit, metrics, completeness audit, flow audit, Drive-PTJ freshness check.
- **Design & Review** — the design_review skill: performance scoring, learning pass,
  engineering-bench triage; all proposals land in the STEER file.
- **Weekly** — `tools/janitor.py` first, then the weekly skill: posture, per-voice ledger
  performance, universe churn, stale rulebook keys, historical-layer maintenance; proposals to
  the STEER file.

## Notes

- `tools/bootstrap.py` encodes the workspace-setup contract for in-code use; the PAT itself
  travels only in the trigger prompt and `config/.env`.
- To change a prompt: `update_trigger` with the new text. Keep this file and the live triggers
  in sync.
- Standing hygiene item: rotate the PAT to a fresh fine-grained, repo-scoped, contents-only
  token periodically.
- Verify after any change: `list_triggers` shows the five tasks with correct next-run times;
  on the next fire, confirm the phone push arrived and `/ops` shows the loop as run.
