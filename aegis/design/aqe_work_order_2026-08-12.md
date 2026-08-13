# AQE Work Order — voice data gaps as implementable tickets

**Date:** 2026-08-12 · **Author:** engineering handover · **Status:** ready to pick up cold.

**What this is.** `aegis/design/voice_data_map.md` tells the PM *what* is missing across 229
(voice, requirement) pairs. This document tells an engineer *what to build, where, and how to
know it is done*. Every item has an ID, exactly one class, and — for BUILD and SOURCE — an
acceptance test that can be run without asking anybody a question.

**Verification basis.** Every "already exists" claim below was checked against the real export
file, not the glossary:

| Source | What it was used for | Verified |
|---|---|---|
| `aegis/output/aqe_daily_export.json` | field existence + populated-row counts | 1,409,782 bytes · `date` = 2026-07-28 · `daily_list` = **162 rows** · md5 `3e69499d960f…` |
| `AQE_FIELD_GLOSSARY.md` | formulas, engine file:line, thresholds | read in full; 3 disagreements with the export recorded in §6 |
| `aegis/packaging/build_claude.py` | `VOICE_MENUS`, parsed with `ast.literal_eval` | 14 voices, lines 155–227 of the working checkout |
| `aegis/canon/<voice>/canon.lock.yaml` | which recogniser needs which field | 14 locks; `recognisers[].fields` + `methods[].fields` |
| `src/`, `aegis/tools/pma_run.py` | where a change lands | engine + exporter + packet-builder paths cited per ticket |

**Counting convention.** `n/162` = rows of `daily_list` where the field is present AND not
`null`/`[]`/`{}`. A field that is legitimately null (e.g. a label that only exists when its
setup fires) is marked so — a low count is not automatically a defect.

---

## 1. One-page summary

### Count by class

| Class | Items | What it means |
|---|---|---|
| **CONFIG** | **21** | Field is already in the export at the counts shown. Only `VOICE_MENUS` needs the entry. Copy-paste diff in Part A. |
| **BUILD** | **16** | AQE holds the inputs (5+ years of daily OHLCV per name, plus hourly) but does not compute or export this. Real engineering, no new data source. |
| **SOURCE** | **8** | Needs data AQE does not have at all. FMP is already wired (`src/data/fmp_client.py`) and covers 5 of the 8. |
| **WON'T BUILD** | **8** | Legitimately outside a US-equity single-name scanner's remit. Do not spend a sprint on these; the requesting voice must declare them permanently unserved in its own canon. |
| **PM DECISION** | **6** | Looks like a gap, is actually a setting, a landed rename, or a stale branch. No code required until the PM answers. |

### The three things to do first, and why

1. **E-4 — push the working checkout's `build_claude.py` to main, before anything else.**
   `origin/main`'s `aegis/packaging/build_claude.py` was last touched by commit `865ec13`
   (2026-08-05) and still carries the **old narrow 11-voice menus** — no `rogers`, no
   `livermore`, `wyckoff` at 9 fields instead of 31. The wide menus that `voice_data_map.md`
   and this document are written against exist only in the working checkout (25 unpushed
   commits). **The Part A diff will not apply to `origin/main` as it stands.** This is a
   5-minute `git push`, and every other menu ticket is blocked behind it.

2. **Part A in full — 21 CONFIG entries, one commit, zero new computation.**
   Two seats are starved almost entirely by the menu and not by the data: `detect-lens` reads
   8 fields against a canon that names ~40 available ones, and `elder-lens` reads 6 and has
   never been shown the `bracket` object its own R10 makes mandatory before it may nominate.
   Everything they need is sitting in `daily_list` at 155–162/162. This is the single largest
   capability gain per line changed in the whole backlog.

3. **E-1 — answer the regime stop-% ceiling question.**
   135 of 162 rows carry `bracket.valid = false`; 134 of those for the same reason
   (*"no structural support passes the 3 gates"*). That is the gate doing its job under a
   YELLOW 8% ceiling — but VIX printed **18.7**, i.e. 0.7 above the GREEN/YELLOW boundary at
   18.0. A 0.7-point VIX move flips the ceiling from 8% to 12% and changes the shape of every
   committee day. Nothing downstream should be rebuilt until the PM says whether 8% is right.

**Ordering rule for Parts B and C: descending by number of voices unblocked.** That is the
only ordering used. It is not a priority call and it is not a difficulty ranking.

---

## 2. PART A — CONFIG changes

Every field below is in the export at the row-count shown. The only change is the
`VOICE_MENUS` entry in `aegis/packaging/build_claude.py`.

**Apply against the working checkout's `VOICE_MENUS` (14 voices, lines 155–227) — not
against `origin/main`'s copy. See E-4.**

### A.1 The diff

```diff
--- a/aegis/packaging/build_claude.py
+++ b/aegis/packaging/build_claude.py
@@ VOICE_MENUS

  "oneil":        ["ticker","sc_momentum","structure","structure_shift","energy","flow","lens",
+                 "lens.coil","lens.structure","lens.sector",
                  "day_vol","rvol","rs_spy_20d","rs_leadership","rank","gics_sector","gics_sector_name",
                  "sector_trend_state","sma_distance_pct","ma_50","ma_200","entry","atr_14d",
                  "bracket.stop","bracket.rr","bracket.price","bracket.risk_pct","bracket.valid",
                  "bracket.targets","bracket.atr_fallback_stop","held"],

  "wyckoff":      ["ticker","flow","energy","structure","structure_shift","mp_state","mp_accel_state",
                  "day_vol","lens","lens.coil","lens.structure","lens.resistance","sma_distance_pct",
                  "ma_20","ma_50","ma_200","atr_14d","atr_caution","pin_bar_state","choch_state",
                  "div_state","div_bear_count","entry","bracket","bracket.stop","bracket.stop_type",
-                 "bracket.stop_atr_dist","bracket.risk_pct","bracket.rr","bracket.valid","bracket.targets"],
+                 "bracket.stop_atr_dist","bracket.risk_pct","bracket.rr","bracket.valid","bracket.targets",
+                 "subcomponents.energy.vp_position_score","subcomponents.energy.squeeze_score"],

  "raschke":      ["ticker","rank","held","structure","structure_shift","sma_distance_pct",
                  "atr_14d","atr_caution","day_vol","mp_state","mp_accel_state","lens","entry",
-                 "bracket","bracket.stop","bracket.stop_type","bracket.valid","bracket.risk_pct"],
+                 "bracket","bracket.stop","bracket.stop_type","bracket.valid","bracket.risk_pct",
+                 "subcomponents.mp.adx_val"],

  "thorp":        ["ticker","sc_momentum","atr_14d","day_vol","bracket.price","bracket.stop",
                  "bracket.atr_fallback_stop","bracket.valid","bracket.risk_pct","bracket.stop_atr_dist",
-                 "bracket.rr","bracket.rr_tp1","bracket.rr_tp2","knn_prob","knn_significant",
-                 "sc_m_gate_detail","sc_p_gate_detail","beta_30d"],
+                 "bracket.rr","bracket.rr_tp1","bracket.rr_tp2","knn_prob","knn_significant",
+                 "sc_m_gate_detail","sc_p_gate_detail","beta_30d",
+                 "vol_30d_ann","on_longlist","on_elder","source"],

  "seow":         ["ticker","ma_20","ma_50","ma_100","ma_200","sma_distance_pct","mp_state",
-                 "sector_trend_state","entry","bracket.stop"],
+                 "sector_trend_state","entry","bracket.stop","fib_swing_low"],

- "druckenmiller":["ticker","gics_sector_name","sc_momentum","beta_30d","sector_trend_state","thematic_basket","thematic_grade"],
+ "druckenmiller":["ticker","gics_sector_name","sc_momentum","beta_30d","sector_trend_state",
+                 "thematic_basket","thematic_grade",
+                 "bracket","bracket.valid","bracket.stop"],

- "detect-lens":  ["ticker","lens","lens_positive","lens_warnings","runner_setup","runner_conviction","premove_setup","premove_conviction"],
+ "detect-lens":  ["ticker","lens","lens_positive","lens_warnings","runner_setup","runner_conviction",
+                 "premove_setup","premove_conviction",
+                 "lens.leadership","lens.coil","lens.insti_money","lens.structure","lens.resistance","lens.sector",
+                 "ptrs",
+                 "mover_subtype","runner_conviction_label","premove_conviction_label",
+                 "choch_state","choch_date",
+                 "knn_prob","knn_significant","knn_neighbors_used","knn_tp1","knn_tp2","knn_tp3",
+                 "div_state","div_bull_count","div_bear_count","div_oscs","div_date",
+                 "pin_bar_state","pin_bar_level","inside_bar","pib_pattern",
+                 "subcomponents.flow.ext_score","subcomponents.energy.en_pos50",
+                 "subcomponents.energy.exhaustion_score","subcomponents.energy.atr_score",
+                 "subcomponents.structure.earn_score"],

- "elder-lens":   ["ticker","elder","elder_5d","elder_pattern","mp_state","mp"],
+ "elder-lens":   ["ticker","elder","elder_5d","elder_pattern","mp_state","mp",
+                 "held","entry","ma_20","ma_50",
+                 "bracket","malformed_bracket",
+                 "choch_state","structure_shift",
+                 "pin_bar_state","pin_bar_level"],

  "rogers":       ["ticker","rank","held","gics_sector","gics_sector_name","sector_trend_state",
                  "sma_distance_pct","ma_20","ma_50","ma_200","day_vol","structure",
-                 "structure_shift","rs_leadership","rs_spy_20d","entry","bracket"],
+                 "structure_shift","rs_leadership","rs_spy_20d","entry","bracket","bracket.valid"],
```

**Deliberately absent from the diff: a volume field for `elder-lens`.** It is the only seat with
no volume field at all, and its own canon **C23** is explicit — *"Elder's own persistence test is
a volume test. A trend runs on while volume is steady or climbing in an orderly [way]."* The line
to add is `"day_vol"` (or `"rvol"`), and **which one depends on E-2**. Add it in the commit that
resolves E-2, not in this one.

**Two notes an implementer needs before applying.**

- **`detect-lens` composites are deliberately excluded.** Its `canon.lock.yaml` R10 is a
  *refusal*, not a request: *"a composite score would strengthen my case and tempts me →
  I refuse (C30). sc_momentum, flow, energy, structure, mp, elder are the human voices'
  territory; this seat's only value is orthogonality."* Do not add them. `ptrs` **is** added —
  R1 names it as the explicit third sort key of `build_lens_ranking`.
