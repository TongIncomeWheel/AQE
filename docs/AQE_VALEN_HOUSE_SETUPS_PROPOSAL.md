# VALEN Part 3 — House (the five setups): deep dive + build proposal

Status: **SIGNED OFF + BUILT** (2026-10-05). PM rulings: (1) retire the proxies -- yes;
(2) **high tight flag only**, no looser Momentum Breakout grade ("closer to the VALEN method");
(3) piece 12 **long-only** warnings; (4) past earnings dates pull -- yes.
Code: `src/valen/setups.py` (graders), `src/valen/setups_daily.py` (export glue),
`src/valen/house.py` (page reader), thresholds in `src/valen/spec.py` (`HB_*` / `IMPL_*`).
Source: VIV handbook *21 Building Blocks to Profitability*, pages 30-40 (pieces 08-12).
Current code: `src/valen/house.py` (shipped 2026-09-30).

## 1. Why this matters

The handbook opens Part 3 with: *"Each one is defined tightly enough to say no
with. A setup you cannot describe is a setup you cannot repeat."* Every setup is
a **measured checklist**, not a vibe. The handbook also names the tool: a
**Setup Grader** — "grade a chart before you buy it".

Today's `house.py` does not grade anything. It relabels existing DETECT fields,
and those proxies are loose enough that they break the handbook's own
"common mistakes" lists. On the last saved export (130 names):

| Piece | Current proxy | Names tagged | Handbook verdict |
|---|---|---|---|
| 09 Momentum breakout / HTF | `mover_subtype` in (trend, tight_base) **or** squeeze BREAKOUT_UP | **98** | "Forcing the label onto a stock that ran 40% and paused" — the pole is a *measured number* (90-100% in ≤8 weeks). |
| 08 VCP | `elder_context.vcp`: 5-day range < 50% of 20-day range + 4 conditions | 40 | "Calling one quiet week a VCP. It has to be a sequence." The current test IS one quiet week. |
| 10 Undercut & rally | bullish pin bar **or** bullish divergence + BOS | 2 | Never checks the defining event: a dip *below* a prior low, then a close back *above* it. |
| 11 Episodic pivot | `premove_setup` + `mover_subtype == explosive` | 0 | Never checks the gap (≥10%, or ≥4% on earnings day), volume ≥3×, or holding the gap. |
| 12 Parabolic / breakdown | Energy `exhaustion_score` < 8.5 | — | Never checks either version's measurable criteria. |

So a 98-name "momentum breakout" list is not a list. That is the first thing to fix.

## 2. Separate bug fixed today (shipped with this doc)

The page's **Run VALEN read** button rebuilt Part 1 only and saved over the
artifact, deleting Parts 2-6. Part 3 then said "No setup pattern flagged today"
when nothing had been computed. The button now rebuilds Parts 2-6 from the
export too, and the page shows a red "NOT computed" banner instead of an empty
list when they are missing.

## 3. What the handbook actually requires, piece by piece

Each criterion below is tagged by data source: **[D]** measurable from AQE's
daily OHLCV panel (6 years, 819 tickers — enough for every lookback here),
**[E]** needs the FMP earnings calendar, **[X]** not measurable (no news feed).

### 08 — VCP (pp. 31-32)
- **Stage 1, the move before the base**
  - [D] A run of **≥30%** into the base.
  - [D] Run "clean and steady, not a zig-zag" (measure: share of down-closes / overlapping bars over the run).
  - [D] A **young trend: 1st, 2nd or 3rd base** of the run. A 4th base is on the no-buy list.
- **Stage 2, the shrinking pullbacks**
  - [D] Each pullback clearly shallower than the one before — "roughly halving: 25%, then 12%, then 6%".
  - [D] Last pullback **≤10%** deep.
  - [D] Volume drying up through the base, quietest inside the final pullback.
  - [D] Higher lows into the buy point; price riding rising 10/20/50-day lines.
  - [D] Extras: inside bars before trigger; 10/20/50 converging at the buy point.
- **Stage 3, the trigger**
  - [D] Buy point = flat line across the highs of the final pullback (the pivot).
  - [D] Expansion day: range **≥4%**, bigger than the last 5-10 bars, close in **top 30%** of range, volume above prior day.
  - [D] **No more than two up-days into it** ("not buying on day three").
  - [E/X] Catalyst within a couple of sessions = bonus, never required.
- "Until the expansion day arrives, this is a watchlist name and nothing more."

