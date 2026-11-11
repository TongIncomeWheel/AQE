# Run notes 2026-11-11 (conductor)
- TRIGGER: pma-auto backstop 08:20 SGT found AQE run 140 cancelled (job time limit); run 141 re-dispatched 08:24 SGT finished 10:11:59 SGT; handoff Healthy after PR #83 (check.py false fail on 22 screened extra names). Started 10:40 SGT.
- DATA: committee_data requested 468 (446 export + screened extras), manifest OK but time_budget_exhausted: 26 closes-scope names (not export names) unserved; scorecard understated by 26. Macro: dispersion_vixeq and dspx PUBLISHER_LAG (Cboe posts 10:11 and 10:41 SGT); COT 3 Nov. Crown DEGRADED.
- BOOK: NOT FLAT. Journal 2026-11-10 + live read-only Tiger pull: EBAY 150, GPN 100, RBRK 80, all auto-included unrecognised fills, NO working stop orders (UNPROTECTED; Tiger open orders hold only an NVDA option stop). broker_stops.json: 3 positions, 3 no stop. PM told by push.
- INBOX-CLEAN: not run (declared).
- NOMINATE: Seow screened its 463-line packet with pattern searches (position-system conditions, cci_20 below -100) and did not read every row; declared in its form. Same packet-size limit as Minervini on 10 Nov: A's packet is too large for one seat to read whole.
- RANK/ROOM: 27 nominated across 7 seats; room 49 (30 momentum, 19 pullback); 3 held names seated by the HELD door; MTF 49/49 served.
- B (2026-11-11-B): 14 nominated, room 17 incl 3 held; reuse-a NOT run (A's consensus did not exist yet): B deliberates all 17 itself. Coverage gate: all 51 screened names served (committee_data scope now includes screens).
- A RATIFY: 7 of 7 seats; QA (Steenbarger) HELD five tickets (KO, MAC, EMBJ, TMO, PRCH) because the slate carried no ratification dissent and the ADVANCE triggers were thin; hold round run once (35 floor messages, floor-check OK) and re-ratified; final count AGREED 1 (TGTX), CONTESTED 5 (HUM, CAH, EMBJ, GPN, LTH), DROPPED 4 (KO, TMO, MAC, PRCH). 0 stances changed on the floor.
- R44: RUN.yaml manual override applied by ratify-count: APO, COMP, F, RY not deal-pinned (the scan misread them).
- ADOPT: 7 of 7 answered; rationale-final attached 7 AMEND texts verbatim; committee_position declared nothing.
- SCORECARD: only the exports present locally (2-10 Nov) were passed; 1 run mature at the 5-session horizon, 160 rows graded, 26 refused (closes-scope names unserved by the committee-data time budget, fixed for tomorrow in #85), 1,643 ungraded (older runs have no export on this machine). Declared.
- VOTE_PACKET was about 100KB vs the 70,000-byte guide (declared deviation, packets are trimmed by engineering next).

CARDS FALLBACK: the v3 page was NOT published (pma_cards_v3.py exited 1:              ~~~^^^^^^^^^^^^ TypeError: '<' not supported between instances of 'NoneType' and 'float'). The v2 page was published instead.
- CARDS: the v3 page crashed on held names with no stop at first publish (v2 page shown 16:28 SGT); engineering fixed it (#87, #88) and the v3 page and card_fields.json were republished the same day.
