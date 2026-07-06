# Promote the Signal Radar into AQE — Integration Build Order

**Status:** FROZEN SPEC for the promotion session. Read this whole file before touching anything.
**What this is:** three tested, working research deliverables (continuation scan, pre-mover scan,
BQ calibration evidence) are ready to move from a research checkout into the real, live AQE
codebase. This brief tells a fresh Claude Code session — opened directly inside the real AQE
project — exactly how to do that safely, in one pass, without breaking anything already running.

**Non-negotiable framing (carried from the research session, do not re-litigate):**
- The signal is a **%-based radar** for momentum-swing trading. Two jobs: (1) what's about to run
  [pre-move], (2) what will keep running [continuation]. It is **NOT** a risk/bracket/sizing
  engine — bracketing and sizing stay 100% the PM's live discretion.
- Every % this system reports is a **detection rate** (how often tagged names touched a level,
  price path only) — never a win rate, never risk-adjusted alpha. Label it that way everywhere.
- **Additive only.** Nothing in the existing scoring engines, gates, DSL, or export fields gets
  changed, renamed, or removed by this work. New fields are appended; nothing existing is touched.
- **The BQ finding is evidence only, NOT part of this promotion.** It shows Base Quality (35% of
  SC_POSITION) currently rewards the slowest-moving names. That's a live-indicator change and
  needs its own PM/committee ruling + backtest sign-off first (Charter v2.3 duplicate-indicator
  rule). Do not fold it into this build. Just make sure `bq_calibration_evidence.md` reaches the
  PM/committee for that separate decision.

---

## 0. Before touching anything — verify the target repo matches what this was built against

This package was built and proven against a specific version of the AQE codebase. The real repo
may have moved since. **Do not assume file paths or column names — check first:**

1. Confirm these files exist and look at their current shape:
   `src/pipeline/daily_orchestrator.py`, `src/data/drive_sync.py`, `src/data/db.py`,
   `data/scores_daily.parquet`, `data/panel_daily.parquet`.
2. Confirm `data/scores_daily.parquet` currently carries these columns (the engine needs them):
   `base_days, resist_score, mp_100, adx_val, k39_value, pipe_rank, bq_vol_dry, bq_100,
   bq_range_tight, squeeze_score, ext_score, rd_compression, energy_100, bq_base_dur,
   bq_base_days, bq_ema_conv, sc_momentum, elder_score`. If any are missing, STOP and report —
   do not silently substitute or drop a rule leg.
3. Confirm `data/panel_daily.parquet` has `date, ticker, open, high, low, close, volume` (needed
   to compute the 3–5 day trajectory features).
4. Read `src/data/drive_sync.py`'s `_FIELD_SCHEMA`, `_FIELD_GLOSSARY`, and `_REQUIRED_FIELDS`
   blocks — the new export fields must follow this exact pattern (see step 3 below), not be
   bolted on loosely.

If anything above doesn't match, adapt the steps below to the real shape rather than forcing it —
but do not change the underlying tag logic or the frozen params without flagging it explicitly.

---

## 1. What's in this package

| File | Goes where | Purpose |
|---|---|---|
| `engine/aegis_signal_engine.py` | `src/engines/signal_radar.py` (suggested name) | Core tag logic: `runner_setup`, `runner_conviction`, `mover_subtype`, `premove_setup`, `premove_conviction`. Already imports/re-derives nothing from the research checkout — self-contained. |
| `engine/signal_papertrack.py` | `src/engines/signal_papertrack.py` (or alongside) | Forward paper-track: logs tagged names daily, reconciles matured ones against pre-registered pass/fail bands. |
| `engine/signal_engine_params.json` | `data/signal_engine_params.json` | **FROZEN.** Tercile cuts, subtype z-params, and the M18-confirmed premove rule + conviction cuts + track bands. Same pattern as `data/active_recipe.json` — loaded, never re-fit in production. |
| `run_signal_scan.bat` | repo root (or wherever the other `.bat` launchers live) | Reference double-click entry point from the research session — the real integration should fold its logic into the existing daily job instead (step 4), but keep this as a manual on-demand fallback. |
| `m18_premove_synthesis.md`, `m16_winner_fingerprint_synthesis.md`, `m17_real_R_synthesis.md`, `BUILD_REPORT_SIGNALS.md` | reference only | The evidence trail. Not runtime files — keep for the committee/DS record. |
| `bq_calibration_evidence.md`, `bq_decile_curves.csv`, `bq_weight_sweep.csv` | reference only, route to PM/committee | The BQ finding. **Do not deploy.** Separate decision, separate session. |

