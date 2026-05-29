"""Streamlit Cloud entrypoint for AQE.

Streamlit Cloud looks for `streamlit_app.py` at the repo root. This shim does
two things before handing off to the multi-page app:

1. Bridges `st.secrets["FMP_API_KEY"]` (the cloud's secret store) into
   `os.environ["FMP_API_KEY"]` so the existing `FMPClient` -- which reads from
   `os.environ` -- works unchanged. Local users keep using their `.env`; this
   bridge is a no-op when no Streamlit secret is set.
2. Runs `src/ui/1_Scanner.py` as the main script so `st.set_page_config` lands
   in the right scope.

Local users keep launching via `run_app.bat` -> `streamlit run src/ui/1_Scanner.py`
exactly as before. This file is purely additive.
"""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCANNER = ROOT / "src" / "ui" / "1_Scanner.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Secrets bridge: st.secrets -> os.environ
# ---------------------------------------------------------------------------
# Streamlit Cloud injects values from the app's Secrets UI into st.secrets.
# Our existing AQE code reads `os.environ.get("FMP_API_KEY")` so we mirror
# the secret into the environment before any AQE import runs.

def _bridge_secrets_to_env() -> None:
    try:
        import streamlit as st                                          # noqa: PLC0415
    except ImportError:
        return  # not in a Streamlit context
    try:
        # `st.secrets` raises if no secrets.toml exists locally; treat as absent.
        secrets = st.secrets
    except Exception:
        return
    for key in ("FMP_API_KEY",):
        try:
            val = secrets.get(key) if hasattr(secrets, "get") else secrets[key]
        except Exception:
            val = None
        if val and not os.environ.get(key):
            os.environ[key] = str(val)


_bridge_secrets_to_env()


# ---------------------------------------------------------------------------
# Hand off to the Scanner page
# ---------------------------------------------------------------------------

runpy.run_path(str(SCANNER), run_name="__main__")
