"""
LinkedIn-Specific Form Filler Adapter
Phase 3: LinkedIn Portal Integration

Orchestrates the chatbot form-filling process for LinkedIn job applications:
- Navigates to LinkedIn job apply flow
- Detects dynamic form questions (LinkedIn application forms)
- Auto-fills questions using semantic matching
- Handles LinkedIn-specific form behaviors (modals, validation)
- Provides reporting and human fallback
"""

import asyncio
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.common_stuff.chatbot_form_filler import ChatbotFormFiller, ChatbotFormFillerStats
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.answer_validators import AnswerNormalizer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LinkedInFormFillingSession:
    """Represents a LinkedIn form filling session."""
    job_id: str
    company_name: Optional[str]
    job_title: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    form_stats: Optional[ChatbotFormFillerStats]
    status: str  # 'started' | 'completed' | 'failed' | 'partial' | 'manual_review'
    error_message: Optional[str] = None
    url: Optional[str] = None
    manual_answers: Dict[str, str] = None


class LinkedInFormFiller:
    """
    Orchestrates intelligent form filling for LinkedIn job applications.
    
    Workflow:
    1. Navigate to LinkedIn job apply URL
    2. Wait for application form to load
    3. Detect form questions
    4. Initialize ChatbotFormFiller
    5. Auto-fill forms with semantic matching
    6. On low confidence or detection errors: Human fallback
    7. Validate form before submission
    8. Return results
    
    Features:
    - Automatic retry on form load failures
    - Timeout handling for slow forms
    - LinkedIn modal/popup handling
    - Human fallback for uncertain answers
    - Form validation before submission
    - Session logging and statistics
    """
    
    # LinkedIn-specific selectors
    LINKEDIN_SELECTORS = {
        'job_title': 'h2[data-test-id="job-card-title"]',
        'company_name': '[data-test-id="company-name"]',
        'apply_button': 'button[aria-label*="Apply"]',
        'form_container': '.artdeco-modal__content, [role="dialog"]',
        'form_fields': 'input, select, textarea, [role="combobox"], [role="radio"]',
        'next_button': 'button[aria-label*="Next"]',
        'submit_button': 'button[aria-label*="Send application"], button:has-text("Send")',
        'modal_close': 'button[aria-label*="Dismiss"]',
        'loader': '.artdeco-spinner, .artdeco-loader, [data-test-id="loader"]',
        'error_message': '[role="alert"], .artdeco-inline-feedback--error',
    }
    
    # Constants
    FORM_LOAD_TIMEOUT = 10000  # 10 seconds
    MAX_RETRIES = 3
    
    def __init__(
        self,
        page: Page,
        vector_db_manager: VectorDBManager,
        confidence_threshold: float = 0.65,  # LinkedIn: balanced threshold
        enable_logging: bool = True
    ):
        """
        Initialize LinkedIn form filler.
        
        Args:
            page: Playwright page object (assumed to be on LinkedIn)
            vector_db_manager: VectorDBManager instance for answer lookup
            confidence_threshold: Min confidence for auto-fill (LinkedIn: 0.65)
            enable_logging: Whether to log all actions
        """
        self.page = page
        self.vector_db = vector_db_manager
        self.confidence_threshold = confidence_threshold
        self.enable_logging = enable_logging
        self.answer_normalizer = AnswerNormalizer()
        
        if enable_logging:
            logger.setLevel(logging.DEBUG)
        
        self.session: Optional[LinkedInFormFillingSession] = None
    
    async def fill_linkedin_job_application(
        self,
        job_url: str,
        max_questions: Optional[int] = None,
        dry_run: bool = False,
        allow_human_input: bool = True,
        submit_form: bool = False
    ) -> LinkedInFormFillingSession:
        """
        Main entry point: Fill LinkedIn job application form.
        
        Args:
            job_url: LinkedIn job page URL (not application URL)
            max_questions: Max form questions to process (None = all)
            dry_run: If True, only detect without filling
            allow_human_input: If True, ask user for answers on low confidence (fallback)
            submit_form: If True, submit form after filling (CAUTION: actual application!)
        
        Returns:
            LinkedInFormFillingSession with results
        """
        logger.info(f"Starting LinkedIn job application filling for: {job_url}")
        
        # Extract job ID from URL
        job_id = self._extract_job_id_from_url(job_url)
        
        self.session = LinkedInFormFillingSession(
            job_id=job_id,
            start_time=datetime.now(),
            end_time=None,
            form_stats=None,
            status="started",
            url=job_url,
            manual_answers={}
        )
        
        try:
            # Step 1: Navigate to job page
            logger.info(f"Navigating to: {job_url}")
            await self.page.goto(job_url, wait_until='networkidle')
            
            # Step 2: Extract job details
            await self._extract_job_details()
            
            # Step 3: Click Apply button
            logger.info("Clicking Apply button...")
            await self._click_apply_button()
            
            # Step 4: Wait for form to load
            logger.info("Waiting for application form to load...")
            await self._wait_for_form_load()
            
            # Step 5: Initialize form filler
            form_filler = ChatbotFormFiller(
                self.page,
                self.vector_db,
                enable_logging=self.enable_logging
            )
            
            # Step 6: Auto-fill form with human fallback
            logger.info("Auto-filling form questions...")
            form_stats = await self._fill_form_with_fallback(
                form_filler,
                max_questions=max_questions,
                dry_run=dry_run,
                allow_human_input=allow_human_input
            )
            
            self.session.form_stats = form_stats
            
            # Step 7: Optional submit
            if submit_form and not dry_run:
                logger.warning("⚠️ SUBMITTING FORM - This will create an actual application!")
                await self._submit_form()
                self.session.status = "completed"
            else:
                self.session.status = "partial" if not dry_run else "completed"
            
            logger.info(f"✅ Form filling completed: {form_stats.auto_filled}/{form_stats.total_questions} auto-filled")
        
        except PlaywrightTimeoutError as e:
            self.session.status = "failed"
            self.session.error_message = f"Timeout: {str(e)}"
            logger.error(f"❌ Timeout during form filling: {str(e)}")
        
        except Exception as e:
            self.session.status = "failed"
            self.session.error_message = str(e)
            logger.error(f"❌ Error during form filling: {str(e)}", exc_info=True)
        
        finally:
            self.session.end_time = datetime.now()
        
        return self.session
    
    async def _fill_form_with_fallback(
        self,
        form_filler: ChatbotFormFiller,
        max_questions: Optional[int] = None,
        dry_run: bool = False,
        allow_human_input: bool = True
    ) -> ChatbotFormFillerStats:
        """
        Fill form with automatic fallback to human input for low confidence.
        
        Args:
            form_filler: ChatbotFormFiller instance
            max_questions: Max questions to process
            dry_run: If True, only detect without filling
            allow_human_input: If True, ask user for answers on low confidence
        
        Returns:
            ChatbotFormFillingStats with results
        """
        try:
            # Detect questions
            questions = await form_filler._detect_form_questions()
            logger.info(f"Detected {len(questions)} form questions")
            
            if max_questions:
                questions = questions[:max_questions]
            
            stats = ChatbotFormFillerStats(total_questions=len(questions))
            
            if dry_run:
                logger.info("DRY RUN MODE: Not filling form, only detecting")
                return stats
            
            # Process each question
            for i, question in enumerate(questions, 1):
                logger.info(f"Processing question {i}/{len(questions)}: {question.question_text}")
                
                try:
                    # Try semantic matching first
                    candidate = self.vector_db.answer_question(
                        question.question_text,
                        confidence_threshold=self.confidence_threshold
                    )
                    
                    answer = None
                    confidence = 0.0
                    
                    if candidate and candidate.should_autofill:
                        # High confidence - use it
                        answer = candidate.answer_text
                        confidence = candidate.confidence
                        logger.debug(f"✓ High confidence match: {answer} ({confidence:.2f})")
                        stats.auto_filled += 1
                    
                    elif allow_human_input and candidate:
                        # Low confidence - ask user
                        logger.warning(f"⚠️ Low confidence: {candidate.answer_text} ({candidate.confidence:.2f})")
                        user_input = input(f"\n❓ Question: {question.question_text}\n" +
                                         f"   Suggested: {candidate.answer_text} ({candidate.confidence:.2f})\n" +
                                         f"   Enter answer (press Enter to use suggestion, or type new answer): ").strip()
                        
                        if user_input:
                            answer = user_input
                            confidence = 1.0  # User provided
                            logger.debug(f"✓ User provided answer: {answer}")
                            self.session.manual_answers[question.question_text] = answer
                        else:
                            answer = candidate.answer_text
                            confidence = candidate.confidence
                            logger.debug(f"✓ Using suggestion: {answer}")
                        
                        stats.auto_filled += 1
                    
                    elif allow_human_input:
                        # No semantic match - ask user
                        logger.warning(f"⚠️ No semantic match found for: {question.question_text}")
                        user_input = input(f"\n❓ Question: {question.question_text}\n" +
                                         f"   No suggestion available.\n" +
                                         f"   Enter answer (or press Enter to skip): ").strip()
                        
                        if user_input:
                            answer = user_input
                            confidence = 1.0  # User provided
                            logger.debug(f"✓ User provided answer: {answer}")
                            self.session.manual_answers[question.question_text] = answer
                            stats.auto_filled += 1
                        else:
                            logger.debug("→ Skipped by user")
                            stats.skipped += 1
                            continue
                    else:
                        # No match and no human input allowed
                        logger.debug("→ No match and human input disabled")
                        stats.skipped += 1
                        continue
                    
                    # Fill the field if we have an answer
                    if answer:
                        fill_success = await form_filler._fill_form_field(question, answer)
                        if fill_success:
                            logger.info(f"✓ Filled: {question.question_text} → {answer}")
                        else:
                            logger.error(f"✗ Failed to fill field: {question.question_text}")
                        if allow_human_input:
                            logger.warning("⚠️  Initiating MCP/Human Fallback due to UI interaction failure.")
                            prompt_text = (
                                f"\n🤖 MCP/HUMAN FALLBACK TRIGGERED\n"
                                f"❓ Question: {question.question_text}\n"
                                f"💡 Target Answer: {answer}\n"
                                f"❌ Issue: Cannot find or interact with the input element (UI might have changed).\n"
                                f"👉 Action: Please fill this field manually in the browser (or use MCP tools), then press Enter to continue.\n"
                                f"   Press Enter when done: "
                            )
                            await asyncio.to_thread(input, prompt_text)
                            logger.info(f"✓ Assumed filled via fallback: {question.question_text}")
                        else:
                            stats.failed += 1
                
                except Exception as e:
                    logger.error(f"Error processing question: {str(e)}")
                    stats.failed += 1
            
            return stats
        
        except Exception as e:
            logger.error(f"Error in form filling with fallback: {str(e)}")
            raise
    
    async def _click_apply_button(self) -> None:
        """Click the Apply button to open application form."""
        try:
            apply_buttons = await self.page.query_selector_all(self.LINKEDIN_SELECTORS['apply_button'])
            if apply_buttons:
                await apply_buttons[0].click()
                await asyncio.sleep(1)  # Wait for modal to appear
                logger.debug("Apply button clicked")
            else:
                logger.warning("Could not find Apply button")
        except Exception as e:
            logger.warning(f"Error clicking Apply button: {str(e)}")
    
    async def _extract_job_details(self) -> None:
        """Extract job title and company name from page."""
        try:
            # Get job title
            job_title_elem = await self.page.query_selector(self.LINKEDIN_SELECTORS['job_title'])
            if job_title_elem:
                self.session.job_title = await job_title_elem.text_content()
                logger.info(f"Job: {self.session.job_title}")
            
            # Get company name
            company_elem = await self.page.query_selector(self.LINKEDIN_SELECTORS['company_name'])
            if company_elem:
                self.session.company_name = await company_elem.text_content()
                logger.info(f"Company: {self.session.company_name}")
        
        except Exception as e:
            logger.warning(f"Error extracting job details: {str(e)}")
    
    async def _wait_for_form_load(self, timeout_ms: int = 10000) -> None:
        """Wait for application form to be visible."""
        try:
            await self.page.wait_for_selector(
                self.LINKEDIN_SELECTORS['form_container'],
                timeout=timeout_ms
            )
            logger.debug("Form container detected")
        except PlaywrightTimeoutError:
            logger.warning("Form container not found - proceeding anyway")
    
    async def _submit_form(self) -> None:
        """Submit the filled form."""
        try:
            logger.info("Submitting form...")
            
            submit_button = await self.page.query_selector(
                self.LINKEDIN_SELECTORS['submit_button']
            )
            
            if submit_button and await submit_button.is_visible():
                await submit_button.click()
                logger.info("Form submitted successfully")
                
                # Wait for confirmation
                await asyncio.sleep(2)
            else:
                prompt_text = (
                    f"\n🤖 MCP/HUMAN FALLBACK TRIGGERED\n"
                    f"❌ Issue: Submit button not found or not visible.\n"
                    f"👉 Action: Please manually click Submit/Next in the browser (or use MCP tools), then press Enter to verify.\n"
                    f"   Press Enter when done: "
                )
                await asyncio.to_thread(input, prompt_text)
                logger.info("✅ Continuing after manual submission intervention.")
        
        except Exception as e:
            logger.error(f"Error submitting form: {str(e)}")
            raise
    
    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract job ID from LinkedIn URL."""
        import re
        # LinkedIn URLs: /jobs/12345678/ or similar
        match = re.search(r'/jobs/(\d+)', url)
        if match:
            return match.group(1)
        return "unknown"
    
    def get_session_report(self) -> Dict:
        """Get detailed report of the form filling session."""
        if not self.session:
            return {}
        
        report = {
            'job_id': self.session.job_id,
            'job_title': self.session.job_title,
            'company_name': self.session.company_name,
            'url': self.session.url,
            'status': self.session.status,
            'start_time': self.session.start_time.isoformat(),
            'end_time': self.session.end_time.isoformat() if self.session.end_time else None,
            'duration_seconds': (
                (self.session.end_time - self.session.start_time).total_seconds()
                if self.session.end_time else None
            ),
            'error': self.session.error_message,
            'manual_answers_count': len(self.session.manual_answers) if self.session.manual_answers else 0
        }
        
        if self.session.form_stats:
            report['form_stats'] = {
                'total_questions': self.session.form_stats.total_questions,
                'auto_filled': self.session.form_stats.auto_filled,
                'skipped': self.session.form_stats.skipped,
                'failed': self.session.form_stats.failed,
                'fill_rate': (
                    self.session.form_stats.auto_filled / self.session.form_stats.total_questions
                    if self.session.form_stats.total_questions > 0 else 0
                )
            }
        
        if self.session.manual_answers:
            report['manual_answers'] = self.session.manual_answers
        
        return report


if __name__ == "__main__":
    print("LinkedInFormFiller module loaded successfully")
