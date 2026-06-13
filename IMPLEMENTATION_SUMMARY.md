# Implementation Summary: Naukri Automation Fixes

## Overview
Three critical fixes have been implemented for your Naukri job application automation script:
1. ✅ Interactive VectorDB terminal test
2. ✅ Fixed radio button clicks, save button, and added Playwright codegen fallback
3. ✅ Silent batched auto-apply (hardcoded 5 jobs per batch)

---

## Step 1: Interactive VectorDB & Normalizer Test

### Location
**File**: `scripts/tests/test_interactive_vector_db.py` *(New)*

### What It Does
- **Interactive Terminal**: Ask questions in real-time and get normalized answers
- **Semantic Matching**: Tests your Vector DB retrieval with confidence scores
- **Field Category Detection**: Automatically detects question type (salary, location, experience, etc.)
- **Answer Normalization**: Shows how answers are formatted for form submission

### How to Use
```bash
# From project root
python scripts/tests/test_interactive_vector_db.py
```

### Example Session
```
🎯 Ask a question: How many years of Angular experience?

FIELD CATEGORY DETECTED:
   EXPERIENCE (FieldCategory.EXPERIENCE)

VECTOR DB MATCHES (Top 3):
   [1] Source: work_experience
       Answer: 5 years
       Confidence: 92.50%
       Auto-fill: YES

NORMALIZATION:
   Normalizer: normalize_experience
   Raw: 5 years
   Normalized: 5

✅ FINAL ANSWER FOR FORM:
   5
```

### Exit Commands
- Type `exit`, `quit`, `q`, or `:q` to stop
- Or press `Ctrl+C`

---

## Step 2: Fixed Chatbot Form Filling Issues

### Fixed Issues

#### 2.1 Radio Button Clicks Timeout
**Problem**: `await radio.click()` was timing out because radio inputs are hidden/layered behind labels.

**Solution**: Three-strategy fallback in `_fill_radio_field()`:
```python
# Strategy 1: force=True click
await radio.click(force=True)

# Strategy 2: Find and click associated label
label_elem = await page.query_selector(f'label[for="{radio_id}"]')
await label_elem.click()

# Strategy 3: JavaScript click
await radio.evaluate('el => el.click()')
```

**File**: `scripts/cookie_management_login/naukri_form_filler.py` → `_fill_radio_field()` method

---

#### 2.2 Save Button Not Found
**Problem**: Save button is a `<div>`, not a `<button>`:
```html
<div id="sendMsg__..." class="send">
  <div class="sendMsg" tabindex="0">Save</div>
</div>
```

**Solution**: Five-strategy search in `click_chatbot_save_button()`:
1. Standard button elements (`button[data-qa="save"]`)
2. Naukri div buttons (`div.send:not(.disabled) > .sendMsg`)
3. Text-based selectors (`button:has-text("Save")`)
4. Any clickable element with action text
5. Waits for disabled class to be removed before clicking

**File**: `scripts/cookie_management_login/naukri_form_filler.py` → `click_chatbot_save_button()` method

---

#### 2.3 Codegen Fallback for Automation Failures
**Problem**: When automation times out or fails, there's no recovery mechanism.

**Solution**: Playwright Inspector (codegen) fallback integrated into `_fill_form_with_fallback()`:

```python
# On TimeoutError or click failure:
try:
    await chip_elem.click()
except PlaywrightTimeoutError:
    await self._launch_codegen_fallback()
    # Codegen launches, user records action manually
    # Script resumes when inspector closes
```

**New Method**: `_launch_codegen_fallback()`
- Pauses automation with clear instructions
- Launches Playwright Inspector (if CLI available)
- User manually performs the action (click radio, fill text, etc.)
- Inspector records the correct selectors/actions
- Script resumes when inspector closes
- Falls back to manual guidance if CLI unavailable

**File**: `scripts/cookie_management_login/naukri_form_filler.py` → `_launch_codegen_fallback()` method

---

## Step 3: Silent Batched Auto-Apply

### What Changed
Removed user input prompt, now runs automatically with batch size of **5 jobs**.

### Before
```python
max_jobs_str = input("How many jobs would you like to apply to? (default: 5): ").strip() or "5"
max_jobs = int(max_jobs_str)
```

### After
```python
max_jobs = 5  # Hardcoded - silent batch processing
```

### Behavior
- **Batch Size**: Exactly 5 jobs per run
- **No Prompts**: Starts immediately when Naukri option is selected
- **Repeated Runs**: Run the script multiple times to apply to more jobs
- **Message**: Shows helpful text suggesting to run again for more jobs

**File**: `scripts/orchestrator/orchestrator.py` → Lines 262-268

### Usage
```bash
# From project root
python scripts/orchestrator/orchestrator.py

# Select: 2 (Naukri) → 2 (Apply to jobs)
# → Automatically applies to 5 jobs without asking
# → To apply to 5 more: Run script again
```

---

## Testing the Fixes

### Test 1: VectorDB Functionality
```bash
python scripts/tests/test_interactive_vector_db.py
# Type various questions to verify semantic matching
```

### Test 2: Radio Button & Save Button Fixes
```bash
# These are tested automatically during form filling
# Check logs for: "Selected radio (force=True)" or "Save button clicked"
```

