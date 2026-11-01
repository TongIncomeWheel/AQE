---
name: pma
description: "PMA — Premarket Analysis, the committee morning. Trigger: /pma (or /pma resume). v5 CONDUCTOR architecture (PM-approved design 2026-08-28): the run is an explicit map of steps with a durable scoreboard — every step reads saved files, writes saved files, ticks run_manifest.json; the conductor schedules and holds nothing else, so crashes cost one step, never the run. Data-steward agent fetches ALL outside data up front (incl. FMP fundamentals batch + AQE pre-sliced voice packets, stamp-verified with local fallback); registrar.py validates every seat FORM on arrival; purity_check.py proves rank invariance to bracket/fundamental fields + prints the crowding audit; PM LENS runs in its own lane beside the committee; repeat-watch and verdict ledgers snapshot to the store each tick; brief-writer renders the 9-section CIO brief from the store ONLY, to the connective-narrative contract, and the brief ALWAYS lands — degraded with declared gaps if needed. Analysis only — no brokers, no orders, no sizing."
---

# /pma — PREMARKET ANALYSIS (v5.4 conductor card)

**This card is short on purpose.** Until 2026-09-07 it was a 117-line prose essay, and an operator
whose context is compacted mid-run cannot reliably re-derive a step's inputs, barrier and meter call
from a paragraph. On 2026-09-06 three rulings held and three did not, and the difference was never
authority — only whether the rule had been compiled into something that could fail.

**The run is now defined by two data files, not by this page:**

| File | What it holds | Read it with |
|---|---|---|
| `RUN.yaml` | Every step: command, inputs, outputs, barrier, on-fail, meter call | `preflight_run.py step <NAME>` |
| `RULINGS.yaml` | Every standing ruling, its check, and where it binds | `preflight_run.py run` |

This card explains. It does not decide. **Where this page and those files disagree, the files win.**

---

## THE LOOP — every step, no exceptions

```
preflight_run.py step <NAME>          # inputs present + rulings binding here, printed
<run the command, or spawn the seats>
registrar.py validate --file <f> --round <n> --packet <the seat's packet>   # model steps
registrar.py commit ... --step <NAME> # each artifact as it lands, not at end of stage
git_sync.py -m "pma <date> after <NAME>"   # IF RUN.yaml marks this step checkpoint_after
registrar.py meter  --step <NAME> ... # spawns + bytes, or --tool-only
registrar.py tick   --step <NAME> --status done|degraded
```

**Three things that step will now refuse to let you skip, each because skipping it cost a run:**

- `validate --packet` is not optional on a model step. Without it the figure audit does not run,
  and a seat that invented its numbers commits as if it had read the row. R2's md5 half never ran
  once — no seat has a hashing tool, so on 2026-09-15 all eleven declared `NOT_VERIFIED` and it had
  been routine long enough to be invisible.
- `tick --status done` **refuses** to close a step whose declared `produces:` are not at their
  declared paths. On 2026-09-15 GATHER's ledgers landed under `data/`, GATHER ticked done anyway,
  and the first complaint came four steps and ~115k model tokens later. Do not answer that refusal
  by re-pointing the next tool at wherever the files actually landed — that adapter is forbidden
  (R6). Fix the step. A genuinely degraded run uses `--status degraded` or `--force-incomplete`,
  both of which write the gap to the scoreboard.
- A `checkpoint_after` step is not finished until it is pushed. Local disk is disposable; the run
  map says which steps are worth the push and why.

A finished step is NEVER re-run. `/pma resume` reads the scoreboard and restarts the first step not
ticked done. The conductor holds nothing in its own memory but the scoreboard.

## BEFORE THE RUN — one command, non-negotiable

```
preflight_run.py run     # asserts the mechanical rulings AND runs the regression suite
preflight_run.py stamp   # records the sha256 of every tool this run will execute (R7)
```

