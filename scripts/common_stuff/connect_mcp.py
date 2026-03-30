import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from playwright.async_api import async_playwright

async def run_mcp_automation():
    # Define how to launch the Playwright MCP server
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-playwright"],
        env={**os.environ, "DISPLAY": ":99"} # Useful for headful in Docker
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()

            # Now you can call Playwright tools via MCP
            # Example: Navigate to LinkedIn
            result = await session.call_tool(
                "playwright_navigate", 
                arguments={"url": "https://www.linkedin.com"}
            )
            print(f"MCP Response: {result}")

async def run_connect_docker_mcp():
    async with async_playwright() as p:
        # Connect to the Docker container's WebSocket
        browser = await p.chromium.connect("ws://127.0.0.1:3000/")
        
        # Now you can use it exactly like a local browser
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.linkedin.com")
        
        print(f"Connected to remote browser. Title: {await page.title()}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_connect_docker_mcp())