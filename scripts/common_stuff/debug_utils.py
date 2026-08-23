import os
import asyncio
from datetime import datetime
from playwright.async_api import Page
import traceback

async def dump_dom_on_error(page: Page, error: Exception, context_name: str = "error"):
    """
    Dumps the current page HTML DOM, screenshot, and error message to the logs directory.
    """
    try:
        # Find project root logs directory
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        log_dir = os.path.join(project_root, 'logs', 'error_dumps')
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_context = context_name.replace(" ", "_").replace("/", "_").lower()
        base_filename = f"{timestamp}_{safe_context}"
        
        html_path = os.path.join(log_dir, f"{base_filename}.html")
        error_path = os.path.join(log_dir, f"{base_filename}.txt")
        screenshot_path = os.path.join(log_dir, f"{base_filename}.png")
        
        # 1. Save HTML
        try:
            html_content = await page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
        except Exception as html_err:
            html_path = f"Failed to save HTML: {html_err}"
            
        # 2. Save Screenshot
        try:
            await page.screenshot(path=screenshot_path, full_page=True)
        except Exception as ss_err:
            screenshot_path = f"Failed to save screenshot: {ss_err}"
            
        # 3. Save Error Details
        with open(error_path, "w", encoding="utf-8") as f:
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Context: {context_name}\n")
            try:
                f.write(f"URL: {page.url}\n")
            except:
                pass
            f.write(f"\nError Message:\n{str(error)}\n\n")
            f.write("Traceback:\n")
            f.write(traceback.format_exc())
            
        print(f"\n🚨 AUTOMATION FAILED ({context_name}) 🚨")
        print(f"Saved debug info for AI analysis:")
        print(f" 📄 HTML: {html_path}")
        print(f" 🖼️  IMG:  {screenshot_path}")
        print(f" 📝 ERR:  {error_path}\n")
        
        # Also log to Google Sheets/Firebase!
        from scripts.common_stuff.remote_logger import log_application_to_remote
        log_application_to_remote(
            job_title="AUTOMATION FAILURE",
            company=context_name,
            portal="Agent System",
            status="failed",
            extra_data={"error_message": str(error)}
        )
        
    except Exception as e:
        print(f"\n⚠️ Failed to create debug dump: {e}")
