---
name: voice-common
description: Shared voice engine — the identical procedure every voice skill runs with its own methodology card. Includes reserve bench rules.
---

# VOICE ENGINE (shared — one machinery, ten methodology cards)
Every voice runs this identical procedure with its own card. Voices never see each other's work (RB:committee.anti_anchoring).

INPUTS: universe_YYYY-MM-DD.json · this voice's data menu (fields it may read from the AQE working read) · methodology card · own ledger memory (its last 15 days of nominations + outcomes).
PROCEDURE:
1. Load universe. Apply the methodology card's checklist IN ORDER to shortlist candidates. Cite AQE fields read (source+date tag per read).
2. A nomination requires a framework reason in the voice's own terms — reciting a score is not analysis (constitution law 3 corollary).
3. Check own ledger memory: if a past nomination in-window has hit stop or invalidated, say so; persistence of a signal is information.
4. Held names in universe are reviewed with the same checklist; verdict per held name: KEEP / TIGHTEN / EXIT-CASE, one line.
OUTPUT: `nomination.json` per contracts/nomination.schema.json — exactly 10 nominations (fewer only if the checklist genuinely yields fewer; say why), each: ticker, one-line framework reason, key fields cited, conviction 1-5; plus held-book lines.
FORBIDDEN: seeing other voices' outputs · macro/SRM inputs pre-nomination · computing scores · nominating EVENT-DRIVEN names.

# RESERVE BENCH: DeMark, Pardo, Elder, Dalio, Murphy
Not active nominators. Elder's method is embedded in AQE (elder score). Pardo sits the unanimity-challenge rotation and chairs backtest-integrity questions in Design & Review. Activation of any reserve = decisions_log entry.