If preflight fails, **the run does not start.** On 2026-09-06 the committee executed a pipeline one
commit stale and nothing noticed for a day; `stamp` plus the R7 check is why that cannot recur.

## THE MAP

```
INBOX-CLEAN → GATHER → PREPARE → [MACRO ∥ NOMINATE] → RANK ─┬→ CHALLENGE → VOTE → DECIDE → CONDITIONS → REPEAT-WATCH → BRACKET → SCORECARD ─┬→ WRITE → CHECK → LEVELS → REPORT → PUBLISH
                                              └→ PM-LENS (independent lane, feeds nothing) ─┘
```

26 model spawns across 5 spawn steps (VOTE is 10 seats since R22: Lynch is consulted, not voting). Everything else is a tool step and costs no model tokens.
Measured budget: **~905k model tokens for a clean run** (VOTE 352k · NOMINATE 172k · WRITE 240k ·
CHALLENGE 107k · MACRO 34k) plus conductor overhead. `registrar.py status` prints the live number.


## WHAT CHANGED 2026-10-23 (PM rulings R22–R24)

| Ruling | What it does |
|---|---|
| **R22** | Livermore votes. Lynch files the fundamentals challenge only; `consensus` ignores any Lynch ballot. 10 voters. |
| **R23** | **The Committee Cards report has ONE fixed format**, rendered by `tools/pma_cards.py render` from the run files + `cards_text.json` (words only). Publish it to the ONE artifact URL in `RUN.yaml parameters.card_report_artifact`, updated in place. Never hand-write or restyle the HTML. Triggers for LEVELS come from `pma_cards.py triggers`. |
| **R24** | **INBOX-CLEAN** runs first: trash (never delete) every Gmail thread from "AQE Alerts" or whose subject starts with "[AQE]". GitHub "[TongIncomeWheel/AQE]" mail is skipped. |
| Valen | GATHER fetches `aqe_valen_dashboard.json`; `r2digest --valen` adds a VALEN block to the vote packet (levels omitted, R1); the card report and §1A carry the weather, setups and U&R. |
| Seats | Spawned as general-purpose agents reading their own card + packet by path (the voice agent types have no file tools). Challenge packets: `pma_pipeline.py challenge-packets`. |
| Fixes | figure audit reads `field=value`; vote-packet fundamentals map the nested FMP pack; an injected held row's `entry` is the last price, not the cost. |

## THE FLOOR, THEN THE DOORS (admission — RANK)

**R16, PM ruling 2026-09-24 — the doors are ADDITIVE. They never gate or remove an analyst pick.**

> "I never asked to leave 5 seats or whatever that means. It is additive and not to gate or remove
> voice (analyst) picks."

**THE FLOOR — admitted unconditionally, never cut, never bounded by the cap:**

| On the floor because | Rule |
|---|---|
| NOMINATED | any seat nominated it, at any conviction |
| HELD | the PM owns it (R16 + R12) — so the ADD question is asked, not only keep/exit |

**THE DOORS — ADDITIONS ONLY.** They fill `--door-budget` (default 8) *on top of* the floor and can
never displace a floor name. `--cap` bounds the doors alone. There is no sector door and no strength
reserve (retired).

| Door | Opens when |
|---|---|
| ELDER+LENS | elder ≥ 7 on each of the last 2 bars AND ≥ 3 of 6 lenses strong |
| LENS | ≥ 4 of 6 lenses strong |
| STRENGTH | rs_spy_20d top decile of today's list, OR mp ≥ 75 and ACCELERATING |
| PM_LENS | ≥ 5 of the PM's 6 checks |
| AQE_LEADER | elder_pattern SUSTAINED\|ACCELERATION AND rs_leadership LEADER (R13) |

Floor ordering (`seat_count > conviction_sum > thematic_support > sc_momentum`) is for READING ONLY —
it never removes a name (R4: sector is not in it). Additions order by
`doors_opened > lenses_strong > AQE rank`. `cmd_rank` asserts the invariant and **aborts the run** if
a nomination is ever cut.

