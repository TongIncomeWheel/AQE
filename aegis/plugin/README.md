# aegis plugin source (v5.3, 2026-09-05)

This directory IS the source of truth for the two installed Cowork plugins, `aegis-core` and `aegis-voices`.

Why it exists: on 2026-09-05 the installed plugin was found to have drifted from `aegis/skills/` — the `premarket`, `ptj`
and `committee-pm` cards that actually run had been edited after being derived from repo files and never committed back
(111 and 432 lines of difference). `packaging/build_claude.py` builds an older `aegis-v4` layout and cannot reproduce the
installed plugin. So the installed trees were copied in here verbatim, patched for v5.3, and committed.

Rules:
- Edit HERE. Then `python3 aegis/plugin/build.py` zips `aegis-core.plugin` and `aegis-voices.plugin` into `dist/`.
- `aegis-core/skills/pma/` mirrors `aegis/skills/premarket-analysis/` (card, tools, contracts, brief-writer). Keep them
  identical — `build.py` copies premarket-analysis in before zipping, so premarket-analysis stays the editable original.
- Voice cards under `aegis-voices/agents/` are the only copy. There is no `skills/voice-*/` equivalent for the agents.

v5.3 changes carried here: snapshot-every-tick, verified-read seat spawn (general-purpose + MD5 + line-N), two-wave vote,
four admission doors (SEATS / ELDER+LENS / PM_LENS / AQE_LEADER, cap 30, one-seat exception closed), tool-built Round-2
digest (`pma_pipeline.py r2digest`), executive-form brief (brief-writer v5.3 + gate QX1–QX4), preflight PAT optional,
connector push path documented, bracket-reject lines deleted from oneil/raschke/wyckoff, Livermore sma_distance misread fixed.
