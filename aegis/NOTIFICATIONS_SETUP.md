# AEGIS — Notification & Self-Heal Setup

> ## ⛔ THIS GUIDE IS THE POST-MIGRATION (LOCAL BOX / KIMI) PATH — NOT FOR THE COWORK PILOT (D-46)
>
> **The pilot runs on Claude Cowork, where notifications are NATIVE — there is nothing to set up.**
> Each scheduled task carries its run message to your phone via Cowork's own **push notification**
> (`notifications.channel: cowork`). `notify.py` emits the message as the session's output and the
> task's push delivers it. `/ops` will show the channel as **cowork-native**. Do NOT wire WhatsApp,
> Twilio, healthchecks.io, Windows batch files, or `schtasks` for the pilot — none of them are used.
>
> Come back to everything below **only after** you decide to migrate off Cowork onto the local box
> (or Kimi), at which point you set `AEGIS_NOTIFY_CHANNEL=whatsapp` and follow these steps.

---

## PILOT (Claude Cowork) — the whole setup, in three lines
1. When you create the Phase-6 scheduled tasks (`create_trigger`), turn on each task's **push** notification.
2. That's it — run confirmations and the unmistakable failure page arrive on your phone automatically.
3. Ask for `/ops` any time for the live liveness card. (Optional: a small pre-run heartbeat task for the "starting soon, alive" ping.)

---

# ↓↓↓ POST-MIGRATION SETUP (local box / Kimi only — ignore for the pilot) ↓↓↓

**Goal:** switch on the WhatsApp pings + external dead-man's-switch in ~20 minutes, copy-paste, no coding.
Only relevant once you've migrated off Cowork. Until then the system runs fine on Cowork's native push.

You are switching on four things:
1. a **WhatsApp** channel (one-way alerts to your phone),
2. an **external watchdog** (so silence-because-the-box-died becomes an alarm),
3. the **secrets** that connect them (in the gitignored `config/.env`),
4. the **heartbeat** scheduled tasks (the T-minus-15 "system alive" pings).

---

## STEP 1 — Get a WhatsApp channel (pick ONE path)

### Path A — Twilio (fastest to TEST, ~5 min)
1. Create a free account at twilio.com → **Messaging → Try WhatsApp**.
2. Join the **WhatsApp Sandbox**: send the given code (e.g. `join xxxx-yyyy`) from your phone to Twilio's number. Your phone is now a permitted recipient.
3. From the console copy three values:
   - **Account SID** → goes in `TWILIO_SID`
   - **Auth Token** → goes in `TWILIO_TOKEN`
   - The sandbox **From** number, formatted `whatsapp:+14155238886` → `TWILIO_WHATSAPP_FROM`
4. Your own number goes in `WHATSAPP_TO`, formatted `whatsapp:+65XXXXXXXX`.

*(Sandbox is perfect for the pilot. For production, register a Twilio WhatsApp sender — same three values, no sandbox join step.)*

### Path B — Meta WhatsApp Cloud API (production, ~15 min)
1. developers.facebook.com → **Create App → Business → add WhatsApp**.
2. In WhatsApp → API Setup, copy the **temporary access token** → `WHATSAPP_TOKEN`, and the **Phone number ID** → `WHATSAPP_PHONE_ID`.
3. Add your phone as a **recipient** (verify the code Meta sends). Your number → `WHATSAPP_TO` as `+65XXXXXXXX` (no `whatsapp:` prefix for Meta).
4. For always-on, later swap the temporary token for a **permanent** System-User token (Business Settings → System Users). Everything else stays the same.

---

## STEP 2 — Get the watchdog (healthchecks.io, free, ~3 min)
1. Sign up at healthchecks.io.
2. **Add Check** → name it "Aegis heartbeat". Set **Period = 1 day**, **Grace = 1 hour** (adjust later to your tightest run gap).
3. Copy the check's **Ping URL** (looks like `https://hc-ping.com/<uuid>`) → `WATCHDOG_URL`.
4. Add your email/phone under **Notifications** so healthchecks pages *you* if a check-in is ever missed.

---

