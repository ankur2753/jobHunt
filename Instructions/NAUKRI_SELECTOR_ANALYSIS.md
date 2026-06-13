# Naukri Selector Analysis & Gaps Report

**Date**: April 23, 2026  
**Phase**: 2 - Selector Discovery & Validation  
**Status**: Discovery Phase (Recommendations)

---

## Overview

This document provides a comprehensive analysis of Naukri selectors currently used in the auto-apply workflow and identifies potential gaps, brittle points, and recommendations based on typical Naukri HTML structure.

**Key Findings:**
- ✅ Core selectors are data-qa based (good: more stable than CSS classes)
- ⚠️ Some selectors use `.data-qa` pattern may need fallbacks
- ❌ Job title extraction selector (`h1.jobTitle`) may be fragile
- ⚠️ Company name selector may not work on all job pages
- ✅ Form containers use multiple patterns (good resilience)

---

## Selector Categories & Analysis

### 1. Job Card Selectors (Recommended Jobs Page)

**Location**: `scripts/job_scraping/naukri_job_apply.py` → `SELECTORS` dict

| Selector Name | Current Selector | Status | Stability | Alternative Selectors | Notes |
|---|---|---|---|---|---|
| `job_cards` | `[data-qa="jobTuple"]` | ✅ | High | `[data-qa="job-card"]`, `.jobCardContainer` | Primary selector with data-qa. Highly stable. |
| `job_card_title` | `[data-qa="jobTitle"]` | ✅ | High | `.jobTitle`, `h2.jobTitle` | Located within job card. Good specificity. |
| `apply_button` | `button[data-qa="nxtApplyBtn"]` | ⚠️ | Medium | `button[data-qa="applyBtn"]`, `button:has-text("Apply")` | May fail if button text changes. Needs fallback. |
| `job_url` | `a[data-qa="jobCardCurrentJobTitle"]` | ✅ | High | `.jobCardLink`, `a[role="link"]` | Stable link selector but URL structure may vary. |
| `loader` | `.loader, [data-qa="loader"], .spinner` | ✅ | High | N/A | Multiple fallbacks already present. Good. |
| `popup_close` | `button[aria-label="Close"], .popup-close` | ⚠️ | Medium | `button[aria-label="close"]`, `.modal-close`, `[data-qa="closeModal"]` | aria-label may not be localized. Needs multiple fallbacks. |

**Issues Identified:**
1. ❌ No timeout/retry for locating job cards (may need wait_for_selector)
2. ⚠️ Apply button selector lacks robust fallback chain
3. ⚠️ Popup close button using aria-label (may break with UI changes)

**Recommendations:**
- [ ] Add `wait_for_selector` with timeout for job cards on page load
- [ ] Implement fallback selector chain for apply button  
- [ ] Use data-qa attributes preferentially for popup close button
- [ ] Add scroll-into-view retry if job card not visible

---

### 2. Form Page Selectors (Job Detail/Apply Page)

**Location**: `scripts/cookie_management_login/naukri_form_filler.py` → `NAUKRI_SELECTORS` dict

| Selector Name | Current Selector | Status | Stability | Alternative Selectors | Notes |
|---|---|---|---|---|---|
| `job_title_heading` | `h1.jobTitle` | ⚠️ | Medium | `h1[data-qa="jobTitle"]`, `[data-qa="jobDetailTitle"]`, `.jobDetailTitle` | CSS class based - fragile. Prefer data-qa. |
| `company_name` | `[data-qa="jobCardCompanyName"]` | ⚠️ | Medium | `[data-qa="companyName"]`, `.companyName`, `[data-qa="jobDetailsCompany"]` | May not exist on all pages. Consider optional. |
| `apply_button` | `button[data-qa="nxtApplyBtn"]` | ✅ | High | `button[data-qa="applyBtn"]` | Good selector, but may appear multiple places. |
| `chatbot_form_container` | `.filler-container, .customFields, [data-qa="customFields"]` | ✅ | High | `[role="form"]`, `.application-form` | Multiple CSS classes (good) + data-qa. Robust. |
| `form_fields` | `input, select, textarea, [role="combobox"], [role="radio"]` | ✅ | High | N/A | Comprehensive field selector. Good. |
| `submit_button` | `button[type="submit"], button[data-qa="submit"]` | ⚠️ | Medium | `button[data-qa="submitBtn"]`, `button:has-text("Submit")`, `button:has-text("Apply")` | May have different text/data-qa on Naukri. Needs testing. |
| `next_button` | `button[data-qa="nxtBtn"], button:has-text("Next")` | ⚠️ | Medium | `button[data-qa="nextBtn"]`, `.next-button` | Multi-step forms may have this. Text-based fallback fragile. |
| `nla_popup_close` | `button[aria-label="Close"], .popup-close, [data-qa="closeModal"]` | ⚠️ | Medium | `button[class*="close"]`, `[data-qa="nlaClose"]` | Naukri-specific NLA (Next Level Automation) popup. Needs refinement. |
| `loader` | `.loader, .spinner, [data-qa="loader"]` | ✅ | High | N/A | Multiple fallbacks already present. |

