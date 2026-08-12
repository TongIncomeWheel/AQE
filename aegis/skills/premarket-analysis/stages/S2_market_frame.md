# S2 — MARKET FRAME · ONE macro read, no competing numbers

**PM ruling 2026-08-12: harmonise the macro and the Nick Crown read into one. No conflicting
figures.** The 2026-08-12 run put VIX 18.7 (from the stock scan's regime block) and VIX 15.28
(from Crown, same day) on the same page, and derived the day's momentum verdict from the stale
one. All eleven seats flagged it. **A frame that carries two values for the same quantity is not
a frame — it is two frames stapled together.**

---

## The precedence rule

There is **one** macro read. Where two sources describe the same quantity, one wins, always, by
rule — never by whichever was read last.

| Quantity | Authority | Why |
|---|---|---|
| **Volatility (VIX)** | **Crown** | Crown is the macro layer and is refreshed daily; the scan's regime block is a by-product of a stock scan |
| **Breadth** | **Crown** | Crown measures it directly (equal-weight vs cap-weight); the scan has only a proxy |
| **Volatility regime / state** | **Crown** | Level *and* direction; the scan carries level only |
| **Positioning, dealer flows, cross-asset levels** | **Crown** | The scan has no equivalent |
| **Trend character (Hurst), risk tone** | **Scan** | Crown does not compute these |
| **Sector grades, rotation, entry gates** | **Scan** | Crown does not compute these |
| **Per-name anything** | **Scan** | Crown never names a ticker |

**The losing value is not shown.** It is not printed in a second column, not footnoted as "the
scan also says". It goes into `market_frame.superseded[]` — visible in the JSON for audit,
absent from every packet and every page. A voice cannot cite a number it never receives.

## The two hard rules that follow

**1 · Every derived verdict is computed from the winning source.**
The momentum caveat is the case that broke: it was computed from the scan's VIX. Under this
rule it is computed from Crown's. If Crown is absent, the caveat is computed from the scan
**and labelled with the scan's own date** — never presented as today's read.

**2 · Disagreement is a data-quality finding, not a display problem.**
When the two sources materially differ on a quantity where one supersedes the other, that gap is
itself a signal about staleness. Record it:

```json
"reconciliation": [
  {"quantity":"vix","authority":"crown","authority_value":15.28,
   "superseded_source":"export.regime.vix","superseded_value":18.7,
   "delta_pct":-18.3,"as_of_gap_trading_days":11,"flag":"MATERIAL"}
]
```
`MATERIAL` = the two differ by more than 10%. Every MATERIAL entry appears in the report's
data-confidence table as one line: *"Volatility: using today's 15.28. The 28 July scan said 18.7
— 18% higher — and that figure has been discarded."* One number on the page; the discard is
disclosed, not displayed as an alternative.

---

## What S2 produces

`data/pma/<date>/market_frame.json`:

- `risk_tone` · `trend_character` — from the scan, labelled with the scan's date
- `volatility` · `breadth` · `positioning` · `key_levels` — from Crown
- `regime_verdict` — the plain-English caveat, computed from the **winning** sources, stating
  which source and which as-of date it used
- `sectors[]` — from the scan
- `crown_call` — expression family, size multiplier, match quality, conditions met/not met
- `reconciliation[]` — every superseded quantity, as above
- `superseded[]` — the discarded values, for audit only
- `declared_gaps[]` — absent or degraded inputs, named

**Every value carries its source path and its as-of date.** A number without both does not enter
the frame. This is what makes "one macro read" enforceable rather than aspirational: a reader
can always ask *which file and which day did this come from*, and the frame answers.
