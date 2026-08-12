# PMA — EXECUTIVE REVIEW · what is designed, what is left, what needs your steer

**Wed 12 Aug 2026 · for PM sign-off before the sample run**
Everything referenced here is on GitHub `TongIncomeWheel/AQE` @ `main`. The local working copy
is disposable — it has been wiped by container resets four times in this build and every
artifact that survived did so because it was pushed.

---

## 1 · WHERE THE DESIGN STANDS

| Stage | Card | Contracts | Runner code | Ever run |
|---|---|---|---|---|
| S1 Ingest | ✅ v0.4 (repo-as-source) | ✅ | ⚠️ built for the **old Drive layout** | ✅ |
| S2 Market frame | ⚠️ thin (v0.1, 1.6 KB) | ✅ | ✅ | ✅ clean |
| S3 Candidate frame | ⚠️ thin (v0.1, 1.2 KB) | ✅ | ✅ | ✅ clean |
| S3H Held book | ✅ v0.4 | ❌ none | ❌ | ❌ |
| S4 Round 1 swarm | ✅ v0.4 | ✅ reuses `nomination.schema.json` | ❌ | ❌ (F1 fabrication) |
| S5 Challenge + weather | ✅ v0.4 | ✅ | ❌ | ❌ |
| S6 R2 / R3 / consensus | ✅ v0.4 (the deepest card) | ✅ ×3 | ❌ | ❌ |
| S7 CIO output | ✅ v0.4 | ✅ | ✅ | ✅ partial |
| S8 Self-audit | ⚠️ thin (v0.1, 1.5 KB) | ⚠️ predates completeness cert | ✅ | ✅ |

**Plain reading:** the *thinking* half — S4, S5, S6 — is fully designed and completely unbuilt.
The *plumbing* half — S1, S2, S3, S7, S8 — is built and proven on real data, but S1 still
fetches the old way and S2/S3/S8's cards were never upgraded past v0.1.

The judgment stages have never executed end-to-end. That is the honest headline.

---

## 2 · THE NINE GAPS

Ranked by what blocks a real run.

### BLOCKING — a live PMA cannot run without these

**G1 · No orchestration spec.** `SKILL.md` says what the stages *are*; nothing says how the
orchestrator *drives* them — spawn concurrency, retry policy, timeouts, how a failed seat is
detected, ordering guarantees between R2 and R3. This is the single largest hole and it is
pure design, not code.

**G2 · No packet-builder spec.** S4 mandates inlined content (finding F1: toolless seats handed
a path *fabricate* rather than fail). But nothing specifies the component that slices the
universe to a seat's menu, shuffles row order per seat, injects ledger memory, and inlines it.
Without this, S4 cannot be built correctly — and built incorrectly it hallucinates silently.

**G3 · No held-read contract.** S3H says every seat gives a read on every position, but
`nomination.schema.json` describes *nominations*. A held read (RUN/TAKE-PARTIAL/TIGHTEN/EXIT
with reasons, falsifier, opposing argument) has no schema. S3H cannot be built until it does.

**G4 · S1 fetches the old way.** The runner was written when Drive was the source; the v0.4
card rules the repo is the source (`data/aqe/<date>/`, gzipped, `latest.json` pointer). Runner
and card disagree. Card wins; code needs updating.

### SHOULD-FIX — the run works but degrades or misleads

**G5 · S8 does not re-derive the completeness certificate.** The S6 card requires S8 to rebuild
it independently and fail on disagreement — "a completeness claim checked only by the component
that made it is not a check." `run_audit.schema.json` predates that requirement.

**G6 · TAKE-PARTIAL cap not in the schema.** S3H rules conviction ≤3 on TAKE-PARTIAL while
unrealised is unserved. `consensus.schema.json`'s cap enum has no such value.

**G7 · "What changed" has no source.** S7 renders a diff against yesterday's plan; nothing
specifies where yesterday's plan is found or what happens on day one.

