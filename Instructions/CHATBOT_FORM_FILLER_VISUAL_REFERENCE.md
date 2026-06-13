# Visual Architecture & Reference Guide

Quick visual reference for the Chatbot Form Filler System design.

---

## System Layers & Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 5: User Interface                      │
│  Claude Desktop / Orchestrator / Browser UI                     │
└──────────────────────┬──────────────────────────────────────────┘
                       │
       ┌───────────────▼─────────────────┐
       │  LAYER 4: MCP Tool Interface    │
       │  • auto_fill_naukri_form()      │
       │  • get_answer_for_question()    │
       │  • answer_chatbot_question_manual()  │
       └───────────────┬─────────────────┘
                       │
       ┌───────────────▼──────────────────────┐
       │  LAYER 3: Orchestration             │
       │  ChatbotFormFiller Class             │
       │  • auto_fill_chatbot_form()          │
       │  • _process_question()               │
       │  • Error handling & logging          │
       └───────────────┬──────────────────────┘
                       │
       ┌───┬───────────┼──────────┬───┐
       │   │           │          │   │
       ▼   ▼           ▼          ▼   ▼
    ┌──────────┐  ┌───────────┐  ┌──────────┐
    │ Question │  │ Semantic  │  │ Answer   │
    │Detection │  │ Matching  │  │Validation│
    │ (HTML)   │  │(STS)      │  │& Fill    │
    └──────────┘  └───────────┘  └──────────┘

       ┌───────────────▼──────────────────────┐
       │  LAYER 2: Vector DB Interface        │
       │  VectorDBManager (Extended)          │
       │  • answer_question()                 │
       │  • answer_question_with_candidates() │
       │  • store_answered_question()         │
       └───────────────┬──────────────────────┘
                       │
       ┌───────────────▼──────────────────────┐
       │  LAYER 1: Data & Models              │
       │  ChromaDB + Embeddings               │
       │  SentenceTransformer Model           │
       │  Personal Details Collection         │
       └──────────────────────────────────────┘
                       │
       ┌───────────────▼──────────────────────┐
       │  BROWSER LAYER: Playwright           │
       │  Form Detection & Filling            │
       │  Page Interaction                    │
       └──────────────────────────────────────┘
```

---

## Question Detection Logic

```
Form Page HTML
      │
      ▼
Query All Form Fields
├─ input[text, email, number]
├─ select
├─ radio
├─ checkbox
├─ textarea
      │
      ▼
For Each Field:
├─ Get HTML attributes (type, id, name, placeholder)
│
├─ Find Associated Label (Priority Order)
│  1. <label for="field_id">
│  2. aria-label
│  3. placeholder
│  4. field name
│
├─ Create FormQuestion Object
│  ├─ question_text (cleaned)
│  ├─ field_selector
│  ├─ field_type (detected)
│  ├─ is_required
│  └─ metadata
│
      │
      ▼
Return List[FormQuestion]
```

---

## Semantic Matching Algorithm

```
User Question (from form)
"What's your expected salary?"
      │
      ▼
Encode to Embedding (SentenceTransformer)
[0.142, -0.234, 0.891, ... 384D]
      │
      ▼
Query ChromaDB (Top-5)
      │
      ├─ "salary_expected: 12-15 LPA"    ← Similarity: 0.92
      ├─ "salary_current: 10-12 LPA"     ← Similarity: 0.78
      ├─ "location: Remote"               ← Similarity: 0.31
      ├─ "experience: 5.2 years"          ← Similarity: 0.28
      └─ "skills: Python, React"          ← Similarity: 0.15
      │
      ▼
Compute Cosine Similarity
      │
      ▼
Apply Confidence Threshold (default: 0.65)
      │
      ├─ 0.92 ≥ 0.65 ✅ → should_autofill = True
      └─ 0.78 ≥ 0.65 ✅ → should_autofill = True (alternate)
      │
      ▼
Return AnswerCandidate
{
  answer_text: "12-15 LPA",
  confidence: 0.92,
  source_key: "salary_expected",
  should_autofill: True
}
```

---

## Answer Validation & Normalization

```
Raw Answer from Vector DB
"salary_expected: 12-15 LPA"
      │
      ▼
