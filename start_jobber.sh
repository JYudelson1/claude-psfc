#!/bin/bash
# start_jobber.sh - Start the PSFC slot monitor

# End the jobber process if it's running
./end_jobber.sh

# Copy to LaunchAgents
cp com.user.psfc-monitor.plist ~/Library/LaunchAgents/

# Load it
launchctl load ~/Library/LaunchAgents/com.user.psfc-monitor.plist