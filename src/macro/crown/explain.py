"""The regime in plain English — generated from the data, never hand-written.

Every other module in this layer produces numbers. This one produces the
sentence a person actually wants: what kind of market is this, why, what does
the process say to do, and what would change the answer.

**It is regenerated on every run from the finished Crown read**, so it cannot go
stale or drift away from the numbers it describes. If the spread moves, the
sentence about the spread moves with it.

Two rules the writing follows, because they are what make it readable:

  1. **No jargon without its meaning.** "Dispersion at the 98th percentile" is
     not English. "Single stocks are far more volatile than the index — wider
     than 98% of the last two years" is.
  2. **No claim without its number, and no number without its claim.** A
     sentence that says only "breadth is weak" cannot be checked; one that says
     only "0.328" cannot be understood.

Pure: it takes the finished dicts and returns strings. No network, no files, no
recomputation — so what it says is exactly what the rest of the page shows.
"""

from __future__ import annotations

from . import spec as S

# ── plain words for the layer's internal vocabulary ──────────────────────

FAMILY_PLAIN = {
    "BROADENING_CARRY": "Own the average stock, not just the leaders — and "
                        "collect premium against it.",
    "NARROWING_CONCENTRATED": "Stay with the leaders. Keep the risk defined.",
    "HIDDEN_STRESS_DOWNSIDE": "Buy cheap index downside. Small size — this one "
                              "is tactical and time-sensitive.",
    "DIVERGENCE_PAIR_SHORT": "Pair it up: short the stretched leader against the "
                             "average stock.",
    "MEAN_REVERSION_PREMIUM": "Fade the extremes. Sell premium rather than chase "
                              "breakouts.",
    "NONE": "No new risk.",
}

SCENARIO_PLAIN = {
    "DISPERSION_REGIME": "a stock-picker's market — the index tells you very "
                         "little about the average name",
    "REFLATION": "reflation — growth and yields rising together",
    "GROWTH_SCARE": "a growth scare — credit and cyclicals giving way",
    "INFLATION_SHOCK": "an inflation shock — commodities and rates up together",
    "DISINFLATION_GOLDILOCKS": "goldilocks — yields falling without credit breaking",
    "LIQUIDITY_STRESS": "liquidity stress — everything trading as one thing",
    "DOLLAR_SQUEEZE": "a dollar squeeze draining everything else",
}

MARKET_PLAIN = {
    "ES": "the S&P", "NQ": "the Nasdaq", "YM": "the Dow", "RTY": "small caps",
    "ZN": "the 10-year note", "ZB": "the long bond", "ZF": "the 5-year",
    "ZT": "the 2-year", "CL": "crude", "BZ": "Brent", "NG": "natural gas",
    "GC": "gold", "SI": "silver", "HG": "copper", "DX": "the dollar",
    "ZC": "corn", "ZS": "soybeans", "ZW": "wheat",
}

CHECK_PLAIN = {
    "rsi": "momentum is not keeping up with price",
    "rsi_slope": "price is climbing while momentum falls",
    "cross_asset": "other markets are not confirming the move",
    "vix": "protection is getting more expensive into strength",
    "breadth": "the average stock is not following the index",
    "breadth_ma": "breadth is rolling over toward its own average",
    "dispersion": "single-stock volatility is pulling away from the index",
    "positioning": "the crowd is already positioned this way",
}


def _pct(x, nd=0):
    return None if x is None else f"{float(x) * 100:.{nd}f}%"


def _plain_market(k):
    return MARKET_PLAIN.get(k, k)


def _join(items, conj="and"):
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} {conj} {items[-1]}"


# ── the reasons, each tied to a number ───────────────────────────────────

def _breadth_reason(hb: dict) -> str | None:
    regime, pos = hb.get("regime"), hb.get("range_position")
    if not regime:
        return None
    if regime == "narrowing":
        s = "A handful of big names are carrying the index — the average stock is falling behind."
        if pos == "bottom":
            s += (" This has been going on long enough to look tired. Breadth "
                  "is near the bottom of its 12-month range, which is usually "
                  "where it turns.")
    elif regime == "broadening":
        s = "The average stock is keeping up with the index — the rally is broad."
        if pos == "top":
            s += (" Breadth is near the top of its 12-month range, so this "
                  "phase is probably closer to its end than its start.")
    else:
        s = "Breadth is going sideways — neither the big names nor the average stock is leading."
    return s