Extract Value (remove key prefix)
"12-15 LPA"
      │
      ▼
Apply Field Type Specific Validation
      │
      ├─ TEXT: trim, check not empty
      │
      ├─ EMAIL: check @ symbol present
      │
      ├─ NUMBER: extract digits only (12-15 → 12-15)
      │
      ├─ DATE: validate format (YYYY-MM-DD)
      │
      ├─ SELECT/RADIO: check option exists
      │
      └─ SALARY (custom): normalize to "12-15 LPA" format
      │
      ▼
Normalized Answer
"12-15"  (for numeric select)
or
"12-15 LPA"  (for text field)
      │
      ▼
Return Validated Answer → Fill Form Field
```

---

## Form Filling Strategy

```
For Each FormQuestion:

1. Wait for Field
   await page.wait_for_selector(selector, timeout=10s)

2. Determine Field Type
   ├─ Text Input: page.fill()
   ├─ Email: page.fill() + validate @
   ├─ Number: page.fill() + regex extract
   ├─ Select: page.select_option()
   ├─ Radio: find label + click
   ├─ Checkbox: find + check()
   └─ Textarea: page.fill()

3. Verify Fill (for text inputs)
   current_value = page.input_value()
   assert current_value == expected_answer

4. Return Result
   ├─ status: "filled" | "failed"
   ├─ confidence: 0.92
   └─ error_message: null || "Selector not found"
```

---

## Confidence Score Interpretation

```
Confidence Score → Action Mapping

┌─────────────┬──────────────┬─────────────────────────┐
│Confidence   │ Score Range  │ Action                  │
├─────────────┼──────────────┼─────────────────────────┤
│ Very High   │ 0.85 - 1.0   │ ✅ Auto-fill + log      │
│ High        │ 0.75 - 0.84  │ ✅ Auto-fill            │
│ Medium      │ 0.65 - 0.74  │ ✅ Auto-fill (default)  │
│ Low         │ 0.50 - 0.64  │ ⚠️  Flag for LLM       │
│ Very Low    │ < 0.50       │ ❌ Skip entirely        │
└─────────────┴──────────────┴─────────────────────────┘

Recommended Threshold by Portal:
├─ Naukri:    0.70 (stricter, more manual validation)
├─ LinkedIn:  0.65 (balanced)
└─ InstaHyre: 0.60 (more lenient)

Recommendation: Start with 0.65, tune based on real data
```

---

## State Machine: Form Filling Lifecycle

```
START
  │
  ├─ Detect Questions ────────────────────────┐
  │                                           │
  │ Total Questions detected: 10              │
  │                                           │
  └─ For Each Question:                      │
      │                                       │
      ├─ Query Vector DB                      │
      │  ├─ Not found → SKIPPED               │
      │  ├─ Confidence < 0.65 → SKIPPED       │
      │  └─ Found & High confidence           │
      │      │                                 │
      │      ├─ Validate Answer               │
      │      │  ├─ Invalid → FAILED           │
      │      │  └─ Valid                     │
      │      │      │                         │
      │      │      ├─ Fill Form Field       │
      │      │      │  ├─ Timeout → FAILED  │
      │      │      │  ├─ Not Found → FAILED│
      │      │      │  └─ Filled → Complete│
      │      │      │      │                 │
      │      │      ├─ Verify Fill           │
      │      │      │  ├─ Mismatch → FAILED │
      │      │      │  └─ Match → FILLED    │
      │
  ├─ Generate Stats:
  │  ├─ auto_filled: 8
  │  ├─ skipped: 1
  │  └─ failed: 1
  │
  ├─ Return ChatbotFormFillerStats
  │
  └─ END

Legend:
  FILLED  = Successfully filled + verified
  SKIPPED = No match or low confidence
  FAILED  = Validation/filling error
```

---

## Integration Timeline

```
Week 1          Week 2          Week 3          Week 4          Week 5
├────────────┼────────────┼────────────┼────────────┼────────────┤
│            │            │            │            │            │
│ Question   │ Semantic   │ Form       │ MCP        │ Production │
│ Detection  │ Matching   │ Filling    │ Tools      │ Ready      │
│            │            │            │            │            │
│ ✓ Detect   │ ✓ Match    │ ✓ Fill     │ ✓ Expose   │ ✓ E2E Test │
│ ✓ Parse    │ ✓ Score    │ ✓ Validate │ ✓ Logging  │ ✓ Optimize │
│ ✓ Test     │ ✓ Fallback │ ✓ Error Hn │ ✓ Docs     │ ✓ Live Data│
│            │            │            │            │            │
└────────────┴────────────┴────────────┴────────────┴────────────┘

