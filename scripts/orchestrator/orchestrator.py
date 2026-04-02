import time
import os
import json
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, expect

# Add project root to path to import other modules
import sys
sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.job_scraping.linkedin_job_apply import LinkedInJobApply

# Define paths
COMMON_STUFF_DIR = Path(__file__).parent.parent / "common_stuff"
PORT_INFO_FILE = COMMON_STUFF_DIR / "port_info.json"
LOCK_EXPIRY = 300  # 5 minutes

class LinkedInPlaywright:
    def __init__(self, cookies_file: str = "../../personal_details/linkedin_cookies.json"):
        script_dir = Path(__file__).parent
        self.cookies_file = (script_dir / cookies_file).resolve()
        self.base_url = "https://www.linkedin.com"
        self.browser = None
        self.context = None
        self.page = None

    async def setup_driver(self, headless: bool = False):
        p = await async_playwright().start()
        self.browser = await p.chromium.launch(headless=headless)
        print(self.cookies_file)
        print(os.path.exists(self.cookies_file))
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

def get_lock():
    """
    Tries to acquire a lock on the port_info.json file.
    If the lock is acquired, it returns True.
    If the file is locked by another process and the lock is not expired, it returns False.
    If the lock is expired, it acquires the lock and returns True.
    """
    if PORT_INFO_FILE.exists():
        with open(PORT_INFO_FILE, 'r+') as f:
            try:
                data = json.load(f)
                lock_time = data.get("lock_time", 0)
                if time.time() - lock_time < LOCK_EXPIRY:
                    print("Another process is running. Please try again later.")
                    return False
            except json.JSONDecodeError:
                # File is empty or corrupted, take over
                pass
            # Lock is expired or file is invalid, acquire lock
            f.seek(0)
            json.dump({"lock_time": time.time()}, f)
            f.truncate()
            return True
    else:
        # File doesn't exist, create it and acquire lock
        with open(PORT_INFO_FILE, 'w') as f:
            json.dump({"lock_time": time.time()}, f)
        return True

def release_lock():
    """Releases the lock on the port_info.json file."""
    if PORT_INFO_FILE.exists():
        try:
            os.remove(PORT_INFO_FILE)
            print("Lock released.")
        except OSError as e:
            print(f"Error releasing lock: {e}")


async def main():
    """
    Main function for the orchestrator.
    """
    if not get_lock():
        return

    linkedin = None
    try:
        print("Which website would you like to use?")
        print("1. LinkedIn")
        print("2. Naukri")
        print("3. InstaHyre")

        website_choice = input("Enter your choice (1, 2, or 3): ")

        if website_choice == '1':
            linkedin = LinkedInPlaywright()
            await linkedin.setup_driver()
            if not await linkedin.is_logged_in():
                if os.path.exists(linkedin.cookies_file):
                    print("⚠️ Your session has expired. Please log in again.")
                else:
                    print("Not logged into LinkedIn. Please log in manually.")
                await linkedin.login_manually_and_save()
            else:
                print("Successfully logged into LinkedIn.")
        elif website_choice in ['2', '3']:
            print("Coming soon!")
            return
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
            return

        print("What would you like to do?")
        print("1. Send cold messages")
        print("2. Apply on job portals")

        choice = input("Enter your choice (1 or 2): ")

        if choice == '1':
            print("Starting the process to send cold messages...")
            # Here you would call the script for sending cold messages
            # For example:
            # os.system("python3 scripts/networking/send_messages.py")
        elif choice == '2':
            print("Starting the process to apply on job portals...")
            # Here you would call the script for applying on job portals
            # For example:
            # os.system("python3 scripts/applying_to_portals/apply.py")
            if website_choice == '1':
                print("Starting the process to apply for jobs on LinkedIn...")
                
                # Load job preferences and user details
                project_root = Path(__file__).parent.parent.parent
                job_prefs_path = project_root / "personal_details" / "job_prefrences.json"
                user_details_path = project_root / "personal_details" / "user_details.json"

                if not job_prefs_path.exists() or not user_details_path.exists():
                    print(f"⚠️ Missing personal details or job preferences files.")
                    print(f"Ensure 'job_prefrences.json' and 'user_details.json' exist in the 'personal_details/' directory.")
                    return

                with open(job_prefs_path, 'r') as f:
                    job_prefs = json.load(f)
                
                with open(user_details_path, 'r') as f:
                    user_details = json.load(f)

                job_title = input(f"Enter job title to search for (default: {job_prefs.get('targetTitles', ['Software Engineer'])[0]}): ").strip() or job_prefs.get('targetTitles', ['Software Engineer'])[0]
                location = input(f"Enter location (default: {job_prefs.get('preferredLocations', ['Remote'])[0]}): ").strip() or job_prefs.get('preferredLocations', ['Remote'])[0]
                max_apps_str = input("Maximum number of applications (default 5): ").strip() or "5"
                max_apps = int(max_apps_str)

                applicator = LinkedInJobApply(linkedin.page)
                await applicator.apply_to_jobs(job_title, location)
            else:
                print("Job application for this portal is not yet implemented.")
        else:
            print("Invalid choice. Please enter 1 or 2.")

    finally:
        if linkedin and linkedin.browser:
            await linkedin.browser.close()
            print("Browser closed.")
        release_lock()

if __name__ == "__main__":
    asyncio.run(main())
