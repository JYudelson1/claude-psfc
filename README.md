# PSFC Orientation Slot Monitor 🥬

Automatically monitors the Park Slope Food Coop orientation appointment page and sends you a push notification when slots become available.

## Features

- ✅ Logs into ort.foodcoop.com with your credentials
- ✅ Checks for available orientation slots
- ✅ Filters out slots during Fri 3pm - Sat 7pm (Shabbat)
- ✅ Sends push notifications via ntfy.sh (free, no account needed)
- ✅ Runs on a schedule via macOS launchd

## Quick Start

### 1. Install Dependencies

```bash
# Clone/copy this directory somewhere permanent
cp -r psfc-monitor ~/psfc-monitor
cd ~/psfc-monitor

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 2. Configure Credentials

```bash
# Copy the example env file
cp .env.example .env

# Edit with your actual credentials
nano .env  # or vim, or whatever
```

Fill in:
- `PSFC_EMAIL` - Your ort.foodcoop.com email
- `PSFC_PASSWORD` - Your password
- `NTFY_TOPIC` - A unique, hard-to-guess string (this is basically a password for your notifications)

### 3. Set Up ntfy.sh on Your Phone

1. Install the ntfy app: [iOS](https://apps.apple.com/us/app/ntfy/id1625396347) | [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
2. Open the app and tap "+" to subscribe to a topic
3. Enter the EXACT same topic string you put in `.env`
4. Make sure notifications are enabled for the app

### 4. Test It Manually

```bash
cd ~/psfc-monitor
source venv/bin/activate
./run_monitor.sh
```

You should see output like:
```
============================================================
[2025-01-13 15:30:00] Checking for PSFC slots...
============================================================
[1/4] Loading login page...
[2/4] Logging in...
[3/4] Logged in successfully. Current URL: https://ort.foodcoop.com/home/
[4/4] Checking for available orientation slots...
[INFO] No slots available (found: 'pausing orientations')
```

### 5. Set Up Automatic Scheduling (macOS)

```bash
# Edit the plist to fix the path (if you didn't use ~/psfc-monitor)
nano com.user.psfc-monitor.plist

# Copy to LaunchAgents
cp com.user.psfc-monitor.plist ~/Library/LaunchAgents/

# Load it
launchctl load ~/Library/LaunchAgents/com.user.psfc-monitor.plist

# Verify it's running
launchctl list | grep psfc
```

By default, it runs **every 5 minutes**. You can adjust this in the plist file.

### Stopping/Restarting

```bash
# Stop
launchctl unload ~/Library/LaunchAgents/com.user.psfc-monitor.plist

# Start
launchctl load ~/Library/LaunchAgents/com.user.psfc-monitor.plist

# Check logs
tail -f ~/psfc-monitor/monitor.log
tail -f /tmp/psfc-monitor.out
```

## Troubleshooting

### "Login failed" errors

- Double-check your credentials in `.env`
- Try logging in manually at https://ort.foodcoop.com to verify your account works
- Check `debug_screenshot.png` and `debug_page.html` if they get generated

### No notifications received

1. Make sure your ntfy topic matches EXACTLY between `.env` and the app
2. Test ntfy manually: `curl -d "test message" ntfy.sh/YOUR_TOPIC`
3. Check that notifications aren't silenced on your phone

### Script not running on schedule

```bash
# Check if launchd loaded it
launchctl list | grep psfc

# Check for errors
cat /tmp/psfc-monitor.err

# Make sure the path in the plist is correct
# Make sure run_monitor.sh is executable: chmod +x run_monitor.sh
```

### "Page structure may have changed"

The PSFC website might have been updated. Check `debug_screenshot.png` to see what the page looks like, then update the selectors in `monitor.py`.

## Customization

### Change excluded times

Edit the `is_slot_during_shabbat()` function in `monitor.py`:

```python
def is_slot_during_shabbat(slot_datetime: datetime) -> bool:
    weekday = slot_datetime.weekday()  # Monday=0, Sunday=6
    hour = slot_datetime.hour
    
    # Customize your excluded times here
    # Currently: Friday after 3pm through Saturday until 7pm
    if weekday == 4 and hour >= 15:  # Friday 3pm+
        return True
    if weekday == 5 and hour < 19:   # Saturday until 7pm
        return True
    return False
```

### Run more frequently around midnight

Edit the plist to use `StartCalendarInterval` instead of `StartInterval` - there's a commented-out example in the file.

### Auto-book a slot (advanced)

The script currently just alerts you. To auto-book, you'd need to:
1. Click on the slot link/button
2. Fill out any confirmation form
3. Submit

This is riskier (what if it books a bad time?) so I left it as alert-only. Let me know if you want help adding auto-booking later.

## How It Works

1. Playwright launches a headless Chromium browser
2. Navigates to ort.foodcoop.com and logs in with your credentials
3. Checks the home page for available orientation slots
4. If slots are found, filters out any during your excluded times
5. If acceptable slots remain, sends a push notification via ntfy.sh
6. Exits (launchd will run it again on schedule)

## Security Notes

- Your credentials are stored in `.env` which should NOT be committed to git
- The ntfy topic is essentially a password - anyone who knows it can send you notifications
- Consider using a unique, random topic like `psfc-yourname-a8f3k2m9x`
