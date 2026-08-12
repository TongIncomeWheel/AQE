# S6 — DELIBERATION · bounded inter-agent debate, provable completeness

**Design rulings applied.** (PM, 2026-08-12) The committee is the eleven grounded seats;
deliberation is those seats cross-examining each other, not fresh personas invented for the
occasion — the earlier BULL/BEAR/JUDGE draft is retired, those three had no canon. (PM,
2026-08-12b) Rogers and Steenbarger positioning confirmed. (PM, 2026-08-12c) Debate is
**iterative** — a seat may speak more than once — and the round trip must be **provable**.

---

## Shape

```
S4  ROUND 1 — independent assessment      11 seats, isolated, full universe
        ↓  deterministic tally + narrowing
S5  CHALLENGE + WEATHER                   rogers · crown (verbatim) · druckenmiller
        ↓
S6  ROUND 2 — cross-examination           ALL 11 seats, see each other, stance on EVERY name
        ↓  obligation register computed
    ROUND 3 — rebuttal (TRIGGERED)        ONLY seats carrying an open direct challenge
        ↓  completeness certificate
    CONSENSUS                             arithmetic close · no model
```

Round 1 asks *what do you like?* Round 2 asks *now that you see everyone else — do you still?*
Round 3 asks only the seats who were **named and attacked**: *answer that.*

---

## The two contrarian functions (PM-confirmed)

- **rogers — is the CROWD wrong?** Files its challenge in S5 on crowding · certainty · timing.
  Its entries become obligations every supporting seat must answer in Round 2.
- **steenbarger — is the COMMITTEE wrong about its own certainty?** Its canon is trading
  psychology, which makes it the auditor of conviction itself: unanimity, conviction inflation,
  attachment to a name carried from a prior day, revenge-nomination after a loss. Returns a
  `conviction_audit` covering every narrowed name alongside its normal position.

Different targets, both wanted. Neither blocks; both cap.

---

## ROUND 2 — cross-examination (all seats)

Packet collapses from Round 1's ~215 KB to ~25 KB, because the set collapsed from 162 names to
6–10: the narrowed set · every seat's Round 1 case for those names verbatim with `field_values`
· this seat's own Round 1 position (as data, to defend or revise) · rogers' challenge · the
weather · its unchanged field menu.

Each seat returns a position on **every** name (`contracts/pma/round2_position.schema.json`):
`stance` (SUPPORT/OPPOSE/ABSTAIN — mandatory, silence unavailable) · revised `conviction` ·
`conviction_change_reason` naming what moved it · `opposing_argument` (required on every OPPOSE
**and** every SUPPORT at conviction ≥4 — high conviction must show it has looked) ·
`answers_challenge` · `what_would_make_me_wrong` · `abstain_reason` ("outside my canon" is valid
and useful — it tells the PM where a seat has no competence).

---

## The obligation register — what makes completeness provable

Every mandatory element of the deliberation is instantiated as a tracked obligation the moment
it is created, and carried until discharged. This is the round-trip proof.

| ID | Obligation | Owed by | Created when |
|---|---|---|---|
| **O1** | A stance on every narrowed name | every responding seat | Round 2 opens |
| **O2** | An opposing argument on every OPPOSE | the opposing seat | that stance is filed |
| **O3** | A self-authored counter-argument at conviction ≥4 | the supporting seat | that stance is filed |
| **O4** | A falsifier on every stance | every seat | that stance is filed |
| **O5** | A reason naming what moved a changed conviction | that seat | conviction ≠ Round 1 |
| **O6** | An answer to each rogers challenge entry | every supporting seat on that name | S5 files the challenge |
| **O7** | **A reply from any seat challenged BY NAME** | the named seat | a peer's OPPOSE cites its case |
| **O8** | Conviction-audit coverage of every narrowed name | steenbarger | Round 2 opens |

**O7 is the inter-agent debate.** When one seat's OPPOSE directly attacks another seat's named
case, the attacked seat acquires a right — and an obligation — of reply. That is what triggers
a seat speaking twice.

### Coverage matrix

`voice × name → stance`. `cells_expected = responding_seats × narrowed_names`. The close is
blocked while `cells_present < cells_expected`. A seat returning a position set that skips a
name fails schema validation and is re-spawned before it is ever counted.

