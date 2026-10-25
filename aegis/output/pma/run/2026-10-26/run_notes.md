- Checkpoint pushes (MACRO, NOMINATE, CHALLENGE, VOTE, WRITE): NOT done mid-run. git_sync.py maps its --paths to the aegis/ root of the repo, outside aegis/output/pma/, and any other path redeploys the HF Space. Work stays on local disk until PUBLISH pushes under aegis/output/pma/ only. Declared.
- Seats read their card and packet by path (voice agent types have no file tools). Cards at /mnt/skills/plugin-files/aegis-voices~g2/agents/.
- Plugin used: aegis-core v1.30.0 (synced copy); prior working copy was v1.29 (no R28/R29) and was replaced.

## CHALLENGE declarations (2026-10-26)
- Fundamentals: 38 names carried unchanged from the d23 pack; 43 names pulled fresh from FMP by the conductor on 2026-10-26 (profile, metrics-ratios-ttm, income-statement-growth x3 annual) because the data-steward agent has no tools. Pack 81/81. CNQ growth is reported in CAD; ratios are unitless. Figures are FMP as served (e.g. DXC FCF yield, VG revenue growth look extreme; not adjusted).
- figure_audit finds "NO auditable field claims" on challenge forms (it reads ballot-shaped forms; challenge seats cite figures in findings[].evidence). Not a clean bill. Compensating check by the conductor (read-only, not part of the pipeline): every decimal in findings[].evidence traced to the seat's own packet -- rogers 81/81, steenbarger 51/51, detect-lens 40/40 traced, 0 untraceable. Challenge forms committed with `registrar commit --step CHALLENGE --seat <seat>` (d23 precedent; registrar validate has no challenge mode).
- VOTE ballots: 51 names, split into 3 parts of 17 (R16.1), `--of 3`.
- Lynch (consulted): 51 verdicts, 349 decimals traced; 346 trace to the packet, 3 do not and are legitimate: BBY "implied payout 0.64" (= priceToEarningsRatioTTM x dividendYieldTTM = 0.636, labelled implied), V "PEG proxy 1.9 to 7.0" (= P/E over growthEPS x100 = 7.03/1.98/1.90, labelled proxy), MP broker stop 36.66 (real, from broker_stops.json, given in the seat prompt). Lynch declares forward growth, net cash, inventory vs sales, ownership unserved.

## VOTE declarations (2026-10-26)
- VOTE_PACKET.txt is 133,075 bytes (md5 116e812ae52f652b9a7b68fcb66dc782), over r2digest's 70,000-byte soft limit. d23's 38-name packet was 99,599 bytes and also over; per-name density is unchanged (2.6 KB/name). Not trimmed: the analysts' findings and Lynch's 51 reads reach every voting seat whole. Seats read the packet by path (v1.30 transport), not pasted (R2 text predates this).
- 10 voters spawned in parallel as general-purpose agents from d26/prompts/vote_<seat>.txt; ballots are 3 parts of 17 names.

## SCORECARD declarations (2026-10-26)
- Graded as of 2026-10-23 close, horizon 5, beta cap 2.5, six runs (10-15, 10-19, 10-20, 10-21, 10-22, 10-23). 738 rows graded, 0 refused on the 0.5% ref-price check. 263 not graded: 233 are today's own run (2026-10-26, no session after it yet), 27 are the 2026-08-31 run (no window), 3 are ACA.
- Closes: base file from AQE main (519 tickers through 10-22) plus the 10-23 close for 301 names from today's export `last_close`, and the 10-22 close from d23's export where missing (none needed). 186 further tickers (42 for 10-22, 179 for 10-23) were pulled from FMP `historical-price-eod-light` by the conductor and typed in by hand into sc/fetched.json. Cross-check: where an export value and an FMP value both existed they agreed within 0.2% (0 mismatches). Biggest one-day move in the set is RHI +21.7% (37.68 to 45.87), confirmed directly at FMP.
- ACA: FMP returned no data for 10-23. It drops out of the 10-21, 10-22 and 10-23 list means (universe 326/327, 276/277, 372/373). Declared, not filled.
- scorecard_log.jsonl seeded from AQE main (origin/main == local HEAD 9aa00ee, 10 lines); the 10-23 line is new (11 lines).

## WRITE/CHECK declarations (2026-10-26)
- WRITE was metered twice (first without a token count, then again with the exact 180,627 subagent tokens); the status line therefore shows WRITE spawns=2 and total spawns 27. The true count is ONE writer spawn, 26 model spawns in the run. Not hand-edited (the manifest is the registrar's).
- The card report's fixed wording (entry labels 'Hourly close above', 'First target', the Valen no-buy note, and the word 'stretched' in the Valen INDEX extension table) is code-rendered by pma_cards.py and cannot follow the plain-English rules. It is a code change for the maintainers; 'stretched' there describes the index extension flag, not any momentum name. Declared in the brief header and caveats.
- CHECK gate: 0 FAIL.

## LEVELS declarations (2026-10-26)
- pma_levels.py emit --window 3 with the dated files for 2026-10-23 and 2026-10-22 from AQE main as --history (origin/main == local HEAD 9aa00ee at fetch time) and --closes from the 10-23 closes. 89 rows: ADVANCE 20 (9 fresh + 11 carried), HELD 2, HOLD_FOR_CONDITIONS 57, WATCH 10; 39 carried, 44 retired. Not yet structured (AQE skips): COST, CTAS, FRSH, EW (COST is today's HOLD with no resolved buy level; the other three are carried).
