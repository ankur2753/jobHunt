import asyncio
import logging
from playwright.async_api import async_playwright
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.job_scraping.naukri_job_apply import NaukriJobApply

logging.basicConfig(level=logging.INFO)

async def main():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=False)
    context = await browser.new_context(storage_state="/home/ankurkumar/ankur_code/agent/personal_details/naukri_cookies.json")
    page = await context.new_page()
    
    applier = NaukriJobApply(page, None, enable_selector_validation=False)
    result = await applier.apply_to_recommended_jobs(max_jobs=5, use_bulk_select=True)
    
    print("\nFINAL RESULT:", result)
    
    await browser.close()
    p.stop()

if __name__ == "__main__":
    asyncio.run(main())
