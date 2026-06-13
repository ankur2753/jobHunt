# Naukri Auto-Apply Implementation Summary

**Phase**: 1-6 Complete  
**Date**: April 23, 2026  
**Status**: ✅ Ready for testing & validation

---

## What's Been Implemented

### Phase 1: Selector Discovery & Validation ✅
**Files Created:**
- `scripts/common_stuff/naukri_selector_discovery.py` — Validates all Naukri selectors at runtime
  - `SelectorValidator` class with multi-selector support
  - Exports JSON reports for diagnostics
  - Detects which selectors work/fail on live pages
  - Provides HTML samples for debugging

**Features:**
- Validates job card selectors (recommended jobs page)
- Validates form field selectors (apply/form page)
- Logs selector usage at each step
- Generates timestamped validation reports
- Fallback selector chains for resilience

---

### Phase 2: Logging & Diagnostics ✅
**Files Modified:**
- `scripts/job_scraping/naukri_job_apply.py` — Enhanced with selector validation
  - Integrated `SelectorValidator` into auto-apply workflow
  - Logs selector usage at each job card/button interaction
  - Exports diagnostic JSON reports
  - Added `get_diagnostics()` method to NaukriJobApply class

**New Methods:**
- `get_diagnostics()` — Returns validation diagnostics
- `export_diagnostics()` — Saves diagnostic logs to JSON
- Constructor now accepts `enable_selector_validation` flag

**Features:**
- Validates selectors on recommended jobs page before processing
- Logs selector health status for debugging
- Includes selector validation report path in results
- Comprehensive error tracking

---

### Phase 3: End-to-End Test Runner ✅
**Files Created:**
- `scripts/tests/naukri_e2e_test.py` — Complete E2E test framework
  - **Stage 1**: Navigate & collect job cards
  - **Stage 2**: Validate job card elements & apply buttons
  - **Stage 3**: Test apply click & form detection
  - **Stage 4** (future): Form filling validation

**Features:**
- CLI: `python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headless`
- Detailed stage-by-stage reporting
- Selector validation at each stage
- JSON report output for analysis
- Supports headed/headless modes
- Configurable verbosity

**Usage Examples:**
```bash
# Test 3 jobs in headless mode (default)
python scripts/tests/naukri_e2e_test.py --max-jobs 3

# Test 1 job with browser visible
python scripts/tests/naukri_e2e_test.py --max-jobs 1 --headed

# Verbose logging
python scripts/tests/naukri_e2e_test.py --max-jobs 5 --verbose
```

---

### Phase 4: Selector Gap Analysis ✅
**Files Created:**
- `Instructions/NAUKRI_SELECTOR_ANALYSIS.md` — Comprehensive selector audit
  - Documents all current selectors with stability ratings
  - Identifies 10+ selector gaps & brittleness points
  - Provides fallback recommendations
  - Testing checklist for validation

**Key Findings:**
- ✅ Core selectors use stable `data-qa` attributes
- ⚠️ Job title selector (`h1.jobTitle`) is fragile (CSS class)
- ⚠️ Company name extraction optional (may not exist)
- ⚠️ Submit button detection needs multi-tier strategy
- ✅ Form container selectors already have good fallbacks
- ⚠️ NLA popup handling needs Naukri-specific refinement

---

### Phase 5: Selector Improvements ✅
**Files Modified:**
- `scripts/cookie_management_login/naukri_form_filler.py` — Enhanced selectors & validation
  
**Selector Enhancements:**
```python
# OLD: Single selectors (fragile)
'job_title_heading': 'h1.jobTitle'

# NEW: Multi-tier fallback chains (resilient)
'job_title_heading': '[data-qa="jobDetailTitle"], h1.jobTitle, h1[data-qa="jobTitle"], .jobDetailTitle'

# NEW: Added required field detection
'required_indicator': '[required], [aria-required="true"], .required, .mandatory, [data-qa*="required"]'

# NEW: Added error message detection
'error_message': '.error, [role="alert"], .validation-error, .form-error, [data-qa*="error"]'
```

