# KNOWN BUGS & LIMITATIONS

Related: [[PROJECT_MAP]] | [[ARCHITECTURE]] | [[COMPONENTS]]

> This file tracks active bugs, known limitations, and unimplemented stubs.
> Update status when a bug is fixed or a feature is implemented.

---

## Critical Bugs

### BUG-001: LinkedIn Job Scraping & Automation is a Complete Failure
**Status**: ❌ FAILED (Won't Fix)
**Severity**: Critical
**Source**: LinkedIn Anti-Bot Measures

**Symptom**: LinkedIn cookie login succeeds, but job scraping and auto-applying consistently fail.
**Cause**: Aggressive anti-bot measures and CAPTCHAs from LinkedIn block Playwright automation completely.
**Workaround**: Discontinue automated LinkedIn scraping. The system now completely delegates UI fallback to the user or avoids LinkedIn entirely.

---

## Unimplemented Features

### BUG-002: InstaHyre Entirely Unimplemented
**Status**: ❌ Stub only
**Severity**: Low

**Symptom**: Selecting InstaHyre or sending an InstaHyre task via the `redis_gateway.py` immediately returns without doing anything.
**Affected Files**:
- `scripts/cookie_management_login/instahyre_login.py` (login only, no apply/scrape)

---

## Known Limitations & Tech Debt

### LIMITATION-001: CustomLLMAgent Cost & Latency
**Status**: ⚠️ Active
**Severity**: Medium

**Symptom**: The new `CustomLLMAgent` which handles visual fallbacks via Native LLM Function Calling (`click`, `type_text`, `scroll`, `ask_user`) can be slower and more costly than direct Playwright selectors.
**Mitigation**: The system always attempts standard scripted interactions first and only cascades to the `CustomLLMAgent` when a selector fails or a complex form is encountered.

### LIMITATION-002: Telegram Rate Limits
**Status**: ⚠️ Active
**Severity**: Low

**Symptom**: The `ask_user` tool in `CustomLLMAgent` routes messages to the user via Telegram. High frequency of fallback events may trigger Telegram API rate limits.
**Mitigation**: Implement throttling in `redis_gateway.py` when dispatching `ask_user` events.

---

## Recently Resolved (✅ FIXED)

- **Naukri End-to-End**: Auto-apply works completely fine end-to-end. Multi-step forms, NLA popups, and dynamic form fields are now successfully handled natively or via `CustomLLMAgent` fallback. All related bugs have been removed from this tracker.
- **UI Decoupling**: CLI menus have been replaced; Telegram is now the first-class UI, driven by `redis_gateway.py` and `JobTaskFactory`.
