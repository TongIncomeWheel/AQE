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
  3. Configure the OAuth consent screen ("External", testing mode is fine
     for personal use; add your own Google email as a Test User).
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

Plus you'll add one Variable (not Secret):
    GDRIVE_FOLDER_PATH = "Trading Strategy/AQE"   (or set GDRIVE_FOLDER_ID
                                                   if you know it)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLIENT_SECRET_PATH = PROJECT_ROOT / "client_secret.json"
TOKEN_CACHE_PATH = PROJECT_ROOT / "gdrive_token_cache.json"

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


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

    # Print what to paste into HF
    print()
    print("=" * 70)
    print("Paste these into Hugging Face Space Settings -> Variables and secrets:")
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
    print("--- VARIABLE (mark 'New variable' in HF UI; visible to operators) ---")
    print()
    print(f"GDRIVE_FOLDER_PATH")
    print(f'    Trading Strategy/AQE')
    print()
    print("=" * 70)
    print("After setting, restart the HF Space.")
    print("Then check the Scanner sidebar's Cloud diagnostic -- Drive sync")
    print("should now show 'configured' with your authenticated email.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
