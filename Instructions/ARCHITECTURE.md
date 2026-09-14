# ARCHITECTURE - Three-layer system design

Related: [[PROJECT_MAP]] | [[COMPONENTS]] | [[WORKFLOWS]]

---

## Overview

The system separates concerns across three tiers. The scripted path runs first. If it fails, the system invokes the LLM. If the LLM fails, it prompts the human user.

```text
┌─────────────────────────────────────────────────────┐
│  Layer 3: Agent / LLM                               │
│  MCP-compatible Agent (e.g., Hermes, Claude)        │
│  Role: Problem-solving, context handover            │
└──────────────────────┬──────────────────────────────┘
                       │ fallback / error resolution
┌──────────────────────▼──────────────────────────────┐
│  Layer 2: Orchestrator                              │
│  scripts/orchestrator/orchestrator.py               │
│  Role: Sequence tasks, route errors, lock mgmt      │
│  Also: mcp_server.py exposes tools to LLM           │
└──────────────────────┬──────────────────────────────┘
                       │ invokes tools
┌──────────────────────▼──────────────────────────────┐
│  Layer 1: Scripts / Tools                           │
│  Playwright automation scripts per portal           │
│  Role: Repetitive browser actions                   │
└──────────────────────┬──────────────────────────────┘
                       │ drives browser
                  Chromium Browser
                  (Naukri, LinkedIn, InstaHyre)
```

---

## Failure escalation path

```text
Script fails
    → Orchestrator retries (retry_utils.py @retry_async)
    → Still fails → Pass context to LLM Agent (via MCP)
    → LLM resolves or applies fix
    → Still fails → Notify user via Telegram bot
    → User intervenes manually
```

---

## Layer 1: Scripts and tools

Each script is a Playwright automation module.

### Key design principles
- **Async-first**. All scripts use `async/await` with `playwright.async_api`.
- **Selector resilience**. Multi-tier `data-qa`, CSS, and text fallback chains.
- **Retry on failure**. `@retry_async` decorator from `retry_utils.py`.
- **Cookie-based auth**. Sessions stored in `personal_details/*_cookies.json`.

### Portal script map

| Portal | Login | Job Scrape | Job Apply | Form Fill |
|--------|-------|------------|-----------|-----------|
| Naukri | `naukri_login.py` | `naukri_job_apply.py` | `naukri_job_apply.py` | `naukri_form_filler.py` |
| LinkedIn | `orchestrator.py` (LinkedInPlaywright) | `linkedin_job_scraper.py` | `linkedin_job_apply.py` | `linkedin_form_filler.py` |
| InstaHyre | `instahyre_login.py` | — | — | — |

---

## Layer 2: Orchestrator

**File**: `scripts/orchestrator/orchestrator.py`

### Responsibilities
1. Acquire and release file lock (`port_info.json`). This prevents concurrent browser instances.
2. Present CLI menu.
3. Initialize the correct portal browser manager.
4. Call layer 1 scripts in sequence.
5. Handle exceptions and surface results.

### Lock mechanism
```python
# port_info.json is used as a lock file
# lock expires after 300 seconds (LOCK_EXPIRY)
get_lock()  # must call before any action
release_lock()  # always called in finally block
```

### MCP Server (`mcp_server.py`)
- Exposes automation as MCP tools.
- Any MCP-compatible agent can call these tools directly.
- Allows LLM to trigger `check_linkedin_login`, `apply_to_jobs`, etc.

---

## Layer 3: Agent and LLM

**Current state**: MCP server is partially built (`mcp_server.py`). Full LLM fallback loop is not yet wired.

### Planned capability
- Receive failed-script context from orchestrator.
- Use MCP tools and browser access to solve the issue.
- Apply fix and signal orchestrator to resume.
- If unresolvable, trigger Telegram human-fallback.

### MCP tools spec

| Tool | Inputs | Purpose |
|------|--------|---------|
| `auto_fill_naukri_form` | `max_questions`, `confidence_threshold`, `dry_run` | Auto-fill all form questions |
| `get_answer_for_question` | `question`, `n_candidates` | Get top answer candidates |
| `answer_chatbot_question_manual` | `question`, `answer`, `category` | Manually teach system |

