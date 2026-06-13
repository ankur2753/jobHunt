# KNOWN BUGS & LIMITATIONS

Related: [[PROJECT_MAP]] | [[ARCHITECTURE]] | [[COMPONENTS]]

> This file tracks active bugs, known limitations, and unimplemented stubs.
> Update status when a bug is fixed or a feature is implemented.

---

## Critical Bugs

### BUG-001: LinkedIn Job Scraper Broken
**Status**: ❌ Open  
**Severity**: High  
**Source**: git commit `199a4e5` — "Able to login using cookie, Still failing to scrape jobs"

**Symptom**: LinkedIn cookie login succeeds but `linkedin_job_scraper.py` fails to scrape job listings.

**Likely Cause**: LinkedIn has anti-scraping measures that block automated navigation after login. The job search page or job card selectors have changed.

**Affected Files**:
- `scripts/job_scraping/linkedin_job_scraper.py`
- `scripts/orchestrator/orchestrator.py` (Workflow 3 / choice '3')

**Workaround**: Use LinkedIn's native job search manually; use Naukri for automated scraping.

**To Investigate**:
1. Run with headed browser: check what page loads after job search
2. Inspect selectors against current LinkedIn HTML
3. Check for bot-detection CAPTCHA or redirect

---

### BUG-002: Naukri Auto-Apply Not Validated on Live Site
**Status**: ⚠️ Unverified  
**Severity**: High  
**Source**: `Instructions/IMPLEMENTATION_SUMMARY.md` — "Not tested on real Naukri jobs yet"

**Symptom**: All 6 phases of Naukri implementation are complete in code, but no live end-to-end run has been validated against real Naukri job postings.

**Risk Areas** (from `NAUKRI_SELECTOR_ANALYSIS.md`):
- `h1.jobTitle` CSS class selector is fragile (may not match current Naukri DOM)
- Submit button detection may miss Naukri's actual button structure
- NLA popup handling may close wrong elements or miss actual NLA popups

**To Validate**:
```bash
python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed
# Check logs/naukri_selector_validation_*.json for PASS/FAIL
```

---

### BUG-003: Multi-Step Naukri Forms Not Handled
**Status**: ❌ Open (planned Phase 7)  
**Severity**: Medium  
**Source**: `IMPLEMENTATION_SUMMARY.md` — "Multi-step forms — Not yet handled"

**Symptom**: If a Naukri job application has multiple pages (Next → Next → Submit), the automation fills only the first page and fails to proceed.

**Affected Files**:
- `scripts/cookie_management_login/naukri_form_filler.py`
- `scripts/common_stuff/chatbot_form_filler.py`

**Current Selector**: `button[data-qa="nxtBtn"], button:has-text("Next")` — defined but not wired into form loop.

**Fix Plan**: Detect "Next" button after form fill; click and loop until Submit is the only remaining button.

---

## Medium Bugs

### BUG-004: NLA Popup Selector Not Specific Enough
**Status**: ⚠️ Open  
**Severity**: Medium  
**Source**: `NAUKRI_SELECTOR_ANALYSIS.md`

**Symptom**: `_close_nla_popups()` uses generic selectors (`button[aria-label="Close"]`) which may close unrelated modals or miss Naukri's specific NLA popup overlay.

**Affected File**: `scripts/cookie_management_login/naukri_form_filler.py` → `_close_nla_popups()`

**Fix**: Use Naukri-specific selectors like `[data-qa="nlaModal"]` or `.nextLevelAutomation`. Requires inspection of Naukri's actual popup DOM.

---

### BUG-005: LinkedIn Apply Uses Legacy JSON Instead of Vector DB
**Status**: ⚠️ Open (tech debt)  
**Severity**: Medium  
**Source**: `scripts/orchestrator/orchestrator.py` lines 215-229

**Symptom**: LinkedIn apply flow reads `job_prefrences.json` and `user_details.json` (legacy flat files). If these files are missing, the orchestrator aborts with a warning instead of using the vector DB.

**Affected File**: `scripts/orchestrator/orchestrator.py` — choice `'2'`, `website_choice == '1'` branch

**Fix**: Replace legacy JSON reads with `VectorDBManager.answer_question()` calls, consistent with Naukri flow.

