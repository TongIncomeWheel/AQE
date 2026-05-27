"""Streamlit Cloud entrypoint for AQE.

Streamlit Cloud looks for `streamlit_app.py` at the repo root. This shim simply
hands off to the multi-page app rooted at `src/ui/1_Scanner.py`, which already
detects cloud (read-only) mode and renders from the committed export JSON when
the heavy `data/*.parquet` caches are absent.

Local users keep launching via `run_app.bat` → `streamlit run src/ui/1_Scanner.py`
exactly as before. This file is purely additive.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCANNER = ROOT / "src" / "ui" / "1_Scanner.py"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Execute the Scanner page in this process so st.set_page_config + every
# subsequent Streamlit call run as if it were the entrypoint itself.
runpy.run_path(str(SCANNER), run_name="__main__")
