"""AQE handoff: alerts that watch the committee's conditions (D123 / R21,
2026-10-02) — the frozen word vocabulary and constants, transcribed from
the handoff's own §5 table, never re-derived. `aegis/contracts/condition_
vocab.json` is "the only dictionary both sides use" per the handoff, but
was not itself delivered with it — this module IS that dictionary on
AQE's side, built from the handoff's own spec text (§5's table is the
source of truth cited in every docstring below). If a real condition_
vocab.json ever lands in the repo, it describes the SAME words; this
module does not read it at runtime (the handoff never requires that —
only that AQE recognise the shared vocabulary, which this enumerates).

A word NOT in CONDITION_WORDS is UNKNOWN_WORD: AQE logs it and skips it,
never guesses at what it might mean (handoff §2).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Session grid — the same 09:30 anchor every word below is read against.
# ---------------------------------------------------------------------------
SESSION_OPEN_MIN = 9 * 60 + 30   # 09:30 ET
SESSION_CLOSE_MIN = 16 * 60      # 16:00 ET
SLOT_MINUTES = 15
N_SLOTS = (SESSION_CLOSE_MIN - SESSION_OPEN_MIN) // SLOT_MINUTES  # 26 slots
HOUR_BOUNDARIES_MIN = list(range(SESSION_OPEN_MIN, SESSION_CLOSE_MIN + 1, 60))
# [570, 630, ..., 960] -> 09:30, 10:30, ..., 16:00 — 6 completed hourly
# candles in a 6.5-hour session (09:30-10:30, ..., 15:00-16:00).

# §7: the switch. "shadow" (default) logs only; "live" emails state changes.
MODE_SHADOW = "shadow"
MODE_LIVE = "live"

# §6: the final-cycle time. close_above/close_below, clv_ge/le and red_bar
# are only evaluated at or after this ET time (the provisional close).
FINAL_CYCLE_HOUR_MIN = 15 * 60 + 45  # 15:45 ET

# §4.4: session VWAP is not a gate before this many completed hourly candles.
VWAP_MIN_CANDLES = 2

# ---------------------------------------------------------------------------
# §5's word table, transcribed exactly. Each entry: (needs, cob_only) where
# `needs` names what evaluate_word() must be handed (used for NOT_YET
# detection) and `cob_only` marks a word PMA already judged at the close —
# AQE reports it as given and never re-evaluates it intraday.
# ---------------------------------------------------------------------------
PRICE_WORDS = {
    "close_above", "close_below",              # final cycle only
    "h1_close_above", "h1_close_below",        # last completed hourly candle
    "trade_above", "trade_below",              # day_high/day_low, INFO only
    "reclaim", "reject",
    "in_zone",
}
VOLUME_WORDS = {"vol_x_ge", "vol_x_le"}
VWAP_WORDS = {"above_vwap_s", "below_vwap_s"}
RS_WORDS = {"rs_today_gt_spy"}
ATR_WORDS = {"fade_atr_ge"}
FINAL_CYCLE_WORDS = {"close_above", "close_below", "clv_ge", "clv_le", "red_bar"}
CLV_WORDS = {"clv_ge", "clv_le"}

# §5's own callout: these are COB words PMA already judged at the close.
# AQE reports them as given (from the row/export) and does not re-evaluate
# them intraday — never routed through evaluate_word()'s live-data path.
COB_WORDS = {"elder_", "ma_above", "choch_bearish", "age_ge"}

CONDITION_WORDS = (PRICE_WORDS | VOLUME_WORDS | VWAP_WORDS | RS_WORDS
                  | ATR_WORDS | CLV_WORDS | {"red_bar"})


def is_cob_word(word: str) -> bool:
    """`elder_*` is a prefix family (elder_5d, elder_pattern, ...); the rest
    are exact matches."""
    return word in COB_WORDS or word.startswith("elder_")


def is_known_word(word: str) -> bool:
    return is_cob_word(word) or word in CONDITION_WORDS
