import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="personal_details/linkedin_cookies.json")
        page = await context.new_page()
        
        await page.goto("https://www.linkedin.com/search/results/people/?keywords=Baxter%20International%20Inc.%20Software%20Engineer", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        all_links = await page.locator('a[href*="/in/"]').all()
        seen_urls = set()
        
        for link in all_links:
            href = await link.get_attribute("href")
            if not href or "?" in href: href = href.split("?")[0] if href else ""
            if href in seen_urls or "/in/ACoAA" in href or "search" in href: continue
            seen_urls.add(href)
            
            # Find the card root
            card = link.locator('xpath=./ancestor::div[@data-display-contents="true" or contains(@class, "entity") or contains(@class, "search-result")]').first
            if await card.count() == 0:
                card = link.locator('xpath=../..')
                
            text = await card.text_content()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            # Print lines to debug
            print(f"--- URL: {href} ---")
            print("Lines:", lines[:5])
            
        await browser.close()

asyncio.run(main())
