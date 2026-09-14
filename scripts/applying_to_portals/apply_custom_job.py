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
    cover_letter_path: Optional[str] = None,
    headed: bool = False
) -> dict:
    """
    Apply to any external custom job URL using ATSAdapterRegistry.
    
    Args:
        url: Target job URL
        review_mode: If True, pauses at final review screen
        page: Optional Playwright Page object (will create/connect browser if None)
        resume_path: Path to resume file
        cover_letter_path: Optional path to cover letter file
    
    Returns:
        dict: Status dictionary like {"status": "SUCCESS"} or {"status": "LOGIN_REQUIRED"}
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
            browser = await playwright_instance.chromium.launch(headless=not headed, args=["--remote-debugging-port=3000"])
            context = await browser.new_context()
            page = await context.new_page()

            # Update port_info.json so the fallback agent can connect to it
            try:
                PORT_INFO_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(PORT_INFO_FILE, 'w') as f:
                    json.dump({"ws_endpoint": "http://localhost:3000"}, f)
            except Exception as e:
                logger.warning(f"Failed to write port_info.json: {e}")

    try:
        error_message = None
        logger.info(f"🔗 Navigating to target job URL: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Login Wall Heuristic Check
        page_url = page.url.lower()
        sso_domains = ["login.", "sso.", "okta.com", "auth0.com", "accounts.google.com", "signin"]
        if any(domain in page_url for domain in sso_domains):
            logger.info(f"Login wall detected via URL redirect: {page_url}")
            return {"status": "LOGIN_REQUIRED"}

        login_text_exists = await page.evaluate('''() => {
            const text = document.body.innerText.toLowerCase();
            return (text.includes("sign in to apply") || text.includes("log in to apply") || (text.includes("sign in") && text.includes("password")));
        }''')
        
        if login_text_exists:
            logger.info("Login wall detected via page text")
            return {"status": "LOGIN_REQUIRED"}

        # Stealth rename the resume file to avoid detection
        import shutil
        import tempfile
        import os
        
        page_title = await page.title() if page else ""
        safe_title = "".join(c for c in (page_title or "") if c.isalnum() or c in " -_").strip()[:30]
        domain = url.split("/")[2] if url and "//" in url else "unknown"
        
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

        try:
            result = await adapter.apply(
                resume_path=stealth_resume_path,
                user_profile={},
                review_mode=review_mode,
                cover_letter_path=cover_letter_path
            )
            if not result:
                raise Exception("Adapter apply returned False")
            final_status = "SUCCESS"
        except Exception as e:
            logger.warning(f"Standard adapter failed: {e}. Falling back to native API LLM loop.")
            from scripts.common_stuff.custom_llm_agent import CustomLLMAgent
            import os
            
            fast_model = os.getenv("FAST_MODEL", "gemini-3.6-flash")
            expensive_model = os.getenv("EXPENSIVE_MODEL", "gemini-3.6-pro")
            
            from scripts.common_stuff.prompt_manager import load_prompt
            prompt = load_prompt("apply_custom_job_agent")
            
            logger.info("Running custom LLM cascade loop.")
            agent = CustomLLMAgent()
            success = await agent.run_cascade(page, fast_model, expensive_model, prompt)
            
            if success:
                logger.info("Autonomous fallback completed successfully.")
                final_status = "SUCCESS"
                result = True
            else:
                error_message = "Autonomous fallback failed to complete the application"
                logger.error(error_message)
                final_status = "FAILED"
                result = False
        
        # If we reached here, everything was successful up to this point
        pass

    except Exception as e:
        logger.error(f"❌ Error applying to custom job URL {url}: {e}", exc_info=True)
        error_message = str(e)
        final_status = "FAILED"
        result = False

    finally:
        # Take a screenshot half a second after finish (in all cases, even on failure)
        screenshot_path = ""
        if page and not page.is_closed():
            import time
            try:
                await page.wait_for_timeout(500)
                screenshot_dir = PROJECT_ROOT / "scratch" / "screenshots"
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                
                # Use safe_title and domain if defined, otherwise fallbacks
                s_title = locals().get("safe_title", "Application")
                s_domain = locals().get("domain", "unknown")
                screenshot_name = f"apply_{s_domain}_{s_title}_{int(time.time())}.png"
                full_screenshot_path = screenshot_dir / screenshot_name
                
                await page.screenshot(path=str(full_screenshot_path), full_page=False)
                screenshot_path = str(full_screenshot_path)
                logger.info(f"📸 Captured final application state screenshot at {screenshot_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to capture screenshot: {e}")
                
        # Extract Company and Position via LLM
        extracted_company = locals().get("domain", "unknown")
        extracted_position = locals().get("page_title", "Unknown Job")
        if screenshot_path:
            logger.info("Triggering LLM visual analysis to extract metadata...")
            try:
                from scripts.common_stuff.custom_llm_agent import CustomLLMAgent
                from scripts.common_stuff.prompt_manager import load_prompt
                analyze_prompt = load_prompt("apply_custom_job_analysis")

                agent = CustomLLMAgent()
                output = await agent.analyze_image_from_path(screenshot_path, analyze_prompt)
                
                if output:
                    try:
                        import json
                        output = output.strip()
                        if output.startswith("```json"): output = output[7:]
                        if output.startswith("```"): output = output[3:]
                        if output.endswith("```"): output = output[:-3]
                        
                        parsed = json.loads(output.strip())
                        if parsed.get("company") and str(parsed.get("company")).strip():
                            extracted_company = str(parsed.get("company")).strip()
                        if parsed.get("position") and str(parsed.get("position")).strip():
                            extracted_position = str(parsed.get("position")).strip()
                            
                        # Override false positives by verifying visually
                        if "is_success" in parsed:
                            visually_successful = bool(parsed.get("is_success"))
                            if not visually_successful and final_status == "SUCCESS":
                                logger.warning("LLM visual verification determined application actually FAILED despite script reporting success!")
                                final_status = "FAILED"
                                error_message = "Visual verification failed. Screen does not show application success."
                        
                        if final_status == "FAILED" and parsed.get("reason"):
                            llm_reason = parsed["reason"]
                            error_message = f"{error_message or 'Failed'}. LLM Analysis: {llm_reason}"
                    except Exception as json_err:
                        logger.warning(f"Failed to parse LLM analysis JSON: {json_err}. Output was: {output}")
            except Exception as e:
                logger.warning(f"Failed to analyze screenshot: {e}")

        # Log to remote (Google Sheets) ALWAYS
        try:
            from scripts.common_stuff.remote_logger import log_application_to_remote
            status_for_log = "successful" if (locals().get("final_status") == "SUCCESS") else "failed"
            
            # If failed, append the URL to the screenshot path so it shows up in Google Sheets
            final_screenshot_log = screenshot_path
            if status_for_log == "failed" and url:
                final_screenshot_log = f"{screenshot_path} | URL: {url}" if screenshot_path else f"URL: {url}"

            log_application_to_remote(
                job_title=extracted_position,
                company=extracted_company,
                portal=locals().get("adapter").adapter_name() if locals().get("adapter") else "Unknown Portal",
                status=status_for_log,
                extra_data={
                    "log_type": "custom_apply",
                    "url": url,
                    "screenshot_path": final_screenshot_log,
                    "account_created": "No"
                }
            )
        except Exception as log_err:
            logger.error(f"Failed to trigger remote logger: {log_err}")

        if should_close_browser and browser:
            logger.info("Cleaning up browser resources...")
            try:
                await browser.close()
            except Exception:
                pass
            if playwright_instance:
                try:
                    await playwright_instance.stop()
                except Exception:
                    pass

    if locals().get("final_status") == "FAILED" and locals().get("error_message"):
        return {"status": locals().get("final_status"), "error": locals().get("error_message")}
    return {"status": locals().get("final_status", "FAILED")}


def main():
    parser = argparse.ArgumentParser(description="Custom ATS Auto-Apply Engine")
    parser.add_argument("--url", type=str, help="Target job URL")
    parser.add_argument("--file", type=str, help="Text file containing list of job URLs (one per line)")
    parser.add_argument("--review", action="store_true", default=True, help="Pause for manual review before submit (default)")
    parser.add_argument("--no-review", action="store_true", help="Automatically submit applications without review pause")
    parser.add_argument("--resume", type=str, help="Path to custom resume PDF file")
    parser.add_argument("--cover-letter", type=str, help="Path to custom cover letter file (PDF/txt)")
    parser.add_argument("--json", action="store_true", help="Print output as JSON")
    parser.add_argument("--headed", action="store_true", help="Launch browser in headed mode")

    args = parser.parse_args()
    review_mode = not args.no_review
    
    original_stdout = sys.stdout
    if args.json:
        sys.stdout = sys.stderr

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
        results = []
        for idx, url in enumerate(urls_to_process, 1):
            if not args.json:
                logger.info(f"\n--- Processing Job {idx}/{len(urls_to_process)} ---")
            res = await apply_to_custom_url(url, review_mode=review_mode, resume_path=args.resume, cover_letter_path=getattr(args, 'cover_letter', None), headed=args.headed)
            results.append({"url": url, "result": res})
            
        if args.json:
            print(json.dumps(results if len(results) > 1 else results[0]["result"]), file=original_stdout)

    asyncio.run(run_batch())


if __name__ == "__main__":
    main()
