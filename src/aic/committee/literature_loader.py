"""Literature loader — reads PM-uploaded speed-learning summaries from the spec.

Per the spec section "Literature Upload Holding Area -- PM to Populate":
PM may paste richer text between `<<<{VOICE}_LITERATURE_START>>>` and
`<<<{VOICE}_LITERATURE_END>>>` markers in the spec markdown file. If the slot
is empty, the default summary in `voice_config.speed_learning` is used as
fallback.

This module reads the spec file on demand and returns a dict mapping
`voice_id` (lowercase) -> uploaded literature text or None.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Default spec location -- the PM places it in Downloads per the build session.
DEFAULT_SPEC_PATH = Path(
    os.environ.get(
        "AIC_SPEC_PATH",
        r"C:\Users\ashtz\Downloads\AEGIS_POC_BUILD_SPEC_v2.md",
    )
)

_SLOT_PATTERN = re.compile(
    r"<<<(\w+)_LITERATURE_START>>>(.*?)<<<\1_LITERATURE_END>>>",
    re.DOTALL,
)


def load_literature(spec_path: Path | str | None = None) -> dict[str, str | None]:
    """Parse the spec file's literature slots.

    Returns {voice_id_lowercase: uploaded_text_or_None}. If the slot is empty
    (only whitespace between START/END markers), the value is None and callers
    fall back to the default summary in `voice_config.speed_learning`.

    Missing spec file -> empty dict (every voice falls back to default).
    """
    path = Path(spec_path) if spec_path else DEFAULT_SPEC_PATH
    if not path.exists():
        return {}

    spec = path.read_text(encoding="utf-8")
    out: dict[str, str | None] = {}
    for match in _SLOT_PATTERN.finditer(spec):
        voice_id = match.group(1).lower()
        content = match.group(2).strip()
        out[voice_id] = content if content else None
    return out


def get_voice_literature(
    voice_id: str,
    cached: dict[str, str | None] | None = None,
    spec_path: Path | str | None = None,
) -> str | None:
    """Return PM-uploaded literature for the voice, or None if not populated.

    Callers typically build the prompt with the override iff this is non-None,
    otherwise fall back to `voice_config.speed_learning`.
    """
    if cached is None:
        cached = load_literature(spec_path)
    return cached.get(voice_id)


if __name__ == "__main__":
    lit = load_literature()
    if not lit:
        print(f"No spec found at {DEFAULT_SPEC_PATH} -- every voice will use defaults.")
    else:
        for voice, text in sorted(lit.items()):
            if text is None:
                print(f"  {voice:<14} (slot empty -- default)")
            else:
                print(f"  {voice:<14} PM-uploaded ({len(text)} chars)")
