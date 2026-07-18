"""Agentic AQE — the agent-facing data-contract view (additive tab, D-24/D-29).

Purely additive Streamlit page. Does NOT touch any production page, export, or
calculation. It surfaces, for the agentic consumer (Aegis), the complete data
contract AQE serves: every field's definition, method, and enum, the subcomponent
tree, and live coverage — so the voices read understanding, not bare numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.engines import agentic_dictionary as ad

st.set_page_config(page_title="AQE — Agentic AQE", layout="wide")
st.title("Agentic AQE")
st.caption("The data contract AQE serves to the agentic system (Aegis). Additive view — production unaffected.")

# Load the latest daily export (whatever the production pipeline last wrote).
export = None
for p in [ROOT / "output" / "aqe_daily_export.json", ROOT / "data" / "aqe_daily_export.json"]:
    if p.exists():
        export = json.loads(p.read_text())
        break

if export is None:
    st.warning("No aqe_daily_export.json found in output/ or data/. Run the daily pipeline first.")
    st.stop()

ad.augment_export(export)          # non-destructive: fills glossary + enums in the loaded copy
cov = ad.coverage(export)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Fields in record", cov["total_fields"])
c2.metric("Glossary covered", f'{cov["glossary_covered"]}/{cov["total_fields"]}')
c3.metric("Enum fields published", cov["enum_fields"])
c4.metric("Still undocumented", len(cov["undocumented"]))
if cov["undocumented"]:
    st.error("AQE owner to define: " + ", ".join(cov["undocumented"]))

st.subheader("Field dictionary (definition · enum)")
row = next((r for r in export["daily_list"] if isinstance(r, dict)), {})
fg = export["field_glossary"]; fse = export["field_schema_enums"]
recs = []
for f in sorted(k for k in row if not k.startswith("_")):
    recs.append({
        "field": f,
        "definition": fg.get(f, "— (gap)"),
        "enum": ", ".join(fse[f]) if f in fse else "",
    })
st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)

st.subheader("Subcomponent tree (behind each composite)")
for eng, doc in export["_agentic_subcomponent_docs"].items():
    st.markdown(f"**{eng}** — {doc}")

st.subheader("Export the agentic dictionary")
st.download_button("Download field_dictionary.json",
                   json.dumps({"fields": {f: {"definition": fg.get(f, ""), "enum": fse.get(f)} for f in row if not f.startswith("_")},
                               "subcomponents": export["_agentic_subcomponent_docs"]}, indent=1),
                   file_name="field_dictionary.json", mime="application/json")