**Why this changed.** Three runs shared one 24-seat pool between seat picks and machine finds and the
machine won: 107 nominations → 43 seated, **64 binned**, and 29 chairs to names no analyst asked for.
Conviction-4/5 nominations ADVANCE 70% (n=23); no-nominator admits ADVANCE 10% (n=29, 14 passed
outright). The cap was never a PM rule — its real ceiling was `MAX_FORM_BYTES` in `registrar.py`, so a
**file size limit was deciding which of the PM's analysts were heard.** Split ballots
(`registrar validate --part N --of M`, then `registrar merge`) removed that ceiling; R16 removed the
competition.

## THE CONDITIONS (R21 / D123 — what AQE watches)

The vote is unchanged. Every SUPPORT also writes, in the shared words of `contracts/condition_vocab.json`,
when the analyst acts and when they are wrong (levels by field name, never numbers). `pma_conditions.py`
compiles them without judgment; `pma_levels.py` attaches them to each alert row for AQE. Seat prompt
text: `contracts/conditions_block.md`.

## THE SCORECARD (D122.1 — every run, logged)

Every run grades every logged call three ways — vs SPY, vs the AQE list it was picked from, net of
beta — and appends one line per close to `scorecard_log.jsonl` on AQE main. The brief and the card
report carry it. `pma_scorecard.py trend --log scorecard_log.jsonl` prints the monitored trend.
Grading only; it never moves a verdict. PM review due 2026-10-15.

## THE VERDICT RULE (DECIDE)

`ADVANCE` = support > oppose AND support ≥ 2 AND median support conviction ≥ 3.
Else support ≥ 2 → `HOLD-FOR-CONDITIONS`, with a mandatory observable condition line.
Else `PASS`. **Never hand-tallied** — `pma_pipeline.py consensus` computes it or the run is invalid.

## THE LEVELS FILE (R20) — what AQE watches live

After CHECK, `pma_levels.py emit` turns the committee's output into `pma_levels.json`: every ADVANCE,
HOLD-FOR-CONDITIONS, HELD and WATCH name with numeric triggers. WRITE must put each condition into
`cards.json` as structured `triggers` (kind / level / basis / volume_min_x / priority / action) and each
held name's `committee_exit`; GATHER must write `broker_stops.json` from the broker (read-only). PUBLISH
pushes the file to AQE main at `aegis/output/pma/` — never elsewhere, because any other path redeploys the
HF Space. Alerts only; the file places nothing.

## FAILURE POLICY

| Situation | Action |
|---|---|
| No export | FATAL. Halt, page the PM. |
| Packet stamp mismatch | Local slice fallback at PREPARE, declared, continue. |
| Seat malformed / off-universe / hangs past 15 min | Reject on arrival, one respawn, then absent. |
| NOMINATE < 8 of 9 | Halt and report — no committee. |
| VOTE < 8 of 11 | Watch-table-only run, declared. |
| Purity invariance FAIL | Do not publish on that ranking. Fix at RANK, max 2 loops. |
| Shape mismatch on any read | **Fix the contract. An adapter is not a fix (R6).** |
| Held position absent from the universe, or served without `hl_state` | **PREPARE refuses to build packets (R12).** Re-run `trim`. A name the PM owns is never screened out of its own committee. |
| Session crash / compaction | Nothing to do. `/pma resume` in a fresh session. |
| Durable store unwritable | The one hard stop. |
| Brief deadline (4h) | WRITE runs on whatever the store holds. **The brief always lands.** |

## WHAT NEVER CHANGES

Every degradation is declared in the brief header. Nothing is ever silently dropped or
reconstructed. Footer, always: **"DRAFT — PM approval required. Nothing is staged, nothing is armed."**

---

*The v5.3 prose card is kept as `SKILL_v53_prose.md.bak` for reference only. It is not authoritative.*
