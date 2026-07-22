"""
voices.py — spawn the 11 voices in parallel, each ISOLATED (Phase 1).

Each voice = one model call: its methodology card + its trimmed per-voice universe +
its memory stub -> a nomination.json, VALIDATED against contracts/nomination.schema.json.
This is the judgment plane on the API. Anti-anchoring is preserved: each call is a fresh
context, no voice sees another's output (constitution / D-5 / D-16).
"""
import os
import json
import asyncio

VOICES = ["lynch", "oneil", "wyckoff", "raschke", "steenbarger", "thorp",
          "seow", "minervini", "druckenmiller", "detect-lens", "elder-lens"]


def _load_card(kernel, voice):
    """Voice methodology card: prefer the compiled agent card, else compose from skills."""
    compiled = os.path.join(kernel, "dist", "claude-plugin", "aegis-v4", "agents", f"voice-{voice}.md")
    if os.path.isfile(compiled):
        return open(compiled).read()
    common = os.path.join(kernel, "skills", "voice-common", "SKILL.md")
    card = os.path.join(kernel, "skills", f"voice-{voice}", "SKILL.md")
    txt = ""
    for p in (common, card):
        if os.path.isfile(p):
            txt += open(p).read() + "\n\n"
    return txt or f"(voice {voice} card not found)"


def _universe_for(kernel, date, voice):
    path = os.path.join(kernel, "data", "sod", date, f"universe_{voice}.json")
    if not os.path.isfile(path):
        return None
    return json.load(open(path))


def _compact_names(universe, cap=60):
    """Trim the per-voice universe to a compact names list to keep tokens sane."""
    names = universe.get("names", universe) if isinstance(universe, dict) else universe
    return names[:cap] if isinstance(names, list) else []


def _validate(nom, kernel):
    schema_path = os.path.join(kernel, "contracts", "nomination.schema.json")
    try:
        import jsonschema
        jsonschema.validate(nom, json.load(open(schema_path)))
        return True, "ok"
    except ImportError:
        # fall back to a minimal required-keys check if jsonschema absent
        req = ["voice", "date", "nominations", "held_review"]
        missing = [k for k in req if k not in nom]
        return (not missing), ("ok" if not missing else f"missing {missing}")
    except Exception as e:
        return False, str(e)


def _mock_nomination(voice, date, names, idx=0):
    """A plausible, schema-valid nomination for offline mock runs. Each voice takes a
    DIFFERENT window of the sc_momentum-ranked names (spread + overlap) so the mock tally
    is realistic — distinct names, real consensus, a genuine shortlist downstream."""
    ranked = sorted([n for n in names if isinstance(n, dict)],
                    key=lambda n: n.get("sc_momentum") or 0, reverse=True)
    offset = (idx % 6) * 4
    window = ranked[offset:offset + 6] or ranked[:6]
    noms = []
    for i, n in enumerate(window):
        noms.append({
            "ticker": n.get("ticker"),
            "reason": f"[MOCK {voice}] top-momentum candidate from my universe",
            "fields_cited": ["sc_momentum", "structure", "flow"],
            "conviction": max(1, 4 - i),
            "price_at_nomination": n.get("entry"),
            "field_values": {k: n.get(k) for k in ("sc_momentum", "structure", "flow") if k in n},
        })
    return {"voice": voice, "date": date, "universe_file": f"universe_{voice}.json",
            "nominations": noms, "held_review": [], "data_gaps": []}


def _run_one(gateway, kernel, date, voice, idx=0):
    universe = _universe_for(kernel, date, voice)
    if universe is None:
        return voice, None, f"no universe_{voice}.json for {date}"
    names = _compact_names(universe)
    card = _load_card(kernel, voice)
    system = card
    user = (f"DATE {date}. You are the '{voice}' voice, in isolation. Nominate up to 10 names "
            f"ONLY from this universe, per your methodology. Return ONE JSON object matching the "
            f"nomination schema (keys: voice,date,nominations[],held_review). Each nomination: "
            f"ticker, reason, fields_cited[], conviction 1-5, price_at_nomination, field_values{{}}.\n\n"
            f"UNIVERSE (names):\n{json.dumps(names)[:60000]}")
    mock = json.dumps(_mock_nomination(voice, date, names, idx))
    raw = gateway.complete("voices", system, user, max_tokens=3000, mock_response=mock)
    try:
        nom = gateway.extract_json(raw)
    except Exception as e:
        return voice, None, f"parse failed: {e}"
    nom.setdefault("voice", voice)
    nom.setdefault("date", date)
    nom.setdefault("held_review", [])
    ok, msg = _validate(nom, kernel)
    return voice, (nom if ok else None), msg


async def run_swarm(gateway, kernel, date, out_dir):
    """Run all 11 voices concurrently; write each nomination; return {voice: nomination}."""
    os.makedirs(out_dir, exist_ok=True)
    tasks = [asyncio.to_thread(_run_one, gateway, kernel, date, v, i) for i, v in enumerate(VOICES)]
    results = await asyncio.gather(*tasks)
    noms = {}
    for voice, nom, msg in results:
        status = "OK" if nom else "SKIP"
        print(f"  voice {voice:14} {status}  ({msg})")
        if nom:
            noms[voice] = nom
            json.dump(nom, open(os.path.join(out_dir, f"{voice}.json"), "w"), indent=1)
    return noms
