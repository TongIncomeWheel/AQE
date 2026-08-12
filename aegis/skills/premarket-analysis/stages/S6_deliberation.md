# S6 — DELIBERATION · two rounds, same voices, deterministic close

**Design ruling (PM, 2026-08-12).** The committee is the eleven grounded seats. Deliberation is
those seats cross-examining each other — not fresh personas invented for the occasion. An
earlier draft of this card spawned BULL / BEAR / JUDGE agents; that is retired. Those three had
**no canon**: no locked source, no page cites, no spot-check. Every other agent in Aegis is
grounded, and a verdict shaped by ungrounded personas is exactly the "house view invented in
the middle" the charter forbids (§0.2/§0.3).

The adversarial pressure that draft was trying to buy is real and still wanted. It is now
bought from seats that have standing to give it.

---

## Shape

```
S4  ROUND 1 — independent assessment        11 seats, isolated, full universe
         ↓  deterministic tally + narrowing (no model)
S5  CHALLENGE + WEATHER                     rogers · crown (verbatim) · druckenmiller
         ↓
S6a ROUND 2 — cross-examination             THE SAME 11 seats, now seeing each other
         ↓  deterministic consensus (no model)
S6b CONSENSUS                               verdicts + conviction from a published rule
```

**Round 1 asks "what do you like?" Round 2 asks "now that you can see what everyone else
said — do you still?"** That is the whole difference, and it is where conviction is actually
set. Round 1 conviction is a first impression; Round 2 conviction is a position defended in
front of peers.

---

## S6a · ROUND 2 — cross-examination