### 09 — Momentum breakout / high tight flag (pp. 33-34)
- [D] **Pole:** roughly a double, **90-100%+ in ≤8 weeks**.
- [D] Pole climbs at **~45°**: steady staircase, strong closes, bars not overlapping much. Near-vertical = blow-off, not a pole. One spike day is not a pole.
- [D] **Flag shallow:** ≤**20-25%** off the pole high.
- [D] **Flag brief:** **3-5 weeks**, not much past 8.
- [D] **Flag tight:** clean drift, no jagged bars, volume fading, narrow days into the buy point; must not round out or cut deep.
- [D] **Trigger:** break above the *pattern high* (not the flag trendline) on rising volume.
- [D] **First or second flag** of the run.
- "There is no partial credit. The moment the flag rounds out or cuts deep, the setup is gone."
- Note the handbook's broader **Momentum Breakout** (leader, big move, tight base, breaks out) — HTF is its strictest shape. Propose two grades: `HTF` (all of the above) and `MOMENTUM_BREAKOUT` (big prior move + tight base + break), the latter with its own measured pole floor, PM to set.

### 10 — Undercut and rally (UnR) (pp. 35-36)
- [D] Moving averages still rising: short ones sloping up, price above the longer ones.
- [D] Young trend: **1st, 2nd or 3rd pullback**.
- [D] Volume drying up on the way down.
- [D] **A real dip below a prior low / obvious support, then a close back above it**, ideally on a reversal bar. "No dip means no shakeout. No reclaim means no trade."
- [D] **Stop at the pullback low, under one daily range.** Wider = "the chart is telling me no".
- [D] Everything else intact: group being bought (piece 02 in-theme — now computed), RS holding (piece 04), trend unbroken.
- Entry is the reclaim, never while price is falling.

