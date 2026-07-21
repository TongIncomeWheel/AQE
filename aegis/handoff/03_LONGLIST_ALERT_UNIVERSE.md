# AEGIS — LONGLISTING & THE AQE ALERT UNIVERSE (THE CASTING MAT)
**The stock-selection recipe + the 2-day deliberation that produced it · 20–21 Jul 2026**

This document captures the tension and enrichment worked through over two days on ONE question: **how
should stocks be longlisted for the day and fed into the AQE alerts view?** It ends in a concrete,
tunable, mechanical recipe (the "casting mat"), wired as `tools/alert_universe.py` with thresholds in
`parameters.yaml → alert_universe` (D-77).

---

## 1. THE TENSION (what we were arguing about, and how it resolved)

Five corrections landed over the two days. Each is now doctrine.

**T1 — Momentum-first; do not distort the voices.** The voices were chosen as momentum traders. The
system's only job is to feed them clean data and not layer a perfectionist filter on top. Extension
above a moving average is *strength* in a momentum book, not a flaw; risk is a bracket question, not a
gate (D-52, D-63).

**T2 — Sector concentration is CONTEXT, never a gate.** The committee had been holding strong momentum
leaders (FBP, CSX, DINO, TRV, FA) off the actionable list purely because they sat in an over-weight
sector (XLK 113% / XLF 79% of dynCap). The PM overruled: surface them on merit, show concentration as
a sizing caveat, let the PM decide (D-4 reaffirmed). *Effect: three of the five strongest-consensus
names had been wrongly buried.*

**T3 — The event filter is the news catch the voices structurally cannot be.** PYPL screened as the
#1 momentum name (sc 82.5) — but that was a **+17% takeover pop**, not momentum. No voice reads news
(by design), so four voices "backed" it on inflated momentum fields. The event filter correctly struck
it (announced M&A). *Lesson: high momentum can be a fake; the event overlay is mandatory, and a
"strong name the committee threw away" may be a correct exclusion, not an error.*

**T4 — A single-factor alert screen is wrong in both directions.** The old AQE alert feed was
`sc_momentum > 70` → 57 names, noisy. Tightening to `sc_momentum > 80` → 2 names, far too narrow —
because "many good sc_mom that aren't top still run when they have a good structure or a good elder
around it" (PM). And the committee hand-picking ~37 names was worse: it limited the feed to "our
singular view" and would miss genuine intraday runners (BILL and ETSY ran; a narrow list misses them).

**T5 — Detection must be a COUNT of many momentum-incoming signals, not any single lens.** The decisive
finding: **BILL scored 0/6 on the detect lens** yet ran — because it carried `sc_m_gates` (all 5
momentum sub-gates), a **BULLISH change-of-character**, and a **significant KNN**. A detect-lens filter
would have thrown BILL away. So detection must count *many* lanes, with the detect lens as ONE
OR-booster, never the gate. This is the enrichment over the earlier D-57 `flag_condition` doctrine.

---

## 2. THE RECIPE — THE CASTING MAT (D-77)

**Membership:** a name is in the alert universe if
```
sc_momentum >= SC_FLOOR (default 70)   AND   detection_lanes >= MIN_LANES (default 2)
```
**Then tiered by lane depth** (how confirmed the momentum is — "arriving vs. stale"):
- **Tier 1 (>= 5 lanes):** high-confirmation → priority alerts
- **Tier 2 (3–4 lanes):** confirmed → second priority
- **Tier 3 (2 lanes):** headline score, thin confirmation → watch-only

**The 8 detection lanes** (each a distinct momentum-incoming signal; count how many fire):

| Lane | Fires when | Reads |
|---|---|---|
| `5gates` | all 5 momentum sub-gates pass | `sc_m_gates == True` |
| `CHoCH+` | bullish change-of-character (Wyckoff turn) | `choch_state == BULLISH` |
| `KNN` | Thorp's quant edge significant | `knn_significant == True` |
| `detect` | 6-lens detect count high | `lens_positive >= 4` |
| `LEADER` | relative-strength leader | `rs_leadership == LEADER` |
| `struct` | structural quality | `structure >= 72` |
| `flow` | participation / accumulation | `flow >= 68` |
| `accel` | momentum not rolling over | `mp_accel_state != DECELERATING` |

**Event overlay:** event-driven names (announced M&A / activist / single-catalyst >15% in <10 days)
are **struck** from the universe regardless of lanes (D-11). The screen catches the momentum; the event
filter removes the fake.

