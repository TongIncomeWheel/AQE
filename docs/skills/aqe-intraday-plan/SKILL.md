---
name: aqe-intraday-plan
description: >-
  Turn the AQE daily export plus live intraday 5-minute bars into a calm,
  rule-based trade plan: an intraday momentum read, an operative stop anchored to
  real intraday support (3-gate validated), a momentum-conditioned entry zone that
  never chases, a take-profit ladder, position size, and an IBKR-ready bracket
  spec. Recommend-only — never places orders. Use whenever the user asks for an
  intraday plan, "where do I buy / where's my stop", whether to chase a mover, or
  to evaluate today's momentum for AQE shortlist names (held positions, top picks,
  precision-edge, longlist, watchlist).
---

# AQE Intraday Momentum & Bracket (recommend-only)

You turn AQE's end-of-day structure + **live intraday bars** into a systematic plan,
so entries and stops are math, not emotion. AQE is EOD-only; this skill adds the
intraday layer at decision time. **You place no orders.** Lead with the calm verdict —
"stand down" is a valid, useful answer.

## Inputs and how to get them (in the Claude app)

1. **AQE export (`aqe_daily_export.json`)** — the EOD structure per ticker.
   - Preferred: the user's **Google Drive connector** — load `aqe_daily_export.json`
     from the AQE folder.
   - Or the user uploads it to the chat (they can download it from the AQE Scanner
     sidebar → "Download export JSON").
   - From it you read, per ticker: `entry`, `dsl_stop`, `dsl_risk`, `atr_14d`,
     `dsl_tp_1r/2r/3r`, `max_chase_tp2`, `structural_levels` (list of {type, price}),
     `structural_targets` (list of {type, price}); and top-level `regime` ({level}).
