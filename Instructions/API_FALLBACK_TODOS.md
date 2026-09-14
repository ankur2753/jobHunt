# API fallback and model cascading tasks

- [x] Define the `CustomLLMAgent` class.
- [x] Implement `take_screenshot_base64(page)` helper.
- [x] Implement the `run_cascade(page, fast_model, expensive_model)` orchestrator.
- [x] Ensure the cheap model is hard-capped at 3 iterations.
- [x] Ensure `page.reload()` is called before handing off to the expensive model.
- [x] Hook the custom loop into `apply_custom_job.py` and remove `AgentRuntime.invoke()`.

To run this custom API fallback, add `LLM_API_KEY` and `LLM_BASE_URL` to your `.env` file. You also need to install the OpenAI package with `pip install openai`.
