---
name: pma-deliberate
description: The Chair's procedure for the committee floor (R36, PM 2026-10-30) — rounds 3 to 7 of /pma: board, open floor on contested names, slate (at most 15), ratification, Steenbarger's QA note with at most one hold per ticket, close. Invoked by the /pma conductor at the FLOOR step; never typed by the PM. Code counts (board / floor-check / ratify-count); the Chair runs the table and never votes.
---
# PMA-DELIBERATE — the floor, the slate, the ratification (the Chair's half of R36)

**Job:** turn seven blind votes on an identical packet into the committee's AGREED BEST — a ranked slate
of at most 15 tickets with every objection on the record — without any one agent ever writing another's words.
**Trigger:** the `/pma` conductor, at RUN.yaml step FLOOR, after every decider's round-2 ballot is committed.
**Owner agent:** `agents/chair.md`. **Seat side:** `aegis-voices:voice-deliberate`.

## Inputs (files + contracts)
| File | Contract | Made by |
|---|---|---|
| `phase4.json` | universe/phase4 | RANK |
| `forms/r2/<voice>.json` | `contracts/vote_round2.schema.json` + `case_form.schema.json` | VOTE (deciders) |
| `forms/challenge/steenbarger.json` | `contracts/challenge.schema.json` | CHALLENGE |
| `board.json` | `board.v1` (built here) | `pma_pipeline.py board` |

## Steps
```
FLOOR  pma_pipeline.py board --round2 forms/r2 --phase4 phase4.json \
           --challenge forms/challenge/steenbarger.json --date <date> --out board.json
       Chair posts each contested name to the deciders (SendMessage), quoting board.json
       deciders message each other -> forms/floor/<ticker>/<msg_id>.json
         each: registrar.py validate --file <msg> --kind floor --phase4 phase4.json --board board.json
       pma_pipeline.py floor-check --messages forms/floor --board board.json --out floor_check.json   (must exit 0)
SLATE  Chair writes slate.json; registrar.py validate --file slate.json --kind slate --phase4 phase4.json
RATIFY each decider -> forms/ratify/<voice>.json; registrar.py validate --file <f> --kind ratify --slate slate.json
QA     steenbarger -> forms/qa/steenbarger.json; registrar.py validate --file <f> --kind qa --slate slate.json
       if holds: per held ticket, Chair posts the question; forms/floor2/ ; floor-check --messages forms/floor2 --qa forms/qa/steenbarger.json
                 deciders -> forms/ratify2/<voice>.json (held tickets only; validate --kind ratify --slate <slate cut to held>)
DECIDE pma_pipeline.py ratify-count --slate slate.json --ratifications forms/ratify --ratifications2 forms/ratify2 \
           --qa forms/qa/steenbarger.json --board board.json --messages forms/floor --messages2 forms/floor2 \
           --phase4 phase4.json --date <date> --out consensus.json --record committee_record.json
```
Every file is committed with `registrar.py commit` as it lands (checkpoints after FLOOR, SLATE, RATIFY, QA).

## Outputs
`board.json`, `forms/floor/**`, `floor_check.json`, `slate.json`, `forms/ratify/*.json`, `forms/qa/steenbarger.json`,
optionally `forms/floor2/**`, `forms/ratify2/*.json`; then `consensus.json` + `committee_record.json` at DECIDE.

## Checks (what proves it ran)
- `floor-check` exit 0 on every round it was run.
- `slate.json` validates; `len(tickets) <= 15`; every ticket in the deliberation set.
- A ratification from every decider present (barrier 6 of 7); `ratify-count` refuses fewer than 4.
- `committee_record.json` has one row per decider per room name; every floor msg_id in the record exists on disk.
- No `verdict` key anywhere in `board.json`.

## Failure policy
A cap breach: the message is rejected, its author re-files once. A slate REJECT: fixed once, then halt + declare.
A silent seat on the floor: recorded as silent, never spoken for. A missing QA note: DECIDE runs with no hold and
declares it. Fewer than 4 ratifications: halt, no committee today, say so in chat.

## What the PM sees
Nothing from this skill directly. The card report's Part 2 shows the slate (ADVANCE then WATCH, up to 15),
the objections on CONTESTED tickets and what would clear them, and the dropped names in the appendix.

## Budget
Unmeasured until the Phase 1b pilot (two real seats, one contested name). Each seat resume on 30 Oct cost
66–72k tokens of fixed overhead on trivial agents. The spend ceiling (1.5× the ~905k baseline) is the Checker's.

## Laws that bind here
R1 (a bracket is never a reject — on the floor too), R31 (who speaks), R32 (all seven count), R34 (the count),
R35 (everything recorded), R36 (the rounds and the caps). The Chair is not a voice (R36).
