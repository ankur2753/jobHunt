# COMPONENTS — Script & Module Reference

Related: [[PROJECT_MAP]] | [[ARCHITECTURE]] | [[WORKFLOWS]]

---

## Orchestrator Layer

### `scripts/orchestrator/orchestrator.py`
**Role**: Main CLI entry point for all automation.

- Presents portal selection menu (LinkedIn / Naukri / InstaHyre)
- Presents action menu (apply, scrape, cold message, form fill)
- Manages browser lifecycle: setup, login check, teardown
- Owns the file lock (`port_info.json`) via `get_lock()` / `release_lock()`
- Contains `LinkedInPlaywright` class (handles LinkedIn session inline)
- Delegates to `NaukriPlaywright`, `LinkedInJobApply`, `NaukriJobApply`, etc.

**Key classes/functions**:
- `LinkedInPlaywright` — cookie-based login, session save
- `get_lock()` / `release_lock()` — 5-min expiry file lock
- `main()` — async entry point with full menu flow

---

### `scripts/orchestrator/mcp_server.py`
**Role**: MCP protocol server exposing automation tools to Claude Desktop.

- Allows LLM to invoke automation without running CLI manually
- Tools: check login, apply to jobs, scrape jobs (partial implementation)
- Connects to existing browser via WebSocket endpoint from `port_info.json`

---

### `scripts/orchestrator/resume_modifier.py`
**Role**: LLM-powered resume customization per job posting.

- Uses personal data to tailor resume/cover letter for specific jobs
- Status: Partially implemented

---

## Common Utilities

### `scripts/common_stuff/chatbot_form_filler.py` (~514 LOC)
**Role**: Core form detection and filling logic shared across portals.

- Detects form questions via 3-level strategy:
  1. HTML `<label for="...">` mapping
  2. `placeholder` attribute extraction
  3. `aria-label` attribute detection
- Supports 8 field types: text, number, email, select, radio, checkbox, textarea, date
- Calls `vector_db_manager.answer_question()` for semantic matching
- Calls `answer_validators.normalize()` before filling
- Human fallback: prompts user when confidence < threshold
- Returns `FormSession` with stats: total, auto_filled, skipped, failed

---

### `scripts/common_stuff/answer_validators.py` (~380 LOC)
**Role**: Answer normalization for 9 field categories.

| Category | Input Example | Output |
|----------|--------------|--------|
| `SALARY` | "12-15 LPA" | "12-15" |
| `EXPERIENCE` | "5 years" | "5" |
| `LOCATION` | "Bangalore, India" | "Bangalore" |
| `NOTICE_PERIOD` | "30 days" | "30" |
| `PHONE` | "+91 98765 43210" | "919876543210" |
| `EMAIL` | email string | validates format |
| `DATE` | various formats | "YYYY-MM-DD" |
| `NAME` | string | trimmed |
| `GENERIC` | any | trimmed |

---

### `scripts/common_stuff/vector_db_manager.py`
**Role**: ChromaDB interface for personal profile semantic search.

- Manages ChromaDB collection at `vector_db/`
- `answer_question(query)` → `AnswerCandidate(answer_text, confidence, source)`
- `add_answer(question, answer, category)` — learns new Q&A pairs
- Uses `sentence-transformers/all-MiniLM-L6-v2` for embeddings
- Extended with `answer_question()` method during Phase 2

---

### `scripts/common_stuff/retry_utils.py` (~250 LOC)
**Role**: Retry decorators and helpers for Playwright async operations.

- `@retry_async(max_attempts, backoff, initial_delay)` — exponential backoff decorator
- `retry_until_visible(page, selector, timeout)` — wait for element visibility
- `retry_until_enabled(page, selector, timeout)` — wait for element to be enabled
- `RetryException` — custom exception class

```python
@retry_async(max_attempts=3, backoff=2, initial_delay=1)
async def click_apply_button(page):
    button = await page.query_selector('button[data-qa="nxtApplyBtn"]')
    await button.click()
```

---

### `scripts/common_stuff/naukri_selector_discovery.py` (~380 LOC)
**Role**: Runtime selector validation for Naukri pages.

- `SelectorValidator` class: probes live pages for selector health
- Exports timestamped JSON reports to `logs/`
- Used by E2E test runner to check selector pass/fail
- Reports: HTML samples, working/broken selectors, fallback recommendations

---

### `scripts/common_stuff/pattern_learner.py`
**Role**: Learns patterns from user corrections to improve future form filling.

- Stores corrected Q&A pairs
- Status: Scaffolded, not fully integrated

---

### `scripts/common_stuff/connect_mcp.py`
**Role**: Helper to connect to existing browser session via WebSocket.

---

### `scripts/common_stuff/login_linkedin.py`
**Role**: Standalone LinkedIn login utility.

---

### `scripts/common_stuff/open_browser.py`
**Role**: Utility to open a Playwright browser with standard settings.

---

## Login / Cookie Management

### `scripts/cookie_management_login/naukri_login.py`
**Role**: `NaukriPlaywright` class — Naukri session management.

