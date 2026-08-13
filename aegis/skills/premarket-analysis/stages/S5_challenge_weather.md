# S5 — CHALLENGE + WEATHER (judgment · 2 agents + 1 verbatim relay)

Runs strictly AFTER the tally. Both functions are reactive by construction: they respond to
what the swarm produced and are structurally incapable of having steered it (D-4 weather-never-gates;
D-97 challenge-sees-tally).

---

## S5a · ROGERS — the challenge seat

One isolated agent. Input: its card + **the tally** (every deliberation-set name with its
nomination_count, the seats that nominated it and their convictions) + the universe rows for
those names. That tally block is the seat's entire input and it must actually be passed —
unwired, the seat has nothing to stand on and its own card instructs it to file one line
saying so, which is an honest failure and a finding about this stage, not a seat shortfall.

Returns `challenge.json` — entries on three axes:

- **CROWDING** — the consensus ratio. A name every seat loves is evidence about the seats,
  never about the asset.
- **CERTAINTY** — unanimity or any conviction-5 draws a mandatory challenge. An unfound flaw
  is a finding ("looked, found nothing"), not a pass.
- **TIMING** — extended, volume-spiked, late in the move.

Plus a standing **Catalyst Check** on any name carried as cheap, neglected or sold-off: name
the catalyst that forces recognition, or record `NO_CATALYST_NAMED`.

**Severity is `note` or `flag`, NEVER `block`.** A challenge removes nothing, advances nothing
and changes no tier. It travels verbatim into S6's bear packet and onto the plan line where it
fired. The seat is barred from arguing against a stop, bracket or gate — its canon objects to
them and its canon loses to house law there. A challenge entry that does so is discarded for
that entry and the fact is noted, not silently dropped.

---

## S5b · CROWN — the NOW read (verbatim relay, not an agent)

**No model runs here.** AQE already computed and wrote the reading — headline, reasons with
numbers, the call, what would change it. Re-generating that with an LLM adds hallucination
risk and nothing else. S5b copies from `aegis/output/aqe_crown_macro.json`:

`read_me_first` (all four blocks verbatim) · `the_call` (expression_family, match_quality,
size_multiplier, conditions_met/not_met) · `status` + `limits[]` · nearest `key_levels`.

If `crown_absent`, the block says exactly that and the plan's headline carries it.

Crown is the one seat whose voice is a file. Its multiplier rides as context; it sizes nothing.

---

## S5c · DRUCKENMILLER — the NEXT read (one isolated agent)

Input: its card + its now-grounded canon (27 principles, NMW pp.229–256; the three
`pm_override` principles may NOT be used to argue against house risk law) + the GLOBAL blocks
(`regime`, `intermarket`, `macro_weather`, `srm[]`, `thematic_baskets`).

Returns the standing macro brief per its card's checklist: regime first with the momentum
caveat stated plainly; cross-asset (dollar/bonds/credit/commodities) each with its number;
rotation from the RRG blocks; breadth honestly labelled a proxy — never a literal
advance-decline line, which does not exist here; and a sizing **tone** (aggressive/normal/light),
never a number.

**Mandatory:** an explicit `crown_agreement {agrees_on[], differs_on[]}`. The PM reads the pair
back to back and the disagreement is the information.

---

## The pairing (PM ruling 2026-08-11)

**Crown = NOW** (positioning, breadth, dealer flows, vol structure as they stand).
**Druckenmiller = NEXT** (the 18-month lean).

Read consecutively in the plan, never merged into a single "macro view". When they conflict,
the conflict is surfaced — two stories fitting one tape is contested, not a call.

**Output:** `challenge.json` + `weather.json`. Neither gates anything.