def _vol_reason(vol: dict) -> str | None:
    disp = vol.get("dispersion") or {}
    state, pctl = disp.get("state"), disp.get("percentile")
    spread, chg = disp.get("spread"), disp.get("spread_20d_change")
    if not state or spread is None:
        return None

    if state == "ELEVATED_RISING":
        s = (f"Single stocks are much more volatile than the index, and the gap "
             f"is still growing. It widened by {abs(chg or 0):.1f} points over "
             f"the last month and is now wider than {_pct(pctl)} of readings in "
             "the past two years. Gaps this wide and still growing have come "
             "before index falls of 5 to 7 percent.")
    elif state == "ELEVATED_EASING":
        s = (f"Single stocks are much more volatile than the index, but the gap "
             f"is closing. It narrowed by {abs(chg or 0):.1f} points over the "
             f"last month, from a level wider than {_pct(pctl)} of the past two "
             "years. The stress is leaving the market rather than building, so "
             "index puts would be late here.")
    elif state.startswith("CALM"):
        s = ("Single stocks are moving no more than the index is. There is "
             "nothing building underneath a calm surface.")
    else:
        s = "Single stocks are moving about as much as the index."

    vix, vpctl = vol.get("vix"), vol.get("vix_percentile")
    if vix is not None:
        s += f" The index itself is quiet, with VIX at {vix:.1f}"
        s += (f", lower than {_pct(1 - (vpctl or 0))} of the past two years."
              if vpctl is not None else ".")
    return s


def _gamma_reason(gam: dict) -> str | None:
    if (gam or {}).get("status") != "OK":
        return None
    if gam.get("regime") == "POSITIVE":
        return ("Option dealers are positioned in a way that damps moves — "
                "rallies get sold into and dips get bought.")
    if gam.get("regime") == "NEGATIVE":
        return ("Option dealers are positioned in a way that amplifies moves — "
                "expect bigger swings in both directions than the news deserves.")
    return None


def gamma_reading(prof: dict) -> dict:
    """One gamma profile, in the words a person would use about it.

    The numbers on their own do not say the thing that matters. "+$1.5bn, flip
    at 776.88, spot 773.92" is three facts; *"pinned while it holds 777, and
    unstable the moment it loses it"* is the read. The distance to the flip is
    what turns a comfortable regime into a knife-edge, and it is the first thing
    a person looks for and the last thing a metric row conveys.
    """
    if not prof or not prof.get("available"):
        return {"headline": None, "lines": [],
                "reason": (prof or {}).get("reason")}

    spot = prof.get("spot")
    gex = prof.get("total_gex") or 0.0
    flip = prof.get("gamma_flip")
    dist = prof.get("flip_distance_pct")
    cw = prof.get("call_wall") or {}
    pw = prof.get("put_wall") or {}
    pos = prof.get("regime") == "POSITIVE"

    lines = []
    if pos:
        headline = "Dealers are long gamma — they sell rallies and buy dips, so moves get damped and price pins."
        lines.append("That is a mean-reversion tape: fade extremes, sell premium, "
                     "do not chase breakouts.")
    else:
        headline = "Dealers are short gamma — they buy rallies and sell dips, so moves get amplified."
        lines.append("Expect bigger swings in both directions than the news "
                     "deserves, and give stops more room than usual.")

    knife = dist is not None and abs(dist) < S.GAMMA_FLIP_NEAR_PCT
    if flip is not None and dist is not None:
        where = "above" if dist > 0 else "below"
        if knife:
            lines.append(
                f"The tipping point sits at {flip:,.2f}, only {abs(dist):.2f}% "
                f"{where} today's price. "
                + ("If the market trades through it, dealers stop damping moves "
                   "and start amplifying them. Treat the calm as fragile."
                   if pos else
                   "If the market trades back through it, dealers stop "
                   "amplifying moves and start damping them."))
        else:
            lines.append(
                f"This holds until {flip:,.2f}, which is {abs(dist):.1f}% "
                f"{where} today's price. Past that level the effect reverses.")

    if cw.get("strike") and pw.get("strike"):
        lines.append(
            f"The heaviest positioning sits at {pw['strike']:,.0f} below and "
            f"{cw['strike']:,.0f} above, holding {pw['share_of_side']:.0%} and "
            f"{cw['share_of_side']:.0%} of each side. Price tends to get pulled "
            "toward those levels, and to move quickly once it clears them.")

    lines.append(
        f"The effect is worth about ${abs(gex) / 1e9:,.2f} billion for every 1% "
        f"the index moves, spread across "
        f"{prof.get('total_open_interest', 0):,} open contracts.")

    return {"headline": headline, "lines": lines, "knife_edge": bool(knife),
            "reason": None}


