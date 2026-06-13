# CLAUDE.md — Automated Job Search Agent

> Claude Code entry point. Start here for project context before making changes.

---

## Project in One Sentence

A three-layer automation system (Scripts → Orchestrator → LLM Agent) that scrapes job postings, fills application forms using semantic matching against a personal vector database, and sends networking messages — with Telegram-based human fallback when automation fails.

---

## [[PROJECT_MAP]] — Full Knowledge Graph

For the complete picture: architecture, components, workflows, requirements, and bugs, navigate the graph starting from [[PROJECT_MAP]].

---

## Quick-Start Commands

```bash
# Activate virtualenv
cd /home/ankurkumar/ankur_code/agent
source .venv/bin/activate

# Run orchestrator (main entry point)
python scripts/orchestrator/orchestrator.py

# Run Naukri E2E selector test
python scripts/tests/naukri_e2e_test.py --max-jobs 3 --headed

# Test form filling on a real job (dry-run)
python scripts/tests/test_real_job_posting.py --portal naukri --url "<url>" --dry-run

# Install dependencies
pip install -r config/requirements.txt

# Setup personal data (fill setup.html in browser first)
python setup_data.py
```

---

## Critical Files Claude Must Know

| File | Role |
|------|------|
| `scripts/orchestrator/orchestrator.py` | Main entry point — menu-driven CLI |
| `scripts/orchestrator/mcp_server.py` | MCP server exposing tools to Claude Desktop |
| `scripts/job_scraping/naukri_job_apply.py` | Naukri auto-apply orchestration |
| `scripts/job_scraping/linkedin_job_apply.py` | LinkedIn apply (partially implemented) |
| `scripts/cookie_management_login/naukri_form_filler.py` | Naukri chatbot form filling |
| `scripts/cookie_management_login/linkedin_form_filler.py` | LinkedIn form filling |
| `scripts/common_stuff/vector_db_manager.py` | ChromaDB semantic search for profile answers |
| `scripts/common_stuff/chatbot_form_filler.py` | Core form detection & filling logic |
| `scripts/common_stuff/answer_validators.py` | Answer normalization (salary, dates, phone, etc.) |
| `scripts/common_stuff/retry_utils.py` | `@retry_async` decorator with exponential backoff |
| `scripts/common_stuff/naukri_selector_discovery.py` | Runtime selector validation, exports JSON reports |
| `personal_details/` | Legacy JSON user data (being replaced by vector DB) |
| `vector_db/` | ChromaDB persistent store |

---

## Architecture Summary (3 Layers)

```
Layer 3: Agent/LLM  ──── fallback resolution, dynamic problem solving
     ↑↓
Layer 2: Orchestrator ── sequences tasks, routes errors, human Telegram alerts
     ↑↓
Layer 1: Scripts/Tools ─ Playwright browser automation, Naukri/LinkedIn/Instahyre
```

See [[ARCHITECTURE]] for full details.

---

## Active Portals

| Portal | Login | Scrape | Apply | Form Fill |
|--------|-------|--------|-------|-----------|
| LinkedIn | ✅ Cookie | ⚠️ Broken | ✅ Partial | ✅ Phase 3 |
| Naukri | ✅ Cookie | ✅ | ✅ Phase 6 | ✅ Phase 6 |
| InstaHyre | ✅ Cookie | ❌ Not started | ❌ Not started | ❌ Not started |

---

## Known Bugs — Quick Links

See [[KNOWN_BUGS]] for full detail. Critical issues:

1. **LinkedIn job scraping broken** — cookie login works but scraper fails
2. **Naukri not tested live** — all phases implemented but untested on real site
3. **Multi-step Naukri forms** — "Next" button navigation not implemented
4. **InstaHyre stub only** — `Coming soon!` in orchestrator

---

## Coding Conventions

- All browser automation uses **Playwright async API** (`playwright.async_api`)
- Selectors prefer **`data-qa` attributes** over CSS classes for stability
- Use **`@retry_async`** from `retry_utils.py` for any Playwright interactions
- **Vector DB** (`vector_db_manager.py`) is the source of truth for personal data answers
- Session state (cookies) stored in `personal_details/*_cookies.json`
- Lock file `scripts/common_stuff/port_info.json` prevents concurrent runs

---

## Do Not Break

- `get_lock()` / `release_lock()` in orchestrator — prevents concurrent Playwright instances
- `VectorDBManager` singleton pattern — ChromaDB collection must be initialized once
- Cookie files in `personal_details/` — deleting these forces manual re-login
