#!/usr/bin/env python3
"""
Park Slope Food Coop Orientation Slot Monitor

Checks for available orientation slots and sends a push notification via ntfy.sh
when slots become available (excluding Fri 3pm - Sat 7pm).
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# =============================================================================
# CONFIGURATION - Edit these values
# =============================================================================

# Your ort.foodcoop.com credentials
PSFC_EMAIL = os.environ.get("PSFC_EMAIL", "your-email@example.com")
PSFC_PASSWORD = os.environ.get("PSFC_PASSWORD", "your-password")

# ntfy.sh topic - pick something unique and hard to guess
# You'll subscribe to this topic in the ntfy app on your phone
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "psfc-slots-yourname-12345")

# URLs
LOGIN_URL = "https://ort.foodcoop.com/login/"
HOME_URL = "https://ort.foodcoop.com/home/"

# Timezone for slot filtering
TZ = ZoneInfo("America/New_York")

def get_calendar_url() -> str:
    """Get the calendar URL for today's date."""
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    return f"https://ort.foodcoop.com/calendar/0/0/0/{today}/"

# =============================================================================
# SLOT FILTERING
# =============================================================================

def is_slot_during_shabbat(slot_datetime: datetime) -> bool:
    """
    Returns True if slot falls during Fri 3pm - Sat 7pm (times you want to exclude).
    
    Args:
        slot_datetime: The datetime of the orientation slot (should be timezone-aware)
    """
    # Ensure we're working in Eastern time
    if slot_datetime.tzinfo is None:
        slot_datetime = slot_datetime.replace(tzinfo=TZ)
    else:
        slot_datetime = slot_datetime.astimezone(TZ)
    
    weekday = slot_datetime.weekday()  # Monday=0, Sunday=6
    hour = slot_datetime.hour
    
    # Friday (4) after 3pm
    if weekday == 4 and hour >= 15:
        return True
    
    # All of Saturday (5) until 7pm
    if weekday == 5 and hour < 19:
        return True
    
    return False


def filter_slots(slots: list[dict]) -> list[dict]:
    """
    Filter out slots that fall during excluded times.
    
    Args:
        slots: List of slot dicts with 'datetime' and 'text' keys
    
    Returns:
        Filtered list of acceptable slots
    """
    acceptable = []
    for slot in slots:
        if not is_slot_during_shabbat(slot["datetime"]):
            acceptable.append(slot)
        else:
            print(f"  [SKIP] Filtering out slot during excluded time: {slot['text']}")
    return acceptable


# =============================================================================
# NOTIFICATION
# =============================================================================

async def send_slots_detected_notification(slot_info: list[str], calendar_url: str) -> None:
    """
    Send a push notification when slots might be available.
    
    This fires when the 'Sorry, all appointments taken' message is NOT present,
    which strongly suggests slots are available (or the page changed).
    """
    
    if slot_info:
        slot_list = "\n".join([f"• {s}" for s in slot_info[:5]])
        extra = f"\n...and more!" if len(slot_info) > 5 else ""
        message = f"🎉 PSFC slots likely available!\n\nFound on page:\n{slot_list}{extra}\n\nGO NOW: {calendar_url}"
    else:
        message = f"🎉 PSFC calendar changed!\n\nThe 'all appointments taken' message is GONE.\n\nThis probably means slots are available!\n\nGO NOW: {calendar_url}"
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                content=message.encode("utf-8"),
                headers={
                    "Title": "🚨 PSFC SLOTS AVAILABLE!",
                    "Priority": "urgent",
                    "Tags": "rotating_light,grocery",
                    "Click": calendar_url,
                },
            )
            resp.raise_for_status()
            print(f"[OK] Notification sent to ntfy.sh/{NTFY_TOPIC}")
        except Exception as e:
            print(f"[ERROR] Failed to send notification: {e}")
            await send_error_notification(f"SLOTS AVAILABLE!!")


async def send_error_notification(error_msg: str) -> None:
    """Send an error notification so you know if the monitor is broken"""
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                content=f"⚠️ PSFC Monitor Error:\n\n{error_msg}".encode("utf-8"),
                headers={
                    "Title": "PSFC Monitor Error",
                    "Priority": "default",
                    "Tags": "warning",
                },
            )
        except Exception:
            pass  # Don't fail on notification errors


# =============================================================================
# MAIN SCRAPER
# =============================================================================

