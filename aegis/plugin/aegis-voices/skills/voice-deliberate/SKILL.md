---
name: voice-deliberate
description: Shared deliberation procedure for every DECIDING voice (R36, rebuilt for the two-tier funnel R38–R40, PM 2026-11-02) — how a seat rules on a peer's claim through its own lens on the weekly / daily / 1-hour grid (tier 1), answers its refuter and decides every survivor with ONE trigger (tier 2), and ratifies or objects to the slate. Loaded with the seat's own card at CROSS, TIER2 and RATIFY. Rounds 1 and 2 stay blind; this begins only after the blind vote is filed.
---
# VOICE-DELIBERATE — the two-tier funnel (the seat's half of R38)

You have filed your blind nomination and your blind vote, with the case form on every name: the case FOR, the
case AGAINST, your entry trigger, where you are wrong, your horizon in sessions, what would change your mind,
what you cannot see. Independence is kept: nothing below starts until every decider is on record.

**Why it changed (PM 2026-11-02).** The open floor of 2 Nov carried 151 messages and changed 0 stances; 105
ratification answers raised 0 objections. Everyone agreed with their own card. The PM: *"the new info should be
voices looking at what others have tabled, and apply their lenses to it to form a supportive or non supportive
view."* So you no longer argue your case at the room. You rule on someone else's claim, with your own method,
and then you decide.

## THE CLAIMS BOARD
Code builds it from the blind votes (`pma_pipeline.py claims`), not the Chair and not a seat. Per room name: the
`case.for` of the two highest-conviction SUPPORT seats and the `case.against` of the two highest-conviction
OPPOSE seats. A name with no SUPPORT vote is out already and gets no claims. Each claim is routed to two
reviewers from a **different method family** and, where one exists, **the opposite camp**. Your packet
(`claims_packets/<you>.json`) holds exactly the claims routed to you, each with the name's row and its **MTF
grid** — W / D / H1: close vs EMA9 and EMA21, EMA order, the last bar's colour, higher highs / higher lows over
three bars, distance to the 20-bar high, and on H1 where the close sits in the day's range. You never see the
author's stance count or another reviewer's ruling.

A frame marked `MTF NOT SERVED` is not a neutral reading. You cannot see it; say so.

## TIER 1 — CROSS-EXAMINATION (one form, `contracts/cross_ruling.schema.json`)
For **every** claim routed to you, one ruling:
- **CONFIRM** — your method sees the same thing. Name the fields and values that show it.
- **REFUTE** — your method sees the opposite, or the claim fails your test. Name the fields and values.
- **CANNOT_SEE** — your method has no test for this claim, or the field it needs is not served. Say which.

How to rule:
1. **Through your own lens, on the grid.** Fill `tf` for W, D and H1 — what YOUR method reads on each frame for
   this claim (≤ 90 characters each), or `not served`. Elder reads the weekly tide before the daily wave; O'Neil
   and Minervini judge the base on the weekly; Wyckoff reads structure across frames; Raschke times on the lower
   frame. Use the frames your canon uses, and say what each one shows.
2. **Never restate your own case.** The claim is someone else's. Your blind vote is already on the record; this
   form is about whether THEIR claim survives YOUR test.
3. **Concede only on evidence your method cares about.** A daily breakout 6% extended on the weekly is evidence
   to a base-reader; it may be nothing to an impulse seat. Do not confirm because the claim is well written, and
   do not refute because the room leans the other way.
4. **`stance_after`** — your own stance on the NAME after ruling (SUPPORT / OPPOSE / ABSTAIN). If it differs
   from your blind vote, set `changed_mind: true` and write `what_moved_me` by field name. A stance that moved on
   a peer's evidence is the funnel working; a stance that moved on nothing is what the record exists to catch.
5. **A bracket is never a reason** (R1) — its existence, its validity, its risk % or its R:R.

Code (`claims-score`) then applies the survival rule: a name survives when at least one of its support claims is
CONFIRMED by a cross-lens reviewer and its support claims are not net-refuted (confirms ≥ refutes). Everything
else leaves the room here, with the refuting evidence on the record. You do not count; you rule.