**Tunable knobs (parameters.yaml):** `sc_floor` (70 wide ↔ 72 tighter), `min_lanes` (2 wide net ↔ 3
drops the thin tail), `t1_lanes` / `t2_lanes` (tier cutoffs), and the per-lane thresholds
(`lane_structure`, `lane_flow`, `lane_detect`).

---

## 3. VALIDATION (21 Jul 2026, against the operator's own examples)

Run: `python3 tools/alert_universe.py build --export output/aqe_daily_export.json --event-blocked PYPL`

| Screen | Names | BILL? | ETSY? | DINO |
|---|---|---|---|---|
| old `sc_mom >= 70` | 57 (flat, noisy) | ✅ | ✅ | in |
| tighten `sc_mom >= 80` | 2 (too narrow) | ❌ | ❌ | in |
| committee hand-pick | 37 (too rigid) | ❌ | ❌ (cut as "noise") | gated |
| **casting mat** | **56** (40 T1 / 10 T2 / 6 T3) | ✅ Tier 1 (6 lanes) | ✅ Tier 1 (5 lanes) | **Tier 3 (2 lanes)** |

Two results prove the design:
- **BILL and ETSY both land Tier 1** — via `5gates + CHoCH+ + KNN` (the signals a detect-lens screen
  missed). The exact runners the operator flagged are caught.
- **DINO is correctly demoted to Tier 3.** Its 79.7 headline momentum (the "#1 name" earlier) is a
  **25%-extended late move** with only 2 lanes (`LEADER + flow`; no gates, no CHoCH, no KNN). The mat
  separates fresh momentum from a stale high score — the whole point.

Tier 1 also surfaces ~40 names the committee hand-pick never touched (LNC, DJT, RSI, NWBI, ZION, VLO,
MPC, WDAY, IOT, BBY…) — the "good intraday moves we'd miss by limiting to our singular view," now
caught mechanically.

---

## 4. HOW IT FEEDS THE DAY (longlist → alerts → pod)

```
AQE nightly export (all analytics per name)
        │
        ▼
CASTING MAT (alert_universe.py, deterministic)   ← the LONGLIST for intraday alerts
   sc_floor + >=2 lanes, tiered, event-struck     = a formula the PM controls, wide but not noisy
        │  writes data/alerts/DATE/alert_universe.json  (each name carries lane_count + lanes_fired)
        ▼
AQE ALERT ENGINE writes inbox every 15 min, scoped to the mat (Tier 1 loudest)
        │
        ▼
MARKET-HOURS POD (D-63) — when an alert fires, the pod reads the SAME lanes + subcomponents the
   voices read, and judges runner-or-not with normal conviction. Pages the PM only on an actionable
   CONFIRM. Held-book stop/approach alerts page immediately, always.
```

**The clean separation the PM insisted on:** the *universe* is mechanical (wide, tunable, no
hand-picking); the *committee/pod* applies judgment only to what fires. The committee does NOT
pre-select the universe — that was the error corrected on 21 Jul.

**Why the same numbers, twice:** the lanes that scope the universe (`sc_m_gates`, `choch_state`,
`knn_significant`, `structure`, `flow`, `rs_leadership`, detect, `mp_accel`) are exactly the fields the
voices read to nominate. So when an alert brings a name to the pod, the decision data is already
present and consistent with SOD — one evaluation logic, used at open-of-day and intraday (anti-spaghetti).

---

## 5. RELATIONSHIP TO EXISTING DOCTRINE (no spaghetti)

This is not a new parallel concept. It is the **wired implementation** of the D-57 `flag_condition`
doctrine (which already declared sc_momentum>70 obsolete and specified score-factors: structure,
participation, detect_lens, elder, extension_penalty, sector_alignment). D-77 adds the missing,
empirically-required enrichment — the `sc_m_gates`, bullish-CHoCH, and significant-KNN lanes that BILL
proved matter — and ships it as a deterministic tool with tunable parameters and a tiering that carries
confirmation depth into the pod. `flag_condition` remains the doctrine; `alert_universe` is its engine.

---

## 6. OPEN CALIBRATION ITEMS (for Design & Review / walk-forward)

- The thresholds are a **one-day calibration** (21 Jul). Per the Pardo guard (D-57 `profile:
  robust_first`), the regime-adaptive reweighting must pass walk-forward validation before going live —
  do not in-sample-fit. Ship the robust default; measure hit-rate of Tier 1 vs Tier 2/3 alerts over
  time via the nomination ledger.
- Decide whether Tier 3 (thin, often extended) should alert at all, or only be promoted when its
  confirmation lanes light up intraday.
- Confirm the `mp_accel != DECELERATING` lane is not too lenient (it currently admits FLAT).
