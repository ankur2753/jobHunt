import json
import random
from urllib.parse import urlparse

from playwright.async_api import Page
from scripts.common_stuff.vector_db_manager import VectorDBManager


class LinkedInConnector:
    def __init__(self, page: Page, db_manager: VectorDBManager = None):
        self.page = page
        self.db_manager = db_manager or VectorDBManager()

    async def _human_pause(self, min_ms: int = 700, max_ms: int = 1600):
        await self.page.wait_for_timeout(random.randint(min_ms, max_ms))

    async def _human_type(self, locator, text: str):
        await locator.click()
        for char in text:
            await locator.type(char, delay=random.randint(30, 80))
        await self._human_pause(300, 800)

    async def _move_human_mouse(self):
        bounds = await self.page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
        x = random.randint(0, max(0, bounds['w'] - 1))
        y = random.randint(0, max(0, bounds['h'] - 1))
        await self.page.mouse.move(x, y, steps=random.randint(4, 12))

    def _clean_profile_url(self, profile_url: str) -> str:
        if not profile_url.startswith('http'):
            profile_url = f'https://www.linkedin.com{profile_url}'
        parsed = urlparse(profile_url)
        return parsed.geturl()

    def _build_connection_message(self, connection_reason: str = None) -> str:
        query = connection_reason or 'summary'
        results = self.db_manager.query_personal_profile(query, n_results=5)
        snippets = []
        for doc, meta in zip(results.get('documents', []), results.get('metadatas', [])):
            if meta.get('normalized_key') in ('summary', 'skills', 'experience', 'education', 'salary', 'location'):
                snippets.append(doc)
        snippets = snippets[:3]

        if snippets:
            details = ' '.join(snippets)
        else:
            details = 'Experienced QA automation engineer with full-stack workflow and cloud-ready skills.'

        prefix = 'I came across your profile and would love to connect.'
        if connection_reason:
            prefix = f'I came across your profile and would love to connect to discuss {connection_reason}.'

        return (
            f"Hi, I’m Ankur. {prefix} "
            f"I work in QA automation, building resilient web workflows and automation tooling. "
            f"Here is a bit about my background: {details}"
        )

    async def send_connection_invite(self, profile_url: str, connection_reason: str = None) -> str:
        profile_url = self._clean_profile_url(profile_url)
        await self.page.goto(profile_url, wait_until='load')
        await self._human_pause(1200, 2200)
        await self._move_human_mouse()

        connect_button = self.page.locator('button:has-text("Connect"), button[aria-label*="Connect"]')
        if not await connect_button.is_visible():
            return f'Unable to find a Connect button on {profile_url}.'

        await connect_button.click()
        await self._human_pause(900, 1600)

        add_note = self.page.locator('button:has-text("Add a note"), button:has-text("Add note")')
        if await add_note.is_visible():
            await add_note.click()
            await self._human_pause(700, 1200)

        note_area = self.page.locator('textarea[aria-label*="Add a note"], textarea[name="message"]')
        message = self._build_connection_message(connection_reason)
        if await note_area.is_visible():
            await self._human_type(note_area, message)
        else:
            return 'Could not locate the note field for LinkedIn connection invite.'

        send_button = self.page.locator('button:has-text("Send"), button:has-text("Send now"), button[aria-label*="Send now"]')
        if await send_button.is_visible():
            await send_button.click()
            await self._human_pause(1000, 1800)
            return f'Sent connection invite to {profile_url} with a personalized message.'

        return 'Connection invite flow opened, but the Send button was not visible.'
