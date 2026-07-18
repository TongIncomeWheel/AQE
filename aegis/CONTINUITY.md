# CONTINUITY REGISTER — your established commands and outputs, mapped old → new
The worry this file answers: "established procedures like /srm /ptj /bracket look gone — are my outputs still produced the same way?" Answer per item, with the guarantee stated.

| You had | You have now | Format / scope guarantee |
|---|---|---|
| **/ptj** — trade journal export: open positions (live stop vs reference stop, MATCH/MISMATCH/MISSING), closed trades, metrics, broker sync, dynCap | **/ptj — kept, exact command only, same weight rules.** The nightly post-market journal IS the same document, produced automatically at 4am instead of on command; /ptj prints it on demand | **Field-for-field verified by today's audit:** stop_reference, stop_live_broker, stop_match, tp1/2/3, unrealised, closed_trades, metrics, broker_sync, dynCap method unchanged. BL-019: first live run produces old-style and new side by side and diffs them — you sign off the parity, not me |
| **/fa** — quick book view, token-cheap, no pulls | **/fa — kept unchanged** | Same: conversation-state render, no connectors, no writes |
| **/srm** — sector scorecard (11 sectors, grades, trend states) | **/srm — restored.** End-of-day sector read comes from the feed's sector block (same underlying data you had); NEW: during market hours it also runs the live pulse | Scorecard content preserved via the feed; the live pulse is an addition, not a replacement |
| **/bracket T /trail T** — bracket card, feed values verbatim + live distance | **/bracket T — kept** (in the registry since v4.5) | Same doctrine: feed bracket verbatim, live spot overlay, no recomputation |
| **/hedge** — coverage matrix + 3 candidates | **/hedge — restored** as on-demand run of the same premarket hedge check | Same two-phase logic, same Alpaca/Tiger data split, same skip rule |
| Old premarket /pm ritual | **/pm — kept**, same one-pass discipline, committee now truly isolated | Sequence preserved; anti-anchoring now structural |
| Lessons log, DPRS | Absorbed: lessons that were rules ARE the rulebook; audit substance lives in the auditor; scoring by outcomes in the ledger | Nothing deleted — traced in CONTEXT Part 2 |
Rule going forward: retiring or renaming ANY command you use requires a decisions-log entry naming the replacement — silent disappearance is itself a breach.
