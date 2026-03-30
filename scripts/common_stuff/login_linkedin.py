import json
import os
import asyncio
from playwright.async_api import async_playwright, expect

class LinkedInPlaywright:
    def __init__(self, cookies_file: str = "linkedin_cookies.json"):
        self.cookies_file = cookies_file
        self.base_url = "https://www.linkedin.com"
        self.browser = None
        self.context = None
        self.page = None

    async def setup_driver(self, headless: bool = False):
        p = await async_playwright().start()
        self.browser = await p.chromium.launch(headless=headless)
        
        # If the cookie file exists, load the context with that state
        if os.path.exists(self.cookies_file):
            print("✅ Loading existing session state...")
            self.context = await self.browser.new_context(
                storage_state=self.cookies_file,
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        else:
            print("⚠️ No session file found. Starting fresh context.")
            self.context = await self.browser.new_context()
        
        self.page = await self.context.new_page()

    async def is_logged_in(self):
        """Check if we are authenticated by looking for the profile identity."""
        try:
            await self.page.goto(self.base_url)
            # Equivalent to your Selenium presence_of_element_located check
            # We look for the 'me' icon or navigation bar
            await self.page.wait_for_selector(".global-nav__me", timeout=5000)
            return True
        except:
            return False

    async def save_session(self):
        """Saves current cookies and local storage to a file."""
        await self.context.storage_state(path=self.cookies_file)
        print(f"💾 Session saved to {self.cookies_file}")

    async def login_manually_and_save(self):
        """Opens browser for manual login, then saves state.Use this if your cookies expire"""
        print("Please log in manually in the browser window...")
        await self.setup_driver(headless=False)
        await self.page.goto(f"{self.base_url}/login")
        
        # Wait for the user to finish login (detecting the feed/home page)
        await self.page.wait_for_url("**/feed/**", timeout=120000) 
        
        # Save the state so we never have to do this again
        await self.save_session()
        print("✅ Login successful and cookies captured!")