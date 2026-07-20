import asyncio
import os
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Add project root to path to import other modules
sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.orchestrator.orchestrator import LinkedInPlaywright
from scripts.job_scraping.linkedin_job_apply import LinkedInJobApply
from scripts.job_scraping.linkedin_job_scraper import LinkedInJobScraper
from scripts.cookie_management_login.naukri_login import NaukriPlaywright
from scripts.networking.linkedin_connect import LinkedInConnector
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.orchestrator.orchestrator import PORT_INFO_FILE, get_lock
import json

# Initialize FastMCP server
mcp = FastMCP("LinkedIn Agent")

# Global state to maintain the browser session
_linkedin_session = None
_naukri_session = None

async def get_naukri_session() -> NaukriPlaywright:
    """Helper to get or initialize the NaukriPlaywright session."""
    global _naukri_session
    
    if _naukri_session is None:
        # Check if we can connect to an existing running browser first
        session = NaukriPlaywright()
        connected = False
        if PORT_INFO_FILE.exists():
            try:
                with open(PORT_INFO_FILE, 'r') as f:
                    data = json.load(f)
                    ws = data.get("ws_endpoint")
                if ws:
                    await session.setup_driver(headless=False)
                    # Test if the connection works and we are logged in
                    if await session.is_logged_in():
                        _naukri_session = session
                        connected = True
            except Exception:
                pass
                
        if not connected:
            # We must acquire the lock to launch a new browser
            if not get_lock():
                raise Exception("Another process is currently holding the lock for the browser session.")
            _naukri_session = NaukriPlaywright()
            await _naukri_session.setup_driver(headless=False)
            if not await _naukri_session.is_logged_in():
                raise Exception("Not logged into Naukri. Please run orchestrator manually to login and save session.")
                
    return _naukri_session

async def get_linkedin_session() -> LinkedInPlaywright:
    """Helper to get or initialize the LinkedInPlaywright session."""
    global _linkedin_session
    
    if _linkedin_session is None:
        # Check if we can connect to an existing running browser first
        session = LinkedInPlaywright()
        connected = False
        if PORT_INFO_FILE.exists():
            try:
                with open(PORT_INFO_FILE, 'r') as f:
                    data = json.load(f)
                    ws = data.get("ws_endpoint")
                if ws:
                    await session.setup_driver(headless=False)
                    if await session.is_logged_in():
                        _linkedin_session = session
                        connected = True
            except Exception:
                pass
                
        if not connected:
            # We must acquire the lock to launch a new browser
            if not get_lock():
                raise Exception("Another process is currently holding the lock for the browser session.")
            _linkedin_session = LinkedInPlaywright()
            await _linkedin_session.setup_driver(headless=False)
            if not await _linkedin_session.is_logged_in():
                raise Exception("Not logged into LinkedIn. Please run orchestrator manually to login and save session.")
                
    return _linkedin_session

@mcp.tool()
async def get_browser_control_details() -> str:
    """
    Returns the WebSocket connection URL (ws_endpoint) and session details of the open browser.
    This allows an LLM or an external tool (like the default Playwright MCP tools) to take full control 
    of the active browser session by connecting to it via Playwright (e.g. p.chromium.connect_over_cdp(ws_endpoint)).
    """
    # 1. First, check if port_info.json already exists and has a valid ws_endpoint
    if PORT_INFO_FILE.exists():
        with open(PORT_INFO_FILE, 'r') as f:
            try:
                data = json.load(f)
                if data.get("ws_endpoint"):
                    return json.dumps({
                        "message": "You can connect to this active browser using the details below.",
                        "ws_endpoint": data.get("ws_endpoint"),
                        "cookies_file": data.get("cookies_file"),
                        "lock_time": data.get("lock_time")
                    }, indent=2)
            except json.JSONDecodeError:
                pass
                
    # 2. If no browser is currently active, try to start a new LinkedIn session
    if not _linkedin_session and not _naukri_session:
        try:
            await get_linkedin_session()
        except Exception as e:
            return f"Could not start or connect to the browser: {str(e)}"
        
    if PORT_INFO_FILE.exists():
        with open(PORT_INFO_FILE, 'r') as f:
            try:
                data = json.load(f)
                return json.dumps({
                    "message": "You can connect to this active browser using the details below.",
                    "ws_endpoint": data.get("ws_endpoint"),
                    "cookies_file": data.get("cookies_file"),
                    "lock_time": data.get("lock_time")
                }, indent=2)
            except json.JSONDecodeError:
                return "Error: Could not read session details from port_info.json"
    
    return "Error: Browser is running but session details are not available."

