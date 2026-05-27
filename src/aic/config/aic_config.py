"""Credential loader + startup guard for the AIC layer.

Per spec: any required credential field that is empty MUST raise
CredentialsMissingError with the field name before any API call is attempted.
Subsystems may be independent (Anthropic vs FMP vs Telegram, etc.) so we
expose `assert_required(*subsystems)` for each call site to opt in only to
what it needs -- e.g. the Alfred orchestrator asserts "anthropic" but the
AQE post-processor asserts "fmp" only.
"""

from __future__ import annotations

from src.aic.config import credentials as _creds


class CredentialsMissingError(RuntimeError):
    """Raised when a required credential is empty at the point of use.

    The message names the exact field + subsystem so the PM can fix it
    without grep-spelunking. Never silently downgrade.
    """


def get_credential(field: str) -> str:
    """Return the value of a credential field, or raise if it doesn't exist."""
    if not hasattr(_creds, field):
        raise CredentialsMissingError(
            f"Credential field '{field}' is not defined in "
            f"src/aic/config/credentials.py. "
            f"Add it (copy from credentials_template.py if reset)."
        )
    return getattr(_creds, field)


def is_subsystem_ready(subsystem: str) -> bool:
    """True iff every credential required by `subsystem` is populated."""
    fields = _creds.REQUIRED_BY.get(subsystem)
    if fields is None:
        raise CredentialsMissingError(
            f"Unknown subsystem '{subsystem}'. Known: {list(_creds.REQUIRED_BY)}"
        )
    return all(bool(get_credential(f).strip()) for f in fields)


def assert_required(*subsystems: str) -> None:
    """Raise if any field required by any listed subsystem is empty.

    Usage at the start of each external-call entry point:

        from src.aic.config import assert_required
        assert_required("anthropic", "fmp")

    Fails loudly with the offending field name + subsystem.
    """
    missing: list[tuple[str, str]] = []
    for subsystem in subsystems:
        fields = _creds.REQUIRED_BY.get(subsystem)
        if fields is None:
            raise CredentialsMissingError(
                f"Unknown subsystem '{subsystem}'. "
                f"Known: {list(_creds.REQUIRED_BY)}"
            )
        for f in fields:
            value = get_credential(f).strip()
            if not value:
                missing.append((subsystem, f))
    if missing:
        bullets = "\n".join(f"  - [{s}] {f}" for s, f in missing)
        raise CredentialsMissingError(
            f"Required credentials are empty in src/aic/config/credentials.py:\n"
            f"{bullets}\n"
            f"PM: open credentials.py and fill these in before retrying."
        )
