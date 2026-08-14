# WORKFLOWS — Execution Flows

Related: [[PROJECT_MAP]] | [[ARCHITECTURE]] | [[COMPONENTS]]

---

## Workflow 1: Initial Setup

One-time setup before any automation can run.

```
1. Install dependencies
   pip install -r config/requirements.txt
   playwright install chromium

2. Fill personal profile
   → Open setup.html in browser
   → Complete all fields (name, skills, experience, salary, etc.)
   → Click "Generate Script" → saves setup_data.py

3. Populate vector database
   python setup_data.py
   → Inserts profile data into ChromaDB at vector_db/

4. Run orchestrator to log in and save cookies
   python scripts/orchestrator/orchestrator.py
   → Select portal → Log in manually → Cookies auto-saved
```

## Workflow 5: 1-Page A4 Resume & Cover Letter Tailoring ([[RESUME_TAILORING_ENGINE]])

```
User (Telegram Chat or CLI)
  → Send Job URL or Job Description Text
        ↓
  scripts/cli_tailor.py --url "<URL>" --json (or --jd-text)
        ↓
  1. Playwright Scraping: DOM innerText extraction (domcontentloaded + 3s render delay)
        ↓
  2. Provider-Agnostic LLM Query (llm_fallback.py):
     - Checks GEMINI_API_KEY -> OPENAI_API_KEY -> OPENROUTER_API_KEY -> LLM_API_KEY
     - Extracts Must Have / Nice To Have skills
     - Tailors master resume bullets (Senior QA Engineer + GET + Deloitte + 2 Projects)
     - Formats 1-page A4 executive HTML
        ↓
  3. Playwright PDF Engine:
     - Applies A4 page budget CSS (9.5pt font, 1.42 line height, 14px section margin)
     - Renders Ankur_Kumar_[Company]_Resume.pdf (~92% page height)
     - Renders Ankur_Kumar_[Company]_Cover_Letter.pdf
        ↓
  4. Returns JSON Schema Output:
     - status: "success"
     - resume_pdf: path to Resume PDF
     - cover_letter_pdf: path to Cover Letter PDF
     - linkedin_dm: recruiter outreach message text
        ↓
  5. Telegram Bot Handler (telegram_bot_sample.py):
     - Uploads Resume & Cover Letter PDF documents into Telegram chat
     - Sends LinkedIn DM message
```

---

## Workflow 2: Naukri Auto-Apply (Primary Flow)

```
python scripts/orchestrator/orchestrator.py
  → Select: 2 (Naukri)
  → Checks cookie login → auto-login or prompt manual
  → Select: 2 (Apply on job portals)
  → Enter max_jobs (default: 5)

  ┌─ NaukriJobApply.apply_to_recommended_jobs(max_jobs) ─┐
  │                                                       │
  │  Navigate to /mnjuser/recommendedjobs                 │
  │  → SelectorValidator validates page selectors         │
  │  → Collect job cards [data-qa="jobTuple"]             │
  │                                                       │
  │  For each job card:                                   │
  │    → Extract job title, URL                           │
  │    → @retry_async: find & click apply button          │
  │    → Wait for form to load (20s timeout)              │
  │    → Init NaukriFormFiller                            │
  │         → _close_nla_popups()                        │
  │         → ChatbotFormFiller.detect_questions()        │
  │         → For each question:                          │
  │              VectorDBManager.answer_question()        │
  │              If confidence >= 0.70: auto-fill         │
  │              If confidence < 0.70: prompt user        │
  │         → AnswerValidators.normalize(answer)          │
  │         → Playwright fills field                      │
  │         → _submit_form() (multi-tier button detect)   │
  │                                                       │
  │  Return results dict                                  │
  └───────────────────────────────────────────────────────┘

  Print summary: total_attempted, successful, failed, skipped
```

---

## Workflow 3: LinkedIn Auto-Apply

```
python scripts/orchestrator/orchestrator.py
  → Select: 1 (LinkedIn)
  → Checks cookie login → auto-login or prompt manual
  → Select: 2 (Apply on job portals)
  → Enter job title, location, max_applications

  LinkedInJobApply.apply_to_jobs(job_title, location)
  → Search LinkedIn jobs
  → Find Easy Apply buttons
  → Click and fill forms
  → Submit

  ⚠️ Status: Partial — see [[KNOWN_BUGS]] BUG-002
```