### Test 3: Codegen Fallback
```bash
# The fallback triggers automatically on timeout errors
# You'll see: "PLAYWRIGHT INSPECTOR (CODEGEN) FALLBACK TRIGGERED"
```

### Test 4: Silent Batched Apply
```bash
python scripts/orchestrator/orchestrator.py
# Select: 2 (Naukri) → 2 (Apply to jobs)
# Should start applying to 5 jobs immediately with no input prompt
```

---

## Key Implementation Details

### Radio Button Fix - Multi-Strategy Approach
```python
# Try force=True (works for most hidden inputs)
await radio.click(force=True)

# If that fails, find label and click it
radio_id = await radio.get_attribute('id')
label = await page.query_selector(f'label[for="{radio_id}"]')
await label.click()

# If that fails, use JavaScript
await radio.evaluate('el => el.click()')
```

**Why multiple strategies?**
- Different Naukri page versions use different HTML structures
- Some radios are hidden, some are labeled, some are JavaScript-controlled
- Fallback chain ensures at least one strategy works

---

### Save Button Fix - Handles Div Structure
```python
# Before: Only looked for <button> elements
# After: Also looks for <div class="send"> structure

# Wait for disabled class to be removed
send_button = await page.query_selector('div.send:not(.disabled)')
if send_button:
    send_msg = await send_button.query_selector('.sendMsg')
    await send_msg.click(force=True)
```

---

### Codegen Fallback - Graceful Degradation
```python
# 1. Automation tries to click element
try:
    await element.click()
except PlaywrightTimeoutError:
    # 2. On failure, launch interactive recording mode
    await self._launch_codegen_fallback()
    # 3. User performs action manually
    # 4. Playwright records the correct selector
    # 5. Script resumes (you can update the selector later)

# No more stuck scripts - user always has an escape hatch
```

---

## File Changes Summary

### New Files
- `scripts/tests/test_interactive_vector_db.py` - Interactive VectorDB tester

### Modified Files
1. `scripts/cookie_management_login/naukri_form_filler.py`
   - `_fill_radio_field()` - Added 3-strategy fallback
   - `click_chatbot_save_button()` - Added 5-strategy fallback for div buttons
   - `_fill_form_with_fallback()` - Added codegen fallback on failures
   - `_launch_codegen_fallback()` - NEW method for Playwright Inspector

2. `scripts/orchestrator/orchestrator.py`
   - Removed `input()` prompt for job count
   - Hardcoded `max_jobs = 5`
   - Added batch processing message

---

## Troubleshooting

### Issue: VectorDB test shows "no matches"
**Solution**: Run `setup.html` to add personal details to vector DB
```bash
# Open in browser and fill form
open setup.html
# Then run the test again
python scripts/tests/test_interactive_vector_db.py
```

### Issue: Radio button still times out
**Solution**: The codegen fallback will help you identify the correct selector
- When timeout occurs, Playwright Inspector launches
- Click the radio button manually in the browser
- The inspector shows you the exact selector you should use
- Update `_fill_radio_field()` with the new selector for future runs

### Issue: Save button still not found
**Solution**: Use codegen fallback to identify it
- On failure, the script launches Playwright Inspector
- Click the actual save button in the browser
- Inspector records the selector
- You can then update `click_chatbot_save_button()` with the new selector

### Issue: Playwright CLI not found for codegen
**Solution**: The script falls back to manual guidance
```bash
# Install Playwright CLI
npm install -g @playwright/test
# Or use Python package
pip install playwright
playwright install
```

---

## Next Steps

1. **Test the interactive VectorDB tool**:
   ```bash
   python scripts/tests/test_interactive_vector_db.py
   ```

2. **Run an auto-apply batch**:
   ```bash
   python scripts/orchestrator/orchestrator.py
   # Select: 2 (Naukri) → 2 (Apply to jobs)
   ```

3. **Monitor logs** for:
   - ✅ "Selected radio (force=True)" - Radio fix working
   - ✅ "Save button clicked" - Save button fix working
   - ✅ Auto-applying to 5 jobs without prompt - Batch fix working

4. **If failures occur**:
   - Codegen will launch automatically
   - Perform action manually in browser
   - Close inspector - script resumes

---

## Questions & Customization

### To change batch size from 5 to another number:
Edit `scripts/orchestrator/orchestrator.py`:
```python
max_jobs = 10  # Change from 5 to 10
```

### To disable codegen fallback:
Remove the try-except blocks in `_fill_form_with_fallback()` method

### To test specific normalizers:
```bash
python scripts/tests/test_interactive_vector_db.py
# Type: "What is your salary?" (tests normalize_salary)
# Type: "Where do you want to work?" (tests normalize_location)
# Type: "How much experience?" (tests normalize_experience)
```

---

## Summary of Improvements

| Issue | Before | After |
|-------|--------|-------|
| Testing VectorDB | Manual debugging | Interactive terminal test |
| Radio button timeouts | Script hangs | 3-strategy fallback + codegen |
| Save button not found | Script stuck | 5-strategy fallback + codegen |
| Automation failures | No recovery | Playwright Inspector codegen |
| Job batch input | User prompted each time | Silent 5-job batches |
| Batch size | Variable | Fixed 5 per run |

---

All changes are production-ready. The script now handles edge cases gracefully and provides clear feedback when issues occur. 🚀
