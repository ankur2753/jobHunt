import os
import json
import time
from pathlib import Path
from playwright.async_api import async_playwright

COMMON_STUFF_DIR = Path(__file__).resolve().parents[1] / "common_stuff"
PORT_INFO_FILE = COMMON_STUFF_DIR / "port_info.json"

class NaukriPlaywright:
    def __init__(self, cookies_file: str = "../../personal_details/naukri_cookies.json"):
        script_dir = Path(__file__).parent
        self.cookies_file = (script_dir / cookies_file).resolve()
        self.base_url = "https://www.naukri.com"
        self.browser_server = None
        self.ws_endpoint = None
        self.browser = None
        self.context = None
        self.page = None

    async def setup_driver(self, headless: bool = False, port: int = 3000):
        p = await async_playwright().start()
        
        connected = False
        if PORT_INFO_FILE.exists():
            try:
                with open(PORT_INFO_FILE, 'r') as f:
                    data = json.load(f)
                    ws = data.get("ws_endpoint", f"http://localhost:{port}")
                print(f"🔄 Attempting to connect to existing browser at {ws}...")
                self.browser = await p.chromium.connect_over_cdp(ws)
                self.ws_endpoint = ws
                if self.browser.contexts:
                    self.context = self.browser.contexts[0]
                    if self.context.pages:
                        self.page = self.context.pages[0]
                    else:
                        self.page = await self.context.new_page()
                else:
                    self.context = await self.browser.new_context()
                    self.page = await self.context.new_page()
                print("✅ Connected to existing browser session successfully!")
                connected = True
            except Exception as e:
                print(f"⚠️ Could not connect to existing browser: {e}. Launching new one...")

        if not connected:
            # Start the browser with remote debugging
            self.browser = await p.chromium.launch(headless=headless, args=[f"--remote-debugging-port={port}"])
            self.ws_endpoint = f"http://localhost:{port}"
            
            print(self.cookies_file)
            if os.path.exists(self.cookies_file):
                print("✅ Loading existing session state for Naukri...")
                self.context = await self.browser.new_context(
                    storage_state=self.cookies_file,
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                )
            else:
                print("⚠️ No session file found. Starting fresh context for Naukri.")
                self.context = await self.browser.new_context()
            
            self.page = await self.context.new_page()

            # Update port_info.json with session memory
            if PORT_INFO_FILE.exists():
                with open(PORT_INFO_FILE, 'r+') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = {}
                    data["ws_endpoint"] = self.ws_endpoint
                    data["cookies_file"] = str(self.cookies_file)
                    f.seek(0)
                    json.dump(data, f)
                    f.truncate()
            else:
                # File doesn't exist, create it
                PORT_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(PORT_INFO_FILE, 'w') as f:
                    json.dump({"ws_endpoint": self.ws_endpoint, "cookies_file": str(self.cookies_file)}, f)

    async def is_logged_in(self):
        """Check if we are authenticated by looking for the profile identity."""
        try:
            await self.page.goto(self.base_url)
            # A common selector for logged-in users on Naukri is .nI-gNb-drawer__icon or user avatar
            await self.page.wait_for_selector(".nI-gNb-drawer__icon, .nI-gNb-info__sub-title", timeout=5000)
            return True
        except:
            await self.page.screenshot(path="naukri_login_failed.png")
            return False

    async def save_session(self):
        """Saves current cookies and local storage to a file."""
        self.cookies_file.parent.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=self.cookies_file)
        print(f"💾 Session saved to {self.cookies_file}")

    async def login_manually_and_save(self):
        """Opens browser for manual login, then saves state.Use this if your cookies expire"""
        print("Please log in manually in the browser window...")
        # Assuming setup_driver has been called already since we are doing logic
        if not self.browser:
             await self.setup_driver(headless=False)
             
        await self.page.goto(f"{self.base_url}/nlogin/login")
        
        # Wait for the user to finish login
        try:
            await self.page.wait_for_selector(".nI-gNb-drawer__icon, .nI-gNb-info__sub-title", timeout=120000) 
            await self.save_session()
            print("✅ Login successful and cookies captured for Naukri!")
        except Exception as e:
            print("Login failed or timed out.", e)
