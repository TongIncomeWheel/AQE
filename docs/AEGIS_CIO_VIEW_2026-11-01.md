# Aegis — the CIO view (as built, 1 Nov 2026)

**One paragraph.** AQE computes the data every night and publishes one export. Aegis is a committee of seven isolated analyst agents that reads that export, argues, and hands the PM a ranked slate of at most 15 tickets with every objection on the record. Code counts; the voices judge; the PM decides and executes every order himself. Nothing in the system places, sizes or arms anything. As of today the committee engine is built and tested (476 plugin tests, 1708 AQE tests, zero new failures) on the branch `claude/upbeat-curie-s7i1ut`; it has **not** run a live committee and is **not** on `main`.

---

## 1 · What is deployed, in layers

| Layer | What it is | Where | State |
|---|---|---|---|
| **Data engine (AQE)** | Nightly US-equity scanner: 5 engines, brackets, DETECT, Crown macro, Valen dashboard, voice packets. One export JSON. | `src/`, runs in GitHub Actions `daily-run.yml`, mirrored to the HF Space | **Live.** Unchanged in judgment this session; only the packet roster (7 deciders) and two safety fixes. |
| **Committee kernel (plugins)** | `/pma` conductor (RUN.yaml, 22 steps), registrar (every form validated on arrival), the counting tools, the Chair, the seven decider cards + Steenbarger QA, `/daily`, `/stops`, live review. | `aegis/plugin/` — the one code tree; `build.py` makes the installable `.plugin` files | **Built, tested, not installed.** The PM's machine still runs the old 15-voice plugins. |
| **Scheduled tasks** | 05:30 `/daily` (book close, journal); 08:30 AQE dispatch + dated-output check. | Claude scheduled tasks on the account | **Live.** The trigger-file push that rebuilt the Space was removed today. |
| **Checker** | `daily-check`: READY (AQE finished today, success) and chain proof after a run. Read-only. | `aegis/plugin/aegis-core/skills/daily-check/` | **Built, tested against seeded failures, not yet scheduled.** |
| **Cards report** | The PM's one read: weather, book, the slate with objections, Detect-lens top 10. Fixed layout, one artifact URL. | `pma_cards.py` | **Built.** Status pills, objections, DROPPED marks and the lens panel added today. |

---

## 2 · The daily process (SGT)

```
05:30  /daily          close the book (Tiger pull, PTJ batch), push the journal to GitHub, print it.
08:30  AQE run         scheduled task dispatches daily-run.yml; export + packets + Crown + Valen land
                       under aegis/output/ on main; aqe_last_run.json is written LAST (~08:59).
~09:00 READY           Checker: aqe_last_run.json dated today, status success → "READY" in chat.
       PM taps /pma    (by design there is no PMA routine — the PM holds the start)
         prep          inbox clean · gather · prove the inputs                       (tool steps)
         committee     NOMINATE (7 blind, ≤6 each) → RANK → CHALLENGE (Steenbarger)
                       → VOTE (7 blind, case form) → FLOOR (board, 2 msgs/seat/name)
                       → SLATE (Chair, ≤15) → RATIFY (7) → QA (note + ≤1 hold/ticket)
                       → DECIDE (code counts: 0 agreed / 1–3 contested / 4+ dropped)
         publish       conditions · brackets · scorecard · brief · levels · Cards report
                       → pma_levels.json pushed under aegis/output/pma/ (what the alerts watch)
       Checker         chain proof: every step ticked, forms present, caps held, levels dated,
                       spend under 1.5× baseline → "Healthy" or what broke.
21:30–04:00 US session AQE alert digests every 15 min (code only); live review every 30 min.
```

Every model round is checkpointed to `aegis/output/pma/run/<date>/`; a crash costs one step, never the run (`/pma resume`).

---

## 3 · Architecture — the rules that hold it together

1. **One code tree.** `aegis/plugin/` is the truth. The three files the nightly run reads are generated from it; a test fails on drift. (Before today AQE sliced packets with a plugin a week behind the live one.)
2. **Code counts, voices judge.** Tally, contested set, floor caps, objection count, verdict words, record — all tools. No model ever writes another model's words; the Chair quotes, never paraphrases.
3. **Blind, then open.** Nominate and vote are blind on an identical packet. The floor opens only after every decider is on record, and only on contested names.
4. **Forms, not essays.** Nomination, vote (with the case form: for, against, trigger, wrong-if, horizon, would-change-my-mind, cannot-see), challenge, floor message, slate, ratification, QA note — each has a contract and is rejected on arrival if incomplete. History validates as it was filed.
5. **Everything recorded.** `committee_record.json`: per voice, per ticket — blind vote, horizon, floor messages, change of mind and what moved it, ratification, objection. Dropped and contested names tracked. Each voice is graded at its own horizon.
6. **Rulings are data.** R1–R36 in `RULINGS.yaml`; preflight binds each at the step it governs. R14/R22/R30 superseded, never deleted.
7. **Nothing rebuilds the Space by accident.** Pushes land under `aegis/output/**` only; the checkpoint tool refuses anything else.
8. **A bracket is never a reject** (R1) — on the floor as everywhere. Enforced by the registrar on every free-text field.
9. **One risk figure.** 1R = $620 (PM 27 Oct) in `aegis_fund.md`; every Aegis sizing path reads it and says so. AQE's alert cards keep their own $75K/3% and are to be ignored for Aegis sizing.