@mcp.tool()
async def check_naukri_login() -> str:
    """Check if the agent is currently logged into Naukri and initialize the session."""
    try:
        naukri = await get_naukri_session()
        is_logged = await naukri.is_logged_in()
        if is_logged:
            return "Successfully logged into Naukri."
        else:
            return "Not logged into Naukri."
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def check_linkedin_login() -> str:
    """Check if the agent is currently logged into LinkedIn and initialize the session."""
    try:
        linkedin = await get_linkedin_session()
        is_logged = await linkedin.is_logged_in()
        if is_logged:
            return "Successfully logged into LinkedIn."
        else:
            return "Not logged into LinkedIn."
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def apply_to_linkedin_jobs(job_title: str, location: str) -> str:
    """
    Search and apply to jobs on LinkedIn using Easy Apply.
    
    Args:
        job_title: The title of the job to search for (e.g., 'Software Engineer').
        location: The location to search in (e.g., 'Remote', 'San Francisco').
    """
    try:
        linkedin = await get_linkedin_session()
        applicator = LinkedInJobApply(linkedin.page)
        await applicator.apply_to_jobs(job_title, location)
        return f"Completed job application process for '{job_title}' in '{location}'."
    except Exception as e:
        return f"Error during job application process: {str(e)}"

@mcp.tool()
async def scrape_linkedin_jobs(job_title: str, location: str) -> str:
    """
    Scrape recent LinkedIn job postings (past 24 hours) and save their links to a CSV file.
    
    Args:
        job_title: The title of the job to search for.
        location: The location to search in.
    """
    try:
        linkedin = await get_linkedin_session()
        scraper = LinkedInJobScraper(linkedin.page, job_title, location)
        await scraper.scrape_jobs()
        return f"Completed job scraping process for '{job_title}' in '{location}'. Check the 'logs' directory for the CSV file."
    except Exception as e:
        return f"Error during job scraping process: {str(e)}"

@mcp.tool()
async def query_personal_profile(query: str, n_results: int = 5) -> str:
    """
    Query the personal details vector DB for a given natural language prompt.
    """
    try:
        manager = VectorDBManager()
        result = manager.query_personal_profile(query, n_results=n_results)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error querying personal profile: {str(e)}"

@mcp.tool()
async def send_linkedin_connection_invite(profile_url: str, connection_reason: str = None) -> str:
    """
    Send a personalized LinkedIn connection invitation to the given profile URL.

    Args:
        profile_url: The full LinkedIn profile URL for the person to connect with.
        connection_reason: Optional reason for connection to help generate the message.
    """
    try:
        linkedin = await get_linkedin_session()
        connector = LinkedInConnector(linkedin.page)
        result = await connector.send_connection_invite(profile_url, connection_reason)
        return result
    except Exception as e:
        return f"Error sending LinkedIn connection invite: {str(e)}"

@mcp.tool()
async def browser_navigate(url: str, portal: str = "naukri") -> str:
    """
    Navigate the active browser page to the specified URL.
    
    Args:
        url: The URL to navigate to.
        portal: The portal session to use ('linkedin' or 'naukri').
    """
    try:
        session = await get_linkedin_session() if portal == "linkedin" else await get_naukri_session()
        await session.page.goto(url)
        return f"Successfully navigated to {url}"
    except Exception as e:
        return f"Error navigating to {url}: {str(e)}"

@mcp.tool()
async def browser_click(selector: str, portal: str = "naukri") -> str:
    """
    Click the element matching the specified selector on the active page.
    
    Args:
        selector: The CSS or XPath selector of the element to click.
        portal: The portal session to use ('linkedin' or 'naukri').
    """
    try:
        session = await get_linkedin_session() if portal == "linkedin" else await get_naukri_session()
        await session.page.click(selector)
        return f"Successfully clicked element: {selector}"
    except Exception as e:
        return f"Error clicking element {selector}: {str(e)}"

@mcp.tool()
async def browser_fill(selector: str, value: str, portal: str = "naukri") -> str:
    """
    Fill the input element matching the specified selector with the given value.
    
    Args:
        selector: The CSS or XPath selector of the input element.
        value: The text value to enter.
        portal: The portal session to use ('linkedin' or 'naukri').
    """
    try:
        session = await get_linkedin_session() if portal == "linkedin" else await get_naukri_session()
        await session.page.fill(selector, value)
        return f"Successfully filled element {selector} with value"
    except Exception as e:
        return f"Error filling element {selector}: {str(e)}"

@mcp.tool()
async def browser_get_content(portal: str = "naukri") -> str:
    """
    Get the text content (inner text) of the body of the active page.
    
    Args:
        portal: The portal session to use ('linkedin' or 'naukri').
    """
    try:
        session = await get_linkedin_session() if portal == "linkedin" else await get_naukri_session()
        content = await session.page.inner_text("body")
        return content
    except Exception as e:
        return f"Error getting content: {str(e)}"

@mcp.tool()
async def browser_screenshot(path: str = "logs/browser_screenshot.png", portal: str = "naukri") -> str:
    """
    Take a screenshot of the active page and save it to the specified path.
    
    Args:
        path: The path where the screenshot will be saved.
        portal: The portal session to use ('linkedin' or 'naukri').
    """
    try:
        session = await get_linkedin_session() if portal == "linkedin" else await get_naukri_session()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await session.page.screenshot(path=path)
        return f"Screenshot saved successfully to {path}"
    except Exception as e:
        return f"Error taking screenshot: {str(e)}"

if __name__ == "__main__":
    # Start the MCP server using stdio transport
    mcp.run(transport="stdio")
