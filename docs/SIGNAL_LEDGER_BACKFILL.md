# Signal Ledger — Historical Backfill Instructions

Two ways to populate the signal ledger with ~365 days of historical data.
Pick whichever suits your weekend.

---

## Option A: Run locally on your PC (recommended)

No timeouts, no cloud throttling. Uses your local `panel_daily.parquet`
and FMP key from `.env`.

### Prerequisites

- AQE repo pulled to your PC (`C:\Users\ashtz\Backtest Engine`)
- `.env` with `FMP_API_KEY` (already there if the daily pipeline runs)
- `data/panel_daily.parquet` exists (built by the daily pipeline)

### Steps

1. **Pull the latest code** (one time):
   ```
   git pull origin main
   ```

2. **Double-click one of:**

   | Launcher | What it does | Runtime |
   |----------|-------------|---------|
   | `backfill_ledger.bat` | Uses existing panel — no FMP calls | 15–30 min |
   | `backfill_ledger_pull.bat` | Refreshes bars from FMP first, then scores + ledger | 30–60 min |

   Use `backfill_ledger.bat` if your daily pipeline ran recently (panel is
   current). Use `backfill_ledger_pull.bat` if the panel might be stale
   or you want the absolute latest bars.

3. **Watch the output.** It prints progress as it goes:
   - Step 1: Panel check (instant)
   - Step 2: Score rebuild — progress bar, ~600 tickers (15–30 min)
   - Step 3: Ledger population + forward return fill (~2 min)
   - Step 4: Hit rate preview printed to screen

4. **Done.** The database is at `data/aqe.db`. Open the app → Math Lab →
   Section 9 to browse signals and slice hit rates by any factor combo.

### What it produces

- `data/aqe.db` table `signal_snapshots`: one row per (date, ticker,
  list_source) with all scores at that date (SC_MOM, Elder, Flow, Energy,
  Structure, MP, BQ, readiness, health) + DSL levels
- `data/aqe.db` table `signal_outcomes`: forward returns T+5/10/20,
  intraday high/low over each window, TP1/TP2 hit flags, SL hit flag
- `data/scores_daily.parquet` is rebuilt with readiness + health columns
  for all historical dates (side benefit)

---

## Option B: Run via Claude (chrome extension / claude.ai)

Hand this to Claude and let it run overnight. Copy-paste the prompt below
into a Claude Code session connected to the AQE repo.

### Prompt to give Claude

```
I need you to run the signal ledger historical backfill on the AQE repo.
This is a one-off job that populates ~365 days of signal history.

Here's what to do:

1. Make sure you're on main branch with the latest code:
   git checkout main && git pull origin main

2. Check that data/panel_daily.parquet exists:
   python -c "from src.data.paths import PANEL_DAILY; print(f'exists={PANEL_DAILY.exists()}')"

   If it does NOT exist, build it first:
   python -c "from src.data.panel_builder import build_panel; build_panel()"
   This pulls daily bars from FMP for the full universe. Takes ~15-20 min.
   FMP_API_KEY must be set in the environment.

3. Rebuild scores_daily.parquet (adds readiness/health for all dates):
   python -c "from src.scanner.score_runner import build_scores; build_scores()"
   This runs all 7 engines on ~600 tickers. Takes ~15-30 min.
   You'll see a progress bar.

4. Populate the signal ledger:
   python -c "
   from src.data.signal_ledger import backfill_historical, get_hit_rates
   result = backfill_historical()
   print(result)
   rates = get_hit_rates()
   print(rates)
   ll = get_hit_rates(list_source='longlist')
   print('Longlist:', ll)
   hc = get_hit_rates(min_sc=75, list_source='longlist')
   print('High-conviction:', hc)
   "

5. Report the results:
   - How many signals were recorded
   - Date range covered
   - Hit rates: avg T+5/T+10/T+20, TP1/TP2/SL rates
   - Longlist-only vs high-conviction (SC_MOM>=75) comparison

6. Commit and push the updated aqe.db:
   git add data/aqe.db
   git commit -m "Populate signal ledger with historical backfill"
   git push origin main

Do each step sequentially. If any step fails, report the error
and stop — don't skip steps.
```

### Notes for the Claude session

- The FMP API key needs to be available. On HF Space it's in secrets.
  On claude.ai cloud, it needs to be in the environment config.
- Step 3 (scoring) is CPU-bound, not network-bound — no throttling risk.
  It's just math on the parquet data.
- Step 2 (panel build) is the only step that calls FMP. Skip it if the
  panel already exists and is recent.
- The whole job is idempotent — safe to re-run if it times out partway
  through. `INSERT OR IGNORE` means no duplicates.

---

## After the backfill

### Daily procedure (automatic)

Nothing changes. The daily pipeline Step 8c auto-appends each day's
longlist + elder_list signals and backfills outcomes for older signals
as forward bars come in.

### Viewing results

- **Math Lab → Section 9**: Hit Rates tab with SC_MOM/source filters,
  Browse tab for individual signal history, CSV export
- **Programmatic**: `from src.data.signal_ledger import get_hit_rates,
  get_signal_history`

### What the data tells you

The ledger answers the question the backtest can't: **system-level
performance by factor combination**.

Examples you can now query:
- "When AQE longlists a name with SC_MOM > 75, how often does it hit TP1?"
- "Do names on both longlist AND elder_list outperform longlist-only?"
- "What's the avg T+20 return for names with rd_score > 50 vs rd_score < 20?"
- "How often does SL get hit within 5 days for names with hl_score < 30?"

Use the Hit Rates tab filters or query directly:
```python
from src.data.signal_ledger import get_hit_rates
get_hit_rates(min_sc=75, list_source="longlist", from_date="2026-01-01")
```
