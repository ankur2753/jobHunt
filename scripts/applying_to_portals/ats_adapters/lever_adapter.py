"""
Lever ATS Adapter
Specialized adapter for Lever job postings (jobs.lever.co).
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
class LeverAdapter(BaseATSAdapter):
    """Adapter for Lever application forms."""

    LEVER_SELECTORS = {
        'apply_btn': 'a.postings-btn, a:has-text("Apply for this job")',
        'resume_file': 'input[type="file"][name="resume"]',
        'full_name': 'input[name="name"]',
        'email': 'input[name="email"]',
        'phone': 'input[name="phone"]',
        'company': 'input[name="org"]',
        'linkedin_url': 'input[name*="urls[LinkedIn]"]',
        'github_url': 'input[name*="urls[GitHub]"]',
        'submit_btn': 'button[id="btn-submit"], button:has-text("Submit application")',
    }

    def __init__(self, page: Page):
        super().__init__(page)
        self.vector_db = VectorDBManager()

    @classmethod
    def adapter_name(cls) -> str:
        return "Lever"

    @classmethod
    def can_handle(cls, url: str, html_snippet: str = "") -> bool:
        return (
            "jobs.lever.co" in url
            or "lever.co" in url
            or 'id="btn-submit"' in html_snippet
            or 'lever-form' in html_snippet
        )

    async def apply(
        self,
        resume_path: str,
        user_profile: Dict[str, Any],
        review_mode: bool = True,
        **kwargs: Any
    ) -> bool:
        logger.info("📐 Starting Lever Application Pipeline...")

        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass

        await self.dismiss_popups()

        # Step 1: Click Apply for this job if on job description page
        try:
            apply_btn = self.page.locator(self.LEVER_SELECTORS['apply_btn']).first
            if await apply_btn.count() > 0 and await apply_btn.is_visible():
                await apply_btn.click()
                await self.page.wait_for_timeout(2000)
        except Exception:
            pass

        # Step 2: Upload Resume
        if resume_path and Path(resume_path).exists():
            try:
                resume_input = self.page.locator(self.LEVER_SELECTORS['resume_file']).first
                if await resume_input.count() > 0:
                    logger.info(f"📄 Uploading resume to Lever: {resume_path}")
                    await resume_input.set_input_files(resume_path)
                    await self.page.wait_for_timeout(2000)
            except Exception as e:
                logger.debug(f"Lever resume upload note: {e}")

        # Step 3: Auto-fill fields using ChatbotFormFiller
        form_filler = ChatbotFormFiller(self.page, self.vector_db)
        stats = await form_filler.auto_fill_chatbot_form()
        logger.info(f"📊 Lever Form Filler Stats: {stats.to_dict()}")

        # Step 4: Check Submit / Review Mode
        submit_btn = self.page.locator(self.LEVER_SELECTORS['submit_btn']).first
        if review_mode:
            logger.info("⏸️  Lever Application filled! Paused at Submit screen (Review Mode active).")
            return True
        else:
            if await submit_btn.count() > 0 and await submit_btn.is_visible():
                logger.info("🚀 Submitting Lever Application...")
                await submit_btn.click()
                await self.verify_submission()
                logger.info("✅ Lever Application submitted successfully.")
                return True

        return True
