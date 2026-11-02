"""Root conftest — ensures project root is on sys.path for pytest collection."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force-check src is importable
import src  # noqa: F401


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _heartbeat_never_writes_the_repo_tree(tmp_path, monkeypatch):
    """Any in-window alert cycle under test beats; keep that file out of aegis/output/."""
    from src.alerts import heartbeat
    monkeypatch.setattr(heartbeat, "LOCAL_PATH", tmp_path / "aqe_alert_heartbeat.json")
