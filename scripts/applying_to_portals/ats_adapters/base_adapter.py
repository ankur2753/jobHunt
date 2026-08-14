"""
Base ATS Adapter Interface
Defines the standard contract for all portal-specific ATS adapters (Workday, Greenhouse, Lever, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from playwright.async_api import Page


class BaseATSAdapter(ABC):
    """Abstract interface for all ATS portal adapters."""

    def __init__(self, page: Page):
        self.page = page

    @classmethod
    @abstractmethod
    def adapter_name(cls) -> str:
        """Return human-readable name of the ATS adapter."""
        pass

    @classmethod
    @abstractmethod
    def can_handle(cls, url: str, html_snippet: str = "") -> bool:
        """
        Check if this adapter can handle the target URL or page content.
        
        Args:
            url: Target job URL
            html_snippet: Optional HTML content snippet of the page
        """
        pass

    @abstractmethod
    async def apply(
        self,
        resume_path: str,
        user_profile: Dict[str, Any],
        review_mode: bool = True,
        cover_letter_path: Optional[str] = None
    ) -> bool:
        """
        Execute the multi-step application workflow for this ATS.
        
        Args:
            resume_path: Absolute path to user's resume file
            user_profile: User profile details dictionary
            review_mode: If True, pause before final submission for human review
            cover_letter_path: Optional absolute path to user's cover letter file
            
        Returns:
            bool: True if application completed/paused for review, False if failed
        """
        pass

    async def _human_pause(self, min_ms: int = 400, max_ms: int = 1200):
        """Pause for a randomized human-like delay."""
        import random
        await self.page.wait_for_timeout(random.randint(min_ms, max_ms))

    async def _move_human_mouse(self):
        """Emulate realistic human mouse movement across the viewport."""
        import random
        try:
            bounds = await self.page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
            x = random.randint(0, max(0, bounds['w'] - 1))
            y = random.randint(0, max(0, bounds['h'] - 1))
            await self.page.mouse.move(x, y, steps=random.randint(4, 12))
        except Exception:
            pass

    async def _human_scroll_into_view(self, field_locator):
        """Scroll element into view with human pause."""
        try:
            await field_locator.scroll_into_view_if_needed()
            await self._human_pause(400, 1000)
        except Exception:
            pass

    async def _human_type(self, field_locator, text: str):
        """Type text character-by-character with realistic keypress delays."""
        import random
        await self._human_scroll_into_view(field_locator)
        await self._move_human_mouse()
        await field_locator.click()
        await self._human_pause(200, 500)
        for char in text:
            await field_locator.type(char, delay=random.randint(30, 90))
        await self._human_pause(300, 800)

    async def dismiss_popups(self) -> int:
        """
        Detect and dismiss cookie consent banners, chatbot widgets, and popups
        obscuring form fields before human/bot interaction.
        """
        from scripts.common_stuff.retry_utils import dismiss_overlays_and_popups
        return await dismiss_overlays_and_popups(self.page)


