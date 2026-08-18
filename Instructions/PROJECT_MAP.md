# PROJECT_MAP — Automated Job Search Agent

> Central knowledge graph hub. All nodes link from here.

---

## Graph Index

| Node | Description |
|------|-------------|
| [[RESUME_TAILORING_ENGINE]] | 1-Page A4 Resume & Cover Letter Automation, Provider-Agnostic LLM & Telegram Bot Integration |
| [[ARCHITECTURE]] | 3-layer system design and data flow (Redis Gateway & JobTaskFactory) |
| [[COMPONENTS]] | Every script/module with purpose and status |
| [[WORKFLOWS]] | Step-by-step execution flows per feature (Telegram UI driven) |
| [[REQUIREMENTS]] | Setup, dependencies, configuration |
| [[KNOWN_BUGS]] | Active bugs, limitations, future work |
| [[CLAUDE]] | Claude Code entry point and quick-start |

---

## Project Goal

Automate the full job search lifecycle:

```text
Telegram Command → Scrape Jobs → Tailor Resume → Personalize Application → Apply (CustomLLMAgent fallback)
```

All steps run via scripts first; `CustomLLMAgent` with Native Function Calling (click, type_text, scroll, ask_user) takes over when scripts fail.

---

## Repository Structure

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
│   ├── redis_gateway.py          # Main Entry Point via Redis & JobTaskFactory
│   ├── cli_tailor.py
│   ├── common_stuff/
│   │   ├── llm_fallback.py       # CustomLLMAgent (click, type_text, scroll, ask_user)
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

## Feature Status Matrix

| Feature | LinkedIn | Naukri | InstaHyre |
|---------|----------|--------|-----------|
| Cookie Login | ✅ | ✅ | ❌ |
| Manual Login Fallback | ✅ | ✅ | ❌ |
| Job Scraping | ❌ FAILED (Anti-Bot) | ✅ | ❌ |
| Auto Apply | ❌ FAILED | ✅ | ❌ |
| Form Fill (Chatbot) | ❌ | ✅ | ❌ |
| Visual LLM Fallback | ❌ | ✅ | ❌ |
| Telegram UI Gateway | ❌ | ✅ | ❌ |
| E2E Tests | ❌ | ✅ | ❌ |

---

## Implementation Phases (Naukri Focus)

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1-6 | Selectors, Logging, Error Handling, Retries | ✅ Done |
| Phase 7 | Multi-step Form Navigation | ✅ Done |
| Phase 8 | Telegram UI (First-Class Citizen) via Redis | ✅ Done |
| Phase 9 | CustomLLMAgent Visual Fallback (Native Tools) | ✅ Done |

---

## Data Flow & Knowledge Architecture

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

## External Integrations

| Service | Purpose | Status |
|---------|---------|--------|
| Playwright (Chromium) | Browser automation | ✅ Active |
| Redis | Task queuing and Gateway | ✅ Active |
| Telegram Bot | First-class UI / Human fallback | ✅ Active |
| CustomLLMAgent | Visual fallback with tool calling | ✅ Active |
| ChromaDB | Vector store | ✅ Active |
