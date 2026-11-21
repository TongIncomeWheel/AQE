"""Frozen constants for MOMENTUM HIGH, transcribed from the BACKTEST REVIEW session's spec and reference code (PM sign-off 2026-11-21). Not tuned here."""
from __future__ import annotations

MIN_PRICE = 5.0
ATR_N = 14
ATR_MIN_PERIODS = 7                 # reference: simple rolling MEAN of true range over 14 bars, min 7
ATR_PCT_LO, ATR_PCT_HI = 1.5, 15.0  # ATR14 / close * 100
EMA_SPANS = (13, 21, 50, 150, 200)  # pandas ewm(span=N, adjust=False, min_periods=N)
EMA200_RISING_LOOKBACK = 20         # EMA200 / EMA200[t-20] - 1 > 0
HIGH_WINDOW, HIGH_MIN_PERIODS = 252, 200     # 252-day high = rolling max of HIGH
NEAR_HIGH_FRAC = 0.97               # close >= 0.97 x the 252-day high
MOM_SKIP, MOM_LONG = 21, 252        # mom_12_1 = close[t-21] / close[t-252] - 1
RS_LOOKBACK = 63                    # rs_63 = close/close[t-63] - SPY/SPY[t-63], SPY matched by DATE
TOP_PCT = 0.80                      # "top 20%" = percentile rank >= 0.80 within the eligible set that day
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
ADX_N, ADX_MIN = 14, 20.0           # Wilder smoothing: ewm(alpha=1/14, adjust=False, min_periods=14)
WEEK_SMA_FAST, WEEK_SMA_SLOW, WEEK_SLOPE_LOOKBACK = 10, 30, 4      # weekly = W-FRI resample of the daily close
SMA50, SMA200 = 50, 200             # breadth (50-day) and SPY trend (200-day) simple averages
BREADTH_MIN_PCT = 50.0              # market_ok = SPY above its 200-day SMA AND breadth >= 50
FIRST_DAY_LOOKBACK = 5              # first_day = not a member in the prior 5 sessions
STOP_ATR_MULT = 1.2                 # reference_stop = last close - 1.2 x ATR14 (a reference level, not an order)
MIN_BARS_FOR_MOM = MOM_LONG + 1     # a name needs >= 253 bars for mom_12_1

WHAT_IT_IS = (
    "MOMENTUM HIGH lists stocks that are already strong on every timeframe at once. To appear, a stock must: trade at $5 or more with a daily range "
    "of 1.5% to 15% of its price (enough movement to matter, not so much it is erratic); be in a clear long-term uptrend (price above a rising "
    "200-day average, with the 21-, 50-, 150- and 200-day averages stacked in order); sit within 3% of its 52-week high; rank in the top 20% of "
    "eligible stocks both for 12-month momentum (ignoring the last month) and for 63-day outperformance against the S&P 500; show its short-term "
    "trend turning up (13-day average and MACD histogram both rising); show a trending reading (ADX 20 or more, buyers above sellers); and have "
    "the weekly chart agree. It is a screen of what is already working. It is NOT a forecast and NOT a buy list; sizing and the trade decision "
    "stay with the PM. The market check above it says whether the wider market supports this kind of stock: the S&P 500 above its 200-day average, "
    "and at least half of the tradable stocks above their own 50-day average."
)
STOP_NOTE = "reference level from the last close (last close minus 1.2 x ATR14); use the entry price in place of the close. A reference level, not an order."
ODDS_LABEL = "history 2022-2026, 6-position $100k book, not a forecast"
MEASURED_ODDS = {
    "label": ODDS_LABEL,
    "source": "frozen from the BACKTEST REVIEW session's research (2026-11-21); not computed by AQE and not updated by the nightly run",
    "shapes": {
        "hold 20 sessions": {"win_rate_pct": 28, "avg_winner_r": 3.6, "avg_loser_r": -1.0, "avg_r_per_trade": 0.24},
        "half off at +1.5R, stop to breakeven, trail rest at 3xATR": {"win_rate_pct": 43, "avg_winner_r": 1.7, "avg_loser_r": -1.0, "avg_r_per_trade": 0.14},
    },
    "caveat": "survivor universe; most of the gain came in 2024; not statistically proven against SPY on a risk-adjusted basis",
}
RULES = [
    "price >= $5; ATR14 (simple mean of true range, 14 bars) between 1.5% and 15% of close",
    "close > EMA150 > EMA200; EMA200 above its value 20 bars ago; close > EMA50",
    "close >= 0.97 x the 252-day high",
    "EMA21 > EMA50 > EMA150; close > EMA21",
    "12-1 momentum (close 21 bars ago / close 252 bars ago - 1) in the top 20% of eligible names that day",
    "63-day return minus SPY's 63-day return (matched by date) in the top 20% of eligible names that day",
    "Elder green: EMA13 above its prior bar AND MACD(12,26,9) histogram above its prior bar",
    "Wilder ADX14 >= 20 with +DI > -DI",
    "weekly (completed weeks only): close > 30-week SMA, 30-week SMA above its value 4 weeks ago, close > 10-week SMA",
]
