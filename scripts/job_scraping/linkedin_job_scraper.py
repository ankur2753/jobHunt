
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
        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
        except Exception as e:
            print(f"Navigation warning (likely tracking scripts): {e}")
        await asyncio.sleep(2) # Wait for page to settle

        # Click the "Date posted" filter and select "Past 24 hours"
        # Note: LinkedIn has multiple buttons with the same name, we need to be specific
        await self.page.locator('button:has-text("Date posted")').first.click()
        await self.page.locator('label:has-text("Past 24 hours")').first.click()
        
        # Click the "Show results" button
        show_results_button = self.page.locator('button:has-text("Show results")')
        if await show_results_button.is_visible():
            await show_results_button.click()

        # Replacing networkidle with sleep to prevent timeout from tracking/telemetry requests on LinkedIn
        await asyncio.sleep(5)
        
        # Scroll down to load all jobs
        # This is a simplified scroll, a more robust solution would be needed for many jobs
        for _ in range(5): # scroll 5 times
            await self.page.keyboard.press("End")
            await asyncio.sleep(2)

        # Scrape job details
        scraped_jobs = []
        # Look for job card containers
        job_cards = await self.page.locator(".job-card-container, .jobs-search__results-list > li").all()
        for card in job_cards:
            try:
                # Extract URL and Title
                link_el = card.locator('a.job-card-container__link, a.job-card-list__title').first
                if await link_el.count() == 0:
                    continue
                
                link = await link_el.get_attribute("href")
                if not link:
                    continue
                    
                # To prevent capturing screen-reader duplicate text, try to get just the visible text
                title_el = link_el.locator('strong').first
                if await title_el.count() > 0:
                    title_text = (await title_el.text_content()).strip()
                else:
                    title_text = (await link_el.inner_text()).strip().split('\n')[0]
                    
                if not title_text:
                    title_text = self.job_title

                # Extract Company
                company_el = card.locator('.job-card-container__primary-description, .job-card-container__company-name, .artdeco-entity-lockup__subtitle').first
                company_text = "Unknown Company"
                if await company_el.count() > 0:
                    company_text = (await company_el.text_content()).strip()
                
                if not link.startswith("http"):
                    link = self.base_url + link
                
                # Remove query parameters for cleaner URLs
                link = link.split('?')[0]
                
                scraped_jobs.append({
                    'url': link,
                    'job_title': title_text,
                    'company': company_text,
                    'referral_status': 'Pending'
                })
            except Exception as e:
                pass
                
        # Deduplicate based on URL
        unique_jobs = list({j['url']: j for j in scraped_jobs}.values())
        
        # Save raw URLs to logs
        logs_dir = Path(__file__).resolve().parents[2] / "logs"
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_path = logs_dir / f"linkedin_jobs_{timestamp}.csv"

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['url'])
            for job in unique_jobs:
                writer.writerow([job['url']])
        
        # Write to jobs_database.csv in personal_details directory (format required by referral helper)
        project_root = Path(__file__).resolve().parents[2]
        db_file = project_root / "personal_details" / "jobs_database.csv"
        
        db_file.parent.mkdir(parents=True, exist_ok=True)
        file_exists = db_file.exists()
        
        # Read existing URLs to prevent duplicating entries across runs
        existing_urls = set()
        if file_exists:
            with open(db_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'url' in row:
                        existing_urls.add(row['url'])
                        
        with open(db_file, 'a', newline='', encoding='utf-8') as f:
            fieldnames = ['url', 'company', 'job_title', 'referral_status']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            
            added_count = 0
            for job in unique_jobs:
                if job['url'] not in existing_urls:
                    writer.writerow({
                        'url': job['url'],
                        'company': job['company'],
                        'job_title': job['job_title'],
                        'referral_status': job['referral_status']
                    })
                    added_count += 1

        print(f"Scraped {len(unique_jobs)} unique jobs. Added {added_count} new jobs to {db_file}")


