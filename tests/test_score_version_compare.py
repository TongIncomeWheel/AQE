import pandas as pd
import pytest

from scripts import score_version_compare as C

REC = {"sc_mom_min": 75, "flow_min": 80, "energy_min": 64, "structure_min": 60, "mp_min": 60, "elder_min": 7}


def _frame():
    rows = []
    for t, old, new in [("AAA", (80, 85, 70, 65, 65, 8), (80, 85, 70, 65, 65, 8)),        # in both
                        ("BBB", (80, 85, 70, 65, 65, 8), (70, 85, 70, 65, 65, 8)),        # dropped: SC falls under 75
                        ("CCC", (70, 85, 70, 65, 65, 8), (80, 85, 70, 65, 65, 8)),        # added
                        ("DDD", (80, 85, 70, 65, 65, 9), (None, None, None, None, None, None))]:     # new calculation cannot score it: NaN never passes
        r = {"date": "2026-11-20", "ticker": t}
        for k, v in zip(["sc_momentum", "flow_100", "energy_100", "structure_100", "mp_100", "elder_score"], old):
            r[k + "_legacy"] = v
        for k, v in zip(["sc_momentum", "flow_100", "energy_100", "structure_100", "mp_100", "elder_score"], new):
            r[k] = v
        rows.append(r)
    return pd.DataFrame(rows).astype({c: float for c in pd.DataFrame(rows).columns if c not in ("date", "ticker")})


def test_added_and_dropped_names_for_the_same_date_and_nan_never_passes():
    out = C.compare(_frame(), "2026-11-20", "_legacy", "", REC)
    ll = out["longlist"]
    assert ll["old_count"] == 3 and ll["new_count"] == 2 and ll["in_both"] == 1
    assert ll["added_by_new"] == ["CCC"] and ll["dropped_by_new"] == ["BBB", "DDD"] and ll["overlap_of_old_pct"] == 33.3
    assert out["elder"]["old_count"] == 4 and out["elder"]["new_count"] == 3 and out["elder"]["dropped_by_new"] == ["DDD"]


def test_the_v2_suffix_maps_the_mp_twin_name_and_a_missing_date_is_loud():
    assert C._col("mp_100", "_v2") == "mp_score_v2" and C._col("flow_100", "_v2") == "flow_100_v2" and C._col("flow_100", "_legacy") == "flow_100_legacy"
    with pytest.raises(SystemExit, match="no rows"):
        C.compare(_frame(), "2020-01-01", "_legacy", "", REC)
