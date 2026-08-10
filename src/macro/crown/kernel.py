"""§2.1 / §4 / §5 — the decision hierarchy, as sequenced pure functions.

The kernel ships as a LangGraph, but §6 states the intelligence lives in the pure
functions and orchestration "only sequences the pure functions and applies the
conditional gate". So this is that sequence, written plainly — no graph library,
no new dependency, and every step inspectable in a debugger.

The order is not cosmetic (§4):

    1. Heartbeat.                       <- what kind of market is this?
    2. If confidence is low, STOP.      <- the conditional gate
    3. CTA + gamma + dispersion.        <- who is positioned, and how crowded?
    4. Divergences.                     <- where is momentum failing behind price?
    5. Only then, an expression family. <- and only a FAMILY, never a trade.
    6. Apply the size multiplier.

Step 2 is the part most systems skip. A market you cannot read is not a market
you take a smaller position in; it is one where the process stops and nothing
downstream is even computed.

**What this returns, and what it does not.** It returns an allowed *family* of
expressions and a *multiplier* on the PM's own risk budget. It does not size, it
does not pick a ticker, and it does not place anything. Per CLAUDE.md, AQE
exports data and computed levels; the trade call is the PM's.
"""

from __future__ import annotations

from . import spec as S


# ── §3 — the five families, as auditable predicates ───────────────────────
# Each rule lists named conditions. A rule fires when ALL of its conditions hold.
# When none fires cleanly, the best partial match is reported WITH the conditions
# it failed, because "closest family, 3 of 4 conditions" is useful and "NONE" is
# not.

def _conditions(hb: dict, cta: dict, gam: dict, vol: dict, div: dict) -> dict:
    band = ((vol.get("dispersion") or {}).get("band")) if vol else None
    rules = (vol or {}).get("rules", {})
    return {
        "broadening":       hb.get("regime") == "broadening",
        "narrowing":        hb.get("regime") == "narrowing",
        "range_not_extreme": hb.get("range_position") == "mid",
        "gamma_positive":   gam.get("regime") == "POSITIVE",
        "gamma_negative":   gam.get("regime") == "NEGATIVE",
        "dispersion_normal": band in ("NORMAL", "CALM"),
        "dispersion_elevated": band == "ELEVATED",
        # Elevated AND rising. An elevated spread that is unwinding is stress
        # LEAVING the market, and buying downside into it buys the end of the
        # move — so the tactical family needs the direction, not just the level.
        "hidden_stress": bool(rules.get("hidden_stress")),
        "very_low_vix":     bool(rules.get("very_low_vix")),
        "cta_risk_on":      cta.get("overall_bias") == "risk_on",
        "cta_low_flip":     float(cta.get("flip_risk") or 0.0) < S.CTA_FLIP_RISK_LO,
        "cta_high_flip":    float(cta.get("flip_risk") or 0.0) > S.CTA_FLIP_RISK_HI,
        "bearish_divergence": bool(div.get("any_bearish")),
    }


# Priority order. Hidden stress sits first on purpose: §2.4 treats a rising
# dispersion spread as the thing that shows up BEFORE the index admits anything,
# so it must not be outranked by a regime read that still looks healthy.
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("HIDDEN_STRESS_DOWNSIDE",  ("hidden_stress",)),
    ("DIVERGENCE_PAIR_SHORT",   ("bearish_divergence", "narrowing", "cta_high_flip")),
    ("MEAN_REVERSION_PREMIUM",  ("gamma_positive", "very_low_vix", "broadening")),
    ("BROADENING_CARRY",        ("broadening", "range_not_extreme", "gamma_positive",
                                 "dispersion_normal", "cta_low_flip")),
    ("NARROWING_CONCENTRATED",  ("narrowing", "cta_risk_on", "gamma_negative")),
]


def select_expression(hb: dict, cta: dict, gam: dict, vol: dict, div: dict) -> dict:
    """The allowed family, with every condition shown as met or unmet."""
    conds = _conditions(hb, cta, gam, vol, div)

    scored = []
    for name, needed in RULES:
        met = [c for c in needed if conds.get(c)]
        unmet = [c for c in needed if not conds.get(c)]
        scored.append({"family": name, "met": met, "unmet": unmet,
                       "score": len(met) / max(len(needed), 1)})

    exact = [s for s in scored if not s["unmet"]]
    if exact:
        best = exact[0]                 # RULES is already in priority order
        match = "exact"
    else:
        best = max(scored, key=lambda s: (s["score"], -RULES.index(
            next(r for r in RULES if r[0] == s["family"]))))
        match = "partial" if best["score"] > 0 else "none"

    family = best["family"] if match != "none" else "NONE"
    return {
        "family": family,
        "match": match,
        "conditions_met": best["met"],
        "conditions_unmet": best["unmet"],
        "all_conditions": conds,
        "candidates": sorted(scored, key=lambda s: -s["score"]),
        "playbook": S.EXPRESSION_FAMILIES.get(family, S.EXPRESSION_FAMILIES["NONE"]),
    }


# ── §5 — size, from the CTA dial and the family's own ceiling ─────────────

