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
    # Ensure lock is handled
    if not get_lock():
        raise Exception("Another process is currently holding the lock for the browser session.")
        
    if _naukri_session is None:
        _naukri_session = NaukriPlaywright()
        await _naukri_session.setup_driver(headless=False)
        if not await _naukri_session.is_logged_in():
            raise Exception("Not logged into Naukri. Please run orchestrator manually to login and save session.")
    return _naukri_session

async def get_linkedin_session() -> LinkedInPlaywright:
    """Helper to get or initialize the LinkedInPlaywright session."""
    global _linkedin_session
    # Ensure lock is handled
    if not get_lock():
        raise Exception("Another process is currently holding the lock for the browser session.")
        
    if _linkedin_session is None:
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
    # Ensure port_info.json is populated by trying to get a session if none exists
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

if __name__ == "__main__":
    # Start the MCP server using stdio transport
    mcp.run(transport="stdio")
