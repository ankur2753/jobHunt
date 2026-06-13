# REQUIREMENTS — Setup, Dependencies & Configuration

Related: [[PROJECT_MAP]] | [[CLAUDE]] | [[COMPONENTS]]

---

## System Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | Async/await, type hints |
| Chromium | Latest | Installed via `playwright install chromium` |
| Linux / macOS | Any | Windows untested |

---

## Python Dependencies

**File**: `config/requirements.txt`

| Package | Version | Purpose |
|---------|---------|---------|
| `playwright` | 1.58.0 | Browser automation |
| `pytest-playwright` | 0.4.4 | Playwright test fixtures |
| `python-dotenv` | 1.0.1 | Environment variable loading |
| `requests` | 2.31.0 | HTTP requests |
| `beautifulsoup4` | 4.12.3 | HTML parsing fallback |
| `mcp` | >=1.0.0 | Model Context Protocol server |
| `chromadb` | 0.4.24 | Vector database |
| `sentence-transformers` | 2.7.0 | Semantic embeddings |

**Install**:
```bash
pip install -r config/requirements.txt
playwright install chromium
```

---

## Environment Setup

### 1. Virtual Environment (Recommended)
```bash
cd /home/ankurkumar/ankur_code/agent
python -m venv .venv
source .venv/bin/activate
pip install -r config/requirements.txt
playwright install chromium
```

### 2. Personal Data Setup
```bash
# Step 1: Open setup.html in browser, fill all fields, generate script
# Step 2: Save generated file as setup_data.py in project root
# Step 3: Run it to populate vector DB
python setup_data.py
```

### 3. Initial Login (saves cookies)
```bash
python scripts/orchestrator/orchestrator.py
# Select portal → choose to log in manually
# Browser opens → log in → cookies auto-saved
```

---

## Configuration Files

### `personal_details/user_details.json` (Legacy)
Used by LinkedIn flow in orchestrator. Keys:
```json
{
  "name": "...",
  "email": "...",
  "phone": "...",
  "skills": [...],
  "experience_years": "...",
  "current_role": "..."
}
```

### `personal_details/job_prefrences.json` (Legacy)
Used by LinkedIn flow for defaults. Keys:
```json
{
  "targetTitles": ["Software Engineer"],
  "preferredLocations": ["Remote"],
  "expectedSalary": "..."
}
```

### `scripts/common_stuff/port_info.json` (Runtime)
Auto-managed by orchestrator. Contains:
```json
{
  "lock_time": 1745000000.0,
  "ws_endpoint": "http://localhost:3000",
  "cookies_file": "/path/to/cookies.json"
}
```
**Do not edit manually.** Deleted on orchestrator exit (`release_lock()`).

---

## MCP Server Configuration

To use MCP tools from Claude Desktop, add to Claude Desktop config:

```json
{
  "mcpServers": {
    "linkedin-agent": {
      "command": "/home/ankurkumar/ankur_code/agent/.venv/bin/python",
      "args": [
        "/home/ankurkumar/ankur_code/agent/scripts/orchestrator/mcp_server.py"
      ]
    }
  }
}
```

---

## Functional Requirements

### FR-1: Portal Authentication
- System must support cookie-based session reuse
- Must detect expired sessions and prompt re-login
- Must save session state after successful manual login

### FR-2: Job Discovery
- Must scrape job listings from Naukri recommended jobs page
- Must handle pagination or scroll-based loading
- Must extract: job title, company, URL, apply button

### FR-3: Form Detection
- Must detect >95% of form questions using HTML parsing
- Must support 8 field types (text, number, email, select, radio, checkbox, textarea, date)
- Must handle Naukri chatbot-style forms and LinkedIn modal forms

### FR-4: Semantic Matching
- Must match form questions to vector DB answers with confidence scoring
- Confidence thresholds: Naukri 0.70, LinkedIn 0.65
- Must prompt user for questions below threshold

### FR-5: Answer Normalization
- Must normalize 9 field categories before filling
- Must validate format (email regex, numeric ranges, dates)

### FR-6: Error Resilience
- Must retry transient failures with exponential backoff (max 3 attempts)
- Must use multi-tier selector fallback chains
- Must log all failures with enough context for debugging

### FR-7: Human Fallback
- When confidence < threshold: prompt user interactively via stdin
- When all automation fails: notify via Telegram (planned)
- Must not submit form with unresolved required fields

---

## Non-Functional Requirements

| NFR | Target |
|-----|--------|
| Form fill time | < 5 seconds per form |
| Selector resilience | Multi-tier fallbacks; survive CSS class changes |
| Auto-fill accuracy | > 95% for high-confidence answers |
| Auto-fill rate | > 80% of questions answered automatically |
| Concurrency | Single browser instance (enforced by lock) |
| Data privacy | Credentials stored locally only (no cloud) |

---

## Future Requirements (Planned)

- **FR-8**: Telegram bot integration for human-in-the-loop alerts
- **FR-9**: LLM fallback for questions below 0.50 confidence (OpenRouter / Azure)
- **FR-10**: Multi-step form navigation (Next button handling)
- **FR-11**: InstaHyre job scraping and apply
- **FR-12**: Parallel job processing (multiple browser tabs)
- **FR-13**: Analytics dashboard (success rate, fill rate, time metrics)
- **FR-14**: Dynamic selector discovery when all hardcoded selectors fail
