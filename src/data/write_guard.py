"""Password gate for Google Drive WRITE access.

The Hugging Face Space is now public. The ONLY way a random visitor can
mutate the user's real Google Drive is the REST uploader in
``gdrive_uploader.upload_or_replace`` — the local ``G:\\`` Drive mount and the
local ``output/`` writes never exist on a cloud host, so they are not an
exposure. This module is the single authorization chokepoint for that path,
plus the helper the Streamlit UI uses to lock its mutating buttons.

Model
-----
* Protection is **ON** whenever ``AQE_WRITE_PASSWORD`` is present in the
  environment. The user sets it once as a Hugging Face Space *secret*
  (Settings → Variables and secrets → New secret). On the local PC the secret
  is absent, so protection is **OFF** and nothing changes — no terminals, no
  friction, exactly as before.
* The Streamlit UI prompts for the password, verifies it, and only on success
  authorizes write actions for that browser session.
* For pipeline runs (which write to Drive from a *subprocess*), the UI forwards
  the verified password to that one subprocess via the ``AQE_WRITE_TOKEN``
  environment variable. The uploader checks it there.
* All comparisons are constant-time (``hmac.compare_digest``) to avoid timing
  side-channels.
"""

from __future__ import annotations

import hmac
import os

# Env var holding the configured password (set as an HF Space secret).
ENV_PASSWORD = "AQE_WRITE_PASSWORD"
# Env var carrying a per-invocation proof of the password, injected by the UI
# into a single pipeline subprocess so its Drive export is authorized.
ENV_TOKEN = "AQE_WRITE_TOKEN"


def expected_password() -> str | None:
    """The configured write password, or None when protection is off."""
    pw = os.environ.get(ENV_PASSWORD)
    return pw if pw else None


def is_protected() -> bool:
    """True when a write password is configured (i.e. on the public Space)."""
    return expected_password() is not None


def verify(candidate: str | None) -> bool:
    """Constant-time check of a candidate password.

    Returns True when protection is off (no password configured), so callers
    on the trusted local PC never get gated.
    """
    pw = expected_password()
    if pw is None:
        return True
    if not candidate:
        return False
    return hmac.compare_digest(candidate, pw)


def is_write_authorized(token: str | None = None) -> bool:
    """Authorize a Google Drive write.

    * Protection off  -> always authorized.
    * Protection on   -> the correct password must be supplied, either via the
      explicit ``token`` argument (in-process UI calls) or the
      ``AQE_WRITE_TOKEN`` env var (pipeline subprocess, injected by the UI for
      that run only).
    """
    if not is_protected():
        return True
    if token and verify(token):
        return True
    env_tok = os.environ.get(ENV_TOKEN)
    return bool(env_tok and verify(env_tok))
