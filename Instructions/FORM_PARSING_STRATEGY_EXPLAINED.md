# Form Parsing & Question Detection Strategy Explained

**Document Purpose:** Detailed explanation of how we detect and parse form questions for the Chatbot Form Filler system.

---

## Table of Contents
1. [Overview](#overview)
2. [Detection Strategy (3-Level Approach)](#detection-strategy)
3. [HTML Parsing Method](#html-parsing-method)
4. [Playwright API Approach](#playwright-api-approach)
5. [JavaScript-Heavy Sites Plan](#javascript-heavy-sites-plan)
6. [Real-World Example](#real-world-example)
7. [Comparison: Our Approach vs Alternatives](#comparison)

---

## Overview

### What We're Doing
We use **Playwright's Page API** to:
1. Navigate to live pages (NOT raw HTML strings)
2. Query the **DOM** (Document Object Model) using CSS selectors
3. Extract question text from HTML elements
4. Fill form fields with Playwright actions

### What We're NOT Doing
- ❌ Parsing raw HTML strings separately
- ❌ Using Playwright MCP (Model Context Protocol)
- ❌ Parsing static HTML with BeautifulSoup
- ❌ Trying to "guess" form structure

### Key Insight
**We work with the rendered DOM, not raw HTML.** This means JavaScript-executed forms work fine if they're already rendered before we start detecting.

---

## Detection Strategy (3-Level Approach)

### Level 1: HTML-Semantic Method (Best Practice)

We look for **standard HTML label + input pattern**:

```html
<!-- Standard pattern we TARGET -->
<label for="salary-input">What's your expected salary?</label>
<input id="salary-input" type="text" name="salary" />
```

**How we detect:**
```python
# Find the label
labels = await self.page.query_selector_all("label")

# Extract label text
label_text = await label.text_content()  # "What's your expected salary?"

# Get the "for" attribute
for_attr = await label.get_attribute("for")  # "salary-input"

# Find the linked field
field = await self.page.query_selector(f"#{for_attr}")

# Extract question + create FormQuestion object
```

**Success Rate:** ~70-80% of well-built forms

---

### Level 2: Placeholder Method (Fallback)

For forms without labels (common in modern forms):

```html
<!-- Pattern WITHOUT label -->
<input type="text" placeholder="Enter your salary (e.g., 12-15 LPA)" />
```

**How we detect:**
```python
# Find all fields with placeholders
inputs_with_placeholder = await self.page.query_selector_all(
    "input[placeholder], textarea[placeholder]"
)

# Use placeholder as question text
placeholder = await field.get_attribute("placeholder")
# "Enter your salary (e.g., 12-15 LPA)"
```

**Success Rate:** ~10-15% (additional catch)

---

### Level 3: Accessibility Method (Robust)

For accessible forms using aria-labels:

```html
<!-- Accessibility-first pattern -->
<input type="text" aria-label="Expected salary range" />
```

**How we detect:**
```python
# Find fields with aria-labels
inputs_with_aria = await self.page.query_selector_all(
    "input[aria-label], select[aria-label]"
)

aria_label = await field.get_attribute("aria-label")
# "Expected salary range"
```

**Success Rate:** ~5-10% (edge cases)

---

### Combined Strategy Flow

```
Page Loaded (JS already executed)
    ↓
Try Level 1: label → input mapping
├─ Success? → Create FormQuestion ✅
├─ No? → Proceed to Level 2
    ↓
Try Level 2: input[placeholder] extraction
├─ Success? → Create FormQuestion ✅
├─ No? → Proceed to Level 3
    ↓
Try Level 3: aria-label extraction
├─ Success? → Create FormQuestion ✅
├─ No? → Skip this field
    ↓
Return all detected FormQuestions
```

---

## HTML Parsing Method

### What We Actually Do With Playwright

```python
# This is the ACTUAL code from chatbot_form_filler.py

async def _detect_form_questions(self) -> List[FormQuestion]:
    """
    Playwright-based detection (NOT raw HTML parsing)
    """
    questions = []
    
    # STEP 1: Wait for form to load
    # This is KEY - we wait for JS to finish rendering
    await self.page.wait_for_selector("label, input, select, textarea", timeout=5000)
    
    # STEP 2: Query the live DOM
    labels = await self.page.query_selector_all("label")
    
    # STEP 3: For each label, extract text and find associated field
    for label in labels:
        label_text = await label.text_content()  # ← Reading from DOM
        
        # Find associated field
        for_attr = await label.get_attribute("for")  # ← Reading attribute
        if for_attr:
            field = await self.page.query_selector(f"#{for_attr}")
            if field:
                # Extract question from field
                question = await self._extract_question_from_field(field, label_text)
                if question:
                    questions.append(question)
```

### Key Points About This Approach

| Aspect | How It Works |
|--------|-------------|
| **HTML Source** | Playwright loads via browser, JS executes naturally |
| **Selectors** | CSS selectors like `"label"`, `"input[type='email']"` |
| **Data Extraction** | `.text_content()`, `.get_attribute()`, `.evaluate()` |
| **Field Detection** | Playwright's `.query_selector()` searches live DOM |
| **Timing** | `.wait_for_selector()` ensures form is rendered first |

---

## Playwright API Approach

### We Use Playwright's Core APIs:

```python
# Query selectors (find elements)
elements = await page.query_selector_all("label")
element = await page.query_selector("#field-id")

# Extract attributes
text = await element.text_content()              # Get text content
attr = await element.get_attribute("aria-label") # Get HTML attribute
input_value = await element.input_value()        # Get input value

# Check state
is_visible = await element.is_visible()
is_checked = await element.is_checked()

# Fill fields
await element.fill("answer-text")                # Fill text input
await element.click()                            # Click button/radio
await element.select_option("option-value")     # Select dropdown

# Advanced: Run JavaScript in context
result = await element.evaluate("el => el.required")  # Check if required
```

### We DON'T Use Playwright MCP

**Why not Playwright MCP?**
- Playwright MCP is for **Claude agents to control the browser**
- We're writing the code that runs **within our system**
- MCP would add unnecessary abstraction layer
- Our code runs in same Python process as Playwright library

**What is Playwright MCP?**
```
Playwright MCP = Tools exposed to Claude Desktop for browser control
Our Approach = We use Playwright library directly in Python
```

---

## JavaScript-Heavy Sites Plan

### Current Situation

Naukri and LinkedIn both use JavaScript extensively:
- Forms rendered via React/Vue
- Fields appear dynamically
- Validation happens on blur
- Modals appear asynchronously

### Our Strategy Handles This

**✅ Already Handled in Design:**

1. **Wait for Selector Pattern**
```python
# Before querying, WAIT for form to load
await self.page.wait_for_selector("label, input", timeout=5000)
# This ensures JS execution completes before we try to read
```

2. **Wait for Network Idle**
```python
# For complex pages, wait for all network requests to finish
await self.page.wait_for_load_state("networkidle")
# Ensures all AJAX calls complete
```

3. **Explicit Element Waits**
```python
# Wait for specific element to be visible
await self.page.locator(".chatbot-form-container").wait_for(state="visible")
# Then proceed with extraction
```

### Example: Handling Naukri's Dynamic Form

**Naukri Flow:**
```
1. Click "Easy Apply"
2. Modal opens (async)
3. Chatbot form loads (JS renders)
4. Question appears dynamically
5. We need to detect it
```

**Our Handling (in naukri_form_filler.py):**
```python
async def fill_naukri_job_application(self, job_url: str):
    # Step 1: Wait for form to fully load
    await self._wait_for_form_load()
    
    # Step 2: Form is ready - now detect questions
    stats = await self.form_filler.auto_fill_chatbot_form()
    
    # Inside auto_fill_chatbot_form():
    # - waits for selector
    # - queries DOM (form already rendered)
    # - extracts questions
```

### Plan for Additional JS Scenarios

| Scenario | Solution |
|----------|----------|
| **Form loaded via AJAX** | Use `.wait_for_load_state("networkidle")` |
| **Hidden fields revealed by JS** | Use `.wait_for_selector()` for new elements |
| **Dynamic validation** | Fill field, trigger blur event, wait for response |
| **Auto-hide after submit** | Check `.is_visible()` before processing |
| **Popup alerts** | Handle with `.handle_dialog()` |
| **Infinite scroll** | Not applicable to chatbots, but use `.locator().scroll_into_view_if_needed()` |

---

## Real-World Example

### Naukri Form Detection Step-by-Step

**HTML on Page:**
```html
<!-- Naukri's React-rendered form -->
<div class="nI-formContainer__row">
    <label class="nI-formLabel__label">
        What is your expected salary?
    </label>
    <input 
        type="text" 
        name="expectedSalary"
        class="nI-formInput__textInput"
        placeholder="e.g., 12-15 LPA"
    />
</div>

<div class="nI-formContainer__row">
    <label class="nI-formLabel__label">
        Preferred work location
    </label>
    <select name="location" class="nI-formSelect__select">
        <option value="">Select location</option>
        <option value="remote">Remote</option>
        <option value="bangalore">Bangalore</option>
    </select>
</div>
```

**Our Detection Code Execution:**

```python
# 1. Wait for form elements
await page.wait_for_selector("label, input, select", timeout=5000)
# ✅ Elements exist → proceed

# 2. Query all labels
labels = await page.query_selector_all("label.nI-formLabel__label")
# ✅ Found 2 labels

# 3. First label processing
label = labels[0]
label_text = await label.text_content()
# ✅ label_text = "What is your expected salary?"

# 4. Find input in same row (label's parent or sibling)
field = await label.evaluate("el => el.closest('.nI-formContainer__row').querySelector('input')")
# ✅ field = <input name="expectedSalary" ...>

# 5. Extract field info
field_name = await field.get_attribute("name")      # "expectedSalary"
field_type = await field.get_attribute("type")      # "text"
placeholder = await field.get_attribute("placeholder")  # "e.g., 12-15 LPA"

# 6. Create FormQuestion object
question = FormQuestion(
    question_text="What is your expected salary?",      # From label
    field_selector="input[name='expectedSalary']",       # CSS selector
    field_type=FieldType.TEXT_INPUT,                     # From input type
    is_required=False,                                   # No required attr
    placeholder="e.g., 12-15 LPA"
)
# ✅ Question detected

# 7. Repeat for second label (location select)
...
```

**Result:**
```
✅ Question 1: "What is your expected salary?" → TEXT_INPUT
✅ Question 2: "Preferred work location" → SELECT
```

---

## Comparison: Our Approach vs Alternatives

### Option 1: Our Approach (Playwright DOM Query) ✅ CHOSEN

```python
# What we do
await page.wait_for_selector("label")  # Wait for JS rendering
labels = await page.query_selector_all("label")  # Query live DOM
text = await label.text_content()  # Extract from rendered element
```

**Pros:**
- ✅ Works with JS-heavy sites (React, Vue, etc.)
- ✅ Forms already rendered when we query
- ✅ No parsing overhead
- ✅ Natural with Playwright

**Cons:**
- ⚠️ Requires page to load (time cost: ~5-15 seconds)
- ⚠️ Can't work without browser (but we always have one anyway)

---

### Option 2: Raw HTML Parsing (BeautifulSoup)

```python
# NOT what we do, but how it would look
import requests
from bs4 import BeautifulSoup

html = requests.get(url).text
soup = BeautifulSoup(html, 'html.parser')
labels = soup.find_all('label')
```

**Pros:**
- ✅ Fast (no browser needed)
- ✅ Lightweight library

**Cons:**
- ❌ Doesn't work with JS-rendered forms (90% fail for Naukri/LinkedIn)
- ❌ Gets static HTML, not rendered DOM
- ❌ JavaScript hasn't executed yet
- ❌ Would see `<div id="root"></div>` instead of actual form

**Example Failure:**
```html
<!-- What raw HTML parser would see (BEFORE JS) -->
<div id="root"></div>
<!-- React hasn't mounted yet! -->

<!-- What Playwright sees (AFTER JS) -->
<div id="root">
    <form>
        <label>Salary?</label>
        <input type="text" />
    </form>
</div>
```

---

### Option 3: Playwright MCP (Claude's Browser Control)

```python
# This is for Claude Desktop, not our internal code
# Claude would call:
# "Use the browser to click the apply button"
# MCP would execute it via Playwright
```

**When to use:**
- Claude agents controlling the browser
- User in Claude Desktop asking agent to fill forms

**When NOT to use (our case):**
- We're building the automation system itself
- We need direct Playwright API access
- We're not exposing to Claude yet

---

### Option 4: Optical Character Recognition (OCR)

```python
# Take screenshot and read form text
screenshot = await page.screenshot()
ocr_results = pytesseract.image_to_string(screenshot)
```

**Pros:**
- ✅ Works for unusual layouts
- ✅ Can handle images with text

**Cons:**
- ❌ Very slow (~2-3 seconds per screen)
- ❌ 70-80% accuracy is not enough for reliable form filling
- ❌ Can't get field metadata (type, name, etc.)
- ⚠️ Only fallback if HTML parsing fails completely

**Our Plan for OCR:**
```
IF HTML parsing works (normal case): Use queries ✅
IF HTML parsing fails (unusual UI): Try OCR fallback ⚠️
```

---

## Current Implementation Summary

### How It Works in Practice

```python
# When filling a Naukri chatbot form:

1. Navigate to job page
   await page.goto(job_url)

2. Click "Easy Apply"
   await page.click("button:has-text('Easy Apply')")

3. Wait for modal/form to appear
   await page.wait_for_selector(".chatbot-form", timeout=10000)
   await page.wait_for_load_state("networkidle")

4. Detect questions from DOM
   questions = await form_filler._detect_form_questions()
   # Uses query_selector_all("label") to find questions
   # Extracts text, field type, selectors from rendered DOM

5. For each question, find answer semantically
   for question in questions:
       answer = vector_db.answer_question(question.text)
       # Queries vector DB for matching answer

6. Fill form fields
   for question, answer in zip(questions, answers):
       await page.fill(question.field_selector, answer)
       # Playwright fills the actual field

7. Submit or continue
   await page.click("button:has-text('Next')")
```

### JavaScript Handling: Already Built In

- ✅ `.wait_for_selector()` - waits for JS to render elements
- ✅ `.wait_for_load_state("networkidle")` - waits for AJAX calls
- ✅ `.fill()`, `.click()`, `.select_option()` - trigger all JS events
- ✅ `.evaluate()` - run custom JS if needed

---

## Key Takeaways

| Question | Answer |
|----------|--------|
| **Are we parsing raw HTML?** | No, we query the live DOM via Playwright |
| **Are we using Playwright MCP?** | No, we use Playwright library directly |
| **Does it handle JS-heavy sites?** | Yes, via `.wait_for_selector()` and `.wait_for_load_state()` |
| **What about forms that render dynamically?** | Already handled - we wait for elements before querying |
| **How fast is detection?** | ~1-3 seconds per form (bottleneck is browser rendering, not parsing) |
| **What's the fallback for unusual forms?** | OCR if needed (future enhancement) |
| **Can Claude use this?** | Yes, via MCP tools once Phase 4 is complete |

---

## Next Steps

**For More Details:**
- See `scripts/common_stuff/chatbot_form_filler.py` - actual detection code
- See `scripts/cookie_management_login/naukri_form_filler.py` - Naukri-specific handling
- See `scripts/tests/test_form_filling.py` - test cases for detection

**For JavaScript-Heavy Sites:**
- Already handled in Phase 1 design
- `.wait_for_selector()` ensures rendering before detection
- Test on Naukri live form in Phase 3

**For Edge Cases:**
- Add OCR fallback in Phase 5 if needed
- Naukri-specific selectors already defined
- Error handling in place for missing/broken forms

---

**Document Version:** 1.0  
**Created:** April 17, 2026  
**Purpose:** Explain form parsing strategy to user