2. **Intraday 5-minute bars per ticker** (≈10 sessions of OHLCV).
   - Preferred: a connected **market-data source** (the user's FMP or IBKR connector) —
     fetch the *5-min intraday* series for each ticker. Each bar = {date, open, high,
     low, close, volume}, timestamps in US/Eastern.
   - Or the user uploads/pastes a JSON array of 5-min bars per ticker.
   - If a name has no bars, skip it and say so — never invent prices.
3. **Scope** — default to `held_positions + top_picks + edge_list`. Honor any tickers
   the user names. Keep it to ~3–12 names so the read stays fast and calm.

## The algorithm (compute this exactly in the analysis tool)

Work in Python in the analysis tool. For each ticker, using its 5-min bars sorted
ascending and the AQE record:

**Session metrics (today = the latest calendar date in the bars):**
- `typical = (high+low+close)/3`; **VWAP** = Σ(typical·volume)/Σ(volume) over today's bars.
- **intraday_ATR** = mean true range of the last 14 5-min bars.
- `price` = last close; `vwap_pos = (price − VWAP)/intraday_ATR`; `above_vwap = price ≥ VWAP`.
- `vwap_slope_up` = VWAP now > VWAP 7 bars ago.
- **Opening range** = bars in the first 30 min (09:30–09:55 ET, six bars): `or_high`,
  `or_low`; `or_break = price > or_high`; `below_or = price < or_low`.
- **RVOL pace** = today's cumulative volume up to the latest bar's clock-time ÷ the mean of
  the prior (≤10) days' cumulative volume to that **same clock-time**. `None` if no prior days.
- **acceleration** = linreg slope ($/bar) of the last 6 closes; `accel_norm = slope/intraday_ATR`;
  `accel_up = slope > 0`.
- **higher_lows** = count of consecutive higher lows at the tail of today's bars.
- **ext_r** = (price − export.`entry`)/export.`dsl_risk` (R's already run); `None` if missing.
- `near_vwap = |vwap_pos| ≤ 0.5`.

**Intraday Momentum Score (IMS, 0–100)** — clip each part to [0,100], weighted average
(weights: vwap .25, slope .15, or .15, rvol .20, accel .15, trend .10):
- vwap = clip(50 + vwap_pos·20); slope = 100 if vwap_slope_up else 30;
  or = 100 if or_break else (10 if below_or else 50); rvol = clip(rvol_pace·50) or 50 if None;
  accel = clip(50 + accel_norm·50); trend = clip(40 + higher_lows·20).

**State** (first match wins; <4 bars → `UNKNOWN`):
1. not above_vwap → `BROKEN` if below_or else `FADING`
2. ext_r ≥ 1.0 AND vwap_pos ≥ 2.0 → `EXTENDED`
3. near_vwap AND vwap_slope_up AND higher_lows ≥ 1 → `PULLBACK_HOLDING`
4. vwap_slope_up AND accel_up AND (rvol_pace is None OR ≥ 1.3) AND (or_break OR vwap_pos>0)
   → `ACCELERATING`
5. else → `COILING`

**Operative stop (the fix for swept stops) — tightest candidate passing all 3 charter gates.**
Candidates (prices below `price`): the most-recent confirmed intraday fractal pivot low
(half-width k=3), `VWAP − 0.5·intraday_ATR`, `or_low`, the prior session's low, and every
`structural_levels[].price` from the export. For a planned entry P (= the entry-zone high,
below), for each candidate s: `risk = P − s`; `atr_ratio = risk/export.atr_14d`;
`rr_tp2 = (tp2 − P)/risk` where `tp2` = the 2nd `structural_targets` price above entry,
else `dsl_tp_2r`; `stop_pct = risk/P·100`. **Valid** iff `atr_ratio ≥ 1.0` AND `rr_tp2 ≥ 2.0`
AND `stop_pct ≤` the regime ceiling (GREEN 8 / YELLOW 6 / ORANGE 5 / RED 4 %). The
**operative stop** = the valid candidate with the highest price (tightest). If none pass,
fall back to export `dsl_stop` and mark the name **CAUTION** (size down or skip).

**Entry zone (the fix for chasing) — state-driven, never above `max_chase_tp2` (= cap).**
- FADING / BROKEN / UNKNOWN → **stand down**.
- EXTENDED → buy-limit zone [VWAP, min(price, cap)]; if VWAP > cap → **stand down** (a
  pullback that deep breaks R:R).
- COILING → buy-stop on the break: [or_high, min(or_high·1.003, cap)].
- PULLBACK_HOLDING → buy-limit [min(VWAP, price), min(price, cap)] (best R:R).
- ACCELERATING → if price > cap → **stand down**; else enter-now band
  [price·0.999, min(price·1.005, cap)].

**Bracket + size:** planned entry P = the zone's high edge. `shares = floor(2100 / risk)`
(risk = entry − operative stop; 3% of $70K = $2,100 per FULL trade). TP ladder = the
`structural_targets` above P (else `dsl_tp_1r/2r/3r`), nearest 3. `R:R = (tp2 − P)/risk`.
Action = `ENTER` (valid operative stop) / `CAUTION` (fallback stop) / `STAND_DOWN`.

## Output (always this shape)

1. **Ranked table** — ENTER first (by IMS desc), then CAUTION, then STAND_DOWN:
   `TICKER · IMS · STATE · ACTION · ENTRY ZONE · STOP · R:R · SHARES`.
2. **IBKR bracket specs** (recommend-only) for ENTER/CAUTION names:
   `SYMBOL: BUY <qty> @ <LMT|STP|MKT> <entry> | stop <stop> | TP <tp2>`.
3. **One-line verdict per name** (state + IMS + action + the why).
4. **AIC prompt** — a single paste-ready line summarizing the actionable setups, ending
   "Recommend entry decision + size per PTRS × regime; AQE makes no call."

## Guardrails
- **Recommend-only.** Never place or stage orders. The user (or an IBKR connector) executes.
- Bars may be ~15-min delayed depending on the data plan — fine for multi-day-hold entries,
  not scalping. Say so if the user implies scalping.
- If the export's `entry` is far from the live price, flag it as **stale** and suggest a
  pipeline rerun — the structural anchors may be off.
- `STAND_DOWN` is a feature: if the math finds no clean entry, say so plainly.
- Regime stop-% ceilings (8/6/5/4) are the assumed table — note they're tunable to the charter.

## Optional: deterministic bundle
For exact, repeatable math you may bundle the AQE repo's `src/intraday/` modules
(`config.py`, `momentum.py`, `bracket.py`, `plan.py`, `run_plan.py`) into this skill's
folder and run `run_plan.py` instead of re-deriving — but the spec above is self-contained
and runs with no extra files.
