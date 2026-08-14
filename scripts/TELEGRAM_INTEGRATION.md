# Telegram Bot & RPC Integration Protocol

This document specifies the complete **JSON-RPC protocol, CLI command contract, error handling standards, and Telegram Bot integration guidelines** for automating 1-page A4 Resume PDF, Cover Letter PDF, and LinkedIn Cold Outreach DM generation.

---

## 1. RPC & CLI Interface Protocol

The automation engine entrypoint is located at:
```
/home/ankurkumar/ankur_code/agent/scripts/cli_tailor.py
```

### Execution Schema

#### A. From Job Posting URL
```bash
python3 /home/ankurkumar/ankur_code/agent/scripts/cli_tailor.py \
  --url "https://company.com/job/123" \
  --json
```

#### B. From Raw Job Description Text
```bash
python3 /home/ankurkumar/ankur_code/agent/scripts/cli_tailor.py \
  --jd-text "We are hiring a Senior QA Engineer skilled in Java, Selenium, REST API testing, and Playwright..." \
  --json
```

#### C. With Company & Role Overrides
```bash
python3 /home/ankurkumar/ankur_code/agent/scripts/cli_tailor.py \
  --url "https://company.com/job/123" \
  --company "Acme Corp" \
  --role "Lead QA Automation Architect" \
  --json
```

---

## 2. JSON Response Contract

When `--json` is supplied, `cli_tailor.py` outputs a structured JSON string to `stdout`:

### Success Payload Schema
```json
{
  "status": "success",
  "company": "Cohesity",
  "role": "Senior Performance Engineer, Data Protection & Security Platform Engineering",
  "resume_pdf": "/home/ankurkumar/ankur_code/agent/resumes/tailored/Resume_Cohesity_SeniorPerformanceEngineer_20260809.pdf",
  "cover_letter_pdf": "/home/ankurkumar/ankur_code/agent/resumes/tailored/Cover_Letter_Cohesity_SeniorPerformanceEngineer_20260809.pdf",
  "linkedin_dm": "Hi! I noticed the open Senior Performance Engineer position at Cohesity and wanted to reach out. As a Senior QA Engineer specializing in Java/Selenium and Playwright test automation, I'd love to connect and share how my background fits your team's goals!"
}
```

### Error Payload Schema
```json
{
  "status": "error",
  "message": "No job description text or reachable URL provided."
}
```

---

## 3. Telegram Bot Handler Implementation

Your Telegram bot (running as a separate service on this machine) invokes `cli_tailor.py` using `subprocess.run()`:

```python
import sys
import subprocess
import json
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
CLI_TAILOR_PATH = "/home/ankurkumar/ankur_code/agent/scripts/cli_tailor.py"

async def handle_job_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    if not user_text:
        return

    await update.message.reply_text("🔄 *Analyzing job posting & tailoring 1-page A4 application documents...*", parse_mode="Markdown")

    is_url = user_text.startswith("http://") or user_text.startswith("https://")
    cmd = [sys.executable, CLI_TAILOR_PATH, "--json"]
    if is_url:
        cmd.extend(["--url", user_text])
    else:
        cmd.extend(["--jd-text", user_text])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if proc.returncode != 0:
            await update.message.reply_text("❌ *Error generating documents.* Check server logs.", parse_mode="Markdown")
            return

        data = json.loads(proc.stdout)
        company = data.get("company", "Company")
        role = data.get("role", "Role")
        resume_pdf = data.get("resume_pdf")
        cover_letter_pdf = data.get("cover_letter_pdf")
        linkedin_dm = data.get("linkedin_dm", "")

        # 1. Send Resume Document
        if resume_pdf and Path(resume_pdf).exists():
            with open(resume_pdf, "rb") as doc:
                await update.message.reply_document(document=doc, filename=f"Ankur_Kumar_{company}_Resume.pdf", caption="📄 *Tailored 1-Page A4 Resume*")

        # 2. Send Cover Letter Document
        if cover_letter_pdf and Path(cover_letter_pdf).exists():
            with open(cover_letter_pdf, "rb") as doc:
                await update.message.reply_document(document=doc, filename=f"Ankur_Kumar_{company}_Cover_Letter.pdf", caption="✉️ *Tailored 1-Page A4 Cover Letter*")

        # 3. Send LinkedIn DM Message
        if linkedin_dm:
            msg = f"🟢 *Tailoring Complete for {role} at {company}!*\n\n💬 *LinkedIn Recruiter DM:*\n```text\n{linkedin_dm}\n```"
            await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ *Failed:* `{e}`", parse_mode="Markdown")
```

---

## 4. Prompts & LLM Provider Configuration

The underlying LLM provider can be swapped at any time by configuring `.env`:
- `GEMINI_API_KEY`: Google Gemini
- `OPENAI_API_KEY`: OpenAI GPT models
- `OPENROUTER_API_KEY`: OpenRouter
- `LLM_API_KEY` + `LLM_BASE_URL`: Local Ollama / vLLM / Groq endpoints

For prompt templates, see:
- [`prompts/telegram_bot_prompt.md`](file:///home/ankurkumar/ankur_code/agent/prompts/telegram_bot_prompt.md)
- [`prompts/job_analysis_prompt.md`](file:///home/ankurkumar/ankur_code/agent/prompts/job_analysis_prompt.md)
- [`prompts/resume_tailoring_prompt.md`](file:///home/ankurkumar/ankur_code/agent/prompts/resume_tailoring_prompt.md)
- [`prompts/cover_letter_prompt.md`](file:///home/ankurkumar/ankur_code/agent/prompts/cover_letter_prompt.md)
- [`prompts/linkedin_outreach_prompt.md`](file:///home/ankurkumar/ankur_code/agent/prompts/linkedin_outreach_prompt.md)
