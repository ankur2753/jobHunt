# CLAUDE.md

> Claude Code entry point. Start here for project context before making changes.

---

## Project summary

A three-layer automation system (Scripts, Orchestrator, LLM Agent) scrapes job postings, fills application forms using semantic matching against a personal vector database, and sends networking messages. It uses a Telegram bot for human fallback when automation fails.

---

## Knowledge graph

For architecture, components, workflows, requirements, and bugs, start from [[PROJECT_MAP]].

---

## Quick-start commands

```bash
# Activate virtualenv
cd /home/ankurkumar/ankur_code/agent
source .venv/bin/activate

# Run orchestrator
python scripts/orchestrator/orchestrator.py

# Run Naukri E2E selector test
python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed

# Test form filling on a real job
python scripts/tests/test_real_job_posting.py --portal naukri --url "<url>" --dry-run

# Install dependencies
pip install -r config/requirements.txt

# Setup personal data
python setup_data.py
```

---

## Critical files

| File | Role |
|------|------|
| `scripts/orchestrator/orchestrator.py` | Main entry point |
| `scripts/orchestrator/mcp_server.py` | MCP server exposing tools to Claude Desktop |
| `scripts/job_scraping/naukri_job_apply.py` | Naukri auto-apply orchestration |
| `scripts/job_scraping/linkedin_job_apply.py` | LinkedIn apply |
| `scripts/cookie_management_login/naukri_form_filler.py` | Naukri chatbot form filling |
| `scripts/cookie_management_login/linkedin_form_filler.py` | LinkedIn form filling |
| `scripts/common_stuff/vector_db_manager.py` | ChromaDB semantic search for profile answers |
| `scripts/common_stuff/chatbot_form_filler.py` | Core form detection and filling logic |
| `scripts/common_stuff/answer_validators.py` | Answer normalization |
| `scripts/common_stuff/retry_utils.py` | Retry logic with exponential backoff |
| `scripts/common_stuff/naukri_selector_discovery.py` | Runtime selector validation, exports JSON reports |
| `personal_details/` | Legacy JSON user data |
| `vector_db/` | ChromaDB persistent store |

---

## Architecture summary

```
Layer 3: Agent/LLM
     ↑↓
Layer 2: Orchestrator
     ↑↓
Layer 1: Scripts/Tools
```

See [[ARCHITECTURE]] for full details.

---

## Active portals

| Portal | Login | Scrape | Apply | Form Fill |
|--------|-------|--------|-------|-----------|
| LinkedIn | ✅ Cookie | ⚠️ Broken | ✅ Partial | ✅ Phase 3 |
| Naukri | ✅ Cookie | ✅ | ✅ Phase 6 | ✅ Phase 6 |
| InstaHyre | ✅ Cookie | ❌ Not started | ❌ Not started | ❌ Not started |

---

## Known bugs

See [[KNOWN_BUGS]] for full details. Critical issues include:

1. **LinkedIn job scraping broken.** Cookie login works but scraper fails.
2. **Naukri not tested live.** All phases implemented but untested on real site.
3. **Multi-step Naukri forms.** The "Next" button navigation fails.
4. **InstaHyre stub only.** `Coming soon!` in orchestrator.

---

## Coding conventions

- Use the Playwright async API.
- Use `data-qa` attributes over CSS classes for stability.
- Use `@retry_async` from `retry_utils.py` for Playwright interactions.
- The vector database (`vector_db_manager.py`) is the source of truth for personal data answers.
- Store session state cookies in `personal_details/*_cookies.json`.
- The lock file `scripts/common_stuff/port_info.json` prevents concurrent runs.

---

## Do not break

- `get_lock()` and `release_lock()` in the orchestrator prevent concurrent Playwright instances.
- The `VectorDBManager` singleton pattern ensures the ChromaDB collection initializes only once.
- Deleting cookie files in `personal_details/` forces a manual re-login.
