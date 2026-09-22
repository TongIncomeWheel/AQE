# VALEN Dashboard — proposal

**Status:** DRAFT, awaiting PM sign-off. Nothing in here is built yet.
**Source:** *The VIV System — 21 Building Blocks to Profitability*, v1.3, September 2026 (the
handbook), cross-checked against the web edition at `valensontrades.com/playbook`, which states
several thresholds the PDF leaves implicit.
**Scope of this document:** what to build, where it lives, what it may and may not say, and how it
marries with the existing daily workflow.

---

## 1. What VALEN Dashboard is — and the line around it

The handbook is a complete six-part trading system. AQE already implements most of parts 2–6 in its
own idiom (longlist/Elder/QS for selection, DETECT + patterns for setups, `bracket_engine` for
entry and management). Rebuilding those would be duplication, and duplication is how two systems
start disagreeing about the same stock.

**VALEN Dashboard is Part 1 only, plus the two group pieces that feed it:**

| Handbook | Piece | What it answers |
|---|---|---|
| Part 1 · Weather | 01 · Check the market first | How hard do I push today? |
| Part 1 · Weather | 02 · Markets move in groups | Where is the money going? |
| Part 1 · Weather | 03 · Rotation | Which groups lead *from their highs*, not off their lows? |
| Part 1 · Weather | — · The card that does all of this | One screen, read before any chart |

Everything downstream — VCP, the momentum breakout, UnR, EP, PS, entry, trimming, trailing,
the three limits — stays where it already lives in AQE. This module answers the **first** question
of the day and then hands off.

The handbook's own words for why this order matters: *"I read the stance first. That decides my
size before I have looked at anything. Then the headline, then the neighbourhood column. That tells
me where to hunt tonight. Then I open the charts. Never before."*

---

## 2. Two hard constraints, resolved up front

These are the two places where a naive port would quietly break something. Both need a PM ruling
before code is written.

### 2.1 VALEN's stance prescribes size. AQE is forbidden from doing that.

The handbook is explicit: RISK ON = full playbook · NEUTRAL = half size, take profit sooner, only
the best setups · RISK OFF = the best work you can do is build the watchlist.

AQE's charter (`CLAUDE.md:25`) is equally explicit: *"AQE makes no decisions, no sizing."* The
FULL/HALF/QUARTER `max_new_size` concept was **removed** as a violation (2026-08-13), as was PTRS
disposition before it. Four tests enforce the absence:
`tests/test_smoke_endtoend.py:305-329`, `:332-365`, `:879`, and
`tests/test_data_taxonomy.py:167-177` (which asserts `"max_size" not in` the taxonomy).

**Proposed resolution — the stance is a reading, not an instruction:**

- AQE **computes and exports** `stance: RISK_ON | NEUTRAL | RISK_OFF`. This is legitimate: it is a
  market-state label in exactly the same category as the `regime` field AQE already ships
  (`export["regime"] = {"vix", "level"}`), or Crown's `heartbeat.regime`. It describes the market,
  not the book.
- AQE **never emits** a size, a size tier, a multiplier, a position count, or a disposition. The
  artifact carries no such key, and a new test asserts it.
- VALEN's "what I do with each answer" is rendered in the UI as **quoted doctrine**, visibly
  attributed to the handbook, sitting beside the stance as reference text — not as a computed
  field, not in the JSON. The PM/AIC still makes the sizing call, exactly as today.

This keeps the whole value of the stance (one word that frames the day) without AQE acquiring an
opinion it is charter-bound not to have.

### 2.2 VALEN's breadth is market-wide. AQE's panel is not.

T2108 is *"the share of **all stocks** above their own 40-day line"*, read against absolute
thresholds — under 20 washed out, over 80 overheated. The 4%-mover and 25%-mover counts are
likewise whole-market counts.

AQE's `panel_daily.parquet` holds **819 tickers**: a 493-name curated universe
(mcap ≥ $2B, 10-day avg volume ≥ 1.5M, NASDAQ/NYSE) plus GICS ETFs, thematic-basket constituents
and held names. Computing "% above the 40-day" across 819 large, liquid, already-screened names
and labelling it T2108 would produce a number that **reads like the real indicator while measuring
a different population**. Its 20/80 thresholds would be meaningless — a universe pre-filtered for
size and liquidity is structurally biased versus the full tape.