## TIER 2 — DECISION (one form, `contracts/tier2.schema.json`)
Your packet (`tier2_packets/<you>.json`) holds the refutations of YOUR claims (the adversary pairing, `pair`) and
the full survivor list with each name's grid and its tier-1 tallies (how many confirmed and refuted, never who).

**(a) Answer your refuter** — one `answers[]` entry per pair where you are the author. Quote the refuter's point
in **ten words or fewer**, then answer with **your method's test** on the grid. `concede: true` when the
refuter's evidence is evidence your method cares about and it stands. One answer; no replies to replies — the
pairing is the exchange.

**(b) Decide every survivor** — one `decisions[]` entry per survivor, every survivor exactly once:
- `stance` — SUPPORT, OPPOSE or ABSTAIN.
- On SUPPORT, `timing`: **ACT_NOW** (act on the trigger from today's session) or **WAIT** (a condition must print
  first — a pull-in, a pause, volume — and the trigger follows it).
- On SUPPORT, **ONE trigger**: `word` is a condition-vocab word with a FIELD level, written `word:field_level`
  (`h1_close_above:bar_high`, `close_above:pivot_high`, `in_zone:ma_20`) — never a typed number; `tf` is the
  frame it is read on (W / D / H1); `plain` says it in plain words. One trigger, not a list. The PM acts on one.
- `wrong_if` — where you are wrong, in one line.
- `market_void` (optional) — the market condition that voids the trade, in words the alert loop can watch
  ("SPY close_below put wall 750"). Null when your method has none. Never invent one to fill the field.

Code (`decide-timing`) counts across all seven seats: fewer than 4 SUPPORT is not slated; otherwise ACT_NOW >
WAIT is ADVANCE, else WATCH — a tie is WATCH (*"a higher win rate is better than a low win rate but bigger R"*).
The ticket's trigger is the modal trigger of the winning timing camp; the slate-wide market kill line is the
modal `market_void`. You never see the count before you file.

## RATIFY (and the re-ratification after a QA hold) — `contracts/ratification.schema.json`
The Chair's slate copies each ticket's verdict and ONE trigger from `decision.json`. For each ticket, one answer:
- **AGREE** — the ticket says what you would act on, or your dissent is printed on it and you can live with it.
- **AGREE_WITH_RESERVATION** — name the reservation, one sentence. A reservation is about the ticket's words or
  its horizon, never about its trigger.
- **OBJECT** — name the one thing wrong with the ticket AS WRITTEN and **the one thing that would clear it**.
  **A trigger you disagree with is an OBJECT, not a reservation** (R40). On 2 Nov thirty "agree with reservation"
  answers carried real disagreement that counted for nothing; that is the failure this rule closes.
Code counts the OBJECT answers (R34): none = AGREED; 1 to 3 = CONTESTED, listed with your objection printed
beside it; 4 or more of 7 = DROPPED, off the list and still tracked. Steenbarger may then hold one ticket; the
hold round is one floor message per decider on that ticket (`forms/floor2/`) and one re-ratification.

## THE RECORD (R35)
Every ruling, answer, decision and ratification is saved per voice per ticket (`committee_record.json`) beside
your blind vote and your stated horizon, and `funnel.json` records the claims issued, the rulings by kind, the
names dropped at tier 1, the seats whose stance changed on a peer's evidence, and the ACT_NOW / WAIT splits. You
are graded on your blind stance AND your final stance, at YOUR horizon. Changing your mind for your own method's
reasons is a strength on this record; changing it because others agreed is what the record exists to catch.

## NEVER
Change a stance because the room leans one way · confirm or refute on a method that is not yours · restate your
own case in a ruling · invent a field, a figure or a level not in your packet · rule on your own claim · file more
than one trigger on a ticket · reserve on a trigger you would object to · vote on or ratify a name you were not
asked about · use a bracket, its validity, its risk % or its R:R as the reason against a name · cite Valen's
no-buy or parabolic flags as a reason (R41: selection is your judgment on your own method).
