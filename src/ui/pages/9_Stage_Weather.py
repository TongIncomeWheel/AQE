"""Stage Weather — Weinstein's four-stage market cycle, read on weekly bars.

Market (SPY/QQQ) -> the 11 GICS sectors -> breadth across every single name on
AQE's panel -> the held book and daily_list names changing stage. Plain
tables only. The page owns no maths: everything comes from the nightly
artifact (`output/stage_weather.json`, written by daily Step 8a-1c), with a
button to recompute it from the panel on disk if it's missing.

A reading, never a gate or a size (AQE makes no decisions). Full doc:
docs/AQE_STAGE_WEATHER.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Stage Weather", page_icon=":partly_sunny:", layout="wide")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.shared import require_login, table_with_copy  # noqa: E402

require_login()

import pandas as pd  # noqa: E402

from src.stages import daily as D  # noqa: E402
from src.stages import spec as S  # noqa: E402

st.title("Stage Weather: the four-stage cycle")
st.caption("Stage 1 Basing (accumulation) → Stage 2 Advancing (mark-up) → Stage 3 Topping "
           "(distribution) → Stage 4 Declining (mark-down). Weekly bars, 30-week average. "
           "A reading, never a gate or a size.")

art = D.load_stage_weather()
if st.button("Recompute from the panel on disk"):
    with st.spinner("Reading every weekly series..."):
        art = D.run_stage_weather()
        D.write_artifacts(art)
if art is None:
    st.error("No Stage Weather read on disk yet. It is written by the daily pipeline "
             "(Step 8a-1c); use the button above to compute it now.")
    st.stop()

pe = art.get("plain_english") or {}
if art.get("status") != "OK":
    st.warning(f"Stage Weather status: {art.get('status')} - "
               f"{art.get('reason') or (art.get('breadth') or {}).get('reason') or ''}")
st.subheader(pe.get("headline") or "")
for line in pe.get("because") or []:
    st.markdown(f"- {line}")
if pe.get("so_what"):
    st.info(pe["so_what"])
for line in pe.get("watch_for") or []:
    st.markdown(f"- **Watch:** {line}")
for line in pe.get("caveats") or []:
    st.caption(line)
st.caption(f"As of session {art.get('as_of_session')} · written {art.get('exported_at')}")

_COLS = ["stage", "stage_name", "since", "weeks_in_stage", "candidate", "candidate_forming",
         "pct_from_ma30w", "ma30w", "ma30w_slope_pct_4w", "rs_mansfield", "rs_rising",
         "updown_volume_ratio", "range_pos_52w", "transition", "status", "reason"]


def _table(rows: dict) -> pd.DataFrame:
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "ticker"
    return df[[c for c in _COLS if c in df.columns]].reset_index()


st.header("Market")
table_with_copy(_table(art.get("market") or {}), key="sw_market")

st.header("Sectors (GICS)")
_sec = _table(art.get("sectors") or {})
if {"stage", "rs_mansfield"} <= set(_sec.columns):
    _sec = _sec.sort_values(["stage", "rs_mansfield"], ascending=[True, False])
table_with_copy(_sec, key="sw_sectors")

st.header("Breadth: share of single names in each stage")
b = art.get("breadth") or {}
if b.get("status") == "OK":
    rows = []
    for label, k in (("Now", "now"), ("1 week ago", "one_week_ago"), ("4 weeks ago", "four_weeks_ago")):
        r = b[k]
        rows.append({"when": label, "n": r["n"],
                     **{f"Stage {s} %": r[f"stage_{s}_pct"] for s in S.STAGES}})
    table_with_copy(pd.DataFrame(rows), key="sw_breadth", filterable=False)
    st.caption(f"Stage 2 share {b.get('stage_2_direction')}, Stage 4 share {b.get('stage_4_direction')} "
               f"vs 4 weeks ago. Population: {b.get('population')} ({b.get('n_na')} names too short to read).")
else:
    st.warning(f"Breadth unavailable: {b.get('reason')}")

st.header("Held book")
st.caption(art.get("held_status") or "")
if art.get("held"):
    table_with_copy(_table(art["held"]), key="sw_held")
else:
    st.warning("No held positions read from the export this run.")

st.header("Daily list names changing stage")
st.caption(art.get("daily_list_status") or "")
ch = art.get("daily_list_changes") or []
if ch:
    table_with_copy(pd.DataFrame(ch), key="sw_dl_changes")
else:
    st.write("None this week.")

st.header("Every name on the panel")
bt = art.get("by_ticker") or {}
if bt:
    table_with_copy(pd.DataFrame.from_dict(bt, orient="index").rename_axis("ticker").reset_index(),
                    key="sw_all")
