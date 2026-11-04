# Industry-group fallback for theme strength: PROPOSAL (4 Nov 2026, not built, nothing live changes)

**Problem.** Only 54 of 260 `daily_list` rows (21%) carry `thematic_basket` / `thematic_grade`. This is by design: the 35 baskets
are a hand-curated list of 330 tickers (`src/engines/srm.py` `THEMATIC_BASKETS`); a row gets a theme only if its ticker is on the
list. There are no mapping gaps (all 54 on-list rows carry the fields). The other 206 rows are not any curated theme's member.

**Proposal.** Give every row a second, coarser tag: its **FMP industry group**, graded by the same function that grades baskets
(`srm.grade_thematic_baskets`), so every row has *a* group read. Curated baskets stay as the named themes and keep priority;
the industry group is the fallback (`theme_source: "basket" | "industry"`).

**Exact cost.**
| Item | Cost |
|---|---|
| Data | One FMP `/stable/profile` call per ticker for `industry` (`sector_mapper.py` already fetches it). `data/sector_map.json` holds 628 tickers => **628 calls, ~7.9 min at the 80 calls/min runner limit, once**. Cached in the sector-map round-trip file on Drive; afterwards only tickers new to the universe (a handful a day) are fetched. |
| Grading | **0 extra calls.** Group return (5d/20d), breadth (% above own 20-day) and RRG come from the daily panel already in memory. |
| Code | ~150 lines: industry map load/cache, group builder reusing the basket grader, three new columns, glossary + schema entries; ~12 tests (a group under 4 members is `UNGRADED`, never a grade built on 2 stocks; a name in a curated basket keeps its basket). |
| Risk | Additive columns only. `pivot_high`, `bracket`, gates, packets untouched. A failed industry pull is LOUD (`theme_status`), never an empty column. |
| Unknown until measured | The industry-size distribution on the 260-row list. FMP has roughly 140 industries; many will have under 4 members on this list and read `UNGRADED`. First pull reports the exact count of rows that get a group grade before anything reads it. |

**Columns (export only):** `theme_source`, `industry_group`, `industry_grade`, `industry_roc5`, `industry_roc20`,
`theme_leader` (member in the top quartile of 20-day return inside its basket or industry AND the group grade is DEPLOY or RRG
LEADING/IMPROVING), `theme_rank_in_group`.

**Where it would be read (each is a PM call, none is done):** (1) ordering key: already uses `thematic_grade`; would use the
industry grade when no basket; (2) a nomination door "strong name in a leading theme" = Longlist or Elder AND `theme_leader`;
(3) cards print one theme line for every name, not 21% of them.

**Decisions for the PM:** (a) build the fallback (about one session); (b) the `theme_leader` definition above, or another;
(c) whether "strong name in a leading theme" may be a nomination door or stays an ordering/reading aid.