---

## Telegram bot integration

The system includes a central gateway via Telegram for interaction and notifications. It uses `redis_gateway.py` and `my-personal-tg-bot`.

### Current state
- **Bot and Redis gateway**. When a user triggers an action from the Telegram bot, `redis_gateway.py` consumes requests from the `agent.job-hunt.requests` Redis stream. It spawns the script, gathers the response, and publishes a `JOB_HUNT_RESPONSE` envelope to the `agent.job-hunt.responses` Redis stream.
- **Draft queue**. Actions like bulk referral drafting save messages locally to `personal_details/pending_referrals.json` and `jobs_database.csv`.

### Planned enhancements
Currently, if a user manually triggers a task via the CLI, there is no automated notification pushed to the Telegram bot. To bridge CLI executions with Telegram notifications, we plan to add:
1. **Redis notifier component**. A utility in `scripts/common_stuff/redis_notifier.py` to handle pushing `MessageEnvelope` payloads to the `agent.job-hunt.responses` Redis topic.
2. **CLI hooks**. Scripts will invoke the Redis notifier upon job completion and construct the drafted message summary.
3. **Graceful failback**. The notifier will wrap Redis connections in `try/except` blocks to fail silently if the Redis server or bot is not running. This ensures CLI tasks can run independently offline.

---

## Semantic matching subsystem

The form-filling intelligence lives in `common_stuff/`:

```text
chatbot_form_filler.py
    └── detect form questions (3-level: label → placeholder → aria-label)
    └── for each question:
            vector_db_manager.py.answer_question(question)
                └── SentenceTransformer encodes question
                └── ChromaDB cosine similarity search
                └── Returns: answer + confidence score
            answer_validators.py.normalize(answer, field_category)
                └── Salary: "12-15 LPA" → "12-15"
                └── Experience: "5 years" → "5"
                └── Phone: "+91 98765" → "919876543210"
            Playwright fills field
```

### Confidence thresholds

| Score | Action | Portal |
|-------|--------|--------|
| ≥ 0.90 | Auto-fill silently | All |
| 0.70–0.89 | Auto-fill, log | Naukri |
| 0.65–0.79 | Auto-fill, log | LinkedIn |
| 0.50–0.64 | Prompt user with suggestion | All |
| < 0.50 | Skip, ask user | All |

---

## Data architecture

### Vector database (ChromaDB)
- **Path**: `vector_db/`
- **Collection**: Personal profile data (skills, experience, salary, preferences)
- **Manager**: `scripts/common_stuff/vector_db_manager.py`
- **Ingestion**: `setup_data.py` (generated from `setup.html`)
- **Query**: `answer_question(query_text)` → `AnswerCandidate(answer, confidence, source)`

### Legacy JSON (phasing out)
- `personal_details/user_details.json` - Flat user profile
- `personal_details/job_prefrences.json` - Job search preferences
- LinkedIn flow in orchestrator still reads these files. Naukri uses the vector DB.

### Session storage
- `personal_details/linkedin_cookies.json` - Playwright storage state
- `personal_details/naukri_cookies.json` - Playwright storage state
- `scripts/common_stuff/port_info.json` - Runtime lock and WebSocket endpoint

---

## Concurrency model

- **Single Playwright instance**. The system enforces one browser session at a time using a lock file.
- **WebSocket endpoint**. Stored in `port_info.json`.
- **MCP tools**. Tools can connect to the existing browser via the stored WS endpoint.
- The system processes one job at a time. It does not run parallel jobs.

---

## Diagnostics

| Output | Location | When Generated |
|--------|----------|----------------|
| Selector validation JSON | `logs/naukri_selector_validation_*.json` | E2E test run |
| E2E test results JSON | `logs/naukri_e2e_test_*.json` | E2E test run |
| Python logging | stdout and file | Runtime |
| Form session report | In-memory dict | After each form fill |
