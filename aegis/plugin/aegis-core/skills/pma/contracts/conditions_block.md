# The conditions block — paste into every round-2 seat prompt (D123, from 2026-10-02)

**Your vote does not change. Judge exactly as your card says.** On every SUPPORT you ALSO write, in the
shared words below, what would make you act and what would prove you wrong, so AQE's live alerts watch
exactly what you said. OPPOSE and ABSTAIN may add a block (what would flip you, or what you'd watch for);
it is optional.

Add to each vote:
```json
"conditions": {
  "lane": "BREAKOUT | PULLBACK | SPRING | FAILED_BREAKOUT | CONTINUATION | NONE",
  "buy":     ["h1_close_above:pivot_high"],
  "confirm": ["vol_x_ge:1.4", "above_vwap_s"],
  "wrong":   ["close_below:pivot_high-0.5atr", "fade_atr_ge:1"],
  "wait":    ["ma_20", "fib_382"],
  "chase":   "close_above:pivot_high+5pct",
  "tf": "1H | EOD | W",
  "non_price": "<=200: a fundamental or tape leg no engine can see, or null"
}
```

**Rules (the registrar rejects the ballot otherwise):**
1. **Name levels by field, never by number.** Write `pivot_high`, `ma_20-0.5atr`, `bar_high+2pct`. The tool
   puts the number on it from the export. `h1_close_above:62.15` is rejected.
2. **"Yesterday's high" is `bar_high`.** `prior_bar_high` is the day before that. `high_52w_close` is a
   CLOSING high: a trade through it is an uptick, not a breakout.
3. **Volume words are time-of-day normalised.** `vol_x_ge:1.4` means 1.4x this stock's normal volume *for this
   time of day*, so your card's "+40%" is written 1.4 and means the same at 10:30 and 15:30.
4. **Two VWAPs.** `vwap_14d` is a level (multi-day value, use it in `wait` or as a line). `above_vwap_s` is
   today's session VWAP from the hourly candles (who is in control today).
5. **Stay inside your own method** (contracts/voice_primitives.json): Livermore does not buy the pullback,
   Minervini and O'Neil do not buy a reclaim, Seow names no 50/100/150/200-day average. Lynch and Thorp
   may support with `wrong` or `non_price` only.
6. Your free-text `falsifier` stays: it is the human sentence; `wrong` is the same thing in shared words.

**Words** (full meanings in contracts/condition_vocab.json):
- price vs a level: `close_above` `close_below` (daily close) · `h1_close_above` `h1_close_below` (hourly candle) ·
  `trade_above` `trade_below` (a touch, logged only) · `reclaim` (dips under, closes the hour back above) ·
  `reject` (pokes over, closes the hour back under) · `in_zone` (comes back to it)
- volume and control: `vol_x_ge:x` `vol_x_le:x` · `above_vwap_s` · `below_vwap_s:n` (n hourly closes under) ·
  `clv_ge:x` `clv_le:x` (where it closes in the day's range) · `red_bar`
- strength: `rs_today_gt_spy` · reaction: `fade_atr_ge:x` (x ATR off the day's high)
- trend state at the close: `elder_le:n` `elder_ge:n` · `ma_above:ma_20:ma_40` · `choch_bearish`
- time: `age_ge:n` (n sessions without a buy)

**Levels:** pivot_high · bar_high · bar_low · prior_bar_high · prior_bar_low · entry (yesterday's close) ·
high_52w_close · low_52w · base_low_20d · ma_20 ma_40 ma_50 ma_100 ma_150 ma_200 · vwap_14d ·
fib_236 fib_382 fib_500 fib_618 fib_786 fib_swing_high fib_swing_low · pin_bar_level. Offsets: `+/-Natr`, `+/-Npct`.

Budget: about 150–250 bytes per vote. Keep `reason` shorter to pay for it; the ballot splits as before.