This is the same class of error the codebase already refuses elsewhere: *"A gamma map without open
interest is UNAVAILABLE, never a flat map"*, and the CTA rule that a proxied market is
*"proxied + labelled, never dropped"* because a shrinking denominator silently re-rates everything.

**The decisive proof that our universe cannot carry these rules.** One of VALEN's own stance-flip
conditions is *"monthly big risers clear **350**"* — an **absolute count** of stocks up 25%+ over a
month. Our panel holds 819 tickers in total, and they are large, liquid, already-screened names.
A count of 350 such movers is arithmetically unreachable here in any normal month; the rule would
sit permanently red and the stance would never flip positive on it. That threshold is calibrated to
a full ~7,000-name tape. It is not a number that can be rescaled by judgement — it has to be
measured on the population it was written for, or not used.

**Proposed resolution — widen the substrate, and label the population on every breadth row:**

- There is already a wider net in the repo: `src/scanner/ma_scanner.py::get_ma_universe()`
  (`:49-102`) screens **all US NASDAQ/NYSE names over $1B market cap, limit 5000**, and computes
  `sma_{20,50,100,200}` per ticker. That is the right substrate — an order of magnitude closer to
  market-wide than the AQE universe.
- The catch: the scanner currently **keeps only rows near an MA** (`:253`) and the
  `data/ma_panel.parquet` / `ma_scan.parquet` files are not on disk right now. Breadth needs the
  **pre-filter** panel, so this requires a small change to persist the unfiltered counts.
- Every breadth row in the artifact carries `population` (`"us_nasdaq_nyse_mcap_gt_1b"`) and `n`.
  A reader can never mistake which tape it describes.
- VALEN's absolute thresholds (20/80, 25/30, 75/80) are shown as **reference lines, visibly marked
  as calibrated to the full tape**, until we have enough history on our own population to state our
  own bands. Until then the *direction and the cross* are tradeable; the absolute level is context.
- If the ma_scanner route is rejected, the honest fallback is `UNAVAILABLE` for T2108 and the mover
  counts — not a universe-scoped number wearing a market-wide name.

**Open question for the PM:** widen ma_scanner and own the breadth series, or ship Part 1 without
the four instruments and mark them unavailable? The card is materially weaker without them — the
six-row checklist is four-fifths breadth — so the recommendation is to widen.

---

## 3. What AQE already answers vs what VALEN asks

Verified against the code, with citations. This is the reuse-vs-build line.

### Reuse as-is — already computed, just needs reading