### The roster (R31)
Deciders: O'Neil, Minervini, Livermore, Elder-lens, Seow, Raschke, Wyckoff. QA: Steenbarger (challenge before the vote; QA note + one hold per ticket after; never votes). Detect-lens: an independent top-10 list from AQE's own `lens_ranking`, shown beside the slate, never a vote. Bench: Weis, Thorp. Stood down: Rogers, Lynch, Crown, Druckenmiller — the weather is read from AQE's Crown file and the Valen dashboard.

---

## 4 · Orchestration and delivery

| Who | Does | Never |
|---|---|---|
| Conductor (`/pma`) | Runs RUN.yaml step by step, ticks the scoreboard, spawns seats, checkpoints | Forms a view, hand-tallies, re-runs a finished step |
| Chair | Posts the board, enforces caps, drafts the slate from what seats said, asks for ratification, reopens a held ticket once | Votes, adds a view, judges a reason's quality |
| Seat (×7) | Blind nomination and vote; floor messages by name; ratification | Sees another seat before its blind vote; invents a field; speaks after the cap |
| Steenbarger | Challenge document; QA note; at most one hold per ticket | Votes, vetoes |
| Registrar / tools | Validate every form; count; write consensus, record, levels | Judge |
| Checker | Prove the chain ran; post READY; name what broke | Fix, trade, re-run |
| AQE engineer | Change AQE code through tests and a safe-window release | Touch a live run; change sizing; push to main without the PM |
| **PM** | Taps `/pma` after READY; reads the Cards; decides; executes at Tiger | — |

Delivered to the PM: the **Cards report** (one fixed artifact URL), the CIO brief (backing), `pma_levels.json` (feeds the 15-minute alert digests), the scorecard, and one chain-status line.

---

## 5 · What has NOT been proven yet (read before the pilot)

| Gap | Why it matters | Proof needed |
|---|---|---|
| Seats talking to each other | Messaging was proven on two trivial agents only (30 Oct). The floor is the untested mechanism. | **Floor test**: two real seats, one contested name, floor + ratify + hold on real forms |
| Cost of the new run | 7 deciders instead of 10 voters; floor and ratification added. Unmeasured. | Pilot run under the 1.5× (≈1.36M token) ceiling; the Checker reports a breach |
| The split sessions (prep / committee / publish) | Designed, not built; today `/pma` is one session with checkpoints | Dry run, then pilot |
| Weather reading | Crown/Valen read-paths are code (`r2digest --crown`, Cards Part 1) but the PM's reading guide lives in memory | Backlog item 1 — PM handover document |
| Install | PM's machine runs 1.31/1.9; the new `.plugin` files are built but not installed | Install after sign-off; `build.py` output |

---

## 6 · Pilot plan for user sign-off (each step on the PM's word)

| # | Step | Spend | Pass means |
|---|---|---|---|
| 0 | **Review this branch** — read `docs/BUILD_STATE.md`, skim `RULINGS.yaml` R31–R36, the Chair card, one decider card's floor block | none | PM says the rulings read as he meant them |
| 1 | **Dry run on a saved day** (`docs/DRYRUN.md`): run the tool steps on the 29 Oct run dir with synthetic forms for the new rounds — no model spend | none | board / floor-check / ratify-count / Cards produce a complete report from fixtures |
| 2 | **Floor test**: two real decider seats on one contested name; the Chair posts the board; floor; ratify; one Steenbarger hold; re-ratify | ~0.3–0.5M tokens | A seat keeps its case across a resume, answers a specific point by name, files a valid ratification; caps hold |
| 3 | **Shadow run**: full `/pma` publishing only to `aegis/output/assess/shadow/`; diff verdicts and `pma_levels.json` against the live 15-voice run of the same day | 1 run | Checker reads Healthy; spend under ceiling; PM reads the Cards and the objections make sense |
| 4 | **Release**: push the branch to `main` in a safe window (not during a run or the US session; rebuilds the Space once); install the new plugins; Checker confirms the next nightly | none | `aqe_last_run.json` dated next day, success; packets 7/7 |
| 5 | **Pilot week**: live `/pma` daily on the PM's tap; Checker READY post each morning; the record accumulates | 5 runs | One clean week; per-voice record readable; no silent failure |

Sign-off criteria for the PM at the end: the slate is what he would have argued to; every dropped name has its objections on file; nothing was placed by the system.

---

## 7 · Decisions outstanding for the PM
1. Capital line: `aegis_fund.md` says allocated $75K / dynCap $66.7K; the 27 Oct ruling said a $62K portfolio. 1R = $620 either way.
2. `held_sl` / `held_tp` columns are blank every night — where do the values come from?
3. Crown + Valen reading handover (backlog 1); AQE alerts content and market-hours cadence (backlog 2).

*Built in Claude Code, 1 Nov 2026. Branch `claude/upbeat-curie-s7i1ut`. Nothing staged, nothing armed.*
