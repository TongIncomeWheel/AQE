"""VALEN House — the VIV handbook's Part 3 (pieces 08-12), the five chart
setups. No new pattern-detection math anywhere in this file: every
classification reads a field AQE's own DETECT/lens engines already stamp
onto `daily_list` rows. Pure functions of an already-loaded list.

Piece-by-piece source (see the field inventory in
docs/AQE_VALEN_DASHBOARD_PROPOSAL.md's follow-ups for the full trace):
  08 VCP              -> elder_context.vcp.vcp_label (already computed,
                         just not previously surfaced at the top level).
  09 Momentum breakout -> mover_subtype in (trend, tight_base) OR
     / high tight flag    squeeze_breakout_state == BREAKOUT_UP.
  10 Undercut & rally  -> pin_bar_state == BULLISH_PIN, or a bullish
                         divergence confirmed by a break of structure up.
  11 Episodic pivot    -> premove_setup (Signal Radar's "quiet name"
                         test) + mover_subtype == explosive. TECHNICAL
                         FINGERPRINT ONLY: AQE has no news/catalyst feed,
                         so this can never confirm the handbook's actual
                         "surprise catalyst" half — labelled as such,
                         every time, never presented as a confirmed EP.
  12 Parabolic short   -> energy.py's exhaustion_score dropping below its
     & breakdown          10.0 baseline (only activates after a mature,
                         sustained run — the handbook's own "only after
                         the top is in" gate is already built into the
                         engine). Reframed here as a RISK WARNING on an
                         existing long holding, never a short signal —
                         AQE's scan universe and charter are long-only;
                         nothing in this file recommends shorting.
"""

from __future__ import annotations

from . import spec as S


def classify_setups(row: dict) -> list[dict]:
    tags = []

    vcp = ((row.get("elder_context") or {}).get("vcp") or {})
    vcp_label = vcp.get("vcp_label")
    if vcp_label == "VCP_SETUP":
        tags.append({"piece": "08", "name": "VCP",
                    "detail": "Volatility contraction tightening into a pivot"})
    elif vcp_label == "VCP_PARTIAL":
        tags.append({"piece": "08", "name": "VCP (forming)",
                    "detail": "Contracting, not yet tight enough to trigger"})

    if row.get("mover_subtype") in ("trend", "tight_base") \
            or row.get("squeeze_breakout_state") == "BREAKOUT_UP":
        tags.append({
            "piece": "09", "name": "Momentum breakout / high tight flag",
            "detail": f"mover_subtype={row.get('mover_subtype')}, "
                     f"squeeze_breakout_state={row.get('squeeze_breakout_state')}",
        })

    bullish_reclaim = (row.get("div_state") == "BULLISH"
                      and row.get("structure_shift") == "BULLISH_BOS")
    if row.get("pin_bar_state") == "BULLISH_PIN" or bullish_reclaim:
        tags.append({
            "piece": "10", "name": "Undercut and rally",
            "detail": f"pin_bar_state={row.get('pin_bar_state')}, "
                     f"div_state={row.get('div_state')}",
        })

    if row.get("premove_setup") and row.get("mover_subtype") == "explosive":
        tags.append({
            "piece": "11", "name": "Episodic pivot — technical fingerprint only",
            "detail": "Quiet name + an explosive move — AQE has no catalyst/news "
                     "feed, so this cannot confirm the actual surprise; read it "
                     "as the shape, not a confirmed EP.",
        })

    exhaustion = ((row.get("subcomponents") or {}).get("energy") or {}).get(
        "exhaustion_score")
    if exhaustion is not None and exhaustion < S.EXHAUSTION_SCORE_WATCH_BELOW:
        tags.append({
            "piece": "12", "name": "Exhaustion / blow-off risk",
            "detail": f"exhaustion_score={exhaustion} (of {S.EXHAUSTION_SCORE_MAX}, "
                     f"only active after a sustained run) — a risk flag on an "
                     f"existing long, not a short signal; structure_shift="
                     f"{row.get('structure_shift')}, div_state={row.get('div_state')}",
        })

    return tags


def house_setups(daily_list: list[dict], only_candidates: bool = True) -> list[dict]:
    """Every ticker (candidates by default, or held positions too if the
    caller passes held rows in) carrying 1+ setup tags."""
    rows = daily_list
    if only_candidates:
        rows = [r for r in daily_list
               if r.get("on_longlist") or r.get("on_elder") or r.get("on_qs")
               or r.get("held")]
    out = []
    for r in rows:
        tags = classify_setups(r)
        if tags:
            out.append({"ticker": r.get("ticker"), "setups": tags})
    return out
