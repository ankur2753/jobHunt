# ARCHITECTURE — Three-Layer System Design

Related: [[PROJECT_MAP]] | [[COMPONENTS]] | [[WORKFLOWS]]

---

## Overview

The system separates concerns across three tiers so that the most reliable (scripted) path runs first, and progressively more expensive resources (LLM, human) are only invoked on failure.

```
┌─────────────────────────────────────────────────────┐
│  Layer 3: Agent / LLM                               │
│  Claude Desktop via MCP, or direct API call         │
│  Role: Dynamic problem-solving, context handover    │
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
│  Role: Repetitive deterministic browser actions     │
└──────────────────────┬──────────────────────────────┘
                       │ drives browser
                  Chromium Browser
                  (Naukri, LinkedIn, InstaHyre)
```

---

## Failure Escalation Path

```
Script fails
    → Orchestrator retries (retry_utils.py @retry_async)
    → Still fails → Pass context to LLM Agent (Claude via MCP)
    → LLM resolves or applies dynamic fix
    → Still fails → Notify user via Telegram bot
    → User intervenes manually
```

---

## Layer 1 — Scripts/Tools

Each script is a self-contained Playwright automation module.

### Key Design Principles
- **Async-first**: all scripts use `async/await` with `playwright.async_api`
- **Selector resilience**: multi-tier `data-qa` → CSS → text fallback chains
- **Retry on failure**: `@retry_async` decorator from `retry_utils.py`
- **Cookie-based auth**: sessions stored in `personal_details/*_cookies.json`

### Portal Script Map

| Portal | Login | Job Scrape | Job Apply | Form Fill |
|--------|-------|------------|-----------|-----------|
| Naukri | `naukri_login.py` | `naukri_job_apply.py` | `naukri_job_apply.py` | `naukri_form_filler.py` |
| LinkedIn | `orchestrator.py` (LinkedInPlaywright) | `linkedin_job_scraper.py` | `linkedin_job_apply.py` | `linkedin_form_filler.py` |
| InstaHyre | `instahyre_login.py` | — | — | — |

---

## Layer 2 — Orchestrator

**File**: `scripts/orchestrator/orchestrator.py`

### Responsibilities
1. Acquire/release file lock (`port_info.json`) — prevents concurrent browser instances
2. Present CLI menu: portal selection → action selection
3. Initialize correct portal browser manager
4. Call layer 1 scripts in sequence
5. Handle exceptions and surface results

### Lock Mechanism
```python
# port_info.json is used as a lock file
# lock expires after 300 seconds (LOCK_EXPIRY)
get_lock()  # must call before any action
release_lock()  # always called in finally block
```

### MCP Server (`mcp_server.py`)
- Exposes core automation as MCP tools
- Claude Desktop can call these tools directly
- Allows LLM to trigger `check_linkedin_login`, `apply_to_jobs`, etc.

---

## Layer 3 — Agent / LLM

**Current state**: MCP server is partially built (`mcp_server.py`). Full LLM fallback loop not yet wired.

### Planned Capability
- Receive failed-script context from Orchestrator
- Use MCP tools + browser access to dynamically solve the issue
- Apply fix and signal Orchestrator to resume
- If unresolvable: trigger Telegram human-fallback

### MCP Tools Spec (Chatbot Form Filler — Phase 4 planned)

| Tool | Inputs | Purpose |
|------|--------|---------|
| `auto_fill_naukri_form` | `max_questions`, `confidence_threshold`, `dry_run` | Auto-fill all form questions |
| `get_answer_for_question` | `question`, `n_candidates` | Get top answer candidates |
| `answer_chatbot_question_manual` | `question`, `answer`, `category` | Manually teach system |

---

## Semantic Matching Subsystem

The form-filling intelligence lives in `common_stuff/`:

```
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

### Confidence Thresholds

| Score | Action | Portal |
|-------|--------|--------|
| ≥ 0.90 | Auto-fill silently | All |
| 0.70–0.89 | Auto-fill, log | Naukri |
| 0.65–0.79 | Auto-fill, log | LinkedIn |
| 0.50–0.64 | Prompt user with suggestion | All |
| < 0.50 | Skip, ask user | All |

---

## Data Architecture

### Vector Database (ChromaDB)
- **Path**: `vector_db/`
- **Collection**: Personal profile data (skills, experience, salary, preferences)
- **Manager**: `scripts/common_stuff/vector_db_manager.py`
- **Ingestion**: `setup_data.py` (generated from `setup.html`)
- **Query**: `answer_question(query_text)` → `AnswerCandidate(answer, confidence, source)`

### Legacy JSON (Being Phased Out)
- `personal_details/user_details.json` — flat user profile
- `personal_details/job_prefrences.json` — job search preferences
- Still read by LinkedIn flow in orchestrator; Naukri uses vector DB

### Session Storage
- `personal_details/linkedin_cookies.json` — Playwright storage state
- `personal_details/naukri_cookies.json` — Playwright storage state
- `scripts/common_stuff/port_info.json` — runtime lock + WebSocket endpoint

---

## Concurrency Model

- **Single Playwright instance** per orchestrator run (enforced by lock)
- **WebSocket endpoint** (`--remote-debugging-port=3000`) stored in `port_info.json`
- **MCP tools** can connect to existing browser via the stored WS endpoint
- No parallel job processing yet (sequential, one job at a time)

---

## Diagnostic & Observability

| Output | Location | When Generated |
|--------|----------|----------------|
| Selector validation JSON | `logs/naukri_selector_validation_*.json` | E2E test run |
| E2E test results JSON | `logs/naukri_e2e_test_*.json` | E2E test run |
| Python logging | stdout + file | Runtime |
| Form session report | In-memory dict | After each form fill |
