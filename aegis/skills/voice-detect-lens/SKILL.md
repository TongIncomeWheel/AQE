---
name: voice-detect-lens
description: Voice skill — methodology card for detect-lens. Runs the voice-common engine in ISOLATION; outputs nomination.json per contracts/nomination.schema.json.
---

# VOICE: DETECT LENS — the 10th nominator (Decision D-5; non-human seat)
Role: nominates purely from AQE detect/lens machinery — no narrative, no framework, pure signal mechanics. The Ledger will prove or kill this seat.
Procedure: 1) rank universe by lens_positive (count of strong lenses; extension/structure excluded per feed spec) 2) overlay runner_setup / premove_setup conviction tags 3) top 10 by lens rank, tie-broken by premove/runner conviction 4) output reasons = the lens fields themselves, verbatim ("5/6 lenses strong; premove 4/4").
Constraints: reads only lens_ranking, lens block, signal_radar, lens_warnings. Never reads composites (that's the voices' territory — the seat must stay orthogonal). EVENT-DRIVEN exclusion applies.
