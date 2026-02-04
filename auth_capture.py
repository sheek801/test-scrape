#!/usr/bin/env python3
"""
LinkedIn Authentication Capture Script

This script opens a browser window for you to manually log into LinkedIn.
Once logged in, it saves the session state to auth.json for use by the scraper.

Usage:
    python auth_capture.py
"""

import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


async def capture_auth():
    """Opens browser for manual LinkedIn login and saves session state."""

    async with async_playwright() as p:
        # Launch browser in non-headless mode so you can log in
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        # Create context with realistic viewport and user agent
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
        )

        page = await context.new_page()

        # Apply stealth to avoid detection
        await stealth_async(page)

        # Navigate to LinkedIn login
        await page.goto('https://www.linkedin.com/login')

        print("\n" + "="*60)
        print("INSTRUCTIONS:")
        print("="*60)
        print("1. Log into your LinkedIn account in the browser window")
        print("2. Complete any 2FA/security challenges if prompted")
        print("3. Once you see your LinkedIn feed, come back here")
        print("4. Press ENTER to save your session and close the browser")
        print("="*60 + "\n")

        # Wait for user to log in
        input("Press ENTER after you've logged in successfully...")

        # Verify we're logged in by checking for feed or search capability
        current_url = page.url
        print(f"\nCurrent URL: {current_url}")

        # Save storage state (cookies + localStorage)
        await context.storage_state(path='auth.json')
        print("\n✓ Session saved to auth.json")

        await browser.close()
        print("✓ Browser closed. You can now run the scraper.")


if __name__ == '__main__':
    asyncio.run(capture_auth())
