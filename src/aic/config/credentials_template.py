"""AIC credentials template — reference copy. Never overwritten by build.

When you run a fresh install or want to reset, COPY this file to
`credentials.py` (same directory) and fill in the blanks.

`credentials.py` is the live file the application reads; it is .gitignored.

Per AEGIS_POC_BUILD_SPEC_v2.md §"Credentials — Entry by PM Tomorrow":
all values must be populated before any API call is attempted. The
startup guard in `aic_config.py` raises CredentialsMissingError if any
required field is left empty.
"""

# Anthropic API (12 committee voices + Alfred orchestrator)
ANTHROPIC_API_KEY = ""                          # sk-ant-...

# Financial Modeling Prep (already in use by AQE — same key)
FMP_API_KEY = ""

# IBKR Flex Web Service (fill reconciliation, position backfill)
IBKR_FLEX_PROXY_URL = ""                        # Apps Script URL
IBKR_FLEX_TOKEN = ""                            # ****6640 token

# Google Drive (PTJ JSON, AQE export, SRM scorecard)
GOOGLE_SA_KEY_PATH = ""                         # /path/to/service_account.json
GOOGLE_DRIVE_FOLDER_ID = ""                     # Trading Strategy folder ID
GOOGLE_DRIVE_PTJ_FILENAME = "aegis_trade_journal"

# Telegram delivery (push briefs + alerts)
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

# SRM cleanup script (Apps Script)
SRM_CLEANUP_SCRIPT_URL = ""

# Environment
PM_TIMEZONE = "Asia/Singapore"                  # locked per spec

# ---- DO NOT EDIT BELOW ----------------------------------------------
# Which credentials are required for which subsystem. The startup guard
# uses this to fail loudly with a specific field name + subsystem when
# a required value is empty. Subsystems may run independently.
REQUIRED_BY = {
    "anthropic":  ["ANTHROPIC_API_KEY"],
    "fmp":        ["FMP_API_KEY"],
    "ibkr_flex":  ["IBKR_FLEX_PROXY_URL", "IBKR_FLEX_TOKEN"],
    "google_drive": ["GOOGLE_SA_KEY_PATH", "GOOGLE_DRIVE_FOLDER_ID"],
    "telegram":   ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    "srm_cleanup": ["SRM_CLEANUP_SCRIPT_URL"],
}
