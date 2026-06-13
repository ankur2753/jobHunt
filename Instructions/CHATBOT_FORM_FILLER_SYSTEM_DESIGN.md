# Chatbot Form Filler System - Design & Implementation Plan

**Date:** April 2026  
**Status:** Design Phase  
**Priority:** High (Naukri Chatbot Integration)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Technical Implementation](#technical-implementation)
4. [Component Design](#component-design)
5. [MCP Tool Specification](#mcp-tool-specification)
6. [Deliverables & Timeline](#deliverables--timeline)
7. [Dos & Donts](#dos--donts)
8. [Integration Points](#integration-points)
9. [Existing Solutions Review](#existing-solutions-review)
10. [Appendix: Prompt Templates](#appendix-prompt-templates)

---

## Executive Summary

### Problem Statement
Naukri job applications involve answering chatbot questions (security questions, work preferences, availability, etc.). Currently, these are manually filled, creating a bottleneck in automation.

### Proposed Solution
**Chatbot Form Filler (CFF) System** - An intelligent form-answering module that:
- Detects questions on the page using HTML parsing & OCR (as fallback)
- Semantically matches questions to user's vector DB profile using sentence transformers
- Extracts context-aware answers (e.g., "What's your expected salary?" → retrieves from vector DB)
- Exposes intelligent form-filling as an **MCP tool** for LLM agents to invoke

### Why This Approach?
✅ Leverages existing sentence-transformers investment  
✅ Reuses vector DB infrastructure  
✅ Semantic matching handles paraphrased questions  
✅ MCP tool allows LLM fallback if confidence is low  
✅ Scalable to other portals (LinkedIn, InstaHyre)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Playwright)                     │
│                    (Naukri/LinkedIn Page)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   Question Detection Layer      │
        │  (HTML Parse + OCR Fallback)    │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   Semantic Matching Engine      │
        │  (Sentence Transformer STS)     │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │    Vector DB: User Profile      │
        │   (ChromaDB + Embeddings)       │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │  Answer Extraction & Ranking    │
        │ (Confidence Score + Validation) │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │   Form Filling & Validation     │
        │  (Playwright Fill + Click)      │
        └────────────────┬────────────────┘
                         │
        ┌────────────────▼────────────────┐
        │     MCP Tool Interface          │
        │  (For LLM Fallback & Logging)   │
        └─────────────────────────────────┘
```

---

## Technical Implementation

### 1. Question Detection (Layer 1)

**Input:** Playwright Page object  
**Output:** List of `{question_text: str, field_selector: str, field_type: str}`

#### Strategy A: HTML-Based Detection (Primary - 95% of cases)
```python
question_patterns = {
    'input': 'input[placeholder], input[aria-label], input[data-test*="input"]',
    'select': 'select, [role="combobox"]',
    'radio': 'input[type="radio"]',
    'checkbox': 'input[type="checkbox"]',
    'textarea': 'textarea'
}
```

**Detection Logic:**
1. Find all form fields
2. Extract labels/placeholders/aria-labels (question text)
3. Map field → question → selector

#### Strategy B: OCR-Based Detection (Fallback - 5% complex forms)
```python
# If HTML parsing fails, use Playwright screenshot + pytesseract
screenshot → OCR → extract text → segment into Q&A pairs
```

**Recommended:** Don't implement OCR initially; start with HTML parsing. Add later if Naukri uses dynamic forms.

---

### 2. Semantic Matching Engine (Layer 2)

**Input:** Question text + User's vector DB  
**Output:** Top-N answer candidates with confidence scores

#### Algorithm
```
1. Encode question using SentenceTransformer('all-MiniLM-L6-v2')
2. Query ChromaDB for top-k relevant documents (k=10)
3. Re-rank results by:
   - Semantic similarity score (0-1)
   - Metadata relevance (key type, category)
   - Recency (if timestamp available)
4. Extract top result with confidence threshold (default: 0.65)
```

#### Example Matches
| Question | Vector DB Match | Confidence | Action |
|----------|-----------------|------------|--------|
| "Expected salary?" | "salary_expected: 12-15 LPA" | 0.92 | ✅ Autofill |
| "Work preference?" | "location: Remote, Bangalore" | 0.88 | ✅ Autofill |
| "Years of experience?" | "experience: 5.2 years" | 0.75 | ✅ Autofill |
| "Favorite tech stack?" | "skills: Python, React" | 0.62 | ⚠️ Show LLM |
| "Why do you want this job?" | (no match) | 0.31 | ❌ Pass to LLM |

---

### 3. Answer Extraction & Ranking (Layer 3)

**Input:** Top semantic matches  
**Output:** `{answer: str, confidence: float, source_key: str, should_autofill: bool}`

#### Logic
```python
def extract_answer(question, matched_docs, confidence_threshold=0.65):
    """
    1. Get top match from semantic search
    2. Apply confidence filter
    3. Validate answer format (optional normalization)
    4. Return with metadata
    """
    if matched_docs[0].confidence < confidence_threshold:
        return {
            'answer': None,
            'confidence': matched_docs[0].confidence,
            'should_autofill': False,
            'requires_llm': True
        }
    
    answer_text = matched_docs[0].document
    normalized_answer = normalize_answer(answer_text, field_type)
    
    return {
        'answer': normalized_answer,
        'confidence': matched_docs[0].confidence,
        'source_key': matched_docs[0].metadata['key'],
        'should_autofill': True
    }
```

#### Answer Normalization Examples
```
"salary_expected: 12-15 LPA" → Extract number → "12-15" (for numeric dropdown)
"location: Remote, Bangalore" → Map to closest option → "Remote" (for select)
"java, python, react" → Select most relevant → "Java" (for ranking)
```

---

## Component Design

### New Module: `scripts/common_stuff/chatbot_form_filler.py`

```python
class ChatbotFormFiller:
    """
    Autonomous chatbot form-filling system for job application portals.
    Detects questions, semantically matches to user profile, and fills forms.
    """
    
    def __init__(self, page: Page, vector_db_manager: VectorDBManager):
        self.page = page
        self.vector_db = vector_db_manager
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # Shared with VectorDB
        
    async def auto_fill_chatbot_form(self, max_questions=None) -> dict:
        """
        Main entry point. Detects and fills all form questions autonomously.
        
        Returns:
            {
                'total_questions': int,
                'auto_filled': int,
                'skipped': int,
                'failed': int,
                'details': [
                    {
                        'question': str,
                        'answer': str,
                        'confidence': float,
                        'status': 'filled' | 'skipped' | 'failed'
                    }
                ]
            }
        """
        pass
    
    async def detect_form_questions(self) -> List[FormQuestion]:
        """Step 1: Detect all questions on the page"""
        pass
    
    async def find_answer_in_profile(self, question: str) -> AnswerCandidate:
        """Step 2: Semantic search for answer in vector DB"""
        pass
    
    async def validate_and_fill_answer(self, question: FormQuestion, answer: AnswerCandidate) -> bool:
        """Step 3: Validate answer format and fill form field"""
        pass
```

### Data Models

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class FormQuestion:
    question_text: str
    field_selector: str
    field_type: str  # 'input', 'select', 'radio', 'checkbox', 'textarea'
    is_required: bool
    placeholder: Optional[str] = None
    aria_label: Optional[str] = None

@dataclass
class AnswerCandidate:
    answer_text: str
    confidence: float  # 0.0 to 1.0
    source_key: str  # From vector DB metadata
    should_autofill: bool  # Based on confidence threshold
    reasoning: Optional[str] = None  # For logging/debugging
```

---

## MCP Tool Specification

### Tool 1: `auto_fill_naukri_form`

**Purpose:** Autonomously detect and fill chatbot questions on Naukri forms  
**Confidence Threshold:** 0.65 (tunable)  
**Fallback:** If confidence < 0.65, returns question + top-3 candidates for LLM

```json
{
  "name": "auto_fill_naukri_form",
  "description": "Automatically detect and fill chatbot form questions using your profile data",
  "parameters": {
    "max_questions": {
      "type": "integer",
      "description": "Maximum questions to process (default: all)",
      "default": null
    },
    "confidence_threshold": {
      "type": "number",
      "description": "Confidence threshold for autofill (0.0-1.0, default: 0.65)",
      "default": 0.65
    },
    "dry_run": {
      "type": "boolean",
      "description": "If true, only detect without filling",
      "default": false
    }
  },
  "returns": {
    "type": "object",
    "properties": {
      "total_questions": "int",
      "auto_filled": "int",
      "skipped": "int | [questions that need manual LLM input]",
      "failed": "int",
      "details": [
        {
          "question": "str",
          "answer": "str | null",
          "confidence": "float",
          "status": "filled | skipped | failed"
        }
      ]
    }
  }
}
```

### Tool 2: `get_answer_for_question`

**Purpose:** Get answer candidates for a specific question (for LLM to choose from)  
**Use Case:** Questions with confidence < 0.65

```json
{
  "name": "get_answer_for_question",
  "description": "Semantically search profile for answer to a specific question",
  "parameters": {
    "question": "str (required) - The question asked by the chatbot",
    "n_candidates": "int (default: 3) - Top N answer candidates to return"
  },
  "returns": {
    "candidates": [
      {
        "answer": "str",
        "confidence": "float",
        "source_key": "str (e.g., 'salary_expected')",
        "metadata": "object"
      }
    ],
    "recommendation": "str (LLM's recommendation based on semantic match)"
  }
}
```

### Tool 3: `answer_chatbot_question_manual`

**Purpose:** Manually provide answer for a question; updates vector DB  
**Use Case:** When LLM/user wants to teach the system

```json
{
  "name": "answer_chatbot_question_manual",
  "description": "Manually answer a chatbot question and store in profile DB",
  "parameters": {
    "question": "str - The question text",
    "answer": "str - Your answer",
    "category": "str (optional) - Category tag (e.g., 'work_preferences')",
    "store_for_future": "bool (default: true) - Store in vector DB for future use"
  },
  "returns": "{ success: bool, stored_key: str, message: str }"
}
```

---

## Deliverables & Timeline

### Phase 1: Core Module (Week 1)
**Deliverables:**
- [ ] `ChatbotFormFiller` class with question detection
- [ ] `detect_form_questions()` method (HTML parsing)
- [ ] Unit tests for question detection
- [ ] Test on Naukri login + sample form

**Files:**
- `scripts/common_stuff/chatbot_form_filler.py` (~300 LOC)
- `scripts/tests/test_chatbot_form_filler.py` (~150 LOC)

**Acceptance Criteria:**
- Detects questions with >90% accuracy on test forms
- Handles input, select, radio, checkbox, textarea

---

### Phase 2: Semantic Matching (Week 2)
**Deliverables:**
- [ ] Semantic matching engine with confidence scoring
- [ ] Answer extraction & normalization logic
- [ ] Integration with VectorDBManager
- [ ] Unit tests for matching accuracy

**Files:**
- `scripts/common_stuff/chatbot_form_filler.py` (updated)
- `scripts/tests/test_semantic_matching.py` (~200 LOC)

**Acceptance Criteria:**
- Achieves >80% precision on known Q&A pairs
- Confidence scores correlate with accuracy
- Handles salary, location, experience correctly

---

### Phase 3: Form Filling & Validation (Week 3)
**Deliverables:**
- [ ] Form field filling with Playwright
- [ ] Answer validation (format checking)
- [ ] Auto-submit logic for simple forms
- [ ] Error handling & edge cases

**Files:**
- `scripts/common_stuff/chatbot_form_filler.py` (updated)
- `scripts/tests/test_form_filling.py` (~150 LOC)

**Acceptance Criteria:**
- Successfully fills >95% of detected questions
- Handles errors gracefully (field not clickable, etc.)
- Logs all actions for debugging

---

### Phase 4: MCP Integration (Week 4)
**Deliverables:**
- [ ] MCP tools for auto-fill & manual answer
- [ ] Integration with `mcp_server.py`
- [ ] Logging & monitoring
- [ ] Documentation & examples

**Files:**
- `scripts/orchestrator/mcp_server.py` (updated)
- `Instructions/MCP_TOOL_USAGE.md` (examples)

**Acceptance Criteria:**
- Tools callable from Claude Desktop
- Proper error handling & logging
- Tested with Naukri forms end-to-end

---

### Phase 5: Naukri Chatbot Integration (Week 5)
**Deliverables:**
- [ ] Adapt form filler for Naukri chatbot flow
- [ ] Integration with `NaukriPlaywright` class
- [ ] E2E test: Full job application with chatbot
- [ ] Performance optimization (caching, parallel queries)

**Files:**
- `scripts/cookie_management_login/naukri_form_filler.py` (~200 LOC)
- `scripts/tests/test_naukri_e2e.py` (~200 LOC)

**Acceptance Criteria:**
- Handle Naukri's dynamic form rendering
- Answer >85% of questions without LLM fallback
- Complete form in <3 seconds avg

---

## Dos & Donts

### ✅ DO

1. **DO** leverage existing `SentenceTransformer('all-MiniLM-L6-v2')` - already in requirements
2. **DO** use confidence thresholds to control fallback to LLM (don't apply blindly)
3. **DO** cache embeddings in vector DB (avoid re-computing)
4. **DO** log all auto-fills for auditing & learning
5. **DO** normalize answers (extract numbers, handle synonyms)
6. **DO** handle timeout/retry for slow form loads
7. **DO** validate answers before filling (format matching)
8. **DO** test on multiple portals (LinkedIn, InstaHyre differences)
9. **DO** make confidence threshold configurable per portal
10. **DO** store failed questions back to vector DB for LLM review

### ❌ DONT

1. **DONT** use simple keyword matching - use semantic similarity only
2. **DONT** hardcode field selectors - parse HTML dynamically
3. **DONT** auto-fill if confidence < 0.60 - invite LLM decision
4. **DONT** ignore validation errors - log & alert user
5. **DONT** re-encode questions every run - cache embeddings
6. **DONT** fill required fields with empty/null values
7. **DONT** assume form structure across portals (standardize selectors per portal)
8. **DONT** skip error handling for browser timeouts
9. **DONT** modify vector DB without user approval (manual answers only)
10. **DONT** attempt complex form logic (tables, nested forms) - escalate to LLM

---

## Integration Points

### 1. With Naukri Job Application Flow
```python
# In scripts/cookie_management_login/naukri_login.py

async def apply_to_job_with_chatbot(self, job_url: str):
    """After clicking 'Apply' button on Naukri job"""
    await self.page.goto(job_url)
    
    # Initialize form filler
    filler = ChatbotFormFiller(self.page, vector_db)
    
    # Auto-fill detected questions
    result = await filler.auto_fill_chatbot_form(
        confidence_threshold=0.70  # Naukri: stricter threshold
    )
    
    # Handle unfilled questions
    if result['skipped'] > 0:
        print(f"⚠️ {result['skipped']} questions need manual review")
        # Could invoke LLM here for intelligent answers
    
    # Submit form
    await self.page.click("button:has-text('Submit')")
```

### 2. With Orchestrator
```python
# In scripts/orchestrator/orchestrator.py

elif choice == '2':
    print("Starting job application with chatbot form filling...")
    job_title = input("Job title: ")
    location = input("Location: ")
    
    # Use new form-filling system
    applicator = NaukriJobApplyWithChatbot(naukri_session.page)
    stats = await applicator.apply_multiple_jobs(job_title, location)
    print(f"Applied to {stats['total_applications']} jobs")
    print(f"Auto-filled: {stats['auto_filled_forms']}, Manual: {stats['manual_forms']}")
```

### 3. With MCP Server (LLM Interface)
```python
# Claude can now call these tools:

# Option A: Auto-fill
await mcp.call_tool("auto_fill_naukri_form", {"confidence_threshold": 0.65})

# Option B: Get smart answers
candidates = await mcp.call_tool("get_answer_for_question", 
    {"question": "What's your notice period?", "n_candidates": 3})

# Option C: Teach the system
await mcp.call_tool("answer_chatbot_question_manual", 
    {"question": "Preferred work environment", "answer": "Remote", "store_for_future": True})
```

---

## Existing Solutions Review

### 1. **Existing: VectorDBManager (`scripts/common_stuff/vector_db_manager.py`)**

**Strengths:**
✅ Already uses `SentenceTransformer` + ChromaDB  
✅ Normalizes keys (aliases: "expected salary" → "salary_expected")  
✅ Handles nested JSON flattening  
✅ Exposes query interface to MCP  

**Gap:**
❌ Only queries documents, doesn't answer specific questions  
❌ No confidence scoring or filtering  
❌ Not optimized for question-answering  

**How to Extend:**
- Wrap `query_personal_profile()` with confidence filtering
- Add `extract_best_answer(question, n_results=5)` method
- Return structured `AnswerCandidate` objects instead of raw docs

```python
# Add to VectorDBManager class:

def answer_question(self, question: str, confidence_threshold: float = 0.65):
    """
    Answer a question by finding most relevant profile data.
    Returns AnswerCandidate or None if below threshold.
    """
    results = self.search_personal_details(question, n_results=5)
    
    if not results['documents']:
        return None
    
    # Score based on semantic similarity
    question_embedding = self.model.encode([question])[0]
    result_embeddings = self.model.encode(results['documents'])
    
    similarities = [
        float(np.dot(question_embedding, emb) / 
              (np.linalg.norm(question_embedding) * np.linalg.norm(emb)))
        for emb in result_embeddings
    ]
    
    best_idx = np.argmax(similarities)
    confidence = similarities[best_idx]
    
    if confidence >= confidence_threshold:
        return AnswerCandidate(
            answer_text=results['documents'][best_idx],
            confidence=confidence,
            source_key=results['metadatas'][best_idx].get('key'),
            should_autofill=True
        )
    return None
```

---

### 2. **LinkedIn Job Apply (`scripts/job_scraping/linkedin_job_apply.py`)**

**Current State:**
```python
# Line 61: This is where the logic to fill the form will go.
# Currently just closes the modal
```

**Opportunity:**
✅ This is the IDEAL place to integrate form filler  
✅ Modal structure similar to Naukri  

**Implementation:**
```python
# In LinkedInJobApply class:

async def apply_to_jobs(self, job_title: str, location: str):
    # ... existing search logic ...
    
    for job_card in job_cards:
        await job_card.click()
        try:
            easy_apply_button = self.page.locator(self.selectors["easy_apply_button"]).first
            await easy_apply_button.click()
            
            modal = self.page.locator(self.selectors["modal"])
            if await modal.is_visible():
                # NEW: Use ChatbotFormFiller!
                filler = ChatbotFormFiller(self.page, vector_db)
                result = await filler.auto_fill_chatbot_form()
                
                # Click Next/Submit based on result
                if result['total_questions'] > 0 and result['auto_filled'] > 0:
                    await self.page.click(self.selectors["next_button"])
```

---

### 3. **Resume/Cover Letter Personalization (Existing)**

**Observation:**
- Folder: `scripts/personalize_resume_coverletter_msg/` (accessible but empty in scan)
- This likely uses LLM + vector DB to personalize content

**Synergy Opportunity:**
- Share the same `VectorDBManager` instance
- Use similar semantic matching for Q&A generation
- Could reuse `SentenceTransformer` embeddings

---

### 4. **Similar Open Source Solutions**

#### A. **Langchain + ChromaDB QA Chain**
```python
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Chroma

qa_chain = RetrievalQA.from_chain_type(
    llm=ChatOpenAI(),
    chain_type="stuff",
    retriever=Chroma(...).as_retriever()
)
```

**Why NOT use it:**
- Overkill for this use case (you don't need LLM for retrieval)
- Adds unnecessary dependency on ChatOpenAI
- Your solution is simpler: semantic matching + validation

**Why USE your approach:**
- Lower latency (no LLM calls for 80%+ of questions)
- Lower cost (pure semantic matching)
- Full control over confidence thresholds

---

#### B. **Haystack + Dense Passage Retrieval**
```python
from haystack.utils.auth import Secret
from haystack.document_stores import ChromaDocumentStore
from haystack.components.retrievers.chat_message_retriever import ChatMessageRetriever
```

**Why NOT use it:**
- Overkill for simple Q&A matching
- Adds heavy dependency
- Your minimal setup is faster

---

#### C. **Simple Sentence Similarity Wrapper (BEST MATCH)**

```python
# Similar to what you could build:

from sentence_transformers import SentenceTransformer, util

class ProfileQA:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.corpus_embeddings = {}  # Pre-computed
    
    def find_answer(self, question: str, threshold=0.5):
        q_emb = self.model.encode(question)
        scores = util.pytorch_cos_sim(q_emb, self.corpus_embeddings)
        # ...
```

**Why THIS is best:**
- Minimal dependencies (what you already have!)
- Full control over matching logic
- Perfect for your 3-layer architecture

---

## Appendix: Prompt Templates

### System Prompt for LLM (When Confidence < 0.65)

```
You are assisting with filling out a job application form. 
The user has a profile with the following information:

[User Profile Context from Vector DB]

The chatbot is asking:
"[QUESTION]"

Based on the user's profile above, what would be the most appropriate answer?

Provide:
1. Recommended answer (concise, form-appropriate)
2. Confidence (low/medium/high)
3. Reasoning

If you cannot determine a good answer from the profile, say "UNCLEAR" 
and ask the user directly.
```

### Example LLM Interaction

```
QUESTION: "What is your notice period?"

PROFILE CONTEXT:
- Category: work_preferences
- key: notice_period
- value: 30 days
- timestamp: 2026-03-15

YOUR RESPONSE:
✓ Recommended: "30 days"
✓ Confidence: HIGH
✓ Reasoning: Explicitly found in work preferences profile
```

---

### Fallback Prompt (No Profile Match)

```
I couldn't find a direct answer to this question in your profile:
"[QUESTION]"

Top 3 guesses based on your experience:
1. [Candidate 1] (confidence: 0.58)
2. [Candidate 2] (confidence: 0.42)
3. [Candidate 3] (confidence: 0.31)

Which one should I use, or would you like to provide a custom answer?
(Your answer will be saved for future applications)
```

---

## Quick Start: Implementation Order

### Week 1: Question Detection
```bash
# Create basic structure
touch scripts/common_stuff/chatbot_form_filler.py
touch scripts/tests/test_chatbot_form_filler.py

# Test on sample HTML
python -m pytest scripts/tests/test_chatbot_form_filler.py::test_question_detection
```

### Week 2: Semantic Matching
```bash
# Extend VectorDBManager with answer_question()
# Test matching accuracy
python -m pytest scripts/tests/test_semantic_matching.py
```

### Week 3: Form Filling
```bash
# Implement fill_form_field() with Playwright
# Test on actual Naukri sandbox environment
python -m pytest scripts/tests/test_form_filling.py -v
```

### Week 4: MCP Integration
```bash
# Add tools to mcp_server.py
# Test with Claude Desktop
claude-tools test scripts/orchestrator/mcp_server.py
```

### Week 5: E2E Testing
```bash
# Full end-to-end on Naukri
python scripts/orchestrator/orchestrator.py
# Select: 2. Apply on Naukri
# Verify: Auto-fills, skips, error logs
```

---

## Success Metrics

| Metric | Target | Current | Week 5 Goal |
|--------|---------|---------|------------|
| Questions Detected | >95% accuracy | N/A | ✅ |
| Auto-Fill Rate | >80% | 0% | ✅ |
| Confidence Avg | 0.75+ | N/A | ✅ |
| Form Completion Time | <5 sec/form | Manual: 3-5 min | 10x faster |
| Manual Overrides | <5% needed | N/A | ✅ |
| Zero False Positives | >99% | N/A | ✅ |

---

## Questions & Next Steps

1. **Confidence Threshold:** Should it vary by portal? (LinkedIn: 0.75, Naukri: 0.65)
2. **LLM Fallback:** When confidence < threshold, auto-invoke Claude or wait for user?
3. **Profile Completeness:** How to handle missing data? (e.g., no phone number in vector DB)
4. **Learning Loop:** Should skipped questions auto-update vector DB for future?
5. **Portal Customization:** How many portal-specific adaptations needed?

---

**Document Version:** 1.0  
**Last Updated:** April 17, 2026  
**Author:** Design Team  
**Status:** Ready for Implementation
