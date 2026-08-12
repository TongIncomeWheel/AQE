# GitHub as AQE's store — daily output, state, and autoload

PM directive, 2026-08-12: *get off local and Google Drive, keep everything in
GitHub.* This is what was built, what you have to do once to switch it on, and
the one place the directive was not followed literally — with the reason.

---

## The shape of it

| What | Where it goes now | Where it used to go |
|---|---|---|
| The day's JSON artifacts | **`aegis/output/` in this repo**, committed | Drive + the container's `output/` |
| The runtime state snapshot | **A GitHub release asset**, tag `state-snapshot` | Drive |
| Everything above, again | Drive, as a **backup leg** | — |
| Restore on app open | **Automatic**, every module | A button on the Scanner page |

Drive is still written every day. It is now the backup rather than the store, so
there is no flag day and no window where the book exists in exactly one place.

---

## What you have to do once

**Create one token and paste it into two places.** Nothing works until this is
done, and until then the daily run reports `GITHUB_TOKEN not set` in its log
rather than failing quietly.

### 1 · Make a fine-grained personal access token

1. Go to <https://github.com/settings/personal-access-tokens/new>
2. **Token name:** `AQE Space writer`
3. **Resource owner:** `TongIncomeWheel`
4. **Repository access:** *Only select repositories* → **`TongIncomeWheel/AQE`**
5. **Permissions → Repository permissions:**
   - **Contents: Read and write** ← the only one required
6. **Expiration:** whatever you are willing to rotate. If it expires the daily
   log will say so on the first run after.
7. Generate, and copy the token. GitHub shows it once.

### 2 · Paste it into the HuggingFace Space

Space → **Settings → Variables and secrets → New secret**

- **Name:** `GITHUB_TOKEN`
- **Value:** the token

That is the only place it is needed. **The GitHub Actions backstop does not need
a token** — it uses the built-in one, which the workflow now grants
`contents: write`.

Treat the token exactly like the FMP key: it goes in the secrets box, never into
chat, a document, or a commit.

---

## Where the day's files land

One folder, one copy of each file, overwritten in place:

```
aegis/output/
├── aqe_daily_export.json      the committee's read
├── aqe_crown_macro.json       Crown reading copy, plain English first
├── crown_macro.json           Crown runtime record, with the chart series
├── macro_scenarios.json       the Crown x Macro Weather merge point
├── qs_daily.json              QS standalone artifact
├── shortlist.json
├── held_positions.json
├── aqe_sector_map.json
├── options_scan.json          universe CSP theta sweep
├── aqe_last_run.json          the run marker the status bar reads
└── aqe_snapshot_meta.json     when the state snapshot was last written
```

**No dated filenames, ever.** A folder a reader has to pick the newest file from
is exactly how the wrong-file held book happened once before. A test enforces it.

Because the files are committed, `git log -p aegis/output/aqe_daily_export.json`
now shows what changed in the book between any two days, which the Drive copy
could never do.

### Times

Unchanged — this migration moved *where*, not *when*.

| Time (SGT) | What |
|---|---|
| 05:30 | Universe CSP theta scan |
| 06:00 | Universe rebuild |
| **08:30 Tue–Sat** | **Full pipeline** → writes GitHub, then Drive |
| 09:30 Tue–Sat | Actions backstop, only if the Space did not run |

---

## The one place the directive was not followed literally

**The state snapshot is a release asset, not a commit.** Everything else went
into the repo as asked; this one could not.

The snapshot carries `panel_daily`, `ma_panel` (~2,000 tickers), `scores_daily`
and `aqe.db`. It runs to tens or hundreds of megabytes. **Git keeps every version
of every committed file forever**, so committing it daily would add its full size
to the repository permanently, every single day — a few hundred megabytes a
month that can never be reclaimed without rewriting history. `git clone` would be
unusable inside a month, and the HF deploy mirror clones the whole repo on every
push.

A release asset solves it exactly: up to 2GB, replaced in place on every run, and
**outside git history entirely**. One current state, nothing accumulating, still
on GitHub, still one credential.

Find it at **Releases → `state-snapshot`**. It is marked pre-release so it never
looks like a shipped version.

---

## Autoload — every module opens warm

`require_login()` now runs a once-per-process bootstrap after the sign-in check,
so it covers **every page of every module** — Scanner, Option scanner, Crown
Macro — with no per-page wiring.

It is **gated on the state actually being missing**. A container that already has
today's panel does not need another copy, so a warm page load costs one
`exists()` check and downloads nothing. Only a cold container pays.

It is **synchronous, behind a spinner**, on purpose. Restoring in a background
thread would let a page render while parquet files were half-written, and a
truncated panel does not raise — it reads short. A page showing 40 of 900 tickers
with no error is the silent-empty failure CLAUDE.md forbids.

### Three sources, in order, and it always says which one answered

1. **GitHub release asset** — the full state. Normal path.
2. **Drive** — the backup. Works, but the page shows a **warning**, because a
   working app and a broken primary are two separate facts and hiding the second
   means finding out on the day the backup is gone too.
3. **The repo's `aegis/output/` folder** — last resort. Pulls the day's JSON
   only. The committee read, the held book and the Crown page come back; scanning
   and scoring do not, because the price panels are not there. Reported as
   **partial**, never as a restore.

Layer 3 replaces the old committed root copy of the export, and is strictly
better: it fetches the *current* file rather than whatever was frozen into the
repo the last time someone remembered to commit one.

---

## What changed in the repo

| File | Change |
|---|---|
| `src/data/github_sync.py` | New. Contents API + Releases API, loud degradation. |
| `src/data/persist.py` | `save_snapshot_everywhere()`, `load_snapshot_best()`. One zip feeds both stores so they can never differ. |
| `src/ui/bootstrap.py` | New. The cold-start autoload and its status line. |
| `src/ui/shared.py` | `require_login()` calls the autoload after sign-in. |
| `src/pipeline/daily_orchestrator.py` | Step 8a-2 publishes to GitHub; step 8b writes both stores. |
| `.github/workflows/deploy-hf.yml` | **`paths-ignore: aegis/output/**`** |
| `.github/workflows/daily-run.yml` | `permissions: contents: write` |
| `tests/test_github_sync.py` | New, 22 tests. |

### The deploy guard is not optional

`deploy-hf.yml` rebuilds the Space on every push to `main`. Without the
`paths-ignore`, the daily data commit would trigger a rebuild — **destroying the
container that had just written the file, on a schedule.** A test asserts the
guard is present, because it is the kind of line that gets tidied away by someone
who does not know what it is for.

---

## Removed

- `output/aqe_daily_export.json` — the committed root copy. It was a second
  location for the same file, which is what "one spot" was meant to end. Still
  written at runtime as the working copy; now gitignored so it cannot come back.
- `aegis/output/aqe_daily_export_2026-07-28_LIVE.json` — a dated duplicate with a
  byte-identical sha to the file beside it.

**`aegis/output/aqe_daily_export.json` is stale until the next pipeline run
overwrites it.** It currently holds 2026-07-28 data. Nothing in this migration
could refresh it — that needs a real scan against live FMP data.

---

## Still on Drive, and why

- **The PTJ held-positions journal.** AQE *reads* it; the PM's journal process
  writes it. Moving it is a change to that process, not to AQE, so it was left
  alone.
- **The sector map round-trip** and the CSP folder, for the same reason — they
  have writers outside this repo.
- **Everything else**, as the backup leg.

Turning Drive off entirely is a one-line change once you have watched the GitHub
path run clean for a week. It was deliberately not done in the same commit as
the migration, so a failure has somewhere to fall back to.
