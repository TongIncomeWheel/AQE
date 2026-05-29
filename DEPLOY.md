# AQE Cloud Deployment

This is the active-cloud setup: the **Streamlit Cloud app runs the daily
pipeline itself** so it works even when your laptop is off. Free tier, single
public-URL endpoint, your FMP key as the only secret.

## Architecture

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

## Page behaviour on the cloud

| Page | Cloud behaviour |
|---|---|
| **1 Scanner** | Full functionality. Sidebar shows "Cloud mode" + a `Bootstrap + run daily pipeline` button. After it runs, every section (regime, SRM, Precision Edge, longlist, watchlist, ad-hoc scorer) works normally. |
| **2 Math Lab** | Works AFTER you've run the pipeline at least once in the session. Asks you to run Scanner first if parquets aren't built yet. |
| **3 Positions** | Disabled on cloud. Needs `data/open_positions.json` which is gitignored (stays on your local PC). |
| **4 Scheduler** | Errors gracefully — uses Windows Task Scheduler, not available on Linux. |
| **5 AIC** | UAT page for the AIC committee — works (reads SQLite + export JSON). |

## One-time setup

### 1. Push the repo to GitHub

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

### 2. Deploy to Streamlit Community Cloud

1. Sign in at <https://share.streamlit.io> with the GitHub account that owns
   the private repo.
2. Click **"New app"**.
3. Pick your repo → branch `main` → main file `streamlit_app.py`.
4. **Advanced settings**:
   - **Python version**: 3.11 or 3.12.
   - **App URL** (optional): pick a slug like `aqe`.
5. **Don't deploy yet** — set secrets first (next step), then deploy.

### 3. Add your FMP key as a Streamlit secret

1. In the new-app dialog (or after, via **Settings → Secrets**), paste:

   ```toml
   FMP_API_KEY = "fmp_xxx_your_real_key_here"
   ```

   Replace with the value from your local `.env` file.

2. Save. Streamlit redeploys automatically.

That's the only secret AQE itself needs. AIC LLM features (Anthropic key)
are optional and stay disabled on cloud unless you also add `ANTHROPIC_API_KEY`.

### 4. First run

1. Open the app URL (e.g. `https://aqe.streamlit.app`).
2. Sidebar shows "Cloud mode" badge.
3. Click **Bootstrap + run daily pipeline**.
4. Live log stream appears. You'll see lines like `[daily] 1/491 AAPL`.
5. After ~3-5 min the page refreshes with regime, SRM, longlist, etc.

## Daily workflow

```
You open the app URL on phone or laptop.
   ↓
If first visit of the day (or container slept):
   → click "Run daily pipeline" → wait 3-5 min → done for the day
If you used it within ~30 min before:
   → already warm, click "Run daily pipeline" → seconds (incremental)
   → or just read the current data, no re-run needed
```

## Universe management

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

## Secrets you might add later

These are NOT required for the AQE scanner; only if you re-enable specific features:

| Secret | Enables |
|---|---|
| `ANTHROPIC_API_KEY` | AIC LLM committee (Page 5 in deeper modes) |

A template lives at `.streamlit/secrets.toml.example`.

## RAM, CPU and rate-limit reality

- **RAM**: Streamlit free tier is 1 GB. After a full pipeline run, the panel
  + scores DataFrames hold ~300-400 MB. Headroom is tight but OK for one user.
- **CPU**: 1 CPU. Pipeline takes ~3-5 min wall-clock against FMP's rate limit.
- **FMP**: Starter plan = 300 calls/min. AQE caps itself at 250 to leave headroom.
  Same key on cloud + local is fine for personal use; you'll never come close
  to the per-day cap.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "FMP_API_KEY is not set in Streamlit secrets" | Secret not configured | Settings → Secrets → paste `FMP_API_KEY = "..."` |
| Pipeline exits with FMPError | Wrong key, expired key, or hit rate limit | Verify key in FMP dashboard; copy fresh into Streamlit secrets |
| App boots but Scanner shows "Cold start" | Container was asleep; parquets gone | Click **Bootstrap + run daily pipeline** |
| Cloud OOM (Streamlit restarts) | 1 GB cap exceeded | Cut universe size or remove unused engines; surface to dev |
| Cloud app sleeps too aggressively | Streamlit's idle policy | Bookmark + visit it once a few times a day; or click any button to keep warm |
| Push fails on `git push` | Credentials not cached | Run `first_push.bat` once in a real cmd window |

## Adding a new dependency

If you `import` something new that runs on cloud:

1. `pip install <pkg>` locally.
2. Add it to `requirements.txt` (pin to a major version).
3. Commit + push. Streamlit Cloud reinstalls on next deploy (~30s for small deps).

## What stays local-only (by design)

- Your real `data/open_positions.json` — Position Manager only on desktop.
- The full `data/scores_daily.parquet` (137 MB) — too big for git; cloud
  rebuilds it from FMP on demand.
- AIC SQLite + Anthropic key — LLM committee runs locally unless you wire it.
- The NiceGUI brief frontend (`src/aic/web/`) — separate process, not Streamlit.

## Rollback

If something on `main` breaks the cloud app:

```bash
git revert <bad-commit-sha>
git push
```

Streamlit Cloud auto-redeploys the reverted state in ~30 s.
