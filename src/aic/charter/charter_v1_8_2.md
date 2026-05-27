# AIC Charter v1.8.2 — Operating Document (Spec-Derived)

> **PROVENANCE NOTE.** This file collects the parts of AIC Charter v1.8.2 that are *explicit in* `AEGIS_POC_BUILD_SPEC_v2.md`. Where the spec references the charter but does not reproduce a clause verbatim, this file marks the gap. The PM must populate `<<<CHARTER_GAP — PM TO POPULATE>>>` blocks before the system is run live against real capital. Until populated, the orchestrator and voices operate on the rules derivable below.

**Effective:** 21 May 2026
**Cell composition:** 12 voting voices (8 Deliberation + 4 Risk & Structure)

---

## §3A — Cell Governance (Committee Independence)

The Deliberation Cell answers a single question: *Is this trade worth taking?*

1. **No validation drift.** Agreement must be earned through analysis, never deference.
2. **Challenge when warranted.** Constructive dissent is an obligation, not an option.
3. **Independent conclusions first.** Each voice completes its own assessment before consensus forms.
4. **Anchor first.** Each voice cites its own canonical literature before any deliberation.
5. **Prior outputs are reference only.** Visible to subsequent voices but never authoritative — no anchoring.

**Inversion Mandate (rule 3).** When all 8 deliberation voices reach the same conclusion (8/8 APPROVE or 8/8 REJECT), Steenbarger MUST argue the strongest possible counter-case BEFORE the Risk Cell runs. Non-negotiable. Unanimous consensus conceals blind spots; PM reviews the consensus AND the inversion argument before Risk Cell is invoked.

---

## §3B — Alfred Mandate (Orchestrator Only)

Alfred is the Scrum Master. Alfred's mandate is to:

1. **Orchestrate** — manage session flow, enforce protocol sequence, coordinate cells, track state.
2. **Enforce charter** — flag violations, gate breaches, missing data, stale inputs.
3. **Execute** — run SRM, compute PTRS, post PTJ, pull data, manage Drive.
4. **Flag gaps** — if data is missing or a protocol is incomplete, STOP and surface it.

Alfred does **NOT**:

- Provide analytical opinions on trade direction, thesis quality, or market outlook.
- Speak when a committee voice should be speaking.
- Vote on any trade.
- Summarise or paraphrase committee conclusions in Alfred's own voice.
- Fill silence with analysis when the correct action is to run a protocol.

**Universe cap.** Maximum 5–10 names in active consideration at any time (BRACKET + WATCH combined). Alfred enforces — if pipeline is at 10, no new name advances to deliberation until an existing name is bracketed or killed.

---

## §6 — PTRS (Pure Quality Gate)

```
PTRS = SC_MOMENTUM + CM
CM   = SH + RA + RL
```

| Component | Range | Meaning |
|---|---|---|
| **SC_MOMENTUM** | 0–100 | AQE canonical composite (Flow 30 / Energy 30 / Structure 20 / MP 20). |
| **SH (Sector Health)** | −8 to +3 | Above SMA20 by >2% → +3 · at/near SMA20 → 0 · below → −5 · >5% below → −8. |
| **RA (Regime Alignment)** | −10, 0, +5 | ALIGNED → +5 · NEUTRAL → 0 · MISALIGNED → −10. |
| **RL (Regime Level — DSL v1.4)** | −5 to +2 | GREEN (VIX <18) → +2 · YELLOW (18–25) → −3 · ORANGE (25–30) → −5 · RED (>30) → HARD STOP. |

**Threshold.** `PTRS ≥ 65` → **QUALIFIED** → advance to Deliberation Cell. `PTRS < 65` → **REJECTED**. Reason logged. PM notified. STOP.

**PTRS is a binary quality filter only. It does not determine position size.** Sizing is owned by the Risk & Structure Cell, post-deliberation.

---

## §6A — Combined Stop-Out Risk Rule (Elder hard-block authority)

```
Combined Stop-Out = Σ (Entry − Stop) × Shares  for all open positions + proposed new position
```

If combined stop-out >5% of dynamic capital → **BLOCK** (no override). This is Elder's primary hard-block authority in the Risk Cell. Mechanical; not a discretionary vote.

---

## §6B — Breakout Stop Rule (DSG-12)

```
breakout_stop = (min(DSL, flush_low) − 1%)   if flush_low exists in prior 5 sessions
              = DSL                          otherwise
```

The 1% buffer below the lower of (DSL, flush low) absorbs noise around the structural breakout level.

---

## §8 — Regime Tiers (DSL v1.4)

| Tier | VIX | Operations |
|---|---|---|
| 🟢 GREEN | <18 | Full operations. All protocols active. |
| 🟡 YELLOW | 18–25 | Reduced new entries. Existing positions managed normally. |
| 🟠 ORANGE | 25–30 | No new entries. Position management only. |
| 🔴 RED | >30 | HARD STOP. No entries. No add-ons. Escalate to PM immediately. |

