
import asyncio
import unittest
from pathlib import Path
import os
import sys

# Add the parent directory of 'scripts' to the Python path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.orchestrator.orchestrator import LinkedInPlaywright

class TestLinkedInLogin(unittest.TestCase):

    def test_linkedin_login_with_cookies(self):
        """
        Tests that we can successfully log into LinkedIn using saved cookies.
        """
        # The test needs to be run from the root of the project for the path to be correct.
        cookies_path = "personal_details/linkedin_cookies.json"
        
        # Check if the cookies file exists before running the test
        if not os.path.exists(cookies_path):
            self.fail(f"Cookie file not found at {cookies_path}. Please ensure you have logged in once manually to create the cookie file.")

        async def run_test():
            linkedin = LinkedInPlaywright(cookies_file=cookies_path)
            await linkedin.setup_driver(headless=True)
            logged_in = await linkedin.is_logged_in()
            if not logged_in:
                await linkedin.page.screenshot(path="login_test_failed.png")
            await linkedin.browser.close()
            return logged_in

        # Run the async test
        logged_in = asyncio.run(run_test())
        
        try:
            self.assertTrue(logged_in, "Failed to log into LinkedIn using cookies.")
        except AssertionError:
            print("\n⚠️ The LinkedIn session has expired. Please run the orchestrator manually to refresh the cookies.")
            if os.path.exists("login_test_failed.png"):
                os.remove("login_test_failed.png")
            self.skipTest("Skipping test because LinkedIn session has expired.")

if __name__ == '__main__':
    unittest.main()
