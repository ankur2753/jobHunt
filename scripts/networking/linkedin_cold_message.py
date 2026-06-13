import random
from typing import List, Optional
from playwright.async_api import Page
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.networking.linkedin_connect import LinkedInConnector


class LinkedInColdMessenger:
    def __init__(self, page: Page, db_manager: VectorDBManager = None):
        self.page = page
        self.db_manager = db_manager or VectorDBManager()
        self.connector = LinkedInConnector(page, self.db_manager)

    async def _human_pause(self, min_ms: int = 700, max_ms: int = 1600):
        await self.page.wait_for_timeout(random.randint(min_ms, max_ms))

    async def _human_type(self, locator, text: str):
        await locator.click()
        for char in text:
            await locator.type(char, delay=random.randint(30, 80))
        await self._human_pause(300, 800)

    def _build_cold_message(self, connection_reason: Optional[str] = None) -> str:
        query = connection_reason or "summary"
        results = self.db_manager.query_personal_profile(query, n_results=6)
        snippets = []
        for doc, meta in zip(results.get('documents', []), results.get('metadatas', [])):
            if meta.get('normalized_key') in ('summary', 'skills', 'experience', 'education', 'salary', 'location'):
                snippets.append(doc)
        intro = ' '.join(snippets[:3]).strip()
        if not intro:
            intro = 'I build resilient automation tooling and workflows for modern SaaS teams.'

        if connection_reason:
            return (
                f"Hi, I’m Ankur. I noticed we have shared interests in {connection_reason}. "
                f"I work in QA automation and workflow orchestration. {intro} "
                f"Would love to connect and explore how we can collaborate."
            )

        return (
            f"Hi, I’m Ankur. I build resilient automation tooling for QA and software delivery teams. "
            f"{intro} "
            f"I’d love to connect and learn about your experience."
        )

    async def _send_direct_message(self, message: str) -> str:
        message_button = self.page.locator('button:has-text("Message"), button[aria-label*="Message"]')
        if await message_button.is_visible():
            await message_button.click()
            await self._human_pause(800, 1500)
            text_area = self.page.locator('div[role="textbox"]')
            if await text_area.is_visible():
                await self._human_type(text_area, message)
                send_button = self.page.locator('button:has-text("Send"), button[aria-label*="Send"]')
                if await send_button.is_visible():
                    await send_button.click()
                    await self._human_pause(900, 1400)
                    return 'Sent direct LinkedIn message.'
                return 'Opened message box but could not find the Send button.'
            return 'Message composer was not visible.'
        return 'Direct message button not available.'

    async def send_cold_message(self, profile_url: str, connection_reason: Optional[str] = None, message: Optional[str] = None) -> str:
        message = message or self._build_cold_message(connection_reason)
        await self.page.goto(profile_url, wait_until='load')
        await self._human_pause(1200, 2100)
        await self.connector._move_human_mouse()

        # Prefer direct message if already connected.
        msg_result = await self._send_direct_message(message)
        if 'Sent direct LinkedIn message' in msg_result:
            return f'{profile_url}: {msg_result}'

        # Fall back to connection invite with a personalized note.
        return f'{profile_url}: {await self.connector.send_connection_invite(profile_url, connection_reason)}'

    async def send_bulk_outreach(self, profile_urls: List[str], connection_reason: Optional[str] = None) -> List[str]:
        results = []
        for profile_url in profile_urls:
            profile_url = profile_url.strip()
            if not profile_url:
                continue
            try:
                results.append(await self.send_cold_message(profile_url, connection_reason))
            except Exception as exc:
                results.append(f'{profile_url}: failed with error {exc}')
        return results
