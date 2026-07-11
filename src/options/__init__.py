"""AQE Options — standalone scanner + calculator (IBKR-fed, recommend-only).

A SEPARATE options layer (does not touch the AQE equity export). It turns an
IBKR-sourced option chain (spot + strike + expiry + IV — no local server, no paid
API) into:
  * a **calculator**: BS market-maker fair value, full Greeks, and the economics of
    selling a cash-secured put or a put credit spread;
  * a **theta scanner**: rank a watchlist's puts by annualised income / capital
    efficiency, filtered by delta band, DTE, POP and liquidity — for the income wheel.

Pure + deterministic (stdlib only — `math`, `statistics.NormalDist`; no numpy/scipy).
Live data is fetched by the caller (the `aqe-option-scanner` skill drives the IBKR
MCP and passes contracts in), exactly like `src/intraday/` consumes bars.
"""
