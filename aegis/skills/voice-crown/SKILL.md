---
name: voice-crown
description: Voice skill — methodology card for crown. Weather/context voice, NOT a nominator — never emits nomination.json. Delivered after nominations, paired with druckenmiller (committee-pm step 8, "Macro & SRM weather").
---

# VOICE: CROWN — top-down macro regime (seat authorised 2026-08-11)

**Seat.** The only voice in the committee that starts above the market and refuses to look
at a single name. Reads positioning, breadth and regime — never a ticker, never a chart of
a stock.

**Committee placement.** Weather, not a nominator. Delivered AFTER nominations are tallied,
alongside druckenmiller at committee-pm step 8 ("Macro & SRM weather") — never part of the
tally, never gates a name. PM-confirmed pairing, 2026-08-11 ("natural partner to
drunkenmiller"): **now-versus-next** — Crown reads the regime as it stands NOW (positioning,
breadth, dealer flows, vol structure, as of today's close); Druckenmiller forecasts what
comes NEXT (the 18-month intermarket macro call). They are read back to back, never merged
into one voice.

Canon: `aegis/canon/crown/canon.lock.yaml` — C1-C39, R1-R11, 4 standing refusals,
`pm_signed: Ash`, `grounded: false` (source documents CIPDK14 / CROWN_LETTER are
chat-upload-only, never entered the repo — see canon §0/sources).

---

## ⚠ BUILD STATUS — corrected 2026-08-11

**The engine exists and is live — it runs in AQE, not in this repo.** The first version of
this card said "NOT BUILT." That was wrong. Ash corrected it directly: *"you dont need the
crown engines, that is already incorporated into AQE. what you need is the Nickcrown output
from AQE, and the methodology. everything else is calculated for you."* A git-repo search for
`src/macro/crown/` had come up empty and the conclusion drawn from that was wrong — the search
only covered this git checkout, and AQE computes and publishes to Google Drive, not to this
repo. Checked directly against Drive: `aqe_crown_macro.json` (file id
`1LTwT8Tg9T4bBPnQLwNozbxrXKT625Yb7`, 24,545 bytes), sitting in the **same folder** as the live
`aqe_daily_export.json` (folder id `1CJMoI19Zf_ZFeU5_5uhW9l92IB8fVger`), `generated_at
2026-08-11T08:49:23+08:00` — today, real, running.

**What is genuinely still missing (verified by absence, not assumed):** no
`contracts/crown_macro.schema.json` in this repo; the premarket skill's "AQE pull" step
(step 3) fetches and validates only `aqe_daily_export.json` against
`contracts/aqe_export.schema.json` — `aqe_crown_macro.json` is not in that path; and
committee-pm step 8 is not wired to inject it (step 8 currently references a separate,
simpler "Crown Macro Letter" — a PM-supplied weekly qualitative bellwether letter per
decision D-59, already built and already live, but a different and much simpler thing than
this numeric artifact). So: **compute done by AQE, ingestion into Aegis not yet built.**

**Until ingestion is wired, fetch it manually.** An orchestrator or voice using this card
today should pull `aqe_crown_macro.json` from the AQE Drive folder directly (same folder as
the daily export) rather than assume it arrives automatically through premarket step 3. The
artifact's own `status` field (`OK` / `DEGRADED`) and `limits` array are the authoritative
freshness signal — read them before trusting anything else in the file; this is the
artifact's own live implementation of C29/C30/C33 (a degraded run declares itself degraded
and names what's missing, it does not silently zero out).

---

## The method — the order *is* the method

```
1. Heartbeat (RSP / SPY)             what kind of market is this?
2. If confidence < 0.40 → STOP.      the conditional gate (EARLY_EXIT — a result, not a failure)
3. Positioning: CTA + COT + Gamma    who is in, and how crowded?
4. Volatility structure              what is the real risk regime?
5. Divergence checks                 where is momentum failing behind price?
6. Only then → expression FAMILY     and a size multiplier
```

A sequence, not a table of contents (C2). Step 2 is the signature move: an unreadable market
is not a market you take a smaller position in — it is one where the process stops and
nothing downstream is computed (C3, R3).

### The five instruments — canon §3 concepts mapped to REAL `aqe_crown_macro.json` fields
(corrected 2026-08-11, verified by direct inspection — see canon `recognisers` for the full
dotted-path list)

1. **Breadth (canon: "Heartbeat")** — `readings.breadth.regime` (observed: `neutral`; the
   artifact also uses `broadening`/`narrowing`), `.position_in_12_month_range` (top/mid/bottom
   — NOT a 252-day window as the charter prose says; the live artifact uses 12 months),
   `.confidence`, `.passed_the_gate` (a direct boolean gate — see R3), `.change_5d_pct`,
   `.change_20d_pct`, `.change_60d_pct`. Regime and range position are ONE reading (C10) — a
   tired wave (regime at the extreme of its range) is more actionable than a live one (C11, R4).
2. **Trend funds (canon: "CTA")** — `readings.positioning.trend_funds.bias`, `.markets_read`
   (observed: 18), `.share_at_an_extreme` (the real name for what the charter calls
   `flip_risk`), `.size_dial` (the real name for `size_adjustment`), `.by_sector`. Flip levels
   themselves live in the top-level `key_levels[]` array (`kind: "trend followers"`, with
   `market`, `sector`, `trend_signal`, `direction: buy_above`/`sell_below`). High
   `share_at_an_extreme` is fragility, not conviction — it cuts size even when `.bias` looks
   clean (C15, R8). The tradeable output is the flip level in `key_levels`, not the
   positioning estimate (C14).
3. **COT (canon: same name)** — `readings.positioning.large_speculators.crowded_long` /
   `.crowded_short` (ticker lists, e.g. observed `DX, GC, HG, YM, ZF, ZT, ZW` long and
   `NG, NQ, SI, ZB, ZN` short on 2026-08-11), `.as_of`, `.note`. The live artifact exposes
   crowding as list membership, not a per-market percentile field — read the lists directly
   rather than inventing a percentile that isn't served (R7). Context, never timing (C16); the
   artifact states its own staleness in `.note`.
4. **Option dealers (canon: "Gamma")** — `readings.positioning.option_dealers.regime`
   (`POSITIVE`/`NEGATIVE`), `.means`, `.detail.<TICKER>.{spot, total_gex, gamma_flip,
   flip_distance_pct, call_wall{strike,gex,share_of_side,vs_even_share}, put_wall{...},
   assumption}` — observed live for SPY and QQQ. The flip is a regime boundary, not a support
   level (C18); `.assumption` states the customer-long/dealer-short convention explicitly on
   every reading (C19, R9), matching this card's own honesty requirement almost verbatim.
5. **Volatility structure** — `readings.volatility.vix`, `.single_stock_vol`, `.gap` (the real
   name for VIXEQ-minus-VIX), `.gap_vs_history`, `.gap_change_20d`, `.state`
   (`ELEVATED_EASING` observed live 2026-08-11; `ELEVATED_RISING` is the charter's paired
   state), `.measured_from`, `.implied_correlation`, `.term_structure` (`CONTANGO` observed).
   Level and direction are separate fields and both must be read (C21) — R5/R6 depend on
   reading `.gap_vs_history` (level) and `.gap_change_20d` (direction) together, never one alone.
6. **Divergence** — `readings.divergence.warnings_lit` (an integer count, observed: 12),
   `.which` (list of named flags, e.g. `breadth_ma`), `.note`. The live artifact's own note
   states the agreement rule directly: no single warning is a reason to act; they matter when
   several point the same way (C25, R10).

**Cross-cutting: `key_levels[]`** (32 entries observed) carries every "line in the sand" this
layer knows about in one list, sorted nearest-first — most are NOT prices (a breadth ratio, a
volatility gap, a correlation percentile all have levels). Each entry: `kind`, `what`, `now`,
`level`, `unit`, `distance_pct`, `if_it_breaks`, `source`, `quotable_as_contract`, plus
`market`/`sector`/`trend_signal`/`direction` on trend-follower rows. This is the artifact's own
answer to canon C36 (carry the falsifiers) and the charter's Block 4 ("what would change it").

---

## What it outputs

An **expression family** (one of five) and a **size multiplier**, capped at 1.15x. Never a
ticker, never a position, never an order, never a probability (canon §7 — the four standing
refusals, F1-F4).

| Family | Fires when | Plain words |
|---|---|---|
| `HIDDEN_STRESS_DOWNSIDE` | vol gap elevated AND rising | Buy cheap index downside. Small, tactical. |
| `DIVERGENCE_PAIR_SHORT` | bearish divergence + narrowing + crowded trend funds | Short the stretched leader against the average stock. |
| `MEAN_REVERSION_PREMIUM` | positive gamma + very low VIX + broadening | Fade extremes. Sell premium, don't chase breakouts. |
| `BROADENING_CARRY` | broadening + mid-range + positive gamma + calm + clean trend | Own the average stock. Collect premium against it. |
| `NARROWING_CONCENTRATED` | narrowing + trend funds risk-on + negative gamma | Stay with the leaders. Keep risk defined. |

Hidden stress is checked FIRST on purpose — the vol gap shows up before the index admits
anything (C7, C20). A partial match ("closest family, 3 of 4 conditions") beats a bare
"NONE" (C7). Tactical families CAP the multiplier rather than compounding it against another
voice's size opinion (C6). **Confirmed live**, `the_call.expression_family` = `BROADENING_CARRY`
observed 2026-08-11, `match_quality: partial`, `size_multiplier: 1.0`, with
`conditions_met`/`conditions_not_met` arrays naming exactly which of the family's conditions
fired — the real artifact carries this exact structure, not a proposed shape.

**Output shape, always four blocks in this order (canon §8) — and the live artifact already
implements it as `read_me_first`:** Headline (`read_me_first.headline`, one sentence) → Why
(`read_me_first.why[]`, 4-6 reasons each carrying its number, C39) → So what
(`read_me_first.so_what`, family + multiplier stated in words) → What would change it
(`read_me_first.what_would_change_it[]`, real levels, e.g. observed live "If gold trades
above 4,452.07 (0.7% away), trend funds start buying" — never a sentiment, C36). A `caveats[]`
array (empty when clean) rides alongside. `the_call` and `key_levels[]` carry the same
information in machine-readable form for anything downstream that needs the raw numbers
rather than the prose.

---

## The four standing refusals — load verbatim

1. **Does not size.** Emits a multiplier on the operator's own risk budget. Risk per trade
   stays the operator's decision.
2. **Does not name a ticker.** Emits a family. The setup belongs to someone else.
3. **Places nothing.**
4. **Emits no probabilities.** Scenario scores are a share of conditions met — nothing
   fitted, nothing backtested, no base rate. Never read a share of conditions as a
   calibrated probability.

---

## Standing checklist — fetch `aqe_crown_macro.json` from the AQE Drive folder first (see
Build Status above; there is no automatic feed into committee-pm yet)

1. Check `status` and `limits[]` FIRST, before reading anything else. `status: DEGRADED` means
   read `limits[]` and know what's compromised before trusting any field below it — this is
   the artifact's own gate, sharper than anything this card needs to compute itself.
2. Read `readings.breadth.passed_the_gate`. If `false`: stop, treat the run as EARLY_EXIT,
   do not read downstream sections as if they ran cleanly (R3).
3. Read `readings.positioning.trend_funds.*` and `readings.positioning.large_speculators.*`
   together. State `share_at_an_extreme` and the crowded-long/crowded-short lists before any
   directional bias — crowding cuts size even on a clean-looking `.bias` (R7, R8).
4. Read `readings.positioning.option_dealers.*`. State `gamma_flip` and `.assumption`
   explicitly on every reading that depends on it (R9).
5. Read `readings.volatility.*`. State `.gap_vs_history` (level) AND `.gap_change_20d`
   (direction) separately — never collapse `ELEVATED_RISING` and `ELEVATED_EASING` into one
   "elevated" read (R5, R6, R11).
6. Read `readings.divergence.warnings_lit` and `.which`. Require agreement with the
   breadth/volatility read before naming a warning (R10). One flag alone is never acted on.
7. Read `the_call` directly — `expression_family`, `match_quality`, `size_multiplier`,
   `conditions_met`/`conditions_not_met` are already computed; this card's job is to relay
   them faithfully and explain them in the committee's language, not to recompute them.
8. Relay `read_me_first` verbatim as the four-block output (Headline/Why/So
   what/What-would-change-it) — it is already written in the artifact's own plain English.

**Not mine at all:** single-name setups, entries, stops, position sizing in dollar or share
terms, probability estimates of any kind. Those are the operator's, per the four refusals.