- **`lens.*` and `bracket.*` sub-keys.** The parent objects (`lens`, `bracket`) already carry
  the data where they are on a menu, so the sub-key lines are for menu-slicing safety and for
  the `_field_meanings_block` renderer, which resolves a dotted entry as *"sub-field of
  `<parent>` (see above)"*. They are additive and cannot break a seat that already had the
  parent.

### A.2 The table

| ID | Field (exact JSON path) | Populated rows /162 | Add to menus of | Unblocks (voice + principle/recogniser ID) |
|---|---|---|---|---|
| C-01 | `daily_list[].ptrs` | 162 | detect-lens | detect-lens **R1** — *"rank every scored name by lens_positive desc, then lens_warnings asc, then ptrs desc — the exact build_lens_ranking sort key (C10)"*. Without it the seat cannot break a tie the way its own canon specifies. |
| C-02 | `daily_list[].mover_subtype` | 162 | detect-lens | detect-lens **R3** — mover family (explosive / trend / tight_base / squeeze) is the named tie-break in the top band. Values today: tight_base 97, squeeze 32, trend 27, explosive 6. |
| C-03 | `daily_list[].runner_conviction_label`, `daily_list[].premove_conviction_label` | 2 and 8 | detect-lens | detect-lens **R3, R12** — *"the word that must travel with each conviction number"*. **Not a gap:** `runner_setup` is true on exactly 2 rows and `premove_setup` on exactly 8, so the labels are populated on 100% of the rows that can carry one. |
| C-04 | `daily_list[].choch_state`, `.choch_date` | 159, 159 | detect-lens, elder-lens | detect-lens **R7**; elder-lens **R11** — *"whether the up-structure has already broken"*. |
| C-05 | `daily_list[].knn_prob`, `.knn_significant`, `.knn_neighbors_used`, `.knn_tp1`, `.knn_tp2`, `.knn_tp3` | 159 each | detect-lens | detect-lens **R7** — the seat must see `knn_neighbors_used` to apply the Charter v2.8 caveat that k=5 is a threshold check, not a significance test. |
| C-06 | `daily_list[].div_state`, `.div_bull_count`, `.div_bear_count` | 159 each | detect-lens | detect-lens **R8** — which oscillators disagree with price, and how many. |
| C-07 | `daily_list[].div_oscs`, `.div_date` | 61, 61 | detect-lens | detect-lens **R8**. **Not a gap:** these are only populated where a divergence exists (`div_state != NONE`); 61 rows carry one. |
| C-08 | `daily_list[].pin_bar_state`, `.inside_bar`, `.pib_pattern` | 159 each | detect-lens, elder-lens | detect-lens **R9**; elder-lens **R12** — *"so the stop is not placed beyond the tail"*. |
| C-09 | `daily_list[].pin_bar_level` | **0** | detect-lens, elder-lens | detect-lens **R9**, elder-lens **R12**. **Caveat:** `pin_bar_state` reads `"NONE"` on all 159 populated rows on this date, so a null level is *consistent* — no pin fired. The field is correct-by-construction but **unverified against live data**; see D-07 in §6. |
| C-10 | `daily_list[].subcomponents.flow.ext_score`, `.energy.en_pos50`, `.energy.exhaustion_score`, `.energy.atr_score` | 159 each | detect-lens | detect-lens **R5** — *"lens.extension is always null by PM ruling, and I point at the served numbers instead"*. The seat's own canon names these four as the substitute. |
| C-11 | `daily_list[].subcomponents.structure.earn_score` | 159 | detect-lens | detect-lens **R11** — earnings proximity. Partial only: this is a 0/4/7/10 band, not a day count. The real fix is **B-04**. |
| C-12 | `daily_list[].lens.leadership`, `.coil`, `.insti_money`, `.structure`, `.resistance`, `.sector` | 162 each | detect-lens, oneil | detect-lens **R4** — the six named sub-lenses it writes its reasons from; oneil **R3** (`lens.coil`, `lens.structure`), **R9** (`lens.sector`). |
| C-13 | `daily_list[].held` | 162 | elder-lens | elder-lens **R7** — decides tighten-versus-enter. Today 3 of 162 rows are held names. |
| C-14 | `daily_list[].ma_20`, `.ma_50`, `.entry` | 162, 162, 162 | elder-lens | elder-lens **R9** — pullback into value under a rising stack. |
| C-15 | `daily_list[].bracket` (object), `daily_list[].malformed_bracket` | 162, 162 | elder-lens | elder-lens **R10** — the seat is required to see the bracket *before it may nominate at all*, and has never been shown it. Highest-value single line in Part A. |
| C-16 | `daily_list[].structure_shift` | 155 | elder-lens | elder-lens **R11**. |
| C-17 | `daily_list[].bracket` (object), `.bracket.valid`, `.bracket.stop` | 162, 162, **27** | druckenmiller | druckenmiller **R7** (*"I put any name forward without a written premise and a written invalidation"*) and **R8** (*"any part of my output cited to set size…"*). `bracket.stop` at 27/162 is the regime gate, not a defect — see E-1. |
| C-18 | `daily_list[].bracket.valid` | 162 | rogers | rogers **R7** — *"the stop object as a whole, deferred to without argument"*. `bracket` is already on his menu; the explicit `.valid` matches the convention used on every other seat. |
| C-19 | `daily_list[].vol_30d_ann` | 162 | thorp | thorp **R1** (`realised_vol_30d`) and **C5/C6** — *"when two candidates are otherwise equivalent, volatility decides before time horizon does"*. Decimal fraction (0.7553 = 75.5%). This seat's core ranking input, and it has been sitting on the row. |
| C-20 | `daily_list[].on_longlist`, `.on_elder`, `.source` | 162 each | thorp | thorp **R8** (`universe_membership`) and **C17** — *"state the population it was fitted on"*. |
| C-21 | `daily_list[].fib_swing_low` | 155 | seow | seow **R3** (`most_recent_swing_low`) and **C8** — *"the stop is fixed by the chart at the moment of entry"*, one tick below the swing low. 7 rows null (insufficient pivot history). |
| C-22 | `daily_list[].subcomponents.energy.vp_position_score`, `.squeeze_score` | 159 each | wyckoff | wyckoff **C25** (the volume-at-price layer) and **C3/R3** (coil). The nearest served read on value-area position and on the coil behind `lens.coil`. |
| C-23 | `daily_list[].subcomponents.mp.adx_val` | 159 | raschke | raschke **C7** — THE HOLY GRAIL is specified as *"buy the first pullback after fresh highs in a strong uptrend"* with an explicit ADX gate. The seat currently has `mp_state` only and cannot gate at ADX > 30. Sample: CERT `adx_val` = 25.9. |

*(23 rows, 21 distinct CONFIG items — C-04, C-08, C-09 and C-12 each serve two voices and are counted once.)*

**One field deliberately NOT in Part A:** `rvol` / `day_vol`. It looks like the cheapest fix in
the document and it is not a CONFIG item today — see **E-2**, which is the single most
important thing in Part E.

---

## 3. PART B — BUILD tickets

**Ordered by number of voices unblocked, descending. That is the only ordering.**

---

### B-01 — Sector, regime and macro block routed into voice packets
*(3 voices)*

- **What:** a `GLOBAL_MENUS` dict beside `VOICE_MENUS`, and a `global` key on the voice packet
  carrying the export's already-existing root blocks. Target paths (all at export root, not per row):
  `regime.*`, `regime_stop_pct_ceiling`, `spy_roc_20d`, `intermarket.*`, `macro_weather.*`,
  `srm[]`, `srm_signals`, `thematic_baskets.*`, `summary`.
- **Definition:** per-ticker menus cannot carry a market-level object. Today they simply do not
  arrive, so three seats whose canon opens on a macro gate open on nothing. Rule: a voice
  declares the *global* blocks it may read, exactly as it declares per-row fields; the packet
  builder attaches those blocks verbatim, never re-derived.
- **Inputs:** nothing new. All nine blocks are populated in `aqe_daily_export.json` today
  (`regime` = `{vix 18.7, level YELLOW, hurst 0.603, trend TRENDING, implication "Momentum
  strategies favoured"}`; `srm` = 11 sector rows each with grade/RRG/macro-headwind/entry-gate;
  `macro_weather` = 19 keys; `intermarket` = 5). `aegis/tools/pma_run.py` **already relays every
  one of them into `market_frame.json` at S2** (`crown_block`, `sectors`, `cross_asset`) — the
  relay code exists and is proven; it just does not reach the seats.
- **Where:** `aegis/packaging/build_claude.py` (add `GLOBAL_MENUS`, render into the card) +
  `aegis/skills/premarket-analysis/stages/S4_voice_swarm.md` (packet assembly, "menu slicing"
  section) + `aegis/tools/pma_run.py` if the packet is written server-side.
- **Requested by:**
  - druckenmiller **R2** — *"a liquidity or central-bank-policy read is required — which is the first-order input for this entire seat"* — names `intermarket.tlt.roc5/roc20/above_sma20`, `intermarket.uup.*`, `intermarket.hyg.hyg_tlt_spread`, `macro_weather.*_direction`, `regime.vix`, `regime.level`, `regime.implication`. Also **R3, R4, R6, R7, R8** (`srm[].*`, `thematic_baskets.*`, `regime_stop_pct_ceiling`).
  - oneil **R1** — fields `srm_weather`, `macro_brief`. C1: *"Only buy when the general market is in a Confirmed Uptrend. The market gate is a hard pass/fail that runs BEFORE"* everything else.
  - steenbarger **R3** — *"a nomination cannot name the market environment/regime it is valid inside → block"*, fields `regime`, `srm`.
- **Unblocks:** druckenmiller stops being a 7-field per-ticker seat and becomes the macro seat
  the charter seats him as; oneil's C1 market gate becomes evaluable instead of asserted;
  steenbarger's R3 block becomes checkable instead of always-fires.
- **Acceptance test:** every voice packet for druckenmiller, oneil and steenbarger carries a
  non-empty `global` object whose `regime.vix`, `srm[0].entry_gate` and
  `macro_weather.regime_description` are byte-identical to the same paths in the source
  `aqe_daily_export.json`; a seat that is not in `GLOBAL_MENUS` gets no `global` key at all.
- **Effort: S.** Pure wiring — the data, the relay pattern and the schema all already exist.

---

### B-02 — Raw-bar context block on every row
*(3 voices)*

- **What:** `daily_list[].bars` — target paths `bars.prior.open/high/low/close`,
  `bars.today.open/high/low/close`, `bars.high_20d`, `bars.low_20d`, `bars.nr4`, `bars.nr7`,
  `bars.id_nr4`, `bars.range_ratio_6_100`, `bars.tick_size`.
