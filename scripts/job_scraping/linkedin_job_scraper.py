
import asyncio
import csv
from pathlib import Path
from datetime import datetime
from playwright.async_api import Page

class LinkedInJobScraper:
    def __init__(self, page: Page, job_title: str, location: str):
        self.page = page
        self.job_title = job_title
        self.location = location
        self.base_url = "https://www.linkedin.com"

    async def scrape_jobs(self):
        # Construct the search URL
        search_url = f"{self.base_url}/jobs/search/?keywords={self.job_title}&location={self.location}"
        await self.page.goto(search_url, wait_until="load")
        await asyncio.sleep(2) # Wait for page to settle

        # Click the "Date posted" filter and select "Past 24 hours"
        # Note: LinkedIn has multiple buttons with the same name, we need to be specific
        await self.page.locator('button:has-text("Date posted")').first.click()
        await self.page.locator('label:has-text("Past 24 hours")').first.click()
        
        # Click the "Show results" button
        show_results_button = self.page.locator('button:has-text("Show results")')
        if await show_results_button.is_visible():
            await show_results_button.click()

        await self.page.wait_for_load_state("networkidle")
        
        # Scroll down to load all jobs
        # This is a simplified scroll, a more robust solution would be needed for many jobs
        for _ in range(5): # scroll 5 times
            await self.page.keyboard.press("End")
            await asyncio.sleep(2)

        # Scrape job links
        job_links = []
        job_cards = await self.page.locator(".jobs-search__results-list .job-card-list__title").all()
        for card in job_cards:
            link = await card.get_attribute("href")
            if link:
                job_links.append(self.base_url + link)
        
        # Save to CSV
        logs_dir = Path(__file__).resolve().parents[2] / "logs"
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_path = logs_dir / f"linkedin_jobs_{timestamp}.csv"

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['url'])
            for link in job_links:
                writer.writerow([link])
        
        print(f"Scraped {len(job_links)} job links and saved to {file_path}")