---

## Workflow 4: Form Fill Only (Direct URL)

Use this when you have a specific job URL and want to fill only the form.

```
python scripts/orchestrator/orchestrator.py
  → Select portal (1=LinkedIn or 2=Naukri)
  → Select: 4 (Auto-fill forms)
  → Paste job URL
  → Select mode:
       1 = Dry-run (detect questions, no fill)
       2 = Auto-fill with human fallback (recommended)
       3 = Auto-fill and submit

OR via test script:
  python scripts/tests/test_real_job_posting.py \
    --url "https://www.naukri.com/job-details-..." \
    --portal naukri \
    --dry-run
```

---

## Workflow 5: LinkedIn Cold Messaging

```
python scripts/orchestrator/orchestrator.py
  → Select: 1 (LinkedIn)
  → Select: 1 (Send cold messages)
  → Paste LinkedIn profile URLs (comma-separated)
  → Enter outreach context/reason

  LinkedInColdMessenger.send_bulk_outreach(profile_urls, reason)
  → Navigate to each profile
  → Click Connect / Message
  → Personalize message with user context
  → Send
```

---

## Workflow 6: Job Scraping (LinkedIn)

```
python scripts/orchestrator/orchestrator.py
  → Select: 1 (LinkedIn)
  → Select: 3 (Scrape jobs posted in last 24 hours)
  → Enter job title, location

  LinkedInJobScraper.scrape_jobs()
  → Navigates LinkedIn job search
  → Filters by date (last 24h)
  → Returns list of job postings

  ⚠️ Status: Broken — see [[KNOWN_BUGS]] BUG-001
```

---

## Workflow 7: E2E Test / Selector Validation

For debugging selector failures before a live run.

```bash
# Stage 1-3: Full Naukri flow validation
python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed

# Analyze output
cat logs/naukri_e2e_test_*.json | python -m json.tool
cat logs/naukri_selector_validation_*.json | python -m json.tool

# Run unit tests
cd /home/ankurkumar/ankur_code/agent
source .venv/bin/activate
python -m pytest scripts/tests/test_chatbot_form_filler.py -v  # 41 tests
python -m pytest scripts/tests/test_semantic_matching.py -v    # 18 tests
python -m pytest scripts/tests/test_form_filling.py -v         # 10 tests
```

---

## Workflow 8: Add New Personal Data to Vector DB

When you want the system to learn a new answer (e.g., updated salary expectation).

```python
# Option A: Via vector_db_manager directly
from scripts.common_stuff.vector_db_manager import VectorDBManager
db = VectorDBManager()
db.add_answer(
    question="What is your expected salary?",
    answer="18-22 LPA",
    category="salary"
)

# Option B: Via MCP tool (when implemented)
# answer_chatbot_question_manual(question, answer, category, store_for_future=True)

# Option C: Re-run setup
# Edit setup.html data → regenerate setup_data.py → python setup_data.py
```

---

## Confidence Threshold Decision Tree

```
Question detected
    ↓
VectorDB.answer_question(question)
    ↓
confidence >= 0.90? → Auto-fill silently ✅
    ↓ No
confidence >= portal_threshold (0.70/0.65)?
    → Auto-fill + log ✅
    ↓ No
confidence >= 0.50?
    → Show to user with suggestion
    → User: Enter/Accept/Skip
    ↓ No
confidence < 0.50?
    → Prompt user for answer
    → Store in session for future questions
```

---

## MCP Tool Invocation Flow (Claude Desktop)

```
User asks Claude Desktop to apply to a job
    ↓
Claude calls MCP tool: apply_to_naukri_jobs(max_jobs=3)
    ↓
mcp_server.py receives call
    ↓
Connects to running browser via port_info.json WebSocket endpoint
    ↓
Triggers NaukriJobApply.apply_to_recommended_jobs()
    ↓
Returns results to Claude
    ↓
Claude reports summary to user
```
