#!/usr/bin/env python3
"""Integration test for the rewired Naukri bulk-apply chatbot loop.

Builds a logged-in page from cookies and runs the real production path
(NaukriJobApply.apply_to_recommended_jobs, bulk-select mode) on N jobs,
fully unattended so we can see whether the chatbot drawer completes.
"""

import asyncio
import json
import sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.common_stuff.logging_setup import setup_logging
LOG_FILE = setup_logging(run_name="naukri_test")

from scripts.job_scraping.naukri_job_apply import NaukriJobApply

COOKIES = ROOT / "personal_details/naukri_cookies.json"
N_JOBS = 5


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=str(COOKIES))
        page = await context.new_page()

        applier = NaukriJobApply(page, enable_selector_validation=False)
        applier.enable_human_fallback = False  # unattended: guess + log, never block

        results = await applier.apply_to_recommended_jobs(max_jobs=N_JOBS, use_bulk_select=True)

        print("\n" + "=" * 70)
        print("RESULT SUMMARY")
        print("=" * 70)
        print(json.dumps({k: v for k, v in results.items()
                          if k not in ('selector_validation',)}, indent=2, default=str))

        await page.wait_for_timeout(4000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
