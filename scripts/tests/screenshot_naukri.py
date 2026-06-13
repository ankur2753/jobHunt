import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(storage_state="/home/ankurkumar/ankur_code/agent/personal_details/naukri_cookies.json")
    page = await context.new_page()
    await page.goto("https://www.naukri.com")
    await page.wait_for_timeout(5000)
    await page.screenshot(path="naukri_screenshot.png")
    html = await page.content()
    with open("naukri_home.html", "w") as f:
        f.write(html)
    await browser.close()
    p.stop()

if __name__ == "__main__":
    asyncio.run(main())
