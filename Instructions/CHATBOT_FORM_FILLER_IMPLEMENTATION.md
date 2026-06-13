# Chatbot Form Filler - Implementation Guide & Code Templates

This guide provides concrete code examples, class signatures, and integration patterns.

---

## Table of Contents
1. [Core Module Structure](#core-module-structure)
2. [VectorDBManager Extension](#vectordbmanager-extension)
3. [ChatbotFormFiller Class](#chatbotformfiller-class)
4. [Question Detection Patterns](#question-detection-patterns)
5. [Answer Validation & Normalization](#answer-validation--normalization)
6. [MCP Tool Integration](#mcp-tool-integration)
7. [Naukri-Specific Adaptations](#naukri-specific-adaptations)
8. [Error Handling & Logging](#error-handling--logging)
9. [Test Cases Template](#test-cases-template)

---

## Core Module Structure

```
scripts/
├── common_stuff/
│   ├── vector_db_manager.py (EXTEND: add answer_question method)
│   ├── chatbot_form_filler.py (NEW: main form filler class)
│   └── answer_validators.py (NEW: validation rules per field type)
├── cookie_management_login/
│   └── naukri_form_filler.py (NEW: Naukri-specific adapter)
├── orchestrator/
│   └── mcp_server.py (EXTEND: add 3 new MCP tools)
└── tests/
    ├── test_chatbot_form_filler.py (NEW)
    ├── test_semantic_matching.py (NEW)
    ├── test_form_filling.py (NEW)
    └── test_naukri_e2e.py (NEW)
```

---

## VectorDBManager Extension

### Current Method
```python
def query_personal_profile(self, query, n_results=5):
    return self.search_personal_details(query, n_results=n_results)
```

### Extended Method (Add to VectorDBManager)

```python
import numpy as np
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class AnswerCandidate:
    """
    Represents a potential answer to a form question.
    """
    answer_text: str
    confidence: float  # 0.0 to 1.0 (semantic similarity)
    source_key: str  # e.g., 'salary_expected'
    source_category: str  # e.g., 'personal_details'
    should_autofill: bool
    reasoning: str = ""

class VectorDBManager:
    # ... existing code ...
    
    def answer_question(
        self, 
        question: str, 
        n_candidates: int = 5,
        confidence_threshold: float = 0.65
    ) -> Optional[AnswerCandidate]:
        """
        Find best answer in profile for a given question.
        
        Args:
            question: The form question text
            n_candidates: Top-N results to consider
            confidence_threshold: Min confidence to auto-fill (0.0-1.0)
        
        Returns:
            AnswerCandidate if found above threshold, else None
        """
        if not question or not question.strip():
            return None
        
        # Step 1: Semantic search
        results = self.search_personal_details(question, n_results=n_candidates)
        
        if not results['documents'] or len(results['documents']) == 0:
            return None
        
        # Step 2: Compute similarity scores
        question_embedding = self.model.encode([question])[0]
        document_embeddings = self.model.encode(results['documents'])
        
        similarities = []
        for doc_emb in document_embeddings:
            # Cosine similarity
            similarity = float(
                np.dot(question_embedding, doc_emb) / 
                (np.linalg.norm(question_embedding) * np.linalg.norm(doc_emb) + 1e-8)
            )
            # Convert from [-1, 1] to [0, 1] if using cosine with negatives
            similarity = (similarity + 1) / 2  # Normalize to [0, 1]
            similarities.append(similarity)
        
        # Step 3: Get best match
        best_idx = np.argmax(similarities)
        best_confidence = similarities[best_idx]
        best_document = results['documents'][best_idx]
        best_metadata = results['metadatas'][best_idx]
        
        # Step 4: Apply threshold
        should_autofill = best_confidence >= confidence_threshold
        
        # Step 5: Extract answer text (remove key prefix if present)
        answer_text = self._extract_answer_value(best_document)
        
        return AnswerCandidate(
            answer_text=answer_text,
            confidence=best_confidence,
            source_key=best_metadata.get('key', 'unknown'),
            source_category=best_metadata.get('category', 'personal_details'),
            should_autofill=should_autofill,
            reasoning=f"Semantic match: {best_document[:50]}..."
        )
    
    def answer_question_with_candidates(
        self, 
        question: str, 
        n_candidates: int = 3,
        confidence_threshold: float = 0.65
    ) -> List[AnswerCandidate]:
        """
        Return top-N answer candidates for a question.
        Useful for LLM to choose from when confidence is mixed.
        
        Returns:
            List[AnswerCandidate] sorted by confidence (descending)
        """
        results = self.search_personal_details(question, n_results=n_candidates)
        
        if not results['documents']:
            return []
        
        question_embedding = self.model.encode([question])[0]
        document_embeddings = self.model.encode(results['documents'])
        
        candidates = []
        for i, doc_emb in enumerate(document_embeddings):
            similarity = float(
                np.dot(question_embedding, doc_emb) / 
                (np.linalg.norm(question_embedding) * np.linalg.norm(doc_emb) + 1e-8)
            )
            similarity = (similarity + 1) / 2
            
            candidate = AnswerCandidate(
                answer_text=self._extract_answer_value(results['documents'][i]),
                confidence=similarity,
                source_key=results['metadatas'][i].get('key', 'unknown'),
                source_category=results['metadatas'][i].get('category', 'personal_details'),
                should_autofill=similarity >= confidence_threshold,
            )
            candidates.append(candidate)
        
        return sorted(candidates, key=lambda x: x.confidence, reverse=True)
    
    def _extract_answer_value(self, document_text: str) -> str:
        """
        Extract the answer value from document text.
        
        Example:
            "salary_expected: 12-15 LPA" → "12-15 LPA"
            "location: Remote" → "Remote"
        """
        if ':' in document_text:
            return document_text.split(':', 1)[1].strip()
        return document_text.strip()
    
    def store_answered_question(
        self, 
        question: str, 
        answer: str,
        category: str = 'answered_questions',
        tags: list = None
    ) -> dict:
        """
        Store a user-provided answer for learning.
        
        Example:
            store_answered_question(
                "What's your notice period?",
                "30 days",
                tags=['naukri', 'work_preferences']
            )
        """
        # Create a synthetic key from question
        key = f"q_{len(self.collection.get()['ids'])}"
        
        return self.add_or_update_detail(
            key=key,
            value=f"Q: {question} → A: {answer}",
            category=category
        )
```

---

## ChatbotFormFiller Class

### File: `scripts/common_stuff/chatbot_form_filler.py`

```python
import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from playwright.async_api import Page
from .vector_db_manager import VectorDBManager, AnswerCandidate

logger = logging.getLogger(__name__)

class FieldType(Enum):
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

@dataclass
class FormFillingResult:
    """Result of auto-filling a question."""
    question: str
    answer: str
    status: str  # 'filled' | 'skipped' | 'failed'
    confidence: float
    error_message: Optional[str] = None
    timestamp: Optional[str] = None

@dataclass
class ChatbotFormFillerStats:
    """Statistics for form filling session."""
    total_questions: int = 0
    auto_filled: int = 0
    skipped: int = 0
    failed: int = 0
    details: List[FormFillingResult] = field(default_factory=list)


class ChatbotFormFiller:
    """
    Intelligent chatbot form filler using semantic matching.
    
    Features:
    - Auto-detects form questions from page HTML
    - Queries vector DB for relevant answers
    - Validates & fills form fields with high confidence answers
    - Logs all actions for auditing
    - Supports fallback to LLM for low-confidence questions
    """
    
    # CSS selectors for form fields
    FORM_FIELD_SELECTORS = {
        'text_input': 'input[type="text"], input:not([type])',
        'email_input': 'input[type="email"]',
        'number_input': 'input[type="number"]',
        'select': 'select, [role="listbox"]',
        'radio': 'input[type="radio"]',
        'checkbox': 'input[type="checkbox"]',
        'textarea': 'textarea',
        'date_input': 'input[type="date"]',
    }
    
    # Timeout for waiting for form elements
    ELEMENT_TIMEOUT = 10000  # 10 seconds
    
    def __init__(
        self, 
        page: Page, 
        vector_db_manager: VectorDBManager,
        default_confidence_threshold: float = 0.65,
        enable_logging: bool = True
    ):
        """
        Initialize the form filler.
        
        Args:
            page: Playwright page object
            vector_db_manager: VectorDBManager instance
            default_confidence_threshold: Min confidence for auto-fill (0.0-1.0)
            enable_logging: Whether to log all actions
        """
        self.page = page
        self.vector_db = vector_db_manager
        self.confidence_threshold = default_confidence_threshold
        self.enable_logging = enable_logging
        
        if enable_logging:
            logger.setLevel(logging.DEBUG)
    
    async def auto_fill_chatbot_form(
        self,
        max_questions: Optional[int] = None,
        confidence_threshold: Optional[float] = None,
        dry_run: bool = False
    ) -> ChatbotFormFillerStats:
        """
        Main entry point: Detect and fill all form questions.
        
        Args:
            max_questions: Max questions to process (None = all)
            confidence_threshold: Override default threshold
            dry_run: If True, only detect without filling
        
        Returns:
            ChatbotFormFillerStats with results
        """
        threshold = confidence_threshold or self.confidence_threshold
        stats = ChatbotFormFillerStats()
        
        try:
            # Step 1: Detect questions
            logger.info("Starting form question detection...")
            questions = await self._detect_form_questions()
            logger.info(f"Detected {len(questions)} form questions")
            
            stats.total_questions = len(questions)
            if max_questions:
                questions = questions[:max_questions]
            
            if dry_run:
                logger.info("DRY RUN MODE: Not filling form, only detecting questions")
                for q in questions:
                    stats.details.append(FormFillingResult(
                        question=q.question_text,
                        answer="",
                        status="skipped",
                        confidence=0.0,
                        error_message="Dry run mode"
                    ))
                return stats
            
            # Step 2: Find answers for each question
            logger.info("Searching for answers in vector DB...")
            for question in questions:
                result = await self._process_question(
                    question, 
                    threshold
                )
                stats.details.append(result)
                
                if result.status == 'filled':
                    stats.auto_filled += 1
                elif result.status == 'skipped':
                    stats.skipped += 1
                else:  # failed
                    stats.failed += 1
            
            logger.info(f"Form filling complete: {stats.auto_filled} filled, "
                       f"{stats.skipped} skipped, {stats.failed} failed")
        
        except Exception as e:
            logger.error(f"Error during form filling: {str(e)}", exc_info=True)
            stats.failed += 1
        
        return stats
    
    async def _detect_form_questions(self) -> List[FormQuestion]:
        """
        Step 1: Detect all form questions on the page.
        Uses HTML parsing primarily, OCR fallback for complex forms.
        """
        questions = []
        
        try:
            # Strategy A: Find all form fields
            all_fields = await self.page.query_selector_all(
                'input, select, textarea, [role="combobox"], [role="radio"]'
            )
            
            logger.debug(f"Found {len(all_fields)} form fields")
            
            for field in all_fields:
                question = await self._extract_question_from_field(field)
                if question:
                    questions.append(question)
                    logger.debug(f"Detected question: {question.question_text}")
        
        except Exception as e:
            logger.error(f"Error detecting questions: {str(e)}")
        
        return questions
    
    async def _extract_question_from_field(self, field) -> Optional[FormQuestion]:
        """
        Extract question text, type, and metadata from a form field element.
        """
        try:
            # Get field attributes
            field_type_str = await field.get_attribute('type')
            field_id = await field.get_attribute('id')
            field_name = await field.get_attribute('name')
            placeholder = await field.get_attribute('placeholder')
            aria_label = await field.get_attribute('aria-label')
            required = await field.get_attribute('required')
            
            # Determine field type
            field_type = self._determine_field_type(field_type_str)
            
            # Find associated label
            label_text = None
            if field_id:
                label = await self.page.query_selector(f'label[for="{field_id}"]')
                if label:
                    label_text = await label.text_content()
            
            # Compose question text (priority: label > aria-label > placeholder)
            question_text = (
                label_text or aria_label or placeholder or field_id or field_name
            )
            
            if not question_text:
                logger.debug("Could not extract question text for field")
                return None
            
            # Clean question text
            question_text = question_text.strip()
            
            # Create selector
            selector = f'input#{field_id}' if field_id else 'input'
            
            return FormQuestion(
                question_text=question_text,
                field_selector=selector,
                field_type=field_type,
                is_required=required is not None,
                placeholder=placeholder,
                aria_label=aria_label,
                visible_label=label_text,
                field_name=field_name,
                field_id=field_id,
            )
        
        except Exception as e:
            logger.debug(f"Error extracting question: {str(e)}")
            return None
    
    def _determine_field_type(self, type_attr: Optional[str]) -> FieldType:
        """Determine field type from HTML attributes."""
        if not type_attr:
            return FieldType.TEXT_INPUT
        
        type_map = {
            'text': FieldType.TEXT_INPUT,
            'email': FieldType.EMAIL_INPUT,
            'number': FieldType.NUMBER_INPUT,
            'date': FieldType.DATE_INPUT,
            'radio': FieldType.RADIO,
            'checkbox': FieldType.CHECKBOX,
        }
        return type_map.get(type_attr, FieldType.UNKNOWN)
    
    async def _process_question(
        self, 
        question: FormQuestion, 
        confidence_threshold: float
    ) -> FormFillingResult:
        """
        Process a single question:
        1. Search vector DB for answer
        2. Validate answer
        3. Fill form field
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Step 1: Find answer in vector DB
            logger.debug(f"Finding answer for: {question.question_text}")
            answer_candidate = self.vector_db.answer_question(
                question.question_text,
                n_candidates=1,
                confidence_threshold=confidence_threshold
            )
            
            if not answer_candidate or not answer_candidate.should_autofill:
                logger.debug(
                    f"No answer found or below threshold for: {question.question_text}"
                )
                return FormFillingResult(
                    question=question.question_text,
                    answer="",
                    status="skipped",
                    confidence=answer_candidate.confidence if answer_candidate else 0.0,
                    error_message="Below confidence threshold or no match found"
                )
            
            # Step 2: Validate & normalize answer
            validated_answer = self._validate_and_normalize_answer(
                answer_candidate.answer_text,
                question.field_type
            )
            
            if not validated_answer:
                logger.warning(f"Failed to validate answer: {answer_candidate.answer_text}")
                return FormFillingResult(
                    question=question.question_text,
                    answer=answer_candidate.answer_text,
                    status="failed",
                    confidence=answer_candidate.confidence,
                    error_message="Answer validation failed"
                )
            
            # Step 3: Fill the form field
            fill_success = await self._fill_form_field(
                question,
                validated_answer
            )
            
            if not fill_success:
                logger.error(f"Failed to fill field: {question.field_selector}")
                return FormFillingResult(
                    question=question.question_text,
                    answer=validated_answer,
                    status="failed",
                    confidence=answer_candidate.confidence,
                    error_message="Could not fill form field"
                )
            
            logger.info(
                f"✓ Filled: {question.question_text} → {validated_answer} "
                f"(confidence: {answer_candidate.confidence:.2f})"
            )
            
            return FormFillingResult(
                question=question.question_text,
                answer=validated_answer,
                status="filled",
                confidence=answer_candidate.confidence,
            )
        
        except Exception as e:
            logger.error(f"Error processing question: {str(e)}")
            return FormFillingResult(
                question=question.question_text,
                answer="",
                status="failed",
                confidence=0.0,
                error_message=str(e)
            )
    
    def _validate_and_normalize_answer(
        self, 
        answer: str, 
        field_type: FieldType
    ) -> Optional[str]:
        """
        Validate and normalize answer based on field type.
        """
        if not answer or not answer.strip():
            return None
        
        answer = answer.strip()
        
        # Type-specific validation
        if field_type == FieldType.EMAIL_INPUT:
            if '@' not in answer:
                logger.warning(f"Invalid email format: {answer}")
                return None
        
        elif field_type == FieldType.NUMBER_INPUT:
            try:
                # Try to extract number
                import re
                match = re.search(r'\d+(?:\.\d+)?', answer)
                if match:
                    answer = match.group()
                else:
                    return None
            except Exception as e:
                logger.warning(f"Could not parse number: {answer}, {e}")
                return None
        
        elif field_type == FieldType.DATE_INPUT:
            # Try to format date (simplified)
            if len(answer) < 8:
                return None
        
        return answer
    
    async def _fill_form_field(
        self, 
        question: FormQuestion,
        answer: str
    ) -> bool:
        """
        Fill a form field with the answer.
        """
        try:
            await self.page.wait_for_selector(
                question.field_selector,
                timeout=self.ELEMENT_TIMEOUT
            )
            
            field = self.page.locator(question.field_selector)
            
            # Type-specific filling
            if question.field_type in [FieldType.TEXT_INPUT, FieldType.EMAIL_INPUT, FieldType.NUMBER_INPUT]:
                await field.fill(answer)
            
            elif question.field_type == FieldType.TEXTAREA:
                await field.fill(answer)
            
            elif question.field_type == FieldType.SELECT:
                await field.select_option(answer)
            
            elif question.field_type in [FieldType.RADIO, FieldType.CHECKBOX]:
                # Find option with matching text
                option = await self.page.query_selector(
                    f'{question.field_selector} + label:has-text("{answer}")'
                )
                if not option:
                    # Try by value
                    option = await self.page.query_selector(
                        f'{question.field_selector}[value="{answer}"]'
                    )
                if option:
                    await option.check()
            
            # Verify field was filled (for text input)
            if question.field_type in [FieldType.TEXT_INPUT, FieldType.EMAIL_INPUT, FieldType.NUMBER_INPUT]:
                current_value = await field.input_value()
                if current_value != answer:
                    logger.warning(
                        f"Field value mismatch: expected '{answer}', got '{current_value}'"
                    )
                    return False
            
            return True
        
        except Exception as e:
            logger.error(f"Error filling field: {str(e)}")
            return False
    
    async def get_answer_candidates_for_question(
        self,
        question_text: str,
        n_candidates: int = 3
    ) -> List[AnswerCandidate]:
        """
        Get top answer candidates for a question (for LLM to choose from).
        """
        return self.vector_db.answer_question_with_candidates(
            question_text,
            n_candidates=n_candidates
        )
```

---

## Question Detection Patterns

### Naukri-Specific Selectors

```python
# In scripts/cookie_management_login/naukri_login.py

NAUKRI_FORM_SELECTORS = {
    # Common Naukri patterns
    'question_text': [
        'label.nI-formLabel__label',
        'div.jobProfileForm--question',
        'p.nI-formLabel__label',
    ],
    'text_field': [
        'input[name*="responseText"]',
        'input.nI-formInput__textInput',
    ],
    'select_field': [
        'select[name*="response"]',
        'div[role="combobox"]',
    ],
    'radio_group': [
        'div.nI-formRadio__options',
        'div[role="radiogroup"]',
    ],
    'submit_button': [
        'button:has-text("Next")',
        'button:has-text("Proceed")',
        'button.nI-formButton',
    ],
}
```

### HTML Structure Examples

```html
<!-- Naukri Text Input Pattern -->
<div class="nI-formContainer__row">
    <label class="nI-formLabel__label">What is your expected salary?</label>
    <input type="text" name="responseText" class="nI-formInput__textInput" />
</div>

<!-- LinkedIn Select Pattern -->
<fieldset>
    <legend>Do you have authorization to work in [country]?</legend>
    <select name="work_authorization">
        <option>Select one</option>
        <option>Yes, I have authorization</option>
        <option>Need sponsorship</option>
    </select>
</fieldset>

<!-- InstaHyre Radio Pattern -->
<div role="radiogroup" aria-labelledby="q1">
    <span id="q1">Available to start?</span>
    <label>
        <input type="radio" name="availability" value="immediate" />
        Immediately
    </label>
    <label>
        <input type="radio" name="availability" value="notice" />
        With notice period
    </label>
</div>
```

---

## Answer Validation & Normalization

### File: `scripts/common_stuff/answer_validators.py`

```python
import re
from enum import Enum
from typing import Optional, Dict

class AnswerNormalizer:
    """Normalize answers based on expected format."""
    
    # Salary pattern: "12-15 LPA" or "12 LPA" or "1200000" or "12 lakhs"
    SALARY_PATTERNS = {
        'lpa': r'(\d+(?:\.\d+)?)\s*-?\s*(\d+(?:\.\d+)?)?\s*(?:lpa|lakhs|l)',
        'numeric': r'(\d+(?:,\d{3})*(?:\.\d+)?)',
    }
    
    # Location standardization
    LOCATION_ALIASES = {
        'bangalore': ['bengaluru', 'blr', 'bangalore'],
        'remote': ['wfh', 'work from home', 'hybrid'],
        'delhi': ['new delhi', 'delhi ncr', 'gurgaon', 'noida'],
    }
    
    # Notice period standardization
    NOTICE_PERIOD_PATTERNS = {
        'immediate': r'(0|immediate|now|asap)',
        '15 days': r'(15)',
        '30 days': r'(30)',
        '60 days': r'(60)',
        '90 days': r'(90)',
    }
    
    @staticmethod
    def normalize_salary(answer: str) -> Optional[str]:
        """Normalize salary answer."""
        if not answer:
            return None
        
        answer = answer.lower().strip()
        
        # Try LPA pattern first
        match = re.search(
            r'(\d+(?:\.\d+)?)\s*-?\s*(\d+(?:\.\d+)?)?\s*(?:lpa|lakhs|l)',
            answer
        )
        if match:
            lower = match.group(1)
            upper = match.group(2)
            if upper:
                return f"{lower}-{upper} LPA"
            return f"{lower} LPA"
        
        # Try numeric pattern
        match = re.search(r'(\d+(?:,\d{3})*)', answer)
        if match:
            return match.group(1)
        
        return answer


    @staticmethod
    def normalize_location(answer: str) -> Optional[str]:
        """Normalize location answer."""
        if not answer:
            return None
        
        answer = answer.strip()
        answer_lower = answer.lower()
        
        # Check aliases
        for standard, aliases in AnswerNormalizer.LOCATION_ALIASES.items():
            if answer_lower in aliases:
                return standard.title()
        
        return answer
    
    @staticmethod
    def normalize_notice_period(answer: str) -> Optional[str]:
        """Normalize notice period answer."""
        if not answer:
            return None
        
        answer_lower = re.sub(r'[^\w\s]', '', answer).lower()
        
        for standard_period, pattern in AnswerNormalizer.NOTICE_PERIOD_PATTERNS.items():
            if re.search(pattern, answer_lower):
                return standard_period
        
        return answer
```

---

## MCP Tool Integration

### File: `scripts/orchestrator/mcp_server.py` (NEW TOOLS)

```python
# Add these to existing mcp_server.py

from scripts.common_stuff.chatbot_form_filler import ChatbotFormFiller

@mcp.tool()
async def auto_fill_naukri_form(
    max_questions: int = None,
    confidence_threshold: float = 0.65,
    dry_run: bool = False
) -> str:
    """
    Automatically detect and fill chatbot form questions using user profile data.
    
    Args:
        max_questions: Max questions to process (None = all)
        confidence_threshold: Confidence threshold for auto-fill (0.65 is recommended)
        dry_run: If true, only detect without filling
    
    Returns:
        JSON with statistics: {
            total_questions: int,
            auto_filled: int,
            skipped: int,
            failed: int,
            details: [...]
        }
    """
    try:
        linkedin = await get_linkedin_session()
        vector_db = VectorDBManager()
        filler = ChatbotFormFiller(linkedin.page, vector_db)
        
        stats = await filler.auto_fill_chatbot_form(
            max_questions=max_questions,
            confidence_threshold=confidence_threshold,
            dry_run=dry_run
        )
        
        return json.dumps({
            'total_questions': stats.total_questions,
            'auto_filled': stats.auto_filled,
            'skipped': stats.skipped,
            'failed': stats.failed,
            'details': [
                {
                    'question': d.question,
                    'answer': d.answer,
                    'status': d.status,
                    'confidence': d.confidence,
                    'error': d.error_message
                }
                for d in stats.details
            ]
        }, indent=2)
    
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def get_answer_for_question(question: str, n_candidates: int = 3) -> str:
    """
    Semantically search for answer to a specific question.
    Useful for questions that don't meet auto-fill confidence threshold.
    
    Args:
        question: The question text
        n_candidates: Number of candidate answers to return
    
    Returns:
        JSON with top candidates and recommendation
    """
    try:
        vector_db = VectorDBManager()
        candidates = vector_db.answer_question_with_candidates(
            question,
            n_candidates=n_candidates
        )
        
        return json.dumps({
            'question': question,
            'candidates': [
                {
                    'answer': c.answer_text,
                    'confidence': c.confidence,
                    'source': c.source_key,
                    'should_use': c.should_autofill
                }
                for c in candidates
            ],
            'recommendation': candidates[0].answer_text if candidates else None
        }, indent=2)
    
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
async def answer_chatbot_question_manual(
    question: str,
    answer: str,
    category: str = 'answered_questions',
    store_for_future: bool = True
) -> str:
    """
    Manually answer a chatbot question and store in profile for future use.
    
    Args:
        question: The question text
        answer: Your answer
        category: Category for organization
        store_for_future: Whether to store in vector DB
    
    Returns:
        JSON with success status and stored key
    """
    try:
        vector_db = VectorDBManager()
        
        if store_for_future:
            result = vector_db.store_answered_question(
                question,
                answer,
                category=category
            )
            return json.dumps({
                'success': True,
                'message': f"Answer stored: {question} → {answer}",
                'stored_key': result.get('key'),
                'will_be_reused': True
            }, indent=2)
        else:
            return json.dumps({
                'success': True,
                'message': f"Answer recorded but not stored",
                'will_be_reused': False
            }, indent=2)
    
    except Exception as e:
        return f"Error: {str(e)}"
```

---

## Naukri-Specific Adaptations

### File: `scripts/cookie_management_login/naukri_form_filler.py`

```python
import asyncio
from playwright.async_api import Page
from ..common_stuff.chatbot_form_filler import ChatbotFormFiller
from ..common_stuff.vector_db_manager import VectorDBManager


class NaukriFormFiller(ChatbotFormFiller):
    """
    Naukri-specific form filler with custom selectors and logic.
    """
    
    # Naukri-specific confidence thresholds
    NAUKRI_THRESHOLDS = {
        'salary': 0.75,  # Higher threshold for salary
        'location': 0.70,
        'experience': 0.72,
        'default': 0.65,
    }
    
    def __init__(self, page: Page, vector_db_manager: VectorDBManager):
        super().__init__(page, vector_db_manager)
        self.portal_name = "Naukri"
    
    async def _detect_form_questions(self):
        """Override with Naukri-specific detection."""
        questions = []
        
        try:
            # Naukri uses specific structure
            elements = await self.page.query_selector_all(
                'div.nI-formContainer__row'
            )
            
            for element in elements:
                # Extract label
                label = await element.query_selector('label.nI-formLabel__label')
                if not label:
                    continue
                
                question_text = await label.text_content()
                
                # Find field
                field = await element.query_selector(
                    'input, select, textarea, [role="combobox"]'
                )
                
                if field:
                    # Create question object with Naukri context
                    question = await self._extract_question_from_field(field)
                    if question:
                        question.question_text = question_text.strip()
                        questions.append(question)
        
        except Exception as e:
            self.logger.error(f"Naukri-specific detection failed: {e}")
            # Fallback to generic detection
            questions = await super()._detect_form_questions()
        
        return questions
    
    async def _fill_form_field(self, question, answer):
        """Override with Naukri-specific filling logic."""
        try:
            # For Naukri, often need to click first to open
            field = self.page.locator(question.field_selector)
            await field.click()
            await asyncio.sleep(0.5)  # Brief wait for UI
            
            # Then fill
            return await super()._fill_form_field(question, answer)
        
        except Exception as e:
            self.logger.error(f"Naukri-specific filling failed: {e}")
            return False
    
    async def auto_fill_naukri_form(self, **kwargs):
        """Wrapper with Naukri-specific defaults."""
        kwargs.setdefault('confidence_threshold', 0.65)
        return await self.auto_fill_chatbot_form(**kwargs)
```

---

## Error Handling & Logging

### Logging Configuration

```python
# In scripts/common_stuff/chatbot_form_filler.py

import logging
import sys

def setup_form_filler_logging(log_file: str = None):
    """Setup logging for ChatbotFormFiller."""
    logger = logging.getLogger('chatbot_form_filler')
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    if log_file:
        file_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    return logger
```

### Error Handling Patterns

```python
class FormFillingError(Exception):
    """Base exception for form filling errors."""
    pass

class QuestionDetectionError(FormFillingError):
    """Exception during question detection."""
    pass

class AnswerNotFoundError(FormFillingError):
    """Exception when answer not found in vector DB."""
    pass

class FormFieldFillError(FormFillingError):
    """Exception during form field filling."""
    pass
```

---

## Test Cases Template

### File: `scripts/tests/test_chatbot_form_filler.py`

```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from playwright.async_api import Page
from pathlib import Path
import sys

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.common_stuff.chatbot_form_filler import (
    ChatbotFormFiller, FormQuestion, FieldType, FormFillingResult
)
from scripts.common_stuff.vector_db_manager import VectorDBManager


@pytest.fixture
def mock_page():
    """Mock Playwright Page."""
    return Mock(spec=Page)


@pytest.fixture
def mock_vector_db():
    """Mock VectorDBManager."""
    return Mock(spec=VectorDBManager)


@pytest.fixture
def form_filler(mock_page, mock_vector_db):
    """Form filler instance."""
    return ChatbotFormFiller(mock_page, mock_vector_db)


class TestQuestionDetection:
    """Test question detection from forms."""
    
    @pytest.mark.asyncio
    async def test_detect_text_input(self, form_filler):
        """Should detect text input field."""
        # Setup mock
        form_filler.page.query_selector_all = AsyncMock(
            return_value=[Mock()]
        )
        form_filler.page.query_selector = AsyncMock(return_value=None)
        
        # Mock getting field attributes
        field = form_filler.page.query_selector_all.return_value[0]
        field.get_attribute = AsyncMock(side_effect=mock_attributes)
        
        # Test
        questions = await form_filler._detect_form_questions()
        
        # Assert
        assert len(questions) > 0
        assert questions[0].field_type in [FieldType.TEXT_INPUT, FieldType.UNKNOWN]
    
    @pytest.mark.asyncio
    async def test_extract_question_text_from_label(self, form_filler):
        """Should prioritize label text over placeholder."""
        # ... test implementation
        pass


class TestSemanticMatching:
    """Test semantic matching and answer finding."""
    
    def test_answer_question_high_confidence(self, form_filler, mock_vector_db):
        """Should return answer when confidence is high."""
        # Setup
        from scripts.common_stuff.vector_db_manager import AnswerCandidate
        mock_vector_db.answer_question.return_value = AnswerCandidate(
            answer_text="12-15 LPA",
            confidence=0.85,
            source_key="salary_expected",
            source_category="personal_details",
            should_autofill=True
        )
        
        # Test
        result = form_filler.vector_db.answer_question("Expected salary?")
        
        # Assert
        assert result.should_autofill is True
        assert result.confidence >= 0.65
    
    def test_answer_question_low_confidence(self, form_filler, mock_vector_db):
        """Should skip answer when confidence is low."""
        from scripts.common_stuff.vector_db_manager import AnswerCandidate
        mock_vector_db.answer_question.return_value = AnswerCandidate(
            answer_text="Maybe",
            confidence=0.42,
            source_key="unknown",
            source_category="personal_details",
            should_autofill=False
        )
        
        result = form_filler.vector_db.answer_question("Feeling lucky?")
        
        assert result.should_autofill is False


class TestFormFilling:
    """Test form field filling with Playwright."""
    
    @pytest.mark.asyncio
    async def test_fill_text_input(self, form_filler):
        """Should fill text input field."""
        # Setup
        question = FormQuestion(
            question_text="Name",
            field_selector="input#name",
            field_type=FieldType.TEXT_INPUT,
            is_required=True
        )
        
        # Mock Playwright
        mock_field = AsyncMock()
        form_filler.page.wait_for_selector = AsyncMock()
        form_filler.page.locator = Mock(return_value=mock_field)
        mock_field.input_value = AsyncMock(return_value="John Doe")
        
        # Test
        result = await form_filler._fill_form_field(question, "John Doe")
        
        # Assert
        assert result is True
        mock_field.fill.assert_called_once_with("John Doe")
    
    @pytest.mark.asyncio
    async def test_fill_select_field(self, form_filler):
        """Should fill select dropdown."""
        question = FormQuestion(
            question_text="Country",
            field_selector="select#country",
            field_type=FieldType.SELECT,
            is_required=True
        )
        
        # Test...
        pass


class TestAnswerValidation:
    """Test answer validation and normalization."""
    
    def test_validate_salary(self, form_filler):
        """Should validate and normalize salary."""
        answer = form_filler._validate_and_normalize_answer(
            "12-15 LPA",
            FieldType.NUMBER_INPUT
        )
        assert answer is not None
    
    def test_validate_invalid_email(self, form_filler):
        """Should reject invalid email."""
        answer = form_filler._validate_and_normalize_answer(
            "notanemail",
            FieldType.EMAIL_INPUT
        )
        assert answer is None


@pytest.mark.asyncio
async def test_end_to_end_form_filling():
    """End-to-end test of full form filling process."""
    # This would be an integration test with real or sandbox forms
    pass


# Helper functions
async def mock_attributes(**kwargs):
    """Mock field attribute getter."""
    attr_map = {
        'type': 'text',
        'id': 'test-field',
        'name': 'test_field',
        'placeholder': 'Enter text',
        'aria-label': None,
        'required': None,
    }
    return attr_map.get(kwargs.get('attr_name'))
```

---

## Quick Reference: Files to Create/Modify

```
new: scripts/common_stuff/chatbot_form_filler.py (500 LOC)
new: scripts/common_stuff/answer_validators.py (150 LOC)
new: scripts/cookie_management_login/naukri_form_filler.py (200 LOC)
new: scripts/tests/test_chatbot_form_filler.py (300 LOC)
new: scripts/tests/test_semantic_matching.py (200 LOC)
new: scripts/tests/test_form_filling.py (200 LOC)
new: scripts/tests/test_naukri_e2e.py (200 LOC)
mod: scripts/common_stuff/vector_db_manager.py (+300 LOC)
mod: scripts/orchestrator/mcp_server.py (+150 LOC)
mod: scripts/orchestrator/orchestrator.py (integration)
doc: Instructions/MCP_TOOL_USAGE.md (NEW)
```

---

**Document Version:** 1.0  
**Last Updated:** April 17, 2026  
**Status:** Ready for Development
