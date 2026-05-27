# AQE Cloud Deployment

This document covers deploying the AQE Streamlit Scanner to **Streamlit
Community Cloud** as a phone-accessible, read-only mirror of your local
scanner.

## Architecture

```
LOCAL (your Windows PC)               GITHUB (private repo)            STREAMLIT CLOUD
─────────────────────────             ─────────────────────            ─────────────────
run_daily.bat                                                          streamlit_app.py
  → src.pipeline.daily_orchestrator                                      → src/ui/1_Scanner.py
    writes data/*.parquet  ←(stays local, 150MB)                          (auto-detects "cloud mode"
    writes output/aqe_daily_export.json  ─push_aqe.bat─►  git push  ───► reads only the JSON,
                                                                          no parquet ever ships)
```

The Scanner detects cloud mode by checking whether
`data/scores_daily.parquet` exists. On the cloud it doesn't (gitignored),
so the page renders entirely from the committed `aqe_daily_export.json`.

Other pages:
- **Page 2 Math Lab** — disabled in cloud mode (needs panel/score parquets).
- **Page 3 Positions** — disabled in cloud mode (sensitive + needs parquets).
- **Page 4 Scheduler** — disabled on Linux (uses Windows Task Scheduler).
- **Page 5 AIC** — works (reads SQLite + export JSON).

## One-time setup

### 1. Create the private GitHub repo

```bash
# from the project root
git init -b main
git add .
git commit -m "Initial AQE commit"

# Either via the GitHub CLI (auth required):
gh repo create <username>/aqe --private --source=. --remote=origin --push

# Or manually: create at https://github.com/new (private), then:
git remote add origin https://github.com/<username>/aqe.git
git push -u origin main
```

The `.gitignore` is already wired to keep parquets, SQLite, real positions
and `.env` out of the repo. Verify before pushing with:

```bash
git status              # should NOT list scores_daily.parquet or .env
git ls-files | head     # should list streamlit_app.py + src/ + output/aqe_daily_export.json
```

### 2. Connect Streamlit Community Cloud

1. Sign in at <https://share.streamlit.io> with the GitHub account that owns
   the private repo.
2. Click **"New app"**.
3. Pick your `aqe` repo → branch `main` → main file `streamlit_app.py`.
4. **Advanced settings → Python version**: 3.11 or 3.12 (both work).
5. Hit **Deploy**.

First boot takes ~3 minutes (installs `requirements.txt`). Subsequent
auto-deploys (after each `push_aqe.bat`) take ~30 seconds.

### 3. (Optional) Set Streamlit secrets

Currently the cloud read-only mode needs **no secrets** — it reads the
committed JSON. If you later re-enable interactive features:

```toml
# Paste this in Streamlit Cloud → Settings → Secrets
FMP_API_KEY = "fmp_xxx"            # only if cloud-side FMP fetches are re-enabled
ANTHROPIC_API_KEY = "sk-ant-xxx"   # only if AIC LLM features are re-enabled
```

A template lives at `.streamlit/secrets.toml.example`.

## Daily workflow

```
Step 1. Run your daily pipeline locally (as you do today)
            → double-click run_daily.bat
            → writes data/panel_daily.parquet + output/aqe_daily_export.json

Step 2. Publish to the cloud
            → double-click push_aqe.bat
            → commits aqe_daily_export.json + small configs, pushes to GitHub
            → Streamlit Cloud auto-redeploys in ~30s

Step 3. Open the cloud app on your phone
            → https://<your-app-slug>.streamlit.app
            → "Cloud read-only mode" banner confirms you're on the remote
```

### What `push_aqe.bat` stages

Only these files:

```
output/aqe_daily_export.json      ← the canonical cloud-mode source (~140KB)
output/recipes.json               ← recipe configs
data/active_recipe.json           ← active recipe thresholds
data/sector_map.json              ← ticker → GICS ETF mapping
data/universe.txt                 ← universe list
data/earnings_calendar.json       ← earnings dates
```

Everything else (positions, SQLite, parquets, recipes, calibration reports)
is gitignored. To verify: `python -m scripts.push_to_cloud --dry-run`.

## Adding a new dependency

If you `import` something new in code that runs on the cloud:

1. `pip install <pkg>` locally.
2. Add it to `requirements.txt` (pin to a major version).
3. Commit + push. Streamlit Cloud reinstalls on next deploy.

If the new dep is **only** used on the local desktop side (e.g. you add a
Windows-only library), guard the import in a try/except so the cloud import
chain doesn't break.

## Cloud detection logic

`src/ui/shared.py`:

```python
def is_cloud_mode() -> bool:
    return not SCORES_DAILY.exists()
```

Every page that touches parquets checks this and either:
- (Scanner) substitutes the export JSON, or
- (Math Lab, Positions) shows a "this page is local-only" message and stops.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Cloud shows "No shortlist.json found" | First push didn't include the export | Run `push_aqe.bat` |
| Cloud watchlist is empty | Export was pushed but watchlist field is empty | Rerun `run_daily.bat` locally then `push_aqe.bat` |
| Cloud build fails on `import nicegui` | NiceGUI optional dep | Already in `requirements.txt`; if pruning, only the Scanner import path runs on cloud |
| Cloud build fails on `zoneinfo("Asia/Singapore")` | Linux needs `tzdata` | Already in `requirements.txt` |
| You accidentally committed `.env` | Secret leak | `git rm --cached .env`, force-rotate the FMP key |
| Cloud app says "Cloud read-only mode" locally | `data/scores_daily.parquet` missing on your local PC | Rebuild via `run_app.bat` → sidebar → Rebuild scores |

## What's NOT on the cloud (by design)

- The 137MB `scores_daily.parquet` — too big for git, too slow to rebuild on
  the cloud's RAM cap.
- Your real `open_positions.json` — Positions page would expose it.
- The AIC SQLite + Anthropic key — LLM committee runs locally only.
- The NiceGUI brief frontend (`src/aic/web/`) — separate process, not a
  Streamlit app. If you want briefs on your phone too, deploy that one
  separately on Render/Railway/Fly.io.

## Rollback

If something on `main` breaks the cloud app:

```bash
git revert <bad-commit-sha>
git push
```

Streamlit Cloud will redeploy the reverted state in ~30s.
