# Signal Build Report — the three deliverables (plain English)

**Built and tested 2026-07-06.** Everything lives in `scripts/` + `output/signals/` — the live
AQE pipeline, engines and export are untouched. Promoting these INTO AQE is a separate session
(the live scores file already carries every column needed, so promotion is plug-in work).
Every % below is a **detection rate** — how often tagged names went on to touch the level,
price path only. Not a win rate, not sizing advice. You decide entry/bracket/size live.

---

## 1. Continuation scan — "what will keep running" ✅ LIVE

**What it is:** a nightly tag (`runner_setup`) for names already moving that have another leg:
short young base + strong 5-day thrust + clear overhead. Plus a **conviction score 0–4** and a
**setup type** (explosive / trend / tight-base / squeeze).

**Proof:** the engine reproduces the studies exactly (features match to the last decimal;
held-out detection 50.6% vs the study's 52.4%). Historically ~half of tagged names touched
+20% within a month, vs ~16% of the untagged pond. The conviction ladder is clean:
conviction 1 → 4.5%, 2 → 12.6%, 3 → 27.2%, **4 → 43.4%**.

**Today's scan (2026-07-02 data): 35 names tagged** — APP, ASTS, RDDT, VSAT, MDB, NOW, SNOW…
(full list: `aegis_signal_scan_latest.json`).

## 2. Pre-mover scan — "what's about to run" ✅ CONFIRMED + LIVE

**What it is:** a tag (`premove_setup`) for names that are **flat and quiet right now** but
coiled to launch: a very young base (≤ ~1 week), squeeze on, still sitting well below the
recent high. The classic pulled-back-and-coiled spring.

**Proof (the M18 study):**
- Tagged names were **genuinely flat when tagged** (median move over the prior month: −0.5%).
- **49.4% of them launched +20% within a month — vs 10% of untagged quiet names. 5× better,**
  proven on 2,249 held-out cases the rule never saw, and it holds in every market regime.
- **Real warning:** the launch came a **median 12 days after the tag**. Only 6.5% popped within
  3 days. This sees the move coming — it is not the continuation scan in disguise.

**Today's scan: 3 names tagged — BE, SNDK, UNIT** (all max conviction).

## 3. BQ calibration — "make the position score point at what runs" ✅ EVIDENCE READY

**The problem, measured:** Base Quality (35% of SC_POSITION — its biggest weight) rewards calm,
tight, long bases — and those are the **slowest** names. Lowest-BQ names ran +20% **33.5%** of
the time; highest-BQ names **8.4%**. Net effect: the current SC_POSITION ranks movers
**backwards** — its top decile catches movers *less* often than picking at random from the pond.

**The fix options, tested (no fitting, held-out era checked):**

| SC_POSITION variant | Top-decile mover detection (held-out era) |
|---|---|
| Current (BQ 35%) | 11.7% |
| BQ cut to 15% | 15.4% |
| BQ removed | 22.7% |
| **BQ swapped for a short-base score** | **43.7%** |

**Nothing was changed live.** SC_POSITION is a deployed indicator — this is the evidence pack
for the committee to rule on (versioned variant, duplicate-indicator prompt, backtest before
deploy). Note the honest alternative on the table: leave SC_POSITION as a *position* score and
let the two radar tags above carry move-detection.

## 4. The forward tracker — the proof machine (and the gate to sizing) ✅ RUNNING

Every scan logs its tags; every logged name gets scored against what price actually did.
Pass/fail rules were **written down before it started** (60+ matured tags and 3+ months;
runner passes at ≥35% forward detection and ≥1.5× the pond; pre-mover bands set from M18).
**No tag informs sizing until its track says PASS.** The math was validated end-to-end on a
back-dated test (11 May-tagged runners → 63.6% detection vs 41.9% base) before the real log
started. **Real log live since 2026-07-02: 38 tags on the clock.**

---

## How to run it (no terminal)

**Double-click `run_signal_scan.bat`** any evening after the AQE pipeline has run.
It scans, logs, scores everything old enough, and writes:
- `output/signals/aegis_signal_scan_latest.json` — today's runner + pre-mover names
- `output/signals/papertrack_report.md` — the forward proof so far

## The honest caveats (carried on every number)

All history is 2020–2026 (mostly a rising market) with today's universe applied backward —
so every detection rate is a **best case** until the forward tracker confirms it live.
That's exactly what the tracker is for.

## What's next (your call)

1. Committee reviews this + the BQ evidence (`output/calibration/bq_calibration_evidence.md`).
2. The tracker accumulates forward proof daily (just keep double-clicking the bat).
3. When confidence is good → **promotion session**: wire `runner_setup` / `premove_setup` /
   conviction into the AQE export and Scanner, and (if ruled) ship the SC_POSITION variant.