Same eleven seats, re-spawned fresh (no memory of their own Round 1 context — they receive
their Round 1 output as data, like everyone else's).

**Packet** — note how much smaller this is than Round 1:

```yaml
round2_packet:
  run:            {date, staleness, degraded_flags}
  narrowed_set:   ~6-10 names only          # NOT the 162-row universe
  peer_cases:     every seat's Round 1 case for those names, VERBATIM with field_values
  my_round1:      this seat's own Round 1 position (as data, to defend or revise)
  challenge:      rogers' entries (crowding · certainty · timing)
  weather:        crown NOW + druckenmiller NEXT
  menu:           unchanged — a seat may still only cite what its canon entitles it to see
```

**Each seat returns a position on every name in the narrowed set** — not just its own picks.
This is the mandatory part, and it is what replaces the invented BEAR:

| Field | Rule |
|---|---|
| `stance` | `SUPPORT` · `OPPOSE` · `ABSTAIN` — **mandatory on every name**. A seat cannot stay silent on a name the committee is considering. |
| `conviction` | 1–5, revised. If it moved from Round 1, `conviction_change_reason` is required — naming the peer case or challenge entry that moved it. |
| `opposing_argument` | Required on every `OPPOSE`, and **also required on every `SUPPORT` at conviction ≥4**: the strongest case against your own position. High conviction must show it has looked. |
| `answers_challenge` | For each rogers entry on this name: answered-how, or conceded. |
| `what_would_make_me_wrong` | Mandatory, all stances. The falsifier, as an observable. |
| `abstain_reason` | Required on `ABSTAIN` — "outside my canon" is a valid and useful answer. |

Every claim still carries `{field, value}`. Unanchored claims are struck at validation before
the consensus rule ever sees them.

**Two seats carry a standing brief in Round 2** — both were already in the committee, and this
is where their canon is worth the most:

- **rogers — is the CROWD wrong?** Challenge already filed in S5; in Round 2 its entries are
  the thing every other seat must answer. Severity stays `note`/`flag`, never `block`.
- **steenbarger — is the COMMITTEE wrong about its own certainty?** Its canon is trading
  psychology, which makes it the natural auditor of *conviction itself*: unanimity, conviction
  inflation, attachment to a name carried from a prior day, revenge-nomination after a loss.
  It returns a `conviction_audit` alongside its normal position: per name, a flag where the
  committee's certainty looks like a psychological artefact rather than an evidentiary one.

These attack different things and both are wanted. Rogers doubts the market's agreement;
Steenbarger doubts ours.

> **Open item for the PM.** In the built system `rogers` is the designated challenge seat
> (`seat_kind: challenge`, D-97) and `steenbarger` is a nominator. Your note called Steenbarger
> the contrarian. The design above gives it a second, distinct contrarian *function* in Round 2
> while keeping it a nominator in Round 1 — which is the reading that costs nothing and loses
> nothing. If you meant to reassign the challenge seat itself, say so and it is a one-line change.

**One round only.** No iterate-to-convergence. Convergence in a debate between models is
agreement, not truth, and it costs tokens to manufacture. Positions are taken once, in view of
everything, and then the rule closes.

---

## S6b · CONSENSUS — deterministic, no agent

**No model runs here.** The verdict is arithmetic over the seats' own positions, and the
rationale is the seats' own words quoted. This is how the orchestrator stays an orchestrator.

**Verdict**

| Outcome | Rule |
|---|---|
| `PASS` | `oppose_count > support_count`, OR any `OPPOSE` argument no supporter answered |
| `ADVANCE` | `support_count ≥ 2` AND median supporter conviction ≥ 3 AND every `OPPOSE` argument answered |
| `HOLD-FOR-CONDITIONS` | everything else in the narrowed set; carries the observable that would promote it |

**Conviction** = median of supporters' revised conviction, then capped:

- cap **3** if any decisive claim rests on a `NOT_SERVED` field
- cap **3** if steenbarger's `conviction_audit` flagged this name
- cap **4** if a rogers `flag` was filed and not answered by any supporter
- cap **4** if `support_count < 3`

Caps only ever lower. Nothing raises conviction above what the seats themselves gave.

**What the record carries** — all quoted, none generated:
`verdict` · `conviction` + which cap bound it · `stance_split` (who supported, opposed,
abstained, by name) · `decisive_exchange` (the peer case or challenge entry that moved the most
convictions between rounds — computed, not judged) · `bear_case` = the strongest `OPPOSE` or
self-authored counter-argument, verbatim · `dissent` = named minority, preserved never averaged ·
`falsifiers[]` = the union of `what_would_make_me_wrong` · `data_anchors[]`.

**Portfolio view** — also arithmetic: sector/factor concentration across the ADVANCE set,
count of ideas aligned vs contradicting the Crown family, the highest-conviction name that did
NOT advance and the rule that stopped it, and the union of every `NOT_SERVED` that mattered.
Flags only. Position-level risk gates live outside PMA.

---

## Why this is cheaper

Round 2 is the **narrowed** set, so its packet collapses from ~215 KB (162 rows) to ~25 KB
(6–10 rows plus peer cases). The expensive per-name fan-out disappears entirely, and the two
purely-synthetic stages become arithmetic.

| | Retired draft | This design |
|---|---|---|
| Agent spawns | ~33 | **24** (11 + 11 + rogers + druckenmiller) |
| Ungrounded personas | 3 | **0** |
| Per-name fan-out | 2–3 agents × N names | none |
| Judge / synthesis agent | 2 | **0** — deterministic |
| Crown | verbatim relay | verbatim relay |

Round 2 costs materially less than Round 1 despite involving the same eleven seats, because
the candidate set collapsed by ~95% before it ran.

---

## The orchestrator's bias guarantee — testable, not promised

The orchestrator may **fetch, validate, slice, spawn, collect, count, cap, and render.** It may
not form a view. Enforced by one invariant S8 checks every run:

> **Every prose sentence in the plan is one of: a template string from S7, a number traced to a
> field in the day's data, or a verbatim quote attributed to a named seat.**

Nothing in the CIO output is model-generated at orchestration level. If a sentence cannot be
traced to a template, a field, or a seat, S8 fails the run. That is what makes "Alfred holds
zero independent analytical voice" an engineering property rather than an intention.

## Hard limits

No sizes, no orders, no dollar amounts, no position management. Conviction and frame-fit are
the ceiling; capital is the PM's and lives behind the existing gates. Constitution law 1 untouched.
