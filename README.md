# Automated Job Search Agent

A multi-portal automation system that scrapes job postings, fills application forms using semantic matching against a personal vector database, and logs job application status — with progressive fallback from scripts to LLM agents.

```
Scrape Jobs → Match & Personalize → Auto-Apply → Log Results (Google Sheets) → Outreach
```

---

## 🚀 Key Features

* **Deterministic & Semantic Form Filling**: Uses a hybrid approach (Deterministic Canonical Rules + ChromaDB Vector Search using `all-MiniLM-L6-v2`) to answer job application questions with high confidence.
* **Naukri Module**: Fully functional automated job searching, chatbot form filling, and job application submission.
* **Google Sheets Application Reporting**: Real-time logging of applied jobs, status, timestamps, and answered questions via Google Apps Script Webhooks.
* **Privacy & Multi-User Support**: Completely configurable for any user with zero hardcoded personal data. All sensitive personal details, cookies, and local databases are safely ignored by Git.

---

## 🛠️ System Architecture

```
┌───────────────────────────────────────────────┐
│  Layer 3: Agent / LLM                          │  Dynamic problem-solving &
│  Claude Desktop via MCP, or direct LLM API     │  outreach message generation
└──────────────────────┬─────────────────────────┘
                       │ fallback / error resolution
┌──────────────────────▼─────────────────────────┐
│  Layer 2: Orchestrator                         │  Sequences tasks, routes
│  scripts/orchestrator/orchestrator.py          │  errors, manages browser lock
└──────────────────────┬─────────────────────────┘
                       │ invokes tools
┌──────────────────────▼─────────────────────────┐
│  Layer 1: Playwright Automation                │  Deterministic browser
│  Naukri, LinkedIn, InstaHyre modules           │  interactions & form filling
└────────────────────────────────────────────────┘
```

---

## 📦 Feature Status Matrix

| Feature | Naukri | LinkedIn | InstaHyre |
|---------|--------|----------|-----------|
| Cookie Login | ✅ | ✅ | ✅ |
| Manual Login Fallback | ✅ | ✅ | ✅ |
| Job Scraping & Apply | ✅ | ⚠️ Partial | ❌ |
| Chatbot Form Filling | ✅ | ✅ | ❌ |
| Google Sheets Logging | ✅ | ✅ | ✅ |
| ATS Resume Tailoring | ✅ | ✅ | ✅ |

---

## ⚙️ Setup & Configuration Guide

Follow these steps to set up the agent for your own personal job search.

### 1. Prerequisites & Installation

* **Python 3.10+**
* **Chromium Browser** (via Playwright)
* **Linux / macOS / Windows**

```bash
# Clone the repository
git clone https://github.com/your-username/jobHunt.git
cd jobHunt

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r config/requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

---

### 2. Environment Variables Setup (`.env`)

Copy `.env.example` to create your local `.env` configuration file:

```bash
cp .env.example .env
```

Open `.env` and set your API keys and webhook URL:

```env
# OpenRouter / LLM API Key (for LLM fallback & cold outreach generation)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Google Sheets Webhook URL for Application Reporting (See section below)
GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec
```

---

### 3. Personal Profile Configuration

Copy the example template files in `personal_details/` to configure your profile details:

```bash
# Copy template files
cp personal_details/personal_details.example.json personal_details/personal_details.json
cp personal_details/custom_details.example.json personal_details/custom_details.json
cp personal_details/config.example.json personal_details/config.json
cp personal_details/job_prefrences.example.json personal_details/job_prefrences.json
cp resumes/resume_master.example.md resumes/resume_master.md
```

#### File Descriptions:

1. **`personal_details/personal_details.json`**: Enter your contact details, work experience, education, salary expectations, notice period, and core skills.
2. **`personal_details/config.json`**: Define your job target preferences (preferred job titles, locations, excluded companies, experience level).
3. **`resumes/resume_master.md`**: Your master Markdown resume used for ATS tailoring.

---

### 4. Vector Database Initialization

Populate ChromaDB vector database with your personal profile answers:

```bash
# Seed vector DB from your personal_details.json
python scripts/seed_profile_answers.py