async def check_for_slots() -> None:
    """Main function to log in and check for available slots."""
    
    print(f"\n{'='*60}")
    print(f"[{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}] Checking for PSFC slots...")
    print(f"{'='*60}")
    
    async with async_playwright() as p:
        # Launch browser (headless for automation, set to False for debugging)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        try:
            # Step 1: Go to login page
            print("[1/4] Loading login page...")
            await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
            
            # Wait for any loading spinners to disappear
            # The page shows "Please wait ...." while loading
            await asyncio.sleep(2)  # Give JS time to render
            
            # Wait for form to be visible
            try:
                await page.wait_for_selector('input[type="text"], input[type="password"]', timeout=10000)
            except PlaywrightTimeout:
                # Save debug info if form doesn't appear
                screenshot_path = Path(__file__).parent / "debug_login.png"
                await page.screenshot(path=screenshot_path)
                raise Exception(f"Login form not found. Screenshot saved to {screenshot_path}")
            
            # Step 2: Fill in credentials and submit
            print("[2/4] Logging in...")
            
            # The form uses "Username" and "Password" labels
            # Try multiple selector strategies
            username_selectors = [
                'input[name="username"]',
                'input[type="text"]',
                'input#id_username',
                'input[placeholder*="user" i]',
            ]
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                'input#id_password',
            ]
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Log in")',
                'input[value="Login"]',
            ]
            
            # Find and fill username
            username_filled = False
            for selector in username_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.fill(PSFC_EMAIL)
                        username_filled = True
                        print(f"  [DEBUG] Username filled using: {selector}")
                        break
                except Exception:
                    continue
            
            if not username_filled:
                raise Exception("Could not find username field")
            
            # Find and fill password
            password_filled = False
            for selector in password_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.fill(PSFC_PASSWORD)
                        password_filled = True
                        print(f"  [DEBUG] Password filled using: {selector}")
                        break
                except Exception:
                    continue
            
            if not password_filled:
                raise Exception("Could not find password field")
            
            # Find and click submit
            submitted = False
            for selector in submit_selectors:
                try:
                    elem = await page.query_selector(selector)
                    if elem:
                        await elem.click()
                        submitted = True
                        print(f"  [DEBUG] Submitted using: {selector}")
                        break
                except Exception:
                    continue
            
            if not submitted:
                # Fallback: try pressing Enter in the password field
                await page.keyboard.press("Enter")
                print("  [DEBUG] Submitted using Enter key")
            
            # Wait for navigation after login
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Check if login succeeded (should redirect to home or show error)
            current_url = page.url
            if "login" in current_url.lower():
                # Might still be on login page - check for error messages
                error_elem = await page.query_selector(".alert-danger, .error, .errorlist")
                if error_elem:
                    error_text = await error_elem.text_content()
                    raise Exception(f"Login failed: {error_text}")
                else:
                    raise Exception("Login failed - still on login page")
            
            print(f"[3/4] Logged in successfully. Current URL: {current_url}")
            
            # Step 3: Navigate to the calendar page
            calendar_url = get_calendar_url()
            print(f"[4/4] Navigating to calendar: {calendar_url}")
            await page.goto(calendar_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # Let JS render
            
            # Get page content
            content = await page.content()
            page_text = await page.inner_text("body")
            
            # Check for the "no slots" message
            NO_SLOTS_MESSAGE = "Sorry, all appointments are currently taken"
            
            if NO_SLOTS_MESSAGE in page_text:
                print(f"[INFO] No slots available - found the 'all appointments taken' message")
                await browser.close()
                return
            
            # Check if we're still on login page (session expired?)
            if "please login" in page_text.lower() or "/login" in page.url:
                raise Exception("Session expired or login failed - redirected to login page")
            
            # If we get here, the "sorry" message is NOT present!
            # This means either:
            # 1. Slots are available! 🎉
            # 2. The page structure changed and we need to investigate
            
            print("[ALERT] 'Sorry, all appointments taken' message NOT found!")
            print("[ALERT] This likely means slots are available!")
            await send_slots_detected_notification([], calendar_url)
            
            # Save debug info
            screenshot_path = Path(__file__).parent / "slots_available_screenshot.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"[DEBUG] Screenshot saved to: {screenshot_path}")
            
            html_path = Path(__file__).parent / "slots_available_page.html"
            html_path.write_text(content)
            print(f"[DEBUG] HTML saved to: {html_path}")
            
            # Try to extract any visible slot information for the notification
            # Look for common calendar/slot elements
            slot_info = []
            
            # Try to find any links or buttons that might be slots
            slot_elements = await page.query_selector_all("a[href*='calendar'], button, .slot, .appointment, td a")
            for elem in slot_elements:
                try:
                    text = await elem.text_content()
                    if text and text.strip() and len(text.strip()) < 100:
                        # Filter out navigation links
                        text_lower = text.lower().strip()
                        if text_lower not in ["home", "profile", "calendar", "logout", "login", "register"]:
                            slot_info.append(text.strip())
                except Exception:
                    continue
            
            # Deduplicate
            slot_info = list(dict.fromkeys(slot_info))[:10]
            
            # Send notification - ALWAYS notify when the "sorry" message is missing
            # because that's our signal that something changed
            await send_slots_detected_notification(slot_info, calendar_url)
            
        except PlaywrightTimeout as e:
            error_msg = f"Timeout error: {e}"
            print(f"[ERROR] {error_msg}")
            await send_error_notification(error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            print(f"[ERROR] {error_msg}")
            await send_error_notification(error_msg)
            
        finally:
            await browser.close()


# =============================================================================
# ENTRY POINT
# =============================================================================

async def main():
    """Main entry point."""
    
    # Validate configuration
    if PSFC_EMAIL == "your-email@example.com" or PSFC_PASSWORD == "your-password":
        print("ERROR: Please set PSFC_EMAIL and PSFC_PASSWORD environment variables")
        print("  export PSFC_EMAIL='your-email@example.com'")
        print("  export PSFC_PASSWORD='your-password'")
        sys.exit(1)
    
    if NTFY_TOPIC == "psfc-slots-yourname-12345":
        print("WARNING: Using default ntfy topic. Consider setting NTFY_TOPIC for privacy.")
    
    await check_for_slots()


if __name__ == "__main__":
    asyncio.run(main())