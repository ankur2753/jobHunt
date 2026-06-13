import time
import os
import json
import asyncio
import logging
from pathlib import Path
from playwright.async_api import async_playwright, expect

# Add project root to path to import other modules
import sys
sys.path.append(str(Path(__file__).resolve().parents[2]))

# Configure logging early — clean terminal, full detail to logs/<name>_run_<ts>.log.
# Pass --verbose to also stream DEBUG to the console. Must run before importing the
# heavy modules below so HF/transformers progress bars are suppressed at model load.
from scripts.common_stuff.logging_setup import setup_logging
_console_level = logging.DEBUG if '--verbose' in sys.argv else logging.INFO
LOG_FILE = setup_logging(console_level=_console_level, run_name='orchestrator')
logger = logging.getLogger(__name__)
logger.info(f"📂 Full log: {LOG_FILE}")

from scripts.job_scraping.linkedin_job_apply import LinkedInJobApply
from scripts.job_scraping.naukri_job_apply import NaukriJobApply
from scripts.job_scraping.linkedin_job_scraper import LinkedInJobScraper
from scripts.cookie_management_login.naukri_login import NaukriPlaywright
from scripts.cookie_management_login.instahyre_login import InstahyrePlaywright
from scripts.networking.linkedin_cold_message import LinkedInColdMessenger
from scripts.cookie_management_login.naukri_form_filler import NaukriFormFiller
from scripts.cookie_management_login.linkedin_form_filler import LinkedInFormFiller
from scripts.common_stuff.vector_db_manager import VectorDBManager

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
        self.browser = await p.chromium.launch(headless=headless, args=["--remote-debugging-port=3000"])
        self.ws_endpoint = "http://localhost:3000"
        
        logger.debug(f"Cookies file: {self.cookies_file}")
        logger.debug(f"Cookies file exists: {os.path.exists(self.cookies_file)}")
        # If the cookie file exists, load the context with that state
        if os.path.exists(self.cookies_file):
            logger.info("✅ Loading existing session state...")
            self.context = await self.browser.new_context(
                storage_state=self.cookies_file,
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        else:
            logger.warning("⚠️ No session file found. Starting fresh context.")
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
        
        logger.debug(f"Browser endpoint registered: {self.ws_endpoint}")


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
        logger.info(f"💾 Session saved to {self.cookies_file}")


    async def login_manually_and_save(self):
        """Opens browser for manual login, then saves state. Use this if your cookies expire."""
        print("Please log in manually in the browser window...")
        if not self.browser or not self.page:
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

    browser_manager = None
    try:
        print("Which website would you like to use?")
        print("1. LinkedIn")
        print("2. Naukri")
        print("3. InstaHyre")

        website_choice = input("Enter your choice (1, 2, or 3): ")

        if website_choice == '1':
            browser_manager = LinkedInPlaywright()
            await browser_manager.setup_driver()
            if not await browser_manager.is_logged_in():
                if os.path.exists(browser_manager.cookies_file):
                    print("⚠️ Your session has expired. Please log in again.")
                else:
                    print("Not logged into LinkedIn. Please log in manually.")
                await browser_manager.login_manually_and_save()
            else:
                print("Successfully logged into LinkedIn.")
        elif website_choice == '2':
            browser_manager = NaukriPlaywright()
            await browser_manager.setup_driver()
            if not await browser_manager.is_logged_in():
                if os.path.exists(browser_manager.cookies_file):
                    print("⚠️ Your session has expired. Please log in again.")
                else:
                    print("Not logged into Naukri. Please log in manually.")
                await browser_manager.login_manually_and_save()
            else:
                print("Successfully logged into Naukri.")
        elif website_choice == '3':
            print("Coming soon!")
            return
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")
            return

        print("What would you like to do?")
        print("1. Send cold messages")
        print("2. Apply on job portals")
        print("3. Scrape jobs posted in last 24 hours")
        print("4. Auto-fill forms (NEW - Phase 3)")

        choice = input("Enter your choice (1, 2, 3 or 4): ")

        if choice == '1':
            print("Starting the process to send cold messages...")
            profile_urls = input("Enter LinkedIn profile URLs separated by commas: ").split(",")
            profile_urls = [url.strip() for url in profile_urls if url.strip()]
            if not profile_urls:
                print("No profile URLs provided. Aborting cold message flow.")
            else:
                reason = input("Enter a brief reason for connecting / outreach context (optional): ").strip() or None
                messenger = LinkedInColdMessenger(browser_manager.page)
                results = await messenger.send_bulk_outreach(profile_urls, reason)
                for result in results:
                    print(result)
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

                applicator = LinkedInJobApply(browser_manager.page)
                await applicator.apply_to_jobs(job_title, location)
            elif website_choice == '2':
                print("\n🤖 Starting Naukri Auto-Apply Process...")
                print("="*60)
                
                # Initialize Vector DB for form filling
                vector_db = VectorDBManager()
                print("✓ Vector DB initialized")
                
                # Silent auto-apply: Hardcode max_jobs to 5 per batch
                # No user prompt - automatically starts batched application
                max_jobs = 5
                print(f"\n🔄 Starting auto-apply process for {max_jobs} jobs per batch...")
                print(f"   (Run multiple times to apply to more jobs)")
                print("-"*60)
                
                try:
                    # Initialize Naukri job applicator
                    applicator = NaukriJobApply(browser_manager.page, vector_db)
                    
                    # Auto-apply to jobs in batch of 5
                    results = await applicator.apply_to_recommended_jobs(max_jobs=max_jobs)
                    
                    # Print summary
                    print("\n" + "="*60)
                    print("📊 AUTO-APPLY SUMMARY")
                    print("="*60)
                    print(f"Total Attempted: {results['total_attempted']}")
                    print(f"Successful: {results['successful']}")
                    print(f"Failed: {results['failed']}")
                    print(f"Skipped: {results['skipped']}")
                    
                    if results['details']:
                        print("\n📋 Detailed Results:")
                        for detail in results['details']:
                            status_emoji = "✅" if detail['status'] == "completed" else "⚠️" if detail['status'] == "partial" else "❌"
                            print(f"{status_emoji} {detail['job_title']}")
                            print(f"   Status: {detail['status']}")
                            print(f"   Message: {detail['message']}")
                    
                    print("="*60)
                    print(f"\n💡 To apply to more jobs, run this script again and select Naukri → Apply to Jobs")
                
                except Exception as e:
                    print(f"\n❌ Error during auto-apply process: {str(e)}")
                    import traceback
                    traceback.print_exc()
            else:
                print("Job application for this portal is not yet implemented.")
        elif choice == '3':
            print("Starting the process to scrape recent job links...")
            if website_choice == '1':
                # Load job preferences and user details to get default values
                project_root = Path(__file__).parent.parent.parent
                job_prefs_path = project_root / "personal_details" / "job_prefrences.json"

                if not job_prefs_path.exists():
                    print(f"⚠️ Missing job preferences file.")
                    print(f"Ensure 'job_prefrences.json' exists in the 'personal_details/' directory.")
                    return

                with open(job_prefs_path, 'r') as f:
                    job_prefs = json.load(f)

                job_title = input(f"Enter job title to search for (default: {job_prefs.get('targetTitles', ['Software Engineer'])[0]}): ").strip() or job_prefs.get('targetTitles', ['Software Engineer'])[0]
                location = input(f"Enter location (default: {job_prefs.get('preferredLocations', ['Remote'])[0]}): ").strip() or job_prefs.get('preferredLocations', ['Remote'])[0]
                
                scraper = LinkedInJobScraper(browser_manager.page, job_title, location)
                await scraper.scrape_jobs()
            else:
                print("Job scraping for this portal is not yet implemented.")
        
        elif choice == '4':
            print("\n🤖 Starting Auto-Fill Form Process...")
            print("="*60)
            
            # Initialize Vector DB for semantic matching
            vector_db = VectorDBManager()
            print("✓ Vector DB initialized")
            
            if website_choice == '1':
                print("\n📋 LinkedIn Form Filler")
                print("-"*60)
                
                job_url = input("Enter LinkedIn job URL (e.g., https://www.linkedin.com/jobs/123456/): ").strip()
                if not job_url:
                    print("❌ No job URL provided")
                    return
                
                print("\nOptions:")
                print("1. Dry-run (detect questions only)")
                print("2. Auto-fill with human fallback (recommended)")
                print("3. Auto-fill and submit")
                
                mode = input("Select mode (1, 2, or 3): ").strip() or "2"
                
                dry_run = mode == '1'
                submit = mode == '3'
                allow_human = True
                
                print("\n🔄 Processing LinkedIn job application...")
                print("-"*60)
                
                form_filler = LinkedInFormFiller(
                    browser_manager.page,
                    vector_db,
                    confidence_threshold=0.65,  # LinkedIn balanced threshold
                    enable_logging=True
                )
                
                try:
                    session = await form_filler.fill_linkedin_job_application(
                        job_url=job_url,
                        max_questions=None,
                        dry_run=dry_run,
                        allow_human_input=allow_human,
                        submit_form=submit
                    )
                    
                    # Print results
                    report = form_filler.get_session_report()
                    print("\n" + "="*60)
                    print("📊 FORM FILLING REPORT - LinkedIn")
                    print("="*60)
                    print(f"Job ID: {report.get('job_id')}")
                    print(f"Job Title: {report.get('job_title')}")
                    print(f"Company: {report.get('company_name')}")
                    print(f"Status: {report.get('status').upper()}")
                    print(f"Duration: {report.get('duration_seconds', 0):.1f}s")
                    
                    if report.get('form_stats'):
                        stats = report['form_stats']
                        print(f"\nForm Statistics:")
                        print(f"  • Total Questions: {stats['total_questions']}")
                        print(f"  • Auto-Filled: {stats['auto_filled']}")
                        print(f"  • Skipped: {stats['skipped']}")
                        print(f"  • Failed: {stats['failed']}")
                        print(f"  • Fill Rate: {stats['fill_rate']*100:.1f}%")
                    
                    if report.get('manual_answers_count', 0) > 0:
                        print(f"\nManual Answers Provided: {report['manual_answers_count']}")
                        if report.get('manual_answers'):
                            for q, a in report['manual_answers'].items():
                                print(f"  • {q[:50]}... → {a[:50]}")
                    
                    if report.get('error'):
                        print(f"\n❌ Error: {report['error']}")
                    
                    print("="*60)
                
                except Exception as e:
                    print(f"\n❌ Error during form filling: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            elif website_choice == '2':
                print("\n📋 Naukri Form Filler")
                print("-"*60)
                
                job_url = input("Enter Naukri job URL (e.g., https://www.naukri.com/job-details-...): ").strip()
                if not job_url:
                    print("❌ No job URL provided")
                    return
                
                print("\nOptions:")
                print("1. Dry-run (detect questions only)")
                print("2. Auto-fill with human fallback (recommended)")
                print("3. Auto-fill and submit")
                
                mode = input("Select mode (1, 2, or 3): ").strip() or "2"
                
                dry_run = mode == '1'
                submit = mode == '3'
                allow_human = True
                
                print("\n🔄 Processing Naukri job application...")
                print("-"*60)
                
                form_filler = NaukriFormFiller(
                    browser_manager.page,
                    vector_db,
                    confidence_threshold=0.70,  # Naukri stricter threshold
                    enable_logging=True
                )
                
                try:
                    session = await form_filler.fill_naukri_job_application(
                        job_url=job_url,
                        max_questions=None,
                        dry_run=dry_run,
                        allow_human_input=allow_human,
                        submit_form=submit
                    )
                    
                    # Print results
                    report = form_filler.get_session_report()
                    print("\n" + "="*60)
                    print("📊 FORM FILLING REPORT - Naukri")
                    print("="*60)
                    print(f"Job ID: {report.get('job_id')}")
                    print(f"Job Title: {report.get('job_title')}")
                    print(f"Company: {report.get('company_name')}")
                    print(f"Status: {report.get('status').upper()}")
                    print(f"Duration: {report.get('duration_seconds', 0):.1f}s")
                    
                    if report.get('form_stats'):
                        stats = report['form_stats']
                        print(f"\nForm Statistics:")
                        print(f"  • Total Questions: {stats['total_questions']}")
                        print(f"  • Auto-Filled: {stats['auto_filled']}")
                        print(f"  • Skipped: {stats['skipped']}")
                        print(f"  • Failed: {stats['failed']}")
                        print(f"  • Fill Rate: {stats['fill_rate']*100:.1f}%")
                    
                    if report.get('manual_answers_count', 0) > 0:
                        print(f"\nManual Answers Provided: {report['manual_answers_count']}")
                        if report.get('manual_answers'):
                            for q, a in report['manual_answers'].items():
                                print(f"  • {q[:50]}... → {a[:50]}")
                    
                    if report.get('error'):
                        print(f"\n❌ Error: {report['error']}")
                    
                    print("="*60)
                
                except Exception as e:
                    print(f"\n❌ Error during form filling: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
            else:
                print("Form filling for this portal is not yet implemented.")
        

    finally:
        if browser_manager and browser_manager.browser:
            await browser_manager.browser.close()
            print("Browser closed.")
        release_lock()

if __name__ == "__main__":
    asyncio.run(main())
