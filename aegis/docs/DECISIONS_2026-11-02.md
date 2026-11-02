# DECISIONS 2026-11-02 — the two-tier funnel (R38–R41)

PM rulings from the first automated PMA pilot (Mon 2 Nov 2026, run on the Fri 30 Oct close). Verbatim where it matters.

> "No minds changed sounds like something isn't working and a waste of effort, basically everyone agreeing their own cards.
> Not purposeful to the spirit of multi round deliberation funneling towards the daily PMA goal."
> "One forced round doesn't represent a two tier funnel for me. That is essential for proper deliberation."
> "Isn't it that the new info should be voices looking at what others have tabled, and apply their lenses to it to form a
> supportive or non supportive view? Premarket and gap info adds nothing based on voices own methodology. The chair needs to
> be smarter — to trigger then cross intelligence across the voices and first funnel lost."
> "An alternative suggestion maybe is to force a multi timeframe look (weekly, daily, 1hour)."
> "Agree, implement it. Also Valen risk do not need to appear at ticket selection level."

## What the pilot showed (the evidence these rulings answer)
- 151 floor messages, 0 changed stances. 105 first-round ratification answers, 0 objections, 30 "agree with reservation".
- The slate's trigger lines carried every supporter's own words, so every seat found itself in the ticket: breadth, not convergence (QA seat).
- The one round that produced movement was the QA hold round — one forced question per ticket ("ADVANCE or WATCH, and the one
  trigger") — which split the room 4–3 on MA and TTEK and produced the run's only objections.
- The ADVANCE/WATCH call rested on a Chair counting rule whose denominator depended on who had supported.
- The two open floor waves cost ~2.4M actual tokens; the hold round ~1.4M.

## R38 — The two-tier funnel replaces the open floor
The floor is no longer "argue your case at each other". It is two tiers, each fed by NEW INFORMATION of the only kind a
fixed-method seat can act on: another seat's specific, testable claim, ruled on through its own lens.

**Tier 1 — CROSS-EXAMINATION (the first funnel).** Code (`pma_pipeline.py claims`) builds a CLAIMS BOARD from the blind
votes: per room name, the sharpest claims = the `case.for` of the two highest-conviction SUPPORT seats and the `case.against`
of the two highest-conviction OPPOSE seats (deterministic; conviction ties broken by seat order). Names with no SUPPORT vote are
out already and get no claims. Each claim is ROUTED to two reviewer seats from a different method family and, where one exists,
the opposite camp (code, round-robin, load-balanced). Each reviewer RULES on each claim routed to it — `CONFIRM`, `REFUTE` or
`CANNOT_SEE` — with the evidence its own method reads, and states its own stance on the name after ruling. Code
(`claims-score`) then applies the survival rule: a name survives tier 1 when at least one of its support claims is CONFIRMED by a
cross-lens reviewer and its support claims are not net-refuted (`confirms >= refutes`). Everything else leaves the room here,
with the refuting evidence on the record.

**Tier 2 — DECISION (the second funnel).** Code (`pair`) puts every REFUTE of a surviving claim in front of the claim's author —
the adversary pairing. Each seat files ONE tier-2 form: (a) an answer to every refutation of its own claims (quote, answer by
own method, concede or hold); (b) a DECISION on every survivor: stance, and on SUPPORT the timing `ACT_NOW` or `WAIT`, ONE
trigger (condition-vocab word + timeframe + plain words), where it is wrong, and an optional market condition that voids the
trade. Code (`decide-timing`) counts across all seven seats: fewer than 4 SUPPORT = not slated; otherwise `ACT_NOW > WAIT` =
ADVANCE, else WATCH (a tie is WATCH — "a higher win rate is better than a low win rate but bigger R"). The ticket's trigger is
the modal trigger of the winning timing camp. The slate-wide MARKET KILL line is the modal market condition.

The Chair never votes and holds no view. Its job is now to extract, route and pair (all by code, which it runs), and to write
`why_agreed` / `dissent` in the seats' own words on tickets whose verdict and trigger code has already fixed. A slate ticket
that disagrees with `decision.json` on verdict or trigger is REJECTED by the registrar.

Steenbarger's CHALLENGE (before the vote) and QA note (after ratification, one hold per ticket) are unchanged.

## R39 — Multi-timeframe is a required look, not an optional one
Every tier-1 ruling and every tier-2 trigger carries the WEEKLY / DAILY / 1-HOUR grid. The seats' own canons are
multi-timeframe (Elder's Triple Screen; O'Neil and Minervini judge the base on the weekly; Wyckoff reads structure across
frames; Raschke times on the lower frame), so this is information each voice uses by its own method — unlike premarket price,
which adds nothing to a method-bound seat. Daily-only packets are one reason nobody moved on 2 Nov: MA's daily breakout
6% extended on the weekly is exactly the fact that settles ADVANCE vs WATCH. A new step MTF (after RANK, for the room only)
pulls daily history and 1-hour bars (FMP, ~40 names) and `mtf.py` computes the grid; `r2digest --mtf` and the claims board carry
it. Missing bars are declared `MTF NOT SERVED` on that name, never a neutral reading.

## R40 — One trigger per ticket, and a market kill line
A ticket carries ONE trigger (word, timeframe, plain words), never a merge of every supporter's. A seat that disagrees with it
must OBJECT at ratification, not reserve. The slate carries one MARKET KILL line (e.g. "void if SPY closes under the 750 put
wall"); `pma_levels.py` publishes it as top-level `market_kill` so the alert loop can say "market condition broken — take no new
triggers" instead of firing buys into a broken tape.

## R41 — Valen's risk flags leave ticket selection
Valen's stance, trend and breadth remain the market weather (Part 1 of the Cards, the brief's §1A). Its no-buy list and parabolic
warnings no longer appear in the vote packet (the R37 RISK block is removed), on the cards, on the slate or in the levels file.
Selection is the seats' judgment on their own methods.

## Tool fixes shipped with this release
- `pma_cards.py triggers` builds a hold card for a HELD name on HOLD-FOR-CONDITIONS from the shared add line (29 Oct and 2 Nov
  both needed a conductor patch for V; `pma_levels.py` refused the file without it).
- `check.py chain` spend ceiling raised to 2,500,000 on the registrar's byte basis (the 1,357,500 figure predates the 7-seat,
  39-name design and tripped before FLOOR on 2 Nov). Optimisation is a later PM decision.

## Measurement (from the first run on this design)
`funnel.json` records, per run: claims issued, rulings CONFIRM / REFUTE / CANNOT_SEE, names dropped at tier 1, seats whose stance
changed on a peer's evidence, ACT_NOW vs WAIT splits. These are the numbers that say whether the funnel is working.
