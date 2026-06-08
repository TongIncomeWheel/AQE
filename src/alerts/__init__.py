"""AQE live alert subsystem — the Trade Entry Menu's poll-and-notify engine.

Polls FMP for 15-min-delayed quotes, compares each monitored ticker (longlist /
watchlist / Precision Edge / held) against its key levels, and emails the PM a
digest with a ready-to-paste "engage AIC via Claude" workflow when a level hits.
"""
