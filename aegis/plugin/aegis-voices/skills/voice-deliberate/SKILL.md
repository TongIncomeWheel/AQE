---
name: voice-deliberate
description: Shared floor and ratification procedure for every DECIDING voice (R36, PM 2026-10-30) — how a seat judges a case against its own method, answers a peer by name, concedes or holds, and ratifies or objects to the slate. Loaded with the seat's own card at FLOOR and RATIFY. Rounds 1 and 2 stay blind; this begins only after the blind vote is filed.
---
# VOICE-DELIBERATE — now the committee talks (the seat's half of R36)

You have filed your blind nomination and your blind vote, with the case form on every name: the case FOR, the
case AGAINST, your entry trigger, where you are wrong, your horizon in sessions, what would change your mind,
what you cannot see. Independence is kept: nothing below starts until every decider is on record.

## THE BOARD
The Chair posts, per CONTESTED name (SUPPORT and OPPOSE both present among the deciders, or named in
Steenbarger's challenge): every decider's stance and case, quoted, and Steenbarger's claim if any. Read the
board for the name before you write. You are arguing with a peer's stated case, never with a summary.

## THE FLOOR (round 3) — one file per message, `contracts/floor_message.schema.json`
1. **Answer the point that was made, by name.** `to: <voice>`, `in_reply_to: <msg_id>`. Quote the point in ten
   words or fewer, then answer it.
2. **Press with your own method's tests**, not someone else's. Your card's "Presses" block says what you ask.
3. **Concede only when the evidence YOUR method cares about appears** — on the board or in a peer's message.
   Say which evidence, by field name. Set `changed_mind: true` and write `what_moved_me`. Never concede because
   the room leans one way; never concede to a seat's conviction number.
4. **Hold when it does not appear.** Say what would change your mind — the one observable.
5. **State what you cannot see.** Do not argue a field you cannot define (your `cannot_see` list).
6. **Two messages per name, maximum.** `floor-check` counts; a third is rejected. Then stop.
7. **A bracket is never a reject** (R1) — on the floor as everywhere.
8. You may call on **Steenbarger** by name for a process question (crowding, anchors, an unanswered point).
   He answers with `stance_now: NO_VOTE`; he never votes.

## RATIFY (round 5, and round 6 after a hold) — `contracts/ratification.schema.json`
For each ticket on the Chair's slate, one answer:
- **AGREE** — the ticket says what you would say, or your dissent is already printed on it and you can live with it.
- **AGREE_WITH_RESERVATION** — name the reservation (one sentence).
- **OBJECT** — name the one thing wrong with the ticket AS WRITTEN and **the one thing that would clear it**.
  An objection that does not name what clears it is not accepted by the registrar.
Code counts the OBJECT answers (R34): none = AGREED; 1 to 3 = CONTESTED, listed with your objection printed
beside it; 4 or more of 7 = DROPPED, off the list and still tracked. You never see the count before you answer.

## THE RECORD (R35)
Every message and every answer is saved per voice per ticket (`committee_record.json`) beside your blind vote
and your stated horizon. You are graded on your blind stance AND your final stance, at YOUR horizon. After 20
runs there is a per-voice review. Changing your mind for your own method's reasons is a strength on this record;
changing it because others agreed is what the record exists to catch.

## NEVER
Change a stance because the room leans one way · invent a field or a figure not in your packet · vote on or
ratify a name you were not asked about · speak after the cap · answer a point that was not made · speak for a
seat that is silent · use a bracket, its validity, its risk% or its R:R as the reason against a name.
