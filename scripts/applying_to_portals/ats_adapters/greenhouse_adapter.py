"""
Greenhouse ATS Adapter
Specialized adapter for Greenhouse job boards (boards.greenhouse.io, *.greenhouse.io).
"""

import logging
from typing import Dict, Any
from pathlib import Path
from playwright.async_api import Page

from .base_adapter import BaseATSAdapter
from .registry import ATSAdapterRegistry
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.chatbot_form_filler import ChatbotFormFiller

logger = logging.getLogger(__name__)


@ATSAdapterRegistry.register
class GreenhouseAdapter(BaseATSAdapter):
    """Adapter for Greenhouse application forms."""

    GREENHOUSE_SELECTORS = {
        'first_name': 'input[id="first_name"], input[name*="first_name"]',
        'last_name': 'input[id="last_name"], input[name*="last_name"]',
        'email': 'input[id="email"], input[name*="email"]',
        'phone': 'input[id="phone"], input[name*="phone"]',
        'resume_file': 'input[type="file"][id*="resume"], input[type="file"][name*="resume"]',
        'submit_btn': 'input[type="submit"][id="submit_app"], button[id="submit_app"], button:has-text("Submit Application")',
    }

    def __init__(self, page: Page):
        super().__init__(page)
        self.vector_db = VectorDBManager()

    @classmethod
    def adapter_name(cls) -> str:
        return "Greenhouse"

    @classmethod
    def can_handle(cls, url: str, html_snippet: str = "") -> bool:
        return (
            "greenhouse.io" in url
            or "boards.greenhouse.io" in url
            or 'id="submit_app"' in html_snippet
            or 'grnhse' in html_snippet
        )

    async def apply(
        self,
        resume_path: str,
        user_profile: Dict[str, Any],
        review_mode: bool = True,
        **kwargs: Any
    ) -> bool:
        logger.info("🌿 Starting Greenhouse Application Pipeline...")

        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass

        await self.dismiss_popups()

        # Step 1: Upload Resume
        if resume_path and Path(resume_path).exists():
            try:
                resume_input = self.page.locator(self.GREENHOUSE_SELECTORS['resume_file']).first
                if await resume_input.count() > 0:
                    logger.info(f"📄 Uploading resume to Greenhouse: {resume_path}")
                    await resume_input.set_input_files(resume_path)
                    await self.page.wait_for_timeout(2000)
            except Exception as e:
                logger.debug(f"Greenhouse resume upload note: {e}")

        # Step 2: Auto-fill fields using ChatbotFormFiller
        form_filler = ChatbotFormFiller(self.page, self.vector_db)
        stats = await form_filler.auto_fill_chatbot_form()
        logger.info(f"📊 Greenhouse Form Filler Stats: {stats.to_dict()}")

        # Step 3: Check Submit / Review Mode
        submit_btn = self.page.locator(self.GREENHOUSE_SELECTORS['submit_btn']).first
        if review_mode:
            logger.info("⏸️  Greenhouse Application filled! Paused at Submit screen (Review Mode active).")
            return True
        else:
            if await submit_btn.count() > 0 and await submit_btn.is_visible():
                logger.info("🚀 Submitting Greenhouse Application...")
                await submit_btn.click()
                await self.verify_submission()
                logger.info("✅ Greenhouse Application submitted successfully.")
                return True

        return True