# Verify stored facts and retrieval confidence
python scripts/seed_profile_answers.py --verify
```

---

## 📊 Google Sheets Reporting Setup

The system automatically logs every completed job application to a Google Sheet using a lightweight Google Apps Script Webhook.

```
Application Completed → remote_logger.py → Google Apps Script Webhook → Google Sheet Row Added
```

### Step-by-Step Setup:

1. **Create a Google Sheet**:
   * Open [Google Sheets](https://sheets.google.com) and create a new blank spreadsheet (e.g. named `Job Application Tracker`).

2. **Open Apps Script Editor**:
   * Click on **Extensions** → **Apps Script**.

3. **Paste the Script**:
   * Copy the full content of [`scripts/common_stuff/google_apps_script.js`](scripts/common_stuff/google_apps_script.js) and paste it into the Apps Script code editor (replace any default code).

4. **Deploy as Web App**:
   * Click **Deploy** → **New deployment**.
   * Click **Select type** (gear icon) → **Web app**.
   * Fill out the fields:
     * **Description**: `Job Hunt Remote Logger`
     * **Execute as**: `Me (your-email@gmail.com)`
     * **Who has access**: `Anyone` *(Crucial: allows the script to post without complex OAuth flow)*.
   * Click **Deploy**. Authorize access when prompted.

5. **Copy Web App URL**:
   * Copy the generated **Web App URL** (looks like `https://script.google.com/macros/s/AKfycb.../exec`).

6. **Add to `.env`**:
   * Paste the URL into your `.env` file:
     ```env
     GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec
     ```

7. **Test Google Sheets Logging**:
   ```bash
   python scripts/tests/test_remote_logger.py
   ```
   Check your Google Sheet! You will see automatic headers `[Timestamp, Job Title, Company, Portal, Status, Questions Answered]` and a test row added.

---

## 🏃 Execution Guide

### First-Time Login (Save Session Cookies)

Run the orchestrator CLI menu to perform initial login:

```bash
python scripts/orchestrator/orchestrator.py
```

1. Select **Naukri** (or LinkedIn/InstaHyre).
2. Choose **Login manually**.
3. Complete the login inside the Playwright browser window.
4. Session cookies are automatically saved to `personal_details/naukri_cookies.json` for headless runs.

### Run Naukri Auto-Apply

```bash
# Run automated Naukri search and apply flow via Orchestrator CLI
python scripts/orchestrator/orchestrator.py

# Or run Naukri job application script directly:
python scripts/job_scraping/naukri_job_apply.py
```

---

## 🔒 Security & Privacy

This codebase is configured to keep all personal data local and private:

* **Ignored by Git**: `.env`, `personal_details/*.json` (except templates), `vector_db/`, session cookies (`*_cookies.json`), and generated PDFs/resumes are excluded via `.gitignore`.
* **No Telemetry**: No personal credentials or application history leave your machine except to your configured Google Sheet webhook and target job portals.

---

## 📂 Repository Structure

```
jobHunt/
├── config/requirements.txt          # Python dependencies
├── Instructions/                     # Knowledge-graph design documentation
├── personal_details/                 # Local user config & cookies (Git ignored)
│   ├── personal_details.example.json # Example profile configuration
│   ├── custom_details.example.json   # Example learned Q&A template
│   ├── config.example.json           # Example target preferences template
│   └── job_prefrences.example.json   # Example search preferences template
├── resumes/                          # Master & tailored Markdown/PDF resumes
│   └── resume_master.example.md      # Template master resume
├── scripts/
│   ├── applying_to_portals/          # Submission scripts
│   ├── common_stuff/                 # Vector DB, Google Sheets logger, Form filler
│   │   ├── google_apps_script.js    # Google Apps Script template for Sheets
│   │   ├── remote_logger.py         # Google Sheets Webhook logger client
│   │   ├── vector_db_manager.py     # ChromaDB client & canonical evaluator
│   │   └── chatbot_form_filler.py   # RAG form filler engine
│   ├── cookie_management_login/      # Portal login & session persistence
│   ├── job_scraping/                 # Naukri & LinkedIn job apply runners
│   ├── networking/                   # LinkedIn cold outreach & referral helpers
│   └── orchestrator/                 # Main CLI menu & MCP server
├── .env.example                      # Environment variables template
└── README.md                         # Main documentation
```

---

## 📄 License

MIT License. Free for personal use and customization.
