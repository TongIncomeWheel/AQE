#!/usr/bin/env python3
"""conditions.py -- the shared condition grammar (D123, PM 2026-10-02).

The committee's judgment does not change. What changes is that each analyst writes WHAT WOULD MAKE
THEM ACT and WHAT WOULD PROVE THEM WRONG in words from contracts/condition_vocab.json, which AQE's
live alert engine evaluates word for word. Levels are named by field ("pivot_high"), never typed as
numbers: the tool reads the number from the stamped export, so a level can never be mistyped,
invented, or pinned to the wrong bar.

Used by registrar.py (validate a ballot's `conditions` block) and pma_conditions.py (compile).
Pure functions, no I/O beyond loading the two contract files.
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACTS = os.path.join(HERE, "..", "contracts")
_VOCAB = None
_SEATS = None
LEVEL_RE = re.compile(r"^([a-z_0-9]+?)(?:([+-])(\d+(?:\.\d+)?)(atr|pct))?$")
NON_PRICE_MAX = 200
BLOCK_KEYS = {"lane", "buy", "confirm", "wrong", "wait", "chase", "tf", "non_price"}


def vocab():
    global _VOCAB
    if _VOCAB is None:
        _VOCAB = json.load(open(os.path.join(CONTRACTS, "condition_vocab.json")))
    return _VOCAB


def seat_rules(seat):
    global _SEATS
    if _SEATS is None:
        _SEATS = json.load(open(os.path.join(CONTRACTS, "voice_primitives.json")))
    d = dict(_SEATS["default"])
    d.update({k: v for k, v in (_SEATS["seats"].get(seat) or {}).items() if k != "why"})
    return d


def parse_level(s):
    m = LEVEL_RE.match(s or "")
    if not m or m.group(1) not in vocab()["levels"]:
        return None
    f, sign, n, unit = m.groups()
    return {"field": f, "offset": (float(n) * (1 if sign == "+" else -1)) if n else 0.0, "unit": unit}


def parse(word):
    """'close_below:pivot_high-0.5atr' -> {'w': 'close_below', 'args': [...]} or raises ValueError."""
    if not isinstance(word, str) or not word:
        raise ValueError(f"condition must be a non-empty string, got {word!r}")
    parts = word.split(":")
    w, raw = parts[0], parts[1:]
    spec = vocab()["words"].get(w)
    if spec is None:
        raise ValueError(f"unknown word {w!r} (not in condition_vocab.json)")
    if len(raw) != len(spec["args"]):
        raise ValueError(f"{w} takes {len(spec['args'])} argument(s) {spec['args']}, got {len(raw)} in {word!r}")
    args = []
    for kind, val in zip(spec["args"], raw):
        if kind == "level":
            lv = parse_level(val)
            if lv is None:
                raise ValueError(f"{word!r}: {val!r} is not a level field from the vocabulary "
                                 "(write the field name, e.g. pivot_high or ma_20-0.5atr -- never a number)")
            args.append(lv)
        else:
            try:
                args.append(float(val))
            except ValueError:
                raise ValueError(f"{word!r}: {val!r} must be a number")
    return {"w": w, "args": args, "when": spec["when"], "family": spec["family"], "raw": word}


def validate_block(seat, stance, block, where=""):
    """Return a list of errors for one vote's `conditions` block. SUPPORT must say when it acts and
    when it is wrong; OPPOSE and ABSTAIN may file one (a flip or a watch) but need not."""
    errs, p = [], (where + ": " if where else "")
    rules = seat_rules(seat)
    if block is None:
        if stance == "SUPPORT":
            errs.append(p + "SUPPORT requires a `conditions` block (D123): when you act and when you are wrong, "
                            "in words from condition_vocab.json")
        return errs
    if not isinstance(block, dict):
        return [p + "`conditions` must be an object"]
    extra = set(block) - BLOCK_KEYS
    if extra:
        errs.append(p + f"`conditions` has unknown keys {sorted(extra)}")
    if block.get("lane") not in vocab()["block"]["lane"]:
        errs.append(p + f"conditions.lane must be one of {vocab()['block']['lane']}")
    if block.get("tf") is not None and block.get("tf") not in vocab()["block"]["tf"]:
        errs.append(p + "conditions.tf must be 1H, EOD or W")
    np_ = block.get("non_price")
    if np_ is not None and (not isinstance(np_, str) or len(np_) > NON_PRICE_MAX):
        errs.append(p + f"conditions.non_price must be text <= {NON_PRICE_MAX}")
    parsed = {}
    for key in ("buy", "confirm", "wrong"):
        lst = block.get(key) or []
        if not isinstance(lst, list):
            errs.append(p + f"conditions.{key} must be a list"); continue
        parsed[key] = []
        for wd in lst:
            try:
                parsed[key].append(parse(wd))
            except ValueError as e:
                errs.append(p + f"conditions.{key}: {e}")
    for f in block.get("wait") or []:
        if parse_level(f) is None:
            errs.append(p + f"conditions.wait: {f!r} is not a level field")
    if block.get("chase"):
        try:
            parse(block["chase"])
        except ValueError as e:
            errs.append(p + f"conditions.chase: {e}")
    if stance == "SUPPORT":
        if rules["buy_required"] and not block.get("buy"):
            errs.append(p + "SUPPORT requires conditions.buy: what makes you act")
        if rules["wrong_required"] and not block.get("wrong") and not np_:
            errs.append(p + "SUPPORT requires conditions.wrong (or non_price, for a seat whose exit is not a price)")
    for c in parsed.get("buy", []):
        if c["w"] in rules["forbid_in_buy"]:
            errs.append(p + f"{seat} may not buy on {c['w']!r} -- outside this seat's own method (voice_primitives.json)")
    used = [a["field"] for k in parsed for c in parsed[k] for a in c["args"] if isinstance(a, dict)]
    used += [f for f in (block.get("wait") or [])]
    for f in used:
        base = (parse_level(f) or {}).get("field", f) if isinstance(f, str) else f
        if base in rules["forbid_levels"]:
            errs.append(p + f"{seat} may not use {base} -- outside this seat's own method (voice_primitives.json)")
    return errs


def _row_value(row, field):
    if field == "high_52w_close":
        field = "high_52w"
    v = row.get(field)
    if isinstance(v, dict):
        v = v.get("price")
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def resolve_level(lv, row):
    base = _row_value(row, lv["field"])
    if base is None:
        return None
    if not lv["offset"]:
        return round(base, 4)
    if lv["unit"] == "atr":
        atr = _row_value(row, "atr_14d")
        return None if atr is None else round(base + lv["offset"] * atr, 4)
    return round(base * (1 + lv["offset"] / 100.0), 4)


def resolve(word, row):
    """Attach numbers from the export row. Unresolvable levels come back as None and are DECLARED,
    never guessed."""
    c = parse(word)
    out = {"word": c["raw"], "w": c["w"], "when": c["when"], "family": c["family"], "levels": [], "x": None}
    for a in c["args"]:
        if isinstance(a, dict):
            out["levels"].append({"field": a["field"] + (f"{a['offset']:+g}{a['unit']}" if a["offset"] else ""),
                                  "value": resolve_level(a, row)})
        else:
            out["x"] = a
    out["resolved"] = all(l["value"] is not None for l in out["levels"])
    return out


PLAIN = {
    "close_above": "closes above {L}", "close_below": "closes below {L}",
    "h1_close_above": "an hourly candle closes above {L}", "h1_close_below": "an hourly candle closes below {L}",
    "trade_above": "trades through {L}", "trade_below": "trades under {L}",
    "reclaim": "dips under {L} then closes the hour back above it", "reject": "pokes over {L} then closes the hour back under it",
    "in_zone": "comes back to {L}", "vol_x_ge": "volume at least {x}x normal for the time of day",
    "vol_x_le": "volume at most {x}x normal for the time of day", "above_vwap_s": "holds above today's VWAP",
    "below_vwap_s": "{x} hourly closes under today's VWAP", "rs_today_gt_spy": "outperforms SPY today",
    "fade_atr_ge": "falls {x} ATR off the day's high", "clv_ge": "closes in the top {x} of the day's range",
    "clv_le": "closes in the bottom {x} of the day's range", "red_bar": "closes below its open",
    "elder_le": "elder reading drops to {x} or less", "elder_ge": "elder reading {x} or more",
    "ma_above": "{L} above {L2}", "choch_bearish": "structure turns bearish", "age_ge": "{x} sessions pass without a buy",
}


def plain(r):
    """One resolved condition in plain words, e.g. 'closes below pivot_high 62.15'."""
    L = [f"{l['field']} {l['value']:g}" if l["value"] is not None else f"{l['field']} (not served)" for l in r["levels"]]
    x = r["x"]
    return PLAIN[r["w"]].format(L=L[0] if L else "", L2=L[1] if len(L) > 1 else "",
                                x=(f"{x:g}" if x is not None else ""))