Phase 1      Phase 2      Phase 3      Phase 4      Phase 5
Deliverable: Q Detection & Matching    Filling      Tools        Production
             2-3 days     2-3 days     2-3 days     1-2 days     2-3 days
             ~40 test     ~10 Q&A      1 real form  Claude       10 real jobs
             cases        pairs        working      Desktop       >80% auto-fill
```

---

## Data Model Relationships

```
FormQuestion
├─ question_text: str
├─ field_selector: str
├─ field_type: FieldType (enum)
├─ is_required: bool
├─ placeholder: str | null
├─ aria_label: str | null
├─ visible_label: str | null
├─ field_name: str | null
└─ field_id: str | null
      │
      └─ Used by: _process_question()
            │
            ▼
      AnswerCandidate
      ├─ answer_text: str
      ├─ confidence: float (0.0-1.0)
      ├─ source_key: str
      ├─ source_category: str
      ├─ should_autofill: bool
      └─ reasoning: str
            │
            └─ Used by: _fill_form_field()
                  │
                  ▼
            FormFillingResult
            ├─ question: str
            ├─ answer: str
            ├─ status: str ("filled"|"skipped"|"failed")
            ├─ confidence: float
            ├─ error_message: str | null
            └─ timestamp: str | null
                  │
                  └─ Collected in: ChatbotFormFillerStats
                        │
                        ├─ total_questions: int
                        ├─ auto_filled: int
                        ├─ skipped: int
                        ├─ failed: int
                        └─ details: List[FormFillingResult]
```

---

## Vector DB Query Pattern

```
Vector DB Schema (ChromaDB)

Collection: "personal_details"
├─ Documents:
│  ├─ "salary_expected: 12-15 LPA"
│  ├─ "salary_current: 10-12 LPA"
│  ├─ "location: Remote"
│  ├─ "location: Bangalore"
│  ├─ "experience: 5.2 years"
│  ├─ "skills: Python, React, Node.js"
│  └─ ... more flattened entries
│
├─ Embeddings:
│  ├─ [0.142, -0.234, 0.891, ...] ← for "salary_expected: 12-15 LPA"
│  ├─ [0.178, -0.201, 0.854, ...] ← for "salary_current: 10-12 LPA"
│  └─ ... more embeddings
│
├─ Metadatas:
│  ├─ {key: "salary_expected", category: "personal_details"}
│  ├─ {key: "salary_current", category: "personal_details"}
│  ├─ {key: "location", normalized_key: "location"}
│  └─ ... more metadata
│
└─ IDs:
   ├─ "personal_details_salary_expected_0"
   ├─ "personal_details_salary_current_1"
   └─ ... more IDs

Query Process:
Question: "What's your expected salary?"
      │
      ▼
Encode: [0.140, -0.236, 0.893, ...]  (STS)
      │
      ▼
ChromaDB.query(embeddings=..., n_results=5)
      │
      ▼
Returns: {
  documents: ["salary_expected: 12-15 LPA", ...],
  embeddings: [[0.142, ...], ...],
  metadatas: [{key: "salary_expected", ...}, ...],
  distances: [[0.08], [0.22], ...]  (converted to similarity)
}
      │
      ▼
Post-process: confidence = (1 - distance) = similarity score
```

---

## Error Handling Tree

```
ChatbotFormFiller.auto_fill_chatbot_form()
      │
      ├─ EXCEPTION: QuestionDetectionError
      │  └─ HANDLE: Log + return empty list
      │
      └─ For Each Question:
            │
            ├─ EXCEPTION: AnswerNotFoundError
            │  └─ HANDLE: Status = "skipped"
            │
            ├─ EXCEPTION: ValidationError
            │  └─ HANDLE: Status = "failed"
            │
            ├─ EXCEPTION: FormFieldFillError
            │  ├─ TIMEOUT → Retry once
            │  ├─ SELECTOR_NOT_FOUND → Status = "failed"
            │  ├─ NOT_CLICKABLE → Scroll & retry
            │  └─ OUTPUT MISMATCH → Status = "failed"
            │
            └─ SUCCESS → Status = "filled"

