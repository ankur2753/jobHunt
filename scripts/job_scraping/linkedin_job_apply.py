import asyncio
from playwright.async_api import Page

class LinkedInJobApply:
    def __init__(self, page: Page):
        self.page = page
        self.selectors = {
            # Job search and listing
            "job_search_input": 'input[placeholder*="Title, skill or Company"]',
            "location_input": 'input[placeholder*="City"]',
            "search_button": 'button:has-text("Search")',
            "easy_apply_filter": 'button:has-text("Easy Apply")',
            "job_cards": "div.job-card-container--clickable",
            # Easy Apply process
            "easy_apply_button": "button:has-text('Easy Apply')",
            "next_button": 'button[aria-label*="Continue"], button:has-text("Next")',
            "submit_button": 'button[aria-label*="Submit application"]',
            "review_button": 'button[aria-label*="Review"]',
            # Modal and overlay
            "modal": '[role="dialog"]',
            "close_modal": 'button[aria-label*="Dismiss"]',
            "success_message": "text=Application submitted",
        }

    async def apply_to_jobs(self, job_title: str, location: str):
        print(f"Starting job search for '{job_title}' in '{location}'...")
        await self.page.goto("https://www.linkedin.com/jobs/")

        # Search for jobs
        try:
            await self.page.fill(self.selectors["job_search_input"], job_title)
            await self.page.fill(self.selectors["location_input"], location)
            await self.page.press(self.selectors["location_input"], "Enter")
            await self.page.wait_for_load_state("networkidle")
        except Exception as e:
            print(f"Error during job search: {e}")
            return
        
        print("Applying Easy Apply filter...")
        try:
            await self.page.click(self.selectors["easy_apply_filter"])
            await self.page.wait_for_load_state("networkidle")
        except Exception as e:
            print(f"Could not apply Easy Apply filter: {e}")

        print("Searching for job cards...")
        job_cards = await self.page.query_selector_all(self.selectors["job_cards"])
        print(f"Found {len(job_cards)} job(s).")

        for job_card in job_cards:
            await job_card.click()
            await self.page.wait_for_timeout(2000) # Wait for job details to load

            try:
                easy_apply_button = self.page.locator(self.selectors["easy_apply_button"]).first
                await easy_apply_button.click()

                modal = self.page.locator(self.selectors["modal"])
                if await modal.is_visible():
                    print("Applying to a job...")
                    # This is where the logic to fill the form will go.
                    # For now, we'll just close the modal.
                    await self.page.click(self.selectors["close_modal"])
                    print("Closed application modal (for now).")

            except Exception as e:
                print(f"Could not apply to a job: {e}")

        print("Finished applying to jobs.")

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
