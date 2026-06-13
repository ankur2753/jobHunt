# Session 2026-06-13 — Naukri Chatbot Fix, Profile Seeding & Logging Cleanup

Related: [[CLAUDE]] | [[PHASE_2_BULK_APPLY_IMPLEMENTATION]] | [[KNOWN_BUGS]] | [[NAUKRI_QUICK_REFERENCE]]

> What changed today, how to run it, and the prioritized TODOs (with context) for the next session.

---

## TL;DR

- **Naukri bulk apply now works end-to-end — verified 5/5 jobs applied.** The chatbot side-panel form filling was rewritten.
- **Vector DB seeded** with Ankur's real answers (391 phrasings) so common recruiter questions auto-answer above the 0.6 threshold.
- **Terminal logging cleaned up** — clean console, full detail to a per-run log file. New `--verbose` flag.

---

## 1. Naukri chatbot form filling — fixed

### The bug (why it bailed at ~2/3 jobs)
- The bulk-apply path detected form inputs **page-wide**, so `input[type=text]` matched the **search / experience / location boxes on the recommended-jobs page sitting *behind* the chatbot drawer**. Typing / pressing Enter into them stole focus and **closed the drawer** — the "clicks outside the box, closes at 2/3 jobs" symptom.
- It also treated the chatbot as a **static form** (`detect_chatbot_questions_in_panel`) and looked for `button` / `.chip` / `<input>` options that **don't exist** in Naukri's chatbot.

### Real Naukri chatbot DOM (discovered live)
| Thing | Selector |
|---|---|
| Drawer (scope EVERYTHING to this) | `.chatbot_DrawerContentWrapper` |
| Current question | last visible `.botItem .botMsg span` inside the drawer |
| Single-select (MCQ **and** Yes/No) | `input[type=radio]` (Naukri class `.ssrc__radio`) + `label[for=<id>]` (`.ssrc__label`) |
| Multi-select | `input[type=checkbox]` + `label[for=<id>]` |
| Free text (e.g. "enter YOE") | contenteditable `div.textArea` — **NOT** a real `<input>` |
| Advance / submit | `div.send:not(.disabled) .sendMsg` ("Save") — click after every answer |

**Key fact:** a bulk apply opens **ONE continuous drawer that handles ALL selected jobs** in a single conversation (not one drawer per job). The loop runs until the drawer closes.

### What was changed
**`scripts/cookie_management_login/naukri_form_filler.py`**
- `DRAWER` constant + `_is_chatbot_open()`.
- Rewrote `_detect_current_chatbot_state()` → **drawer-scoped**, detects input kind by **element type** (`radio` / `checkbox` / `contenteditable`), returns a normalized dict `{done, question, kind, options, text_el}`.
- New `run_chatbot_conversation()` — the single conversational driver (detect → answer → click Save → repeat until drawer closes / stall).
- New answer router `_answer_question()` + helpers: `_resolve_option`, `_click_option`, `_click_option_by_text`, `_fill_text`, `_click_send_button`, `_derive_yes_no`, `_answer_fallback`, `_finish`, `_clean_answer`.
- `_clean_answer()` extracts the value from vector-DB facts stored as `"Question?\nA: value"` (otherwise the whole stored string got typed into text boxes).
- Confidence threshold dropped to **0.60**. Legacy `_fill_form_with_fallback()` now delegates to the new driver.

**`scripts/job_scraping/naukri_job_apply.py`**
- Replaced the broken per-job static loop with a **single `run_chatbot_conversation()` call**; writes a review log of low-confidence/guessed answers to `logs/naukri_chatbot_review_*.json`.

### Answering rules (confirmed with user)
- Semantic match via the sentence-transformer, threshold **0.6**.
- `>= 0.6` → auto-answer **+ log for review**.
- `< 0.6` → prompt the human if available (`enable_human_fallback`), else **best guess + log**.
- Genuinely unanswerable → pick **"Skip"** option if offered, else first option (**never block, never skip the job**); always logged.
- Yes/No where the threshold is in the *question* ("more than 3 years?") → derived from the user's known years.

### Verify it
```bash
cd /home/ankurkumar/ankur_code/agent && source .venv/bin/activate
python3 scripts/test_naukri_apply.py     # set N_JOBS / enable_human_fallback inside
```
Last run: **Total Attempted 5 · Successful 5 · Failed 0 · drawer completed**.
> ⚠️ Each run submits **real applications** to the live account.

---

## 2. Profile answers seeded into the vector DB

**`scripts/seed_profile_answers.py`** stores every fact under several natural recruiter phrasings (so "years in Java?" and "Java experience?" both hit).

- Skill YOE = **3 years for everything except Docker = 1**.
- Current CTC **₹12 LPA**, expected **16–20 LPA**, notice **30 days**.
- **Open to relocate anywhere in India**, flexible work mode, OK with 6 days/shifts.
- Current company **Thomson Reuters**; primary target = **full-stack dev**.
- SDET stack: Selenium, Playwright, Postman/REST Assured · NUnit/xUnit, Pytest, SpecFlow/Cucumber · Azure DevOps, GitHub Actions.

