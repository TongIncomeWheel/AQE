# /pma — bundled copy

**The repo is the source of truth, not this folder.**
`TongIncomeWheel/AQE` @ `main` → `aegis/skills/premarket-analysis/`

SKILL.md's own rule is "fetch fresh from main every run — never a cached copy".
The files bundled here (`tools/`, `stages/`, `contracts/`) are an OFFLINE FALLBACK
only, so a run can still proceed if GitHub is unreachable. If they ever disagree
with `main`, `main` wins — and S6B_post_committee.md wins over SKILL.md.

Bundled at packaging time from `main`:
  SKILL.md                        v4.4  (S6.8 PM LENS, 9-section report, gate Q7L)
  stages/S6B_post_committee.md    v4.4
  tools/pma_pipeline.py                 (trim/packets/tally/rank/consensus/ledger/
                                         gate/record-verdicts/grade/repeat-watch)
  tools/pm_lens.py                      (PM LENS — 6 checks, blocks nothing)
  contracts/voice_menus.json
