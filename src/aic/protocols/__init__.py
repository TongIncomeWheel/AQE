"""AIC protocols A-F (spec §11).

Each protocol is a top-level entry point that the scheduler invokes:

  A -- Pre-market brief         09:00 SGT
  B -- Candidate qualification   PM command (or fed from A's new-name list)
  C -- Position management       continuous + 03:55 SGT trail-tier sweep
  D -- Market close brief        04:00 SGT
  E -- Weekly scorecard          Friday close / Monday review
  F -- Emergency                 RED regime / stop-out breach / FMP outage

This package is intentionally functional (not class-y) -- each protocol is a
single callable + result dataclass for ease of scheduler wiring.
"""