| VALEN input | Where it already is |
|---|---|
| VIX/VXV ratio (VXV *is* VIX3M) | `src/macro/crown/vol.py:215-235` — `term_structure()` emits `ratio_30d_3m = vix/vix3m`, plus `shape: BACKWARDATION\|CONTANGO` |
| Whole VIX complex | `src/macro/crown/cboe.py:43-58` — VIX, VIXEQ, DSPX, COR1M, COR3M, VIX3M, VIX9D, VVIX, RVX, straight from Cboe |
| 52-week range per ticker | `high_52w`, `low_52w`, `pct_from_52w_high` — `src/data/drive_sync.py:1123-1124`, `:1415-1423` (close-to-close, not intraday) |
| Sector + theme grades, RRG | `src/engines/srm.py` — 11 GICS ETFs (`:25`), 35 thematic baskets (`:70`), `rrg_quadrant` LEADING/IMPROVING/WEAKENING/LAGGING (`:662-669`), `rrg_direction` ENTERING/DEEPENING/EXITING/STABLE (`:672-685`) |
| Group 1-week / 1-month performance | `roc5` / `roc20` per group — `src/engines/srm.py:296-297` |
| Group "thrust" (this week's push) | `divergence = roc5 − roc20` (`:300`) + the explicit acceleration path (`:303`). Not named thrust; is exactly it |
| Card grammar (headline / why / what-would-change-it) | `src/macro/crown/explain.py:455-465` — keys are `headline`, `regime_words`, `because`, `so_what`, `watch_for`, `caveats`, `as_of`, `note` |
| "What would change it" with today's value beside each rule | `src/macro/crown/levels.py:33-39` — `key_levels` rows already carry `{what, now, level, distance_pct, if_it_breaks}`, sorted nearest-first |
| Table + one-click copy to AIC | `src/ui/shared.py:203-281` — `table_with_copy()` |

**The important finding:** Crown's `explain.py` + `levels.py` already produce *exactly* VALEN's card
grammar — a headline, the reasons under it, and a list of named thresholds each showing today's
value and what breaking it would mean. VALEN Dashboard is not a new narrative engine. It is a new
**reading** (trend, breadth, rotation) rendered through machinery that already exists and is already
tested against jargon leakage.

### Cheap derivations — existing data, small additions

| VALEN input | Derivation |
|---|---|
| ATR multiple from the 50-day | `extension_atr_20 = (entry − ma_20)/atr_14d` already exists (`src/data/drive_sync.py:1553-1556`). `ma_50` and `atr_14d` are both per-ticker fields — the 50-day variant is one line |
| SPY 10/20-day rows, 10-above-20 | SPY **is** a row in `panel_daily` (`src/data/universe.py:68`, `:150-151`). Note: no `ma_10` in the export schema; a local one exists at `src/engines/enrichment.py:458`. `stack_state` is 20>50 and 100>200 (`drive_sync.py:153`) — **not** 10-vs-20, so it cannot be reused as-is |
| Group-level % off 52-week high | Needs group index highs; constituent data is present |

### Genuine builds

| VALEN input | Status |
|---|---|
| **QQQ bars** | **Not in the panel.** Nor IWM, RSP, SMH, DIA. Sector ETFs are. QQQ must be added — one ticker |
| **20-week SMA** | Missing. `wk_sma10` + `wk_rising` exist (`src/engines/structure.py:203-213`); there is no 20-week anywhere |
| **"Rising 5-day line"** | Missing as such |
| **% above 20/40/50/200-day, universe-wide** | Missing. Only per-basket 20-day breadth exists (`src/engines/srm.py:388-405`) |
| **Up-4% / down-4% daily counts (and 5d, 10d ratios)** | Missing entirely |
| **Up-25% / down-25% month and quarter counts** | Missing entirely |
| **52-week new highs minus new lows, 8d vs 20d smoothing** | Missing entirely |
| **Cross-group ranking** (the 3-way Theme Leaders table) | `roc5`/`roc20` exist per group but **no ranking across groups** is computed — the export only buckets ETFs by grade |
| **NAAIM managers' exposure** | External weekly source (naaim.org), not in AQE. Optional; carries its own as-of date |
| **A non-VIX regime read** | AQE's `regime` is VIX-only (`src/engines/bracket_engine.py:52-62`). VALEN's UPTREND/CHOP/DOWNTREND is a *price-structure* read — genuinely new, and deliberately separate from the VIX regime rather than replacing it |
| **A card/banner UI helper** | `src/ui/shared.py` has no card/banner/metric helper. Pages use ad-hoc `st.metric` / `st.columns` / `st.expander` (see `src/ui/pages/8_Crown_Macro.py:259-262`) |

---

## 3b. The frozen thresholds (`src/valen/spec.py`)

Transcribed from the handbook and the web edition. These are the numbers the stance turns on, and
they are the reason the module needs a frozen spec file rather than constants scattered through the
code — same discipline as `qs_spec.py`.

**Market trend (SPY and QQQ)**
- Daily buy signal: price above its 10-day **and** 20-day line, and the 10 above the 20.
- Weekly buy signal: the same test on weekly bars (10-week / 20-week).
- Above a rising 5-day line.
- Regime: all three SPY rows yes = `UPTREND`; all three no = `DOWNTREND`; anything mixed = `CHOP`
  — *"and chop is where breakouts get sold."*

**Extension**
- Stocks above their 20-day line, three populations tracked separately: low line **25** (**30** for
  the S&P), high line **80** (**75** for the S&P).
- VIX/VXV (VXV = VIX3M): above **1.00** uncertainty · below **0.82** calm.
- SPY and QQQ ATR multiples from the 50-day: around **6** is as stretched as an index gets.
- NAAIM exposure 0–100, weekly (Wednesdays), carries its own as-of date; colours only at extremes.

**The six-row checklist** (more yes, more size — and the Net High Net Low row alone governs how
open trades are managed)
1. Net High Net Low: the 8-day average above the 20-day average.
2. Today's count green: more stocks up 4%+ than down 4%+.
3. The 5-day count at **1.00** or better.
4. Month count green: more stocks up 25%+ than down 25%+.
5. Three-month count green: the same test over three months.
6. The last five closed trades net positive. ← *AQE already has this from the PTJ journal.*

**The four instruments**
- 5-day and 10-day count: stocks up 4%+ divided by stocks down 4%+, summed over the last five and
  the last ten sessions. Needs **1.00** or better on both. Under **0.50** sellers rule. Over
  **2.00** aggressive buying.
- T2108: share of all stocks above their own 40-day line, 0–100. Under **20** washed out (where
  bottoms form), over **80** overheated.
- Net High Net Low: 52-week highs minus 52-week lows, smoothed by an 8-day and a 20-day average.
  8-day above 20-day = breakouts are being rewarded; below = they are being sold.
- Big movers, three counts: today up 4%+ vs down 4%+; one month and three months up 25%+ vs
  down 25%+.

**What flips the stance** (each shown on the card with today's value beside it)
- To positive: stocks above their 40-day line clear **50** · monthly big risers clear **350** ·
  the 5-day count above **1.00**.
- To negative: the daily count stays red · the 5-day count falls under **0.70**.
- Trade management changes when the 8-day average of net new highs crosses back above the 20-day.

**Rotation state**
- `LEADING` — strong rank **and** within a few percent of its highs.
- `OFF_THE_FLOOR` — the same strong numbers, still 15–25% below its highs.

**Per-stock stretch** (for the no-buy list, Phase 3): ATR multiple from the 50-day — under **4** is
the launchpad, around **5** no adds, **7.5–8** is rare air, around **10** on a single stock is a
trim signal (**6–7** on an index or a leveraged fund, *"because a basket of stocks never stretches
as far as one"*). Exact formula to be lifted from the published Pine source rather than inferred —
see §9.6.

---

## 4. Module architecture

Follows the Crown/QS conventions already in the repo: a frozen spec file, one module per reading, a
rule-based explainer, and a card renderer that can rebuild the card from the artifact alone.

```
src/valen/
  __init__.py
  spec.py        every threshold, transcribed from the handbook with page cites.
                 Frozen — changes are PM sign-off, same rule as qs_spec.py.
  trend.py       SPY/QQQ daily + weekly rows -> UPTREND / CHOP / DOWNTREND
  breadth.py     the four instruments + the six-row checklist.
                 Every output carries population + n.
  extension.py   % above 20-day (3 populations), VIX/VIX3M (from crown.vol),
                 SPY/QQQ ATR multiple from the 50-day, NAAIM (optional)
  groups.py      Theme Leaders 3-way ranking + the Rotation table
                 (thrust, 1M RS, % off 52-week high, LEADING vs OFF_THE_FLOOR)
  stance.py      combines the above -> stance + watch_for, with today's value per rule
  explain.py     plain-English card text. Rule-based, no LLM, same discipline
                 and the same jargon-prohibition test as crown/explain.py
  card.py        renders the card FROM THE ARTIFACT ALONE — a test forbids it
                 importing pandas or opening a file (the qs_card.py rule)

data/valen/thresholds.json   frozen constants, PM sign-off to edit
src/ui/pages/7_VALEN_Dashboard.py   (7 is free; pages 1, 2 and 7 are currently absent)
output/valen_dashboard.json         local, carries chart series for the page
output/aqe_valen_dashboard.json     published: plain English first, series stripped
docs/AQE_VALEN_DASHBOARD.md         the reference doc once built
tests/test_valen_*.py
```

**Daily pipeline:** a new **Step 6i**, after Crown (6f) / scenarios (6g) / reading copy (6h). It
needs SRM's group grades, so it runs after SRM grading and before the export is written — the group
ranking is then passed into `drive_sync` the same way `sector_grades` already is.

---

## 5. The card — formatting and organisation

This is the part the handbook is most specific about, and the part worth copying precisely. The
card is *"one sentence at the top, three columns underneath, and a stance in the corner."*

```
┌────────────────────────────────────────────────────────────────────────────┐
│ SITUATIONAL AWARENESS                                   stance  RISK OFF   │  <- one word, colour-coded
├────────────────────────────────────────────────────────────────────────────┤
│ ▍ The index rose while more stocks fell — a narrow advance, and the main    │  <- the headline: 1-2 sentences.
│   breadth switch flipped red. Thursday's big surge did not follow through.  │     "If you read nothing else, read this."
├──────────────────────┬──────────────────────┬──────────────────────────────┤
│ THE WEATHER          │ THE NEIGHBOURHOOD    │ WHAT WOULD CHANGE IT         │
│ (piece 01)           │ (pieces 02 + 03)     │                              │
│                      │                      │                              │
│ • S&P closed +0.7%   │ • Cloud and Software │ • The quarter switch         │
│   but 216 stocks     │   lead AND sit near  │   turning green again        │
│   fell 4% against    │   their highs        │ • The 5-day ratio getting    │
│   only 179 that rose │ • Software up +6.3%  │   back above 1               │
│ • The main switch    │   this week, finally │ • Still getting weaker:      │
│   flipped red        │   green on the month │   Semis −7.9% week           │
│ • The month is worse │ • China ranks just   │ • Bottom of the rotation     │
│ • Fewer and fewer    │   as high but sits   │   table: healthcare, biotech │
│   names carrying     │   24–34% below its   │                              │
│                      │   highs — a bounce,  │  each rule shows TODAY'S     │
│                      │   not a breakout     │  VALUE beside it             │
├──────────────────────┴──────────────────────┴──────────────────────────────┤
│ BREAKOUTS: LESS likely │ STRONG AND NEAR HIGHS: CLOU·WCLD·BOAT             │
│ TOP-RANKED BUT FAR BELOW HIGHS: 3 │ THEMES THIS WEEK: China Int·Medical    │
└────────────────────────────────────────────────────────────────────────────┘
```

Four organising principles worth preserving exactly, because each one is load-bearing:

1. **The stance is in the corner, not the middle.** It is read first and then not argued with. One
   word. Colour-coded. Everything below explains it; nothing below overrides it.
2. **The headline is a sentence, not a number.** The handbook's test is *"if you read nothing else,
   read this."* This is the same job Crown's `plain_english.headline` already does.
3. **Three columns, in workflow order** — the market, then where the money is, then what would
   flip it. Left to right *is* the order of the day. The third column is the one people skip and
   the one that tells you what to do tomorrow.
4. **Every threshold shows today's value beside it.** *"The stance never flips on a feeling, and
   never on one session. It flips when a rule is met, and the rules sit on the card with today's
   number beside each one."* Crown's `key_levels` rows already have this exact shape
   (`what` / `now` / `level` / `distance_pct` / `if_it_breaks`).

Below the card, two tables, both using the existing `table_with_copy()`:

- **Theme Leaders** — every group ranked three ways at once: Since Open, 1 Week, 1 Month.
  "Since Open" is `(close − open) / open` of the latest bar, which the panel already carries. The
  reading rule is the cross-reference, not any single column: on both lists = real leadership ·
  strong week, absent month = new money arriving · strong month, fading week = a leader resting or
  ending · today's big gainers from the month's worst groups = a bounce, not leadership.
- **Rotation** — sorted by thrust, with the honesty column. Three numbers: rank (1-month RS),
  thrust (this week's push), and **% off the 52-week high**, which is what separates a group
  leading *from its highs* from one merely bouncing off its lows. State is `LEADING` (strong and
  within a few percent of highs) or `OFF_THE_FLOOR` (same strong numbers, still 15–25% below).
  The handbook is blunt that conflating these is how *"a bounce gets bought at full leadership
  size."*

---

## 6. How it marries with the existing workflow

The dashboard is worthless if it is a screen nobody routes through. Three concrete joins:

### 6.1 `in_theme` as a column on `daily_list`

This is the highest-leverage integration and it costs almost nothing. The handbook's central
selection claim is *"about half of any stock's move comes from its group, not from the stock
itself"*, and its rule is mechanical: a stock whose group is top-five on the week or month list is
**in-theme**; *"It is a status I look up, not a feeling I have."*

AQE's charter is already **"ONE list, membership as columns"** — `on_longlist`, `on_elder`,
`on_qs`, `in_ledger`, `held`. Adding `in_theme` (plus `theme_rank` and `theme_state`) is exactly
that pattern, stamped during the export the same way `held` is. The committee then reads group
membership in the same row as everything else, and the Signals table gets one more lens checkbox
beside Longlist / Elder ≥8 / QS / Held.

This turns VALEN's neighbourhood read from a screen you look at into a filter you act on.

### 6.2 Page order — VALEN first, then hunt

The dashboard becomes the first page, and it **ends with a handoff**: a control that opens the
Signals table pre-filtered to in-theme names. That is the marriage point — the card says where to
hunt, and the click takes you there, rather than leaving the reader to re-derive it.

The existing Scanner page keeps its order; nothing there is disturbed.

### 6.3 The no-buy list — nearly free, and the biggest committee win

Ten fixed deal-breakers, *"not a score to weigh up. One yes ends the conversation."* Almost every
line already exists as an AQE field:

| No-buy line | Existing field |
|---|---|
| Market check red | new: `stance` |
| Below the 200-day | `ma_200` |
| Group on neither list, or only bouncing off its lows | new: `theme_state` |
| Stretched — 4+ daily ranges above the 50-day | `extension_atr_*` (50-day variant, one line) |
| Base is wide and loose | `pattern`, `pattern_stage` |
| No volume on the break | `day_vol` |
| Earnings within 5 sessions | `days_to_earnings` |
| Total open risk at its limit | held book / hedge layer |

Rendered as a per-row checklist, this is a **gate the committee reads, not a score AQE computes** —
booleans and breakdowns, which is precisely what the charter permits. Recommended as Phase 3
because it is cheap and it is the piece that most directly prevents losses.

---

## 7. Phasing

**Phase 1 — the card.** Trend rows (needs QQQ + 20-week SMA), extension strip (VIX/VIX3M is free
from Crown), stance, `explain.py`, the page, the artifact. Breadth rows render as `UNAVAILABLE`
until Phase 2 — honestly absent rather than quietly wrong.

**Phase 2 — breadth and groups.** The ma_scanner widening and the four instruments, the six-row
checklist, Theme Leaders, the Rotation table, and the `in_theme` flag on `daily_list`.

**Phase 3 — the no-buy list** as a per-row checklist over fields that already exist.

Phase 1 is genuinely useful alone: stance + trend + extension + the rotation read answers "how hard
do I push, and where" without a single new data source beyond QQQ.

---

## 8. How this fails, and what the tests must catch

- **The stance acquires an opinion.** A test asserts the artifact contains no size, size tier,
  multiplier, disposition, or position count — mirroring `test_ptrs_and_disposition_are_both_retired`.
- **A universe number wears a market-wide name.** A test asserts every breadth row carries a
  `population` and an `n`, and that no row is labelled `t2108` unless its population is the wide one.
- **Jargon reaches the card.** Reuse Crown's prohibition test — no "percentile", "dispersion",
  "z-score", "RS ratio" in generated prose.
- **The card drifts from the artifact.** `card.py` may not import pandas or open a file, so every
  claim on the card is reconstructible from the JSON alone (the `qs_card.py` rule).
- **A missing leg reads as a calm one.** Per-source `as_of` + `days_stale`, and the run reports its
  oldest leg — the 2026-08-10 Crown incident, where a stale local panel displaced a live fetch and
  the Heartbeat read June while everything else read August.
- **`in_theme` silently empties.** If group ranking is unavailable, the flag must be **absent**,
  never `False` — absent means "not evaluated", False means "evaluated and failed". Same distinction
  the `qs` block already makes.

---

## 9. Decisions needed from the PM

1. **Breadth substrate** — widen `ma_scanner`'s universe and own the breadth series, or ship
   Part 1 with the four instruments marked unavailable? (Recommendation: widen. Without it the
   six-row checklist is mostly empty and the card loses its spine.)
2. **NAAIM** — fetch it weekly from naaim.org, or leave it out? (It is one number a week and it
   carries its own as-of date; low cost, low weight.)
3. **Stance doctrine text** — confirm that quoting the handbook's size guidance in the UI, visibly
   attributed and outside the JSON, is the right line. It is the one place where VALEN's words and
   AQE's charter touch.
4. **Absolute thresholds** — show VALEN's full-tape numbers (20/80 etc.) as reference lines with a
   caveat until we have our own calibration, or suppress them until calibrated?
5. **Does the VIX regime stay?** VALEN's UPTREND/CHOP/DOWNTREND is a separate, price-structure
   read. Recommendation: keep both, side by side, never merged — the same discipline that keeps
   Crown standalone from SRM so the overlap stays measurable.
6. **Lift the Pine sources?** The published scripts (VIV Chart Suite, VIV Volume Suite, VIV
   Execution Table, and the optional *ATR% Multiple From MA*) are the authoritative definitions for
   three numbers this module needs: the **ATR multiple from the 50-day** (which ATR length, SMA or
   EMA), **ADR%**, and the **time-matched RVOL** rule. The handbook gives the thresholds but not the
   formulas. Transcribing them from source beats inferring them — Pine is the spec, the same way
   Pine is the spec everywhere else in AQE. Low effort, removes a whole class of silent mismatch.
   Only the first two matter for Phase 1–2; the RVOL rule belongs to the entry layer, which is out
   of scope here.
