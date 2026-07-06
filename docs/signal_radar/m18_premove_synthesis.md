# M18 — Job-1 Pre-Move Detection: Synthesis

**Frozen spec `run_20260706v_m18`.** Reinstates the M12/M13 quiet-universe base-structure signal
in **pure %** — upward volatility is the target, never stripped. The only control is **timing**:
does the signal fire before the swing, or only alongside it. QUAL-independent pond: the **full
universe while names are still quiet** (trailing-20d in [−8%, +8%] AND below the top decile of
its own 20-day range), n=416,476 name-days (53% of the universe). Outcome: pure % touch from
open(t0+1). OOS 65/35 by date. v1.8.0.

---

## 1. Does a pre-move signal exist in pure %? YES.

Of the 52 features tested (38 deduped score representatives + 14 trajectory features), **45
separate launchers from non-launchers at FDR significance.** The top separators, raw and
out-of-sample:

| Feature | d (all) | d (OOS test) | Reading |
|---|---|---|---|
| base_days | −0.74 | −0.72 | Launchers sit in a much YOUNGER base |
| dist_20dhigh | −0.71 | −0.75 | Launchers are further BELOW their 20-day high (room above) |
| bq_base_dur | −0.55 | −0.56 | Same base-age signal, second measure |
| bq_base_days | −0.47 | −0.45 | Same, third measure |
| k39_value | −0.39 | −0.27 | Lower K39 (less "settled") among launchers |
| bq_ema_conv | +0.31 | +0.30 | EMA convergence (coil) present |
| rd_score | +0.24 | +0.21 | Readiness composite elevated |
| squeeze_score | (rule leg) | — | Compression present — the trigger ingredient |

The effect sizes **barely move** from in-sample to out-of-sample — this is not a fitted mirage.

## 2. Does it fire BEFORE the swing? YES — proven two ways.

**(a) Quiet-at-signal proof.** Launchers were genuinely flat when tagged: median trailing-20-day
return **−0.52%** (essentially zero), median position in their own 20-day range **0.46** (mid-range,
not extended), median distance to the 20-day high **−8.5%** (real room above). **0.0% of launchers
were already up more than 8% at signal** — the pond definition held; there is no continuation
contamination. This is not the runner-continuation signal wearing a disguise.

**(b) Lead-time distribution — the money number.** For names that went on to launch:

| Target | Median lead time | 25th–75th pct | Fires within 3 days | Fires 5+ days out | Fires 10+ days out |
|---|---|---|---|---|---|
| +10% | 10 trading days | 6–15 days | 12.0% | 81.9% | 52.1% |
| +20% | **12 trading days** | 8–16 days | 6.5% | 89.7% | 64.5% |

**The radar gives real warning — a median of ~2.5 weeks before a +20% move, and only 1 in 15
launches happens within 3 days of the tag.** This is a genuine pre-move detector, not a
same-day confirmation relabelled.

## 3. The pre-move rule (conjunction, shallow tree, OOS-validated)

> **`base_days ≤ 7.5` AND `squeeze_score > 4.5` AND `dist_20dhigh ≤ −16.2%`**
> (a very young base, compression on, and still well below the recent high)

| | Train | **Test (OOS)** |
|---|---|---|
| Base rate (quiet pond) | 7.2% | 10.0% |
| Rule-positive detection | 40.2% | **49.4%** |
| Lift | 5.6× | **4.96×** |
| Support | n=3,006 | n=2,249 |

**Robustness check (10-trading-day per-ticker cooldown, so repeat tags on the same runaway name
don't inflate the count):** n=2,556 non-overlapping episodes, detection **41.7%** — still ~4× the
base rate. The rule survives de-duplication.

Regime cut: holds in every regime (feature d's stay in the same direction and similar magnitude
GREEN/YELLOW/ORANGE) — not a GREEN-only artifact.

## 4. Base rates — the quiet-pond radar's raw yield

| Threshold | within 10 days | within 20 days |
|---|---|---|
| +10% | 15.6% | 29.0% |
| +20% | 3.6% | 8.7% |

Read plainly: of ALL quiet (not-yet-moving) names on any given day, about **1 in 11 will launch
+20% within a month** — and the rule above finds the ~0.5% of the quiet pond where that
probability rises to roughly **1 in 2.**

## 5. CONFIRMED vs CANDIDATE

**CONFIRMED** (survives the only legitimate control — timing, out-of-sample, robust to cooldown,
regime-consistent): a genuine pre-move detector exists. It is **not** a re-discovery of the
continuation signal — the quiet-at-signal proof and the positive lead-time distribution establish
that directly. This is the first confirmed answer to Job 1 in the entire program.

**CANDIDATE for deployment** (per standing discipline): single-regime 2020–2026, survivorship-
tainted universe, in-sample window — detection rates are upper bounds. **Forward paper-track
before this informs any sizing decision**, exactly as for the continuation signal. The rule,
conviction cuts (top-4 fingerprint legs), and pre-registered track bands (pass ≥15.0% forward
detection, fail <10.0%, both scaled off this study's OOS quiet-pond base) are frozen into
`signal_engine_params.json` as `premove_rule` / `premove_conviction_cuts` / `premove_track_bands`
for the paper-track harness to apply mechanically, without re-fitting.

---

*Deliverables: this synthesis + `m18_base_rates.csv`, `m18_launcher_fingerprint.csv`,
`m18_leadtime.csv`, `m18_timing.json`, `m18_regime_cut.csv`, `m18_premove_rules.csv`.
Reproducible via `scripts/m18_premove_study.py`. Registry: `run_20260706v_m18`. The confirmed rule
is already live-tagging (3 names as of 2026-07-02: BE, SNDK, UNIT) via the research-side paper
tracker — promotion into the live AQE pipeline is a separate, deliberate step (see
`promotion_package/INTEGRATION_BRIEF.md`).*
