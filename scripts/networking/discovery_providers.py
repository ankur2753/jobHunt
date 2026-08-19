"""
Discovery Providers module for candidate sourcing.

Defines the BaseDiscoveryProvider interface and modular discovery provider implementations:
- BaseDiscoveryProvider (Abstract Base Class interface)
- LinkedInSearchDiscoveryProvider (Playwright browser automation)
- LinkedInAPIDiscoveryProvider (linkedin-api Python package)
"""

import json
import logging
import os
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import quote

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import Page
except ImportError:
    Page = Any

try:
    from linkedin_api import Linkedin
except ImportError:
    Linkedin = None


class BaseDiscoveryProvider(ABC):
    """
    Abstract Base Class defining the interface for candidate discovery.
    """

    @abstractmethod
    async def discover_candidates(self, company_name: str, job_title_keyword: str) -> list:
        """
        Discover potential referral candidates for a given company name and job keyword.

        :param company_name: Name of target firm.
        :param job_title_keyword: Extracted role keyword for peers.
        :return: List of candidate dictionaries: [{"name": ..., "headline": ..., "profile_url": ...}]
        """
        pass


class LinkedInSearchDiscoveryProvider(BaseDiscoveryProvider):
    """
    LinkedIn search implementation of candidate discovery using Playwright browser automation.
    """

    def __init__(self, page: Optional[Page] = None) -> None:
        self.page = page

    async def _human_pause(self, min_ms: int = 700, max_ms: int = 1600):
        if self.page:
            await self.page.wait_for_timeout(random.randint(min_ms, max_ms))

    async def search_people(self, query: str, max_results: int = 5) -> list:
        """
        Navigates to LinkedIn people search and parses candidate name, profile URL, and headline.
        Resilient to selector changes and rate limit / checkpoint checks.
        """
        if not self.page:
            logger.warning("Playwright Page not initialized.")
            return []
            
        query_encoded = quote(query)
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={query_encoded}"
        logger.info(f"Searching LinkedIn people: {search_url}")
        
        await self.page.goto(search_url, wait_until="domcontentloaded")
        await self._human_pause(2500, 4000)
        
        # Check for security verification checkpoint
        body_html = await self.page.content()
        if "checkpoint" in self.page.url or "challenge" in self.page.url or "captcha" in body_html.lower() or "security check" in body_html.lower():
            print("\n⚠️  SECURITY CHECKPOINT / CAPTCHA DETECTED on LinkedIn!")
            print("Please solve the verification challenge in the browser window.")
            # Pause and wait for manual resolution
            for i in range(12):
                await self._human_pause(5000, 5000)
                body_html = await self.page.content()
                if "checkpoint" not in self.page.url and "challenge" not in self.page.url:
                    print("✅ Verification resolved. Continuing search...")
                    break
        
        try:
            await self.page.wait_for_selector('a[href*="/in/"]', timeout=15000)
        except Exception as e:
            logger.warning(f"Timeout waiting for search results selectors for query '{query}': {e}")
            
        # Scroll to lazy-load elements
        for _ in range(3):
            await self.page.evaluate("window.scrollBy(0, 350)")
            await self._human_pause(300, 600)
            
        candidates = []
        all_links = await self.page.locator('a[href*="/in/"]').all()
        seen_urls = set()
        for link in all_links:
            try:
                href = await link.get_attribute("href")
                if not href:
                    continue
                if "?" in href:
                    href = href.split("?")[0]
                if href in seen_urls or "/in/ACoAA" in href or "linkedin.com/in/search" in href:
                    continue
                
                text = await link.text_content()
                if not text:
                    continue
                text = text.strip()
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                name = lines[0] if lines else ""
                
                for term in ["•", "1st", "2nd", "3rd", "degree"]:
                    if term in name:
                        name = name.split(term)[0].strip()
                        
                if not name or name.lower() in ["linkedin member", "view profile", "connect", "message"]:
                    continue
                    
                seen_urls.add(href)
                
                # Get headline from the ancestor LI or parent container
                headline = "LinkedIn Member"
                try:
                    li_locator = link.locator('xpath=./ancestor::li').first
                    if await li_locator.count() > 0:
                        card_text = await li_locator.text_content()
                    else:
                        # Fallback to a div that might contain the card
                        div_locator = link.locator('xpath=./ancestor::div[contains(@class, "search-result") or contains(@class, "entity")]').first
                        if await div_locator.count() > 0:
                            card_text = await div_locator.text_content()
                        else:
                            card_text = ""
                            
                    if card_text:
                        card_lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                        headline = " | ".join(card_lines[:6])
                except Exception:
                    pass
                    
                candidates.append({
                    "name": name,
                    "headline": headline,
                    "profile_url": href
                })
                
                if len(candidates) >= max_results:
                    break
            except Exception as e:
                logger.debug(f"Parsing failed for link: {e}")
                
        return candidates

    async def discover_candidates(self, company_name: str, job_title_keyword: str) -> list:
        """
        Dual-Query Search implementation mapping recruiters and peers using browser automation.
        """
        # Query 1: Recruiters
        recruiter_query = f"{company_name} recruiter"
        recruiter_candidates = await self.search_people(recruiter_query)
        
        # Query 2: Peers
        peer_query = f"{company_name} {job_title_keyword}"
        peer_candidates = await self.search_people(peer_query)
        
        # Merge & deduplicate by profile URL
        seen_urls = set()
        unique_candidates = []
        for c in recruiter_candidates + peer_candidates:
            url = c["profile_url"]
            if url not in seen_urls:
                seen_urls.add(url)
                unique_candidates.append(c)
                
        return unique_candidates


