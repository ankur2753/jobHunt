# REQUIREMENTS - Setup, dependencies, and configuration

Related: [[PROJECT_MAP]] | [[CLAUDE]] | [[COMPONENTS]]

---

## System requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10+ | Async/await, type hints |
| Chromium | Latest | Installed via `playwright install chromium` |
| Linux / macOS | Any | Windows untested |

---

## Python dependencies

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

## Environment setup

### 1. Virtual environment
```bash
cd /home/ankurkumar/ankur_code/agent
python -m venv .venv
source .venv/bin/activate
pip install -r config/requirements.txt
playwright install chromium
```

### 2. Personal data setup
```bash
# Step 1: Open setup.html in browser, fill all fields, generate script
# Step 2: Save generated file as setup_data.py in project root
# Step 3: Run it to populate vector DB
python setup_data.py
```

### 3. Initial login
```bash
python scripts/orchestrator/orchestrator.py
# Select portal → choose to log in manually
# Browser opens → log in → cookies auto-saved
```

---

## Configuration files

### `personal_details/user_details.json` (legacy)
The orchestrator reads this file for the LinkedIn flow. Keys:
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

### `personal_details/job_prefrences.json` (legacy)
The orchestrator reads this file for the LinkedIn flow defaults. Keys:
```json
{
  "targetTitles": ["Software Engineer"],
  "preferredLocations": ["Remote"],
  "expectedSalary": "..."
}
```

### `scripts/common_stuff/port_info.json` (runtime)
Orchestrator manages this file. Contains:
```json
{
  "lock_time": 1745000000.0,
  "ws_endpoint": "http://localhost:3000",
  "cookies_file": "/path/to/cookies.json"
}
```
**Do not edit manually.** The system deletes this file when the orchestrator exits (`release_lock()`).

---

## MCP server configuration

To use MCP tools from Claude Desktop, update the Claude Desktop config:

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

## Functional requirements

### FR-1: Portal authentication
- Support cookie-based session reuse.
- Detect expired sessions and prompt re-login.
- Save session state after successful manual login.

### FR-2: Job discovery
- Scrape job listings from Naukri recommended jobs page.
- Handle pagination or scroll-based loading.
- Extract job title, company, URL, apply button.

### FR-3: Form detection
- Detect >95% of form questions using HTML parsing.
- Support 8 field types (text, number, email, select, radio, checkbox, textarea, date).
- Handle Naukri chatbot-style forms and LinkedIn modal forms.

### FR-4: Semantic matching
- Match form questions to vector DB answers with confidence scoring.
- Confidence thresholds: Naukri 0.70, LinkedIn 0.65.
- Prompt user for questions below threshold.

### FR-5: Answer normalization
- Normalize 9 field categories before filling.
- Validate formats (email regex, numeric ranges, dates).

### FR-6: Error resilience
- Retry transient failures with exponential backoff (max 3 attempts).
- Use multi-tier selector fallback chains.
- Log failures with enough context for debugging.

### FR-7: Human fallback
- When confidence < threshold, prompt user via stdin.
- When all automation fails, notify via Telegram.
- Do not submit forms with unresolved required fields.

---

## Non-functional requirements

| NFR | Target |
|-----|--------|
| Form fill time | < 5 seconds per form |
| Selector resilience | Multi-tier fallbacks; survive CSS class changes |
| Auto-fill accuracy | > 95% for high-confidence answers |
| Auto-fill rate | > 80% of questions answered automatically |
| Concurrency | Single browser instance |
| Data privacy | Credentials stored locally only |

---

## Future requirements

- **FR-8**: Telegram bot integration for alerts.
- **FR-9**: LLM fallback for questions below 0.50 confidence.
- **FR-10**: Multi-step form navigation.
- **FR-11**: InstaHyre job scraping and apply.
- **FR-12**: Parallel job processing.
- **FR-13**: Analytics dashboard.
- **FR-14**: Dynamic selector discovery when hardcoded selectors fail.
