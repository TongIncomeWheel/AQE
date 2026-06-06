# AQE Cloud Deployment

Two free-tier targets are supported. Same source code, same `streamlit_app.py`
entrypoint, different host trade-offs:

| Host | Sleep timeout | RAM | Disk persistence | Recommended for |
|---|---|---|---|---|
| **Hugging Face Spaces (free)** | ~48 hr idle | **16 GB** | Ephemeral (5 GB persistent = $5/mo upgrade) | Single-user, infrequent visits — **best free option** |
| Streamlit Community Cloud | ~12-24 hr idle | 1 GB | Ephemeral | Quick prototypes |

Both run the daily pipeline themselves so the app works even when your laptop
is off.

Jump to:
- [Hugging Face Spaces (recommended)](#hugging-face-spaces-recommended)
- [Streamlit Community Cloud (alternative)](#streamlit-community-cloud-alternative)

---

## Hugging Face Spaces (recommended)

### Why HF over Streamlit

- **48-hour idle window** (vs Streamlit's ~12-24h) — single visit every two
  days keeps the container warm.
- **16 GB RAM** (vs 1 GB) — pandas pipeline has 40× headroom.
- **2 vCPU** (vs 1) — pipeline rebuilds faster.
- **50 GB ephemeral disk** — parquet caches sit easily.

The trade-off: HF's free tier ephemeral disk wipes when the Space is asleep
or rebuilt, exactly like Streamlit. On a cold start the pipeline has to
refetch from FMP (3-5 min). But with the longer sleep window you hit this
less often. Add HF's $5/month persistent storage (5 GB at `/data`) and the
cache survives restarts forever; AQE auto-picks it up via `AQE_DATA_DIR`.

#### One-time setup

1. **Sign up for Hugging Face** at <https://huggingface.co/join> (free, takes
   30 seconds — email + password).
2. **Create a new Space**:
   - <https://huggingface.co/new-space>
   - Owner: your account
   - Space name: e.g. `aqe-scanner`
   - License: pick one (MIT is fine for personal use)
   - SDK: **Streamlit**
   - Hardware: **CPU basic — free**
   - **Visibility**: Private (recommended) or Public — your choice
   - Click **Create Space**.
3. **Set your FMP secret**:
   - In the new Space, click **Settings** (top right) → **Variables and
     secrets** → **New secret**.
   - Name: `FMP_API_KEY`
   - Value: paste from your local `.env`.
   - Save.
3b. **Set the app password (REQUIRED if the Space is Public)**:
   - The Space is public, so lock the whole app behind a single password at
     the front door. Nothing loads until the password is entered.
   - **Settings → Variables and secrets → New secret**.
   - Name: `AQE_APP_PASSWORD`
   - Value: any password you choose.
   - Save, then restart the Space.
   - Effect: when this secret is present, every page shows a sign-in screen
     first; after one correct entry the session is unlocked (all pages).
     Locally (no secret) the app opens with no friction — `run_app.bat` is
     unchanged.
   - **Automation is unaffected.** The 9am scheduled job runs the pipeline
     directly (`python -m src.pipeline.daily_orchestrator`, or via Claude
     dispatch / a scheduled app call) and never goes through this UI gate, so
     Drive writes keep working unattended.
4. **(Optional) Enable persistent storage** if you want the cache to survive
   sleeps. **Settings → Variables and secrets → Persistent storage** → enable
   5 GB ($5/month). Then add two more *variables* (NOT secrets — variables
   are visible to the app at boot):
   - `AQE_DATA_DIR` = `/data`
   - `AQE_OUTPUT_DIR` = `/data/output`
5. **Push the code to your HF Space**:
   - Each Space has a git remote URL shown at the top of the Space page,
     usually `https://huggingface.co/spaces/<your-user>/<space-name>`.
   - From your local repo:
     ```bash
     git remote add hf https://huggingface.co/spaces/<your-user>/<space-name>
     git push hf main
     ```
   - HF asks for an access token (not your password). Generate one at
     <https://huggingface.co/settings/tokens> with **write** scope. Use it
     as the password when git prompts.

### Daily push workflow

After the first push, your local repo has two remotes:

```bash
git remote -v
# origin    https://github.com/TongIncomeWheel/AQE.git   (private GitHub)
# hf        https://huggingface.co/spaces/<user>/<space> (HF Space)

# After making changes locally:
git add <files>
git commit -m "..."
git push                # pushes to origin (default = GitHub)
git push hf main        # pushes to HF, which redeploys the Space
```

Or push to both in one command:
```bash
git push origin main && git push hf main
```

### What you'll see on HF

After `git push hf main` triggers a deploy, the Space rebuilds (~2-4 min for
first build, ~30s on code-only updates). Visit `https://<user>-<space>.hf.space`
(URL shown on the Space page).

The Scanner page renders identically to your local app. Cloud-mode detection
(`is_cloud_mode()`) still fires because the parquets aren't in the repo. The
sidebar shows "Cloud mode" + the bootstrap button. Click it → 3-5 min FMP
fetch → done.

If you enabled persistent storage with `AQE_DATA_DIR=/data`, the parquets
land in `/data/` and survive restarts indefinitely. Cold start after sleep
is then a sub-30-second event (just re-reads from disk).

### Cloud → Google Drive sync (optional but recommended)

Locally AQE writes `aqe_daily_export.json` to `G:\My Drive\Trading Strategy\AQE\`
where Google Drive Desktop picks it up. On HF the cloud container has no `G:`
drive — you wire OAuth so the cloud uploads the JSON via Drive's REST API into
the same Drive folder. The result is your Claude native (or anything else that
reads from Drive) sees the same file regardless of whether AQE ran locally or
in the cloud.

#### Step-by-step (one-time, ~10 min)

1. **Create a Google Cloud project** (free):
   <https://console.cloud.google.com/projectcreate> — any name, no billing.

2. **Enable Google Drive API**:
   GCP Console → **APIs & Services → Library** → search "Google Drive API"
   → **Enable**.

3. **Configure the OAuth consent screen**:
   **APIs & Services → OAuth consent screen** → choose **External** → fill
   only the required app-name/email fields → **Save**.
   Add your own Google email under **Test users** (only Test users can grant
   consent while the app is in "Testing" mode, which is fine for personal use).

4. **Create the OAuth Client ID**:
   **APIs & Services → Credentials → Create Credentials → OAuth Client ID**
   - Application type: **Desktop app**
   - Name: e.g. "AQE Drive uploader"
   - Click **Create** → **Download JSON**.
   - Save the downloaded file as `client_secret.json` in the project root
     (`C:\Users\ashtz\Backtest Engine\client_secret.json`). It's already
     gitignored.

5. **Run the one-time setup helper**:
   Double-click **`setup_gdrive.bat`** at the project root. A browser tab
   opens → click **Allow** to grant Drive access to your AQE app. The helper
   then prints THREE secrets you paste into HF Space settings.

6. **Paste secrets into HF**:
   <https://huggingface.co/spaces/AQE-Aegis/aqe/settings> → **Variables and secrets**:

   | Type | Name | Value |
   |---|---|---|
   | Secret | `GOOGLE_OAUTH_CLIENT_ID` | from helper output |
   | Secret | `GOOGLE_OAUTH_CLIENT_SECRET` | from helper output |
   | Secret | `GOOGLE_OAUTH_REFRESH_TOKEN` | from helper output |
   | Variable | `GDRIVE_FOLDER_PATH` | `Trading Strategy/AQE` |

   (Use `GDRIVE_FOLDER_ID` instead of `GDRIVE_FOLDER_PATH` if you know the
   folder ID — last URL segment when you open the folder in Drive's web UI.)

7. **Restart the Space**: any push triggers a rebuild, OR Settings → **Factory rebuild**.

8. **Verify**: open the Scanner sidebar → **Cloud diagnostics** → scroll to
   "Google Drive sync" → click **Test Drive credentials**. Should print
   `Drive OK -- auth'd as <your email>`.

#### Behaviour after setup

- Local PC + cloud both export to `Trading Strategy/AQE/aqe_daily_export.json`.
- The cloud always uses the same file ID (replaces in place), so Claude native
  doesn't see broken links between exports.
- If the OAuth token is ever revoked or expires (very rare for refresh tokens),
  re-run `setup_gdrive.bat` to capture a fresh one.

#### What this does NOT do

- Doesn't sync the local data parquets to Drive — only the export JSON.
- Doesn't read FROM Drive — the cloud doesn't pull anything from your account.
- Doesn't affect AIC / NiceGUI briefs (those don't write to Drive).

---

## Streamlit Community Cloud (alternative)

This is the **active-cloud setup**: the Streamlit Cloud app runs the daily
pipeline itself. Free tier, single public-URL endpoint, your FMP key as the
only secret.

### Architecture

```
LOCAL (your Windows PC)             GITHUB (private repo)         STREAMLIT CLOUD (free)
─────────────────────────           ─────────────────────         ─────────────────────────
run_app.bat                         streamlit_app.py              streamlit_app.py
  → desktop Streamlit                 + src/ (engines, scanner,     → bridges st.secrets
  → reads/writes local                  pipeline, analyzer, ui)       to os.environ
    data/*.parquet                                                  → runs Scanner page
                                                                    → "Run daily pipeline"
                                                                       button kicks off
                                                                       FMP fetch + scoring
                                                                       in the cloud container
                                                                  
                                                                  Cold start: ~3-5 min
                                                                    (490 tickers × FMP)
                                                                  Subsequent same-session:
                                                                    seconds (incremental)
                                                                  Container idle ~30 min
                                                                    → cold again next visit
```

The cloud is **stateful per session** but the container's filesystem is
ephemeral. When Streamlit's auto-sleep fires (~30 min idle) the cached
parquets disappear; the next visit needs another pipeline run. With <5
visits/day you'll typically pay one ~3-5 min wait per day.

### Page behaviour on the cloud

| Page | Cloud behaviour |
|---|---|
| **1 Scanner** | Full functionality. Sidebar shows "Cloud mode" + a `Bootstrap + run daily pipeline` button. After it runs, every section (regime, SRM, Precision Edge, longlist, watchlist, ad-hoc scorer) works normally. |
| **2 Math Lab** | Works AFTER you've run the pipeline at least once in the session. Asks you to run Scanner first if parquets aren't built yet. |
| **3 Positions** | Disabled on cloud. Needs `data/open_positions.json` which is gitignored (stays on your local PC). |
| **4 Scheduler** | Errors gracefully — uses Windows Task Scheduler, not available on Linux. |
| **5 AIC** | UAT page for the AIC committee — works (reads SQLite + export JSON). |

### One-time setup

#### 1. Push the repo to GitHub

Already done if you've reached this point: <https://github.com/TongIncomeWheel/AQE>.
For a fresh clone:

```bash
git init -b main
git add .
git commit -m "Initial AQE commit"
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```

`.gitignore` is wired to keep parquets, SQLite, real positions and `.env`
out of git. Verify:

```bash
git status              # should not list scores_daily.parquet or .env
git ls-files | head     # should list streamlit_app.py + src/ + output/aqe_daily_export.json
```

#### 2. Deploy to Streamlit Community Cloud

1. Sign in at <https://share.streamlit.io> with the GitHub account that owns
   the private repo.
2. Click **"New app"**.
3. Pick your repo → branch `main` → main file `streamlit_app.py`.
4. **Advanced settings**:
   - **Python version**: 3.11 or 3.12.
   - **App URL** (optional): pick a slug like `aqe`.
5. **Don't deploy yet** — set secrets first (next step), then deploy.

#### 3. Add your FMP key as a Streamlit secret

1. In the new-app dialog (or after, via **Settings → Secrets**), paste:

   ```toml
   FMP_API_KEY = "fmp_xxx_your_real_key_here"
   ```

   Replace with the value from your local `.env` file.

2. Save. Streamlit redeploys automatically.

That's the only secret AQE itself needs. AIC LLM features (Anthropic key)
are optional and stay disabled on cloud unless you also add `ANTHROPIC_API_KEY`.

#### 4. First run

1. Open the app URL (e.g. `https://aqe.streamlit.app`).
2. Sidebar shows "Cloud mode" badge.
3. Click **Bootstrap + run daily pipeline**.
4. Live log stream appears. You'll see lines like `[daily] 1/491 AAPL`.
5. After ~3-5 min the page refreshes with regime, SRM, longlist, etc.

### Daily workflow

```
You open the app URL on phone or laptop.
   ↓
If first visit of the day (or container slept):
   → click "Run daily pipeline" → wait 3-5 min → done for the day
If you used it within ~30 min before:
   → already warm, click "Run daily pipeline" → seconds (incremental)
   → or just read the current data, no re-run needed
```

### Universe management

The universe lives in `data/universe.txt` and IS committed. To change the
universe:

**From local PC** (recommended):
1. Edit `data/universe.txt` or upload a new CSV via the desktop AQE app.
2. Commit + push the change.
3. Cloud will pick it up on next deploy. Next pipeline run uses the new universe.

**From cloud directly**:
- The Scanner sidebar's **Universe Upload** works on cloud too — but the
  change only lives in the cloud container's ephemeral disk. When the
  container restarts, it reverts to whatever is in git.

### Secrets you might add later

These are NOT required for the AQE scanner; only if you re-enable specific features:

| Secret | Enables |
|---|---|
| `ANTHROPIC_API_KEY` | AIC LLM committee (Page 5 in deeper modes) |

A template lives at `.streamlit/secrets.toml.example`.

### RAM, CPU and rate-limit reality

- **RAM**: Streamlit free tier is 1 GB. After a full pipeline run, the panel
  + scores DataFrames hold ~300-400 MB. Headroom is tight but OK for one user.
- **CPU**: 1 CPU. Pipeline takes ~3-5 min wall-clock against FMP's rate limit.
- **FMP**: Starter plan = 300 calls/min. AQE caps itself at 250 to leave headroom.
  Same key on cloud + local is fine for personal use; you'll never come close
  to the per-day cap.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "FMP_API_KEY is not set in Streamlit secrets" | Secret not configured | Settings → Secrets → paste `FMP_API_KEY = "..."` |
| Pipeline exits with FMPError | Wrong key, expired key, or hit rate limit | Verify key in FMP dashboard; copy fresh into Streamlit secrets |
| App boots but Scanner shows "Cold start" | Container was asleep; parquets gone | Click **Bootstrap + run daily pipeline** |
| Cloud OOM (Streamlit restarts) | 1 GB cap exceeded | Cut universe size or remove unused engines; surface to dev |
| Cloud app sleeps too aggressively | Streamlit's idle policy | Bookmark + visit it once a few times a day; or click any button to keep warm |
| Push fails on `git push` | Credentials not cached | Run `first_push.bat` once in a real cmd window |

### Adding a new dependency

If you `import` something new that runs on cloud:

1. `pip install <pkg>` locally.
2. Add it to `requirements.txt` (pin to a major version).
3. Commit + push. Streamlit Cloud reinstalls on next deploy (~30s for small deps).

### What stays local-only (by design)

- Your real `data/open_positions.json` — Position Manager only on desktop.
- The full `data/scores_daily.parquet` (137 MB) — too big for git; cloud
  rebuilds it from FMP on demand.
- AIC SQLite + Anthropic key — LLM committee runs locally unless you wire it.
- The NiceGUI brief frontend (`src/aic/web/`) — separate process, not Streamlit.

### Rollback

If something on `main` breaks the cloud app:

```bash
git revert <bad-commit-sha>
git push
```

Streamlit Cloud auto-redeploys the reverted state in ~30 s.
