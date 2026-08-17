# Weis — grounded canon (2026-08-17), REPO-SAFE COPY (rev 2)

**Source:** David H. Weis, *Trades About to Happen: A Modern Adaptation of the Wyckoff Method*,
Wiley 2013. Full text read across 5 independent extraction passes. No chapter unread.

**COPYRIGHT NOTE.** This repo is PUBLIC. Per the standing rule in `aegis/.gitignore` and
`canon_build.py` — copyrighted source text never enters version control — the verbatim quotations
grounding this canon are withheld from this file. The authoritative quoted copy lives in the
private claude.ai project doc `claude/canon_weis_2026-08-17_grounded.md`. What follows is derived
analysis only.

**Status: GROUNDED, PENDING PM SIGN-OFF (not sealed — folio note at end). SEATED in S4 as the
9th nominator, 2026-08-17. Menu wired in voice_menus.json (34 fields), verified against the live
export with zero dead columns.**

---

## CORRECTION (rev 2, supersedes rev 1's "BLOCKING FINDING")

Rev 1 of this file asserted a blocking canon collision with `detect-lens`, based on the project
doc `canon_detect_lens_24_principles_2026-08-10.md` (a four-book composite proposal listing Weis
as C19-C24). **That finding was wrong.** The proposal doc was never deployed — it says on its own
face "PENDING YOUR SIGN-OFF. Nothing here is locked." The deployed lock,
`aegis/canon/detect-lens/canon.lock.yaml` (pm_signed: Ash, rebuilt code-first 2026-08-11), sources
`src/engines/*.py` + the AQE field dictionary and reads no books. There is no overlap. The PM's
ruling — weis and detect-lens are complementary — stands: detect-lens reports what the engine
computed; weis interprets what the tape did.

Rule going forward (now in S6B): seat-independence is checked against `canon.lock.yaml` files
only, never against project prose.

---

## What this seat is

**The failed-breakout seat.** Weis does not buy strength; he buys the failure of weakness — the
break that does not follow through. Structural counterweight to oneil/minervini/livermore, who
buy confirmed strength. Nearest neighbour is `wyckoff` (shared ancestor); the menu split keeps
them on different fields — wyckoff keeps the lens.coil/structure/resistance campaign decomposition,
weis takes the false-break + squeeze/VCP contraction family.

## Principles W1-W23 (derived, paraphrased)

**Effort vs result — the master diagnostic**
- W1 Volume is effort; range and net progress are result. The mismatch is the signal.
- W2 Large effort + small reward = the trend's own side is being absorbed.
- W3 Formulaic volume tables rejected as too simplistic.
- W4 Low volume with continued progress is NOT automatically bearish.
- W5 True range substitutes for volume as an effort proxy — Weis's own stated fallback.

**The false break**
- W6 SPRING = penetration of defined support that fails to follow through and reverses up.
- W7 Confirmation is a combination: narrow range or low volume on the penetration OR heavy volume
  with disproportionately small progress; no follow-through next 1-2 bars; close back above with ease.
- W8 Penetration depth is BOUNDED — a break too deep for the range structure is not a spring.
- W9 SECONDARY TEST: pullback on lower volume/narrower range holding above the spring low confirms;
  a deep heavy-volume break below voids.
- W10 TREND GATES THE SPRING: high-probability in uptrends; in downtrends the lowest-conviction
  case in the book, reading as SHORT evidence, not long.
- W11 Degree scales with the timeframe of the violated level; terminal shakeouts are the top class.
- W12 GAPPING SPRING — gap up after a demoralising breakdown, volume soaring. Weis's favourite.
- W13 UPTHRUST = mirror; close erases the breakout bar; size-bounded ~10-15% new high; a
  narrow-range new high is inherently suspect.
- W14 Upthrusts gated inversely: rarely pan out in uptrends, flourish in downtrends. On a long
  candidate in a healthy uptrend an upthrust is a caution flag, not a reversal call.
- W15 An upthrust ends the leg, not necessarily the trend.

**Absorption**
- W16 ABSORPTION = long liquidation, profit taking and new shorts being overcome. Directional,
  not tightness-based. Test: threatening bars fail to follow through; price presses without giving ground.
- W17 Bullish signature: rising supports; volume up near the top of the area; no downward
  follow-through after threatening bars; pressing at resistance; sometimes resolved by a spring;
  minor upthrusts fail.
- W18 BAG-HOLDING — persistent heavy selling against a low that fails to produce weakness. Bullish.
- W19 FAILED ABSORPTION INVERTS — repeated failed springs at a low = sellers absorbing the buying. Bearish.

**Thrust decay and contraction**
- W20 SHORTENING OF THRUST = diminished progress high-to-high / low-to-low. Minimum three impulses;
  past four, suppress the counter-trend signal; with two, consider spring/upthrust instead.
