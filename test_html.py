import asyncio
from playwright.async_api import async_playwright
import sys
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="personal_details/linkedin_cookies.json")
        page = await context.new_page()
        
        await page.goto("https://www.linkedin.com/search/results/people/?keywords=Baxter%20International%20Inc.%20Software%20Engineer", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        all_links = await page.locator('a[href*="/in/"]').all()
        if all_links:
            link = all_links[0]
            li_locator = link.locator('xpath=./ancestor::li').first
            if await li_locator.count() > 0:
                print("--- Found LI ---")
                html = await li_locator.inner_html()
                print(html)
            else:
                print("No LI ancestor!")
                div_locator = link.locator('xpath=./ancestor::div[contains(@class, "search-result") or contains(@class, "entity") or @data-urn]').first
                if await div_locator.count() > 0:
                    print("--- Found DIV ---")
                    html = await div_locator.inner_html()
                    print(html)
                else:
                    print("Could not find any card container. Using parent of parent.")
                    parent = link.locator('xpath=../..')
                    print(await parent.inner_html())
                    
        await browser.close()

asyncio.run(main())
