"""QS frozen spec constants — transcribed from the reference implementation.

Every value here is copied from `daily_scan.py` (the research session's
reference implementation), NOT inferred from the prose handover. Where the
handover and the reference disagree, the line comment says so and names which
one this module follows.

Why this file exists separately: these constants decide which calibration
bucket a name lands in. Get one wrong and every quoted probability shifts,
silently — the output still looks completely plausible. Keeping them in one
transcribed, cited block makes them auditable against source instead of
scattered through engine code as literals.

DO NOT TUNE ANYTHING HERE. The frozen `calibration.json` was measured against
exactly these values. Changing one without re-freezing the calibration breaks
the correspondence between a quoted probability and what it was measured on.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# LENSES — daily_scan.py:287-303, transcribed verbatim.
# ---------------------------------------------------------------------------
# Each lens is 3 (field, orientation) pairs. Orientation +1 uses the raw
# cross-sectional percentile; -1 uses (1 - percentile).
#
# MOMENTUM is fully inverted: LOW raw momentum scores HIGH, because quiet
# momentum is the winning condition. This is the core of the whole method —
# "structurally strong while momentum is still asleep" — so a sign error here
# inverts the signal rather than merely degrading it.
LENSES: dict[str, list[tuple[str, int]]] = {
    "STRUCTURE":  [("en_pos50", +1), ("ms_pos_score", +1), ("structure_100", +1)],
    "COIL":       [("bq_range_tight", +1), ("bq_ema_conv", +1), ("squeeze_score", +1)],
    "MOMENTUM":   [("roc_zscore", -1), ("abs_mom_score", -1), ("rel_mom_score", -1)],
    "FLOW":       [("accum_score", +1), ("cmf", +1), ("mfi", +1)],
    "LEADERSHIP": [("rs_consist", +1), ("rs_vs_spy", +1), ("elder_score", +1)],
}

# Rounding is applied at BOTH levels in the reference (daily_scan.py:310,313):
# each lens score is round(_, 1), then lens_total = round(mean(lenses), 1).
# Rounding only at the end produces different band assignments on boundary
# cases, so the two-stage rounding is part of the spec.
LENS_SCORE_DP = 1
LENS_TOTAL_DP = 1

# Raw component values carried onto the card — daily_scan.py:446-450. The 15
# scored lens components plus `base_days`, which the reference prints on the
# STRUCTURE line but does NOT score. Shipped so a card can be rebuilt from the
# export without a data lookup.
CARD_COMPONENTS: list[str] = [
    "en_pos50", "ms_pos_score", "structure_100", "base_days",
    "bq_range_tight", "bq_ema_conv", "squeeze_score",
    "roc_zscore", "abs_mom_score", "rel_mom_score",
    "accum_score", "cmf", "mfi",
    "rs_consist", "rs_vs_spy", "elder_score",
]


# ---------------------------------------------------------------------------
# CALIBRATION BANDS — daily_scan.py:326-329, transcribed verbatim.
# ---------------------------------------------------------------------------
# NOTE THE ASYMMETRY, it is not a typo:
#   hits and persist bands are RIGHT-inclusive  (<=)
#   the lens band is LEFT-inclusive / right-EXCLUSIVE  (<)
# So lens_total == 6.0 lands in "6-7", NOT in "5-6". Because lens_total is
# rounded to 1dp, exact integers are common, so this boundary is hit often.

def hits_band(hits: int) -> str:
    """daily_scan.py:326 — `"0" if hits==0 else "1-2" if hits<=2 else ...`"""
    if hits == 0:
        return "0"
    if hits <= 2:
        return "1-2"
    if hits <= 7:
        return "3-7"
    return "8+"


def lens_band(lens_total: float) -> str:
    """daily_scan.py:327-328 — strict `<`, so 6.0 -> "6-7" not "5-6"."""
    if lens_total < 5:
        return "<5"
    if lens_total < 6:
        return "5-6"
    if lens_total < 7:
        return "6-7"
    return "7+"


def persist_band(persist: int) -> str:
    """daily_scan.py:329 — `"0-1" if persist<=1 else "2-3" if persist<=3 ...`"""
    if persist <= 1:
        return "0-1"
    if persist <= 3:
        return "2-3"
    return "4-5"


# ---------------------------------------------------------------------------
# RECIPE HIT COUNTING — daily_scan.py:133-143.
# ---------------------------------------------------------------------------
# Counts EVERY entry in book["recipes"] (40), NOT unique condition-sets (32).
# Eight recipes are exact duplicates with their conditions listed in a
# different order, and they are counted twice by design. Confirmed against
# source: the counting loop is byte-identical across build_calibration3.py,
# three sites in daily_scan.py, and qs_memory_lab.py, and calibration.json was
# rebuilt against this exact count. The book also carries a `recipe_hits_rule`
# field stating it inline. DO NOT DEDUPE — the hit bands above were fitted on
# the double-counted total, so de-duplicating would push names down a band and
# systematically understate every probability.
DEDUPE_RECIPES = False

# `between` is right-inclusive: daily_scan.py:56 uses
# `s.between(lo, hi, inclusive="right")` == `lo < x <= hi`.
BETWEEN_INCLUSIVE = "right"

# NaN handling in `cond_mask` (daily_scan.py:45-56): a NaN field makes every
# comparison False, so the condition fails. For RECIPES that is conservative
# and is reproduced exactly. For VETOES the same rule is fail-OPEN — a name
# with a missing veto field is silently NOT struck. The reference accepts
# that; we reproduce the behaviour (so conviction matches) but additionally
# RECORD the gap, so a veto that could not be evaluated is visible rather than
# indistinguishable from a veto that was evaluated and passed.
FLAG_UNEVALUABLE_VETOES = True


# ---------------------------------------------------------------------------
# STATE — daily_scan.py:170-183.
# ---------------------------------------------------------------------------
# `awake` = abs_mom_score > 0 OR rel_mom_score > 0 OR impulse_state == "GREEN".
# AQE's elder engine emits GREEN / RED / NEUTRAL — there is no BLUE — so the
# string comparison is safe as written.
AWAKE_IMPULSE_VALUE = "GREEN"

# READY is tested BEFORE EARLY, so it wins when both would qualify.
#
# READY+ — PM RULING 2026-08-04, a deliberate DEPARTURE from the reference.
# The handover quotes READY+ at 73.1% (§1.3, "both qualifying today AND held
# AND awake") but daily_scan.py emits only READY / EARLY / "". The PM wants it
# surfaced, so it is emitted as a third state.
#
# This is SAFE to add: the state label is descriptive only. est_p is keyed on
# (hits, lens_total, persist) and conviction on (est_p, cell_base_rate) —
# neither reads qs_state, and SORT_KEYS does not include it. Emitting READY+
# therefore changes not one probability, conviction, or rank position. It
# splits the existing READY population into two labels, nothing more.
#
# READY+ is a strict subset of READY: same trigger, plus the profile STILL
# qualifying today. That is the rarer and more informative case — most recipes
# require quiet momentum, so hits normally collapse at the exact moment the
# move begins. A name still printing >=3 hits while awake has not collapsed.
STATE_DESC: dict[str, str] = {
    "EARLY": "quietly strong, hasn't started moving yet",
    "READY": "was quietly strong all week, now starting to move",
    "READY+": "quietly strong all week, now moving — and still qualifying today",
    "": "",
}
PERSIST_WINDOW = 5          # daily_scan.py:151
QS_DAY_MIN_HITS = 3         # daily_scan.py:160 — a "QS day" is hits >= 3
READY_MIN_PERSIST = 3       # daily_scan.py:174
EARLY_MIN_HITS = 3          # daily_scan.py:175
READY_PLUS_MIN_HITS = 3     # handover §1.3 — "both qualifying today"


def qs_state(recipe_hits: int, qs_persist: int, awake: bool) -> str:
    """EARLY / READY / READY+ / "" — daily_scan.py:173-175 plus READY+.

    Order matters: the READY family is tested first, so a name that would
    satisfy both READY and EARLY is reported as READY (it is moving, which is
    the more actionable fact). EARLY requires NOT awake by definition.
    """
    if qs_persist >= READY_MIN_PERSIST and awake:
        return "READY+" if recipe_hits >= READY_PLUS_MIN_HITS else "READY"
    if recipe_hits >= EARLY_MIN_HITS and not awake:
        return "EARLY"
    return ""


# Measured test-window hit rates, for display next to the state so the
# committee reads a state against its own historical base, not the global one.
# Handover Appendix A; base rate for all of them is 0.548.
STATE_TEST_RATE: dict[str, float] = {
    "EARLY": 0.648,
    "READY": 0.694,
    "READY+": 0.731,
}


# ---------------------------------------------------------------------------
# CONVICTION — daily_scan.py:363-377.
# ---------------------------------------------------------------------------
# Banded on the ROUNDED probability: the card shows "60%", so a name
# displaying 60% must score as 60%, not as the 0.596 behind it.
CONVICTION_P_DP = 2
# Regimes with no measured base rate (T1V1, unclassified) fall back to the
# global test base rate — daily_scan.py:363 `reg.get("base_rate_test") or 0.548`.
DEFAULT_CELL_BASE_RATE = 0.548
CONVICTION_WORD: dict[int, str] = {
    0: "vetoed", 1: "none", 2: "low", 3: "moderate", 4: "high", 5: "very high",
}


def conviction(p_display: float | None, cell_base_rate: float,
               vetoed: bool) -> int:
    """0-5. A veto forces 0 regardless of probability (daily_scan.py:374)."""
    if vetoed:
        return 0
    if p_display is None:
        return 1
    edge = p_display - cell_base_rate
    if p_display >= 0.65 and edge >= 0.15:
        return 5
    if p_display >= 0.60 and edge >= 0.10:
        return 4
    if p_display >= 0.55 and edge >= 0.05:
        return 3
    if edge > 0:
        return 2
    return 1


# ---------------------------------------------------------------------------
# SIGNAL LABEL — daily_scan.py:347-350. Driven by HITS, not conviction.
# ---------------------------------------------------------------------------
def signal_label(hits: int, vetoed: bool) -> str:
    if vetoed:
        return "SKIP"
    if hits >= 8:
        return "STRONG"
    if hits >= 3:
        return "GOOD"
    if hits >= 1:
        return "WATCH"
    return "NONE"


# ---------------------------------------------------------------------------
# RANKING + EMISSION — daily_scan.py:381-392.
# ---------------------------------------------------------------------------
# CONFLICT, resolved in favour of source:
#   handover §4.2 says ideas sort "conviction DESC, then p DESC, then
#   lens_total DESC". The reference sorts by RECIPE_HITS DESC, est_p DESC,
#   lens_total DESC — at BOTH sites (qs_rank at :383 and the printed sheet at
#   :392). We follow the reference, because the reference is what produced the
#   worked example the whole spec is validated against.
SORT_KEYS = ("recipe_hits", "est_p", "lens_total")

# qs_rank: hits >= 1, no vetoes, sorted by SORT_KEYS, cut at 50.
QS_RANK_MIN_HITS = 1
QS_RANK_TOP_N = 50

# The printed sheet additionally requires hits >= 2 (daily_scan.py:390) on top
# of the handover's stated noise rule (R8: conviction < 2 never emitted).
# Vetoed names (conviction 0) ARE emitted so the committee sees what was
# struck and why.
SHEET_MIN_HITS = 2
STAND_DOWN_STANCE = "STAND_DOWN"

# REGIME IS A WARNING, NOT A GATE — PM ruling 2026-08-04, a deliberate
# DEPARTURE from the handover (§4.1 "in STAND_DOWN the actionable list is empty
# by design", R8 "enforce ... STAND_DOWN empty list") and from daily_scan.py:391.
#
# The reference emptied the whole list in a STAND_DOWN regime. That makes AQE
# DECIDE, which is the one thing it does not do: "AQE makes no decisions, no
# sizing. It exports data + computed levels only." A market read that silently
# deletes 240 scored names is a decision wearing a filter's clothes — and it is
# indistinguishable, on screen, from an engine that failed.
#
# The regime still matters, and still shows up in two honest places: it sets
# `cell_base_rate`, so a hot market cannot flatter a mediocre name through
# `edge`; and it is published as a graded WARNING the PM reads first.
REGIME_GATES_THE_LIST = False

# Regime colour, derived from the recipe book's OWN measured base rate rather
# than from invented thresholds. base_rate_test is the fraction of eligible
# stocks that reached the objective in that regime during the test window, so
# it is the backtested answer to "how good is this weather".
# Anchored on the global test base rate (0.548): materially above it is green,
# materially below is red.
REGIME_GREEN_MIN = 0.60      # comfortably better than the 0.548 all-market base
REGIME_AMBER_MIN = 0.50      # around the base
REGIME_COLOURS = ("GREEN", "AMBER", "RED", "GREY")


def regime_colour(base_rate_test: float | None) -> str:
    """GREEN / AMBER / RED from the regime's measured base rate; GREY if never
    measured (T1V1 and `unclassified` carry no base_rate_test)."""
    if base_rate_test is None:
        return "GREY"
    if base_rate_test >= REGIME_GREEN_MIN:
        return "GREEN"
    if base_rate_test >= REGIME_AMBER_MIN:
        return "AMBER"
    return "RED"

# `high_probability` — daily_scan.py:352-355. Not in the handover prose.
HIGH_PROB_MIN_HITS = 3
HIGH_PROB_MIN_P = 0.60
HIGH_PROB_MIN_ANALOGUES = 300
HIGH_PROB_MIN_LENS = 6          # applies to L_STRUCTURE and L_MOMENTUM
HIGH_PROB_BLOCKED_STANCES = ("STAND_DOWN", "DEFENSIVE")

# Stance -> the one-line action string shown on the MARKET row
# (daily_scan.py:267-273).
STANCE_ACTION: dict[str, str] = {
    "PRESS": "Good conditions. Act on strong ideas.",
    "PRESS_EXPECT_WHIPSAW": "Conditions work, but expect violent swings.",
    "NEUTRAL": "Ordinary conditions. Normal selectivity.",
    "DEFENSIVE": "Poor conditions. Only the very best ideas.",
    "STAND_DOWN": "No edge in this market. Manage open positions only.",
}

# Probability source — daily_scan.py:332-335.
#   bucket = buckets_persist[hits|lens|persist]  or  buckets[hits|lens]
#   p displayed = p_train ; n_analogues = n_train ; p_test is context only.
# The 2-D fallback carries NO days_median / mae_atr_median, so the reference
# simply omits those lines rather than substituting a global median. We do the
# same: an omitted number is honest, an invented one is not.