def _cta_reason(cta: dict) -> str | None:
    bias, n = cta.get("overall_bias"), cta.get("n_markets")
    if not bias or not n:
        return None
    flip = float(cta.get("flip_risk") or 0.0)
    extremes = round(flip * n)
    if bias == "risk_on":
        s = f"Trend-following funds are net long across the {n} markets we track"
    elif bias == "risk_off":
        s = f"Trend-following funds are net short across the {n} markets we track"
    else:
        s = f"Trend-following funds are mixed across the {n} markets we track"
    if extremes:
        s += (f", and {extremes} of those positions are stretched. Crowded "
              "trades unwind quickly, so the size guidance is cut.")
    else:
        s += ", and none is at an extreme — the positioning is not crowded."
    return s


def _cot_reason(cot: dict) -> str | None:
    if (cot or {}).get("status") != "OK":
        return None
    lo = [_plain_market(k) for k in (cot.get("crowded_long") or [])]
    sh = [_plain_market(k) for k in (cot.get("crowded_short") or [])]
    if not lo and not sh:
        return None

    def _cap(names, limit=3):
        """A twelve-item list is not a sentence anyone reads.

        Plain commas when truncating — `_join` would add its own "and" before
        the last name, giving "gold, copper and the dollar and 4 others".
        """
        if len(names) <= limit:
            return _join(names)
        return f"{', '.join(names[:limit])} and {len(names) - limit} others"

    parts = []
    if lo:
        parts.append(f"unusually long {_cap(lo)}")
    if sh:
        parts.append(f"unusually short {_cap(sh)}")
    # Semicolon, not "and" — each clause already contains one.
    return (f"Big speculators are {'; '.join(parts)} "
            f"(CFTC data to {cot.get('as_of')}).")


def _divergence_reason(div: dict) -> str | None:
    fired = div.get("types_fired") or []
    if not fired:
        return "No warning signs are lit — price and everything behind it agree."
    words = [CHECK_PLAIN.get(f, f) for f in fired]
    n = len(fired)
    s = f"{n} warning sign{'s' if n != 1 else ''} lit: {_join(words)}."
    # `weight` also counts hits from the per-market sweeps. Quoting it as the
    # headline count while listing only the named checks reads as a mismatch.
    extra = int(div.get("weight", n)) - n
    if extra > 0:
        s += f" A further {extra} showed up on individual markets."
    return s + (" No single one of these is a reason to sell. They matter when "
                "several point the same way as the breadth reading.")


# ── what would change the answer ─────────────────────────────────────────

def _watch_for(crown: dict, scen: dict) -> list[str]:
    out = []

    # The nearest CTA flip — the level that actually turns mechanical selling on.
    flips = []
    for k, m in (crown.get("cta_markets") or {}).items():
        for f in (m.get("flips") or []):
            if f.get("horizon") == 1 and f.get("level") and f.get("distance_pct") is not None:
                flips.append((abs(f["distance_pct"]), k, f))
    for _d, k, f in sorted(flips)[:2]:
        side = "below" if f.get("direction") == "sell_below" else "above"
        out.append(f"If {_plain_market(k)} trades {side} {f['level']:,.2f} "
                   f"({abs(f['distance_pct']):.1f}% away), trend funds start "
                   f"{'selling' if side == 'below' else 'buying'}.")

    disp = (crown.get("volatility") or {}).get("dispersion") or {}
    if disp.get("state") == "ELEVATED_EASING":
        out.append("Watch for the volatility gap starting to widen again. That "
                   "would turn a fading warning into a live one.")
    elif disp.get("state", "").startswith("NORMAL") or disp.get("band") == "NORMAL":
        out.append("Watch for single stocks becoming more volatile while the "
                   "index stays calm. That gap is the earliest warning we get.")

    hb = crown.get("heartbeat") or {}
    if hb.get("regime") == "narrowing":
        out.append("Watch for the average stock keeping pace with the index "
                   "again. That ends the leadership trade and starts the "
                   "breadth trade.")

    # The leading scenario's own falsifiers, in its own words.
    lead = (scen or {}).get("leading")
    if lead:
        for s in (scen.get("scenarios") or []):
            if s["scenario"] == lead:
                for m in (s.get("missing_conditions") or [])[:2]:
                    out.append(f"This reading would strengthen if {m} reversed.")
                break
    return out[:5]


