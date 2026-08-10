"""Validate Tiger credentials LOCALLY, before they go anywhere near the Space.

The point is to separate two failures that look identical from the outside: a
bad credential and a bad deployment. Run this on the PC where the `.pem` lives.
If it passes here, the key is good and anything still broken on HuggingFace is
a secrets problem. If it fails here, nothing about the Space will fix it.

    scripts\\tiger_check.bat          (double-click)
    python -m scripts.tiger_check     (or from a prompt)

Reads TIGER_ID / TIGER_ACCOUNT / TIGER_PRIVATE_KEY from the environment or
`.env`. `TIGER_PRIVATE_KEY` may be either the key itself or a PATH to the .pem
file — locally a path is easier, and the script tells you what to paste into the
Space either way.

**It never prints the private key.** It reports its length and whether it looks
like base64, which is enough to tell a truncated paste from a good one without
putting a credential in your scrollback.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OK, BAD, INFO = "  [OK]  ", "  [FAIL]", "  [--]  "


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass


def _resolve_key(raw: str | None) -> tuple[str | None, str]:
    """(key text, where it came from). A path is allowed locally."""
    if not raw:
        return None, "not set"
    p = Path(raw.strip().strip('"'))
    try:
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8"), f"file {p.name}"
    except OSError:
        pass
    return raw, "inline value"


def main() -> int:
    _load_env()
    from src.options.providers import tiger as T

    print("=" * 64)
    print("  Tiger credential check")
    print("=" * 64)

    fails = 0

    # 1 — the SDK
    try:
        import tigeropen  # noqa: F401
        print(f"{OK} tigeropen installed")
    except ImportError:
        print(f"{BAD} tigeropen NOT installed")
        print("        fix: pip install tigeropen")
        return 1

    # 2 — the three values
    tid = os.environ.get(T.TIGER_ID_ENV)
    acct = os.environ.get(T.TIGER_ACCOUNT_ENV)
    raw_key = os.environ.get(T.TIGER_KEY_ENV)
    for label, val in ((T.TIGER_ID_ENV, tid), (T.TIGER_ACCOUNT_ENV, acct)):
        if val:
            print(f"{OK} {label} = {val}")
        else:
            print(f"{BAD} {label} not set")
            fails += 1

    key_text, origin = _resolve_key(raw_key)
    if not key_text:
        print(f"{BAD} {T.TIGER_KEY_ENV} not set")
        print("        set it to the .pem path, or paste the key itself")
        fails += 1
    else:
        body = T.normalise_private_key(key_text)
        looks_b64 = body and all(
            c.isalnum() or c in "+/=\n" for c in body)
        print(f"{OK} {T.TIGER_KEY_ENV} read from {origin}")
        print(f"{INFO} normalised to {len(body)} chars, "
              f"{'looks like base64' if looks_b64 else 'DOES NOT look like base64'}")
        if not looks_b64:
            print("        the paste is probably truncated or not a key")
            fails += 1
        elif len(body) < 200:
            print("        suspiciously short for an RSA key — check for truncation")
            fails += 1

    if fails:
        print("\n  Fix the above before going further.")
        return 1

    # 3 — the connection, and a real chain
    os.environ[T.TIGER_KEY_ENV] = key_text
    print(f"{INFO} connecting to Tiger and pulling a live SPY chain...")
    spot = 600.0
    try:
        from src.data.fmp_client import FMPClient
        q = FMPClient().get_quotes_batch(["SPY"])
        spot = float((q.get("SPY") or {}).get("price") or spot)
        print(f"{OK} SPY spot from FMP: {spot}")
    except Exception as exc:  # noqa: BLE001
        print(f"{INFO} no FMP spot ({str(exc)[:60]}) — using {spot} for the test")

    res = T.fetch_chain("SPY", spot, today=date.today())
    if not res.get("contracts"):
        why = str(res.get("reason") or "")
        print(f"{BAD} chain fetch returned nothing")
        print(f"        reason: {why[:200]}")
        low = why.lower()
        print()
        if "illegal" in low or "tigerid" in low:
            print("  -> TIGER_ID is wrong. Copy it again from the developer portal;")
            print("     it is the numeric tiger_id, not your login or account number.")
        elif "signature" in low or "sign" in low:
            print("  -> the private key does not match the public key Tiger holds.")
            print("     Regenerate the pair on the portal and re-upload the public half.")
        elif "permission" in low or "not allowed" in low or "auth" in low:
            print("  -> the account has no US option market-data entitlement.")
        elif "account" in low:
            print("  -> TIGER_ACCOUNT is wrong. Use the trading account number.")
        else:
            print("  -> send me the reason line above; it is not one I have seen yet.")
        return 1

    cons = res["contracts"]
    print(f"{OK} {len(cons)} contracts with open interest "
          f"(expiries {', '.join(res.get('expiries_used') or [])})")
    print(f"{INFO} total open interest: "
          f"{int(sum(c['open_interest'] for c in cons)):,}")

    # 4 — end to end through the real engine
    from src.macro.crown import explain as E
    from src.macro.crown import gamma as G
    prof = G.gamma_profile(cons, spot)
    if not prof.get("available"):
        print(f"{BAD} gamma engine could not build a map: {prof.get('reason')}")
        return 1
    print(f"{OK} gamma map built — {prof['regime']}, "
          f"flip {prof['gamma_flip']}, total "
          f"${(prof['total_gex'] or 0) / 1e9:+,.2f}bn")

    read = E.gamma_reading(prof)
    print("\n" + "-" * 64)
    print(f"  {read['headline']}")
    for ln in read["lines"]:
        print("   - " + ln.replace("**", ""))
    print("-" * 64)

    print("\n  PASSED. The credentials are good.")
    print("  Now add these three as SECRETS on the HuggingFace Space:")
    print(f"    {T.TIGER_ID_ENV}          {tid}")
    print(f"    {T.TIGER_ACCOUNT_ENV}     {acct}")
    print(f"    {T.TIGER_KEY_ENV}  <the whole .pem file contents>")
    print("\n  Space -> Settings -> Variables and secrets -> New secret.")
    print("  Choose Secret, not Variable. Full guide: docs/AQE_TIGER_SETUP.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
