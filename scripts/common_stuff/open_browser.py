import asyncio
from playwright.async_api import async_playwright

async def run_login():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate and Login
        await page.goto("https://example.com/login")
        await page.fill('input[name="username"]', "your_user")
        await page.fill('input[name="password"]', "your_password")
        await page.click('button[type="submit"]')
        
        # Wait for navigation to ensure login is processed
        await page.wait_for_url("**/dashboard")

        # Save the authentication state (cookies, localStorage, etc.)
        await context.storage_state(path="auth_state.json")
        print("Login successful. Session saved to auth_state.json")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_login())