from typing import Optional
import asyncio
from playwright.async_api import Page
from scripts.applying_to_portals.apply_custom_job import apply_to_custom_url

class LinkedInJobApply:
    def __init__(self, page: Page, review_mode: bool = True):
        self.page = page
        self.review_mode = review_mode
        self.selectors = {
            # Job search and listing
            "job_search_input": 'input[id*="jobs-search-box-keyword"], input[aria-label*="title" i], input[placeholder*="title" i]',
            "location_input": 'input[id*="jobs-search-box-location"], input[aria-label*="City" i], input[aria-label*="location" i], input[placeholder*="City" i], input[placeholder*="location" i]',
            "search_button": 'button:has-text("Search")',
            "easy_apply_filter": 'button:has-text("Easy Apply")',
            "job_cards": "div.job-card-container, div.job-card-container--clickable, li.jobs-search-results__list-item, div.job-card-list",
            # Easy Apply process
            "easy_apply_button": "button:has-text('Easy Apply')",
            "external_apply_button": 'a.jobs-apply-button, button:has-text("Apply")',
            "next_button": 'button[aria-label*="Continue"], button:has-text("Next")',
            "submit_button": 'button[aria-label*="Submit application"]',
            "review_button": 'button[aria-label*="Review"]',
            # Modal and overlay
            "modal": '[role="dialog"]',
            "close_modal": 'button[aria-label*="Dismiss"]',
            "success_message": "text=Application submitted",
        }

    async def apply_to_jobs(self, job_title: str, location: str, review_mode: Optional[bool] = None):
        effective_review_mode = self.review_mode if review_mode is None else review_mode
        print(f"Starting job search for '{job_title}' in '{location}' (review_mode={effective_review_mode})...")
        import urllib.parse
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(job_title)}&location={urllib.parse.quote(location)}"
        print(f"Navigating directly to search URL (ALL jobs): {search_url}")
        
        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            await self.page.wait_for_selector(self.selectors["job_cards"], timeout=15000)
        except Exception as e:
            from scripts.common_stuff.debug_utils import dump_dom_on_error
            await dump_dom_on_error(self.page, e, "linkedin_job_search_url")
            print(f"Error loading search results: {e}")
            return
            
        print("Handing over to Unified LLM Agent for job scraping...")
        from scripts.common_stuff.custom_llm_agent import CustomLLMAgent
        
        from scripts.common_stuff.prompt_manager import load_prompt
        prompt = load_prompt("linkedin_job_apply")
        
        llm_agent = CustomLLMAgent()
        success = await llm_agent.execute_loop(
            page=self.page, 
            model_name="gemini-3.7-flash", 
            max_steps=30, 
            prompt=prompt
        )
        
        if success:
            print("LLM finished job scraping successfully.")
        else:
            print("LLM failed to finish job scraping.")

async def main():
    # This is for testing the script directly
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state="linkedin_cookies.json")
        page = await context.new_page()
        
        applier = LinkedInJobApply(page)
        await applier.apply_to_jobs("Software Engineer", "United States")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