- W21 CONTRACTION PRECEDES EXPANSION — Crabel narrow-range family (NR4/NR7/inside day/hinge)
  imported wholesale. Direction is NOT implied by contraction; read the preceding behaviour.
- W22 CHANGE OF BEHAVIOUR — the first bar breaking the trend's rhythm is an early warning to flag.

**Trend supremacy**
- W23 The trend overrides all other particulars. Every setup above is conditioned on trend first.

## Data standing (post field-audit 2026-08-17)

**SERVED** (all verified non-null on the live export after the 2026-08-17 field audit):

| Principle | Fields |
|---|---|
| W1, W2, W5 | day_vol, flow, atr_14d, energy |
| W6-W8 (single-bar read) | pin_bar_state, structure_shift, sma_distance_pct, bracket.stop, bracket.valid |
| W13 | pin_bar_state, choch_state, structure_shift |
| W16-W19 | flow, structure, energy |
| W20 (proxy) | mp_accel_state, sc_momentum, div_state, div_bear_count |
| W21 | squeeze_breakout_state, was_squeezed, squeeze_breakout_volume_confirmed, elder_context.vcp.vcp_tightness_pct, elder_context.vcp.base_range_pct, inside_bar, atr_caution |
| W22 | choch_state, structure_shift, elder_pattern |
| W23 | ma_20/50/200, sma_distance_pct, mp_state, sector_trend_state |

**NOT SERVED, ranked by damage**
1. Multi-bar follow-through — W7/W9 cannot execute as written; the export is a one-day snapshot.
   Proxies: pin_bar_state (within-bar rejection), elder_5d. Spring calls are single-bar rejection
   reads, declared as such.
2. Close-location value (close-low)/(high-low) — Weis's most-used primitive; no field. Top engine ask.
3. Penetration depth vs a violated level — W8's bound unenforceable; bracket.stop is a proposed stop.
4. Successive thrust magnitudes — W20 proxy only, declared.
5. Volume at prior pivots — only rolling-average comparison available.
6. Secondary-test detection — W9 unserved.

**DATA-AVAILABILITY DECLARATIONS (enforcement level = PM decision, recommendation below)**
The following claims cannot be computed from daily OHLCV — the data does not exist in a daily bar:
- Wave volume (Weis Wave sums volume WITHIN a price wave from tick/minute data; a daily bar
  collapses a session's competing buy/sell effort into one number).
- Intraday tape reading / Level 2 / order flow (premarket: does not exist yet by definition).
- Renko / tick point-and-figure counts (Weis himself flags daily-close P&F as inferior).
- Net up/down volume splits (requires buyer/seller-initiated attribution).
RECOMMENDED handling, pending PM ruling: declare-and-continue — the seat states the limitation and
proceeds on served fields, mirroring the steenbarger pm_only pattern. Alternatives: hard refuse,
or no restriction. Unruled until the PM says.

## Menu (34 fields, wired 2026-08-17, zero dead columns on live export)
ticker, pin_bar_state, choch_state, inside_bar, structure, structure_shift, energy,
squeeze_breakout_state, was_squeezed, squeeze_breakout_volume_confirmed,
elder_context.vcp.base_range_pct, elder_context.vcp.vcp_tightness_pct, flow, day_vol, atr_14d,
atr_caution, sma_distance_pct, ma_20, ma_50, ma_200, mp_state, mp_accel_state, sc_momentum,
div_state, div_bear_count, elder_pattern, elder_5d, sector_trend_state, entry, bracket.stop,
bracket.stop_type, bracket.valid, bracket.atr_fallback_stop, bracket.risk_pct

No rs_leadership/rs_spy_20d (oneil/minervini's lens; Weis never ranks by RS). No knn (thorp).
No thematics (druckenmiller). No lens.* decomposition (wyckoff). No qs.* (PM-only, R3).

## Conviction grading 1-5
5 — terminal shakeout / higher-timeframe undercut (NOT REACHABLE on current fields; reserved).
4 — gapping spring in an established uptrend (W12), or full W17 absorption signature, trend-confirmed.
3 — ordinary minor spring in a clean uptrend correction ("small bet"); contraction with bullish preceding read.
2 — setup lacking supporting context, or resting on a declared proxy.
1 / do not nominate long — any spring-shaped read inside an established downtrend (W10).

## Page basis — declared defect
Extraction passes returned conflicting page indices (printed vs PDF folios diverge ~22 pages).
Citations in the project-doc copy are PDF-approximate ("~p."), not folio-verified, not
citation-grade. Open item: re-extract in 5-page windows against visible folios before
`canon_build.py seal`. Grounded but NOT SEALABLE until then.

## Open PM decisions
1. Enforcement level on the data-availability declarations (recommend declare-and-continue).
2. Close-location-value field in the export (serves weis, wyckoff, raschke, elder-lens).
3. Ceponas seating model when his book lands (market-hours only / narrowed premarket / hold).
4. Folio re-extraction before seal.
