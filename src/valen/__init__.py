"""VALEN Dashboard — VIV System Part 1 (Weather) ported into AQE.

Scope is deliberately narrow: the Situational Awareness card (market trend,
extension, breadth) plus group rotation (pieces 01-03 of the handbook).
Parts 2-6 of the handbook stay where AQE already implements them in its own
idiom (longlist/Elder/QS for selection, DETECT+patterns for setups,
bracket_engine for entry/management) — see docs/AQE_VALEN_DASHBOARD_PROPOSAL.md.

**AQE makes no decisions, no sizing** (CLAUDE.md). `stance` here is a market
READING, in the same category as the existing `regime` field — never a size,
size tier, or disposition. The handbook's "what I do with each answer"
sizing guidance is UI-only quoted doctrine, outside this module and outside
the export.
"""
