"""
committee.py — the committee-desk deliberation (Phase 1).

One Opus-tier call on the DATA+LENS-first shortlist (from the conviction funnel, D-80) plus
the contradictions. Corroborate or challenge each name; return verdicts with a mandatory
bear case. Validated against contracts/committee.schema.json.
"""
import os
import json


def _load_committee_card(kernel):
    for p in (os.path.join(kernel, "dist", "claude-plugin", "aegis-v4", "agents", "committee-desk.md"),
              os.path.join(kernel, "skills", "committee-desk", "SKILL.md")):
        if os.path.isfile(p):
            return open(p).read()
    return "(committee-desk card not found)"


def _mock_committee(date, funnel):
    shortlist = funnel.get("convergence_shortlist", [])
    verdicts = []
    for s in shortlist:
        verdicts.append({
            "ticker": s["ticker"],
            "verdict": "ADVANCE" if s.get("class") in ("TRIPLE", "CONFIRMED") else "HOLD-FOR-CONDITIONS",
            "conviction": 4 if s.get("class") == "TRIPLE" else 3,
            "nominators": [],
            "bear_case": f"[MOCK] {s['ticker']} — {s.get('lane_count')}/8 lanes, "
                         f"consensus {s.get('consensus_read')}; deliberate before sizing.",
            "dissent": [],
            "data_anchors": {"lane_count": s.get("lane_count"), "detect": s.get("detect")},
        })
    for c in funnel.get("contradictions", {}).get("consensus_only", []):
        verdicts.append({
            "ticker": c["ticker"], "verdict": "PASS", "conviction": 2, "nominators": [],
            "bear_case": f"[MOCK] {c['ticker']} — {c.get('tension')}", "dissent": [],
            "data_anchors": {"votes": c.get("votes"), "lane_count": c.get("lane_count")},
        })
    return {"date": date,
            "deliberation_set": [s["ticker"] for s in shortlist],
            "verdicts": verdicts,
            "held_verdicts": [], "portfolio_risk_note": "", "sector_exposure_note": ""}


def _validate(comm, kernel):
    try:
        import jsonschema
        jsonschema.validate(comm, json.load(open(os.path.join(kernel, "contracts", "committee.schema.json"))))
        return True, "ok"
    except ImportError:
        req = ["date", "deliberation_set", "verdicts"]
        missing = [k for k in req if k not in comm]
        return (not missing), ("ok" if not missing else f"missing {missing}")
    except Exception as e:
        return False, str(e)


def deliberate(gateway, kernel, date, funnel, out_path):
    """Run the committee on the funnel shortlist + contradictions; write committee.json."""
    card = _load_committee_card(kernel)
    system = card
    user = (f"DATE {date}. SELECTION DOCTRINE (D-80): DATA leads, LENS seconds, VOICES corroborate "
            f"or challenge -> consensus for HIGH CONVICTION. Deliberate the DATA+LENS-first shortlist "
            f"below and RESOLVE each contradiction (run or drop, with reason). Return ONE JSON object "
            f"matching the committee schema (date, deliberation_set[], verdicts[] with ticker, verdict "
            f"ADVANCE/HOLD-FOR-CONDITIONS/PASS, conviction, mandatory bear_case, dissent, data_anchors).\n\n"
            f"FUNNEL (shortlist + contradictions):\n{json.dumps(funnel)[:80000]}")
    mock = json.dumps(_mock_committee(date, funnel))
    raw = gateway.complete("committee", system, user, max_tokens=6000, mock_response=mock)
    comm = gateway.extract_json(raw)
    comm.setdefault("date", date)
    ok, msg = _validate(comm, kernel)
    json.dump(comm, open(out_path, "w"), indent=1)
    return comm, ok, msg