Return: ChatbotFormFillerStats with all results
```

---

## Naukri-Specific Adaptations

```
Generic ChatbotFormFiller
      │
      ▼
NaukriFormFiller (extends)
├─ NAUKRI_FORM_SELECTORS:
│  ├─ question_label: "label.nI-formLabel__label"
│  ├─ text_field: "input.nI-formInput__textInput"
│  ├─ select_field: "div[role='combobox']"
│  └─ submit_button: "button:has-text('Next')"
│
├─ confidence_threshold: 0.70 (stricter than generic 0.65)
│
├─ _detect_form_questions():
│  └─ Override with Naukri DOM parsing
│
├─ _fill_form_field():
│  ├─ Click field first (Naukri modal behavior)
│  ├─ Wait 500ms for UI to open
│  └─ Then fill with parent logic
│
└─ auto_fill_naukri_form(**kwargs):
   └─ Convenience wrapper with Naukri defaults
```

---

## MCP Tool Invocation Sequence

```
Claude User Query
│
├─ "Fill out the Naukri form"
│  │
│  ├─ Call: auto_fill_naukri_form()
│  │  ├─ Input: confidence_threshold=0.65
│  │  │
│  │  ├─ Process: Detect & fill all questions
│  │  │
│  │  └─ Output: {
│  │       total_questions: 15,
│  │       auto_filled: 12,
│  │       skipped: 2,
│  │       failed: 1,
│  │       details: [...]
│  │     }
│  │
│  ├─ If skipped > 0:
│  │  │
│  │  ├─ For each skipped question:
│  │  │  │
│  │  │  ├─ Call: get_answer_for_question(question)
│  │  │  │  ├─ Input: "What's your notice period?"
│  │  │  │  │
│  │  │  │  └─ Output: {
│  │  │  │       candidates: [
│  │  │  │         {answer: "30 days", confidence: 0.68},
│  │  │  │         {answer: "15 days", confidence: 0.42},
│  │  │  │         ...
│  │  │  │       ]
│  │  │  │     }
│  │  │  │
│  │  │  └─ Claude: "I recommend '30 days', is that correct?"
│  │  │
│  │  └─ If User Approves:
│  │     │
│  │     └─ Call: answer_chatbot_question_manual()
│  │        ├─ Input: question, answer, store_for_future=true
│  │        │
│  │        └─ Output: {
│  │             success: true,
│  │             stored_key: "q_123",
│  │             will_be_reused: true
│  │           }
│  │
│  └─ Summary: "Completed! 13/15 questions filled"
│
└─ END
```

---

## Performance Optimization Checklist

```
Before: ~8-10 seconds per form

Optimization Order   Impact      Implementation    Target
──────────────────   ──────      ──────────────    ──────
1. Batch encode      2-3x faster Encode all Qs    ~5 sec
   sentences         (50ms→20ms) at once

2. Cache embeddings  10% faster  Store in memory   ~4.5 sec
   per session                   during form fill

3. Parallel queries  15% faster  Use asyncio for   ~4 sec
                                multiple Qs

4. Selector caching  5% faster   Cache found       ~3.8 sec
                                elements

5. Skip OCR fallback 1% faster   Only use if HTML  ~3.7 sec
                                fails (rare)

FINAL TARGET: <5 seconds per form ✅
```

---

## Deployment Architecture

```
Local Development
└─ VectorDB (ChromaDB)
└─ Model (SentenceTransformer)
└─ Browser (Playwright)
└─ MCP Server (stdio)
└─ Claude Desktop

Production
└─ VectorDB (ChromaDB persisted)
└─ Model (SentenceTransformer cached)
└─ Browser Pool (multiple instances)
└─ MCP Server (cloud-hosted)
└─ Claude Integration (via API)
```

---

**Document Version:** 1.0  
**Last Updated:** April 17, 2026  
**Purpose:** Quick visual reference for implementation team