**Issues Identified:**
1. ❌ `job_title_heading` uses CSS class (`.jobTitle`) which is brittle
2. ⚠️ `company_name` selector may not work on all job postings
3. ⚠️ `submit_button` may have different text/structure (needs real-world testing)
4. ❌ NLA popup selector not specific enough (may close wrong popups)
5. ⚠️ No selectors for required field indicators (red asterisk, `[required]` attr)

**Recommendations:**
- [ ] Replace `h1.jobTitle` with data-qa based selector `[data-qa="jobDetailTitle"]`  
- [ ] Make `company_name` extraction optional (don't fail if not found)
- [ ] Add submit button detection via multiple strategies (data-qa, type, text content)
- [ ] Refine NLA popup to target Naukri-specific popup structure (usually a modal)
- [ ] Add detection for required form fields before submission attempt
- [ ] Test all form page selectors on 5+ real Naukri job postings

---

### 3. Naukri-Specific UI Quirks

| Issue | Description | Impact | Workaround |
|---|---|---|---|
| **NLA Popups** | Naukri shows "Next Level Automation" popup overlays that block clicks | HIGH | Use `_close_nla_popups()` to close; add wait_for_visibility checks |
| **Lazy-Loaded Forms** | Job application form may load asynchronously (2-5 sec delay) | HIGH | Increase `FORM_LOAD_TIMEOUT` to 15-20 seconds; add retry logic |
| **Form Multi-Step** | Some applications have multi-step forms (Next → Next → Submit) | MEDIUM | Detect multi-step form structure; handle next button clicks |
| **Slider/Range Inputs** | Some fields may be sliders instead of text inputs | MEDIUM | Add support for `input[type="range"]` and slider interactions |
| **Custom Form Controls** | Naukri uses custom dropdowns/radio groups with JS handlers | MEDIUM | Use Playwright's `fill()` and `select_option()` methods; avoid direct element clicks |
| **Disabled Fields** | Required fields marked with `disabled` attribute initially, then enabled | LOW | Check field enablement state before interacting; retry if disabled |

---

## Current Implementation Gaps

### 🔴 Critical Gaps

1. **Job Title Selector Fragility** (`h1.jobTitle`)
   - Current: Uses CSS class selector
   - Problem: CSS classes change frequently on Naukri redesigns
   - Fix: Use `[data-qa="jobDetailTitle"]` or similar data attribute
   - Priority: HIGH

2. **Submit Button Detection**
   - Current: Generic `button[type="submit"]` which may not work if Naukri uses custom structure
   - Problem: Form may not submit if button selector fails silently
   - Fix: Add multi-tier detection (data-qa → type → text content)
   - Priority: HIGH

3. **No Retry Logic for Selector Not Found**
   - Current: Code tries selector once and fails
   - Problem: Transient failures (slow page load, race conditions) cause app failure
   - Fix: Add `@retry_selector()` decorator with exponential backoff
   - Priority: HIGH

### 🟡 Medium Gaps

4. **Company Name Extraction** (optional but logged)
   - Current: Selector may not exist on all pages
   - Problem: Throws error if `company_name` selector not found
   - Fix: Make extraction optional; log warning if not found
   - Priority: MEDIUM

5. **Form Field Validation**
   - Current: No validation for required fields before submission
   - Problem: May submit form with missing required fields
   - Fix: Check for `[required]` attributes and visual indicators before submit
   - Priority: MEDIUM

6. **NLA Popup Detection**
   - Current: Selector chain doesn't target Naukri NLA specifically
   - Problem: May close unrelated modals or miss Naukri-specific popups
   - Fix: Use Naukri-specific selectors like `[data-qa="nlaModal"]` or `.nextLevelAutomation`
   - Priority: MEDIUM

### 🟢 Minor Gaps

7. **No Dynamic Selector Discovery** (addressed in Phase 1)
   - Fix: Implemented in `naukri_selector_discovery.py`
   - Status: ✅ DONE

8. **Error Messages Not Logged**
   - Current: Form filling failures don't capture Naukri error messages
   - Problem: Hard to debug form failures
   - Fix: Capture error message text from form validation alerts
   - Priority: LOW

---

## Testing Recommendations

### Pre-Deployment Validation Checklist

- [ ] **Test 1**: Recommended Jobs Page Selectors
  - Navigate to `https://www.naukri.com/mnjuser/recommendedjobs`
  - Verify: `[data-qa="jobTuple"]` finds job cards
  - Verify: `[data-qa="jobTitle"]` finds job titles
  - Success: ≥10 job cards detected

- [ ] **Test 2**: Job Detail Page Selectors
  - Click on a job card to open detail page
  - Verify: Job title heading appears
  - Verify: Company name appears (if available)
  - Verify: Apply button is visible and clickable
  - Success: All selectors found

- [ ] **Test 3**: Form Page Selectors
  - Click "Apply" button on job detail page
  - Verify: Chatbot form container loads
  - Verify: Form fields are detected (`input`, `select`, `textarea`)
  - Verify: Submit button is visible
  - Success: Form structure validated without submitting

- [ ] **Test 4**: NLA Popup Handling
  - Watch for NLA popup during apply click
  - Verify: Popup is closed automatically
  - Verify: Form loads after popup close
  - Success: No stuck applications

- [ ] **Test 5**: Multi-Step Form Detection**
  - Apply to job with multi-step form (if available)
  - Verify: "Next" buttons are detected and clicked
  - Verify: Form progresses through all steps
  - Success: Multi-step forms handled

- [ ] **Test 6**: Error Handling
  - Test with job that has form validation errors
  - Verify: Error messages are captured
  - Verify: Application doesn't submit with errors
  - Success: Validation prevents bad submissions

---

## Action Items

### Phase 2 (Current) - Discovery ✅
- [x] Create selector discovery utility (`naukri_selector_discovery.py`)
- [x] Document current selectors and gaps
- [x] Create E2E test runner
- [ ] Run E2E test against real Naukri recommended jobs page
- [ ] Capture actual Naukri HTML selectors
- [ ] Document any selector discrepancies

### Phase 3 (Next) - Fix & Update
- [ ] Update `naukri_form_filler.py` with validated selectors
- [ ] Add retry decorator for selector failures
- [ ] Implement multi-tier selector fallbacks
- [ ] Add form field validation before submission
- [ ] Handle NLA popup more robustly
- [ ] Test with 5+ real job postings

### Phase 4 (Polish) - Robustness
- [ ] Add error message capture from form validation
- [ ] Implement multi-step form handling
- [ ] Add support for custom form controls (sliders, etc.)
- [ ] Performance optimization
- [ ] Final integration test with orchestrator

---

## References

- **Naukri Recommended Jobs**: https://www.naukri.com/mnjuser/recommendedjobs
- **SelectorValidator**: `scripts/common_stuff/naukri_selector_discovery.py`
- **E2E Test Runner**: `scripts/tests/naukri_e2e_test.py`
- **Form Filler**: `scripts/cookie_management_login/naukri_form_filler.py`

---

## Next Steps

1. **Run E2E test** to validate current selectors: `python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed`
2. **Review test report** and identify which selectors are failing
3. **Update selectors** in `naukri_form_filler.py` based on test findings
4. **Re-run test** to verify fixes
5. **Test end-to-end** with real job applications (dry-run first)
