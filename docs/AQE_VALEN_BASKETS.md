# Valen's baskets and group ETFs (PM 2026-11-17)

PM: "I'm kind of ok following Valen's baskets. Ours was not particularly well thought through during inception." The theme layer (`src/valen/themes.py`, the Valen page tables, the `themes` / `in_leading_theme` row columns, the card theme line) reads the ACTIVE basket set from `src/valen/baskets.py`.

## The data file
`data/valen_baskets.json`:
```
{"as_of": "2026-11-13", "source": "valensontrades.com Theme Baskets",
 "baskets": {"<name>": {"sector": "Growth|Commodities|Defensive|Interest Sensitive|Healthcare|Index", "constituents": ["TICK", ...]}, ...},
 "groups":  [{"ticker": "XLK", "name": "<group>", "universe": "Industry groups|Index|Segment|EW Sector|SPDR Sector"}, ...]}
```
Valid = at least 90 baskets, every basket at least 3 tickers. Anything else (file missing, unreadable, too few baskets) falls back to AQE's own 35 baskets and says so: `themes.basket_set.status = "fallback_aqe35"` with the reason, and the Valen page shows a warning. The switch is never silent. The old 35 stay in `srm.THEMATIC_BASKETS` (SRM's own sector / thematic grading is unchanged).

## What reads the active set
- the theme block (`themes.baskets`: bullish flag, sessions on/off, shares above 9/21/50/200, RS / thrust / days at 80+, reclaimed / lost, ATR, `sector`, `members`)
- the group-ETF block (`group_etfs`: per ETF its own price series; bullish, sessions on, 1M strength, thrust, days at 80+, returns; leading / fresh surge / cooling lists)
- `themes` and `in_leading_theme` on every export row, the Valen page tables, the card theme line
- `panel_builder`: Valen's constituents and group ETFs are pulled as CONTEXT (graded, never screened), exactly like the GICS ETFs and the old basket constituents.

## Cost
Only tickers not already on the panel need a first full-history FMP call (one call each, 80/min); later nights are incremental. Nightly compute is panel maths only.

## Not switched (said, not hidden)
`setups_daily.in_theme_tickers` (the U&R "group still being bought" tick) and the Rotation / Theme Leaders tables above the theme block still read AQE's 35 baskets through SRM. Moving them is a separate decision.
