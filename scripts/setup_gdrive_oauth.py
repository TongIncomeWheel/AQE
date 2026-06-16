"""ONE-TIME local helper: capture a Google Drive OAuth refresh token.

Run this script ONCE on your Windows PC. It opens your browser, you click
"Allow" to grant Drive access to your AQE app, and the script prints three
values you paste into the Hugging Face Space secret manager. After that the
HF deploy can upload export JSON to your Drive without ever needing you to
re-authenticate.

What you need before running this:
  1. A Google Cloud project (free):
       https://console.cloud.google.com/projectcreate
  2. Enable the Google Drive API in that project:
       APIs & Services -> Library -> "Google Drive API" -> Enable
  3. Configure the OAuth consent screen ("External"). IMPORTANT: set the
     Publishing status to **"In production"** (Publish app), NOT "Testing".
     In Testing mode Google EXPIRES the refresh token after 7 days, which
     causes the recurring "invalid_grant: Token has been expired or revoked"
     error. Production tokens are long-lived; as the sole user you do not need
     Google's verification.
  4. Create an OAuth 2.0 Client ID:
       Credentials -> Create Credentials -> OAuth Client ID
       Application type: **Desktop app**
       Download the JSON. Save it as `client_secret.json` in the project root
       (this file is gitignored).

Then run:
    python -m scripts.setup_gdrive_oauth

Output is three values to paste into HF Space settings:
    GOOGLE_OAUTH_CLIENT_ID          (Secret -- yes, it's "client_id" but mark
                                     it as Secret to keep the cluster of three
                                     together)
    GOOGLE_OAUTH_CLIENT_SECRET      (Secret)
    GOOGLE_OAUTH_REFRESH_TOKEN      (Secret)

The destination folder is pinned in code (gdrive_uploader.DEFAULT_FOLDER_ID),
so you do NOT need to set GDRIVE_FOLDER_ID/PATH. Only set GDRIVE_FOLDER_ID if
you want to override the pinned folder.

NOTE: the scope is full Drive (auth/drive), required to write into a folder
created in the Drive UI by ID. If you previously authorised with the narrower
drive.file scope, revoke the old grant at
https://myaccount.google.com/permissions and re-run this script so the new
refresh token carries the wider scope.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_SECRET_PATH = PROJECT_ROOT / "client_secret.json"
TOKEN_CACHE_PATH = PROJECT_ROOT / "gdrive_token_cache.json"
ENV_PATH = PROJECT_ROOT / ".env"

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _update_env_file(values: dict[str, str]) -> None:
    """Write the OAuth keys into the local (gitignored) .env, in place.

    Replaces any existing GOOGLE_OAUTH_* lines and appends missing ones,
    leaving every other line (FMP_API_KEY, etc.) untouched. This is what
    fixes a "Token has been expired or revoked" error on the LOCAL run —
    the .env is the credential source for double-click .bat / local export.
    """
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    remaining = dict(values)
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    for key, val in remaining.items():            # keys not already present
        out.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    if not CLIENT_SECRET_PATH.exists():
        print(f"ERROR: {CLIENT_SECRET_PATH} not found.")
        print()
        print("Steps to obtain it:")
        print("  1. https://console.cloud.google.com/apis/credentials")
        print("  2. Create OAuth 2.0 Client ID -> Application type: Desktop app")
        print("  3. Download the JSON")
        print(f"  4. Save it as {CLIENT_SECRET_PATH}")
        return 1

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: google-auth-oauthlib not installed.")
        print("Run: pip install google-auth-oauthlib google-api-python-client")
        return 1

    with open(CLIENT_SECRET_PATH, encoding="utf-8") as f:
        client_config = json.load(f)
    cid_secret = (client_config.get("installed") or
                  client_config.get("web") or {})
    client_id = cid_secret.get("client_id")
    client_secret = cid_secret.get("client_secret")
    if not (client_id and client_secret):
        print("ERROR: client_secret.json malformed -- missing client_id/secret.")
        return 1

    print("Opening browser for Google consent flow...")
    print("If your browser doesn't open automatically, copy the URL from the terminal.")
    print()
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH), SCOPES,
    )
    # access_type=offline + prompt=consent forces issuance of a refresh token
    # even if the user has previously granted consent.
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
        open_browser=True,
    )

    if not creds.refresh_token:
        print()
        print("ERROR: Google did NOT return a refresh token.")
        print("This usually means the consent screen wasn't fully completed,")
        print("or this Client ID has already been granted offline access without")
        print("revocation. Revoke previous grants at:")
        print("  https://myaccount.google.com/permissions")
        print("Then re-run this script.")
        return 1

    # Cache locally so we can test in-process before user copies to HF
    TOKEN_CACHE_PATH.write_text(
        json.dumps({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": creds.refresh_token,
        }, indent=2),
        encoding="utf-8",
    )

    # Quick smoke test: list the user's email
    try:
        from googleapiclient.discovery import build
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        about = service.about().get(fields="user(emailAddress,displayName)").execute()
        user = about.get("user", {})
        print()
        print(f"OAuth successful. Authenticated as: {user.get('emailAddress','?')}")
        print(f"Token cached at: {TOKEN_CACHE_PATH}  (gitignored)")
    except Exception as exc:                                                    # noqa: BLE001
        print(f"WARNING: token captured but smoke test failed: {exc}")

    # Fix the LOCAL run immediately: write the three keys into .env in place.
    try:
        _update_env_file({
            "GOOGLE_OAUTH_CLIENT_ID": client_id,
            "GOOGLE_OAUTH_CLIENT_SECRET": client_secret,
            "GOOGLE_OAUTH_REFRESH_TOKEN": creds.refresh_token,
        })
        print(f"Local .env updated at: {ENV_PATH}  (gitignored) -- local export fixed.")
    except Exception as exc:                                                     # noqa: BLE001
        print(f"WARNING: could not auto-update .env ({exc}); paste the values below manually.")

    # Print what to paste into HF + GitHub (those have their own copies)
    print()
    print("=" * 70)
    print("Local .env is done. Now paste these into the CLOUD secret stores so")
    print("the HF Space + GitHub Actions backstop keep writing to Drive:")
    print("  - Hugging Face: Space Settings -> Variables and secrets")
    print("  - GitHub: repo Settings -> Secrets and variables -> Actions")
    print("=" * 70)
    print()
    print("--- SECRETS (mark 'New secret' in HF UI) ---")
    print()
    print(f"GOOGLE_OAUTH_CLIENT_ID")
    print(f"    {client_id}")
    print()
    print(f"GOOGLE_OAUTH_CLIENT_SECRET")
    print(f"    {client_secret}")
    print()
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN")
    print(f"    {creds.refresh_token}")
    print()
    print("The destination folder is pinned in code (DEFAULT_FOLDER_ID), so no")
    print("GDRIVE_FOLDER_ID/PATH is required. Set GDRIVE_FOLDER_ID only to")
    print("override the pinned folder.")
    print()
    print("=" * 70)
    print("After setting, restart the HF Space.")
    print("Then check the Scanner sidebar's Cloud diagnostic -- Drive sync")
    print("should now show 'configured' with your authenticated email.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
