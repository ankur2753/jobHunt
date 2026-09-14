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
            
            name = (await link.inner_text()).split('\n')[0].strip()
            for term in ["•", "1st", "2nd", "3rd", "degree", "View"]:
                if term in name:
                    name = name.split(term)[0].strip()
            
            # Find the card root by going up until we see multiple newlines or specific classes
            # The most reliable way is just to get the sibling of the p tag that contains the link
            # In the DOM I saw: <p><a ...>name</a></p> <div><p>Headline</p></div>
            # So let's just get inner_text of the parent of parent.
            parent = link.locator('xpath=../..')
            text = await parent.inner_text()
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            
            headline = "LinkedIn Member"
            for line in lines:
                if name in line or "View" in line or "degree" in line or "1st" in line or "2nd" in line or "3rd" in line:
                    continue
                headline = line
                break
                
            print(f"Name: {name}")
            print(f"Headline: {headline}")
            print(f"URL: {href}")
            print("---")
            
        await browser.close()

asyncio.run(main())