class LinkedInAPIDiscoveryProvider(BaseDiscoveryProvider):
    """
    LinkedIn API candidate discovery provider using the 'linkedin-api' package.
    Interacts with LinkedIn Voyager API to discover recruiters and peer candidates.
    """

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        cookies: Optional[Union[Dict[str, str], List[Dict[str, Any]]]] = None,
        cookies_file: Optional[Union[str, Path]] = None,
        client: Optional[Any] = None,
        **kwargs
    ) -> None:
        """
        Initialize the LinkedIn API discovery provider.

        :param username: LinkedIn username/email (defaults to LINKEDIN_USERNAME or LINKEDIN_EMAIL env var).
        :param password: LinkedIn password (defaults to LINKEDIN_PASSWORD env var).
        :param cookies: Optional dictionary or list of cookies for session authentication.
        :param cookies_file: Optional path to cookies JSON file (defaults to LINKEDIN_COOKIES_PATH env var).
        :param client: Optional pre-configured Linkedin client instance.
        """
        self.username = username or os.getenv("LINKEDIN_USERNAME") or os.getenv("LINKEDIN_EMAIL")
        self.password = password or os.getenv("LINKEDIN_PASSWORD")
        self.cookies = cookies
        self.cookies_file = cookies_file or os.getenv("LINKEDIN_COOKIES_PATH")
        self.client = client
        self.kwargs = kwargs

        if self.client is None:
            self.client = self._init_client()

    def _load_cookies_dict(self) -> Optional[Dict[str, str]]:
        """Load and normalize cookies into a {name: value} dictionary."""
        if self.cookies:
            if isinstance(self.cookies, dict):
                return self.cookies
            elif isinstance(self.cookies, list):
                return {c["name"]: c["value"] for c in self.cookies if isinstance(c, dict) and "name" in c and "value" in c}

        # Check explicit cookies_file or default paths
        candidate_paths = []
        if self.cookies_file:
            candidate_paths.append(Path(self.cookies_file))
        candidate_paths.extend([
            Path(__file__).resolve().parents[2] / "personal_details" / "linkedin_cookies.json",
            Path("personal_details/linkedin_cookies.json"),
        ])

        for p in candidate_paths:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                        if isinstance(raw, dict):
                            return raw
                        elif isinstance(raw, list):
                            return {c["name"]: c["value"] for c in raw if isinstance(c, dict) and "name" in c and "value" in c}
                except Exception as e:
                    logger.warning(f"Failed to read cookies from {p}: {e}")

        return None

    def _init_client(self) -> Optional[Any]:
        """
        Initialize an instance of the Linkedin client from the linkedin_api package.
        """
        if Linkedin is None:
            logger.warning(
                "The 'linkedin_api' package is not installed. "
                "LinkedInAPIDiscoveryProvider requires 'linkedin-api'."
            )
            return None

        cookies_dict = self._load_cookies_dict()

        try:
            # If username and password are provided, initialize with credentials
            if self.username and self.password:
                logger.info(f"Initializing Linkedin client for user: {self.username}")
                client = Linkedin(self.username, self.password, **self.kwargs)
                if cookies_dict and hasattr(client, "session") and hasattr(client.session, "cookies"):
                    client.session.cookies.update(cookies_dict)
                return client

            # If cookies are provided, attempt initialization using session cookies
            if cookies_dict:
                logger.info("Initializing Linkedin client with session cookies.")
                try:
                    client = Linkedin(username="", password="", authenticate=False, **self.kwargs)
                except TypeError:
                    try:
                        client = Linkedin(self.username or "", self.password or "", **self.kwargs)
                    except Exception:
                        client = Linkedin.__new__(Linkedin)
                
                if hasattr(client, "session") and hasattr(client.session, "cookies"):
                    client.session.cookies.update(cookies_dict)
                return client

            logger.warning(
                "No LinkedIn credentials or cookies found. "
                "Set LINKEDIN_USERNAME/LINKEDIN_PASSWORD or provide cookies."
            )
            return None
        except Exception as e:
            logger.error(f"Failed to instantiate LinkedIn client: {e}")
            return None

    def _parse_candidate(self, item: Any) -> Optional[Dict[str, str]]:
        """
        Parse raw result from linkedin_api into normalized candidate dictionary:
        {"name": ..., "headline": ..., "profile_url": ...}
        """
        if not isinstance(item, dict):
            return None

        # Extract name
        name = item.get("name")
        if not name:
            first_name = item.get("firstName") or item.get("first_name") or ""
            last_name = item.get("lastName") or item.get("last_name") or ""
            name = f"{first_name} {last_name}".strip()
        if not name:
            name = item.get("title") or item.get("actorName") or "LinkedIn Member"

        # Clean name suffixes / connection degree markers
        for term in ["•", "1st", "2nd", "3rd", "degree"]:
            if term in name:
                name = name.split(term)[0].strip()

        if not name:
            name = "LinkedIn Member"

        # Extract headline
        headline = (
            item.get("headline")
            or item.get("subline")
            or item.get("snippet")
            or item.get("occupation")
            or item.get("summary")
            or ""
        ).strip()
        if not headline:
            headline = "LinkedIn Member"

        # Extract profile URL
        profile_url = (
            item.get("profile_url")
            or item.get("public_url")
            or item.get("url")
            or item.get("navigationUrl")
        )

        if not profile_url:
            public_id = (
                item.get("public_id")
                or item.get("publicIdentifier")
                or item.get("urn_id")
                or item.get("id")
            )
            if public_id:
                profile_url = f"https://www.linkedin.com/in/{public_id}"
            elif "entityUrn" in item:
                urn = str(item["entityUrn"])
                urn_id = urn.split(":")[-1] if ":" in urn else urn
                profile_url = f"https://www.linkedin.com/in/{urn_id}"

        if profile_url and "?" in profile_url:
            profile_url = profile_url.split("?")[0]

        if not profile_url:
            return None

        return {
            "name": name,
            "headline": headline,
            "profile_url": profile_url
        }

    def _search_people_api(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        Execute people search query against Linkedin client and return parsed candidates.
        """
        if not self.client:
            logger.warning("LinkedIn client is not initialized; cannot execute search.")
            return []

        results = []
        try:
            if hasattr(self.client, "search_people"):
                try:
                    results = self.client.search_people(keywords=query, limit=limit)
                except TypeError:
                    results = self.client.search_people(keyword=query, limit=limit)
            elif hasattr(self.client, "search_profiles"):
                try:
                    results = self.client.search_profiles(keyword=query, limit=limit)
                except TypeError:
                    results = self.client.search_profiles(keywords=query, limit=limit)
            elif hasattr(self.client, "search"):
                results = self.client.search(keywords=query, limit=limit)
            else:
                logger.error("LinkedIn client has no supported search method (search_people / search_profiles / search).")
                return []
        except Exception as e:
            logger.error(f"LinkedIn API search error for query '{query}': {e}")
            return []

        candidates: List[Dict[str, str]] = []
        for item in results or []:
            cand = self._parse_candidate(item)
            if cand:
                candidates.append(cand)
                if len(candidates) >= limit:
                    break

        return candidates

    async def discover_candidates(self, company_name: str, job_title_keyword: str) -> List[Dict[str, str]]:
        """
        Discover potential referral candidates (recruiters and peers) using the LinkedIn API.

        :param company_name: Name of target firm.
        :param job_title_keyword: Extracted role keyword for peers.
        :return: List of candidate dictionaries: [{"name": ..., "headline": ..., "profile_url": ...}]
        """
        if not company_name:
            return []

        logger.info(f"Discovering candidates via LinkedIn API for company='{company_name}', keyword='{job_title_keyword}'")

        # Query 1: Recruiters
        recruiter_query = f"{company_name} recruiter"
        try:
            recruiter_candidates = self._search_people_api(recruiter_query, limit=5)
        except Exception as e:
            logger.error(f"Error discovering recruiters for '{company_name}': {e}")
            recruiter_candidates = []

        # Query 2: Peers
        peer_query = f"{company_name} {job_title_keyword}" if job_title_keyword else company_name
        try:
            peer_candidates = self._search_people_api(peer_query, limit=5)
        except Exception as e:
            logger.error(f"Error discovering peers for '{company_name}' '{job_title_keyword}': {e}")
            peer_candidates = []

        # Merge & deduplicate by profile URL
        seen_urls = set()
        unique_candidates: List[Dict[str, str]] = []
        for c in recruiter_candidates + peer_candidates:
            url = c.get("profile_url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_candidates.append(c)

        logger.info(f"Discovered {len(unique_candidates)} unique candidates via LinkedIn API for '{company_name}'")
        return unique_candidates
