# Naukri Auto-Apply: Quick Reference

**Last Updated**: April 23, 2026  
**Implementation Status**: ✅ Complete (6 phases)  
**Ready for**: Real-world testing & validation

---

## 📋 What Was Done

| Phase | Component | Status | Files |
|-------|-----------|--------|-------|
| 1 | Selector Discovery | ✅ | `naukri_selector_discovery.py` |
| 2 | Logging & Diagnostics | ✅ | `naukri_job_apply.py` (enhanced) |
| 3 | E2E Test Framework | ✅ | `naukri_e2e_test.py` |
| 4 | Selector Gap Analysis | ✅ | `NAUKRI_SELECTOR_ANALYSIS.md` |
| 5 | Selector Improvements | ✅ | `naukri_form_filler.py` (enhanced) |
| 6 | Retry & Error Handling | ✅ | `retry_utils.py`, `naukri_job_apply.py` |

---

## 🚀 Quick Start

### Test on Real Naukri Site
```bash
# Must be logged into Naukri first
python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed
```

**What it does:**
- Stage 1: Navigate to recommended jobs, collect job cards
- Stage 2: Validate job card structure (title, apply button)
- Stage 3: Click apply on first job, detect form
- Generates JSON reports to `logs/` directory

### Test Form Filling (Dry-Run)
```bash
# Get a Naukri job URL, then run:
python scripts/tests/test_real_job_posting.py --portal naukri \
  --url "https://www.naukri.com/jobs/..." --dry-run
```

### Full Auto-Apply via Orchestrator
```bash
python scripts/orchestrator/orchestrator.py
# Menu: Select 2 (Naukri) → 2 (Apply to jobs)
```

---

## 📁 New/Modified Files

### New Files (5)
- `scripts/common_stuff/naukri_selector_discovery.py` — Selector validation
- `scripts/tests/naukri_e2e_test.py` — End-to-end test runner
- `scripts/common_stuff/retry_utils.py` — Retry decorators
- `Instructions/NAUKRI_SELECTOR_ANALYSIS.md` — Detailed analysis
- `Instructions/IMPLEMENTATION_SUMMARY.md` — Full summary

### Enhanced Files (2)
- `scripts/job_scraping/naukri_job_apply.py` — Validation + retry logic
- `scripts/cookie_management_login/naukri_form_filler.py` — Better selectors + validation

---

## 🔍 Key Features Implemented

### 1. Selector Discovery
```python
validator = SelectorValidator(page)
await validator.validate_all_selectors()
validator.print_summary()
validator.export_report()  # → logs/naukri_selector_validation_*.json
```

### 2. Better Selectors (Multi-Tier Fallbacks)
```python
# OLD: Single selector (fragile)
'job_title': 'h1.jobTitle'

# NEW: Fallback chain (resilient)
'job_title': '[data-qa="jobDetailTitle"], h1.jobTitle, h1[data-qa="jobTitle"]'
```

### 3. Retry Logic
```python
@retry_async(max_attempts=3, backoff=2, initial_delay=1)
async def click_apply():
    button = await page.query_selector('button[...]')
    await button.click()
```

### 4. Enhanced Validation
- Required field detection
- Error message capture
- Better NLA popup handling
- Visibility/enabled checks

---

## ✅ Success Indicators

**E2E Test Passes When:**
- ✅ Collects 10+ job cards from recommended page
- ✅ All job cards have apply buttons
- ✅ Clicking apply loads form (detected in 20s timeout)
- ✅ Form fields are detected
- ✅ No crashes during any stage

**Auto-Apply Works When:**
- ✅ Processes 3+ jobs without errors
- ✅ Form questions detected (5+)
- ✅ Semantic matching matches 50%+ questions
- ✅ No selector failures on job pages
- ✅ Validation prevents bad submissions

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| E2E test crashes on Stage 1 | Naukri layout may have changed. Review selector report. |
| Form not detected on Stage 3 | Increase `FORM_LOAD_TIMEOUT` from 20s to 30s. |
| Apply button not found | Check if Naukri changed `data-qa` attribute. |
| Form validation fails | Run with `--headed` flag to see what's happening. |
| Selector report shows failures | Update `NAUKRI_SELECTORS` dict with new selectors. |

---

## 📊 Diagnostic Outputs

### Selector Validation Report
```json
{
  "timestamp": "2026-04-23T...",
  "categories": {
    "job_cards": {
      "status": "pass|partial|fail",
      "selectors": {
        "job_cards_primary": {
          "selector": "[data-qa=\"jobTuple\"]",
          "found": true,
          "count": 25,
          "visible_count": 20
        }
      }
    }
  }
}
```

### E2E Test Report
```json
{
  "timestamp": "2026-04-23T...",
  "stages": {
    "stage_1": {
      "success": true,
      "job_cards_found": 25
    },
    "stage_2": {
      "jobs_processed": 3,
      "jobs_with_apply_button": 3
    },
    "stage_3": {
      "forms_detected": 1,
      "form_elements_found": 8
    }
  }
}
```

---

## 🎯 Next Steps

1. **Run E2E Test** on live Naukri site
   - Identify any selector mismatches
   - Capture actual HTML for debugging
   
2. **Run Real Form Test** (dry-run)
   - Verify form question detection
   - Check semantic matching
   
3. **Run Full Auto-Apply** on 1-2 jobs
   - Test complete workflow
   - Verify form submission works
   
4. **Monitor & Iterate**
   - Collect diagnostics from real runs
   - Update selectors if Naukri changes UI
   - Improve semantic matching if needed

---

## 📞 API Reference

### SelectorValidator
```python
validator = SelectorValidator(page, enable_logging=True)
await validator.validate_all_selectors()  # Returns Dict[str, SelectorCategory]
validator.print_summary()  # Pretty print
report = validator.export_report()  # JSON file path
```

### NaukriJobApply
```python
applier = NaukriJobApply(page, vector_db, enable_selector_validation=True)
results = await applier.apply_to_recommended_jobs(max_jobs=5)
diagnostics = applier.get_diagnostics()
applier.export_diagnostics()
```

### NaukriE2ETestRunner
```bash
python scripts/tests/naukri_e2e_test.py \
  --max-jobs 3 \
  --headless \
  --verbose
```

### retry_utils
```python
@retry_async(max_attempts=3, backoff=2, initial_delay=1)
async def my_operation():
    pass

await retry_until_visible(page, selector, max_attempts=5)
await retry_until_enabled(page, selector, max_attempts=5)
```

---

## 📚 Documentation Files

- [NAUKRI_SELECTOR_ANALYSIS.md](NAUKRI_SELECTOR_ANALYSIS.md) — Detailed selector audit + recommendations
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) — Complete implementation details
- [README.md](README.md) — Project overview

---

## 💡 Tips

- Always run with `--headed` flag first to debug visually
- Use `--verbose` flag for detailed logging
- Check `logs/` directory for generated reports after tests
- If selectors fail, check `logs/naukri_selector_validation_*.json`
- Test on 1-2 jobs first before scaling to 10+

---

**Ready to Test? Start here:**
```bash
python scripts/tests/naukri_e2e_test.py --max-jobs 1 --headed
```
