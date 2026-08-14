"""
Standalone Custom & External ATS Auto-Apply Engine
Supports direct application to custom job URLs (Workday, Greenhouse, Lever, SmartRecruiters, Ashby, Generic).

Usage via CLI:
    python apply_custom_job.py --url "https://company.wd1.myworkdayjobs.com/Careers/job/123"
    python apply_custom_job.py --file job_urls.txt --review
"""

import sys
import json
import asyncio
import logging
import argparse
from pathlib import Path
from typing import Optional, List
from playwright.async_api import async_playwright, Page

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.applying_to_portals.ats_adapters import ATSAdapterRegistry
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.logging_setup import setup_logging

LOG_FILE = setup_logging(console_level=logging.INFO, run_name="apply_custom_job")
logger = logging.getLogger(__name__)

PORT_INFO_FILE = PROJECT_ROOT / "scripts" / "common_stuff" / "port_info.json"
RESUME_PATH = PROJECT_ROOT / "resumes" / "resume.pdf"


async def apply_to_custom_url(
    url: str,
    review_mode: bool = True,
    page: Optional[Page] = None,
    resume_path: Optional[str] = None,
    cover_letter_path: Optional[str] = None
) -> bool:
    """
    Apply to any external custom job URL using ATSAdapterRegistry.
    
    Args:
        url: Target job URL
        review_mode: If True, pauses at final review screen
        page: Optional Playwright Page object (will create/connect browser if None)
        resume_path: Path to resume file
        cover_letter_path: Optional path to cover letter file
    
    Returns:
        bool: True if completed/paused successfully, False on error
    """
    effective_resume = resume_path or str(RESUME_PATH)
    should_close_browser = False
    playwright_instance = None
    browser = None

    if page is None:
        should_close_browser = True
        playwright_instance = await async_playwright().start()
        
        # Connect to existing browser if port_info.json exists
        connected = False
        if PORT_INFO_FILE.exists():
            try:
                with open(PORT_INFO_FILE, 'r') as f:
                    data = json.load(f)
                    ws = data.get("ws_endpoint")
                if ws:
                    logger.info(f"🔄 Connecting to existing browser session at {ws}...")
                    browser = await playwright_instance.chromium.connect_over_cdp(ws)
                    context = browser.contexts[0] if browser.contexts else await browser.new_context()
                    page = await context.new_page()
                    connected = True
            except Exception as e:
                logger.warning(f"Could not connect to existing browser: {e}")

        if not connected:
            logger.info("🌐 Launching new Chromium browser instance...")
            browser = await playwright_instance.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

    try:
        logger.info(f"🔗 Navigating to target job URL: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Stealth rename the resume file to avoid detection
        import shutil
        import tempfile
        import os
        
        page_title = await page.title()
        safe_title = "".join(c for c in page_title if c.isalnum() or c in " -_").strip()[:30]
        domain = url.split("/")[2] if "//" in url else "unknown"
        
        stealth_resume_path = effective_resume
        if effective_resume and Path(effective_resume).exists():
            safe_role = safe_title[:15].replace(" ", "_") if safe_title else "Application"
            temp_dir = Path(tempfile.gettempdir()) / "job_hunt_stealth"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Preserve original extension
            ext = Path(effective_resume).suffix or ".pdf"
            stealth_resume_name = f"Ankur_Resume_{safe_role}{ext}"
            stealth_resume_path = str(temp_dir / stealth_resume_name)
            
            shutil.copy2(effective_resume, stealth_resume_path)
            logger.info(f"🕵️ Copied resume to stealth filename: {stealth_resume_name}")

        # Match ATS Adapter
        adapter = await ATSAdapterRegistry.get_adapter(page, url)
        logger.info(f"🚀 Executing ATS Adapter '{adapter.adapter_name()}' for URL: {url}")

        result = await adapter.apply(
            resume_path=stealth_resume_path,
            user_profile={},
            review_mode=review_mode,
            cover_letter_path=cover_letter_path
        )
        
        # Take a screenshot half a second after finish
        import time
        await page.wait_for_timeout(500)
        screenshot_dir = PROJECT_ROOT / "scratch" / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract title/company if possible from page title
        # (reusing variables calculated earlier for the resume name)
        
        screenshot_name = f"apply_{domain}_{safe_title}_{int(time.time())}.png"
        screenshot_path = screenshot_dir / screenshot_name
        
        try:
            await page.screenshot(path=str(screenshot_path), full_page=False)
            logger.info(f"📸 Captured final application state screenshot at {screenshot_path}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to capture screenshot: {e}")
            
        # Log to remote (Google Sheets)
        from scripts.common_stuff.remote_logger import log_application_to_remote
        status = "successful" if result else "failed"
        log_application_to_remote(
            job_title=page_title,
            company=domain,
            portal=adapter.adapter_name(),
            status=status,
            extra_data={
                "url": url,
                "screenshot_path": str(screenshot_path),
                "account_created": "No" # Placeholder for future logic if account creation is added
            }
        )
        
        return result

    except Exception as e:
        logger.error(f"❌ Error applying to custom job URL {url}: {e}", exc_info=True)
        return False

    finally:
        if should_close_browser and browser:
            logger.info("Cleaning up browser resources...")
            await browser.close()
            if playwright_instance:
                await playwright_instance.stop()


def main():
    parser = argparse.ArgumentParser(description="Custom ATS Auto-Apply Engine")
    parser.add_argument("--url", type=str, help="Target job URL")
    parser.add_argument("--file", type=str, help="Text file containing list of job URLs (one per line)")
    parser.add_argument("--review", action="store_true", default=True, help="Pause for manual review before submit (default)")
    parser.add_argument("--no-review", action="store_true", help="Automatically submit applications without review pause")
    parser.add_argument("--resume", type=str, help="Path to custom resume PDF file")
    parser.add_argument("--cover-letter", type=str, help="Path to custom cover letter file (PDF/txt)")

    args = parser.parse_args()
    review_mode = not args.no_review

    urls_to_process: List[str] = []
    if args.url:
        urls_to_process.append(args.url)
    elif args.file:
        file_path = Path(args.file)
        if file_path.exists():
            with open(file_path, "r") as f:
                urls_to_process = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        else:
            logger.error(f"File not found: {args.file}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(0)

    logger.info(f"Found {len(urls_to_process)} job URL(s) to process (review_mode={review_mode}).")

    async def run_batch():
        for idx, url in enumerate(urls_to_process, 1):
            logger.info(f"\n--- Processing Job {idx}/{len(urls_to_process)} ---")
            await apply_to_custom_url(url, review_mode=review_mode, resume_path=args.resume, cover_letter_path=getattr(args, 'cover_letter', None))

    asyncio.run(run_batch())


if __name__ == "__main__":
    main()
