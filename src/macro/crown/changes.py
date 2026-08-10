"""What changed since the last run.

Crown's letter is built around shifts: *"the biggest macro shift came from the
labour market"*, *"our model already flipped on metals"*. A regime read that
only ever states today's position makes the reader do that work themselves,
from memory, which is exactly the job software should be doing.

So this diffs today's Crown read against the previous one and reports only what
MOVED. Silence is a real answer here — "nothing changed" is information, and a
list padded with unchanged fields would bury the one line that matters.

The comparison is deliberately narrow. Every number moves a little every day;
only a handful of moves change what a PM would do:

  * the breadth regime flipping, or reaching a range extreme
  * the volatility gap changing state, especially elevated-rising to
    elevated-easing, which reverses the trade
  * the trend-following bias flipping, or crowding crossing the size threshold
  * dealer gamma changing sign
  * a market crossing its flip level between runs
  * positioning becoming crowded, or ceasing to be

Anything smaller is noise dressed as news.
"""

from __future__ import annotations


def _fmt(x, nd=2):
    return "—" if x is None else f"{float(x):,.{nd}f}"


def diff(today: dict, previous: dict | None) -> dict:
    """What moved between two Crown reads, in plain sentences."""
    if not previous:
        return {"available": False, "changes": [],
                "note": "No previous run to compare against — this is the "
                        "first reading on record."}

    out: list[str] = []
    t_hb, p_hb = today.get("heartbeat") or {}, previous.get("heartbeat") or {}
    t_vol, p_vol = today.get("volatility") or {}, previous.get("volatility") or {}
    t_disp = t_vol.get("dispersion") or {}
    p_disp = p_vol.get("dispersion") or {}
    t_cta, p_cta = today.get("cta") or {}, previous.get("cta") or {}
    t_gam, p_gam = today.get("gamma") or {}, previous.get("gamma") or {}
    t_cot, p_cot = today.get("cot") or {}, previous.get("cot") or {}
    t_dec = (today.get("decision") or {}).get("expression") or {}
    p_dec = (previous.get("decision") or {}).get("expression") or {}

    # ── breadth ──
    if t_hb.get("regime") != p_hb.get("regime") and p_hb.get("regime"):
        out.append(f"Breadth flipped from {p_hb['regime']} to "
                   f"{t_hb.get('regime')}. This is the reading everything else "
                   "is gated on, so treat the rest of today's report as a new "
                   "starting point rather than an update.")
    elif (t_hb.get("range_position") != p_hb.get("range_position")
          and t_hb.get("range_position") in ("top", "bottom")):
        out.append(f"Breadth reached the {t_hb['range_position']} of its "
                   "12-month range, which is usually where the current phase "
                   "runs out.")

    # ── volatility ──
    if t_disp.get("state") != p_disp.get("state") and p_disp.get("state"):
        pair = (p_disp["state"], t_disp.get("state"))
        if pair == ("ELEVATED_RISING", "ELEVATED_EASING"):
            out.append("The volatility gap stopped widening and began to close. "
                       "That reverses the downside trade: stress is leaving "
                       "rather than building.")
        elif pair == ("ELEVATED_EASING", "ELEVATED_RISING"):
            out.append("The volatility gap started widening again. This is the "
                       "version that warns, and it is the one worth acting on.")
        else:
            out.append(f"The volatility gap moved from {pair[0]} to {pair[1]}.")

    # ── trend followers ──
    if t_cta.get("overall_bias") != p_cta.get("overall_bias") and p_cta.get("overall_bias"):
        out.append(f"Trend-following funds turned from {p_cta['overall_bias']} "
                   f"to {t_cta.get('overall_bias')} across the markets we read.")
    t_fr, p_fr = t_cta.get("flip_risk"), p_cta.get("flip_risk")
    if t_fr is not None and p_fr is not None:
        from . import spec as SP
        if (p_fr <= SP.CTA_FLIP_RISK_HI) and (t_fr > SP.CTA_FLIP_RISK_HI):
            out.append(f"Trend positioning became crowded ({t_fr:.0%} of "
                       "markets at an extreme), so the size guidance is cut.")
        elif (p_fr > SP.CTA_FLIP_RISK_HI) and (t_fr <= SP.CTA_FLIP_RISK_HI):
            out.append("Trend positioning is no longer crowded, so the size "
                       "guidance is restored.")

    # ── dealer gamma ──
    if (t_gam.get("status") == "OK" and p_gam.get("status") == "OK"
            and t_gam.get("regime") != p_gam.get("regime")):
        out.append(f"Dealer gamma flipped to {t_gam.get('regime')}. "
                   + ("Moves should be damped from here."
                      if t_gam.get("regime") == "POSITIVE" else
                      "Expect wider swings from here."))

    # ── markets that crossed their own flip ──
    p_marks = previous.get("cta_markets") or {}
    for key, m in (today.get("cta_markets") or {}).items():
        pm = p_marks.get(key) or {}
        ts, ps = m.get("signal"), pm.get("signal")
        if ts is None or ps is None:
            continue
        if (ts > 0) != (ps > 0):
            out.append(f"{m.get('label', key)} crossed its trend flip — the "
                       f"model turned {'long' if ts > 0 else 'short'}.")

    # ── positioning ──
    for side, word in (("crowded_long", "crowded long"),
                       ("crowded_short", "crowded short")):
        new = set(t_cot.get(side) or []) - set(p_cot.get(side) or [])
        gone = set(p_cot.get(side) or []) - set(t_cot.get(side) or [])
        if new:
            out.append(f"Large speculators became {word} {', '.join(sorted(new))}.")
        if gone:
            out.append(f"Large speculators are no longer {word} "
                       f"{', '.join(sorted(gone))}.")

    # ── the call itself ──
    if t_dec.get("family") != p_dec.get("family") and p_dec.get("family"):
        out.append(f"The allowed family changed from "
                   f"{p_dec['family'].replace('_', ' ').lower()} to "
                   f"{str(t_dec.get('family')).replace('_', ' ').lower()}.")

    return {
        "available": True,
        "compared_with": previous.get("generated_at"),
        "changes": out,
        "count": len(out),
        "note": ("Only moves that would change what a PM does. Nothing here "
                 "means today's reading is a continuation of the last one."),
    }
