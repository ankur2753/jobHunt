# COMPONENTS - Script and module reference

Related: [[PROJECT_MAP]] | [[ARCHITECTURE]] | [[WORKFLOWS]]

---

## Orchestrator layer

### `scripts/orchestrator/orchestrator.py`
**Role**: CLI entry point.

- Presents portal selection menu (LinkedIn, Naukri, InstaHyre)
- Presents action menu (apply, scrape, cold message, form fill)
- Manages browser lifecycle: setup, login check, teardown
- Owns the file lock (`port_info.json`) via `get_lock()` and `release_lock()`
- Contains `LinkedInPlaywright` class (handles LinkedIn session inline)
- Delegates to `NaukriPlaywright`, `LinkedInJobApply`, `NaukriJobApply`, etc.

**Key classes and functions**:
- `LinkedInPlaywright`. Handles cookie-based login and session saves.
- `get_lock()` and `release_lock()`. Controls the 5-minute expiry file lock.
- `main()`. Async entry point with full menu flow.

---

### `scripts/orchestrator/mcp_server.py`
**Role**: MCP protocol server exposing automation tools.

- Allows LLM to invoke automation without running CLI manually.
- Tools: check login, apply to jobs, scrape jobs.
- Connects to existing browser via WebSocket endpoint from `port_info.json`.

---

### `scripts/orchestrator/resume_modifier.py`
**Role**: Legacy LLM-powered resume customization.

- Superseded by the new [[RESUME_TAILORING_ENGINE]] (`scripts/cli_tailor.py`).

---

## Resume and document automation engine ([[RESUME_TAILORING_ENGINE]])

### `scripts/cli_tailor.py`
**Role**: Standalone automation engine CLI and Python module.

- Scrapes job URLs (Playwright `domcontentloaded` fallback) or accepts raw JD text snippets.
- Interacts with provider-agnostic LLM fallback system (`scripts/common_stuff/llm_fallback.py`).
- Renders 1-page A4 resume PDF and cover letter PDF.
- Generates LinkedIn recruiter cold outreach DM text.
- Outputs clean JSON for Telegram bots and web APIs (`--json`).

---

### `scripts/common_stuff/llm_fallback.py`
**Role**: Provider-agnostic LLM query engine.

- Dynamically selects LLM provider based on environment variables:
  * `GEMINI_API_KEY` (Google Gemini)
  * `OPENAI_API_KEY` (OpenAI GPT-4o-mini)
  * `OPENROUTER_API_KEY` (OpenRouter)
  * `ANTHROPIC_API_KEY` (Anthropic Claude)
  * `LLM_API_KEY` + `LLM_BASE_URL` (Generic OpenAI endpoint, Ollama, vLLM, Groq, DeepSeek)

---

### `scripts/examples/telegram_bot_sample.py`
**Role**: Telegram Bot handler sample script.

- Listens for job URLs and descriptions in Telegram chat.
- Executes `cli_tailor.py --json` in a background subprocess.
- Uploads resume and cover letter PDF documents directly into Telegram chat.

---

### `prompts/`
**Role**: Prompt library.

- `job_analysis_prompt.md`. Extracts requirements.
- `resume_tailoring_prompt.md`. 1-page A4 resume tailoring system prompt.
- `cover_letter_prompt.md`. Technical cover letter prompt.
- `linkedin_outreach_prompt.md`. Cold DM prompt.
- `telegram_bot_prompt.md`. Telegram bot agent system prompt.

## Common utilities

### `scripts/common_stuff/chatbot_form_filler.py`
**Role**: Core form detection and filling logic.

- Detects form questions via 3-level strategy:
  1. HTML `<label for="...">` mapping
  2. `placeholder` attribute extraction
  3. `aria-label` attribute detection
- Supports 8 field types: text, number, email, select, radio, checkbox, textarea, date.
- Calls `vector_db_manager.answer_question()` for semantic matching.
- Calls `answer_validators.normalize()` before filling.
- Prompts user when confidence falls below threshold.
- Returns `FormSession` with stats on total, auto-filled, skipped, and failed fields.

---

### `scripts/common_stuff/answer_validators.py`
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

- Manages ChromaDB collection at `vector_db/`.
- `answer_question(query)` returns `AnswerCandidate(answer_text, confidence, source)`.
- `add_answer(question, answer, category)` saves new Q&A pairs.
- Uses `sentence-transformers/all-MiniLM-L6-v2` for embeddings.

---

### `scripts/common_stuff/retry_utils.py`
**Role**: Retry decorators and helpers for Playwright.

