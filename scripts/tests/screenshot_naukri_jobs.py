import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=False)
    context = await browser.new_context(storage_state="/home/ankurkumar/ankur_code/agent/personal_details/naukri_cookies.json")
    page = await context.new_page()
    await page.goto("https://www.naukri.com/mnjuser/recommendedjobs", wait_until="domcontentloaded")
    await page.wait_for_timeout(15000)  # Wait 15 seconds for jobs to load
    await page.screenshot(path="naukri_jobs.png")
    html = await page.content()
    with open("naukri_jobs.html", "w") as f:
        f.write(html)
    await browser.close()
    p.stop()

if __name__ == "__main__":
    asyncio.run(main())
