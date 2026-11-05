# SWING_PIVOT dry-run on the 5 Nov data (rank --cap 24 --door-budget 8, tally.json and candidate_set.json of run 2026-11-05)

Dry-run only: the export fields come from the 395-name universe scan (momentum_universe.md), not a nightly. Nothing here changes run 2026-11-05.

- Baseline (`--swing-seats 0`): 46 names in the room, identical to the committed run phase4.json.
- With `--swing-seats 6`: 52 names in the room. Pool = 20 names with swing_pivot true.
- Added (SWING_PIVOT, MOMENTUM lane, by AQE rank): ADP (#16, -0.8 ATR), AFL (#19, +1.0 ATR), LTH (#28, +0.0 ATR), SONY (#92, -0.7 ATR), LLY (#122, -0.7 ATR), EL (#125, +0.8 ATR)
- Removed: none. Nominations, the held book, R25 U&R seats and R27 strength seats are unchanged.

Files: phase4_baseline_no_swing.json, phase4_swing.json.