# ── the whole thing ──────────────────────────────────────────────────────

def explain(crown: dict, scenarios: dict | None = None) -> dict:
    """Turn the finished Crown read into plain English. Pure."""
    crown = crown or {}
    scen = scenarios or {}
    hb = crown.get("heartbeat") or {}
    vol = crown.get("volatility") or {}
    dec = crown.get("decision") or {}
    expr = dec.get("expression") or {}

    if crown.get("crown_status") == "UNAVAILABLE":
        return {
            "headline": "We cannot read the market right now.",
            "regime_words": "unreadable",
            "because": ["The breadth data needed to start the process did not load."],
            "so_what": "No new risk until the data is back.",
            "watch_for": [],
            "caveats": crown.get("degraded") or [],
            "as_of": crown.get("generated_at"),
        }

    if dec.get("early_exit"):
        return {
            "headline": "The market is not readable enough to act on.",
            "regime_words": "no clear regime",
            "because": [
                _breadth_reason(hb) or "Breadth gives no clear signal.",
                "Because that first read is the one everything else depends on, "
                "the process stopped there rather than sizing down into a market "
                "it cannot describe.",
            ],
            "so_what": "No new risk.",
            "watch_for": ["A clearer breadth trend — up or down — restarts the process."],
            "caveats": crown.get("degraded") or [],
            "as_of": crown.get("generated_at"),
        }

    # ── the headline: breadth + what is underneath it ──
    disp = vol.get("dispersion") or {}
    regime = hb.get("regime")
    lead_scen = (scen or {}).get("leading")

    breadth_words = {"narrowing": "A narrow market",
                     "broadening": "A broad market",
                     "neutral": "A market with no clear breadth lead"}.get(regime, "A market")
    if disp.get("band") == "ELEVATED":
        under = ("calm on the surface but with single stocks moving very "
                 "differently underneath")
    elif (vol.get("rules") or {}).get("already_priced"):
        under = "with protection already expensive"
    elif (vol.get("rules") or {}).get("very_low_vix"):
        under = "and quiet"
    else:
        under = "with volatility around normal"
    headline = f"{breadth_words}, {under}."
    if lead_scen:
        headline += f" Best fit: {SCENARIO_PLAIN.get(lead_scen, lead_scen.lower())}."

    because = [r for r in (
        _breadth_reason(hb),
        _vol_reason(vol),
        _gamma_reason(crown.get("gamma") or {}),
        _cta_reason(crown.get("cta") or {}),
        _cot_reason(crown.get("cot") or {}),
        _divergence_reason(crown.get("divergence") or {}),
    ) if r]

    fam = expr.get("family", "NONE")
    mult = dec.get("size_multiplier", 0.0)
    so_what = FAMILY_PLAIN.get(fam, FAMILY_PLAIN["NONE"])
    if fam != "NONE":
        if expr.get("match") == "partial":
            so_what += (f" That is the closest fit rather than a clean one — "
                        f"{len(expr.get('conditions_unmet') or [])} of its "
                        "conditions are not met.")
        so_what += (f" Size at {mult:.2f}x your normal risk"
                    + (" (cut because the trend is crowded)." if mult < 1.0
                       else " (the positioning is clean)." if mult > 1.0 else "."))

    caveats = []
    fresh = crown.get("freshness") or {}
    lag = fresh.get("oldest_leg_days")
    if lag and lag > 5:
        caveats.append(f"The oldest piece of this read is from "
                       f"{fresh.get('oldest_leg')}, {lag} days before "
                       f"{fresh.get('today')} — everything above is only as "
                       "current as that.")
    if (crown.get("gamma") or {}).get("status") != "OK":
        caveats.append("No dealer-positioning read today, so nothing above "
                       "accounts for option hedging flows.")
    if disp.get("basis") == "realised":
        caveats.append("The volatility gap is measured from actual price moves "
                       "rather than option prices today — it lags.")

    return {
        "headline": headline,
        "regime_words": f"{regime or 'unclear'} · {disp.get('state', 'unknown vol')}".lower(),
        "because": because,
        "so_what": so_what,
        "watch_for": _watch_for(crown, scen),
        "caveats": caveats,
        "as_of": crown.get("generated_at"),
        "note": ("Written from the numbers on this page every time it runs. "
                 "When the data changes, this changes with it."),
    }