## STEP 3 — Paste the secrets into `config/.env`
Open `aegis/config/.env` (create it by copying `aegis/config/env.example` if it doesn't exist).
Fill in the lines for the path you chose. Example (Twilio):

```
TWILIO_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
WHATSAPP_TO=whatsapp:+65XXXXXXXX
WATCHDOG_URL=https://hc-ping.com/your-uuid-here
```

`.env` is gitignored — it is never committed. Never put these in any other file.

---

## STEP 4 — Create the heartbeat scheduled tasks (Windows)

Set the OptiPlex clock to **Singapore time** so the times below are literal.
Create two small batch files (Notepad → Save As, type = All Files).

**`C:\Aegis\heartbeat_premarket.bat`**
```bat
@echo off
cd /d C:\Aegis
python aegis\tools\notify.py pre_run --loop premarket --at "16:00 SGT" --dashboard http://localhost:8080
python aegis\tools\notify.py --checkin ok
```

**`C:\Aegis\heartbeat_postmarket.bat`**
```bat
@echo off
cd /d C:\Aegis
python aegis\tools\notify.py pre_run --loop post-market --at "04:05 SGT" --dashboard http://localhost:8080
python aegis\tools\notify.py --checkin ok
```

Register them in Task Scheduler (run these in an **Administrator** Command Prompt — 15 min before each run):
```cmd
schtasks /create /tn "Aegis Heartbeat Premarket"  /tr "C:\Aegis\heartbeat_premarket.bat"  /sc weekly /d MON,TUE,WED,THU,FRI /st 15:45
schtasks /create /tn "Aegis Heartbeat Postmarket" /tr "C:\Aegis\heartbeat_postmarket.bat" /sc weekly /d MON,TUE,WED,THU,FRI /st 03:50
```

> The T-15 times (15:45, 03:50) are 15 minutes before your premarket (16:00) and post-market (~04:05) runs — adjust if you move those. The run **confirmations** and **failure pages** need no task; the premarket and post-market skills emit them at the end of each run (steps 12 / 5). This heartbeat only sends the *pre-run "still alive"* ping and the watchdog check-in.

**Linux/Mac cron equivalent** (if you ever run there; times in the box's local TZ = SGT):
```cron
45 15 * * 1-5  cd /home/aegis && python3 aegis/tools/notify.py pre_run --loop premarket --at "16:00 SGT" && python3 aegis/tools/notify.py --checkin ok
50 03 * * 1-5  cd /home/aegis && python3 aegis/tools/notify.py pre_run --loop post-market --at "04:05 SGT" && python3 aegis/tools/notify.py --checkin ok
```

---

## STEP 5 — Test it (2 min, in order)
Open a terminal in `C:\Aegis` and run:

```cmd
python aegis\tools\notify.py pre_run --loop premarket --at "16:00 SGT" --dry-run
```
→ prints the message without sending. Confirm the text reads right.

```cmd
python aegis\tools\notify.py pre_run --loop premarket --at "16:00 SGT"
```
→ this one **sends** — check your phone gets the WhatsApp.

```cmd
python aegis\tools\notify.py run_fail --loop premarket --step "risk-gate check" --last-good "post-market 04:07"
```
→ confirm the **failure page looks unmistakably different** from the green ping (that's the point).

```cmd
python aegis\tools\notify.py --checkin ok
```
→ your healthchecks.io check turns **green**.

```cmd
python aegis\tools\ops_status.py
```
→ the `/ops` card should now show `alerts: whatsapp on · watchdog on`.

---

## VERIFICATION CHECKLIST
- [ ] WhatsApp pre-run ping arrived on my phone
- [ ] Failure page is visibly distinct from the green ping
- [ ] healthchecks.io check went green after `--checkin ok`
- [ ] healthchecks.io will email/SMS me if a check-in is ever **missed** (test by pausing the check)
- [ ] `/ops` shows both channels ON
- [ ] Both heartbeat tasks appear in Task Scheduler with the right next-run times
- [ ] `config/.env` is the ONLY place the secrets live (never committed)

Once every box is ticked, the self-heal loop is fully wired: transient failures heal quietly,
everything else pages you clearly with the exact `/recover`-family fix, and if the whole box
ever dies, the missing check-in is what raises the alarm.
