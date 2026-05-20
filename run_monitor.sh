#!/bin/bash
# run_monitor.sh - Run the PSFC slot monitor

# Change to script directory
cd "$(dirname "$0")"

# Secrets (PSFC_EMAIL/PSFC_PASSWORD/NTFY_TOPIC) come from the shared
# LocalServerApps/.env — monitor.py loads it via python-dotenv's find_dotenv,
# which walks up from here. No local .env sourcing needed.

# Ensure the Playwright browser binary exists (no-op once installed). On a
# fresh machine this downloads it; system libs still need a one-time
# `uv run playwright install-deps chromium` (sudo) — see automation/PI_SETUP.md.
uv run playwright install chromium >> monitor.log 2>&1

# Run the monitor
uv run monitor.py >> monitor.log 2>&1