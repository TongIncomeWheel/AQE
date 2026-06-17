---
name: intraday-plan
description: >
  Produce a calm, rule-based intraday trade plan for AQE shortlist names — the
  momentum read, the operative stop (anchored to real intraday support, 3-gate
  validated), a momentum-conditioned entry zone, and an IBKR bracket spec.
  Recommend-only. Use when the user asks for an intraday plan / "where do I buy /
  where's the stop" / to evaluate today's momentum on the shortlist or a ticker.
---

# Intraday momentum + bracket plan

Fixes AQE's two EOD weaknesses at decision time: stops anchored to real intraday
structure (not the blunt 5-day low), and entries timed to intraday momentum (not a
static EOD `entry − 0.5R`). The math lives in `src/intraday/` (deterministic, tested);
your job is to fetch live bars and run it. **Never invent prices — only use fetched data.**

## Steps

1. **Pick the scope.** Default = `held, top_picks, edge_list`. If the user named
   specific tickers, use those. Read the tickers from `output/aqe_daily_export.json`
   (tiers `held_positions`, `top_picks`, `edge_list`, `longlist`, `watchlist`). Keep the
   list short (≈3–12 names) to stay calm and fast.

2. **Fetch intraday bars per ticker** with the financial MCP `chart` tool,
   `endpoint: "intraday-5-min"`, `symbol: <TICKER>`. (Optionally also `intraday-1-min`
   for finer entry timing.) Each call returns a large OHLCV array — **do not paste it
   into chat.** Write each result array verbatim to `/tmp/aqe_bars/<TICKER>.json`
   (create the dir). The MCP result is saved to a file path when large; copy that JSON
   array to the per-ticker file (use Bash/`python` to move it, not manual transcription).

3. **Run the deterministic planner** (it formats the output — don't hand-build tables):
   ```
   python -m src.intraday.run_plan --bars-dir /tmp/aqe_bars --scope held,top_picks,edge_list
   ```
   Add `--tickers AAPL,MSFT` to restrict, `--risk 2100` to override the risk budget,
   `--export <path>` if not the default.

4. **Relay the runner's output** to the user: the ranked table (ticker · IMS · state ·
   entry zone · stop · R:R · shares), the IBKR bracket specs, the per-name verdicts, and
   the AIC prompt. Lead with the actionable ENTER names; note the STAND_DOWN names briefly.

## What the output means (for explaining to the user)

- **state**: `ACCELERATING` (enter now, not extended) · `PULLBACK_HOLDING` (best R:R —
  pulled to VWAP and holding) · `COILING` (buy-stop on the range break) · `EXTENDED`
  (don't chase — buy the pullback or skip) · `FADING`/`BROKEN` (stand down).
- **operative stop**: the tightest intraday/structural level that passes all 3 charter
  gates — ATR floor (≥1×daily ATR), R:R-to-TP2 ≥ 2, and the regime stop-% ceiling. If
  none pass, it falls back to AQE `dsl_stop` flagged `CAUTION` (size down or skip).
- **entry zone**: never above `max_chase_tp2` (the R:R≥2 chase limit). `stand_down` means
  the math says no clean entry — that's a feature, not a miss.
- **IBKR spec**: recommend-only. The user (or a future IBKR connector) places it.

## Guardrails
- Recommend-only — never place orders. Bars may be ~15-min delayed (fine for multi-day
  holds, not scalping); say so if the user implies scalping.
- If the export is stale (its `entry` far from the live price), flag it and suggest a
  pipeline rerun — the structural anchors may be off.
- If `chart` returns no/short bars for a name, the runner marks it "no bars"; don't guess.
