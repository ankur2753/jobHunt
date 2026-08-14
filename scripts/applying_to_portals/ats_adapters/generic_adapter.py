"""
Generic ATS Adapter
Fallback adapter for arbitrary custom company portals and unrecognized job boards.
Uses ChatbotFormFiller and VectorDBManager for semantic question answering.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .base_adapter import BaseATSAdapter
from .registry import ATSAdapterRegistry
from scripts.common_stuff.chatbot_form_filler import ChatbotFormFiller
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.visual_form_auditor import VisualFormAuditor

logger = logging.getLogger(__name__)


@ATSAdapterRegistry.register
class GenericATSAdapter(BaseATSAdapter):
    """Universal fallback adapter for custom company career portals."""

    def __init__(self, page: Page):
        super().__init__(page)
        self.vector_db = VectorDBManager()
        self.config_path = Path(__file__).resolve().parents[2] / "personal_details" / "custom_ats_config.json"
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load custom_ats_config.json: {e}")
        return {}

    @classmethod
    def adapter_name(cls) -> str:
        return "Generic ATS"

    @classmethod
    def can_handle(cls, url: str, html_snippet: str = "") -> bool:
        # Fallback adapter matches any URL
        return True

    async def dismiss_popups(self):
        popup_selectors = [
            'button:has-text("Accept All")',
            'button:has-text("Accept")',
            '#onetrust-accept-btn-handler',
            '.cookie-accept-btn'
        ]
        for sel in popup_selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    await self.page.wait_for_timeout(500)
            except Exception:
                pass

    async def apply(
        self,
        resume_path: str,
        user_profile: Dict[str, Any],
        review_mode: bool = True,
        cover_letter_path: Optional[str] = None
    ) -> bool:
        logger.info("⚙️ Running Generic ATS Auto-Apply Pipeline...")
        
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass

        await self.dismiss_popups()

        # 1. Look for all File Upload inputs across frames (resume, payslip, etc.) and dispatch change events
        if resume_path and Path(resume_path).exists():
            try:
                frames = self.page.frames if hasattr(self.page, "frames") and self.page.frames else [self.page]
                for target in frames:
                    try:
                        file_inputs = await target.query_selector_all('input[type="file"]')
                        for file_input in file_inputs:
                            try:
                                name_or_id = (await file_input.get_attribute("name") or await file_input.get_attribute("id") or "file_input").lower()
                                
                                is_cover_letter = "cover" in name_or_id or "letter" in name_or_id
                                
                                if is_cover_letter and cover_letter_path and Path(cover_letter_path).exists():
                                    file_to_upload = cover_letter_path
                                    file_type = "cover letter"
                                else:
                                    file_to_upload = resume_path
                                    file_type = "resume"
                                    
                                logger.info(f"📄 Uploading {file_type} via selector/element: {name_or_id}")
                                await file_input.set_input_files(file_to_upload)
                                await file_input.evaluate("""el => {
                                    ['change', 'input', 'blur', 'focusout'].forEach(evt => el.dispatchEvent(new Event(evt, { bubbles: true })));
                                    const parent = el.closest('div, label, td, .form-group') || el.parentElement;
                                    if (parent) {
                                        const err = parent.querySelector('.just-validate-error-label, .error, .invalid-feedback');
                                        if (err) err.style.display = 'none';
                                    }
                                }""")
                                await self.page.wait_for_timeout(1000)
                            except Exception as e:
                                logger.debug(f"File upload attempt failed for {file_input}: {e}")
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Error querying file inputs: {e}")

        # 2. Use ChatbotFormFiller for text inputs, radios, checkboxes, selects
        form_filler = ChatbotFormFiller(self.page, self.vector_db)
        stats = await form_filler.auto_fill_chatbot_form()
        logger.info(f"📊 Generic Form Filler Stats: {stats.to_dict()}")

        # 3. Post-fill Visual Form Audit
        auditor = VisualFormAuditor(self.page)
        audit_report = await auditor.audit_form(screenshot_dir=str(Path.cwd() / "scratch"))
        logger.info(f"🔍 Post-Fill Visual Audit Result: is_valid={audit_report.is_valid}, errors={audit_report.total_errors}")

        # 4. Handle Submit / Review Mode
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Send Application")'
        ]

        if review_mode:
            logger.info("⏸️  Review Mode Active: Form filled! Please review the browser window.")
            return audit_report.is_valid
        else:
            if not audit_report.is_valid:
                logger.warning(f"⚠️ Form has active validation errors, skipping submission attempt.")
                return False
            for sub_sel in submit_selectors:
                try:
                    btn = self.page.locator(sub_sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        logger.info(f"🚀 Submitting application via {sub_sel}...")
                        await btn.click()
                        await self.page.wait_for_timeout(3000)
                        return True
                except Exception as e:
                    logger.debug(f"Submit attempt failed for {sub_sel}: {e}")

        return audit_report.is_valid
