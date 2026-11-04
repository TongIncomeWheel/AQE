---
name: aegis-writing
description: "House writing standard for every sentence the Aegis system shows the PM: Cards text, briefs, alert cards, committee rationales, and conductor/desk/engineering replies. Use whenever you write or edit text a person will read. Read before writing a line; cio-voice says what a report must do, this says how each sentence is built."
---

<!-- Credit: adapted from the institutional-copywriting skill (MIT licence, David Wang,
     github.com/davidwang95/institutional-copywriting-skill). This text is a rewrite for Aegis,
     not a copy; the upstream licence applies to the ideas and eval design borrowed from it. -->

# Aegis writing standard

Reader: a PM who trades US equities from Singapore, reads fast, and will act on a sentence. Make each claim easy to inspect. Plain words, measured tone, no promotion, no padding.

## 1. Fidelity first (hard gate)
Keep, beside the claim they limit: numbers, units, periods, signs, comparison bases, as-of dates, attribution, and whether something is observed, estimated, forecast, assumed or conditional. Never upgrade "may" to "will", a target to a forecast, an analyst inference to a fact. Keep adverse evidence in view. If a fact is missing or sources conflict, say so; never invent a number, quote, reason or source. A short sentence that misleads is a failed edit.

## 2. Lead with the supported conclusion
Answer first: what is true, what it changes, what is needed from the PM. Then evidence, then the limit. Headings and titles state the point and must be no broader or more causal than the body. Say what would change the assessment only when the data supports a test.

## 3. Every figure carries its comparison
"+1.1% vs SPY over 5 sessions", not "+1.1%". Percent vs percentage points vs basis points kept distinct. Distances state direction from the sign (above/below), never a fixed word. Chart: legend names every line.

## 4. Plain sentences
- One idea per sentence; split at a change of claim. Two lines per paragraph at most.
- Concrete verbs: "assess", not "conduct an assessment of".
- One term per concept. No raw field names, rule codes (C5, R34), seat names, vote tallies or indicator jargon on a PM page (daily range, not ATR; momentum, not RSI). Technical terms only when the PM uses them.
- Cut ceremonial openings, "it is important to note", vague praise, empty significance, stock metaphors, forced contrasts, repeated summaries, closing calls to action.
- Keep justified hedges. Do not strip a word because it sounds like AI; strip it only if it weakens the passage.

## 5. Separate what is measured, what is explained, what is advised
Measured result / proposed explanation / implication / recommendation are four different things. An association cannot carry a causal title. A PM decision is asked once, with the options and a recommendation, in the last lines.

## 6. Ownership and honesty
State outcomes as verified or not verified, with what was checked. Say what is not done and why. Own errors plainly in one line (what was wrong, what changed). Do not present an inherited default as the PM's rule.

## 7. Check before sending
Claim-by-claim against the source: figures, signs, periods, attribution, qualifiers, adverse evidence. Read titles alone for overstatement. Read the first lines alone: do they give the point and the ask? Then cadence.

Mechanical backstop already in code: `check.py cards` (raw tokens, jargon, number cap). This skill is the semantic layer above it.

## 8. Evals (hard gates)
`skills/aegis-writing/evals/cases.json` holds five cases taken from real slop of 2026-11-03/04, each with the bad text, an acceptable rewrite and the literals that must / must not appear. **Fidelity** (required literals: the figure, sign, base and date survive) and **uncertainty** (the hedge survives) are hard gates: a draft that fails either is rejected whatever its style. `python3 skills/aegis-writing/evals/run_evals.py` proves the harness separates the bad from the good; `--case ID --file draft.txt` grades a new draft.

Where it is wired: `cio-voice` (section 0), `agents/brief-writer.md`, `agents/chair.md`, the WRITE step in `RUN.yaml`, and the comments of the alert card text builders.
