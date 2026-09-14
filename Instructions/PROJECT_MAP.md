# PROJECT_MAP — Automated Job Search Agent

Index of the project documentation.

---

## Graph index

| Node | Description |
|------|-------------|
| [[RESUME_TAILORING_ENGINE]] | Resume and cover letter automation, provider-agnostic LLM, and Telegram integration |
| [[ARCHITECTURE]] | 3-layer system design and data flow |
| [[COMPONENTS]] | Script and module purposes and statuses |
| [[WORKFLOWS]] | Execution flows |
| [[REQUIREMENTS]] | Setup, dependencies, configuration |
| [[KNOWN_BUGS]] | Active bugs, limitations, future work |
| [[CLAUDE]] | Claude Code entry point and quick-start |

---

## Project goal

Automate the job search process:

```text
Telegram Command → Scrape Jobs → Tailor Resume → Personalize Application → Apply (CustomLLMAgent fallback)
```

Scripts handle the initial steps. If scripts fail, `CustomLLMAgent` uses native function calling (click, type_text, scroll, ask_user) to complete the task.

---

## Repository structure

```text
agent/
├── config/
│   └── requirements.txt
├── Instructions/                 # ← You are here
│   ├── CLAUDE.md
│   ├── PROJECT_MAP.md
│   ├── RESUME_TAILORING_ENGINE.md
│   ├── ARCHITECTURE.md
│   ├── COMPONENTS.md
│   ├── WORKFLOWS.md
│   ├── REQUIREMENTS.md
│   └── KNOWN_BUGS.md
├── personal_details/
├── prompts/
├── resumes/
├── scripts/
│   ├── redis_gateway.py          # Main entry point
│   ├── cli_tailor.py
│   ├── common_stuff/
│   │   ├── llm_fallback.py       # CustomLLMAgent tools
│   │   ├── chatbot_form_filler.py
│   │   └── vector_db_manager.py
│   ├── cookie_management_login/
│   ├── job_scraping/
│   ├── orchestrator/
│   └── tests/
├── vector_db/
└── setup.html
```

---

## Feature status matrix

| Feature | LinkedIn | Naukri | InstaHyre |
|---------|----------|--------|-----------|
| Cookie login | ✅ | ✅ | ❌ |
| Manual login fallback | ✅ | ✅ | ❌ |
| Job scraping | ✅ | ✅ | ❌ |
| Auto apply | ❌ FAILED | ✅ | ❌ |
| Form fill (chatbot) | ❌ | ✅ | ❌ |
| Visual LLM fallback | ❌ | ✅ | ❌ |
| Telegram UI gateway | ❌ | ✅ | ❌ |
| E2E tests | ❌ | ✅ | ❌ |

---

## Implementation phases (Naukri focus)

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1-6 | Selectors, logging, error handling, retries | ✅ Done |
| Phase 7 | Multi-step form navigation | ✅ Done |
| Phase 8 | Telegram UI via Redis | ✅ Done |
| Phase 9 | CustomLLMAgent visual fallback | ✅ Done |

---

## Data flow and architecture

```text
Telegram UI (User Request) 
        ↓
redis_gateway.py (JobTaskFactory) → Parses request, queues task
        ↓
orchestrator / scripts → Naukri Apply Flow
        ↓
        ├── Standard Script Selectors (Playwright)
        └── (If Failed) → CustomLLMAgent (Native Function Calling)
                               ├── click()
                               ├── type_text()
                               ├── scroll()
                               └── ask_user() → sends message back to Telegram
```

---

## External integrations

| Service | Purpose | Status |
|---------|---------|--------|
| Playwright (Chromium) | Browser automation | ✅ Active |
| Redis | Task queuing and gateway | ✅ Active |
| Telegram Bot | UI and human fallback | ✅ Active |
| CustomLLMAgent | Visual fallback | ✅ Active |
| ChromaDB | Vector store | ✅ Active |