- `@retry_async(max_attempts, backoff, initial_delay)` handles exponential backoff.
- `retry_until_visible(page, selector, timeout)` waits for element visibility.
- `retry_until_enabled(page, selector, timeout)` waits for element to be enabled.
- `RetryException` defines custom exception class.

```python
@retry_async(max_attempts=3, backoff=2, initial_delay=1)
async def click_apply_button(page):
    button = await page.query_selector('button[data-qa="nxtApplyBtn"]')
    await button.click()
```

---

### `scripts/common_stuff/naukri_selector_discovery.py`
**Role**: Runtime selector validation for Naukri pages.

- `SelectorValidator` class probes live pages for selector health.
- Exports timestamped JSON reports to `logs/`.
- Used by E2E test runner to check selector pass and fail states.
- Reports HTML samples, working and broken selectors, and fallback recommendations.

---

### `scripts/common_stuff/pattern_learner.py`
**Role**: Learns patterns from user corrections.

- Stores corrected Q&A pairs.
- Status: Scaffolded, not fully integrated.

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

## Login and cookie management

### `scripts/cookie_management_login/naukri_login.py`
**Role**: `NaukriPlaywright` class for Naukri session management.

- Cookie-based login (`naukri_cookies.json`).
- `is_logged_in()` checks session validity.
- `login_manually_and_save()` opens browser for manual login and saves cookies.

---

### `scripts/cookie_management_login/instahyre_login.py`
**Role**: `InstahyrePlaywright` class for InstaHyre session management.

- Cookie-based login only.

---

### `scripts/cookie_management_login/naukri_form_filler.py`
**Role**: Naukri-specific form filling orchestration.

- Wraps `ChatbotFormFiller` with Naukri-specific selectors and flow.
- Default confidence threshold: 0.70.
- Handles NLA popup closing (`_close_nla_popups()`).
- Multi-tier submit button detection.
- Exposes `fill_naukri_job_application(job_url, dry_run, allow_human_input, submit_form)`.
- Exposes `get_session_report()`.

**NAUKRI_SELECTORS** dictionary:

| Key | Selector | Stability |
|-----|----------|-----------|
| `job_title_heading` | `[data-qa="jobDetailTitle"], h1.jobTitle` | Medium |
| `company_name` | `[data-qa="jobCardCompanyName"]` | Medium |
| `apply_button` | `button[data-qa="nxtApplyBtn"]` | High |
| `chatbot_form_container` | `.filler-container, .customFields` | High |
| `submit_button` | `button[type="submit"], button[data-qa="submit"]` | Medium |

---

### `scripts/cookie_management_login/linkedin_form_filler.py`
**Role**: LinkedIn-specific form filling orchestration.

- Default confidence threshold: 0.65.
- Exposes `fill_linkedin_job_application(job_url, ...)`.
- Exposes `get_session_report()`.

---

## Job scraping and application

### `scripts/job_scraping/naukri_job_apply.py`
**Role**: Navigate recommended jobs page, collect job cards, trigger apply.

- Goes to `https://www.naukri.com/mnjuser/recommendedjobs`.
- Collects `[data-qa="jobTuple"]` job cards.
- Integrates `SelectorValidator` for runtime validation.
- Retries apply button click with multiple selectors.
- Initializes `NaukriFormFiller` for each job.
- `apply_to_recommended_jobs(max_jobs)` returns results dict.
- Exposes `get_diagnostics()` and `export_diagnostics()`.

---

### `scripts/job_scraping/linkedin_job_apply.py`
**Role**: LinkedIn Easy Apply automation.

- Partial implementation.

---

### `scripts/job_scraping/linkedin_job_scraper.py`
**Role**: Scrape LinkedIn job listings.

- **Status: Broken** (see [[KNOWN_BUGS]]).

---

## Networking

### `scripts/networking/linkedin_cold_message.py`
**Role**: Automated cold outreach to LinkedIn profiles.

- Sends personalized connection requests via `send_bulk_outreach(profile_urls, reason)`.

---

### `scripts/networking/linkedin_connect.py`
**Role**: LinkedIn connection request automation.

---

## Tests

### `scripts/tests/naukri_e2e_test.py`
**Role**: 3-stage E2E validation framework for Naukri.

- Stage 1: Navigate and collect job cards.
- Stage 2: Validate job card elements and apply buttons.
- Stage 3: Test apply click and form detection.

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

## Configuration and data

### `config/requirements.txt`
```text
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
- `user_details.json` - Flat profile (name, skills, experience, etc.)
- `job_prefrences.json` - Target roles, locations, salary range
- `*_cookies.json` - Playwright session state files