**Method Improvements:**
- `_extract_job_details()` — Makes company name optional (doesn't fail if missing)
- `_close_nla_popups()` — Better NLA-specific popup targeting
- `_validate_form_fields()` — Enhanced validation with required field checking
- `_submit_form()` — Multi-tier submit button detection with visibility/enabled checks

**New Features:**
- Timeout increased from 15s to 20s for slow forms
- Retry delay constants added (1s between retries)
- Selector validation integration (optional)
- Better error messages throughout

---

### Phase 6: Retry Logic & Error Handling ✅
**Files Created:**
- `scripts/common_stuff/retry_utils.py` — Async retry utilities
  - `@retry_async` decorator with exponential backoff
  - `retry_until_visible()` — Wait for element visibility
  - `retry_until_enabled()` — Wait for element enablement
  - `RetryException` — Custom retry exception

**Features:**
- Configurable max attempts, backoff multiplier, delay
- Logging at each retry attempt
- Customizable exception catching
- Optional callback on each retry

**Usage Example:**
```python
@retry_async(max_attempts=3, backoff=2, initial_delay=1)
async def click_apply_button(page):
    button = await page.query_selector('button[data-qa="nxtApplyBtn"]')
    await button.click()
```

**Files Modified:**
- `scripts/job_scraping/naukri_job_apply.py` — Integrated retry logic
  - Apply button finding now retries with multiple selectors
  - Better error handling around button clicking
  - Improved indentation/flow logic for form filling
  - Comprehensive try-catch blocks at each step

**New Flow:**
1. Try to find apply button with multiple selectors (fails fast or retries)
2. Check button visibility & enablement state
3. Scroll into view if needed
4. Click with error handling
5. Wait longer for form to load (3s instead of 2s)
6. Initialize form filler with validation disabled (to avoid double validation)

---

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│  naukri_job_apply.py (Main Orchestrator)    │
│  - Navigates to recommended jobs page       │
│  - Collects job cards                       │
│  - Validates selectors (SelectorValidator)  │
│  - Clicks apply buttons (with retries)      │
│  - Initializes form filler for each job     │
└────────────┬────────────────────────────────┘
             │
             ├─► SelectorValidator (Phase 1)
             │   - Probes page for selectors
             │   - Exports JSON reports
             │   - Integrates with logging
             │
             ├─► retry_utils (Phase 6)
             │   - Decorator-based retries
             │   - Exponential backoff
             │   - Visibility/enabled checks
             │
             ├─► naukri_form_filler.py (Phase 5)
             │   - Opens job application page
             │   - Enhanced selectors (multi-tier)
             │   - Better NLA popup handling
             │   - Improved validation
             │   - Detects form questions
             │   - Auto-fills with vector DB
             │
             └─► vector_db_manager.py (existing)
                 - Semantic matching for answers
                 - Question→Answer lookup
```

---

## Key Improvements

### Resilience
- **Multi-tier selector fallbacks**: Try primary, secondary, tertiary selectors
- **Retry logic**: Exponential backoff for transient failures
- **Graceful degradation**: Make optional fields truly optional
- **Better error messages**: Specific exception types for debugging

### Observability
- **Selector validation reports**: Know which selectors work/fail
- **Comprehensive logging**: Every major step is logged
- **Diagnostic exports**: JSON reports for post-run analysis
- **Stage-based test reporting**: Clear pass/fail for each phase

### Maintainability
- **Isolated utilities**: Retry logic, selectors, validation in separate modules
- **Single responsibility**: Each class has one job
- **Clear documentation**: Docstrings and comments throughout
- **Testing framework**: E2E tests for quick validation

---

## Files Changed Summary

### New Files (5)
1. `scripts/common_stuff/naukri_selector_discovery.py` — ~380 lines
2. `scripts/tests/naukri_e2e_test.py` — ~450 lines
3. `scripts/common_stuff/retry_utils.py` — ~250 lines
4. `Instructions/NAUKRI_SELECTOR_ANALYSIS.md` — ~350 lines
5. `Instructions/IMPLEMENTATION_SUMMARY.md` — This file

### Modified Files (2)
1. `scripts/job_scraping/naukri_job_apply.py` — Enhanced with validation & retry
2. `scripts/cookie_management_login/naukri_form_filler.py` — Updated selectors & validation

---

## Testing Checklist

### Pre-Deployment Validation

- [ ] **Run E2E Test Stage 1**
  ```bash
  python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed
  ```
  - ✅ Navigates to recommended jobs page
  - ✅ Detects job cards with `[data-qa="jobTuple"]`
  - ✅ Generates selector validation report
  - ✅ Saves report to `logs/naukri_selector_validation_*.json`

- [ ] **Run E2E Test Stage 2**
  - ✅ Validates job card structure (title, apply button)
  - ✅ Checks if apply buttons are visible/enabled
  - ✅ Reports on 3+ job cards
  - ✅ No crashes during job card iteration

- [ ] **Run E2E Test Stage 3**
  - ✅ Clicks apply button on first job
  - ✅ Waits for form to load (20s timeout)
  - ✅ Detects form container (`.filler-container`, etc.)
  - ✅ Counts form fields
  - ✅ Validates form page selectors

- [ ] **Test Auto-Apply End-to-End (Dry-Run)**
  ```bash
  # Using test_real_job_posting.py with dry-run
  python scripts/tests/test_real_job_posting.py --portal naukri --url "<job_url>" --dry-run --headless
  ```
  - ✅ Opens job URL
  - ✅ Detects form questions
  - ✅ Attempts semantic matching (no submit)
  - ✅ Reports questions found/filled

- [ ] **Test Form Submission Validation** (no actual submit)
  - ✅ Validates required fields before submit
  - ✅ Detects validation errors
  - ✅ Checks required field indicators
  - ✅ Logs form state

- [ ] **Test Orchestrator Integration**
  ```bash
  python scripts/orchestrator/orchestrator.py
  # Select: 2 (Naukri)
  # Select: 2 (Apply on job portals)
  # Should use updated NaukriJobApply with validation
  ```
  - ✅ Orchestrator menu appears
  - ✅ Naukri option selectable
  - ✅ Apply flow starts correctly
  - ✅ Auto-apply begins with selector validation

---

## Known Limitations & Future Work

### Limitations
1. ❌ **Not tested on real Naukri jobs yet** — Needs live environment validation
2. ⚠️ **Multi-step forms** — Not yet handled (if form has Next button)
3. ⚠️ **Custom form controls** — Limited support for sliders, custom dropdowns
4. ⚠️ **Dynamic form loading** — Timeout might need adjustment per job

### Future Enhancements (Phase 7+)
- [ ] Multi-step form detection and navigation
- [ ] Custom form control handlers (sliders, toggle switches)
- [ ] Dynamic selector discovery (if hardcodes fail, auto-discover)
- [ ] Form field confidence scoring (know which fields are uncertain)
- [ ] Screenshot capture on form filling failures
- [ ] Performance optimization (parallel job processing)
- [ ] Analytics dashboard (success rates, fill rates, time metrics)

---

## Quick Start Guide

### 1. Run Selector Validation
```bash
# Test on live Naukri recommended jobs page
python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed
```
Output: JSON report in `logs/naukri_e2e_test_*.json` and `logs/naukri_selector_validation_*.json`

### 2. Test End-to-End (Dry-Run)
```bash
# Get a Naukri job URL first, then:
python scripts/tests/test_real_job_posting.py --portal naukri --url "https://www.naukri.com/jobs/..." --dry-run
```

### 3. Test Full Auto-Apply (with validation)
```bash
# Via orchestrator
python scripts/orchestrator/orchestrator.py
# Select option 2 (Naukri) → 2 (Apply to jobs)
```

### 4. Analyze Diagnostics
```bash
# Review any generated JSON report:
cat logs/naukri_selector_validation_*.json | python -m json.tool
```

---

## Success Criteria

✅ **Phase Implementation Complete When:**
1. E2E test passes all 3 stages on real Naukri site
2. Selector validation report shows all critical selectors as "PASS"
3. Auto-apply successfully processes 3+ jobs without crashes
4. Form filling detects 5+ test questions per job
5. Orchestrator integration works end-to-end

---

## Support & Debugging

### If E2E Test Fails

1. **Check logs**: `tail -f logs/*.log`
2. **Review selector report**: `cat logs/naukri_selector_validation_*.json`
3. **Run with `--headed` flag** to see browser
4. **Increase timeout**: Edit `FORM_LOAD_TIMEOUT` if forms load slowly
5. **Check Naukri UI**: They may have redesigned the page (update selectors in analysis doc)

### If Form Filling Fails

1. Check form page URL (may have changed structure)
2. Run E2E Stage 3 to validate form selectors
3. Review form container selector in `NAUKRI_SELECTORS['chatbot_form_container']`
4. Check if NLA popup is blocking: `_close_nla_popups()` may need tweaking

---

## References

- **Orchestrator**: [scripts/orchestrator/orchestrator.py](scripts/orchestrator/orchestrator.py)
- **Main Auto-Apply**: [scripts/job_scraping/naukri_job_apply.py](scripts/job_scraping/naukri_job_apply.py)
- **Form Filler**: [scripts/cookie_management_login/naukri_form_filler.py](scripts/cookie_management_login/naukri_form_filler.py)
- **Selector Discovery**: [scripts/common_stuff/naukri_selector_discovery.py](scripts/common_stuff/naukri_selector_discovery.py)
- **E2E Tests**: [scripts/tests/naukri_e2e_test.py](scripts/tests/naukri_e2e_test.py)
- **Selector Analysis**: [Instructions/NAUKRI_SELECTOR_ANALYSIS.md](Instructions/NAUKRI_SELECTOR_ANALYSIS.md)
- **Retry Utilities**: [scripts/common_stuff/retry_utils.py](scripts/common_stuff/retry_utils.py)

---

**Status**: ✅ Ready for testing  
**Next Step**: Run E2E tests against live Naukri to identify any remaining gaps
