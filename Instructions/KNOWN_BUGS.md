# Known bugs and limitations

Related links
- [[PROJECT_MAP]]
- [[ARCHITECTURE]]
- [[COMPONENTS]]

This file tracks active bugs, known limitations, and missing features. Update the status when you fix a bug or add a feature.

## Critical bugs

### BUG-001 LinkedIn scraping fails
**Status** Won't fix
**Severity** Critical

Cookie login succeeds. Scraping and auto-applying fail every time. LinkedIn's anti-bot measures and CAPTCHAs block Playwright.

We stopped automating LinkedIn scraping. The system skips LinkedIn or asks the user to handle it.

## Missing features

### BUG-002 InstaHyre does nothing
**Status** Stub
**Severity** Low

Selecting InstaHyre or sending a task through `redis_gateway.py` returns immediately. The script `scripts/cookie_management_login/instahyre_login.py` only handles login. It does not apply or scrape.

## Known limitations

### LIMITATION-001 CustomLLMAgent is slow and expensive
**Status** Active
**Severity** Medium

The `CustomLLMAgent` uses LLM function calling to handle visual fallbacks. It uses `click`, `type_text`, `scroll`, and `ask_user`. This costs more and runs slower than standard Playwright selectors.

The system tries standard scripted interactions first. It only falls back to the agent when a selector fails or a form is too complex.

### LIMITATION-002 Telegram rate limits
**Status** Active
**Severity** Low

The `ask_user` tool routes messages through Telegram. Sending too many fallback events triggers API rate limits.

We need to add throttling in `redis_gateway.py` for `ask_user` events.

## Recently fixed

### Naukri end-to-end
Auto-apply works. The system handles multi-step forms, NLA popups, and dynamic fields natively or through the `CustomLLMAgent` fallback.

### UI decoupling
We removed the CLI menus. Telegram is the primary interface. `redis_gateway.py` and `JobTaskFactory` drive it.
