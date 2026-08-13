# CENTRAL TOOL & DATA CATALOG (the hub — voices and orchestrators pull through here only)
| Name | What | Where | Who may call | Notes |
|---|---|---|---|---|
| AQE export | scores, brackets, detect, lens, held book — verbatim source of all analytics | GitHub repo engine → aegis/output/ | all (via working read) | validate + tripwires before ANY read |
| Universe screen | daily tradable universe (D-3) | tools/universe_screen.py (FMP) | Premarket orchestrator | the only universe voices see |
| Tiger MCP | equity/ETF spot, positions, orders, preview-confirm staging | REUSED — PM's Google Cloud service (endpoint in config/endpoints.json) | orchestrators | primary live spot |
| Alpaca MCP | options chain / Greeks / IV, 15-min delayed | REUSED — PM's Google Cloud service | hedge tooling only | never for spot |
| IBKR MCP | positions, balances, orders, trades, snapshot — READ-ONLY | tools/mcp/ibkr_mcp/ (new, this repo) | orchestrators | needs Client Portal Gateway; on Claude the built-in connector may substitute |
| FMP | bars, screener, live quotes | connector / REST (FMP_API_KEY) | screen, ledger tracking, SRM | budget-aware |
| Calculators | sizing, bs_price, hedge_engine, performance | tools/calculators/ | everyone | the only place maths lives |
| Nomination Ledger | outcome memory of every nomination | tools/nomination_ledger.py → data/ledger/ | voices (read own), assurance (all) | law 7 |
| Tripwires | feed integrity gate | tools/tripwires.py | orchestrators, AQE job | BLOCKS on anomaly |
| Proposal measurement | panel-before-vote | tools/measure_proposal.py | any voice via Design & Review | no vote without numbers |