---

## §9 — AQE Authority + Gate Sequence

§9A. **AQE is the canonical SC_MOMENTUM source.** The LLM layer (Alfred, voices) MUST NOT compute SC_MOMENTUM. If AQE is unavailable, deliberation is blocked.

§9B. **Gate sequence (Alfred enforces, in order).**

1. SC_MOMENTUM ≥55 (AQE canonical)
2. Elder gate ≥6.5 (AQE)
3. All engine floor gates (flow ≥60, energy ≥60, structure ≥55, mp ≥55)
4. Sector gate ≥HOLD (§4B.4 + DSG-11 correlation override)
5. R:R ≥2:1 vs committee-designated target (§6A)
6. PTRS ≥65 (quality gate — Alfred computes)
7. Universe cap ≤10 names (Alfred enforces)
8. RED regime = HARD STOP (no evaluation proceeds)

Any gate failure ⇒ candidate rejected ⇒ reason logged ⇒ PM notified.

---

## §4B.4 — Sector Gate (with DSG-11 correlation override)

| `sector_grade` | `sector_corr` | Behaviour |
|---|---|---|
| DEPLOY or HOLD | any | Pass (standard). |
| TURNING / WATCH / AVOID | `< 0.3` (idiosyncratic) | Gate converts to SH penalty only. Pass if PTRS ≥65. |
| TURNING / WATCH / AVOID | `0.3 – 0.7` (mixed) | Binary gate holds. PM override requires 4/8 committee majority + documented rationale. |
| TURNING / WATCH / AVOID | `> 0.7` (sector-dependent) | No override. Gate fails. |

---

## §7 — DSG-10 Trail System (DSL v1.4)

| Tier | Range | Stop placement |
|---|---|---|
| 0 | Entry → +0.5R | Fixed at structural SL. |
| 1 | +0.5R → +1R | Raise stop to breakeven. |
| 2 | +1R → +2R | Trail at −0.5R from highest close. |
| 3 | +2R → +3R | Trail at −0.75R from highest close. |
| 4 | +3R+ | Weekly mode — trail at prior week's low. |

---

## Deliberation Cell — Vote Mechanics

- **Vote:** APPROVE / REJECT / ABSTAIN with conviction 1–10.
- **Approval threshold:** ≥5/8 APPROVE.
- **Avg-conviction warning threshold:** <6.5 → advance to PM with flag (does not auto-reject).
- **Inversion trigger:** 0/8 or 8/8 unanimous → Steenbarger Inversion before Risk Cell. PM must read counter-argument before proceeding.

## Risk & Structure Cell — Sizing Mechanics

- **Vote:** FULL (1.0×) / HALF (0.5×) / QUARTER (0.25×) / BLOCK.
- **Sizing threshold:** majority 3/4 for a sizing recommendation.
- **Elder hard-block:** combined stop-out >5% capital ⇒ BLOCK regardless of other votes.
- **Run timing:** only after Deliberation Cell has produced ≥5/8 APPROVE.

---

## Protocol Inventory

- **A — Session Open** (09:00 SGT): stop audit, regime check, SRM run, AQE pull, pipeline × AQE cross-ref, combined stop-out, pre-market brief.
- **B — Candidate Qualification**: source → gates → PTRS → Deliberation → Risk Cell → execution brief.
- **C — Position Management**: DSG-10 trail checks at close; stop audit at open; MP-state monitoring; add-on protocol.
- **D — Session Close** (04:00 SGT): reconcile fills/P&L; DSG-10 tier checks; SRM close run; PTJ auto-run at 04:30 SGT.
- **E — Weekly Scorecard** (Friday close + Monday review).
- **F — Emergency**: RED regime, combined stop-out >5%, FMP data outage.

---

## Charter Gaps Awaiting PM Population

The following clauses are referenced by the spec but not reproduced inside it. They are best-effort or omitted in the current build:

- `<<<CHARTER_GAP — PM TO POPULATE>>>` §4B.5 — full add-on protocol details (current code uses the spec summary only).
- `<<<CHARTER_GAP — PM TO POPULATE>>>` §3B v1.8.1 → v1.8.2 delta — any items added between 1.8.1 and 1.8.2 beyond the v2 changes already in the spec front matter (PTRS binary; sizing to Risk Cell; Druckenmiller added; Risk Cell all-voting; deliberation-first sequence; opus-4-6).
- `<<<CHARTER_GAP — PM TO POPULATE>>>` Recovery-mathematics escalation rules — Seow's lookup table is in the spec, but trigger thresholds (PTJ-side) are not specified.
- `<<<CHARTER_GAP — PM TO POPULATE>>>` Q-aggregated win-rate / drawdown thresholds that gate protocol availability.

PM: fill these in directly in this file. Voice prompts and Alfred re-read this charter at startup.