- **Definition:** the last two closed daily bars in full, the exact rolling 20-day high and low
  as counted values (not the `sma_distance_pct` approximation), and the narrow-range flags.
  `nr4` = today's high−low is the narrowest of the last 4 bars; `nr7` = narrowest of the last 7;
  `id_nr4` = `nr4` AND today's H/L is inside the prior bar's H/L. `range_ratio_6_100` =
  `mean(range, 6) / mean(range, 100)`. `tick_size` = 0.01 for any US equity quoted ≥ $1.00,
  0.0001 below (Reg NMS Rule 612) — a constant, not a feed.
- **Inputs:** the daily OHLCV panel already held per ticker — `src/data/panel_builder.py` pulls
  5+ years from FMP and caches it (*"Engines need at most 252 trading days"*). No new data.
- **Where:** new `src/engines/bars_context.py` (pure function on an OHLCV frame, same shape as
  `src/engines/pin_bar.py`) + register in `src/data/drive_sync.py` alongside the existing
  `candle` lookup block (~line 1100, `fields.update((lk.get("candle") or {}).get(tk) or {})`).
- **Requested by:**
  - raschke **C12** — *"ID/NR4 — an inside day that is ALSO the narrowest range of the last four — precedes trend days"*; **C3** TURTLE SOUP needs *"a new 20-day low"* as a count; **C13** volatility auto-correlation needs the 6-vs-100 range ratio.
  - seow **R2** (`prior_bar_high`, `high`, `tick_size`), **R5** (`prior_bar_low`, `prior_day_low`, `tick_size`), **R9** (`close`, `open`, `low`). **C5**: *"Place a buy stop one tick above the PRIOR DAY'S HIGH"*; **C10**: *"Trail the stop one tick below the PREVIOUS DAY'S LOW and re-set it every session."*
  - wyckoff **C5** — *"A 2Bar NR is the narrowest two-day range… contraction precedes expansion, and it is measured, not eyeballed (Crabel)"*; **C4** — *"the smallest unit of the read is a sequence of two adjacent bars."*
- **Unblocks:** seow's entry trigger and trailing stop stop being unimplementable (his canon
  specifies both to the tick and neither input exists); raschke's two highest-frequency setups
  (ID/NR4, Turtle Soup) become detectable; wyckoff's two-bar unit of read becomes computable.
- **Acceptance test:** every `daily_list` row carries a `bars` object with non-null
  `prior.high`, `prior.low`, `today.close`, `high_20d`, `low_20d` and boolean `nr4`/`nr7`;
  spot-check 3 tickers by pulling the same 20 daily bars from FMP by hand and confirming
  `high_20d` equals `max(high)` over exactly the last 20 closed sessions and that `nr4` is true
  iff today's range is strictly the smallest of the last 4.
- **Effort: M.** New engine module, straightforward maths, but it touches the exporter row
  shape and the export schema contract.

---

### B-03 — 52-week band and 11-month monthly high/low ladder
*(3 voices)*

- **What:** `daily_list[].high_52w`, `.low_52w`, `.pct_off_52w_high`, `.pct_above_52w_low`,
  and `daily_list[].monthly_hl[]` — an 11-element array of `{month, high, low}`, oldest first.
- **Definition:** the 52-week high and low from the daily panel (252 sessions), the two
  derived distances as percentages, and the last eleven completed calendar months' highs and
  lows. The array is the band Thorp's C23 rule is stated against.
- **Inputs:** the daily OHLCV panel (`src/data/panel_builder.py`); month grouping mirrors the
  existing weekly resample in `src/data/fmp_client.py::resample_to_weekly`.
- **Where:** `src/engines/enrichment.py` (it already owns derived per-row reads such as
  `rs_down_day_20d`) + `src/data/drive_sync.py` to export.
- **Requested by:**
  - thorp **R2** (`high_52w`, `low_52w`), **R5** (`monthly_high_11`, `monthly_low_11`), **C3** — *"Test the band you are relying on against how often stocks actually move that far over the intended holding period"*; **C23** — *"A stock trading above its eleven-month average tends to have its options priced below model value."*
  - minervini **C3** THE TREND TEMPLATE — two of the eight all-or-nothing criteria are stated against the 52-week band (within 25% of the 52-week high, at least 30% above the 52-week low). The seat currently proxies both with `sma_distance_pct`, which is not the same test.
  - oneil **C17/C24** — the pivot-extension and climax reads are anchored on the name's own high, not on a moving average.
- **Unblocks:** minervini can run the Trend Template as written instead of as approximated —
  this is the seat's entire first filter; thorp gets the price band his sizing rule needs.
- **Acceptance test:** every `daily_list` row carries non-null numeric `high_52w` and `low_52w`
  with `low_52w < bracket.price < high_52w` (or an explicit flag if price is at a new extreme),
  and `monthly_hl` has exactly 11 elements; spot-check 3 tickers against FMP
  `chart/historical-price-eod-full` by hand.
- **Effort: S.** Rolling max/min over an already-loaded frame plus a month groupby.

---

### B-04 — Days to earnings, exported as a number
*(3 voices)*

- **What:** `daily_list[].days_to_earnings` (int, null if unknown) and
  `daily_list[].next_earnings_date` (ISO date string, null if unknown).
- **Definition:** calendar days from the export date to the name's next scheduled earnings
  release. Today the export ships only `subcomponents.structure.earn_score`, the 0/4/7/10 band
  — which cannot distinguish "reports tomorrow" from "reports in 4 days", since both score 0.
- **Inputs:** none new. `src/data/earnings.py::days_to_earnings(ticker, as_of, cal)` already
  computes exactly this number and `earn_proximity_score()` immediately discards it into a band.
  The FMP earnings calendar is already pulled (2 API calls, ~90 days forward coverage).
- **Where:** `src/data/earnings.py` (return the raw value alongside the score),
  `src/engines/structure.py` (carry it through), `src/data/drive_sync.py` (export it).
- **Requested by:**
  - detect-lens **R11** — *"no event flag is served in the field set — event_flag NOT_SERVED — so I flag the exclusion question to the committee's blocking event filter"*. The seat's own PMA note called this *"the single largest hole in this nomination."*
  - oneil **C7/C12** — the base and breakout arithmetic is invalidated by an earnings print inside the handle.
  - The committee's blocking event filter itself (**Charter §0.3a**) — it currently has no day count to gate on.
- **Unblocks:** the event filter becomes a real gate rather than a declared intention;
  detect-lens can stop flagging every name as possibly-event-driven.
- **Acceptance test:** every `daily_list` row carries `days_to_earnings` as an integer or an
  explicit null, and for every row where `subcomponents.structure.earn_score == 0.0` the value
  is `<= 5`; spot-check 3 tickers against FMP `calendar/earnings-company` by hand.
- **Effort: S.** The function exists; this is plumbing a value that is already computed.

---

### B-05 — Stochastic %K/%D, CCI(20), SMA40 and SMA20 slope
*(2 voices)*

- **What:** `daily_list[].stoch_k`, `.stoch_d`, `.cci_20`, `.ma_40`, `.ma_20_slope_5d`.
- **Definition:** daily stochastic `%K` over 14 with `%D` = SMA(%K, 3);
  `CCI(20) = (typical − SMA(typical,20)) / (0.015 × mean absolute deviation)` where
  `typical = (H+L+C)/3`; simple 40-day moving average; and the 5-session change in `ma_20`
  expressed as a percentage (positive = rising).
- **Inputs:** the daily panel plus `src/engines/utils.py`, which already ships
  `stochastic_k(C,H,L,n)` (used by `k39.py` on weekly bars) and `sma(x,n)`. Only CCI is new maths.
- **Where:** `src/engines/utils.py` (add `cci`), new small block in `src/engines/enrichment.py`,
  export via `src/data/drive_sync.py`.
- **Requested by:**
  - seow **R1** — fields `sma20`, `sma40`, `sma20_slope_5d`, `cci20`. **C1**: *"Judge the chart with exactly two instruments and no more: a 20-period and a 40-period SIMPLE moving average."* **C2**: *"Go long only when the moving average is sloping up."* The 40-day average is the method's own trend line and AQE has never exported it.
  - raschke **C5** — MOMENTUM PINBALL and the 2-PERIOD ROC; the canon's stochastic-based read of *"tomorrow's likely direction"*.
- **Unblocks:** seow's C1/C2 direction gate — the seat is currently reading a 20/50/100/200
  stack that is not its method at all; raschke gets the oscillator her canon is written on.
- **Acceptance test:** every `daily_list` row carries non-null numeric `ma_40`, `cci_20`,
  `stoch_k`, `stoch_d`; spot-check 3 tickers by recomputing `ma_40` as the plain mean of the
  last 40 closes and `cci_20` from the stated formula by hand.
- **Effort: S.** Three of the five reuse existing helpers.

---

### B-06 — 63-day relative performance triad
*(2 voices)*

- **What:** `daily_list[].ret_63d`, `.ret_63d_spy`, `.ret_63d_group`, `.rs_rank_63d_in_group`.
- **Definition:** the name's 63-session percentage change, SPY's over the same window, and the
  name's GICS sector ETF's over the same window; plus the name's rank within the set of scanned
  names sharing its `gics_sector`. Group = the sector ETF already mapped on every row
  (`gics_sector`), used as the industry-group proxy — say so in the field glossary, since it is
  a sector proxy and not a true IBD industry group.
- **Inputs:** the daily panel, which already carries SPY and all 11 GICS ETFs (SRM grades them
  daily); `src/data/sector_mapper.py` for the mapping.
- **Where:** `src/engines/enrichment.py` + `src/data/drive_sync.py`.
- **Requested by:**
  - seow **R8** (`stock_pct_change_63d`, `index_pct_change_63d`, `industry_group_pct_change_63d`), **C6** — *"Do not take a long in a name weaker than what it trades against. Measure the stock's performance against the b[enchmark]."*
  - oneil **C9** — *"Buy strictly the number 1, 2 or 3 stock in its industry group, measured on current and annual earnings growth"* — the price half of that ranking; **C10** RS gate.
- **Unblocks:** seow's C6 relative-strength gate, which today has no input at all; oneil's
  group-rank test gets its price component (the earnings component is **S-01**).
- **Acceptance test:** every `daily_list` row carries non-null numeric `ret_63d`, `ret_63d_spy`,
  `ret_63d_group`, and `rs_rank_63d_in_group` is a dense rank starting at 1 within each
  `gics_sector`; spot-check 3 tickers against FMP `chart/historical-price-eod-light` by hand.
- **Effort: S.**

---

### B-07 — Realised-exit ledger joined to the live bracket
*(2 voices)*

