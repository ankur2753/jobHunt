"""
Naukri-Specific Form Filler Adapter
Phase 3: Naukri Portal Integration
Phase 2+: Enhanced selector validation and fallback chains

Orchestrates the chatbot form-filling process for Naukri job applications:
- Navigates to Naukri job application URL
- Detects dynamic form questions (Naukri chatbot)
- Auto-fills questions using semantic matching
- Handles Naukri-specific form behaviors (popups, animations, validation)
- Provides reporting and logging
- **NEW**: Multi-tier selector fallbacks and validation
"""

import asyncio
import logging
import re
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime
from playwright.async_api import Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError
from pathlib import Path
import sys

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.common_stuff.chatbot_form_filler import ChatbotFormFiller, ChatbotFormFillerStats
from scripts.common_stuff.vector_db_manager import VectorDBManager
from scripts.common_stuff.answer_validators import AnswerNormalizer
from scripts.common_stuff.naukri_selector_discovery import SelectorValidator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NaukriFormFillingSession:
    """Represents a Naukri form filling session."""
    job_id: str
    start_time: datetime
    status: str  # 'started' | 'completed' | 'failed' | 'partial' | 'manual_review'
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    end_time: Optional[datetime] = None
    form_stats: Optional[ChatbotFormFillerStats] = None
    error_message: Optional[str] = None
    url: Optional[str] = None
    manual_answers: Dict[str, str] = None


