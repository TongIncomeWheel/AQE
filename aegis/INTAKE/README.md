# INTAKE — what the PM actually still supplies (short list, final)
1. **GitHub → private + token.** On github.com: repo Settings → General → Danger Zone → "Change visibility" → Private. Then: your avatar → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate: Resource owner = you · Repository access = ONLY TongIncomeWheel/AQE · Permissions = Contents: **Read and write** (nothing else) · Expiry 90 days. Paste the token into a working session when I need to push/pull — I use it and never write it anywhere. Your PC authenticates separately via your normal GitHub login (credential manager) — nothing extra needed there.
2. **Tiger connector URL** (Kimi adapter only — Claude works today with zero action). claude.ai → Settings → Connectors → Tiger MCPv7 → copy the server URL → one line into `config/endpoints.json`. The service itself stays on Google Cloud untouched (PM ruling: more secure there).
3. **PC .env file** (never uploaded, lives only on the PC): FMP_API_KEY · ALPACA_API_KEY / ALPACA_SECRET_KEY (**rotate these — the old skill file had them hardcoded**) · IBKR account id if used. Template: config/env.example.
4. **IBKR decision:** run Client Portal Gateway on the PC (needed on Kimi) or stay on Claude's built-in connector until cutover.
5. **PC OS confirm** (Windows assumed) → I generate the Task Scheduler entries.
6. **Drive mirror decision:** GitHub daily archive is primary (D-9); keep rclone→Drive as second mirror, or skip.

Resolved & closed: ~~Charter v3.0~~ (D-10 — not needed, see decisions log) · ~~Tiger/Alpaca/FMP source~~ (self-located: Alpaca client + FMP usage already in kernel; Tiger stays cloud-side) · ~~CS weekly~~ (drop folder live) · ~~AQE repo~~ (public URL known; item 1 makes it private).
