---
name: browser-broadcast
description: When using browser automation with nodriver or playwright, broadcasts live screenshots and status updates to a file that the dashboard reads in real-time. Call this alongside any browser automation task to enable live view in the dashboard.
triggers: browse website, browser automation, navigate, click button, fill form, web scraping, stealth browser
---

# Browser Live View Broadcaster

## Purpose
Stream live browser state (screenshots + current action) to the dashboard's Live View panel during browser automation tasks.

## Setup
```python
import base64, json, time, os

STATUS_FILE = "/a0/usr/workdir/browser_live_status.json"

def broadcast(tab, action, url=""):
    """Call this after each significant browser action to update the live view"""
    try:
        # Take screenshot
        tab.save_screenshot("/tmp/browser_snap.png")
        with open("/tmp/browser_snap.png", "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        
        status = {
            "timestamp": time.time(),
            "action": action,
            "url": url or "",
            "screenshot_b64": img_b64,
            "active": True
        }
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f)
        print(f"[LiveView] {action}")
    except Exception as e:
        print(f"[LiveView] Could not broadcast: {e}")

def clear_broadcast():
    """Call when browser automation is complete"""
    with open(STATUS_FILE, "w") as f:
        json.dump({"active": False, "action": "Browser idle", "timestamp": time.time()}, f)
```

## Usage Pattern with nodriver

```python
import asyncio, nodriver as uc

async def run_with_live_view(target_url, task_description):
    browser = await uc.start(
        headless=True, sandbox=False,
        browser_executable_path="/usr/bin/chromium",
        browser_args=["--no-sandbox", "--disable-gpu", "--window-size=1280,720"]
    )
    
    try:
        tab = await browser.get(target_url)
        await asyncio.sleep(2)
        broadcast(tab, f"Navigated to {target_url}", target_url)
        
        # Your automation steps here, calling broadcast() after each:
        # element = await tab.find("input[name=email]", timeout=5)
        # await element.send_keys("user@example.com")
        # broadcast(tab, "Filled email field", target_url)
        
        # ... more steps ...
        
    finally:
        clear_broadcast()
        browser.stop()

asyncio.run(run_with_live_view("https://example.com", "Register account"))
```

## Usage Pattern with playwright-stealth

```python
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import asyncio

async def run_playwright_with_view(target_url):
    async with Stealth().use_async(async_playwright()) as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(target_url)
        screenshot = await page.screenshot()
        img_b64 = base64.b64encode(screenshot).decode()
        
        status = {"timestamp": time.time(), "action": f"Loaded {target_url}", 
                  "url": target_url, "screenshot_b64": img_b64, "active": True}
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f)
        
        # ... automation steps ...
        
        clear_broadcast()
        await browser.close()
```

## Dashboard Integration
The dashboard's Live View tab polls for updates every 2 seconds.
The screenshot appears as a live thumbnail showing exactly what the browser sees.
The current action and URL are displayed above the screenshot.

## Best Practices
- Call broadcast() after: page navigation, form field fill, button click, page load completion
- Keep action descriptions short and descriptive: "Filling email", "Submitting form", "Waiting for verification email"
- Always call clear_broadcast() in a try/finally block
- Screenshot adds ~50-100ms per call — don't call it on every keystroke, only on meaningful state changes
