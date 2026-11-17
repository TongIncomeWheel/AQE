"""PM 2026-11-17: the theme-block table on the Valen page and the stop-fit / theme columns in the Scanner signals table (plain tables only)."""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))


def test_scanner_flattens_stop_fit_and_themes_into_plain_columns_and_lists_them():
    src = (ROOT / "src" / "ui" / "1_Scanner.py").read_text()
    i, j = src.index("def _flatten_valen"), src.index("def _flatten_qs")
    ns = {}
    exec(src[i:j], ns)
    df = pd.DataFrame({"stop_fit": [{"fit": "GOOD", "atr_multiple": 0.5, "lod_dist_atr": 0.4}, None],
                       "themes": [[{"name": "AI_Software", "bullish": True, "sessions_on": 4, "rs_1m": 45}], []]})
    out = ns["_flatten_valen"](df)
    assert out.loc[0, "stop_fit"] == "GOOD" and out.loc[0, "stop_atr_multiple"] == 0.5 and out.loc[0, "lod_dist_atr"] == 0.4
    assert out.loc[0, "themes_text"] == "AI Software (bullish 4, RS 45)" and out.loc[1, "themes_text"] == "none"      # read, in no basket
    assert pd.isna(out.loc[1, "stop_atr_multiple"])                                                                 # not read stays blank, never 0
    for col in ("stop_fit", "stop_atr_multiple", "lod_dist_atr", "in_leading_theme", "themes_text", "dryup_45", "dryup_60"):
        assert f'"{col}"' in src[src.index("_EXPORT_COL_ORDER = ["):src.index("def _flatten_valen")]


def test_the_valen_page_renders_the_theme_table_without_an_exception(monkeypatch):
    from streamlit.testing.v1 import AppTest
    import test_valen_themes as TV
    from src.valen import daily as D
    from src.valen import themes as TH
    blk = TH.compute_theme_block(TV.make_panel({TV.UP: 0.006, TV.DOWN: -0.006, TV.FLAT1: 0.0, TV.FLAT2: 0.0}))
    art = json.loads((ROOT / "tests" / "fixtures" / "cards_v3" / "aqe_valen_dashboard.json").read_text())
    for k, v in list(art.items()):                         # the published form lists what the full local artifact keys; the page reads a missing key as UNAVAILABLE
        if isinstance(v, list):
            art[k] = {}
    art["groups"] = {"status": "OK", "reason": None, "groups": [], "theme_leaders": {}, "rotation": [], "themes": blk}
    monkeypatch.setattr(D, "load_valen", lambda: art)
    at = AppTest.from_file(str(ROOT / "src" / "ui" / "pages" / "7_VALEN_Dashboard.py")).run(timeout=120)
    texts = " ".join(x.value for x in at.subheader) + " ".join(x.value for x in at.caption)
    assert not at.exception, at.exception
    assert "Themes: bullish baskets" in texts and "baskets are bullish" in texts
