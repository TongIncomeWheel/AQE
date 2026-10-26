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

## PUBLISH declarations (2026-10-26)
- Pushed to TongIncomeWheel/AQE main as 27a0f09, ONLY under aegis/output/pma/ (levels full + dated copy + levels_parts 8 parts + support cards/broker_stops + scorecard/2026-10-26.md + scorecard_log.jsonl + run/2026-10-26/ with the two ledgers, the brief and run_notes). Read-back from origin/main: 18 files byte-identical (sha256), pma_levels.json parsed-JSON equal, 0 paths outside aegis/output/pma/. AQE's own _load_parts reassembled the 8 parts to 89 rows equal to the full file minus conditions.analysts.
- NOT pushed to the canonical record paths RUN.yaml PUBLISH names (aegis/reports/pma/<date>.md, aegis/reports/pma/latest.md, aegis/data/pma/{verdict,phase4}_ledger.json, data/pma/<date>/): those are outside aegis/output/** and a commit touching them rebuilds the HF Space. Ledgers, brief and run notes sit under aegis/output/pma/run/2026-10-26/ instead. Tomorrow's GATHER reads aegis/data/pma/verdict_ledger.json from main, which does not carry today's rows until the PM decides on the canonical push. PUBLISH ticked degraded for that reason.
- Card report published to the fixed artifact Q6FAPeqn2g8kvQuFja89Z3 (version 8).

## POST-RUN AMENDMENT (PM, Mon 2026-10-26 19:33 SGT): V broker stop 401.15 -> 391.80
- The PM approved a Tiger preview and confirmed it: cancelled order 45061117211970560 (STP_LMT 38 V, 401.15/401.15) and placed STP_LMT sell 38 V, stop 391.80, limit 390.80, GTC (order 45103865188585470 in the open-orders list). Nothing else changed at the broker; MP stop 36.66 unchanged.
- Levels refreshed through the run tools, no hand edit: V row of tiger_orders_raw.json updated from get_open_orders (19:35 SGT), then pma_levels.py stops, pma_cards.py triggers, pma_levels.py emit with the original arguments. Diff against the published file: broker_stop.stop/limit, keep_case, the near-stop trigger level and action on the V row, and generated_at. Nothing else moved (89 rows, 293 triggers; no verdict, rank or conviction changed). levels_parts rebuilt with make_parts.py.
- The brief and the card report were written before the amend and still show 401.15 as the run-time stop; that is the record of the run, not corrected. Pre-amend copies are kept in d26/pre_amend/.
