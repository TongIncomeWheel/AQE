"""Show the exact values to paste into GitHub Actions secrets.

Run this ON YOUR PC (double-click show_github_secrets.bat). It reads the secret
values you already have locally — .env, client_secret.json, the Drive OAuth
token cache, and the HuggingFace token cache — and prints them next to the
GitHub secret name to paste them into.

It only READS local files and prints to your screen; it writes nothing and
sends nothing anywhere. (Don't share/screenshot the output — these are secrets.)

Where to drop them:
  GitHub → repo → Settings → Secrets and variables → Actions → New repository secret
  Direct: https://github.com/TongIncomeWheel/AQE/settings/secrets/actions
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_env_file() -> dict:
    """Parse a simple KEY=VALUE .env at the project root."""
    out: dict[str, str] = {}
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return out
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _from_client_secret() -> tuple[str | None, str | None]:
    """client_id, client_secret from client_secret.json (installed or web)."""
    p = PROJECT_ROOT / "client_secret.json"
    if not p.exists():
        return None, None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        node = data.get("installed") or data.get("web") or data
        return node.get("client_id"), node.get("client_secret")
    except Exception:
        return None, None


def _refresh_token_from_cache() -> str | None:
    """refresh_token from the Drive OAuth token cache, if present."""
    for name in ("gdrive_token_cache.json", "token_cache.json"):
        p = PROJECT_ROOT / name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            # search nested for a refresh_token
            stack = [data]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    if cur.get("refresh_token"):
                        return cur["refresh_token"]
                    stack.extend(cur.values())
                elif isinstance(cur, list):
                    stack.extend(cur)
        except Exception:
            pass
    return None


def _hf_token() -> str | None:
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    p = Path.home() / ".cache" / "huggingface" / "token"
    if p.exists():
        t = p.read_text(encoding="utf-8").strip()
        return t or None
    return None


def _hf_username(token: str | None) -> str | None:
    if not token:
        return None
    try:
        from huggingface_hub import HfApi
        return HfApi().whoami(token=token).get("name")
    except Exception:
        return None


def main() -> int:
    env = _load_env_file()
    cid, csec = _from_client_secret()
    rtok = _refresh_token_from_cache()
    hf = _hf_token()
    hf_user = _hf_username(hf)

    # name -> (value, where-it-came-from / where-to-get-it)
    rows = [
        ("HF_TOKEN", hf,
         "~/.cache/huggingface/token  (or make one: huggingface.co/settings/tokens → Write)"),
        ("HF_USERNAME", hf_user,
         "your HF login name (huggingface.co → avatar). Skip if it's 'AQE-Aegis'."),
        ("FMP_API_KEY", env.get("FMP_API_KEY"),
         ".env  (FMP_API_KEY=...)"),
        ("GOOGLE_OAUTH_CLIENT_ID", env.get("GOOGLE_OAUTH_CLIENT_ID") or cid,
         ".env  or client_secret.json"),
        ("GOOGLE_OAUTH_CLIENT_SECRET", env.get("GOOGLE_OAUTH_CLIENT_SECRET") or csec,
         ".env  or client_secret.json"),
        ("GOOGLE_OAUTH_REFRESH_TOKEN",
         env.get("GOOGLE_OAUTH_REFRESH_TOKEN") or rtok,
         ".env  or gdrive_token_cache.json (else re-run setup_gdrive.bat)"),
    ]

    line = "=" * 72
    print()
    print(line)
    print("PASTE THESE INTO GITHUB → Settings → Secrets and variables → Actions")
    print("https://github.com/TongIncomeWheel/AQE/settings/secrets/actions")
    print("(click 'New repository secret' for each: Name on top, value below)")
    print(line)
    missing = []
    for name, val, where in rows:
        print()
        if val:
            print(f"  Name:  {name}")
            print(f"  Value: {val}")
        else:
            print(f"  Name:  {name}")
            print(f"  Value: ⚠ NOT FOUND — get it from: {where}")
            missing.append(name)
    print()
    print(line)
    if missing:
        print(f"Missing {len(missing)}: {', '.join(missing)} — see the note next to each.")
    else:
        print("All values found. Copy each Name/Value pair into a GitHub secret.")
    print(line)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