class NaukriFormFiller:
    """
    Orchestrates intelligent form filling for Naukri job applications.
    
    Workflow:
    1. Navigate to Naukri job apply URL
    2. Wait for job details to load
    3. Wait for chatbot form to appear
    4. Initialize ChatbotFormFiller
    5. Auto-fill forms with semantic matching
    6. Handle NLA (Next Level Automation) popups
    7. Validate form submission
    8. Return results and logs
    
    Features:
    - Automatic retry on form load failures
    - Timeout handling for slow forms
    - Naukri popup/modal handling
    - Form validation before submission
    - Session logging and statistics
    """
    
    # Naukri-specific selectors (with fallback chains for resilience)
    NAUKRI_SELECTORS = {
        # Job Detail Page - Primary headings
        'job_title_heading': '[data-qa="jobDetailTitle"], h1.jobTitle, h1[data-qa="jobTitle"], .jobDetailTitle',
        'company_name': '[data-qa="jobDetailCompany"], [data-qa="companyName"], .companyName, [data-qa="jobCardCompanyName"]',
        
        # Apply & Form
        'apply_button': 'button.multi-apply-button, button[data-qa="nxtApplyBtn"], button[data-qa="applyBtn"], button:has-text("Apply")',
        'chatbot_form_container': '.chatbot_DrawerContentWrapper',
        'form_fields': 'input, select, textarea, [role="combobox"], [role="radio"]',
        
        # Submit & Navigation
        'submit_button': 'button[data-qa="submit"], button[type="submit"], button[data-qa="submitBtn"], button:has-text("Submit")',
        'next_button': 'button[data-qa="nxtBtn"], button[data-qa="nextBtn"], button:has-text("Next"), .next-button',
        
        # Popups & Modals (NLA = Next Level Automation)
        'nla_popup_close': '[data-qa="nlaClose"], button[data-qa="closeModal"], button[aria-label="Close"], button[aria-label="close"], .popup-close, .modal-close, button[class*="close"]',
        'nla_popup': '[data-qa="nlaModal"], .nextLevelAutomation, .nla-popup, [role="dialog"]',
        
        # Utilities
        'loader': '.loader, .spinner, [data-qa="loader"], [class*="loading"]',
        'required_indicator': '[required], [aria-required="true"], .required, .mandatory, [data-qa*="required"]',
        'error_message': '.error, [role="alert"], .validation-error, .form-error, [data-qa*="error"]',
    }
    
    # Root of the Naukri chatbot side panel. EVERY chatbot query MUST be scoped to
    # this drawer — querying page-wide picks up the search/experience/location inputs
    # on the recommended-jobs page sitting behind the drawer, which steals focus and
    # closes the panel (the original "clicks outside the box" bug).
    DRAWER = '.chatbot_DrawerContentWrapper'

    # Constants (with enhanced timeout for form loading)
    FORM_LOAD_TIMEOUT = 20000  # 20 seconds (increased from 15)
    POPUP_CHECK_INTERVAL = 2000  # 2 seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 1000  # 1 second between retries (in ms)
    
    def __init__(
        self,
        page: Page,
        vector_db_manager: VectorDBManager,
        confidence_threshold: float = 0.60,  # semantic-match threshold (>=0.6 auto-answer + log)
        enable_logging: bool = True,
        enable_selector_validation: bool = False
    ):
        """
        Initialize Naukri form filler.
        
        Args:
            page: Playwright page object (assumed to be on Naukri)
            vector_db_manager: VectorDBManager instance for answer lookup
            confidence_threshold: Min confidence for auto-fill (Naukri: 0.70)
            enable_logging: Whether to log all actions
            enable_selector_validation: Whether to validate selectors during execution
        """
        self.page = page
        self.vector_db = vector_db_manager
        self.confidence_threshold = confidence_threshold
        self.enable_logging = enable_logging
        self.answer_normalizer = AnswerNormalizer()
        self.enable_selector_validation = enable_selector_validation
        
        # Initialize selector validator if enabled
        self.selector_validator = SelectorValidator(page, enable_logging=enable_logging) if enable_selector_validation else None
        
        if enable_logging:
            logger.setLevel(logging.DEBUG)
        
        self.session: Optional[NaukriFormFillingSession] = None
    
    async def fill_naukri_job_application(
        self,
        job_url: str,
        max_questions: Optional[int] = None,
        dry_run: bool = False,
        allow_human_input: bool = True,
        submit_form: bool = False,
        navigate: bool = True
    ) -> NaukriFormFillingSession:
        """
        Main entry point: Fill Naukri job application form.
        
        Args:
            job_url: Naukri job application URL
            max_questions: Max form questions to process (None = all)
            dry_run: If True, only detect without filling
            allow_human_input: If True, ask user for answers on low confidence (fallback)
            submit_form: If True, submit form after filling (CAUTION: actual application!)
            navigate: If True, navigate to job_url first (set False if already there)
        
        Returns:
            NaukriFormFillingSession with results
        """
        logger.info(f"Starting Naukri job application filling for: {job_url}")
        
        # Extract job ID from URL
        job_id = self._extract_job_id_from_url(job_url)
        
        self.session = NaukriFormFillingSession(
            job_id=job_id,
            start_time=datetime.now(),
            end_time=None,
            form_stats=None,
            status="started",
            url=job_url,
            manual_answers={}
        )
        
        try:
            if navigate:
                # Step 1: Navigate to job URL
                logger.info(f"Navigating to: {job_url}")
                await self.page.goto(job_url, wait_until='networkidle')
                
                # Step 2: Close any popups
                await self._close_nla_popups()
                
                # Click Apply button to open form
                await self._click_apply_button()
            
            # Step 3: Extract job details
            await self._extract_job_details()
            
            # Step 4: Wait for form to load
            logger.info("Waiting for chatbot form to load...")
            await self._wait_for_form_load()
            
            # Step 5: Initialize form filler
            form_filler = ChatbotFormFiller(
                self.page,
                self.vector_db,
                enable_logging=self.enable_logging
            )
            
            # Step 6: Auto-fill form
            logger.info("Auto-filling form questions...")
            form_stats = await self._fill_form_with_fallback(
                form_filler,
                max_questions=max_questions,
                dry_run=dry_run,
                allow_human_input=allow_human_input
            )
            
            self.session.form_stats = form_stats
            
            # Step 7: Handle form validation
            await self._validate_form_fields()
            
            # Step 8: Optional: Submit form
            if submit_form and not dry_run:
                logger.warning("⚠️ SUBMITTING FORM - This will create an actual application!")
                await self._submit_form()
                self.session.status = "completed"
            else:
                self.session.status = "partial" if not dry_run else "completed"
            
            logger.info(f"✅ Form filling completed: {form_stats.auto_filled}/{form_stats.total_questions} filled")
        
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
        Fill the Naukri chatbot form sequentially with Playwright codegen fallback.

        The Naukri chatbot presents one question at a time.  Answering a question
        triggers the next one.  This method loops — detecting the current visible
        question, answering it, waiting for the chatbot to advance — until the
        submit button appears or no new question is detected.
        
        On failure: Launches Playwright Inspector (codegen) for manual recording.
        """
        stats = ChatbotFormFillerStats()

        if dry_run:
            state = await self._detect_current_chatbot_state()
            if state.get('question'):
                stats.total_questions = 1
                logger.info(f"DRY RUN: detected question → {state['question'][:60]}")
            return stats

        # Delegate to the single conversational driver (drawer-scoped, handles
        # radio / checkbox / free-text / yes-no, clicks Save to advance).
        conv = await self.run_chatbot_conversation(
            allow_human_input=allow_human_input,
            max_steps=(max_questions or 40),
        )

        stats.total_questions = conv['questions']
        stats.auto_filled = conv['answered']
        stats.skipped = conv['skipped']
        if self.session is not None:
            for item in conv['review']:
                self.session.manual_answers[item['question']] = item['answer']
        return stats

    async def _launch_codegen_fallback(self) -> None:
        """
        Launch Playwright Inspector (codegen) for manual recording when automation fails.
        
        This allows the user to manually perform the action (click radio, fill text, etc.)
        and the codegen tool will record the correct selectors and actions.
        """
        try:
            logger.warning("\n" + "="*70)
            logger.warning("🔧 PLAYWRIGHT INSPECTOR (CODEGEN) FALLBACK TRIGGERED")
            logger.warning("="*70)
            logger.warning("\n⚠️  AUTOMATION FAILED - Starting Manual Recording Mode")
            logger.warning("\n📝 Instructions:")
            logger.warning("   1. The Playwright Inspector window will open")
            logger.warning("   2. Manually perform the action in the browser:")
            logger.warning("      - Click the radio button / option")
            logger.warning("      - Fill the text field")
            logger.warning("      - Click Save button")
            logger.warning("   3. The inspector will record the correct selectors/actions")
            logger.warning("   4. Close the inspector when done")
            logger.warning("   5. The script will resume automatically")
            logger.warning("\n" + "="*70 + "\n")
            
            # Pause and let user know what to do
            await asyncio.to_thread(
                input,
                "\n👉 Press Enter when you're ready to launch the Inspector (or Ctrl+C to cancel): "
            )
            
            # Launch playwright codegen attached to the current page
            # This will record actions on the same page/context
            import subprocess
            
            logger.info("🚀 Launching Playwright Codegen Inspector...")
            
            # Get the WebSocket endpoint from the browser context
            # We'll use the page's URL and browser details to launch codegen
            page_url = self.page.url
            
            logger.info(f"📍 Current page: {page_url}")
            logger.info("\n🎥 Recording mode started - perform actions in the browser now...")
            
            # Start codegen in a subprocess
            # Note: This requires Playwright CLI to be available
            try:
                # Try to launch codegen via playwright CLI
                subprocess.Popen(['playwright', 'codegen', page_url])
                
                # Wait for user to close the inspector
                await asyncio.to_thread(
                    input,
                    "\n👉 Close the Playwright Inspector window when done recording, then press Enter: "
                )
                
                logger.info("✅ Inspector closed. Resuming automation...")
                
            except FileNotFoundError:
                logger.warning("⚠️  Playwright CLI not found. Starting manual guidance mode instead.")
                logger.warning("\n📋 Please manually perform the following:")
                logger.warning("   1. Click the radio button or option in the browser")
                logger.warning("   2. Or fill the text field and press Enter")
                logger.warning("   3. Or click the Save/Next button")
                logger.warning("   4. Note down the element you clicked (right-click → Inspect)")
                logger.warning("   5. This info can help improve the selectors\n")
                
                await asyncio.to_thread(
                    input,
                    "\n👉 Press Enter once you've performed the action in the browser: "
                )
                
                logger.info("✅ Resuming automation...")
            
            logger.warning("\n" + "="*70)
            logger.warning("✅ CODEGEN FALLBACK COMPLETED - Resuming Form Filling Loop")
            logger.warning("="*70 + "\n")
        
        except KeyboardInterrupt:
            logger.warning("\n\n❌ User cancelled codegen fallback (Ctrl+C)")
            raise
        except Exception as e:
            logger.error(f"Error in codegen fallback: {e}")
            # Don't raise — just log and continue

    # ------------------------------------------------------------------
    # Chatbot state helpers
    # ------------------------------------------------------------------

    async def _is_chatbot_open(self) -> bool:
        """True while the Naukri chatbot drawer is present and visible."""
        try:
            el = await self.page.query_selector(self.DRAWER)
            return bool(el and await el.is_visible())
        except Exception:
            return False

    async def _detect_current_chatbot_state(self) -> dict:
        """
        Detect what the Naukri chatbot is currently asking.

        ALL queries are scoped to ``self.DRAWER`` so we never touch the
        recommended-jobs page behind the panel.

        Returns a dict:
            {
              'done':       True if the drawer has closed (all jobs submitted),
              'question':   text of the last visible bot message (or None),
              'kind':       'single' | 'multi' | 'text' | 'none',
              'options':    [(label_text, clickable_element), ...]  (radio/checkbox),
              'text_el':    the contenteditable element for free-text answers (or None),
            }
        """
        if not await self._is_chatbot_open():
            return {'done': True, 'question': None, 'kind': 'none', 'options': [], 'text_el': None}

        D = self.DRAWER

        # --- Current question = last visible bot message inside the drawer ---
        question = None
        try:
            spans = await self.page.query_selector_all(f'{D} .botItem .botMsg span')
            for s in spans:
                if await s.is_visible():
                    t = (await s.text_content() or '').strip()
                    if len(t) > 4:
                        question = t  # keep last → most recent question
        except Exception:
            pass

        # --- Options: radio (single-select) or checkbox (multi-select) ---
        # Detect by INPUT TYPE inside the drawer, not by Naukri wrapper classes,
        # so it survives the different widgets recruiters use.
        options = []
        kind = 'none'
        radios = await self.page.query_selector_all(f'{D} input[type="radio"]')
        checks = await self.page.query_selector_all(f'{D} input[type="checkbox"]')
        inputs = radios or checks
        if inputs:
            kind = 'single' if radios else 'multi'
            for inp in inputs:
                text, clickable = await self._resolve_option(inp)
                if text:
                    options.append((text, clickable))

        # --- Free-text answers go into the contenteditable div ---
        text_el = None
        if not options:
            try:
                ta = await self.page.query_selector(
                    f'{D} div[contenteditable="true"], {D} textarea, {D} input[type="text"]'
                )
                if ta and await ta.is_visible():
                    text_el = ta
                    kind = 'text'
            except Exception:
                pass

        return {
            'done': False,
            'question': question,
            'kind': kind,
            'options': options,
            'text_el': text_el,
        }

    async def _resolve_option(self, input_el):
        """
        Given a radio/checkbox input inside the drawer, return
        (label_text, clickable_element). The label (``label[for=<id>]``) is the
        reliable click target; the styled input itself is often not directly clickable.
        """
        text = ''
        clickable = input_el
        try:
            rid = await input_el.get_attribute('id')
            if rid:
                # Attribute selector in quotes tolerates spaces / '+' (e.g. "6+ yrs")
                label = await self.page.query_selector(f'{self.DRAWER} label[for="{rid}"]')
                if label:
                    text = (await label.text_content() or '').strip()
                    clickable = label
            if not text:
                text = (await input_el.get_attribute('value') or '').strip()
            if not text:
                text = (await input_el.evaluate(
                    "el => (el.closest('.ssrc__radio-btn-container, label, li') || {}).textContent || ''"
                ) or '').strip()
        except Exception:
            pass
        return text, clickable

    async def _click_send_button(self, timeout_s: float = 6.0) -> bool:
        """
        Click the chatbot's Save/send button to submit the current answer and
        advance. The button starts as ``div.send.disabled`` and the ``disabled``
        class is removed once a valid answer is entered, so we poll for it.
        """
        deadline = timeout_s
        while deadline > 0:
            try:
                send = await self.page.query_selector(f'{self.DRAWER} div.send:not(.disabled) .sendMsg')
                if not send:
                    send = await self.page.query_selector('div.send:not(.disabled) .sendMsg')
                if send and await send.is_visible():
                    await send.click(force=True)
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.4)
            deadline -= 0.4
        logger.warning("  ⚠️  Save/send button never became enabled")
        return False

    def _derive_yes_no(self, question: str, options: list) -> Optional[str]:
        """
        For boolean (Yes/No) questions whose threshold lives in the *question*
        (e.g. "Do you have more than 3 years of experience?"), derive the answer
        by comparing the user's known numeric facts against the threshold.

        Returns the matching option text ('yes'/'no'/...) or None if not derivable.
        """
        opt_texts = {t.lower(): t for t, _ in options}
        is_boolean = bool(opt_texts) and all(
            o in ('yes', 'no', 'skip', 'maybe', 'y', 'n') for o in opt_texts
        )
        if not is_boolean:
            return None

        q = question.lower()
        m = re.search(r'(\d+(?:\.\d+)?)\s*(?:\+|years?|yrs?)', q)
        if not m:
            return None
        threshold = float(m.group(1))

        # User's known experience (years). Pull total_experience from vector DB facts.
        user_years = None
        try:
            cands = self.vector_db.answer_question_with_candidates(
                question, n_candidates=1, confidence_threshold=0.0
            )
            if cands:
                nums = re.findall(r'\d+(?:\.\d+)?', self._clean_answer(cands[0].answer_text))
                if nums:
                    user_years = float(nums[0])
        except Exception:
            pass
        if user_years is None:
            return None

        if re.search(r'more than|greater than|over|at least|minimum|>\s*=?|above', q):
            meets = user_years >= threshold
        elif re.search(r'less than|under|below|<\s*=?|at most|maximum', q):
            meets = user_years <= threshold
        else:
            meets = user_years >= threshold  # default reading for "N+ years?"

        want = 'yes' if meets else 'no'
        return opt_texts.get(want)

    # ------------------------------------------------------------------
    # Conversational driver (single source of truth for chatbot filling)
    # ------------------------------------------------------------------

    async def run_chatbot_conversation(
        self,
        allow_human_input: bool = True,
        max_steps: int = 40,
        review_log_path: Optional[str] = None,
    ) -> dict:
        """
        Drive the already-open Naukri chatbot drawer to completion.

        The drawer handles ALL bulk-selected jobs in one continuous conversation:
        answer the current question → click Save → next question appears → ... until
        the drawer closes (everything submitted) or we stall.

        Returns a stats dict with answered/guessed/prompted/skipped counts, whether
        the drawer completed, and a 'review' list of low-confidence / guessed answers.
        """
        stats = {
            'questions': 0, 'answered': 0, 'guessed': 0, 'prompted': 0,
            'skipped': 0, 'completed': False, 'review': [],
        }
        last_q = None
        stall = 0
        MAX_STALL = 4

        for _ in range(max_steps):
            await asyncio.sleep(1.2)  # let the chatbot animate the next question in
            state = await self._detect_current_chatbot_state()

            if state['done']:
                stats['completed'] = True
                logger.info("✅ Chatbot drawer closed — all selected jobs submitted")
                break

            q = state['question']

            if not q:
                stall += 1
                if stall >= MAX_STALL:
                    logger.warning("⚠️  No question detected after retries — stopping")
                    break
                await asyncio.sleep(1.5)
                continue

            if q == last_q:
                # We answered but the chatbot didn't advance — force a fallback answer.
                stall += 1
                if stall >= MAX_STALL:
                    logger.warning(f"⚠️  Stuck on: {q[:60]} — forcing fallback")
                    await self._answer_fallback(state, stats, reason='stall')
                    last_q = None
                    stall = 0
                await asyncio.sleep(1.5)
                continue

            stall = 0
            last_q = q
            stats['questions'] += 1
            await self._answer_question(state, stats, allow_human_input)

        if review_log_path and stats['review']:
            self._write_review_log(review_log_path, stats['review'])

        logger.info(
            f"📊 Chatbot: {stats['answered']} answered "
            f"({stats['guessed']} guessed, {stats['prompted']} prompted), "
            f"completed={stats['completed']}"
        )
        return stats

    async def _answer_question(self, state: dict, stats: dict, allow_human_input: bool) -> None:
        """Answer the current question, then click Save to advance."""
        q = state['question']
        kind = state['kind']
        options = state['options']

        # Semantic candidates from the vector DB (sentence-transformer backed).
        try:
            candidates = self.vector_db.answer_question_with_candidates(
                q, n_candidates=3, confidence_threshold=0.0
            )
        except Exception as e:
            logger.debug(f"vector db lookup failed: {e}")
            candidates = []
        best = candidates[0] if candidates else None
        confident = bool(best and best.confidence >= self.confidence_threshold)
        # Facts are stored as "Question?\nA: value" — fill only the value, never the
        # stored question text, into the chatbot.
        best_text = self._clean_answer(best.answer_text) if best else ''

        # Detail goes to the log file only; the concise one-line result is emitted
        # on the console by _finish().
        logger.debug("BOT: %s | options=%s | best=%s (%.2f)",
                     q,
                     [t for t, _ in options] if options else None,
                     (best_text[:60] if best else None),
                     (best.confidence if best else 0.0))

        # ---------- Option questions (single / multi / yes-no) ----------
        if options:
            # 1) Boolean question with threshold in the prompt → derive from facts.
            derived = self._derive_yes_no(q, options)
            if derived:
                ok = await self._click_option_by_text(derived, options)
                if ok:
                    await self._finish(stats, q, derived, 'derived')
                    return

            # 2) Confident semantic answer → match to an option.
            if confident:
                pick = self._pick_best_chip(best_text, options)
                if pick:
                    await self._click_option(pick[1])
                    await self._finish(stats, q, pick[0], 'auto')
                    return

            # 3) LLM Fallback (Bridge)
            from scripts.common_stuff.llm_fallback import query_llm_fallback, get_api_key_and_provider
            api_key, _, _, _ = get_api_key_and_provider()
            if api_key:
                try:
                    details = self.vector_db.get_all_details()
                    profile_context = "\n".join(details.get("documents", []))
                    opt_list = [t for t, _ in options]
                    llm_ans = await query_llm_fallback(q, options=opt_list, profile_context=profile_context)
                    if llm_ans:
                        pick = self._pick_best_chip(llm_ans, options)
                        if pick:
                            await self._click_option(pick[1])
                            await self._finish(stats, q, pick[0], 'llm_fallback', conf=0.99)
                            return
                except Exception as e:
                    logger.error(f"Error in LLM fallback: {e}")
            else:
                logger.warning("⚠️ LLM Fallback: Bypassed because no active API key was found (set GEMINI_API_KEY or OPENROUTER_API_KEY in your environment or .env).")

            # 4) Low confidence → ask the human if allowed.
            if allow_human_input:
                picked = await self._prompt_for_option(q, options, best_text)
                if picked:
                    await self._click_option(picked[1])
                    self._learn(q, picked[0])
                    await self._finish(stats, q, picked[0], 'prompted')
                    stats['prompted'] += 1
                    return

            # 5) Best-effort guess (top candidate even if <0.6), then fallback.
            if best_text:
                pick = self._pick_best_chip(best_text, options)
                if pick:
                    await self._click_option(pick[1])
                    await self._finish(stats, q, pick[0], 'guess', review=True,
                                       conf=best.confidence)
                    return
            await self._answer_fallback(state, stats, reason='no-match')
            return

        # ---------- Free-text questions ----------
        if state['text_el'] is not None:
            value = None
            tag = 'auto'
            if confident:
                value = best_text
            else:
                from scripts.common_stuff.llm_fallback import query_llm_fallback, get_api_key_and_provider
                api_key, _, _, _ = get_api_key_and_provider()
                if api_key:
                    try:
                        details = self.vector_db.get_all_details()
                        profile_context = "\n".join(details.get("documents", []))
                        llm_ans = await query_llm_fallback(q, options=None, profile_context=profile_context)
                        if llm_ans:
                            value = llm_ans
                            tag = 'llm_fallback'
                    except Exception as e:
                        logger.error(f"Error in LLM fallback: {e}")
                else:
                    logger.warning("⚠️ LLM Fallback: Bypassed because no active API key was found (set GEMINI_API_KEY or OPENROUTER_API_KEY in your environment or .env).")

            if value is None and allow_human_input:
                value = await self._prompt_for_text(q, best_text)
                if value:
                    self._learn(q, value)
                    tag = 'prompted'
                    stats['prompted'] += 1
            if value is None or value == '':
                value = best_text or 'NA'
                tag = 'guess'
            await self._fill_text(state['text_el'], value)
            await self._finish(stats, q, value, tag,
                               review=(tag not in ('auto', 'llm_fallback')),
                               conf=(best.confidence if best and tag == 'auto' else 0.99 if tag == 'llm_fallback' else 0.0))
            return

        # ---------- Unknown widget ----------
        logger.warning(f"  No recognized input for: {q[:60]}")
        await self._answer_fallback(state, stats, reason='no-input')

    async def _finish(self, stats, question, answer, tag, review=False, conf=None):
        """Click Save to advance and record the answer."""
        sent = await self._click_send_button()
        stats['answered'] += 1
        if tag in ('guess', 'derived'):
            stats['guessed'] += (tag == 'guess')
        logger.info(f"✓ [{tag}] {question[:50]} → {str(answer)[:40]} (sent={sent})")
        if review or tag in ('guess', 'derived', 'fallback'):
            stats['review'].append({
                'question': question, 'answer': str(answer),
                'how': tag, 'confidence': round(conf, 3) if conf is not None else None,
            })

    async def _answer_fallback(self, state, stats, reason: str) -> None:
        """
        Unanswerable question: pick a safe option and move on (never block / skip the
        batch). Prefer a 'Skip' option if Naukri offers one, else the first option;
        for text, type a neutral value. Always logged for review.
        """
        options = state.get('options') or []
        q = state.get('question') or ''
        if options:
            skip = next((o for o in options if o[0].strip().lower() in ('skip', 'no')), None)
            choice = skip or options[0]
            await self._click_option(choice[1])
            await self._finish(stats, q, choice[0], 'fallback', review=True)
        elif state.get('text_el') is not None:
            await self._fill_text(state['text_el'], 'NA')
            await self._finish(stats, q, 'NA', 'fallback', review=True)
        else:
            # nothing to do; try to send anyway so we don't deadlock
            await self._click_send_button()
            stats['skipped'] += 1

    async def _click_option(self, clickable) -> bool:
        for attempt in ('click', 'force', 'js'):
            try:
                if attempt == 'click':
                    await clickable.click(timeout=4000)
                elif attempt == 'force':
                    await clickable.click(force=True)
                else:
                    await clickable.evaluate('el => el.click()')
                await asyncio.sleep(0.4)
                return True
            except Exception:
                continue
        logger.warning("  ⚠️  Could not click option")
        return False

    async def _click_option_by_text(self, text: str, options: list) -> bool:
        for t, el in options:
            if t.strip().lower() == text.strip().lower():
                return await self._click_option(el)
        return False

    async def _fill_text(self, text_el, value: str) -> bool:
        try:
            await text_el.click()
            await asyncio.sleep(0.2)
            try:
                await text_el.fill(str(value))
            except Exception:
                # contenteditable fallback: set text + fire input so Save enables
                await text_el.evaluate(
                    "(el, v) => { el.textContent = v; "
                    "el.dispatchEvent(new InputEvent('input', {bubbles: true})); }",
                    str(value),
                )
            await asyncio.sleep(0.3)
            return True
        except Exception as e:
            logger.warning(f"  ⚠️  Could not fill text: {e}")
            return False

    async def _prompt_for_option(self, question, options, suggestion: str = ''):
        opts = [t for t, _ in options]
        ans = (await asyncio.to_thread(
            input,
            f"\n❓ {question}\n   Options: {opts}\n"
            f"   Suggestion: {suggestion}\n   Type the option text (or Enter to skip): "
        )).strip()
        if not ans:
            return None
        pick = self._pick_best_chip(ans, options)
        return pick or (options[0] if options else None)

    async def _prompt_for_text(self, question, suggestion: str = ''):
        ans = (await asyncio.to_thread(
            input,
            f"\n❓ {question}\n   Suggestion: {suggestion}\n"
            f"   Type your answer (or Enter to accept suggestion): "
        )).strip()
        return ans or (suggestion or None)

    @staticmethod
    def _clean_answer(text: str) -> str:
        """
        Extract the answer value from a stored fact.

        The vector DB stores entries as ``"<question>?\\nA: <value>"``; filling the
        whole chunk into a chatbot text box is wrong, so keep only the value after
        the final ``A:`` marker. Plain answers pass through unchanged.
        """
        if not text:
            return ''
        t = text.strip()
        m = re.search(r'(?:^|\n)\s*A:\s*(.+)\Z', t, re.DOTALL)
        if m:
            t = m.group(1).strip()
        return t

    def _learn(self, question: str, answer: str) -> None:
        try:
            self.vector_db.store_answered_question(
                question, answer, category='learned_answers', tags=['naukri']
            )
        except Exception:
            pass

    def _write_review_log(self, path: str, review: list) -> None:
        try:
            import json
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(review, indent=2))
            logger.info(f"📝 {len(review)} answer(s) logged for review → {path}")
        except Exception as e:
            logger.debug(f"could not write review log: {e}")

    def _pick_best_chip(self, answer: str, chip_options: list):
        """
        Return the (text, element) tuple from chip_options that best matches
        the given answer, or None if no option scores above the minimum threshold.
        """
        answer_lower = answer.lower().strip()
        best = None
        best_score = 0.0

        for opt_text, opt_elem in chip_options:
            score = self._score_match(answer_lower, opt_text.lower().strip())
            if score > best_score:
                best_score = score
                best = (opt_text, opt_elem)

        return best if best_score > 0.15 else None

    def _score_match(self, answer: str, option: str) -> float:
        """
        Score how well *option* matches *answer* (0.0–1.0).

        Handles:
        - Exact matches
        - Numeric range matches  ("3 years" → "3-5 years", score 0.9)
        - "less than N" / "more than N" / "N+" patterns
        - Substring containment (penalised to avoid false positives)
        - Significant-word overlap
        """
        if answer == option:
            return 1.0

        # --- Numeric range matching ---
        ans_nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', answer)]
        if ans_nums:
            n = ans_nums[0]

            # Explicit "X-Y" or "X–Y" range in option
            m = re.search(r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)', option)
            if m and float(m.group(1)) <= n <= float(m.group(2)):
                return 0.9

            # "less than N"
            m = re.search(r'less\s+than\s+(\d+(?:\.\d+)?)', option)
            if m and n < float(m.group(1)):
                return 0.85

            # "more than N", "above N", "over N", or "N+"
            m = re.search(r'(?:more\s+than|above|over)\s+(\d+(?:\.\d+)?)', option)
            if not m:
                m = re.search(r'(\d+(?:\.\d+)?)\s*\+', option)
            if m and n > float(m.group(1)):
                return 0.85

            # Same number appears somewhere in the option
            opt_nums = re.findall(r'\d+(?:\.\d+)?', option)
            if any(abs(float(x) - n) < 0.01 for x in opt_nums):
                return 0.65

        # --- Substring containment ---
        if option in answer:
            # option fully contained in answer — fairly good signal
            ratio = len(option) / max(len(answer), 1)
            return min(0.8, 0.4 + 0.4 * ratio)

        if answer in option:
            # answer is a prefix/substring of a longer option — weaker signal
            return 0.4 * (len(answer) / max(len(option), 1))

        # --- Significant word overlap ---
        noise = {
            'year', 'years', 'month', 'months', 'day', 'days',
            'of', 'in', 'a', 'the', 'to', 'and', 'or', 'than', 'less', 'more',
        }
        a_words = set(re.findall(r'\w+', answer)) - noise
        o_words = set(re.findall(r'\w+', option)) - noise
        if a_words and o_words:
            common = a_words & o_words
            if common:
                return 0.4 * len(common) / max(len(a_words), len(o_words))

        return 0.0

    async def _click_apply_button(self) -> None:
        """Click the Apply button to open application form."""
        try:
            logger.info("Clicking Apply button...")
            apply_button = await self.page.query_selector(self.NAUKRI_SELECTORS['apply_button'])
            if apply_button and await apply_button.is_visible():
                await apply_button.click()
                await asyncio.sleep(3)  # Wait for form to appear
                logger.debug("Apply button clicked")
            else:
                logger.warning("Could not find Apply button")
        except Exception as e:
            logger.warning(f"Error clicking Apply button: {str(e)}")

    async def _close_nla_popups(self) -> None:
        """
        Close Naukri popups that might block form interaction.
        Specifically targets NLA (Next Level Automation) popups.
        """
        try:
            # First try to find and close NLA popups
            nla_popup = await self.page.query_selector(
                self.NAUKRI_SELECTORS['nla_popup']
            )
            
            if nla_popup and await nla_popup.is_visible():
                logger.debug("🔍 Detected NLA popup - closing...")
                
                # Try to find close button within or near the NLA popup
                close_buttons = [
                    self.NAUKRI_SELECTORS['nla_popup_close'],
                    'button[aria-label="Close"]',
                    'button[class*="close"]',
                ]
                
                for selector in close_buttons:
                    try:
                        element = await self.page.query_selector(selector)
                        if element and await element.is_visible():
                            logger.debug(f"Closing popup with selector: {selector}")
                            await element.click()
                            await asyncio.sleep(1)  # Wait for animation
                            return
                    except:
                        pass  # Selector not found, continue
                
                logger.warning("⚠️  NLA popup found but close button not found")
        
        except Exception as e:
            logger.debug(f"Error closing popups: {str(e)}")
    
    async def _extract_job_details(self) -> None:
        """Extract job title and company name from page."""
        try:
            # Get job title (required)
            job_title_elem = await self.page.query_selector(
                self.NAUKRI_SELECTORS['job_title_heading']
            )
            if job_title_elem:
                title_text = await job_title_elem.text_content()
                self.session.job_title = title_text.strip() if title_text else None
                logger.info(f"Job: {self.session.job_title}")
            else:
                logger.warning("⚠️  Job title heading not found (continuing anyway)")
            
            # Get company name (optional - don't fail if not found)
            try:
                company_elem = await self.page.query_selector(
                    self.NAUKRI_SELECTORS['company_name']
                )
                if company_elem:
                    company_text = await company_elem.text_content()
                    self.session.company_name = company_text.strip() if company_text else None
                    logger.info(f"Company: {self.session.company_name}")
                else:
                    logger.debug("Company name element not found (this is okay)")
            except Exception as e:
                logger.debug(f"Could not extract company name (optional): {str(e)}")
        
        except Exception as e:
            logger.warning(f"Error extracting job details: {str(e)}")
    
    async def _wait_for_form_load(self, timeout_ms: Optional[int] = None) -> None:
        """Wait for chatbot form container to be visible."""
        if timeout_ms is None:
            timeout_ms = self.FORM_LOAD_TIMEOUT
        try:
            await self.page.wait_for_selector(
                self.NAUKRI_SELECTORS['chatbot_form_container'],
                timeout=timeout_ms
            )
            logger.debug("Form container detected")
        
        except PlaywrightTimeoutError:
            logger.warning("Form container not found - proceeding anyway")
    
    async def _validate_form_fields(self) -> None:
        """
        Validate filled form fields before submission.
        Checks for:
        - Validation error messages
        - Required fields left empty
        - Disabled fields
        """
        try:
            logger.info("Validating form fields...")
            
            # Check for validation error messages
            error_elements = await self.page.query_selector_all(
                self.NAUKRI_SELECTORS['error_message']
            )
            
            if error_elements:
                error_count = len(error_elements)
                logger.warning(f"⚠️  Found {error_count} validation error(s) on form")
                
                for i, elem in enumerate(error_elements[:5], 1):  # Show first 5 errors
                    try:
                        error_text = await elem.text_content()
                        if error_text:
                            logger.warning(f"   Error {i}: {error_text.strip()}")
                    except:
                        pass
                
                if error_count > 5:
                    logger.warning(f"   ... and {error_count - 5} more error(s)")
            
            # Check for required fields
            required_fields = await self.page.query_selector_all(
                self.NAUKRI_SELECTORS['required_indicator']
            )
            
            if required_fields:
                logger.debug(f"Found {len(required_fields)} required field(s)")
                
                for i, field in enumerate(required_fields[:3], 1):  # Log first 3
                    try:
                        is_empty = await field.evaluate('''
                            elem => {
                                if (elem.tagName === "INPUT") return !elem.value;
                                if (elem.tagName === "SELECT") return !elem.value;
                                if (elem.tagName === "TEXTAREA") return !elem.value;
                                return false;
                            }
                        ''')
                        
                        if is_empty:
                            logger.warning(f"   ⚠️  Required field {i} appears empty")
                    except:
                        pass
        
        except Exception as e:
            logger.warning(f"Error validating form: {str(e)}")
    
    async def _submit_form(self) -> None:
        """
        Submit the filled form with improved error handling.
        Tries multiple strategies to find and click submit button.
        """
        try:
            logger.info("Preparing to submit form...")
            
            # Strategy 1: Try data-qa based selector first
            submit_button = await self.page.query_selector(
                '[data-qa="submit"], [data-qa="submitBtn"]'
            )
            
            # Strategy 2: Try type-based selector
            if not submit_button:
                submit_button = await self.page.query_selector('button[type="submit"]')
            
            # Strategy 3: Try text-based selector
            if not submit_button:
                submit_button = await self.page.query_selector('button:has-text("Submit"), button:has-text("Save and Apply"), button:has-text("Update and Apply")')
            
            if not submit_button:
                logger.info("Submit button not found. Checking for auto-submit success or failure messages...")
                await asyncio.sleep(2) # Wait for potential success message
                
                # Check for explicit failure
                failure_elem = await self.page.query_selector(':text("Oops! Your application was not accepted"), .apply-message:has-text("not accepted")')
                if failure_elem and await failure_elem.is_visible():
                    raise ValueError("Form auto-submitted but was REJECTED due to incomplete information.")
                
                # Check for explicit success
                success_elem = await self.page.query_selector('.apply-status-header.green, .apply-message:has-text("application was successful"), :text("Your application was successful"), :text("successfully"), :text("Application sent"), :text("applied successfully"), .success-msg')
                if success_elem and await success_elem.is_visible():
                    logger.info("✅ Success message detected. Form auto-submitted.")
                    return
                
                logger.warning("⚠️  Initiating MCP/Human Fallback for Submission.")
                prompt_text = (
                    f"\n🤖 MCP/HUMAN FALLBACK TRIGGERED\n"
                    f"❌ Issue: Submit button not found and no success message detected.\n"
                    f"👉 Action: Please manually click Submit in the browser (or use MCP tools), then press Enter to verify.\n"
                    f"   Press Enter when done: "
                )
                await asyncio.to_thread(input, prompt_text)
                
                # Re-check for success message
                success_elem = await self.page.query_selector('.apply-status-header.green, .apply-message:has-text("application was successful"), :text("Your application was successful"), :text("successfully"), :text("Application sent"), :text("applied successfully"), .success-msg')
                if success_elem and await success_elem.is_visible():
                    logger.info("✅ Success message detected after manual intervention.")
                    return
                
                raise ValueError("Submit button not found, and manual intervention did not produce a success message.")
            
            # Verify button is visible and enabled
            is_visible = await submit_button.is_visible()
            is_enabled = await submit_button.is_enabled()
            
            logger.info(f"Submit button state: Visible={is_visible}, Enabled={is_enabled}")
            
            if not is_visible:
                logger.warning("⚠️  Submit button not visible - scrolling into view")
                await submit_button.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
            
            if not is_enabled:
                logger.warning("⚠️  Submit button is disabled - cannot submit")
                raise ValueError("Submit button is disabled")
            
            logger.info("Clicking submit button...")
            await submit_button.click()
            
            # Wait for form submission to complete
            logger.info("Waiting for form submission...")
            try:
                await self.page.wait_for_navigation(timeout=10000)
                logger.info("✅ Form submitted successfully - navigation detected")
            except:
                # Navigation might not happen on some forms (AJAX submission)
                logger.info("Form clicked - monitoring for completion (no navigation detected)")
                await asyncio.sleep(3)
                
                # Post-submit verification
                failure_elem = await self.page.query_selector(':text("Oops! Your application was not accepted"), .apply-message:has-text("not accepted")')
                if failure_elem and await failure_elem.is_visible():
                    raise ValueError("Form submitted but was REJECTED due to incomplete information.")
                
                success_elem = await self.page.query_selector('.apply-status-header.green, .apply-message:has-text("application was successful"), :text("Your application was successful"), :text("successfully"), :text("Application sent"), :text("applied successfully"), .success-msg')
                if success_elem and await success_elem.is_visible():
                    logger.info("✅ Explicit success message detected after clicking submit.")
                else:
                    logger.info("⚠️ No explicit success message found, but proceeding assuming success.")
        
        except Exception as e:
            logger.error(f"Error submitting form: {str(e)}")
            raise
    
    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract job ID from Naukri URL."""
        # Naukri URLs typically: /jobs/123456789-job-title
        import re
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
    
    async def wait_for_side_panel_chatbot(self, timeout_ms: int = 30000) -> bool:
        """
        Wait for side panel chatbot to appear after bulk apply.
        
        Args:
            timeout_ms: Maximum time to wait in milliseconds
        
        Returns:
            True if panel found, False if timeout
        """
        try:
            logger.info("⏳ Waiting for side panel chatbot to appear...")
            await self.page.wait_for_selector(
                self.NAUKRI_SELECTORS['chatbot_form_container'],
                timeout=timeout_ms
            )
            logger.info("✅ Side panel chatbot detected")
            return True
        except PlaywrightTimeoutError:
            logger.warning(f"⚠️  Side panel did not appear within {timeout_ms}ms")
            return False
    
    async def detect_chatbot_questions_in_panel(self) -> List[Dict]:
        """
        Detect and extract questions from side panel chatbot.
        
        Returns:
            List of question Data dicts with:
            - question_text: The question string
            - answer_type: 'text', 'select', 'radio', 'checkbox'
            - options: List of options (empty for text inputs)
            - field_selector: CSS selector for answer input
            - is_required: Whether field is required
        """
        questions = []
        
        try:
            logger.info("🔍 Detecting questions in side panel...")
            
            # Get all form field containers in the panel
            field_containers = await self.page.query_selector_all(
                f"{self.NAUKRI_SELECTORS['chatbot_form_container']} .field-container, "
                f"{self.NAUKRI_SELECTORS['chatbot_form_container']} [data-qa*='field'], "
                f"{self.NAUKRI_SELECTORS['chatbot_form_container']} .form-group, "
                f"{self.NAUKRI_SELECTORS['chatbot_form_container']} .chatbot_MessageContainer"
            )

            logger.info(f"Found {len(field_containers)} field containers in panel")

            for idx, container in enumerate(field_containers, 1):
                try:
                    # Extract question text
                    question_text = ""
                    # Check for new chatbot structure first (last bot message)
                    bot_msgs = await container.query_selector_all('.botMsg span, .botMsg div')
                    if bot_msgs:
                        question_text = await bot_msgs[-1].text_content()
                    else:
                        label_elem = await container.query_selector('label, .question, [data-qa*="label"]')
                        if label_elem:
                            question_text = await label_elem.text_content()

                    question_text = question_text.strip() if question_text else ""

                    if not question_text:
                        continue  # Skip if no question found                    
                    logger.debug(f"  [{idx}] Question: {question_text[:60]}...")
                    
                    # Detect answer field type
                    answer_type = "text"
                    field_selector = None
                    options = []
                    
                    # Check for select
                    select_field = await container.query_selector('select')
                    if select_field:
                        answer_type = "select"
                        field_selector = f"select"
                        # Get options
                        option_elems = await select_field.query_selector_all('option')
                        options = [await opt.text_content() for opt in option_elems]
                        logger.debug(f"     Type: select | Options: {len(options)}")
                    
                    # Check for radio buttons
                    if not select_field:
                        radio_fields = await container.query_selector_all('input[type="radio"]')
                        if radio_fields:
                            answer_type = "radio"
                            field_selector = 'input[type="radio"]'
                            # Get labels for radio options
                            label_elems = await container.query_selector_all('label')
                            options = [await lbl.text_content() for lbl in label_elems]
                            logger.debug(f"     Type: radio | Options: {len(options)}")
                    
                    # Check for text input
                    if not select_field and not radio_fields:
                        text_input = await container.query_selector('input[type="text"], textarea, [contenteditable="true"]')
                        if text_input:
                            answer_type = "text"
                            field_selector = 'input[type="text"], textarea, [contenteditable="true"]'
                            logger.debug(f"     Type: text")
                    
                    # Check if required
                    is_required = bool(await container.query_selector('[required], [aria-required="true"]'))
                    
                    if field_selector or answer_type == "text":
                        questions.append({
                            'question_text': question_text,
                            'answer_type': answer_type,
                            'options': options,
                            'field_selector': field_selector,
                            'is_required': is_required
                        })
                
                except Exception as e:
                    logger.debug(f"Error processing field {idx}: {e}")
                    continue
            
            logger.info(f"✅ Detected {len(questions)} questions in side panel")
            return questions
        
        except Exception as e:
            logger.error(f"Error detecting questions in panel: {e}")
            return []
    
    async def fill_chatbot_form_for_job(
        self,
        job_title: str,
        questions: List[Dict],
        allow_human_input: bool = True
    ) -> Dict:
        """
        Fill chatbot form for a single job using vector DB answers.
        
        Args:
            job_title: Title of job being applied to
            questions: List of question dicts from detect_chatbot_questions_in_panel()
            allow_human_input: If True, prompt user for low-confidence answers
        
        Returns:
            Stats dict with: questions_answered, questions_prompted, questions_failed
        """
        stats = {
            'job_title': job_title,
            'questions_answered': 0,
            'questions_prompted': 0,
            'questions_failed': 0,
            'total_questions': len(questions)
        }
        
        try:
            logger.info(f"\n📝 Filling chatbot form for: {job_title}")
            logger.info(f"Questions to answer: {len(questions)}")
            
            for idx, question_data in enumerate(questions, 1):
                question_text = question_data['question_text']
                answer_type = question_data['answer_type']
                options = question_data['options']
                field_selector = question_data['field_selector']
                is_required = question_data['is_required']
                
                logger.info(f"\n  [{idx}/{len(questions)}] {question_text[:60]}...")
                
                # Get answer from vector DB
                answer, confidence, should_prompt = self.vector_db.get_answer_and_convert(
                    question=question_text,
                    answer_type=answer_type if answer_type != "text" else None,
                    options=options if options else None,
                    confidence_threshold=self.confidence_threshold
                )
                
                if not answer:
                    logger.warning(f"     ❌ No answer found")
                    stats['questions_failed'] += 1
                    continue
                
                logger.info(f"     Answer: {answer} (confidence: {confidence:.2f})")
                
                # If low confidence and human input allowed, prompt user
                if should_prompt and allow_human_input:
                    logger.info(f"     ⚠️  Low confidence ({confidence:.2f}) - asking user")
                    user_answer = await asyncio.to_thread(
                        input,
                        f"     📝 {question_text}\n        Suggested: {answer}\n        Your answer (or press Enter to accept): "
                    )
                    if user_answer.strip():
                        answer = user_answer.strip()
                    stats['questions_prompted'] += 1
                
                # Fill the field
                try:
                    if answer_type == "select":
                        await self._fill_select_field(field_selector, answer, options)
                    elif answer_type == "radio":
                        await self._fill_radio_field(field_selector, answer, options)
                    elif answer_type == "text":
                        await self._fill_text_field(field_selector, answer)
                    
                    stats['questions_answered'] += 1
                    logger.info(f"     ✅ Filled")
                
                except Exception as e:
                    logger.error(f"     ❌ Error filling: {e}")
                    stats['questions_failed'] += 1
                
                await asyncio.sleep(0.5)  # Small delay between fills
            
            logger.info(f"\n✅ Panel form complete: {stats['questions_answered']}/{len(questions)} answered")
            return stats
        
        except Exception as e:
            logger.error(f"Error filling chatbot form: {e}")
            return stats
    
    async def _fill_select_field(self, selector: str, answer: str, options: List[str]) -> None:
        """Fill a select/dropdown field."""
        try:
            select_elem = await self.page.query_selector(selector)
            if not select_elem:
                raise ValueError(f"Select field not found: {selector}")
            
            # Find matching option
            matching_option = None
            for option_text in options:
                if answer.lower() in option_text.lower() or option_text.lower() in answer.lower():
                    matching_option = option_text
                    break
            
            if not matching_option:
                matching_option = answer  # Try exact value
            
            await select_elem.select_option(matching_option)
            logger.debug(f"      Selected: {matching_option}")
        except Exception as e:
            logger.error(f"      Error filling select: {e}")
            raise
    
    async def _fill_radio_field(self, selector: str, answer: str, options: List[str]) -> None:
        """
        Fill a radio button field.
        
        Handles hidden/layered radio inputs by:
        1. First trying force=True click on the radio input
        2. Fallback: Find and click the associated label
        3. Fallback: Use JavaScript to trigger click
        """
        try:
            # Find matching radio button
            radio_buttons = await self.page.query_selector_all(selector)
            
            for radio in radio_buttons:
                # Get the associated label
                label = await radio.evaluate('el => el.nextElementSibling?.textContent || el.parentElement?.textContent || ""')
                
                if answer.lower() in label.lower() or label.lower() in answer.lower():
                    # Strategy 1: Try force=True click
                    try:
                        await radio.click(force=True)
                        logger.debug(f"      Selected radio (force=True): {label}")
                        await asyncio.sleep(0.5)
                        return
                    except Exception as e1:
                        logger.debug(f"      force=True click failed: {e1}, trying alternative methods...")
                        
                        # Strategy 2: Click associated label
                        try:
                            radio_id = await radio.get_attribute('id')
                            if radio_id:
                                label_elem = await self.page.query_selector(f'label[for="{radio_id}"]')
                                if label_elem:
                                    await label_elem.click()
                                    logger.debug(f"      Selected radio via label: {label}")
                                    await asyncio.sleep(0.5)
                                    return
                        except Exception as e2:
                            logger.debug(f"      Label click failed: {e2}")
                        
                        # Strategy 3: Use JavaScript to trigger click
                        try:
                            await radio.evaluate('el => el.click()')
                            logger.debug(f"      Selected radio (JavaScript click): {label}")
                            await asyncio.sleep(0.5)
                            return
                        except Exception as e3:
                            logger.debug(f"      JavaScript click failed: {e3}")
            
            # If no match found, try exact answer value
            for radio in radio_buttons:
                value = await radio.get_attribute('value')
                if value and value.lower() == answer.lower():
                    try:
                        await radio.click(force=True)
                        logger.debug(f"      Selected radio by value (force=True): {value}")
                        await asyncio.sleep(0.5)
                        return
                    except:
                        try:
                            await radio.evaluate('el => el.click()')
                            logger.debug(f"      Selected radio by value (JavaScript): {value}")
                            await asyncio.sleep(0.5)
                            return
                        except:
                            pass
            
            logger.warning(f"      Could not find radio option matching: {answer}")
        except Exception as e:
            logger.error(f"      Error filling radio: {e}")
            raise
    
    async def _fill_text_field(self, selector: str, answer: str) -> None:
        """Fill a text input field."""
        try:
            input_elem = await self.page.query_selector(selector)
            if not input_elem:
                raise ValueError(f"Text field not found: {selector}")
            
            await input_elem.fill(answer)
            logger.debug(f"      Filled text: {answer}")
        except Exception as e:
            logger.error(f"      Error filling text: {e}")
            raise
    
    async def click_chatbot_save_button(self) -> bool:
        """
        Find and click the Save/Next button in side panel chatbot to confirm this job and move to next.
        
        Handles both:
        - Standard button elements: <button>Save</button>
        - Naukri div buttons: <div id="sendMsg__..." class="send"><div class="sendMsg" tabindex="0">Save</div></div>
        
        Returns:
            True if button clicked, False if not found
        """
        try:
            logger.info("👆 Looking for Save button in panel...")
            
            # Wait a moment for button to be ready
            await asyncio.sleep(0.5)
            
            # Strategy 1: Try standard button elements with various selectors
            button_selectors = [
                'button[data-qa="save"]',
                'button[data-qa="next"]',
                'button[data-qa="submit"]',
                'button:has-text("Save")',
                'button:has-text("Next")',
                'button:has-text("Submit")',
                'button[type="submit"]',
            ]
            
            for selector in button_selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button:
                        is_visible = await button.is_visible()
                        is_enabled = await button.is_enabled()
                        
                        if is_visible and is_enabled:
                            logger.info(f"✅ Found button: {selector}")
                            await button.click()
                            await asyncio.sleep(2)  # Wait for next job to load in panel
                            logger.info("✅ Save button clicked")
                            return True
                except Exception as e:
                    logger.debug(f"Button selector failed: {selector} - {e}")
                    continue
            
            # Strategy 2: Try Naukri div-based send button
            # Pattern: <div id="sendMsg__..." class="send"><div class="sendMsg" tabindex="0">Save</div></div>
            logger.info("⏳ Trying Naukri div-based send button...")
            
            # Wait for disabled class to be removed (indicates form is ready)
            try:
                send_button_container = await self.page.query_selector('div.send:not(.disabled)')
                if send_button_container:
                    # Try clicking the inner sendMsg div
                    send_msg_div = await send_button_container.query_selector('.sendMsg')
                    if send_msg_div:
                        is_visible = await send_msg_div.is_visible()
                        if is_visible:
                            logger.info("✅ Found Naukri send button (div.send)")
                            # Click with force=True to ensure it works
                            await send_msg_div.click(force=True)
                            await asyncio.sleep(2)  # Wait for next job to load
                            logger.info("✅ Send button clicked")
                            return True
            except Exception as e:
                logger.debug(f"Naukri div-based button failed: {e}")
            
            # Strategy 3: Try to find any clickable element with "Save", "Next", or "Submit" text
            logger.info("⏳ Trying any clickable element with action text...")
            
            for action_text in ["Save", "Next", "Submit"]:
                try:
                    # Look for any element (not just buttons) with the text
                    elements = await self.page.query_selector_all(f':has-text("{action_text}")')
                    for elem in elements:
                        try:
                            is_visible = await elem.is_visible()
                            is_enabled = await elem.is_enabled()
                            
                            # Check if element is clickable (not disabled)
                            has_disabled_class = await elem.evaluate('el => el.classList.contains("disabled")')
                            
                            if is_visible and (is_enabled or not has_disabled_class):
                                logger.info(f"✅ Found clickable '{action_text}' element")
                                await elem.click(force=True)
                                await asyncio.sleep(2)
                                logger.info(f"✅ '{action_text}' clicked")
                                return True
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"Search for '{action_text}' failed: {e}")
                    continue
            
            logger.warning("⚠️  Save button not found with any strategy")
            return False
        except Exception as e:
            logger.error(f"Error clicking save button: {e}")
            return False


# Example usage for testing
async def example_usage():
    """Example of how to use NaukriFormFiller."""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        
        # Initialize vector DB
        vector_db = VectorDBManager(db_path="vector_db")
        
        # Initialize Naukri form filler
        naukri_filler = NaukriFormFiller(
            page=page,
            vector_db_manager=vector_db,
            confidence_threshold=0.70
        )
        
        # Fill a Naukri job application (example URL - replace with real)
        # job_url = "https://www.naukri.com/jobs/123456789-job-title"
        # session = await naukri_filler.fill_naukri_job_application(
        #     job_url=job_url,
        #     dry_run=True  # Just detect, don't fill
        # )
        
        # Get report
        # report = naukri_filler.get_session_report()
        # print(report)
        
        await context.close()
        await browser.close()


if __name__ == "__main__":
    # Run example if executed directly
    # asyncio.run(example_usage())
    print("NaukriFormFiller module loaded successfully")
