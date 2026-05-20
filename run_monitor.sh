#!/bin/bash
# run_monitor.sh - Run the PSFC slot monitor

# Change to script directory
cd "$(dirname "$0")"

# Load environment variables from .env file if it exists
# This uses set -a to automatically export all variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Run the monitor
uv run monitor.py
