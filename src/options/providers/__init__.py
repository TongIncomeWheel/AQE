"""Options data providers — REST adapters that feed the pure engine.

Each provider maps a source's option-chain response into the engine's flat contract
dict ({ticker, spot, strike, dte, iv, bid, ask, right}). The IBKR hosted MCP is the
chat-driven single-ticker source; `alpaca` is the REST source for the hosted
whole-universe sweep (a standalone app can't reach the chat MCPs).
"""