- Cookie-based login (`naukri_cookies.json`)
- `is_logged_in()` — checks session validity
- `login_manually_and_save()` — opens browser for manual login, saves cookies

---

### `scripts/cookie_management_login/instahyre_login.py`
**Role**: `InstahyrePlaywright` class — InstaHyre session management.

- Cookie-based login only; no apply/scrape implemented yet

---

### `scripts/cookie_management_login/naukri_form_filler.py` (~463 LOC)
**Role**: Naukri-specific form filling orchestration.

- Wraps `ChatbotFormFiller` with Naukri-specific selectors and flow
- Default confidence threshold: **0.70** (stricter)
- Handles NLA popup closing (`_close_nla_popups()`)
- Multi-tier submit button detection
- `fill_naukri_job_application(job_url, dry_run, allow_human_input, submit_form)`
- `get_session_report()` — returns form stats dict

**NAUKRI_SELECTORS** dictionary:

| Key | Selector | Stability |
|-----|----------|-----------|
| `job_title_heading` | `[data-qa="jobDetailTitle"], h1.jobTitle, ...` | Medium |
| `company_name` | `[data-qa="jobCardCompanyName"], ...` | Medium |
| `apply_button` | `button[data-qa="nxtApplyBtn"]` | High |
| `chatbot_form_container` | `.filler-container, .customFields, ...` | High |
| `submit_button` | `button[type="submit"], button[data-qa="submit"]` | Medium |

---

### `scripts/cookie_management_login/linkedin_form_filler.py` (~465 LOC)
**Role**: LinkedIn-specific form filling orchestration.

- Default confidence threshold: **0.65** (balanced)
- `fill_linkedin_job_application(job_url, ...)`
- `get_session_report()`

---

## Job Scraping & Application

### `scripts/job_scraping/naukri_job_apply.py`
**Role**: Navigate recommended jobs page, collect job cards, trigger apply.

- Goes to `https://www.naukri.com/mnjuser/recommendedjobs`
- Collects `[data-qa="jobTuple"]` job cards
- Integrates `SelectorValidator` for runtime validation
- Retries apply button click with multiple selectors
- Initializes `NaukriFormFiller` for each job
- `apply_to_recommended_jobs(max_jobs)` → results dict
- `get_diagnostics()` / `export_diagnostics()` — JSON logs

---

### `scripts/job_scraping/linkedin_job_apply.py`
**Role**: LinkedIn Easy Apply automation.

- `LinkedInJobApply(page)`
- `apply_to_jobs(job_title, location)` — searches and applies
- Status: Partial implementation

---

### `scripts/job_scraping/linkedin_job_scraper.py`
**Role**: Scrape LinkedIn job listings (last 24h).

- `LinkedInJobScraper(page, job_title, location)`
- `scrape_jobs()` — returns list of job postings
- **Status: Broken** (see [[KNOWN_BUGS]])

---

## Networking

### `scripts/networking/linkedin_cold_message.py`
**Role**: Automated cold outreach to LinkedIn profiles.

- `LinkedInColdMessenger(page)`
- `send_bulk_outreach(profile_urls, reason)` — sends personalized connection requests
- Status: Implemented and working

---

### `scripts/networking/linkedin_connect.py`
**Role**: LinkedIn connection request automation.

---

## Tests

### `scripts/tests/naukri_e2e_test.py`
**Role**: 3-stage E2E validation framework for Naukri.

- Stage 1: Navigate & collect job cards
- Stage 2: Validate job card elements & apply buttons
- Stage 3: Test apply click & form detection

```bash
python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed
python scripts/tests/naukri_e2e_test.py --max-jobs 5 --verbose
```

---

### `scripts/tests/test_chatbot_form_filler.py`
**Role**: 41 unit tests for `ChatbotFormFiller` and `AnswerNormalizer`.

---

### `scripts/tests/test_semantic_matching.py`
**Role**: 18 integration tests for vector DB semantic matching.

---

### `scripts/tests/test_form_filling.py`
**Role**: 10 integration tests for end-to-end form fill pipeline.

---

### `scripts/tests/test_real_job_posting.py`
**Role**: Test with an actual live job posting URL.

```bash
python scripts/tests/test_real_job_posting.py \
  --url "https://www.naukri.com/job-details-..." \
  --portal naukri --dry-run
```

---

### `scripts/tests/test_linkedin_apply.py`
**Role**: LinkedIn apply flow tests.

---

## Configuration & Data

### `config/requirements.txt`
```
playwright==1.58.0
pytest-playwright==0.4.4
python-dotenv==1.0.1
requests==2.31.0
beautifulsoup4==4.12.3
mcp>=1.0.0
chromadb==0.4.24
sentence-transformers==2.7.0
```

### `setup.html`
Browser-based form to collect personal details. Generates `setup_data.py` which populates the vector DB.

### `personal_details/` (legacy)
- `user_details.json` — flat profile (name, skills, experience, etc.)
- `job_prefrences.json` — target roles, locations, salary range
- `*_cookies.json` — Playwright session state files