---

### BUG-006: Company Name Selector Fails on Some Naukri Pages
**Status**: ⚠️ Open (partially mitigated)  
**Severity**: Low  
**Source**: `NAUKRI_SELECTOR_ANALYSIS.md`

**Symptom**: `[data-qa="jobCardCompanyName"]` doesn't exist on all Naukri job detail pages, causing an exception before applying.

**Mitigation**: Phase 5 made company name optional — `_extract_job_details()` wraps it in try/except. May still log errors.

**Affected File**: `scripts/cookie_management_login/naukri_form_filler.py` → `_extract_job_details()`

---

### BUG-007: InstaHyre Entirely Unimplemented
**Status**: ❌ Stub only  
**Severity**: Low  
**Source**: `scripts/orchestrator/orchestrator.py` line 178 — `print("Coming soon!")`

**Symptom**: Selecting InstaHyre (option 3) in the orchestrator immediately returns without doing anything.

**Affected Files**:
- `scripts/orchestrator/orchestrator.py`
- `scripts/cookie_management_login/instahyre_login.py` (login only, no apply/scrape)

---

### BUG-008: Resume Modifier Not Integrated
**Status**: ❌ Not integrated  
**Severity**: Low  

**Symptom**: `scripts/orchestrator/resume_modifier.py` exists but is not called from the orchestrator menu. Personalized resume generation is not part of any active workflow.

---

## Minor / Low Priority

### BUG-009: Form Validation Errors Not Captured
**Status**: ⚠️ Open  
**Severity**: Low  
**Source**: `NAUKRI_SELECTOR_ANALYSIS.md`

**Symptom**: When Naukri shows form validation errors (red inline messages), the system doesn't detect them and may proceed to submit with invalid data.

**Fix**: Add selector for error elements: `.error, [role="alert"], .validation-error` and check before submit.

**Affected File**: `scripts/cookie_management_login/naukri_form_filler.py` → `_submit_form()`

---

### BUG-010: Pattern Learner Not Integrated
**Status**: ❌ Scaffolded only  
**Severity**: Low  

**Symptom**: `scripts/common_stuff/pattern_learner.py` exists but is not called from the form filler. User-corrected answers during manual fallback are not persisted back to the vector DB for future use.

**Affected Files**:
- `scripts/common_stuff/pattern_learner.py`
- `scripts/common_stuff/chatbot_form_filler.py`

---

### BUG-011: Port Lock May Stale on Crash
**Status**: ⚠️ Known edge case  
**Severity**: Low  

**Symptom**: If the orchestrator process crashes (not a clean exit), `port_info.json` isn't deleted. A new run within 300 seconds will see a valid lock and refuse to start.

**Workaround**: Manually delete `scripts/common_stuff/port_info.json` if orchestrator won't start after a crash.

**Affected File**: `scripts/orchestrator/orchestrator.py` → `get_lock()` / `release_lock()`

---

## Planned Future Work

| ID | Feature | Priority | Phase |
|----|---------|----------|-------|
| FEAT-01 | Multi-step Naukri form navigation | High | Phase 7 |
| FEAT-02 | Full MCP tool integration (3 tools) | High | Phase 8 |
| FEAT-03 | LLM fallback for confidence < 0.50 | High | Phase 9 |
| FEAT-04 | Telegram bot human-fallback alerts | Medium | Future |
| FEAT-05 | InstaHyre job scraping + apply | Medium | Future |
| FEAT-06 | Parallel job processing | Medium | Future |
| FEAT-07 | Analytics dashboard | Low | Future |
| FEAT-08 | Dynamic selector discovery on failure | Medium | Future |
| FEAT-09 | Custom form controls (sliders, toggles) | Medium | Future |
| FEAT-10 | Screenshot capture on form fill failure | Low | Future |
| FEAT-11 | Cover letter customization per job | High | Future |

---

## Bug Reporting Checklist

When reporting a new bug, include:

```
### BUG-XXX: Title
**Status**: ❌ Open / ⚠️ Partial / ✅ Fixed
**Severity**: Critical / High / Medium / Low
**Symptom**: What happens
**Affected Files**: file:line
**Steps to Reproduce**:
1. ...
**Fix / Workaround**: ...
```
