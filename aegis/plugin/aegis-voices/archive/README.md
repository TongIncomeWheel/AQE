# Archived seat cards (R31, PM 2026-10-30) — nothing deleted

Archived 2026-11-01, when the committee went from 15 voices to seven deciders + Steenbarger as QA.
These cards are NOT loaded as agents or skills (they sit outside `agents/` and `skills/`), so the harness
does not offer them as seats. Their canons stay under `canon/<voice>/` untouched.

| Voice | Status (PM 2026-10-30) | Why kept |
|---|---|---|
| weis, thorp | **Bench** — may be re-seated by a PM ruling | a bench seat returns with its card intact |
| rogers, lynch | Stood down | history of the challenge and fundamentals seats |
| crown, druckenmiller | Stood down as voices — the weather is read from AQE's Crown file and the Valen dashboard | the macro cards document what the Crown file replaced |
| detect-lens | Became an independent top-10 LIST (`lens_ranking.ranked[0:10]` in AQE's export), not a voice | the card carried a hand-transcribed canon that was never locked |

To re-seat a bench voice: `git mv archive/agents/voice-<v>.md agents/` and `git mv archive/skills/voice-<v> skills/`,
add it to `DECIDERS` in both `aegis-core/skills/pma/tools/pma_pipeline.py` and `registrar.py`, to RUN.yaml's
seats, and record the ruling in RULINGS.yaml. The tests will tell you what else moved.