```bash
python3 scripts/seed_profile_answers.py            # store + verify retrieval
python3 scripts/seed_profile_answers.py --verify   # verify only (no writes)
```
Result: **16/16** recruiter-style probes clear the 0.6 threshold. To change answers, edit `SKILL_YEARS` / `SCREENING` and re-run (idempotent upsert).

---

## 3. Logging cleanup

**`scripts/common_stuff/logging_setup.py`** — call `setup_logging()` once at an entry point.

| | Terminal | `logs/<name>_run_<timestamp>.log` |
|---|---|---|
| App INFO (progress, summaries) | ✅ clean (no `INFO:module:` prefix) | ✅ |
| DEBUG detail / vector-DB dumps | ❌ hidden | ✅ full |
| Warnings / errors | ✅ flagged `⚠️` / `❌` | ✅ |
| `Batches:`, `Loading weights`, HF token notice, `DEBUG:httpcore` | ❌ suppressed | n/a |

How: file handler captures DEBUG+; console handler shows INFO+ with a clean formatter; noisy third-party loggers pinned to WARNING; HF/transformers progress bars disabled via env vars; a tight **stderr line-filter** drops the few benign lines compiled ML extensions print straight to stderr (bypassing Python logging).

Wired into `orchestrator.py`, `test_naukri_apply.py`, `seed_profile_answers.py`. Removed the root-`DEBUG` `basicConfig` in `naukri_selector_discovery.py` (the source of `DEBUG:` spam). Per-question chatbot detail moved to `logger.debug` (file only).

### `--verbose`
```bash
python scripts/orchestrator/orchestrator.py            # clean console (INFO)
python scripts/orchestrator/orchestrator.py --verbose  # also stream DEBUG to console
```
The orchestrator prints `📂 Full log: logs/orchestrator_run_<ts>.log` at startup. (`logs/` and `*.log` are gitignored.)

---

## Files changed / added today
**Added:** `scripts/common_stuff/logging_setup.py`, `scripts/seed_profile_answers.py`, `scripts/test_naukri_apply.py`, this doc, root `CLAUDE.md`.
**Modified:** `scripts/cookie_management_login/naukri_form_filler.py`, `scripts/job_scraping/naukri_job_apply.py`, `scripts/orchestrator/orchestrator.py`, `scripts/common_stuff/naukri_selector_discovery.py`.

---

## 🔜 Next-Session TODOs (with context)

### TODO-1 — Port the chatbot fix to LinkedIn & Instahyre
**Why:** Naukri now works; LinkedIn form fill is partial and Instahyre is a stub (`print("Coming soon!")`).
**How (reuse the Naukri pattern):**
- Discover each portal's form/drawer DOM live (mirror the approach in this doc).
- **Scope all queries to the form container** (the Naukri "clicks outside" bug will recur otherwise).
- Detect inputs by **element type** (radio/checkbox/contenteditable/select), not vendor CSS classes.
- Build a `run_*_conversation()` / form loop reusing `VectorDBManager`, `_clean_answer`, threshold **0.6**, review-log, and `setup_logging()`.
- Files: `scripts/cookie_management_login/linkedin_form_filler.py`, `scripts/job_scraping/linkedin_job_apply.py`, `scripts/cookie_management_login/instahyre_login.py` (+ new `instahyre_*` apply), orchestrator option 3.
- LinkedIn "Easy Apply" is multi-step (Next → Next → Review → Submit) — handle the step loop (see BUG-003 pattern).

### TODO-2 — Add TDD tests for the message / cover-letter module (write these FIRST)
**Why:** Build the cover-letter/message module test-first.
**How:** Add `scripts/tests/test_cover_letter.py` (and `test_connection_message.py`) with **failing** tests that pin the contract before implementation:
- Input: job `{title, company, job_description}` + profile (from vector DB) → output: tailored cover letter / LinkedIn connection message.
- Assert: contains company + role; references ≥1 real profile skill/experience; respects length limits (e.g. connection note ≤ 300 chars); tone configurable; **no unfilled placeholders** (`{`, `TODO`, `[name]`); deterministic enough to assert structure (mock the LLM call).
- Use these tests to drive TODO-3.

### TODO-3 — Implement the personalized cover-letter / message module
**Why:** Many applications & networking need a tailored note; currently none exists.
**How:** New module (e.g. `scripts/common_stuff/cover_letter_generator.py`) that composes a per-job cover letter and a short connection/referral message from the JD + vector-DB profile facts. Use the **Anthropic API with the latest Claude model (`claude-opus-4-8`)**. Wire into the apply flow wherever a cover-letter / message field appears (Naukri/LinkedIn). Make TODO-2's tests pass.

### TODO-4 — Personalized resume per job
**Why:** `scripts/orchestrator/resume_modifier.py` exists but is **not integrated** (see BUG-008).
**How:** Generate a role-targeted resume variant per job (reorder/emphasize skills & bullets to match the JD using the profile + JD), output to `resumes/`, and integrate into the orchestrator menu + apply flow. Reuse the LLM client from TODO-3.
