# Automated Job Search Agent

A three-layer automation system that scrapes job postings, fills application forms using semantic matching against a personal vector database, and sends networking messages — with progressive fallback from scripts, to an LLM agent, to a human when automation fails.

```
Scrape Jobs → Personalize Application → Apply → Network → Follow Up
```

The guiding principle: the most reliable (scripted) path runs first, and progressively more expensive resources (LLM, then human) are only invoked when the previous layer fails.

---

## Architecture

The system is split into three tiers:

```
┌───────────────────────────────────────────────┐
│  Layer 3: Agent / LLM                          │  Dynamic problem-solving,
│  Claude Desktop via MCP, or direct API call    │  context handover on failure
└──────────────────────┬─────────────────────────┘
                       │ fallback / error resolution
┌──────────────────────▼─────────────────────────┐
│  Layer 2: Orchestrator                         │  Sequences tasks, routes
│  scripts/orchestrator/orchestrator.py          │  errors, lock management
└──────────────────────┬─────────────────────────┘
                       │ invokes tools
┌──────────────────────▼─────────────────────────┐
│  Layer 1: Scripts / Tools                      │  Deterministic Playwright
│  Playwright automation, one module per portal  │  browser automation
└──────────────────────┬─────────────────────────┘
                       │ drives browser
                  Chromium (Naukri, LinkedIn, InstaHyre)
```

**Failure escalation:** Script fails → orchestrator retries (`@retry_async`) → LLM agent resolves via MCP → human notified via Telegram (planned).

See [Instructions/ARCHITECTURE.md](Instructions/ARCHITECTURE.md) for the full design.

---

## Feature Status

| Feature | LinkedIn | Naukri | InstaHyre |
|---------|----------|--------|-----------|
| Cookie Login | ✅ | ✅ | ✅ |
| Manual Login Fallback | ✅ | ✅ | ✅ |
| Job Scraping | ⚠️ Broken | ✅ | ❌ |
| Auto Apply | ⚠️ Partial | ✅ | ❌ |
| Form Fill (Chatbot) | ✅ | ✅ | ❌ |
| Cold Messaging | ✅ | ❌ | ❌ |
| MCP Tools | ⚠️ Partial | ⚠️ Partial | ❌ |
| E2E Tests | ✅ | ✅ | ❌ |

---

## How It Works

### Semantic Form Filling

Application forms are filled by matching each detected question against a personal profile stored in a vector database:

```
chatbot_form_filler.py       → detect questions (label → placeholder → aria-label)
   → vector_db_manager.py    → SentenceTransformer encode + ChromaDB cosine search
   → answer_validators.py    → normalize (salary, experience, phone, dates, …)
   → Playwright              → fill field → submit
```

Answers are auto-filled based on a confidence score; low-confidence questions fall back to prompting the user.

| Confidence | Action |
|-----------|--------|
| ≥ 0.90 | Auto-fill silently |
| 0.65–0.89 | Auto-fill, log (threshold: Naukri 0.70, LinkedIn 0.65) |
| 0.50–0.64 | Prompt user with suggestion |
| < 0.50 | Skip, ask user |

### Data Sources

- **Vector DB** (`vector_db/`, ChromaDB) — source of truth for personal profile answers, populated from `setup.html` → `setup_data.py`.
- **Legacy JSON** (`personal_details/`) — still read by the LinkedIn flow; being phased out.
- **Cookies** (`personal_details/*_cookies.json`) — Playwright session state for each portal.

---

## Getting Started

### Requirements

- Python 3.10+
- Chromium (installed via Playwright)
- Linux / macOS (Windows untested)

### Install

```bash
cd /home/ankurkumar/ankur_code/agent
python -m venv .venv
source .venv/bin/activate
pip install -r config/requirements.txt
playwright install chromium
```

### Set Up Personal Data

```bash
# 1. Open setup.html in a browser, fill all fields, generate the script
# 2. Save the generated file as setup_data.py in the project root
# 3. Populate the vector DB
python setup_data.py
```

### First Login (saves cookies)

```bash
python scripts/orchestrator/orchestrator.py
# Select a portal → choose to log in manually → log in → cookies auto-saved
```

---

## Usage

```bash
# Main entry point — menu-driven CLI (portal → action)
python scripts/orchestrator/orchestrator.py

# Naukri end-to-end selector test
python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed

# Dry-run form filling against a real job posting
python scripts/tests/test_real_job_posting.py --portal naukri --url "<url>" --dry-run
```