---

## ROUND 3 — rebuttal (triggered, not scheduled)

Runs **only** if open O7 obligations exist. Only the challenged seats are spawned, and each
sees only the challenges against it (plus the name's data row). A seat challenged on four names
answers all four in one spawn — typically 2–4 spawns at ~5 KB each. It may revise conviction;
any revision still requires O5's reason.

**Hard cap: `max_exchanges_per_name = 2`.** Initial position plus one rebuttal. There is no
Round 4. Convergence between models is agreement, not truth, and manufacturing it costs tokens
and buys nothing.

---

## Resolution — procedural, never substantive

This is the rule that keeps the orchestrator unbiased while still closing the loop:

> **An obligation is discharged when a reply EXISTS. The orchestrator never judges whether the
> reply was good.**

Whether it persuaded is *computed*, not assessed: after the rebuttal, did the challenging seat's
conviction move?

- reply exists **and** raiser's conviction moved → `discharged`
- reply exists **and** raiser's conviction unmoved → `contested`
- no reply after the cap → `contested`
- seat absent after retries → `waived`, with the failure reason recorded

**`contested` is a legitimate terminal state and it is printed on the plan line.** Two seats
holding opposite positions after full exchange is real information about the name — flattening
it into a number would destroy the most useful thing the committee produced. The orchestrator
records the deadlock; it does not break it. Breaking it is the PM's job.

---

## Failure handling — no silent holes

| Failure | Handling |
|---|---|
| Seat returns invalid | re-spawn once; still invalid → `absent`, its obligations `waived` with reason |
| Seat skips a name | schema rejection → re-spawn; never silently accepted |
| Seat never replies to an O7 | `contested` at the cap, printed |
| Quorum not met (< required responding seats) | deliberation does not stand: no ADVANCE, watch-table-only plan, failure in the headline |

---

## The completeness certificate

`data/pma/<date>/completeness_certificate.json`
(`contracts/pma/completeness_certificate.schema.json`) — produced mechanically, and the
**consensus close is blocked until it exists**. It carries: the expected vs responding roster
with per-seat failure reasons · the full voice×name coverage matrix with any missing cells ·
every obligation from creation to discharge · the complete exchange trail (`from → to`, kind,
whether it moved conviction) · what ran in each round and why · quorum · and the close reason,
one of `all_obligations_discharged` · `rebuttal_cap_reached_remaining_contested` ·
`quorum_failure` · `seat_failures_waived`.

**S8 re-derives this certificate independently from the raw stage outputs and fails the run on
any disagreement.** A completeness claim checked only by the component that made it is not a
check.

---

## CONSENSUS — arithmetic close, no agent

Verdict from the seats' own positions: `PASS` if opposers outnumber supporters or an OPPOSE
went unanswered at the cap; `ADVANCE` if ≥2 supporters, median supporter conviction ≥3, and
every OPPOSE answered; `HOLD-FOR-CONDITIONS` otherwise, carrying the observable that promotes it.

Conviction = median of supporters' revised conviction, then capped — **caps only ever lower**:
3 if any decisive claim rests on a `NOT_SERVED` field · 3 if steenbarger's audit flagged the
name · 3 if the name closed `contested` · 4 if an unanswered rogers flag stands · 4 if
`support_count < 3`.

Record carries, all quoted and attributed, none generated: `stance_split` by name ·
`decisive_exchange` (computed: which exchange moved the most convictions) · `bear_case`
verbatim from the strongest OPPOSE · named `dissent`, preserved never averaged · union of
`falsifiers` · `data_anchors` · `contested` flag.

---

## Cost

| Round | Spawns | Packet |
|---|---|---|
| R1 independent | 11 | ~215 KB (162 names) |
| S5 rogers + druckenmiller | 2 | small / ~45 KB |
| R2 cross-examination | 11 | ~25 KB (6–10 names) |
| R3 rebuttal | 2–4 typical | ~5 KB |
| Consensus + certificate | **0** | arithmetic |
| **Total** | **~26–28** | vs 33 in the retired draft, with zero ungrounded personas |

## Hard limits

No sizes, no orders, no dollar amounts, no position management. Conviction and frame-fit are
the ceiling; capital is the PM's and lives behind the existing gates. Constitution law 1 untouched.
