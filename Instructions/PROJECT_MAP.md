# PROJECT_MAP — Automated Job Search Agent

> Central knowledge graph hub. All nodes link from here.

---

## Graph Index

| Node | Description |
|------|-------------|
| [[ARCHITECTURE]] | 3-layer system design and data flow |
| [[COMPONENTS]] | Every script/module with purpose and status |
| [[WORKFLOWS]] | Step-by-step execution flows per feature |
| [[REQUIREMENTS]] | Setup, dependencies, configuration |
| [[KNOWN_BUGS]] | Active bugs, limitations, future work |
| [[CLAUDE]] | Claude Code entry point and quick-start |

---

## Project Goal

Automate the full job search lifecycle:

```
Scrape Jobs → Personalize Application → Apply → Network → Follow Up
```

All steps run via scripts first; LLM agents take over only when scripts fail.

---

## Repository Structure

```
agent/
├── config/
│   └── requirements.txt          # pip dependencies
├── docker_files/                 # Containerization (future)
├── Instructions/                 # ← You are here (knowledge graph)
│   ├── CLAUDE.md
│   ├── PROJECT_MAP.md
│   ├── ARCHITECTURE.md
│   ├── COMPONENTS.md
│   ├── WORKFLOWS.md
│   ├── REQUIREMENTS.md
│   └── KNOWN_BUGS.md
├── personal_details/             # Legacy JSON + cookie files
│   ├── user_details.json         # (legacy, replaced by vector DB)
│   ├── job_prefrences.json       # (legacy, still used by LinkedIn flow)
│   ├── linkedin_cookies.json
│   └── naukri_cookies.json
├── resumes/                      # Generated resumes
├── scripts/
│   ├── applying_to_portals/
│   │   └── linkedin_apply.py
│   ├── common_stuff/             # Shared utilities
│   │   ├── chatbot_form_filler.py
│   │   ├── answer_validators.py
│   │   ├── vector_db_manager.py
│   │   ├── retry_utils.py
│   │   ├── naukri_selector_discovery.py
│   │   ├── pattern_learner.py
│   │   ├── connect_mcp.py
│   │   ├── login_linkedin.py
│   │   └── open_browser.py
│   ├── cookie_management_login/
│   │   ├── naukri_login.py
│   │   ├── instahyre_login.py
│   │   ├── naukri_form_filler.py
│   │   └── linkedin_form_filler.py
│   ├── job_scraping/
│   │   ├── naukri_job_apply.py
│   │   ├── linkedin_job_apply.py
│   │   └── linkedin_job_scraper.py
│   ├── networking/
│   │   ├── linkedin_cold_message.py
│   │   └── linkedin_connect.py
│   ├── orchestrator/
│   │   ├── orchestrator.py       # Main CLI entry point
│   │   ├── mcp_server.py         # MCP tool server
│   │   └── resume_modifier.py
│   └── tests/
│       ├── naukri_e2e_test.py
│       ├── test_chatbot_form_filler.py
│       ├── test_semantic_matching.py
│       ├── test_form_filling.py
│       ├── test_linkedin_apply.py
│       └── test_real_job_posting.py
├── vector_db/                    # ChromaDB persistent store
└── setup.html                    # Web UI for entering personal data
```

---

## Feature Status Matrix

| Feature | LinkedIn | Naukri | InstaHyre |
|---------|----------|--------|-----------|
| Cookie Login | ✅ | ✅ | ✅ |
| Manual Login Fallback | ✅ | ✅ | ✅ |
| Job Scraping | ⚠️ BUG | ✅ | ❌ |
| Auto Apply | ⚠️ Partial | ✅ Phase 6 | ❌ |
| Form Fill (Chatbot) | ✅ Phase 3 | ✅ Phase 6 | ❌ |
| Cold Messaging | ✅ | ❌ | ❌ |
| MCP Tools Exposed | ✅ Partial | ✅ Partial | ❌ |
| E2E Tests | ✅ | ✅ | ❌ |

---

## Implementation Phases (Naukri Focus)

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Selector Discovery & Validation | ✅ Done |
| Phase 2 | Logging & Diagnostics | ✅ Done |
| Phase 3 | End-to-End Test Runner | ✅ Done |
| Phase 4 | Selector Gap Analysis | ✅ Done |
| Phase 5 | Selector Improvements (multi-tier fallbacks) | ✅ Done |
| Phase 6 | Retry Logic & Error Handling | ✅ Done |
| Phase 7 | Multi-step Form Navigation | ❌ Not started |
| Phase 8 | MCP Tool Integration (full) | ⚠️ Partial |
| Phase 9 | LLM Fallback for Low-confidence Answers | ❌ Not started |

---

## Data Flow

```
setup.html → setup_data.py → vector_db/ (ChromaDB)
                                    ↓
orchestrator.py → naukri_login.py → browser (Playwright)
                                    ↓
               naukri_job_apply.py → job cards → apply button
                                    ↓
               naukri_form_filler.py → chatbot_form_filler.py
                                    ↓
               vector_db_manager.py → semantic match → auto-fill
                                    ↓
               answer_validators.py → normalize → submit
```

---

## External Integrations

| Service | Purpose | Status |
|---------|---------|--------|
| Playwright (Chromium) | Browser automation | ✅ Active |
| ChromaDB | Vector store for personal data | ✅ Active |
| SentenceTransformers | Semantic embeddings (`all-MiniLM-L6-v2`) | ✅ Active |
| MCP Server | Expose tools to Claude Desktop | ✅ Partial |
| Telegram Bot | Human-in-the-loop fallback | ❌ Planned |
| OpenRouter / Azure OpenAI | LLM fallback for low-confidence fills | ❌ Planned |
