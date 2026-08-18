"""
Workday ATS Adapter
Specialized adapter for Workday career portals (*.myworkdayjobs.com, *.workday.com).
Handles dynamic step wizards, data-automation-id attributes, and account/guest flows.
"""

import logging
import asyncio
from typing import Dict, Any
from pathlib import Path
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .base_adapter import BaseATSAdapter
from .registry import ATSAdapterRegistry
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.chatbot_form_filler import ChatbotFormFiller

logger = logging.getLogger(__name__)


@ATSAdapterRegistry.register
class WorkdayAdapter(BaseATSAdapter):
    """Adapter for Workday application portals."""

    WORKDAY_SELECTORS = {
        'apply_btn': 'button[data-automation-id="applyButton"], a[data-automation-id="applyButton"], button:has-text("Apply")',
        'autofill_resume_btn': 'a[data-automation-id="autofillWithResume"], button[data-automation-id="autofillWithResume"]',
        'apply_manually_btn': 'a[data-automation-id="applyManually"], button[data-automation-id="applyManually"]',
        'resume_dropzone': 'input[type="file"][data-automation-id="file-upload-drop-zone"], input[type="file"]',
        'next_btn': 'button[data-automation-id="bottom-navigation-next-button"]',
        'submit_btn': 'button[data-automation-id="page-submission-button"], button[data-automation-id="bottom-navigation-next-button"]:has-text("Submit")',
        'create_account_btn': 'button[data-automation-id="createAccountSubmitButton"], a[data-automation-id="createAccountLink"]',
        'sign_in_btn': 'button[data-automation-id="signInSubmitButton"]',
    }

    def __init__(self, page: Page):
        super().__init__(page)
        self.vector_db = VectorDBManager()

    @classmethod
    def adapter_name(cls) -> str:
        return "Workday"

    @classmethod
    def can_handle(cls, url: str, html_snippet: str = "") -> bool:
        return (
            "myworkdayjobs.com" in url
            or "workday.com" in url
            or 'data-automation-id="workday"' in html_snippet
            or 'data-automation-id="applyButton"' in html_snippet
        )

    async def _click_if_exists(self, selector: str, timeout: int = 5000) -> bool:
        try:
            elem = self.page.locator(selector).first
            if await elem.count() > 0 and await elem.is_visible(timeout=timeout):
                await elem.click()
                await self.page.wait_for_timeout(2000)
                return True
        except Exception:
            pass
        return False

    async def apply(
        self,
        resume_path: str,
        user_profile: Dict[str, Any],
        review_mode: bool = True,
        **kwargs: Any
    ) -> bool:
        logger.info("🏢 Starting Workday Application Pipeline...")

        try:
            await self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        await self.dismiss_popups()

        # Step 1: Click Main Apply Button
        await self._click_if_exists(self.WORKDAY_SELECTORS['apply_btn'], timeout=15000)

        # Step 2: Select Autofill with Resume if available
        if await self._click_if_exists(self.WORKDAY_SELECTORS['autofill_resume_btn']):
            logger.info("📄 Clicked 'Autofill with Resume'")
        elif await self._click_if_exists(self.WORKDAY_SELECTORS['apply_manually_btn']):
            logger.info("📝 Clicked 'Apply Manually'")

        # Step 3: Handle Resume Upload if present on current screen
        if resume_path and Path(resume_path).exists():
            try:
                file_input = self.page.locator(self.WORKDAY_SELECTORS['resume_dropzone']).first
                if await file_input.count() > 0:
                    logger.info(f"Uploading resume to Workday: {resume_path}")
                    await file_input.set_input_files(resume_path)
                    await self.page.wait_for_timeout(3000)
            except Exception as e:
                logger.debug(f"Workday resume dropzone upload note: {e}")

        # Step 4: Step-by-step navigation loop across Workday wizard screens
        max_steps = 10
        form_filler = ChatbotFormFiller(self.page, self.vector_db)

        for step in range(1, max_steps + 1):
            logger.info(f"🔄 Processing Workday Wizard Step {step}...")
            
            # Auto-fill detected form questions on current Workday step
            await form_filler.auto_fill_chatbot_form()
            await self.page.wait_for_timeout(1000)

            # Check if final Submit button is visible
            submit_btn = self.page.locator(self.WORKDAY_SELECTORS['submit_btn']).first
            if await submit_btn.count() > 0 and await submit_btn.is_visible():
                if review_mode:
                    logger.info("⏸️  Workday Application pre-filled! Reached Review & Submit screen (Review Mode active).")
                    return True
                else:
                    logger.info("🚀 Submitting Workday Application...")
                    await submit_btn.click()
                    await self.verify_submission()
                    logger.info("✅ Workday Application submitted successfully.")
                    return True

            # Otherwise, click Next / Save and Continue to advance
            next_clicked = await self._click_if_exists(self.WORKDAY_SELECTORS['next_btn'])
            if not next_clicked:
                # Try generic Save and Continue
                next_clicked = await self._click_if_exists('button:has-text("Save and Continue"), button:has-text("Next")')

            if not next_clicked:
                logger.info(f"No further Next button detected at step {step}. Finishing Workday workflow.")
                raise Exception("Workday workflow finished without reaching the submit button.")

            await self.page.wait_for_timeout(2000)

        raise Exception("Workday application reached max steps without submitting.")