- **What:** a new artifact `aegis/data/eod/exit_ledger.json` with rows
  `{ticker, entry_date, entry_px, exit_date, exit_px, bracket_stop_at_entry,
  bracket_tp1_at_entry, bracket_tp2_at_entry, exit_vs_stop_r, exit_vs_tp1_r, exit_reason}`,
  plus a rolled-up `summary.exit_inside_stop_pct` and `summary.exit_inside_tp1_pct`.
- **Definition:** for every closed position, the realised exit price set against the bracket
  levels that were actually live at entry, expressed in R. The point is to detect the systematic
  case where realised exits sit *inside* the bracket's own levels — i.e. the levels are not
  what the book actually trades.
- **Inputs:** no new vendor. Broker fills are already pulled (Tiger `get_filled_orders` /
  `get_order_transactions`, IBKR `get_account_trades`), the held book is refreshed by
  `aegis/tools/held_book_refresh.py`, and the bracket-at-entry is already recorded by
  `signal_ledger.py` / `aegis/tools/nomination_ledger.py`.
- **Where:** new `aegis/tools/exit_ledger.py`, called from the PTJ CLOSE path
  (`aegis/skills/print-trade-journal/`).
- **Requested by:**
  - steenbarger **R11** — *"if realised exits are systematically inside the bracket's own stop/target levels"* → the recogniser exists and can never fire, because the comparison data is not assembled anywhere.
  - thorp **C13** — *"Score a rule on every position it would have generated on those dates, not on the ones that worked."*
  - seow **C9–C12** (four concurrent stops) reads the same ledger to check its own trailing discipline.
- **Unblocks:** the only feedback loop in the system between what the bracket said and what the
  book did. Without it, every bracket parameter is untested forever.
- **Acceptance test:** `exit_ledger.json` contains one row per closed position in the trade
  journal, each with a non-null `exit_px` and a non-null `bracket_stop_at_entry`;
  `summary.exit_inside_stop_pct` recomputed by hand over 3 closed trades matches.
- **Effort: M.** The data all exists; the join and the historical backfill are the work.

---

### B-08 — Signal evidence block: trade counts, sample window, baseline separation
*(2 voices)*

- **What:** a new export root block `signal_evidence` keyed by signal id, each entry
  `{signal_id, rule_text, sample_start, sample_end, trade_count, trades_per_week, win_rate,
  expectancy_r, baseline_expectancy_r, separation_r, method}`.
- **Definition:** for every signal any voice is allowed to cite as a reason, the measured
  forward-return separation from a stated baseline and the number of trades that measurement
  rests on. A signal with no entry here is citable as description but never as edge.
- **Inputs:** partly assembled already. `data/active_recipe.json` embeds a Precision-Edge
  backtest record (37.2% win rate, 2031 trades, 7.1/week, expectancy 0.64R, Sep 2020–May 2026)
  — that is one entry in the shape required. `src/analyzer/baselines.py` and
  `src/analyzer/capacity.py` are the offline calibration tooling that produces these numbers;
  the glossary notes both are *"not part of the live `aqe_daily_export.json` path."* This ticket
  promotes their output onto the live path. `data/signal_engine_params.json` holds the frozen
  Signal Radar detection rates, which are **detection rates, not win rates** — the block must
  label them as such (glossary §5.1).
- **Where:** `src/analyzer/baselines.py` (emit a stable artifact), `src/data/drive_sync.py`
  (attach as a root block).
- **Requested by:**
  - steenbarger **R1** — *"a nomination cites a signal/field whose forward-return separation from baseline has never been measured → flag UNPROVEN (C1)"*; **R2** — *"a signal's measured forward returns match baseline → propose RETIREMENT, not reparameterisation"*; **C1/C2**.
  - thorp **R6** (`signal_id`, `backtest_trade_count`, `rules_generated_count`, `sample_start`, `sample_end`); **C12** — *"Refuse any rule whose only support is that it fitted the history"*; **C13**; **C15** — *"Carry the assumptions with every performance number — costs, leverage, and how fills were modelled."*
- **Unblocks:** steenbarger's entire seat. Today R1 fires on essentially every nomination
  because nothing is measured, which makes the flag information-free.
- **Acceptance test:** `signal_evidence` contains an entry for every signal id cited in any
  `VOICE_MENUS` field or Signal Radar tag, each with non-null `trade_count`, `sample_start`,
  `sample_end` and `baseline_expectancy_r`; a signal with no measurement is present with
  explicit nulls and `method: "UNMEASURED"`, never absent.
- **Effort: L.** The measurement discipline, not the plumbing, is the work — and the honest
  first delivery is mostly `UNMEASURED` rows, which is itself the finding.

---

### B-09 — VCP contraction sequence: count and depth
*(1 voice)*

- **What:** `daily_list[].vcp` — `vcp.contraction_count`, `vcp.contractions[]` (array of
  `{start, end, depth_pct, duration_days, avg_volume_ratio}`, oldest first), `vcp.is_tightening`.
- **Definition:** inside the current base, each successive pullback from a local high to the
  following local low, its depth as a percentage, and whether each contraction is shallower
  than the one before it. Minervini's pattern is *"two to six successive contractions, each
  shallower than the last, on progressively lighter volume"* — currently proxied on the menu by
  the scalar `flow` and `energy` composites, which cannot count anything.
- **Inputs:** `src/engines/bq.py` already runs a 3-mode base detector with a 60-bar pivot and an
  8% band and a latch/decay counter (`bq_base_days`, 159/162 populated);
  `src/scanner/levels.py::recent_pivot_lows` and `overhead_resistance` already return confirmed
  fractal pivots. The contraction sequence is the pivot pairs inside the latched base window.
- **Where:** new `src/engines/vcp.py` (consumes `bq.py`'s base window and `levels.py`'s pivots),
  export via `src/data/drive_sync.py`.
- **Requested by:** minervini **C4** — *"THE VOLATILITY CONTRACTION PATTERN (VCP) is the base's
  technical footprint under accumulation: two to six successive [contractions]"*; **C5** — *"THE
  PIVOT BUY POINT is the final, tightest contraction of the VCP, on very low volume"*; **C6** —
  the volume signature at every stage.
- **Unblocks:** minervini's actual entry trigger. The seat can identify a base today but not the
  pivot inside it, which is the only price its canon authorises a buy at.
- **Acceptance test:** every `daily_list` row where `subcomponents.structure.base_score > 0`
  carries a `vcp` object with an integer `contraction_count` and a matching-length
  `contractions[]`; spot-check 3 tickers by eye against their daily chart and confirm each
  listed `depth_pct` equals `(high − low) / high × 100` for that leg.
- **Effort: M.**

---

### B-10 — Elder's own instruments: Force Index, impulse colour, channel, weekly trend
*(1 voice, 7 principles)*

- **What:** `daily_list[].elder_own` — `.force_index_raw`, `.force_index_2`, `.force_index_13`,
  `.fi13_above_zero`, `.impulse_color_today`, `.impulse_color_prior`, `.channel_upper`,
  `.channel_lower`, `.channel_coefficient`, `.channel_slope_state`, `.weekly_trend`.
- **Definition:** `force_index_raw = (close − close_prior) × volume`, sign retained; `force_index_2`
  and `force_index_13` are its 2- and 13-bar EMAs. `impulse_color` is the three-state
  green/blue/red already computed inside `elder.py` but collapsed into `elder_score` before
  export — this ticket surfaces the colour itself for today **and the prior bar**, because the
  canon's strongest signal is a colour *vanishing*, which requires two readings. The channel is
  fitted, not drawn: raise the coefficient on `EMA13 ± k × mean|close − EMA13|` until the band
  contains 90–95% of the last N bars, and export `k`. `weekly_trend` is the direction of the
  weekly EMA13, joined look-ahead-safely.
- **Inputs:** `src/engines/elder.py` already computes EMA13, MACD histogram, `impulse_green` /
  `impulse_red` and the slope — the colour exists internally. `src/engines/utils.py` ships `ema`
  and `asof_weekly_value` (the same no-look-ahead weekly join `k39.py` uses).
- **Where:** `src/engines/elder.py` (return the colour and the channel rather than only the
  score), export via `src/data/drive_sync.py`.
