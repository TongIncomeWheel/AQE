"""PM 2026-11-17: Valen's 96 baskets + 116 group ETFs replace AQE's 35 for the theme layer; the switch is never silent and the old 35 stay readable."""
import json

import numpy as np
import pandas as pd

from src.valen import baskets as VB
from src.valen import themes as TH


def doc(n=96, per=4, groups=12):
    return {"as_of": "2026-11-13", "source": "test", "baskets": {f"Basket {i:03d}": {"sector": ["Growth", "Defensive", "Commodities"][i % 3],
            "constituents": [f"T{i:03d}{k}" for k in range(per)]} for i in range(n)},
            "groups": [{"ticker": f"G{j:03d}", "name": f"Group {j}", "universe": "Industry groups"} for j in range(groups)]}


def write(tmp_path, d, name="valen_baskets.json"):
    p = tmp_path / name
    p.write_text(json.dumps(d))
    return p


def test_a_valid_file_becomes_the_active_set_with_sectors_and_groups(tmp_path):
    a = VB.load(write(tmp_path, doc()))
    assert a["status"] == "valen" and a["reason"] is None and len(a["baskets"]) == 96 and len(a["groups"]) == 12
    assert a["baskets"]["Basket 001"]["sector"] == "Defensive" and a["baskets"]["Basket 001"]["constituents"][0] == "T0010"
    assert "T0010" in VB.constituents(a) and VB.group_etfs(a)[0] == "G000"


def test_a_missing_or_invalid_file_falls_back_to_the_35_and_says_why_never_silently(tmp_path):
    from src.engines.srm import THEMATIC_BASKETS
    for p, why in ((tmp_path / "nope.json", "not in data"), (write(tmp_path, doc(n=50), "a.json"), "only 50 baskets"), (write(tmp_path, doc(per=2), "b.json"), "under 3 tickers")):
        a = VB.load(p)
        assert a["status"] == "fallback_aqe35" and why in a["reason"] and len(a["baskets"]) == len(THEMATIC_BASKETS) == 35
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert "unreadable" in VB.load(bad)["reason"]


def make_panel(d, n=260, seed=2):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end="2026-11-13", periods=n)
    rows = []
    tick = [(t, 0.004 if i % 2 == 0 else -0.003) for i, t in enumerate(sorted(VB.constituents(VB.load(None)) if False else {t for b in d["baskets"].values() for t in b["constituents"]} | {g["ticker"] for g in d["groups"]}))]
    for t, drift in tick:
        px = 50 * np.cumprod(1 + rng.normal(drift, 0.004, n))
        rows.append(pd.DataFrame({"date": dates, "ticker": t, "open": px, "high": px, "low": px, "close": px, "volume": 1e6}))
    return pd.concat(rows)


def test_the_theme_block_runs_on_the_active_96_with_sector_and_members_and_membership_follows(tmp_path):
    d = doc(n=96, per=4, groups=12)
    a = VB.load(write(tmp_path, d))
    blk = TH.compute_theme_block(make_panel(d), a)
    assert blk["status"] == "OK" and blk["basket_set"]["status"] == "valen" and blk["basket_set"]["n"] == 96 and len(blk["baskets"]) == 96
    b = next(x for x in blk["baskets"] if x["name"] == "Basket 000")
    assert b["sector"] == "Growth" and b["members"] == ["T0000", "T0001", "T0002", "T0003"]
    mem = TH.membership(blk)
    assert [t["name"] for t in mem["T0000"]] == ["Basket 000"] and TH.theme_fields("T0000", mem, True)["themes"][0]["name"] == "Basket 000"


def test_the_group_block_ranks_the_etfs_and_is_loud_when_there_are_none(tmp_path):
    d = doc(n=96, per=4, groups=12)
    a = VB.load(write(tmp_path, d))
    g = TH.compute_group_block(make_panel(d), a)
    assert g["status"] == "OK" and g["n"] == 12 and all(0 <= r["rs_1m"] <= 100 and r["rs_1m"] % 5 == 0 for r in g["groups"])
    assert [r["rs_1m"] for r in g["groups"]] == sorted((r["rs_1m"] for r in g["groups"]), reverse=True)
    assert g["definitions"]["reading"]
    none = TH.compute_group_block(make_panel(d), VB.load(tmp_path / "missing.json"))
    assert none["status"] == "UNAVAILABLE" and "no group ETFs" in none["reason"] and none["groups"] == []        # the fallback has no groups: loud, never an empty table


def test_panel_builder_adds_the_valen_names_and_etfs_as_context_only():
    import inspect
    from src.data import panel_builder as PB
    src = inspect.getsource(PB)
    assert "_vb.constituents(_act)" in src and "_vb.group_etfs(_act)" in src and 'status"] == "valen"' in src
