import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="personal_details/linkedin_cookies.json")
        page = await context.new_page()
        
        print("Navigating to LinkedIn search...")
        await page.goto("https://www.linkedin.com/jobs/search/?keywords=Software%20Engineer&location=Bangalore", wait_until="domcontentloaded")
        await asyncio.sleep(5)
        
        job_cards = await page.locator(".job-card-container").all()
        if not job_cards:
            print("No job cards found with .job-card-container, trying .jobs-search__results-list > li")
            job_cards = await page.locator(".jobs-search__results-list > li").all()
            
        print(f"Found {len(job_cards)} job cards")
        
        if job_cards:
            html = await job_cards[0].inner_html()
            print("--- HTML of first card ---")
            print(html)
            
            # test my locators
            company_el = job_cards[0].locator('.job-card-container__primary-description, .job-card-container__company-name, .artdeco-entity-lockup__subtitle, .job-card-list__company-name, span.job-card-container__primary-description').first
            if await company_el.count() > 0:
                print(f"Company: {(await company_el.text_content()).strip()}")
            else:
                print("Company locator failed!")
                
        await browser.close()

asyncio.run(main())
