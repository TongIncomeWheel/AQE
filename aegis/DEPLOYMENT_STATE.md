# AEGIS CANON — DEPLOYMENT STATE

Committed 2026-08-11 from the Cowork kernel session.

## Voices: 11 of 13 grounded, locked and PM-signed

| Voice | Principles | State |
|---|---|---|
| O'Neil | 25 | locked, signed Ash |
| Wyckoff | 25 | locked, signed Ash |
| Thorp | 25 | locked, signed Ash |
| Lynch | 24 | locked, signed Ash |
| Raschke | 24 | locked, signed Ash |
| Rogers | 24 | locked, signed Ash — CHALLENGE seat, does not nominate |
| Elder lens | 24 | locked, signed Ash |
| Livermore | 22 | locked, signed Ash |
| Steenbarger | 22 | locked, signed Ash |
| Seow | 21 | locked, signed Ash |
| Minervini | 20 | locked, signed Ash |
| Detect-lens | 24 | NOT locked — hand-transcribed card, sources pending re-extraction |
| Druckenmiller | 10 | NOT locked — hand-written card, primary source pending |

## Recorded defects (disclosed, not hidden)

- **Livermore page citations are unreliable.** The source is a rotated scan with no text
  layer; three sampled quotes sat at offsets +1, +2 and -3 from their cited pages, with no
  correctable offset. The quotes themselves are genuine. PM ruled content over pages; the
  waiver is recorded in `canon/sources.yaml`.
- **Steenbarger quote fidelity was sampled, not assumed.** 4 of 5 verbatim; 1 compression
  found and corrected. Residual rate across all 334 records unknown. Every citation is a
  live permanent URL, so verification is one click.
- **Steenbarger's 2003 book set aside** (`status: not_usable`): scanned image, no text layer,
  and its only extractable text identifies it as a shadow-library scan. The seat is grounded
  instead in the author's own freely published blog corpus (`rights: author_public`).

## Architecture

Two plugins, split on the knowledge/process seam, cut from one build by
`packaging/split_plugins.py` and stamped with the same `kernel_build`:

- **aegis-voices** (knowledge) — 13 voice agents, 14 skills incl. `voice-common`, the
  nomination contract, `canon_validate.py`. No loops, no order path.
- **aegis-core** (process) — loops, desks, `committee-desk`, `staging-gatekeeper`, tooling.

The morning is two commands: `/premarket` (deterministic data prep, cron-able, no voices)
then `/committee-pm` (the judgement half, hard-gated on premarket's stamp).
