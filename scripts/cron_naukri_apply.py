import asyncio
from pathlib import Path
import sys
import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from scripts.cookie_management_login.naukri_login import NaukriPlaywright
from scripts.job_scraping.naukri_job_apply import NaukriJobApply
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.orchestrator.orchestrator import get_lock, release_lock

async def run_apply():
    print(f"[{datetime.datetime.now()}] Starting automated cron job...")
    if not get_lock():
        print("Could not acquire lock. Another process is running.")
        return

    browser_manager = None
    try:
        browser_manager = NaukriPlaywright()
        # Run headed since Naukri blocks headless browsers (Access Denied)
        await browser_manager.setup_driver(headless=False)
        
        if not await browser_manager.is_logged_in():
            print("❌ Session expired or not logged in. Please run orchestrator.py manually to re-authenticate.")
            return
            
        print("✅ Session active. Initializing Vector DB...")
        vector_db = VectorDBManager()
        
        print("🔄 Applying to 5 jobs on Naukri...")
        applicator = NaukriJobApply(browser_manager.page, vector_db)
        results = await applicator.apply_to_recommended_jobs(max_jobs=5)
        
        print(f"📊 Auto-apply complete. Successful: {results['successful']}, Failed: {results['failed']}, Skipped: {results['skipped']}")

        # Note: Profile Last Working Day update (current date + 60 days) is handled
        # automatically at the beginning of applicator.apply_to_recommended_jobs()

    except Exception as e:
        print(f"❌ Error during cron execution: {str(e)}")
    finally:
        if browser_manager and browser_manager.browser:
            await browser_manager.browser.close()
            print("Browser closed.")
        release_lock()

if __name__ == "__main__":
    asyncio.run(run_apply())