- **Requested by:** elder-lens **C5** (*"The Force Index is one number a day: today's close less
  yesterday's close, sign retained, multiplied by today's [volume]"*), **C6** (2-day EMA as a
  pullback timer), **C7** (13-day EMA as the regime layer, zero crossings), **C4** (*"The best
  signals come from a colour vanishing, never from a colour being present"* — needs the prior
  bar), **C11** (*"Channels are fitted, never drawn by eye. Move the coefficient until the band
  holds 90 to 95 percent of the actual [bars]"*), **C12** (channel slope classifies the regime),
  **C21** (*"Read the higher timeframe first and the trading timeframe second"*).
- **Unblocks:** seven of this seat's 24 principles are currently unevaluable. The seat is named
  for the Impulse System and cannot see the impulse — only a 0–10 blend of it.
- **Acceptance test:** every `daily_list` row carries a non-null `elder_own.force_index_13` and
  an `impulse_color_today` in `{GREEN, BLUE, RED}`; the channel contains between 90% and 95% of
  the last 100 closes for every row; spot-check 3 tickers by computing
  `(close − close_prior) × volume` for the last bar by hand.
- **Effort: M.**

---

### B-11 — Wyckoff turning points and the wave triad
*(1 voice)*

- **What:** `daily_list[].wyckoff` — `.range_high`, `.range_low`, `.penetration`
  (`NONE | SPRING | UPTHRUST`), `.penetration_volume_ratio`, `.penetration_type` (1/2/3),
  `.recovered`, `.secondary_test`, `.shakeout`, and `.waves[]` (last N waves, each
  `{direction, length_pct, cum_volume, duration_days}`).
- **Definition:** the trading range's own boundaries; a penetration below `range_low` that fails
  to follow through and reverses is a **Spring**, the mirror above `range_high` is an
  **Upthrust**; the type is graded *by the volume of the penetration, not its depth*. A wave is
  a directional run between confirmed pivots — not a bar and not a fixed period — carrying
  exactly three measurements: length, cumulative volume, duration.
- **Inputs:** `src/scanner/levels.py` already produces confirmed 5-bar fractal pivots, the
  current swing high/low and clustered overhead resistance; the daily panel carries the volume.
  `structure_shift` already computes BOS/CHoCH against the same swing anchors.
- **Where:** new `src/engines/wyckoff_events.py`, export via `src/data/drive_sync.py`.
- **Requested by:** wyckoff **C7** (*"A Spring is a washout below a support level that fails to
  follow through and reverses upward"*), **C8** (*"Springs are graded by the volume of the
  penetration, not by its depth"*), **C9** (a Type 1 spring *"requires a secondary test: a
  light-volume, narrow [bar]"*), **C10** (Upthrust), **C19** (*"A wave… has exactly three
  measurements"*), **C20** (the three wave rules that *"decide entries and exits"*).
- **Unblocks:** the seat's entry trigger. Wyckoff is currently served 13 of 20 requirements but
  none of them is the spring/upthrust event his method actually enters on.
- **Acceptance test:** every `daily_list` row carries a `wyckoff` object with non-null
  `range_high`, `range_low` and a `penetration` value from the enum; `waves[]` has at least one
  element for any row with ≥ 60 bars of history; spot-check 3 tickers by eye against their chart
  and confirm each flagged SPRING has `penetration_volume_ratio` and a low below `range_low`.
- **Effort: L.** Event detection with a confirmation lag and a state machine; the highest-risk
  ticket in Part B.

---

### B-12 — `avg_daily_volume` and dollar liquidity
*(1 voice)*

- **What:** `daily_list[].avg_daily_volume_20d`, `.avg_daily_volume_50d`, `.avg_dollar_volume_20d`.
- **Definition:** mean share volume over the trailing 20 and 50 sessions, and mean
  `close × volume` over 20. Note `rvol`/`day_vol` is a *ratio* to this average — the average
  itself has never been exported, so no seat can apply an absolute liquidity floor.
- **Inputs:** the daily panel. `src/data/drive_sync.py::_compute_v21_lookups` already computes
  `mean of the prior 20 sessions' volume` internally at line ~843 as the denominator of the
  volume ratio, then discards it.
- **Where:** `src/data/drive_sync.py` (return the denominator it already has).
- **Requested by:** thorp **R8** (`avg_daily_volume`), **C24** — *"Break a tie on what it costs
  to get in and out — spread, liquidity and the capital the position ties up."* Also oneil **C8**
  — *"daily volume must average several hundred thousand shares so the position can be exited"*
  — an absolute floor the seat cannot currently apply.
- **Unblocks:** oneil's C8 supply-and-demand floor; the liquidity half of thorp's tie-break.
- **Acceptance test:** every `daily_list` row carries a non-null positive
  `avg_daily_volume_20d`, and `rvol × avg_daily_volume_20d` equals today's raw volume to within
  rounding for 3 hand-checked tickers.
- **Effort: S.** The value is already computed and thrown away.

---

### B-13 — Held-position trade state
*(1 voice)*

- **What:** on `held_positions[]` only — `.days_held`, `.high_since_entry`,
  `.low_since_entry`, `.prior_day_low`, `.pct_from_entry`.
- **Definition:** sessions elapsed since `trade_date`, the highest high and lowest low printed
  since entry, and the prior session's low (the trailing-stop reference).
- **Inputs:** `held_positions[]` already carries `trade_date`, `entry`, `cob_price` and
  `live_px`; the daily panel supplies the bars since. `src/analyzer/held_book.py` already does
  pure arithmetic on this block.
- **Where:** `src/analyzer/held_book.py` + `src/data/drive_sync.py`.
- **Requested by:** seow **R6** (`days_held`, `high_since_entry`), **C11** — *"Impose a time stop
  at day 5. If by the fifth day the profit objective has not been reached… "*; **C9** —
  breakeven stop *"once the trade has gained more than 5% from the ideal entry price"*;
  **C10** — the daily ratchet.
- **Unblocks:** three of seow's four concurrent stops (C12 requires all four to run at once).
- **Acceptance test:** every `held_positions` row carries a non-null integer `days_held` equal
  to the count of US trading sessions between `trade_date` and the export date, and
  `high_since_entry >= entry` or an explicit flag; hand-check all 12 held rows.
- **Effort: S.**

---

### B-14 — Universe-level edge statistics for the screen
*(1 voice)*

- **What:** extend the export root `summary` block with `.median_edge_today`,
  `.median_edge_trailing_60d`, `.candidates_passing_count`, `.candidates_passing_trailing_median`.
- **Definition:** today's median expected edge across names that passed the screen, set against
  its own trailing 60-session median, plus the pass count against its trailing median. The point
  is to detect the screen going quiet — which Thorp treats as an output, not a failure.
- **Inputs:** `summary` already exists at export root
  (`{daily_count 162, longlist_count 105, elder_count 109, ledger_count 9, held_count 12,
  runner_count 2, premove_count 16}`); the trailing series needs
  `src/engines/historical_store.py`, which already persists prior runs.
- **Where:** `src/data/drive_sync.py` + `src/engines/historical_store.py`. Routing to the seat
  is **B-01** (`summary` is a root block, not a row field).
- **Requested by:** thorp **R7** (`signal_edge_current`, `signal_edge_trailing_median`,
  `candidates_passing_count`), **C21** — *"When nothing passes the screen, hold nothing and say
  so — long flat stretches are an output of a working method."*
- **Unblocks:** thorp's "is the screen still alive" test, and with it C19/C20 edge-decay monitoring.
- **Acceptance test:** the root `summary` carries non-null numeric `median_edge_today` and
  `median_edge_trailing_60d` on any run where ≥ 20 prior runs are in the historical store, and
  explicit nulls with a stated reason below that; hand-check the median against the day's
  passing rows.
- **Effort: M.** Needs a defined "edge" — recommend `bracket.rr_tp2` on valid brackets, stated
  in the glossary, and confirmed by the PM before implementation.

---

### B-15 — `nomination_count` and tally metadata wired into the challenge seat
*(1 voice — Aegis-side, not AQE)*

- **What:** on the rogers packet only — `nomination_count`, `nominating_seats[]`,
  `mean_conviction` per name in the deliberation set.
- **Definition:** how many committee seats nominated each name, which ones, and the mean
  conviction. This is committee tally metadata produced at premarket step 6; it is **not** an
  AQE field and must never be requested from AQE.
- **Inputs:** the tally already produced by the committee funnel
  (`aegis/tools/conviction_funnel.py`, `aegis/tools/nomination_ledger.py`).
- **Where:** `aegis/tools/pma_run.py` (the challenge-stage packet) and the rogers card in
  `aegis/packaging/build_claude.py`. The code comment beside his menu already states the
  problem verbatim: *"his load-bearing input — nomination_count / conviction / nominating seats
  — is TALLY metadata from premarket step 6, NOT a universe field, and must be passed in by the
  orchestrator. Unwired, this seat has nothing to stand on."*
- **Requested by:** rogers **R1** (fields `ticker`, `rank`), **C3** protocol rule 1, **C5** —
  *"Monitor the ratio of bullish [to bearish opinion]"* — the crowding instrument the whole
  challenge seat is built on.
- **Unblocks:** the challenge seat entirely. It runs after the tally and currently cannot see it.
- **Acceptance test:** the rogers packet for a run with ≥ 2 nominations carries a
  `nomination_count` ≥ 2 for at least one ticker, and the sum of `nomination_count` across the
  deliberation set equals the total nomination count in `consensus.json`.
- **Effort: S.** Included here rather than in Part D because it is small, actionable and the
  seat is inert without it — but flagged clearly as an **Aegis orchestrator change, not an AQE one**.

---

### B-16 — In-house market breadth from AQE's own scan pool
*(1 voice served directly; supports 3 — see S-03)*

- **What:** export root block `breadth` — `.advancers`, `.decliners`, `.ad_line`,
  `.ad_line_10d_change`, `.new_highs_52w`, `.new_lows_52w`, `.pct_above_ma50`, `.pct_above_ma200`.
- **Definition:** computed across the full scored pool (`signal_radar.n_scored` = 602 names on
  the reference run), not the 162-row `daily_list`. This is a *proxy* for NYSE-wide breadth and
  must be labelled as such in the glossary — it is a 602-name universe, not the exchange.
- **Inputs:** the daily panel for the whole scan universe; `high_52w`/`low_52w` from **B-03**;
  `ma_50`/`ma_200` already computed per row.
- **Where:** `src/data/drive_sync.py` (aggregate before the row loop). Routing is **B-01**.
- **Requested by:** druckenmiller **R4** — currently a literal `NOT_SERVED: advance-decline line;
  new-high/new-low counts` entry in his canon lock; **C6** breadth quality. oneil **C2** —
  *"Call the top by counting distribution days"* — needs index-level participation. raschke
  **C16** — partially (TICK and TRIN are **S-03**; A/D is served here).
- **Unblocks:** replaces one of druckenmiller's five hard `NOT_SERVED` declarations with a
  stated-scope proxy he can actually cite.
- **Acceptance test:** the root `breadth` block carries integer `advancers` and `decliners`
  summing to at most `signal_radar.n_scored`, and `new_highs_52w + new_lows_52w <= n_scored`;
  hand-check `advancers` against a direct count of positive daily returns in the panel.
- **Effort: M.**

---

## 4. PART C — SOURCE tickets

Same shape as Part B, plus candidate provider. **FMP is already wired** —
`src/data/fmp_client.py`, `/stable/` endpoints, throttled, with a Starter+ key. Where FMP
covers a requirement, no alternative is named.

**Ordered by number of voices unblocked, descending.**

---

### S-01 — Company fundamentals block
*(5 voices — the single largest gap in the system)*

- **What:** a per-ticker `fundamentals` object on `daily_list[]` — `.eps_ttm`, `.eps_growth_qoq_yoy`,
  `.eps_growth_last_3y[]`, `.eps_accel_flag`, `.pe`, `.peg`, `.dividend_yield`, `.roe`,
  `.sales_growth_yoy`, `.market_cap`, `.shares_float`, `.cash`, `.long_term_debt`, `.bank_debt`,
  `.inventory`, `.inventory_growth_yoy`, `.operating_cash_flow`, `.capex`, `.free_cash_flow_yield`,
  `.business_description`.
- **Definition:** the standard fundamental set. Note the specific derived fields the canons
  demand by formula, which must be computed here and not left to the voice: Lynch PEG
  (`pe / long_term_growth_rate`), Yield-Adjusted PEG (`(growth + yield) / pe`), Net Cash
  (`cash − long_term_debt`), Effective P/E (`(price − net_cash_per_share) / eps`), the
  balance-sheet test (`equity / (equity + debt)`), FCF Yield (`(ocf − capex) / market_cap`) and
  the Supply Chain Ratio (`inventory_growth / sales_growth`).
- **Inputs:** none in AQE. This is genuinely absent.
- **Where:** new `src/data/fundamentals.py` (mirroring `src/data/earnings.py`'s cache-and-load
  shape), cached to `data/persistent/`, joined in `src/data/drive_sync.py`.
- **Candidate provider — FMP, already wired.** Coverage is complete:
  `statements/key-metrics-ttm` (P/E, ROE, FCF yield, market cap), `statements/metrics-ratios-ttm`
  (payout, debt ratios), `statements/income-statement` (`period="quarter"`, EPS by quarter →
  the QoQ/YoY acceleration test), `statements/income-statement-growth` and
  `statements/financial-statement-growth` (3-year EPS and sales growth), `statements/balance-sheet-statement`
  (cash, long-term debt, inventory, equity), `statements/cashflow-statement` (operating CF, capex),
  `company/market-cap`, `company/shares-float`, `company/profile-symbol` (business description).
- **Cost / latency note:** ~7 calls per ticker. Fundamentals change quarterly, not daily —
  **run this weekly, not in the daily loop**, and cache. At ~600 names that is ~4,200 calls per
  week, well inside a Starter+ allowance at the existing throttle. Do not add it to the nightly
  path.
- **Requested by:**
  - lynch **C8** (Lynch PEG), **C9** (Yield-Adjusted PEG), **C10** (Net Cash Floor), **C11** (Effective P/E), **C12** (balance-sheet test), **C13** (FCF Yield), **C14** (Supply Chain Ratio), **C15** (*"Bank debt versus funded debt… Bank debt can be called on short [notice]"*), **C16** (capital intensity), **C24** (the fixed committee scorecard). Also **C3**, the Two-Minute Drill, which needs the business description.
  - oneil **C4** (*"Current quarterly EPS must be up at least +18–20% year over year"*), **C5** (deceleration red flag), **C6** (*"Annual EPS must have risen in each of the last three years at 25–50%, with return on equity at least 17%"*).
  - minervini **C12** (*"the earnings-growth profile of a genuine market leader… runs 20 percent or better"*), **C20** (the six-category maturation sort).
  - druckenmiller **R1** — currently `NOT_SERVED: market-level valuation (dividend_yield, price_book, pe)`.
  - rogers **C21** (*"THE VALUATION SANITY FILTERS… standard book value, earnings per [share], dividend yield"*).
- **Unblocks:** lynch is a fundamental seat with zero fundamental data — 5 of his 14
  requirements and 10 of his 24 principles are dead today. oneil's C4/C5/C6 are three of the
  four letters in CANSLIM. This ticket alone moves more requirements than the rest of Part C
  combined.
- **Acceptance test:** every `daily_list` row carries a `fundamentals` object with non-null
  `eps_ttm`, `pe`, `market_cap` and `sales_growth_yoy` for at least 90% of rows (ETFs and
  pre-revenue names legitimately null, and must carry an explicit `fundamentals_unavailable_reason`);
  spot-check 3 tickers' `pe` against FMP `statements/key-metrics-ttm` by hand.
- **Effort: L.** Not the fetch — the caching, the staleness policy and the seven derived
  formulas that must match each canon exactly.

---

### S-02 — Institutional sponsorship and insider ownership
*(3 voices)*

- **What:** `daily_list[].ownership` — `.institutional_holders_count`, `.institutional_pct`,
  `.institutional_holders_change_qoq`, `.top_holder_quality_flag`, `.insider_ownership_pct`,
  `.insider_net_buys_90d`.
- **Definition:** the count and quality of institutional sponsors, whether that count is rising,
  and insider ownership plus recent net insider buying.
- **Inputs:** none in AQE.
- **Where:** `src/data/fundamentals.py` (same weekly cache as S-01).
- **Candidate provider — FMP, already wired, but check the plan.** `form13F/positions-summary`
  (symbol, year, quarter) gives holder counts and share totals; `form13F/filings-extract-with-analytics-by-holder`
  gives the quality read; `insiderTrades` gives insider transactions and ownership.
  **Plan caveat: the `form13F` endpoints are documented as Ultimate/Enterprise.** `insiderTrades`
  is available lower. If the account is Starter+, deliver the insider half now and raise the
  13F half as a plan decision — do not silently ship a half-populated field.
- **Cost / latency note:** 13F is quarterly with a 45-day lag. The data is structurally stale by
  design; label it with `as_of_quarter` and never present it as current.
- **Requested by:**
  - oneil **C11** — *"Institutional sponsorship must be present, rising and of quality — at least twenty sponsors for a smaller [name]"*. This is the "I" in CANSLIM and it is a hard criterion, not a garnish.
  - lynch — market cap and institutional ownership (the low-institutional-ownership preference).
  - rogers **C16** THE BEAR SEARCH / NEGLECT PRICING — neglect is measured by ownership.
- **Unblocks:** oneil's C11, currently unevaluable.
- **Acceptance test:** every `daily_list` row carries `ownership.institutional_holders_count` as
  an integer or explicit null with `as_of_quarter` set; spot-check 3 tickers against FMP
  `form13F/positions-summary` by hand.
- **Effort: M.**

---

### S-03 — TICK, TRIN and true exchange breadth
*(3 voices)*

- **What:** export root `breadth_market` — `.tick_nyse_close`, `.tick_nyse_extreme_count`,
  `.trin_nyse`, `.ad_line_nyse`, `.new_highs_nyse`, `.new_lows_nyse`.
- **Definition:** exchange-wide breadth, as distinct from the 602-name in-house proxy in
  **B-16**. TICK is the net count of NYSE issues on an uptick; TRIN is the Arms Index.
- **Inputs:** none in AQE.
- **Where:** new fetch in `src/data/` alongside `fmp_client.py`; export root block.
- **Candidate provider — NOT FMP.** FMP does not serve TICK, TRIN or the NYSE A/D line.
  Its nearest offerings (`marketPerformance/sector-performance-snapshot`,
  `biggest-gainers`, `most-active`) are not substitutes and should not be presented as such.
  **Use IBKR, which is already wired** — `mcp__Interactive_Brokers_IBKR__get_price_history`
  against the index contracts (`TICK-NYSE`, `TRIN-NYSE`). Alternative if IBKR index data is not
  entitled: Polygon.io indices.
  **Deliver B-16 first** — the in-house proxy is free and covers most of the need; buy TICK/TRIN
  only if raschke's C16 is judged load-bearing.
- **Requested by:**
  - raschke **C16** — *"MARKET BREADTH — the NYSE TICK and the Arms Index (TRIN) — is read as a divergence and extremes tool."*
  - druckenmiller **R4** `NOT_SERVED: advance-decline line; new-high/new-low counts`; **C6**.
  - oneil **C2/C3** — distribution-day counting and the follow-through day are index-level reads.
- **Unblocks:** raschke's only breadth instrument.
- **Acceptance test:** the root `breadth_market` block carries a non-null numeric `trin_nyse`
  on every trading-day run, and the value sits in a plausible 0.3–3.0 band; cross-check one
  session against a public TRIN print by hand.
- **Effort: M.** Mostly entitlement and contract-lookup work, not code.

---

### S-04 — Sector and commodity fundamental drivers
*(2 voices)*

- **What:** export root `sector_drivers` — per GICS sector: `.commodity_inputs[]`
  (`{symbol, price, roc20}`), `.aggregate_capex_growth_yoy`, `.aggregate_inventory_growth_yoy`.
- **Definition:** the input-cost and capital-cycle read behind a sector's grade — what actually
  drives it, as opposed to what its price has done.
- **Inputs:** none in AQE.
- **Where:** `src/engines/srm.py` (attach to the existing sector grading) + `src/data/fundamentals.py`.
- **Candidate provider — FMP for the servable half.** `commodity` (spot and futures for copper,
  crude, gold, ags — covers input costs and the C15 margin-squeeze test) and
  `statements/cashflow-statement` aggregated across each sector's constituents (covers capex and
  inventory growth). **FMP does not serve physical supply, capacity or inventory volumes.** For
  energy specifically, the free EIA API covers production and stocks; for agriculture, USDA.
  **Recommendation: scope this ticket to the FMP-servable half only** and have druckenmiller and
  rogers declare physical supply/capacity permanently unserved (see D-08).
- **Requested by:**
  - druckenmiller **R6** — `NOT_SERVED: sector fundamental driver (capacity, supply, capex, earnings, expansion announcements)`; **C21/C22** require him to *name the factor that actually drives a sector*.
  - rogers **C10** — *"THE SUPPLY-DEMAND EQUATION. Basic Economics 101 always wins"*; **C15** — *"THE INPUT COST LOGIC TEST. Calculate the margin squeeze that rising raw-commodity costs impose on consumer-sta[ple names]."*
- **Unblocks:** rogers' C15 test, which is his single most mechanical rule and has no inputs today.
- **Acceptance test:** the root `sector_drivers` block carries a non-empty `commodity_inputs[]`
  for at least XLE, XLB and XLP, each entry with a non-null price and `roc20`; spot-check copper
  and crude against FMP `commodity` by hand.
- **Effort: L** for the full scope, **M** for the FMP-only scope recommended above.

---

### S-05 — Policy rate, curve and liquidity series
*(1 voice, but it is that seat's first-order input)*

- **What:** export root `macro_policy` — `.fed_funds_rate`, `.treasury_2y`, `.treasury_10y`,
  `.curve_2s10s`, `.real_10y`, `.cb_balance_sheet_usd`, `.cb_balance_sheet_change_13w`,
  `.next_policy_event`.
- **Definition:** the policy and liquidity backdrop, in levels and in direction.
- **Inputs:** none in AQE. The existing `intermarket.tlt.*` block is a *price proxy* for rates,
  not a policy series, and the canon says so.
- **Where:** new `src/data/macro.py`, export root block. Routing to the seat is **B-01**.
- **Candidate provider — FMP, already wired, for most of it.** `economics/treasury-rates` gives
  the full curve daily (2y, 10y → `curve_2s10s`); `economics/economics-indicators` (`name=`)
  gives the named series including the policy rate and CPI (→ `real_10y`);
  `economics/economics-calendar` gives `next_policy_event`. **FMP does not serve the central-bank
  balance sheet** — use FRED series `WALCL`, which is free and needs no key.
- **Cost / latency note:** 3 FMP calls per day, once per run, not per ticker. Negligible.
- **Requested by:** druckenmiller **R2** — *"a liquidity or central-bank-policy read is required
  — which is the first-order input for this entire seat"* — carrying the explicit
  `NOT_SERVED: policy rate / central-bank balance sheet / explicit liquidity series`.
- **Unblocks:** the seat's own stated first-order input. Everything druckenmiller does downstream
  is currently built on a rates *proxy* he has declared insufficient.
- **Acceptance test:** the root `macro_policy` block carries non-null `treasury_2y`,
  `treasury_10y` and `fed_funds_rate` on every run, with `curve_2s10s == treasury_10y −
  treasury_2y` to 2dp; cross-check one date against FMP `economics/treasury-rates` by hand.
- **Effort: S.** FMP is wired, the endpoints exist, the block is small.

---

### S-06 — Implied volatility per name
*(1 voice)*

- **What:** `daily_list[].iv_atm_30d`, `.iv_rv_ratio`.
- **Definition:** at-the-money implied volatility at roughly 30 days to expiry, and its ratio to
  the realised `vol_30d_ann` already on the row.
- **Inputs:** `vol_30d_ann` exists (162/162). IV does not.
- **Where:** new fetch beside the existing Alpaca path; export in `src/data/drive_sync.py`.
- **Candidate provider — NOT FMP.** FMP does not serve options IV. **Use Alpaca**, which the
  Charter §0.5 already designates as *the only Greeks source* (15-minute delayed) and which is
  already wired for the options book. Take ATM IV from the chain snapshot.
- **Cost / latency note:** 15-minute delayed is fine for a close-of-day scan. One chain snapshot
  per name is expensive at 162 names — restrict to names with `bracket.valid == true` (27 today)
  or to the deliberation set, and say which in the field glossary.
- **Requested by:** thorp **R5** (`implied_vol`), **C5**, **C7** — *"Correct any screen that
  prices a claim without volatility in it"*; **C23** — the eleven-month-average / option-pricing
  rule (its price half is **B-03**).
- **Unblocks:** thorp's implied-vs-realised comparison, the core of C7 and C23.
- **Acceptance test:** every row with `bracket.valid == true` carries a non-null positive
  `iv_atm_30d`, and `iv_rv_ratio == iv_atm_30d / vol_30d_ann` to 3dp; spot-check 3 tickers
  against a live Alpaca chain snapshot.
- **Effort: M.**

---

### S-07 — Bid/ask spread
*(1 voice)*

- **What:** `daily_list[].bid`, `.ask`, `.spread_bps`.
- **Definition:** the NBBO at the scan snapshot and the spread in basis points of the mid.
- **Inputs:** none in AQE. Note: `src/data/fmp_client.py::get_quotes` is already implemented
  against `/stable/quote`, but that payload is a last-price/volume quote — **it does not carry
  NBBO bid/ask**, so this cannot be served by widening an existing call.
- **Where:** `src/data/drive_sync.py` at the snapshot step.
- **Candidate provider — NOT FMP.** Use **Alpaca** (equity quote endpoint, already wired for the
  options book) or **IBKR** `get_price_snapshot`, which is already the charter's equity-spot
  fallback. Prefer IBKR — it is wired, entitled and already called on this path.
- **Requested by:** thorp **R8** (`bid`, `ask`), **C24** — *"Break a tie on what it costs to get
  in and out — spread, liquidity and the capital the position ties up."*
- **Unblocks:** the cost half of thorp's tie-break (the liquidity half is **B-12**).
- **Acceptance test:** every `daily_list` row carries non-null `bid` and `ask` with
  `bid <= bracket.price <= ask` on ≥ 95% of rows, and `spread_bps > 0`; hand-check 3 tickers
  against a live IBKR snapshot.
- **Effort: S.**

---

### S-08 — Positioning and sentiment
*(1 voice)*

- **What:** export root `positioning` — `.put_call_ratio`, `.short_interest_pct_float`,
  `.short_interest_days_to_cover`, `.aaii_bull_bear_spread`, `.fund_cash_pct`,
  `.cot_crowded_long[]`, `.cot_crowded_short[]`.
- **Definition:** what the crowd is already positioned in, as distinct from what price has done.
- **Inputs:** partially available already — the Crown macro artifact
  (`aegis/data/aqe/<date>/aqe_crown_macro.json`) carries
  `readings.positioning.large_speculators.crowded_long / .crowded_short / .as_of`,
  `readings.positioning.trend_funds.share_at_an_extreme / .bias / .size_dial` and
  `readings.positioning.option_dealers.detail.<TKR>.gamma_flip / .flip_distance_pct`.
  **That artifact is already ingested** — `aegis/tools/pma_run.py` S1 validates it against
  `aegis/contracts/pma/crown_macro.schema.json` and S2 relays it into `market_frame.crown`.
- **Where:** `src/data/macro.py` for the missing pieces; the Crown-sourced pieces need routing
  only (**B-01**).
- **Candidate provider — FMP for the COT half.** `commitmentOfTraders` covers large-speculator
  positioning directly (and duplicates what Crown already derives — prefer Crown, it is already
  in the pipeline). **FMP does not serve put/call ratio, short interest or sentiment surveys.**
  Free alternatives: CBOE publishes the daily equity put/call ratio; FINRA publishes bi-monthly
  short interest; AAII publishes its weekly survey. All three are scrape-or-CSV, not APIs —
  price that in.
- **Requested by:** druckenmiller **R5** — `NOT_SERVED: positioning / sentiment surveys / fund
  cash levels / put-call / short interest`; **C7**.
- **Unblocks:** one of druckenmiller's five hard `NOT_SERVED` declarations.
- **Acceptance test:** the root `positioning` block carries a non-null `put_call_ratio` on every
  trading-day run and a `short_interest_pct_float` per ticker with an explicit `as_of` no more
  than 20 days old; cross-check one name's short interest against the FINRA file by hand.
- **Effort: M.** Three separate non-API sources is the cost here, not the code.

---

## 5. PART D — WON'T BUILD

Do not schedule these. In each case the requesting voice must record the item in its own
`canon.lock.yaml` as **permanently unserved** — the same way druckenmiller already records his
five `NOT_SERVED:` entries inline in `recognisers[].fields`. An unserved requirement that is
*declared* is a working system; one that is silently absent is not.

| Item | Requested by | Why out of scope | What the voice should do instead |
|---|---|---|---|
| **D-01** Country, currency, sovereign debt, savings rate, demographics, rule of law | rogers **C24** Template A (Sovereign/Country Health Grade), **C19** | AQE is a US-equity single-name scanner. There is no country dimension in the universe — every name is one jurisdiction. Building a sovereign layer means building a different product. | Declare `NOT_SERVED: sovereign / country grade — single-jurisdiction universe`. Template A is retired for this seat; Template B (the company grade) stands. |
| **D-02** Black-market exchange parity gap | rogers **C8** — stated as a *HARD STOP, not a score adjustment* | Follows D-01. A US-listed equity has no black-market parity gap; the test is undefined here, not merely unmeasured. | Declare permanently unserved and remove the hard stop from the seat's live gate list, so it does not read as a gate that silently never fires. |
| **D-03** Order-fill difficulty as size is added / market-impact curve | livermore (voice_data_map row 25) | Requires Level 2 depth plus post-trade transaction-cost analysis. Neither broker connector on this system exposes equity depth (Tiger's depth tool is options-only), and no TCA is run. | Use the served proxies: `avg_dollar_volume_20d` (**B-12**) against intended position size, plus `spread_bps` (**S-07**). Declare the impact curve itself unserved. |
| **D-04** Ground visual verification; annual-report footnotes; press-release text | rogers **C13** (*"Do not rely on books; go and see the world"*), **C7**, **C21** | Not a data field. C13 is a research-conduct instruction to a human, and no feed satisfies it. | The business description and SEC filings *are* servable (**S-01** via FMP `company/profile-symbol` and `secFilings`). Declare footnote-reading and site visits as PM-only work, not agent work — the same agent/pm_only split already used in the steenbarger canon. |
| **D-05** A named catalyst forcing revaluation in 12–36 months | rogers **C23** — *"the seat's single most transferable test"* | A catalyst is a judgement about the future, not a field. Any "catalyst" column would be a model's opinion presented as data — the exact failure mode the charter's read-verbatim rules exist to prevent. | Keep it as a question the seat asks the committee in prose, answered by a human. Declare `NOT_SERVED: catalyst`. It stays load-bearing as a *test*, not as an input. |
| **D-06** Consensus ratio, ridicule signal, media sentiment | rogers **C5**, **C9**, **C11** | Requires a licensed media-sentiment feed and an editorial-tone model. FMP's `news` endpoint returns headlines, not a scored consensus ratio; building the scorer is a research project with no ground truth. | Use the served crowding proxies: `nomination_count` from the tally (**B-15**) and the volume-participation field for crowd participation. Declare the media-derived consensus ratio unserved. |
| **D-07** `lens.extension` populating | detect-lens **R5** | **Not a defect — a standing PM ruling.** The export's own `lens_ranking.extension_note` states: *"`extension` is data-only and NEVER counted. The voices disagree on what extension means, so AQE prints the numbers and makes no call."* The seat's R5 already routes around it: *"lens.extension is always null by PM ruling, and I point at the served numbers instead."* Verified 0/162 in the export, by design. | Nothing. The four substitute fields are CONFIG item **C-10** and are already on this document's Part A. Do not "fix" the null — fixing it would overturn a ruling. Confirm at **E-5**. |
| **D-08** Physical supply, capacity, production and inventory volumes | druckenmiller **R6**, rogers **C10** | Requires EIA / USDA / industry-body datasets per commodity, each with its own schema, revision policy and release calendar. That is a data-engineering programme, not a ticket, and it serves two seats partially. | Take the FMP-servable half in **S-04** (commodity prices, aggregate sector capex and inventory growth from company filings) and declare physical volumes permanently unserved. |

---

## 6. PART E — PM parameter decisions, not builds

Nothing below needs code until it is answered.

---

### E-1 — The regime stop-% ceiling: keep 8%, or loosen?

**Current setting** (`src/engines/bracket_engine.py:38-40`, `REGIME_STOP_CEILINGS`):

| Regime | VIX band | Stop-% ceiling |
|---|---|---|
| GREEN | ≤ 18 | **12%** |
| YELLOW | 18 < VIX ≤ 25 | **8%** |
| ORANGE | 25 < VIX ≤ 30 | **6%** |
| RED | > 30 | **4%** |

A stop candidate must pass **all three** charter gates to be `valid`: ATR floor
(`stop_atr_dist ≥ 1.0`), R:R floor (`rr_tp2 ≥ 2.0`) and this regime ceiling.

**What the export shows.** On 2026-07-28, `regime.level = "YELLOW"` with `regime.vix = 18.7`,
so `regime_stop_pct_ceiling = 8.0`.

| Reading | Count |
|---|---|
| `bracket.valid == true` | **27 / 162** |
| `bracket.valid == false` — *"no structural support passes the 3 gates"* | **134 / 162** |
| `bracket.valid == false` — *"no structural resistance above price"* | 1 / 162 |
| `bracket.stop`, `.risk_pct`, `.rr`, `.stop_type`, `.stop_atr_dist` populated | 27 / 162 each |

**This is not a defect.** It is the gate doing exactly what the charter specifies, and the
27/162 figure is the direct consequence.

**The question, framed.** VIX printed **18.7** — **0.7 above the GREEN/YELLOW boundary of 18.0**.
A 0.7-point VIX move takes the ceiling from 8% to 12% and materially changes how many names
carry a tradeable stop. Three options, all PM calls, none of them engineering:

1. **Keep 8%.** Accept that ~83% of a YELLOW day has no structural stop, and treat the survivors
   as the day's actual opportunity set. Nine voices then correctly read `PARTIAL (27/162)` on the
   entire stop family.
2. **Loosen the YELLOW ceiling** (e.g. 8% → 10%). Widens the pass rate; also widens per-trade
   risk on exactly the days the regime says to be careful.
3. **Move the VIX band**, not the ceiling — e.g. GREEN up to 20. Same net effect today at
   VIX 18.7, but a different statement about what "calm" means.

**Do not rebuild anything downstream of the bracket until this is answered.** The stop family is
the #1 deduplicated missing item across nine voices, and its entire "missingness" is this one
number.

---

### E-2 — The `day_vol` / `rvol` question — and it does not resolve the way the map implies

**This is the most important item in Part E. Read it before touching a menu.**

The brief anticipated confirming that the intended field is `rvol`, making it a CONFIG item.
**The evidence says the opposite.** Three sources, checked independently:

| Source | Says |
|---|---|
| `aegis/output/aqe_daily_export.json` (2026-07-28) | `rvol` present and populated **162/162**. `day_vol` **not present at all**, on any row. |
| `aegis/contracts/field_dictionary.json` | Has an entry for **`day_vol`**, none for `rvol`. Its own text: *"(formerly `rvol`) … Renamed rvol -> day_vol on 2026-08-05; same number, same formula."* |
| `src/data/drive_sync.py` (working tree, HEAD) | Emits **`day_vol`** at lines 427, 1099 and 1498. Commit **`865ec13`, 2026-08-05, "Rename the export field rvol -> day_vol, end to end"**. Confirmed present on `origin/main`. |

**The reconciliation.** The rename landed in code on 2026-08-05. The only export that exists is
dated **2026-07-28 — eight days before the rename**. So `day_vol` is not a phantom field; it is
a **field the exporter now emits and that no export has been generated for yet.** `rvol` is not
the "real" field; it is the **pre-rename name of the same number**, still visible only because
AQE has not re-run.

**Corroborating check:** the pull recorded at `aegis/data/aqe/2026-08-12/aqe_daily_export.json`
is **byte-identical** to `aegis/output/aqe_daily_export.json` (same md5 `3e69499d960f…`, same
`date: 2026-07-28`). AQE has produced no new export in 16 days. Every consumer is reading a
2026-07-28 file.

**What this means operationally, today.** The eight menus carrying `day_vol` (lynch, oneil,
wyckoff, raschke, steenbarger, thorp, minervini, rogers, livermore in the working tree) resolve
to **null** against the live file. `oneil` is the only seat carrying **both** `day_vol` and
`rvol`, and is therefore the only seat that can see volume participation at all today. That is
an accident, not a design.

**Three PM options:**

1. **Re-run AQE.** `day_vol` populates at 162/162, `rvol` disappears, and the eight menus are
   correct as written. Then delete the stray `"rvol"` from oneil's menu. **Recommended** — it
   is the smallest change consistent with a decision already taken and already merged.
2. **Emit both for one cycle.** Add `rvol` back to `drive_sync.py` as a deprecated alias
   alongside `day_vol` for N runs, then drop it. Costs one field of export width and removes
   all timing risk.
3. **Revert the rename.** Rewrite all menus, the field dictionary and `drive_sync.py` back to
   `rvol`. **Not recommended** — it reverses a landed, merged, end-to-end change on the strength
   of a stale artifact.

**Consequence for this document:** `rvol`/`day_vol` is deliberately **not** in Part A. It is one
line of menu change under option 1 or 3, and zero lines under option 2 — but which line depends
entirely on the answer. Adding `rvol` to eight menus now would be actively wrong under the
recommended option.

Note also that the canon locks themselves name `day_vol` in `recognisers[].fields` for
minervini **R3**, oneil **R4/R8**, raschke **R5**, rogers **R4**, wyckoff **R4/R5/R10** and
livermore **R5** — so the canon layer has already moved to the new name. Option 3 would require
re-signing seven canon locks.

---

### E-3 — PTRS drift: `CLAUDE.md` vs the code vs the export

- **`CLAUDE.md`** states `PTRS = SC_MOMENTUM + SH`.
- **`src/analyzer/ptrs.py`** computes `ptrs = engine_score + sh`, but **every live call site
  passes `sh = 0.0`** — the Sector-Health adjustment was formally retired by AIC Charter
  Amendment v2.8 (2026-07). The glossary flags this as documentation drift (§10, §15).
- **The export settles it: `ptrs == sc_momentum` on 162 / 162 rows.** Exactly, no exceptions.

**Decision required:** update `CLAUDE.md` to match the code, not the reverse. The glossary is
explicit that a stray `+SH` fork briefly survived live in `daily_orchestrator.py` until it was
found and killed on 2026-07-15 — leaving the doc saying `+ SH` is how that recurs.

This is a one-line documentation edit and it needs a PM signature because `CLAUDE.md` is the
system's top-level contract, not a comment.

---

### E-4 — `origin/main`'s `build_claude.py` is 25 commits behind the working checkout

Blocking for Part A.

| | Voices in `VOICE_MENUS` | `wyckoff` menu width | `rogers` / `livermore` seated |
|---|---|---|---|
| working checkout (HEAD `23ee038`) | **14** | 31 fields | yes |
| `origin/main` (`b1a61ca`) | **11** | 9 fields | no |

`origin/main`'s copy was last touched by `865ec13` (2026-08-05); the working checkout is
**25 commits ahead / 113 behind** on other paths. The voice-grounding work that widened these
menus (oneil 2026-08-06, minervini and raschke 2026-08-07, steenbarger 2026-08-10, and the
seating of rogers and livermore) exists only locally.

Both `voice_data_map.md` and `pma_data_taxonomy_2026-08-12.md` — **which are on main** — are
written against the *wide* menus. So main currently contains two design documents describing a
`build_claude.py` that main does not have.

**Decision required:** push the 25 commits, then apply Part A. Applying Part A to main's copy
as it stands would produce a `build_claude.py` that is neither version.

---

### E-5 — Confirm `lens.extension` stays null by ruling

`lens.extension` is present as a key on all 162 rows and null on all 162. The export's own
`lens_ranking.extension_note` says this is deliberate; detect-lens **R5** is written around it.

**Decision required:** a one-line confirmation that this remains the ruling. If it does, **D-07**
stands and the four substitute sub-scores (**C-10**) are the whole fix. If the PM wants it
populated, that becomes a BUILD ticket and detect-lens R5 must be re-signed.

---

### E-6 — Confirm four low-count fields are correct, not broken

Each of these reads as a gap on a coverage table and is not one. Confirm and record, so they
stop being re-raised every cycle:

| Field | Count | Why it is correct |
|---|---|---|
| `runner_conviction_label` | 2/162 | `runner_setup` is true on exactly **2** rows. 100% of eligible rows carry a label. |
| `premove_conviction_label` | 8/162 | `premove_setup` is true on exactly **8** rows in `daily_list`. (Root `summary.premove_count` = 16 — the other 8 are radar names outside the 162.) |
| `div_oscs`, `div_date` | 61/162 | Only populated where a divergence exists. `div_state` itself is 159/162. |
| `pin_bar_level`, `pin_bar_date` | 0/162 | `pin_bar_state` reads `"NONE"` on all 159 populated rows — no pin fired that session. Structurally correct, but see the caveat at **C-09**: it means the field is **unverified against live data** and should be re-checked on a session where a pin actually prints. |

---

## 7. Where the glossary and the real export disagree

Three places. In each case the export was trusted.

**1. `rvol` vs `day_vol` — the exporter code is ahead of the export artifact.**
`AQE_FIELD_GLOSSARY.md` names neither field anywhere (it documents volume only inside
`flow.volume_score` and `bq_vol_dry`). `contracts/field_dictionary.json` and
`src/data/drive_sync.py` both say **`day_vol`**; the export carries **`rvol`, 162/162**, and no
`day_vol` at all. **Trusted the export for what is readable today; trusted the code for what is
correct going forward.** Full reconciliation at **E-2**. This is the disagreement that matters.

**2. `subcomponents` and `elder_context` are present on 159 and 155 of 162 rows, not all of them.**
The glossary presents both as riding on every row (§1: *"surfaced on every `daily_list`/
`held_positions` row under `subcomponents`"*; §7: *"Rides on every longlist row"*). In the
export, **3 rows carry no `subcomponents` object** and **7 rows carry no `elder_context` object** —
they hold a bare null instead. Every field beneath them is therefore capped at 159/162 and
155/162 respectively, and Part A's counts reflect the real numbers, not the documented ones.
The glossary's own §14 note explains the mechanism (*"a NaN engine value is later converted to
JSON `null` by the export's `_num()` helper"*), but the row-level absence of the whole parent
object is not documented. **An implementer must null-guard the parent, not just the leaf.**

**3. `elder_pattern` is documented as a classifier that always returns, and is null on 37 rows.**
Glossary §7 lists `elder_pattern`'s priority ladder ending in `→ None`, so null is a legal
output — but it does not say how often. In the export it is **125/162 (77%)**, i.e. **37 rows
have no pattern**. Two seats read it as though it always resolves. Coverage tables that treat
`elder_pattern` as a `YES` field are overstating it by 23 percentage points; this document
grades it PARTIAL.

**One further mismatch, recorded but not a glossary defect.** The glossary's §9.1 already flags
its own known fork — Sector Health `TURNING = −3` in AQE's code versus `−5` in the charter text,
*"unreconciled"*. The export's `srm[].sh_value` follows the code (`DEPLOY = 3` observed on XLF).
No action requested here; noted so it is not rediscovered as new.

---

*Every field count in this document was measured against
`aegis/output/aqe_daily_export.json` (2026-07-28, 162 rows, md5 `3e69499d960f…`) by flattening
each `daily_list` row to dotted paths and counting non-null values. Where a count differs from
`AQE_FIELD_GLOSSARY.md` or from `voice_data_map.md`, the export is what is written here.*
