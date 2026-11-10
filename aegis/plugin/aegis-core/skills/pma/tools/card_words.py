#!/usr/bin/env python3
"""card_words.py -- the ONE table that turns every condition word of contracts/condition_vocab.json into plain English for the Cards (PM 2026-11-10),
and the no-raw-words gate every sentence passes before it is printed."""
import re

# ---- ONE table for every condition word the vocabulary allows (contracts/condition_vocab.json) -> plain English (PM 2026-11-10: the triggers sentence
# printed "2 close_above:pivot_high" raw, and 9 Nov's market-kill line printed "SPY close_below ma_50" raw). Nothing in this file prints a raw
# condition word: an unmapped one falls back to a generic plain phrase, and `no_raw_words` is the gate every sentence passes before it is printed.
LEVEL_PLAIN = {
    "pivot_high": "the last pivot high", "bar_high": "yesterday's high", "bar_low": "yesterday's low",
    "prior_bar_high": "the high before yesterday", "prior_bar_low": "the low before yesterday", "entry": "the entry price",
    "high_52w_close": "the 52-week closing high", "low_52w": "the 52-week low", "base_low_20d": "the 20-day base low",
    "ma_20": "the 20-day average", "ma_40": "the 40-day average", "ma_50": "the 50-day average", "ma_100": "the 100-day average",
    "ma_150": "the 150-day average", "ma_200": "the 200-day average", "vwap_14d": "the 14-day average price (VWAP)",
    "fib_236": "the 23.6% retracement", "fib_382": "the 38.2% retracement", "fib_500": "the 50% retracement", "fib_618": "the 61.8% retracement",
    "fib_786": "the 78.6% retracement", "fib_swing_high": "the swing high", "fib_swing_low": "the swing low", "pin_bar_level": "the pin-bar level",
    "pvp_poc": "the point of control", "pvp_vah": "the top of the value area", "pvp_val": "the bottom of the value area",
    "structure_shift_ref": "the broken structure level", "avwap_structure": "the structure anchored average price", "avwap_swing": "the swing anchored average price",
}
WORD_PLAIN = {   # {l} = the level phrase, {n} = a number
    "close_above": "a daily close above {l}", "close_below": "a daily close below {l}", "h1_close_above": "an hourly close above {l}",
    "h1_close_below": "an hourly close below {l}", "trade_above": "a trade above {l}", "trade_below": "a trade below {l}",
    "reclaim": "a reclaim of {l}", "reject": "a rejection at {l}", "in_zone": "a pullback into {l}",
    "vol_x_ge": "volume at least {n} times its average", "vol_x_le": "volume at most {n} times its average",
    "above_vwap_s": "price above the short-term average price", "below_vwap_s": "price below the short-term average price",
    "rs_today_gt_spy": "beating the index today", "fade_atr_ge": "a fade of at least {n} daily ranges", "clv_ge": "a close in the top part of the day's range",
    "clv_le": "a close in the bottom part of the day's range", "red_bar": "a down day", "elder_le": "the momentum score at or below {n}",
    "elder_ge": "the momentum score at or above {n}", "ma_above": "price above {l}", "choch_bearish": "a break lower in market structure",
    "age_ge": "a signal at least {n} days old",
}
GENERIC_COND = "a stated condition"
_TOK = re.compile(r"\b(" + "|".join(sorted(WORD_PLAIN, key=len, reverse=True)) + r")(?:[:\s]+([A-Za-z_][A-Za-z0-9_]*|[0-9]+(?:\.[0-9]+)?))?")

def cond_plain(token):
    """One condition token ('close_above:pivot_high', 'vol_x_ge:1.4', 'in_zone') -> plain English; never the raw word."""
    token = str(token or "").strip()
    w, _, arg = token.partition(":")
    if w not in WORD_PLAIN:
        return GENERIC_COND
    tpl = WORD_PLAIN[w]
    lvl = LEVEL_PLAIN.get(arg)
    if "{l}" in tpl:
        return tpl.format(l=lvl or "the stated level")
    if "{n}" in tpl:
        return tpl.format(n=arg if re.fullmatch(r"[0-9.]+", arg or "") else "the stated multiple")
    return tpl

_SYM = re.compile(r"\b(SPY|QQQ|IWM|VIX)\s+(close_above|close_below)(?:[:\s]+([A-Za-z_][A-Za-z0-9_]*))?")

def _sym_sub(m):
    lvl = LEVEL_PLAIN.get(m.group(3) or "", "the stated level")
    return f"{m.group(1)} closes {'above' if m.group(2) == 'close_above' else 'below'} {lvl}"

def _tok_sub(m):
    w, a = m.group(1), m.group(2)
    if w in WORD_PLAIN and "{l}" in WORD_PLAIN[w] and a in LEVEL_PLAIN:
        return cond_plain(f"{w}:{a}")
    if w in WORD_PLAIN and "{n}" in WORD_PLAIN[w] and a and re.fullmatch(r"[0-9.]+", a):
        return cond_plain(f"{w}:{a}")
    out = cond_plain(w)
    return out + (" " + a if a and a not in LEVEL_PLAIN and "{l}" not in WORD_PLAIN[w] and "{n}" not in WORD_PLAIN[w] else "")

_RAW = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")

def no_raw_words(s):
    """The plain-words gate over a sentence, applied BEFORE it is printed: condition words and levels become English, and any remaining
    snake_case token becomes the generic phrase. Returns the sentence with no raw word in it."""
    s = _SYM.sub(_sym_sub, str(s))
    s = _TOK.sub(_tok_sub, s)
    s = re.sub(r"\b(" + "|".join(sorted(LEVEL_PLAIN, key=len, reverse=True)) + r")\b", lambda m: LEVEL_PLAIN[m.group(1)], s)
    return _RAW.sub(GENERIC_COND, s)

