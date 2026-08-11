# /premarket-analysis — design decisions, asked and answered in plain English

**For PM review, 2026-08-12 morning. Every question below is one I would otherwise have had
to ask you. Each has my recommended answer baked into the v0.1 build — overrule any of them
and the change is cheap NOW, expensive after a month of daily runs.**

---

**Q1. Is this a new thing or a rebuild of the existing /premarket?**
New, separate, analysis-only. The existing `/premarket` does the plumbing day-job — broker
pulls, book close, stops, dynCap, git pushes. Bolting the new frame onto it would tangle
"what should we do today" with "is the machinery on". **Recommended: keep them separate; the
old skill keeps the data duties, PMA is the thinking. When PMA is proven, `/committee-pm`
retires into it.** That last step is your call, later.

**Q2. Where does the data come from?**
Google Drive, the AQE folder — both files (`aqe_daily_export.json` + `aqe_crown_macro.json`).
Reason: it already works today with zero AQE-side changes, and AQE overwrites in place there
every run. GitHub stays the home for contracts, canon, and audit artifacts (the things that
must survive resets and be diffable). This is the hybrid from the bridge plan — the daily
2.6 MB payload would bloat git history for no benefit.

**Q3. How do voices get their data?**
A JSON packet per voice: the market frame (same for everyone), the candidate set (same for
everyone, deliberately un-ordered), that voice's own field menu, and its own memory/lessons.
Nothing else. The voice answers in JSON (`nomination.json`, the existing contract — reused,
not reinvented). **The packet is the entire interface** — a voice cannot see the tally,
another voice, or the plan. That isolation is what makes ten opinions worth having.

**Q4. Do all voices run every day?**
All 10 nominators, yes — an empty chair tells you nothing and the ledger needs daily samples
to prove or kill seats. Rogers (challenge) and Crown+Druckenmiller (weather) always run
AFTER the tally. Cost control comes from packet discipline (voices get distilled JSON, not
the 2.6 MB export), not from benching seats.

**Q5. What happens when the Crown file is missing or degraded?**
Missing → the run continues AQE-only and the plan's first line says so. Degraded → the plan
carries Crown's own `limits[]` verbatim. **Never silently skipped, never silently trusted.**
Same doctrine for every input: a gap is a declared fact in the plan, not an excuse to stop
(unless the main export itself is bad — then there is no honest plan to write, and we stop).

**Q6. Why is Crown relayed verbatim instead of run as an LLM voice?**
Because AQE already computed and WROTE the reading — headline, reasons with numbers, the
call, what would change it. Re-generating that with a model adds hallucination risk and
nothing else. Crown is the one seat whose "voice" is a file. Druckenmiller stays an LLM voice
because forecasting the NEXT 18 months genuinely needs judgment over the global blocks.

**Q7. Ticker-level and held-book analysis?**
Out, per your instruction. One exception: candidates are TAGGED if already held, so no voice
"discovers" a name the book owns. Position-level work (exits, trims, stops) stays in the
existing machinery until you pull it in.

**Q8. What exactly does the PM get?**
One page, fixed order, phone-first: headline (day type + data quality) → weather pair (Crown
NOW / Druck NEXT) → actionable ideas with the numbers that justify them and a bear case each
→ watch table → key levels with "if it breaks" → what would change the plan → declared gaps.
Always ends `DRAFT — PM approval required`. Nothing stages, nothing arms. Silence never trades.

**Q9. Sizes on the ideas?**
No. v0.1 emits conviction and family-fit, not capital. Crown's multiplier rides as context.
Wiring dynCap/1R sizing back in is a one-stage addition AFTER you've approved how ideas are
generated — sizing a pipeline you haven't trusted yet is backwards.

**Q10. How does it learn?**
S8 writes a run audit every day: what each voice asked for vs what the feed served, seats
that failed, claims that didn't trace back to real data. A week of those audits turns "what
data does the committee need from AQE?" into a measurement instead of a workshop — it feeds
the requirements register and the AQE change request directly. Post-market scoring against
realized prices (d1/d3/d5/d10/d15 via the existing ledger) is the named next extension.

**Q11. What stops a voice or the desk inventing numbers?**
Three layers: packets contain only served fields; the tally stamps `field_values` by
dictionary lookup (not by the model); S8 spot-checks every ADVANCE's anchors against the
day's actual inputs and flags any that don't resolve. An idea that can't show its numbers
doesn't reach the plan.

**Q12. When does it run, and what triggers it?**
On demand via `/premarket-analysis` for now. Scheduling (after AQE's export lands, before
your morning) is a one-line addition once you've reviewed a few manual runs. Crawl first.

---

*Everything above is v0.1 and reversible. The one thing I'd resist reversing: JSON bridges
between every stage. That's what makes any morning's run inspectable six weeks later.*