### MCP Server (Claude Desktop)

Expose automation tools to Claude Desktop by adding to its config:

```json
{
  "mcpServers": {
    "linkedin-agent": {
      "command": "/home/ankurkumar/ankur_code/agent/.venv/bin/python",
      "args": ["/home/ankurkumar/ankur_code/agent/scripts/orchestrator/mcp_server.py"]
    }
  }
}
```

---

## Repository Structure

```
agent/
├── config/requirements.txt          # pip dependencies
├── Instructions/                     # Knowledge-graph docs (start at PROJECT_MAP.md)
├── personal_details/                 # Legacy JSON + cookie files
├── resumes/                          # Generated resumes
├── scripts/
│   ├── orchestrator/                 # orchestrator.py, mcp_server.py, resume_modifier.py
│   ├── common_stuff/                 # Shared utils: form filler, vector DB, retry, validators
│   ├── cookie_management_login/      # Per-portal login + form filler
│   ├── job_scraping/                 # Naukri / LinkedIn scrape + apply
│   ├── networking/                   # LinkedIn cold message + connect
│   └── tests/                        # Unit + integration + E2E tests
├── vector_db/                        # ChromaDB persistent store
└── setup.html                        # Web UI for entering personal data
```

---

## Key Components

| Component | Role |
|-----------|------|
| `orchestrator/orchestrator.py` | Main CLI entry point; menu, browser lifecycle, file lock |
| `orchestrator/mcp_server.py` | MCP server exposing tools to Claude Desktop |
| `common_stuff/chatbot_form_filler.py` | Core form detection & filling (8 field types) |
| `common_stuff/vector_db_manager.py` | ChromaDB semantic search (`all-MiniLM-L6-v2`) |
| `common_stuff/answer_validators.py` | Answer normalization across 9 field categories |
| `common_stuff/retry_utils.py` | `@retry_async` exponential-backoff decorator |
| `common_stuff/naukri_selector_discovery.py` | Runtime selector validation → JSON reports |
| `cookie_management_login/naukri_form_filler.py` | Naukri chatbot form flow (threshold 0.70) |
| `cookie_management_login/linkedin_form_filler.py` | LinkedIn form flow (threshold 0.65) |
| `job_scraping/naukri_job_apply.py` | Naukri recommended-jobs auto-apply |

See [Instructions/COMPONENTS.md](Instructions/COMPONENTS.md) for the full module reference.

---

## Conventions

- All browser automation uses the **Playwright async API**.
- Selectors prefer **`data-qa` attributes** over CSS classes for stability, with multi-tier fallback chains.
- Wrap Playwright interactions in **`@retry_async`** from `retry_utils.py`.
- The **vector DB** is the source of truth for personal-data answers.
- Only one Playwright instance runs at a time, enforced by the lock file `scripts/common_stuff/port_info.json` (`get_lock()` / `release_lock()`, 5-min expiry).

---

## Known Limitations

1. **LinkedIn job scraping is broken** — cookie login works but the scraper fails.
2. **Multi-step Naukri forms** — "Next" button navigation not yet implemented.
3. **InstaHyre** — login only; scrape and apply are stubs.
4. **LLM fallback loop** — MCP server is partial; the full agent-driven recovery loop is not wired.
5. **Telegram human fallback** — planned, not implemented.

See [Instructions/KNOWN_BUGS.md](Instructions/KNOWN_BUGS.md) for details.

---

## Documentation

The `Instructions/` folder is a linked knowledge graph. Start at [Instructions/PROJECT_MAP.md](Instructions/PROJECT_MAP.md):

- [PROJECT_MAP.md](Instructions/PROJECT_MAP.md) — central hub, structure, status matrix
- [ARCHITECTURE.md](Instructions/ARCHITECTURE.md) — three-layer design & data flow
- [COMPONENTS.md](Instructions/COMPONENTS.md) — every script/module explained
- [WORKFLOWS.md](Instructions/WORKFLOWS.md) — step-by-step execution flows
- [REQUIREMENTS.md](Instructions/REQUIREMENTS.md) — setup, dependencies, config
- [KNOWN_BUGS.md](Instructions/KNOWN_BUGS.md) — active bugs and future work
- [CLAUDE.md](Instructions/CLAUDE.md) — entry point for Claude Code

---

## Privacy

All credentials, cookies, and personal data are stored **locally only** — nothing is sent to the cloud.
