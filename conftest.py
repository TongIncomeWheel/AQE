"""Root conftest — ensures project root is on sys.path for pytest collection."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force-check src is importable
import src  # noqa: F401
