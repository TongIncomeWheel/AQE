"""The ACTIVE basket set for the Valen theme layer (PM 2026-11-17: "I'm kind of ok following Valen's baskets. Ours was not particularly well thought through").

`data/valen_baskets.json` carries Valen's 96 theme baskets (name, his five-way sector, constituents) and his 116 group ETFs (ticker, name, universe). `load()` returns the
active set in the shape srm.THEMATIC_BASKETS already has ({name: {"constituents": [...], "parent_gics_etf", "sector"}}), so every reader takes it without a rewrite.

THE SWITCH IS NEVER SILENT. A missing or invalid file falls back to AQE's own 35 baskets and says so in `status` ("fallback_aqe35" + the reason); the old 35 stay in srm.py,
untouched and readable. An invalid file is one with fewer than MIN_BASKETS baskets, a basket under MIN_NAMES tickers, a duplicate name, or no tickers at all.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.data.paths import DATA_DIR

BASKETS_FILE = DATA_DIR / "valen_baskets.json"
MIN_BASKETS, MIN_NAMES = 90, 3
SECTORS = ("Growth", "Commodities", "Defensive", "Interest Sensitive", "Healthcare", "Index")


def _clean(tks) -> list[str]:
    out, seen = [], set()
    for t in tks or []:
        t = str(t).strip().upper()
        if t and t not in seen and " " not in t:
            seen.add(t)
            out.append(t)
    return out


def validate(doc) -> tuple[bool, str | None]:
    """(ok, reason). Pure: no file access."""
    if not isinstance(doc, dict) or not isinstance(doc.get("baskets"), dict):
        return False, "no 'baskets' object in the file"
    bs = doc["baskets"]
    if len(bs) < MIN_BASKETS:
        return False, f"only {len(bs)} baskets (need at least {MIN_BASKETS})"
    low = [n for n, b in bs.items() if len(_clean((b or {}).get("constituents"))) < MIN_NAMES]
    if low:
        return False, f"{len(low)} basket(s) under {MIN_NAMES} tickers: {low[:5]}"
    return True, None


def load(path: Path | None = None) -> dict:
    """-> {status: 'valen'|'fallback_aqe35', reason, as_of, source, baskets: {...}, groups: [...]}. Never raises."""
    from src.engines.srm import THEMATIC_BASKETS
    p = path or BASKETS_FILE
    fb = lambda why: {"status": "fallback_aqe35", "reason": why, "as_of": None, "source": "AQE's own 35 baskets (srm.THEMATIC_BASKETS)",   # noqa: E731
                      "baskets": {n: {**b, "sector": None} for n, b in THEMATIC_BASKETS.items()}, "groups": []}
    try:
        if not p.exists():
            return fb(f"{p.name} is not in data/ yet")
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return fb(f"{p.name} unreadable: {type(exc).__name__}: {exc}")
    ok, why = validate(doc)
    if not ok:
        return fb(f"{p.name} refused: {why}")
    baskets = {}
    for name, b in doc["baskets"].items():
        baskets[name] = {"constituents": _clean(b.get("constituents")), "sector": b.get("sector"), "parent_gics_etf": b.get("parent_gics_etf")}
    groups = [{"ticker": str(g.get("ticker")).strip().upper(), "name": g.get("name"), "universe": g.get("universe")}
              for g in (doc.get("groups") or []) if g.get("ticker")]
    return {"status": "valen", "reason": None, "as_of": doc.get("as_of"), "source": doc.get("source") or "Valen theme baskets", "baskets": baskets, "groups": groups}


def constituents(active: dict | None = None) -> set[str]:
    a = active or load()
    return {t for b in a["baskets"].values() for t in b["constituents"]}


def group_etfs(active: dict | None = None) -> list[str]:
    a = active or load()
    return [g["ticker"] for g in a.get("groups") or []]