**G8 · S2/S3/S8 cards are v0.1 stubs.** They work, but they are 1.2–1.6 KB against 3.5–8.9 KB
for the upgraded cards, and they no longer describe what the code does after four revisions.

### DEFERRED — deliberately not now

**G9 · Scheduling, retention tooling, post-market scoring.** All designed-in, none built.
Correct to defer until the pipeline runs once.

---

## 3 · WHAT I NEED YOUR STEER ON

Four decisions. Each changes what gets built; all are cheap now and expensive later.

**D-A · Sample run scope.** A full 11-seat, 2-round run is real token spend and this session has
already been long. I recommend a **3-seat vertical slice** — enough to prove the whole chain
(packet → isolated seat → nomination → tally → narrowing → cross-examination → consensus →
CIO page) without paying for 11. It proves the *machinery*; it does not produce a tradeable plan.

**D-B · Data for the sample.** The newest export on this machine is **2026-07-28 — 15 days
stale**, and today's live Crown file was lost to a reset. Options: (i) run on the stale export
with staleness declared at every stage — this also *tests the honesty ladder*, which is the
thing most worth testing; (ii) re-fetch today's files from Drive first. (i) is faster and proves
more about the design; (ii) produces a more realistic-looking page.

**D-C · Held book in the sample.** S3H has no contract yet (G3). Include held (write the
contract first, sample covers both populations) or exclude (new ideas only, held stays design)?

**D-D · Fix order after sign-off.** My recommendation: **G3 → G2 → G1 → G4**, because the
contract defines the packet, the packet defines the spawn, and the spawn defines the
orchestrator. Building inward-out in that order means nothing gets written twice.

---

## 4 · DATA PROVENANCE — where everything comes from and lands

Confirmed, not assumed.

**Sources**

| What | Where it comes from | Status |
|---|---|---|
| AQE daily export | AQE writes to Drive folder `1CJMoI19Zf_ZFeU5_5uhW9l92IB8fVger` | live; newest local copy 2026-07-28 |
| Nick Crown macro | same Drive folder, `aqe_crown_macro.json` | live; verified 2026-08-11, `status: DEGRADED` |
| Held positions | **the AQE export's `held_positions`** (PM ruling 2026-08-12) | 12 positions, ~80 fields, thesis fully served; PTJ-overlay fields null until PTJ re-runs |
| Voice canon | `aegis/canon/<voice>/canon.lock.yaml` on GitHub | 14 seats locked |
| Voice memory | `tools/voice_memory.py render <voice>` | existing tool |

**Landing — everything in the repo**

```
data/aqe/<date>/    aqe_daily_export.json.gz · aqe_crown_macro.json · manifest.json
data/aqe/latest.json
data/pma/<date>/    ingest_receipt · market_frame · candidate_set · held_set
                    voices/*.json · tally.json
                    challenge.json · weather.json
                    round2/*.json · round3/*.json
                    consensus.json · completeness_certificate.json
                    premarket_plan.json · plan.md · run_audit.json
```

**S1 is the only component permitted to touch Drive.** Enforceable by grep: any Drive tool call
outside S1 is a design violation. Everything downstream reads the repo.

---

## 5 · WHAT IS ALREADY TRUE AND WORTH KEEPING

- **14 seats grounded**, zero stubs. Druckenmiller from the real book (pp.229–256, 21 of 27
  principles cited to pages actually read); detect-lens from executing engine code.
- **The honesty ladder works** — proven live: S1 refused a stale export until an explicit
  acknowledgement was recorded verbatim, and Crown's DEGRADED flags rode through untouched.
- **No synthesis agent anywhere.** The consensus close is arithmetic; every prose field is an
  attributed quote. The orchestrator cannot form a view.
- **Completeness is provable** — 8-type obligation register, voice×name coverage matrix,
  triggered rebuttal with a hard cap, `contested` as a legitimate printed outcome.
- **Cost is bounded** — ~26–28 spawns, no ungrounded personas, R2 cheaper than R1 because the
  set collapses ~95% before it runs.