---

## 2. Step 1 — Drop in the engine, unmodified logic

Copy `engine/aegis_signal_engine.py` and `engine/signal_papertrack.py` into `src/engines/` (or
wherever the target repo's convention puts engines — match the existing pattern, e.g. how
`src/engines/elder.py` or `src/engines/srm.py` are organized).

**Do not rewrite the tag math.** The functions `compute_dynamic_features()`, `forward_touch_frame()`,
`compute_signals()`, `RUNNER_RULE`, `SUBTYPE_FAMILIES` are the exact, verified logic that reproduced
the studies (100% conformance on the dynamic features, 50.6% OOS detection vs the study's 52.4%).
If column names differ slightly in the real repo (e.g. `scores_daily` uses a different name for a
field), adapt the column reference — do not change the thresholds, formulas, or rule legs.

Copy `data/signal_engine_params.json` into the real repo's `data/` folder, verbatim. **This file
must not be regenerated or re-fit against the live data** — it is frozen from the M14–M18 studies.
If the executing session is ever tempted to "re-fit for freshness," stop — that would silently
change the confirmed thresholds without a new study backing them.

---

## 3. Step 2 — Wire one new step into the nightly pipeline

In `src/pipeline/daily_orchestrator.py`, add **one new step after scoring completes** (after the
step that produces the day's `scores_daily` / top-50 scored universe, before or alongside the
Drive export step). It should:

1. Load `data/signal_engine_params.json` (fail loudly if missing — do not run with defaults).
2. Call `compute_signals()` on the day's scored universe + the daily OHLCV panel.
3. Attach the resulting per-ticker fields (`runner_setup`, `runner_conviction`, `mover_subtype`,
   `premove_setup`, `premove_conviction`, `is_quiet`) to the frame that `drive_sync.py` reads to
   build the export.

This step must be **read-only with respect to everything upstream** — it consumes scores and
panel data that already exist; it does not change how scoring, gating, or recipe matching work.
If it throws an exception, the pipeline should log it and continue (these are informational tags,
not required for the pipeline's existing job) — do not let a signal-engine bug take down the
nightly scan.

---

## 4. Step 3 — Add the fields to the Drive export (with schema/glossary, matching the existing pattern)

In `src/data/drive_sync.py`:

1. Add the five new per-record fields (`runner_setup`, `runner_conviction`, `mover_subtype`,
   `premove_setup`, `premove_conviction`) to every ticker record on **all applicable tiers**
   (longlist, elder_list, held_positions) — same normalization pass that already stamps
   `gics_sector`, `rvol`, etc. onto every record.
2. Add matching entries to `_FIELD_SCHEMA` and `_FIELD_GLOSSARY` — follow the existing role/unit/
   side pattern exactly:
   - `runner_setup`, `premove_setup`: role `reference`, unit `decimal` (boolean), side `n/a`.
   - `runner_conviction`, `premove_conviction`: role `reference`, unit `decimal`, side `n/a`.
   - `mover_subtype`: role `reference`, unit `decimal` (categorical string), side `n/a`.
   - Glossary line for each: state plainly it is a **detection tag**, not a gate, not sizing, and
     that any accompanying % elsewhere (e.g. in the Scanner panel, step 6) is a **detection rate**
     (historical, price-path-only), not a win rate.
3. There is already a test that asserts every `_FIELD_SCHEMA` key is covered by `_FIELD_GLOSSARY`
   (mentioned in the schema discipline). **Run it after this change** — it must still pass.
4. Do **not** touch `_REQUIRED_FIELDS` to make these mandatory — they should degrade gracefully
   (null/false) if the signal engine step failed for a given name, not block the whole export.

---

## 5. Step 4 — Persistence for the paper-track (pick one, document the choice)

The paper-track needs to remember, day over day, which names were tagged and what price did
afterward. Two options — **pick based on what fits the target repo's existing patterns best**,
this was left open deliberately rather than forced from the research side:

**Option A — extend the existing SQLite store (`src/data/db.py`).** Add two tables:
`signal_tags (tag_date, ticker, tag, conviction, subtype)` and `signal_track_results` (same shape
as `signal_papertrack.py`'s `papertrack_results.csv` — ticker, tag_date, tag, matured flags,
forward % outcomes). Fits the existing 7-table pattern; nothing new for the PM to open.

**Option B — a Drive-synced JSON/CSV pair**, mirroring how `aqe_alert_state.json` already works
(a small state file the pipeline reads/writes, synced through the same Drive mechanism as
everything else). Simpler to eyeball directly if the PM ever wants to open the raw file.

Either way: port `signal_papertrack.py`'s `log_tags()` / `reconcile()` logic to read/write through
whichever store is chosen instead of the flat CSVs it uses today. **Keep the pre-registered
bands exactly as they are** — they live in `signal_engine_params.json` (`premove_track_bands`) and
in the constants at the top of `signal_papertrack.py` for `runner_setup` — do not adjust these
numbers during integration; they were fixed before the track started and changing them now would
break the pre-registration discipline the whole program has held to.

---

## 6. Step 5 — Surface it to the PM (Scanner UI)

Add a small panel to the existing Scanner page (`src/ui/1_Scanner.py`), in the same plain-table
style as the rest of the app (no fancy visuals, per the project's own rule):

- Today's `runner_setup` names (ticker, conviction, subtype) and today's `premove_setup` names
  (ticker, conviction), sorted by conviction.
- The paper-track scoreboard: for each tag type, matured episode count, forward detection rate,
  the concurrent pond base rate, and the pre-registered verdict (RUNNING / PASS / FAIL /
  INCONCLUSIVE) — reuse `signal_papertrack.py`'s `reconcile()` output directly, don't recompute it
  differently in the UI layer.
- Label the whole panel clearly as **detection tags, not entry signals** — the PM decides
  entry/bracket/size live, same as today.

---

## 7. Verification — do not call this done until these all pass

1. **Reproduction check.** Run the ported engine against a recent historical date this package's
   research session already scored (e.g. 2026-07-02) and confirm the tag output matches
   `promotion_package`'s reference output for that date exactly (same names flagged, same
   conviction scores). If it doesn't match, something drifted in the port — find it before
   shipping, don't average it away.
2. **Additive-only check.** Diff the day's export before/after this change for a handful of
   existing fields (e.g. `sc_momentum`, `dsl_stop`, `optimal_stop`) — they must be byte-for-byte
   identical. If anything existing changed, STOP — that's a spec violation.
3. **Schema/glossary lockstep test** (step 4.3) passes.
4. **Pipeline resilience check** — deliberately break the signal-engine step (e.g. point it at a
   missing params file) and confirm the nightly pipeline still completes and exports everything
   else normally, just without the new tags. The radar must never be able to take down the scan.
5. **BQ evidence routed, not deployed** — confirm `bq_calibration_evidence.md` has gone to the
   PM/committee as a separate item, and that no code in this promotion touches `bq_100`'s weight
   in `SC_POSITION`.

---

## 8. Git discipline (repeat of the project's own standing rules — do not skip)

- Stage only the specific files this build touched. **Never `git add -A` or `git add .`** — this
  repo has real-money JSON and could leak something unrelated.
- Smoke-test before committing (Streamlit AppTest for the UI panel; a scalar/engine import check
  for the pipeline step).
- Commit message: describe intent, end with the standard Co-Authored-By line.
- Push via the project's existing `push_both.py` / `push_both.bat` only when explicitly told to —
  it pushes to **both** GitHub and the HuggingFace Space (which auto-redeploys). Surface the
  GitHub commit URL + HF Space URL back to the PM for UAT afterward, same as any other change.
- If the local checkout's connection to `origin`/`hf` needs to be (re)established, confirm the
  remote URLs match `TongIncomeWheel/AQE` (GitHub) and `AQE-Aegis/aqe` (HF Space) before pushing
  anything — do not push to an unfamiliar remote.

---

## 9. What NOT to do

- Do NOT re-fit or "refresh" `signal_engine_params.json` against live data — it's frozen evidence.
- Do NOT deploy the BQ re-weight as part of this work — evidence pack only, separate PM/committee
  decision, separate build.
- Do NOT let `runner_setup` / `premove_setup` gate, filter, or size anything automatically — they
  are display/context tags the PM reads, exactly like `on_longlist` or `pe` today.
- Do NOT change the pre-registered paper-track pass/fail bands during integration.
- Do NOT touch DSL, stops, brackets, or trailing logic — none of this work concerns them.

---

*This package's research trail (the M14–M18 studies, the M16/M17 real-R robustness checks, the
BQ evidence) lives in `output/calibration/` in the research checkout for anyone who wants the full
derivation. This brief is the self-contained, mechanical "how to ship it" — everything needed to
execute is either in this package or already in the target AQE repo.*