def size_multiplier(cta: dict, family: str) -> dict:
    """The multiplier on the PM's risk budget, and the arithmetic behind it.

    §5 multiplies the CTA dial by 0.7 when flip risk is severe. §3's tactical
    families carry their own ceilings; those are applied as a CAP rather than a
    further multiply, because compounding two independent size opinions
    understates by design rather than by evidence.
    """
    base = float(cta.get("size_adjustment") or S.CTA_SIZE_NEUTRAL)
    steps = [f"CTA dial {base:.2f}"]

    flip = float(cta.get("flip_risk") or 0.0)
    if flip > S.CHECKLIST_FLIP_PENALTY_AT:
        base *= S.CHECKLIST_FLIP_PENALTY
        steps.append(f"x{S.CHECKLIST_FLIP_PENALTY:.2f} (flip risk {flip:.2f} "
                     f"> {S.CHECKLIST_FLIP_PENALTY_AT})")

    cap = None
    if family == "HIDDEN_STRESS_DOWNSIDE":
        cap = S.HIDDEN_STRESS_SIZE
    elif family == "DIVERGENCE_PAIR_SHORT":
        cap = S.DIVERGENCE_PAIR_SIZE
    if cap is not None and base > cap:
        base = cap
        steps.append(f"capped at {cap:.2f} ({family})")

    final = round(min(max(base, S.SIZE_MULT_FLOOR), S.SIZE_MULT_CAP), 2)
    return {"size_multiplier": final, "derivation": " -> ".join(steps),
            "applies_to": "the PM's own risk budget — AQE does not size"}


# ── the run ───────────────────────────────────────────────────────────────

def run(heartbeat: dict, cta_flow: dict, gamma_read: dict, vol_read: dict,
        divergence_read: dict) -> dict:
    """Sequence the hierarchy and return the decision, with its audit trail."""
    messages: list[str] = []
    hb = heartbeat or {}
    conf = float(hb.get("confidence") or 0.0)
    messages.append(f"[Heartbeat] {hb.get('regime')} | conf={conf:.2f} | {hb.get('bias')}")

    # ── the conditional gate (§5 route_after_heartbeat) ──
    if conf < S.HB_CONFIDENCE_GATE:
        messages.append(f"[Early Exit] confidence {conf:.2f} < gate "
                        f"{S.HB_CONFIDENCE_GATE} — process stopped")
        return {
            "checklist_pass": False,
            "early_exit": True,
            "expression": {"family": "NONE", "match": "none",
                           "playbook": S.EXPRESSION_FAMILIES["NONE"],
                           "conditions_met": [], "conditions_unmet": [],
                           "all_conditions": {}, "candidates": []},
            "recommended_structure": "none",
            "size_multiplier": 0.0,
            "size_derivation": "early exit — no new risk",
            "final_rationale": ("Early exit — Heartbeat confidence too low. "
                                "Nothing downstream was computed."),
            "stopped_at": "heartbeat",
            "messages": messages,
        }

    cta = cta_flow or {}
    gam = gamma_read or {}
    vol = vol_read or {}
    div = divergence_read or {}

    messages.append(f"[CTA] {cta.get('overall_bias')} | "
                    f"flip_risk={float(cta.get('flip_risk') or 0.0):.2f} | "
                    f"n={cta.get('n_markets')}")
    messages.append(f"[Gamma] {gam.get('regime')} ({gam.get('status')})")
    disp = vol.get("dispersion") or {}
    messages.append(f"[Vol] VIX={vol.get('vix')} | dispersion {disp.get('band')} "
                    f"({disp.get('basis') or 'n/a'}) | {vol.get('status')}")
    messages.append(f"[Divergence] {div.get('count', 0)} fired: "
                    f"{', '.join(div.get('types_fired') or []) or 'none'}")

    expr = select_expression(hb, cta, gam, vol, div)
    size = size_multiplier(cta, expr["family"])

    # §5 node_checklist: narrowing regimes prefer a pair, everything else is
    # directional. The family already says more than this; it is kept because the
    # kernel names it and the committee reads it.
    structure = "pair" if hb.get("regime") == "narrowing" else "directional"
    if expr["family"] in ("HIDDEN_STRESS_DOWNSIDE", "MEAN_REVERSION_PREMIUM"):
        structure = "options"

    passed = conf >= S.HB_CONFIDENCE_GATE and expr["match"] != "none"
    messages.append(f"[Expression] {expr['family']} ({expr['match']}) | "
                    f"size x{size['size_multiplier']:.2f}")
    messages.append(f"[Checklist] {'PASSED' if passed else 'FAILED'}")

    return {
        "checklist_pass": bool(passed),
        "early_exit": False,
        "expression": expr,
        "recommended_structure": structure,
        "size_multiplier": size["size_multiplier"],
        "size_derivation": size["derivation"],
        "final_rationale": (f"{hb.get('bias')} | CTA={cta.get('overall_bias')} | "
                            f"gamma={gam.get('regime')} | "
                            f"dispersion={disp.get('band')} | "
                            f"size={size['size_multiplier']:.2f}"),
        "stopped_at": None,
        "messages": messages,
    }
