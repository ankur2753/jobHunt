import asyncio
from playwright.async_api import async_playwright
import sys
import os
sys.path.insert(0, os.getcwd())
from scripts.networking.discovery_providers import LinkedInSearchDiscoveryProvider

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="personal_details/linkedin_cookies.json")
        page = await context.new_page()
        
        provider = LinkedInSearchDiscoveryProvider(page)
        
        print("Searching for Baxter International Inc. Software Engineer...")
        candidates = await provider.discover_candidates("Baxter International Inc.", "Software Engineer")
        print(f"Found {len(candidates)} candidates")
        for c in candidates:
            print(c)
            
        await browser.close()

asyncio.run(main())
