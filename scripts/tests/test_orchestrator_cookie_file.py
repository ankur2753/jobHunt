
import unittest
import sys
from pathlib import Path

# Add project root to path to import other modules
sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.orchestrator.orchestrator import LinkedInPlaywright

class TestOrchestratorCookieFile(unittest.TestCase):

    def test_cookie_file_path_is_correct(self):
        """
        Tests if the LinkedInPlaywright class correctly resolves the path
        to the linkedin_cookies.json file.
        """
        # Instantiate the class
        linkedin_playwright = LinkedInPlaywright()

        # Get the resolved cookies_file path
        cookies_file_path = linkedin_playwright.cookies_file

        # 1. Check if the path is absolute
        self.assertTrue(cookies_file_path.is_absolute(), "The path should be absolute.")

        # 2. Check the file name
        self.assertEqual(cookies_file_path.name, "linkedin_cookies.json", "The file name should be 'linkedin_cookies.json'.")

        # 3. Check the parent directory
        self.assertEqual(cookies_file_path.parent.name, "personal_details", "The parent directory should be 'personal_details'.")
        
        # 4. Check that the grandparent is the project root
        # This is a bit more robust
        project_root = Path(__file__).resolve().parents[2]
        self.assertEqual(cookies_file_path.parent.parent, project_root, "The cookie file should be in the 'personal_details' directory at the project root.")

if __name__ == '__main__':
    unittest.main()
