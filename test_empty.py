import asyncio
from playwright.async_api import async_playwright
import sys
import os
sys.path.insert(0, os.getcwd())
from scripts.networking.discovery_providers import LinkedInSearchDiscoveryProvider
from scripts.networking.linkedin_referral_helper import LinkedInReferralHelper

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="personal_details/linkedin_cookies.json")
        page = await context.new_page()
        
        provider = LinkedInSearchDiscoveryProvider(page)
        helper = LinkedInReferralHelper(page, provider)
        
        jobs = [
            ("Tenarai", "Software Engineer"),
            ("Quik Hire Staffing", "Software Engineer"),
            ("1% Club", "Software Engineer")
        ]
        
        for company, keyword in jobs:
            print(f"Searching for {company} {keyword}...")
            candidates = await provider.discover_candidates(company, keyword)
            print(f"Found {len(candidates)} candidates")
            for c in candidates:
                score = helper.score_candidate(c["headline"], keyword)
                print(f"  [{score}] {c['name']} - {c['headline']}")
            
        await browser.close()

asyncio.run(main())
