# Handover: PMA fixes from the 23 Oct run

Repo: TongIncomeWheel/AQE `main`. Plugin: `aegis-core` v5.4. Scripts written during this run are in `data/pma/2026-10-23/tools/`.

## 1. Valen in the PMA (PM ask, 23 Oct): make it permanent

**PM:** "In the PMA there is very little of Valen data available... I want to see it take space in the report."

**Done this run (by hand):**
- GATHER copied `aegis/output/aqe_valen_dashboard.json`.
- `valen_section.json` was condensed from it: stance, trend, extension, breadth, history, gamma, cockpit, themes, house setups, entries and the no-buy list.
- A VALEN block was appended to `VOTE_PACKET.txt`. It holds market weather plus, for each name, the house setup status with checks passed, U&R status and note, and any no-buy flags. Pivot and stop levels were left out under R1. Script: `valen_block.py`.
- The brief gained a new §1A "VALEN: market weather and setups". The §0 table gained two columns, "Valen setup" and "U&R", and a no-buy flag (⛔).

**Plugin changes to make it standard:**
- **RUN.yaml**
  - GATHER: add `aqe_valen_dashboard.json` to `produces`.
  - WRITE: add `"1A valen"` to `sections`.
- **pma_pipeline.py r2digest:** add a `--valen` argument that appends the block. Port `valen_block.py`, keeping the rule that levels are never passed.
- **agents/brief-writer.md:** add the §1A spec and the two §0 columns. Use the write prompt (`prompts/write.txt`, PM instruction 1) as the spec.
- **voice_menus.json** (PM sign-off needed): should seats see `setups` / `unr_status` in their round-1 packets? Today they only saw them at the vote.

## 2. `trim` injects the held cost as `entry` on an injected held row
- MP's universe row carried `entry 53.0`, which is the cost basis, where it should carry the last close, 38.56. Three seats flagged it.
- Fix: in `cmd_trim`, set `entry` from `held_book.live_px` (or the export `last_close`) and keep the cost under `held_book.entry`.

## 3. `cards.json` has no producer tool
- LEVELS needs `cards.json`. This run built it with `build_cards.py` from `conditions.json`. The rules:
  - shared hourly-close buy = ACTION;
  - in_zone/reclaim = dip WARN;
  - yesterday's intraday high = touch;
  - the wait zone top;
  - dead = the exit with the most seats, highest value on a tie.
  - No shared buy: fall back to the supporters' own buys, labelled "not shared".
  - Held + ADVANCE: carry the add triggers, and set `committee_exit` only if it is at or above the broker stop.
- Move this into `pma_levels.py cards` so WRITE stops hand-building triggers.

## 4. Challenge packets have no producer tool
- `build_challenge.py` built them: the tally plus menu-sliced rows, plus fundamentals for lynch. Add `pma_pipeline.py challenge-packets`.

## 5. Fundamentals print in the vote packet (handover 21 Oct item 6): fixed in practice
- The pack now carries flat keys (`pe_ratio`, `debt_to_equity`, `net_profit_margin`, `free_cash_flow_yield` = 1/P/FCF, `revenue_growth_yoy`, `eps_growth_yoy`) beside the nested blocks.
- Move this into the data-steward contract so it is not hand-added.

## 6. Tiger stop triggers (21 Oct item 7): resolved upstream
- Tiger's open-orders call now returns `stop_price`. `pma_levels.py stops` read MP 36.66 and V 401.15 correctly. The STP_LMT fallback is still worth keeping.

## 7. AQE Valen text defects (AQE repo)
- `watch_for` lists "5-day up/down 4% count clears 1.0 (now 4.38)", which is already met. The generator should only list unmet thresholds, or say "stays above".
- The selection funnel shows "Held 1" while the export holds 2 (MP, V).

## 8. Conditions "too late" price below the buy trigger
- ADP (292.45 vs buy 308.63) and SN (183.53 vs 200.06). The chase level is computed from ma_20+1atr, not from the buy. Clamp it to at least the buy.

## 9. Data check: ACA and PAYO ATR
- ACA atr_14d 0.54 is 0.36% of price, and PAYO 0.03 on a 7.17 stock. Several seats refused to read them. Check the AQE ATR series for these names.

## 10. Scorecard (information, not a defect)
- As of the 22 Oct close, over 15–22 Oct: ADVANCE vs SPY +1.76 (31/39 beat), but vs the equal-weight AQE list −1.41.
- PASS −0.10 and near-miss −0.06 vs the list, so both did better than ADVANCE.
- Over this window the committee subtracted value relative to simply holding the list. Recommend the PM review this at the 2-week mark.

DRAFT — PM approval required. Nothing is staged, nothing is armed.
