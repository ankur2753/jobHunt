"""
Chatbot Form Filler - Intelligent form-answering module using semantic matching.

Features:
- Detects form questions from page HTML using CSS selectors
- Matches questions to user's vector DB profile using sentence-transformers
- Extracts context-aware answers with confidence scoring
- Validates and normalizes answers before filling
- Exposes intelligent form-filling as MCP tools for LLM agents
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

from playwright.async_api import Page
from .vector_db_manager import VectorDBManager, AnswerCandidate
from .answer_validators import sanitize_numeric_answer
from .retry_utils import dismiss_overlays_and_popups

logger = logging.getLogger(__name__)


class FieldType(Enum):
    """Enum for different form field types."""
    TEXT_INPUT = "text_input"
    NUMBER_INPUT = "number_input"
    EMAIL_INPUT = "email_input"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    TEXTAREA = "textarea"
    DATE_INPUT = "date_input"
    UNKNOWN = "unknown"


@dataclass
class FormQuestion:
    """Represents a form question detected on the page."""
    question_text: str
    field_selector: str
    field_type: FieldType
    is_required: bool
    placeholder: Optional[str] = None
    aria_label: Optional[str] = None
    visible_label: Optional[str] = None
    field_name: Optional[str] = None
    field_id: Optional[str] = None
    target_frame: Any = None
    
    def __str__(self):
        return self.question_text or f"Field: {self.field_name or self.field_id}"


@dataclass
class FormFillingResult:
    """Result of auto-filling a question."""
    question: str
    answer: Optional[str] = None
    status: str = "skipped"  # 'filled' | 'skipped' | 'failed' | 'manual_required'
    confidence: float = 0.0
    error_message: Optional[str] = None
    timestamp: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ChatbotFormFillerStats:
    """Statistics for form filling session."""
    total_questions: int = 0
    auto_filled: int = 0
    skipped: int = 0
    failed: int = 0
    manual_required: int = 0
    details: List[FormFillingResult] = field(default_factory=list)
    
    def add_result(self, result: FormFillingResult):
        """Add a result and update stats."""
        self.details.append(result)
        if result.status == "filled":
            self.auto_filled += 1
        elif result.status == "skipped":
            self.skipped += 1
        elif result.status == "failed":
            self.failed += 1
        elif result.status == "manual_required":
            self.manual_required += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'total_questions': self.total_questions,
            'auto_filled': self.auto_filled,
            'skipped': self.skipped,
            'failed': self.failed,
            'manual_required': self.manual_required,
            'auto_fill_rate': round(self.auto_filled / max(self.total_questions, 1), 2),
            'details': [
                {
                    'question': d.question[:50],
                    'status': d.status,
                    'confidence': round(d.confidence, 2),
                    'error': d.error_message
                }
                for d in self.details
            ]
        }


class ChatbotFormFiller:
    """
    Intelligent chatbot form filler using semantic matching.
    
    Workflow:
    1. Detect form questions from HTML
    2. Query vector DB for answers using semantic matching
    3. Validate and normalize answers
    4. Fill form fields with high-confidence answers
    5. Report stats and low-confidence questions for LLM review
    """
    
    # CSS selectors for form fields (HTML5 standard)
    FORM_FIELD_SELECTORS = {
        'text_input': 'input[type="text"], input:not([type])',
        'number_input': 'input[type="number"]',
        'email_input': 'input[type="email"]',
        'select_dropdown': 'select',
        'radio_button': 'input[type="radio"]',
        'checkbox': 'input[type="checkbox"]',
        'textarea': 'textarea',
        'date_input': 'input[type="date"]',
    }
    
    # Timeout for waiting for form elements
    ELEMENT_TIMEOUT = 10000  # 10 seconds

    def __init__(
        self,
        page: Page,
        vector_db: VectorDBManager,
        enable_logging: bool = True
    ):
        """
        Initialize the form filler.
        
        Args:
            page: Playwright page object
            vector_db: Vector DB manager instance
            enable_logging: Whether to enable detailed logging
        """
        self.page = page
        self.vector_db = vector_db
        self.enable_logging = enable_logging
        
        if enable_logging:
            setup_form_filler_logging()
            logger.info("ChatbotFormFiller initialized")

    async def auto_fill_chatbot_form(
        self,
        confidence_threshold: float = 0.65,
        max_questions: Optional[int] = None,
        dry_run: bool = False
    ) -> ChatbotFormFillerStats:
        """
        Main method: Auto-detect and fill all form questions.
        
        Args:
            confidence_threshold: Minimum confidence to auto-fill (0.0-1.0)
            max_questions: Max questions to process (None = all)
            dry_run: If True, don't actually fill; just report what would be filled
        
        Returns:
            ChatbotFormFillerStats with results for each question
        """
        try:
            # Step 0: Dismiss overlay popups & cookie banners before scanning form fields
            try:
                await dismiss_overlays_and_popups(self.page)
            except Exception as e:
                logger.debug(f"Dismiss overlays note: {e}")

            # Step 1: Detect all questions on the page
            logger.info("Detecting form questions...")
            questions = await self._detect_form_questions()
            
            if not questions:
                logger.warning("No form questions detected on page")
                stats = ChatbotFormFillerStats()
                stats.total_questions = 0
                return stats
            
            # Limit to max_questions if specified
            if max_questions:
                questions = questions[:max_questions]
            
            stats = ChatbotFormFillerStats()
            stats.total_questions = len(questions)
            
            logger.info(f"Found {len(questions)} form questions")
            
            # Step 2: Process each question
            for question in questions:
                try:
                    result = await self._process_question(
                        question,
                        confidence_threshold=confidence_threshold,
                        dry_run=dry_run
                    )
                    stats.add_result(result)
                    
                    if result.status == "filled":
                        logger.info(f"✅ Filled: {question.question_text[:50]}")
                    elif result.status == "manual_required":
                        logger.info(f"⚠️  Manual needed: {question.question_text[:50]}")
                    else:
                        logger.debug(f"⏭️  Skipped: {question.question_text[:50]}")
                        
                except Exception as e:
                    logger.error(f"Error processing question: {e}")
                    result = FormFillingResult(
                        question=question.question_text,
                        status="failed",
                        error_message=str(e)
                    )
                    stats.add_result(result)
            
            logger.info(f"Form filling complete: {stats.auto_filled} filled, "
                       f"{stats.manual_required} manual, {stats.skipped} skipped")
            
            return stats
            
        except Exception as e:
            logger.exception(f"Fatal error in auto_fill_chatbot_form: {e}")
            raise

    async def _detect_form_questions(self) -> List[FormQuestion]:
        """
        Detect all form questions from the page HTML.
        
        Strategy:
        1. Find all form fields
        2. Extract labels/placeholders/aria-labels (question text)
        3. Map field → question → selector
        
        Returns:
            List of FormQuestion objects
        """
        questions = []
        
        try:
            frames = self.page.frames if hasattr(self.page, "frames") and self.page.frames else [self.page]
            
            for target in frames:
                try:
                    # Strategy A: Find fields with associated labels (HTML best practice)
                    labels = await target.query_selector_all("label")
                    
                    for label in labels:
                        try:
                            label_text = await label.text_content()
                            if not label_text or len(label_text.strip()) < 3:
                                continue
                            
                            label_text = label_text.strip()
                            
                            # Method 1: for attribute pointing to input id
                            for_attr = await label.get_attribute("for")
                            if for_attr:
                                field = await target.query_selector(f'[id="{for_attr}"]')
                                if field:
                                    question = await self._extract_question_from_field(field, label_text, target_frame=target)
                                    if question:
                                        questions.append(question)
                                        continue
                            
                            # Method 2: Field is child of label
                            field = await label.query_selector("input, select, textarea")
                            if field:
                                question = await self._extract_question_from_field(field, label_text, target_frame=target)
                                if question:
                                    questions.append(question)
                                    continue
                        
                        except Exception as e:
                            logger.debug(f"Error processing label: {e}")
                            continue
                    
                    # Strategy B: Find fields with placeholders (no associated labels)
                    inputs_with_placeholder = await target.query_selector_all(
                        "input[placeholder], textarea[placeholder]"
                    )
                    
                    for field in inputs_with_placeholder:
                        try:
                            placeholder = await field.get_attribute("placeholder")
                            if placeholder and len(placeholder.strip()) >= 3:
                                question = await self._extract_question_from_field(field, placeholder, target_frame=target)
                                if question and question not in questions:
                                    questions.append(question)
                        except Exception as e:
                            logger.debug(f"Error processing field with placeholder: {e}")
                            continue
                    
                    # Strategy C: Find fields with aria-labels (accessibility)
                    inputs_with_aria = await target.query_selector_all(
                        "input[aria-label], select[aria-label], textarea[aria-label]"
                    )
                    
                    for field in inputs_with_aria:
                        try:
                            aria_label = await field.get_attribute("aria-label")
                            if aria_label and len(aria_label.strip()) >= 3:
                                question = await self._extract_question_from_field(field, aria_label, target_frame=target)
                                if question and question not in questions:
                                    questions.append(question)
                        except Exception as e:
                            logger.debug(f"Error processing field with aria-label: {e}")
                            continue

                    # Strategy D: Conversational UI / Chatbot Bubbles (Naukri style)
                    bot_messages = await target.query_selector_all(".botItem .botMsg span, .chatbot_ListItem .botMsg span")
                    if bot_messages:
                        try:
                            last_msg_text = None
                            for msg in reversed(bot_messages):
                                if await msg.is_visible():
                                    last_msg_text = await msg.text_content()
                                    break
                            
                            if last_msg_text and len(last_msg_text.strip()) >= 3:
                                active_fields = await target.query_selector_all("input:not([type='hidden']), textarea, select")
                                for field in active_fields:
                                    if await field.is_visible():
                                        question = await self._extract_question_from_field(field, last_msg_text.strip(), target_frame=target)
                                        if question:
                                            existing = next((q for q in questions if q.field_selector == question.field_selector), None)
                                            if existing:
                                                existing.question_text = last_msg_text.strip()
                                            else:
                                                questions.append(question)
                                        break
                        except Exception as e:
                            logger.debug(f"Error processing bot messages: {e}")

                    # Strategy E: Fallback scan for remaining visible form input, select, textarea elements
                    all_fields = await target.query_selector_all("input:not([type='hidden']), select, textarea")
                    for field in all_fields:
                        try:
                            if not await field.is_visible():
                                continue
                            
                            input_type = await field.get_attribute("type")
                            if input_type in ['submit', 'button', 'reset', 'file']:
                                continue
                                
                            field_id = await field.get_attribute("id") or ""
                            field_name = await field.get_attribute("name") or ""
                            
                            already_covered = any(
                                (q.field_name and q.field_name == field_name) or 
                                (q.field_id and q.field_id == field_id) or
                                q.field_selector in [field_id, field_name, f"#{field_id}", f"[name='{field_name}']"]
                                for q in questions
                            )
                            if already_covered:
                                continue

                            label_text = None
                            parent = await field.evaluate_handle("el => el.closest('.form-group, .field, div, p, tr')")
                            if parent:
                                parent_text = await parent.evaluate("el => el.innerText || el.textContent")
                                if parent_text:
                                    lines = [l.strip() for l in parent_text.split('\n') if l.strip()]
                                    if lines:
                                        label_text = lines[0]
                            
                            if not label_text or len(label_text) > 100:
                                raw_identifier = field_name or field_id
                                if raw_identifier:
                                    import re
                                    label_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', raw_identifier).replace('_', ' ').title()

                            if label_text and len(label_text.strip()) >= 2:
                                question = await self._extract_question_from_field(field, label_text.strip(), target_frame=target)
                                if question:
                                    questions.append(question)
                        except Exception as e:
                            logger.debug(f"Error in Strategy E fallback field scanning: {e}")
                            continue

                except Exception as frame_err:
                    logger.debug(f"Error processing frame {target}: {frame_err}")
            
            logger.info(f"Detected {len(questions)} form questions across frames")
            return questions
            
        except Exception as e:
            logger.error(f"Error detecting form questions: {e}")
            return []

    async def _extract_question_from_field(
        self,
        field,
        question_text: str,
        target_frame: Any = None
    ) -> Optional[FormQuestion]:
        """
        Extract question details from a form field.
        
        Args:
            field: Playwright element handle
            question_text: Question text (from label, placeholder, or aria-label)
            target_frame: Frame where field resides
        
        Returns:
            FormQuestion or None if invalid
        """
        try:
            # Enforce Visibility Check to Skip Hidden Form Fields & Popups
            if not await field.is_visible():
                logger.debug(f"Skipping non-visible field: {question_text}")
                return None

            # Get field selector
            field_selector = await field.evaluate("el => el.getAttribute('id') || el.getAttribute('name') || el.getAttribute('name')")
            
            # Get field type
            field_type = await field.evaluate("el => el.tagName.toLowerCase()")
            input_type = await field.get_attribute("type") if field_type == "input" else None
            
            # Determine field type enum
            field_type_enum = self._determine_field_type(input_type, field_type)
            
            # Get other attributes
            field_name = await field.get_attribute("name")
            field_id = await field.get_attribute("id")
            placeholder = await field.get_attribute("placeholder")
            aria_label = await field.get_attribute("aria-label")
            is_required = await field.evaluate("el => el.required || el.getAttribute('required') !== null")
            
            # Create FormQuestion
            return FormQuestion(
                question_text=question_text,
                field_selector=field_selector or field_name or field_id,
                field_type=field_type_enum,
                is_required=is_required,
                placeholder=placeholder,
                aria_label=aria_label,
                field_name=field_name,
                field_id=field_id,
                target_frame=target_frame
            )
            
        except Exception as e:
            logger.debug(f"Error extracting question from field: {e}")
            return None

    def _determine_field_type(self, input_type: Optional[str], tag_name: str) -> FieldType:
        """
        Determine field type from HTML attributes.
        
        Args:
            input_type: HTML input type attribute (e.g., 'text', 'email')
            tag_name: HTML tag name (e.g., 'input', 'select')
        
        Returns:
            FieldType enum value
        """
        if tag_name == "select":
            return FieldType.SELECT
        elif tag_name == "textarea":
            return FieldType.TEXTAREA
        elif tag_name == "input":
            type_map = {
                'text': FieldType.TEXT_INPUT,
                'number': FieldType.NUMBER_INPUT,
                'email': FieldType.EMAIL_INPUT,
                'radio': FieldType.RADIO,
                'checkbox': FieldType.CHECKBOX,
                'date': FieldType.DATE_INPUT,
            }
            return type_map.get(input_type, FieldType.TEXT_INPUT)
        else:
            return FieldType.UNKNOWN

    async def _process_question(
        self,
        question: FormQuestion,
        confidence_threshold: float,
        dry_run: bool = False
    ) -> FormFillingResult:
        """
        Process a single question: find answer and fill field.
        
        Args:
            question: FormQuestion to process
            confidence_threshold: Minimum confidence to auto-fill
            dry_run: If True, don't actually fill the field
        
        Returns:
            FormFillingResult with status and details
        """
        try:
            # Step 1: Query vector DB for answer
            candidate = self.vector_db.answer_question(
                question.question_text,
                confidence_threshold=confidence_threshold
            )
            
            answer_text = None
            confidence = 0.0
            
            if candidate:
                answer_text = candidate.answer_text
                confidence = candidate.confidence
            else:
                logger.info(f"🤖 Vector DB failed to confidently answer '{question.question_text}'. Falling back to agy LLM...")
                try:
                    import asyncio
                    import subprocess
                    import json
                    from pathlib import Path
                    
                    details_str = "{}"
                    details_path = Path("/home/ankurkumar/ankur_code/agent/personal_details/personal_details.json")
                    if details_path.exists():
                        with open(details_path, "r", encoding="utf-8") as f:
                            details_str = f.read()

                    is_cover_letter = "cover letter" in question.question_text.lower()
                    
                    if is_cover_letter:
                        prompt = (
                            f"You are an expert job application assistant. "
                            f"Here are my personal details:\n{details_str}\n\n"
                            f"The application asks for a '{question.question_text}'. "
                            f"Please write a highly professional, engaging, and tailored cover letter in raw text format. "
                            f"Do not include markdown or generic placeholders. Just the final text."
                        )
                    else:
                        prompt = (
                            f"You are an expert job application assistant. "
                            f"Here are my personal details:\n{details_str}\n\n"
                            f"Answer the following job application question concisely: '{question.question_text}'. "
                            f"Provide ONLY the answer text, no explanations, no markdown, just the raw string to fill in the form."
                        )
                    
                    result = await asyncio.to_thread(
                        subprocess.run,
                        ["agy", "--dangerously-skip-permissions", "--print", prompt],
                        cwd="/home/ankurkumar/ankur_code/agent",
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        # Extract the actual answer, ignoring potential agy login logs in stdout
                        lines = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
                        raw_ans = lines[-1] if lines else ""
                        
                        if raw_ans.startswith('"') and raw_ans.endswith('"'):
                            raw_ans = raw_ans[1:-1]
                        
                        answer_text = raw_ans
                        confidence = 1.0  # Trust LLM answer
                        logger.info(f"🤖 LLM Answer received: {answer_text}")
                        
                        # Update vector DB with new answer
                        self.vector_db.store_answered_question(
                            question.question_text, 
                            answer_text, 
                            category="learned_answers", 
                            tags=["agy_fallback"]
                        )
                        logger.info("🤖 Saved new answer to Vector DB for future use.")
                    else:
                        logger.warning(f"🤖 LLM Fallback failed. Output: {result.stderr}")
                except Exception as e:
                    logger.error(f"🤖 Error querying agy LLM: {e}")

            if not answer_text:
                return FormFillingResult(
                    question=question.question_text,
                    status="skipped",
                    confidence=0.0
                )
            
            # Step 2: Validate and normalize answer
            validated_answer = self._validate_and_normalize_answer(
                answer_text,
                question.field_type,
                question_text=question.question_text
            )
            
            if not validated_answer:
                return FormFillingResult(
                    question=question.question_text,
                    status="skipped",
                    confidence=confidence,
                    error_message="Answer validation failed"
                )
            
            # Step 3: Fill form field
            if not dry_run:
                success = await self._fill_form_field(question, validated_answer)
                if not success:
                    return FormFillingResult(
                        question=question.question_text,
                        answer=validated_answer,
                        status="failed",
                        confidence=confidence,
                        error_message="Failed to fill form field"
                    )
            
            return FormFillingResult(
                question=question.question_text,
                answer=validated_answer,
                status="filled",
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return FormFillingResult(
                question=question.question_text,
                status="failed",
                error_message=str(e)
            )

    def _validate_and_normalize_answer(
        self,
        answer: str,
        field_type: FieldType,
        question_text: str = ""
    ) -> Optional[str]:
        """
        Validate and normalize answer based on field type and question text context.
        
        Args:
            answer: Raw answer from vector DB
            field_type: Expected field type
            question_text: Question label or input description
        
        Returns:
            Normalized answer or None if validation fails
        """
        if not answer or len(answer.strip()) == 0:
            return None
        
        answer = answer.strip()
        q_lower = (question_text or "").lower()

        # Check if field requires numeric sanitization (Phone, Year, CTC, Notice Period, etc.)
        numeric_keywords = ['phone', 'mobile', 'contact', 'year', 'passing', 'graduation', 'batch', 'ctc', 'salary', 'package', 'notice', 'days']
        if field_type == FieldType.NUMBER_INPUT or any(k in q_lower for k in numeric_keywords):
            sanitized = sanitize_numeric_answer(answer, question_text)
            if sanitized:
                return sanitized
        
        # Type-specific validation
        if field_type == FieldType.EMAIL_INPUT:
            # Basic email validation
            if '@' in answer and '.' in answer:
                return answer
            else:
                logger.warning(f"Invalid email: {answer}")
                return None
        
        elif field_type == FieldType.NUMBER_INPUT:
            import re
            match = re.search(r'\d+(?:\.\d+)?', answer)
            if match:
                return match.group(0)
            else:
                logger.warning(f"No number found in: {answer}")
                return None
        
        elif field_type == FieldType.DATE_INPUT:
            import re
            match = re.search(r'\d{4}-\d{2}-\d{2}', answer)
            if match:
                return match.group(0)
            else:
                logger.warning(f"Invalid date format: {answer}")
                return None
        
        else:
            return answer

    async def _fill_form_field(
        self,
        question: FormQuestion,
        answer: str
    ) -> bool:
        """
        Fill a form field with the given answer using Playwright.
        
        Args:
            question: FormQuestion with field details
            answer: Answer to fill
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Strategy A: Check for custom chatbot chip buttons that match the answer
            # Naukri often presents multiple-choice options as buttons in the chat
            chip_buttons = await self.page.query_selector_all('.botMsg button, .msgWrap button, .chatbot_ListItem button, .nI-chat-container button:not([aria-label]), .chip')

            if chip_buttons:
                answer_lower = answer.lower().strip()
                best_chip = None
                best_score = 0.0
                for chip in chip_buttons:
                    if await chip.is_visible() and await chip.is_enabled():
                        chip_text = await chip.text_content()
                        if chip_text:
                            score = self._score_option_match(answer_lower, chip_text.lower().strip())
                            if score > best_score:
                                best_score = score
                                best_chip = chip
                if best_chip and best_score > 0.15:
                    chip_text = await best_chip.text_content()
                    await best_chip.click()
                    logger.debug(f"Clicked best-matching chip: '{chip_text.strip()}' (score={best_score:.2f})")
                    await asyncio.sleep(1.5)  # Wait for chatbot to process and load next bubble
                    return True

            # Find the field
            field_selector = question.field_selector
            
            if not field_selector:
                field_selector = 'input:not([type="hidden"]), textarea, select'
            
            # Backward compatibility for raw id/name
            if not any(c in field_selector for c in ['#', '[', ':', '.', ' ']):
                field_selector = f"#{field_selector}, [name='{field_selector}']"
                
            target = question.target_frame or self.page
            field = await target.query_selector(field_selector)

            if not field:
                logger.error(f"Could not find field: {field_selector}")
                return False
            
            # Fill based on field type
            if question.field_type in [FieldType.TEXT_INPUT, FieldType.NUMBER_INPUT, 
                                       FieldType.EMAIL_INPUT, FieldType.TEXTAREA]:
                await field.fill(answer)
                logger.debug(f"Filled text field with: {answer[:50]}")
                try:
                    await field.press('Enter')
                    await asyncio.sleep(1.5)  # Wait for chatbot to process and load next bubble
                except:
                    pass
                return True
            
            elif question.field_type == FieldType.SELECT:
                # Try selecting by label, value, or option text search
                try:
                    await field.select_option(label=answer)
                    logger.debug(f"Selected option by label: {answer}")
                    return True
                except Exception:
                    try:
                        await field.select_option(value=answer)
                        logger.debug(f"Selected option by value: {answer}")
                        return True
                    except Exception:
                        options = await field.query_selector_all("option")
                        for opt in options:
                            opt_text = (await opt.text_content() or "").strip()
                            opt_val = (await opt.get_attribute("value") or "").strip()
                            if answer.lower() in opt_text.lower() or answer.lower() in opt_val.lower() or opt_text.lower() in answer.lower():
                                try:
                                    if opt_val:
                                        await field.select_option(value=opt_val)
                                    else:
                                        await field.select_option(label=opt_text)
                                    logger.debug(f"Selected matched option: {opt_text}")
                                    return True
                                except Exception:
                                    pass
                return False
            
            elif question.field_type == FieldType.RADIO:
                name_attr = await field.get_attribute("name")
                if name_attr:
                    radios = await target.query_selector_all(f'input[type="radio"][name="{name_attr}"]')
                    for r in radios:
                        r_val = (await r.get_attribute("value") or "").strip().lower()
                        r_id = await r.get_attribute("id")
                        r_label = ""
                        if r_id:
                            lbl = await target.query_selector(f'label[for="{r_id}"]')
                            if lbl:
                                r_label = (await lbl.text_content() or "").strip().lower()
                        if not r_label:
                            p_txt = await r.evaluate("el => el.parentElement ? el.parentElement.textContent : ''")
                            r_label = (p_txt or "").strip().lower()
                        
                        if answer.lower() in r_val or answer.lower() in r_label or r_val in answer.lower() or (r_label and r_label in answer.lower()):
                            try:
                                await r.evaluate("el => el.click()")
                            except Exception:
                                await r.click(force=True)
                            logger.debug(f"Clicked matched radio: {answer}")
                            return True
                
                radio_value = await field.get_attribute("value")
                if radio_value and answer.lower() in radio_value.lower():
                    try:
                        await field.evaluate("el => el.click()")
                    except Exception:
                        await field.click(force=True)
                    logger.debug(f"Clicked radio: {answer}")
                    return True
                return False
            
            elif question.field_type == FieldType.CHECKBOX:
                # Check/uncheck based on answer
                should_check = answer.lower() in ['yes', 'true', '1', 'checked']
                is_checked = await field.is_checked()
                if should_check != is_checked:
                    await field.click()
                    logger.debug(f"Toggled checkbox: {answer}")
                return True
            
            elif question.field_type == FieldType.DATE_INPUT:
                await field.fill(answer)
                logger.debug(f"Filled date field: {answer}")
                return True
            
            else:
                logger.warning(f"Unknown field type: {question.field_type}")
                return False
            
        except Exception as e:
            logger.error(f"Error filling form field: {e}")
            return False

    def _score_option_match(self, answer: str, option: str) -> float:
        """
        Score how well *option* matches *answer* (0.0–1.0).

        Handles exact, numeric-range, substring, and word-overlap matching.
        Avoids the false-positive where a short answer like "1 year" is a
        substring of a longer option like "less than 1 year".
        """
        import re

        if answer == option:
            return 1.0

        # Numeric range matching — e.g. "3 years" → "3-5 years"
        ans_nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', answer)]
        if ans_nums:
            n = ans_nums[0]
            m = re.search(r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)', option)
            if m and float(m.group(1)) <= n <= float(m.group(2)):
                return 0.9
            m = re.search(r'less\s+than\s+(\d+(?:\.\d+)?)', option)
            if m and n < float(m.group(1)):
                return 0.85
            m = re.search(r'(?:more\s+than|above|over)\s+(\d+(?:\.\d+)?)', option)
            if not m:
                m = re.search(r'(\d+(?:\.\d+)?)\s*\+', option)
            if m and n > float(m.group(1)):
                return 0.85
            opt_nums = re.findall(r'\d+(?:\.\d+)?', option)
            if any(abs(float(x) - n) < 0.01 for x in opt_nums):
                return 0.65

        if option in answer:
            ratio = len(option) / max(len(answer), 1)
            return min(0.8, 0.4 + 0.4 * ratio)

        if answer in option:
            return 0.4 * (len(answer) / max(len(option), 1))

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

    async def get_answer_candidates_for_question(
        self,
        question: str,
        n_candidates: int = 3,
        confidence_threshold: float = 0.5
    ) -> List[AnswerCandidate]:
        """
        Get answer candidates for a question (for LLM to choose from).
        
        Args:
            question: Question text
            n_candidates: Number of candidates to return
            confidence_threshold: Minimum confidence score
        
        Returns:
            List of AnswerCandidate objects
        """
        return self.vector_db.answer_question_with_candidates(
            question,
            n_candidates=n_candidates,
            confidence_threshold=confidence_threshold
        )


def setup_form_filler_logging(log_level=logging.INFO, log_file: Optional[str] = None):
    """
    Setup logging for ChatbotFormFiller.
    
    Args:
        log_level: Logging level (e.g., logging.DEBUG, logging.INFO)
        log_file: Optional file to write logs to
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger("chatbot_form_filler")
    logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