### 11 — Episodic pivot (EP) (pp. 37-38)
- [D] **Neglect before it:** flat or basing for months, no big run behind it; out of an orderly base, not a falling knife.
- [D] **First surprise:** no recent gap of this kind on the chart.
- [D] **The gap:** opens **≥10%** above prior close — **or [E] a ≥4% expansion on an earnings day**.
- [D] **Volume ≥3× normal by the close** (pre-market volume not available on daily bars).
- [D] **Holds the gap:** closes in the upper part of the day's range, above the prior day. Closing back inside the gap = rejection.
- [D] **Stop that fits:** a tight level within ~1-1.5 daily ranges; clear air overhead.
- Two entries: day one (5-min opening-range high, stop day low — intraday, Part 4's job) and the **Delayed EP** (first constructive pause above the gap; trigger = reclaim of the gap-day high, stop = low of the day) — [D] the delayed form is measurable nightly.
- [X] "Genuinely new information" cannot be verified. Earnings-day gaps [E] are the one catalyst class AQE *can* confirm; any other gap stays labelled "technical fingerprint only".

### 12 — Parabolic short and breakdown (PS) (pp. 39-40)
AQE is long-only. The handbook itself says "You do not have to trade this one."
Proposal keeps piece 12 as **two risk warnings on held positions and
candidates, never a short signal**:
- **Parabolic warning** — [D] vertical run 50-100% (large cap) in days-weeks; [D] 3-5+ up days in a row; [D] far above all rising MAs; [D] first crack = big red bar (intraday VWAP failure is Part 4/live).
- **Failed-leader warning** — [D] failed highs + big red high-volume days; [D] price below 10/20/50 with those lines turning down; [D] 50-day lost with no recovery within a few sessions; [D] down on days SPY is up; [D] 3+ tests of the same support with weak low-volume bounces.
- These are exactly the moments Part 5 (managing held positions) needs, so they belong on held names first.

## 4. Proposed build

One new pure module, `src/valen/setups.py`, replacing the proxies in `house.py`.
Same discipline as `qs_spec.py`: every threshold above transcribed into
`spec.py` with a page cite, never tuned.

**Shared primitives first** (pieces 08, 09 and 10 all depend on them):
1. **Swing/pullback detector** — ordered list of swing highs/lows and pullback depths from daily bars.
2. **Base counter** — which base/pullback of the current run this is (1st/2nd/3rd/late). Also feeds the no-buy list's "4th base" flag (piece 07) for free.
3. **Expansion-day test** — ≥4% range, > last 5-10 bars, top-30% close, volume > prior day, ≤2 up-days into it. Also piece 13's trigger.
4. **Run measurer** — % gain and duration of the move into the base, plus a straightness score (45° staircase vs zig-zag vs vertical).

**Then one grader per piece**, each returning a checklist in the same
✓ / ✗ / ◌ (met / failed / not yet) idiom the alert cards already use:

```
{"piece": "08", "setup": "VCP",
 "status": "TRIGGERED" | "READY" | "FORMING" | "FAILED",
 "pivot": 142.30, "stop": 136.10,
 "checks": [{"rule": "Run into base >= 30%", "value": "41%", "result": "PASS"}, ...],
 "fails": ["Last pullback 13% (rule: <= 10%)"]}
```

- `READY` = every structural check passes, waiting on the expansion day (the handbook's "watchlist name and nothing more").
- `TRIGGERED` = expansion day happened on the latest bar.
- `FAILED` = a no-partial-credit rule broke (e.g. HTF flag > 25% deep). Shown with the reason.
- Pivot and stop are **levels**, not instructions. AQE still sizes nothing.

**Where it shows up**
- VALEN Part 3 card: one row per name with status pill + the checklist, grouped READY / TRIGGERED / FORMING. No cap.
- `daily_list` rows: a `setups` block, so the committee and alert cards read the same grades.
- Alerts (later, separate sign-off): a READY name's pivot becomes a level the 15-minute condition cycle can watch.

**Run scope:** every `daily_list` row plus held positions. Pure pandas on the
panel already loaded nightly. Wrapped like Crown/QS: a grader failure marks
`setups_status: UNAVAILABLE` loudly, never an empty list.

## 5. Suggested order

| Step | What | Why first |
|---|---|---|
| 1 | Shared primitives + VCP (08) | Most-used, "easiest to master"; replaces the one-quiet-week test. |
| 2 | HTF / Momentum breakout (09) | Kills the 98-name over-tag. |
| 3 | UnR (10) | Reuses the swing detector; in-theme + RS inputs already exist. |
| 4 | Piece 12 warnings on held names | Directly protects the live book. |
| 5 | EP (11) incl. Delayed EP | Rarest setup; needs the historical earnings dates wired for the earnings-day half. |

## 6. Decisions the PM needs to make

1. **Retire the proxies?** Proposal: yes. DETECT fields stay on `daily_list` as context; they stop being called setups.
2. **Momentum Breakout pole floor.** HTF is fixed at 90-100%. The broader Momentum Breakout has no number in the handbook. Pick one (e.g. 50% in ≤12 weeks) or ship HTF only.
3. **Piece 12 framing.** Proposal: warnings on held + candidate longs only, never a short list. Confirm.
4. **Earnings-day EP.** Needs past earnings dates per ticker (FMP earnings calendar). OK to add that pull?


## Addendum 2026-10-06 — the PM's own U&R reference levels

From the PM's pasted U&R write-up (third-party, unverified; NOT the handbook).
Built as **separately-named grades** beside the handbook's swing-low U&R, which is
unchanged: "Undercut and rally — Daily EMA8 / EMA10 / EMA21 / SMA50 / Weekly EMA9 /
support gap / round number". Constants `PM_UNR_*` (taken as written: the MA list,
the 1.25%–3.5% buffer-stop zone) and `IMPL_*` (AQE's measurement where the write-up
names a level but no number: undercut depth, gap size/volume, round-number steps).
Only live shapes (Triggered / Ready / Watch / Past pivot) are recorded for these
looser levels — on 800 random uptrends a failed grade was the norm, not a finding.
The buffer-stop zone is shown as a reference figure; the handbook's "stop under one
daily range" stays the hard rule. Intraday reference lines on the alert cards (all
figures only, none feeds a condition): opening-range high/low (first 15 min — the
feed is 15-minute, the write-up uses 5), low of day, VWAP reclaimed / lost.


## Addendum 2026-10-08 — keep it simple

PM: "Keep it simple is the mantra", after Valen's own list: *support levels can be
gaps, horizontal support, trendline support, key moving averages (EMA9/21)*. The
2026-10-06 build was cut back to exactly those. Removed: daily EMA8/EMA10, SMA50,
weekly EMA9, round numbers. Added: trendline support (the line through the last two
rising confirmed swing lows, projected to today). The uptrend gate for these grades
and the live same-day read is now simply "EMA21 rising". Horizontal support remains
the handbook swing-low grade. The intraday EMA8/EMA20 reference figures on the cards
are unchanged (a separate PM ask).
