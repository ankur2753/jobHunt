"""
Base ATS Adapter Interface
Defines the standard contract for all portal-specific ATS adapters (Workday, Greenhouse, Lever, etc.).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from playwright.async_api import Page


class BaseATSAdapter(ABC):
    """Abstract interface for all ATS portal adapters."""

    def __init__(self, page: Page):
        self.page = page

    @classmethod
    @abstractmethod
    def adapter_name(cls) -> str:
        """Return human-readable name of the ATS adapter."""
        pass

    @classmethod
    @abstractmethod
    def can_handle(cls, url: str, html_snippet: str = "") -> bool:
        """
        Check if this adapter can handle the target URL or page content.
        
        Args:
            url: Target job URL
            html_snippet: Optional HTML content snippet of the page
        """
        pass

    @abstractmethod
    async def apply(
        self,
        resume_path: str,
        user_profile: Dict[str, Any],
        review_mode: bool = True,
        cover_letter_path: Optional[str] = None,
        **kwargs: Any
    ) -> bool:
        """
        Execute the multi-step application workflow for this ATS.
        
        Args:
            resume_path: Absolute path to user's resume file
            user_profile: User profile details dictionary
            review_mode: If True, pause before final submission for human review
            cover_letter_path: Optional absolute path to user's cover letter file
            
        Returns:
            bool: True if application completed/paused for review, False if failed
        """
        pass

    async def _human_pause(self, min_ms: int = 400, max_ms: int = 1200):
        """Pause for a randomized human-like delay."""
        import random
        await self.page.wait_for_timeout(random.randint(min_ms, max_ms))

    async def _move_human_mouse(self):
        """Emulate realistic human mouse movement across the viewport."""
        import random
        try:
            bounds = await self.page.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
            x = random.randint(0, max(0, bounds['w'] - 1))
            y = random.randint(0, max(0, bounds['h'] - 1))
            await self.page.mouse.move(x, y, steps=random.randint(4, 12))
        except Exception:
            pass

    async def _human_scroll_into_view(self, field_locator):
        """Scroll element into view with human pause."""
        try:
            await field_locator.scroll_into_view_if_needed()
            await self._human_pause(400, 1000)
        except Exception:
            pass

    async def _human_type(self, field_locator, text: str):
        """Type text character-by-character with realistic keypress delays."""
        import random
        await self._human_scroll_into_view(field_locator)
        await self._move_human_mouse()
        await field_locator.click()
        await self._human_pause(200, 500)
        for char in text:
            await field_locator.type(char, delay=random.randint(30, 90))
        await self._human_pause(300, 800)

    async def dismiss_popups(self) -> int:
        """
        Detect and dismiss cookie consent banners, chatbot widgets, and popups
        obscuring form fields before human/bot interaction.
        """
        from scripts.common_stuff.retry_utils import dismiss_overlays_and_popups
        return await dismiss_overlays_and_popups(self.page)

    async def verify_submission(self, timeout_ms: int = 5000):
        """
        Verify that the form was submitted successfully by explicitly checking
        for form validation errors.
        
        Raises:
            Exception: If validation errors are detected after submit.
        """
        # Save URL before waiting
        initial_url = self.page.url
        
        # Wait briefly for DOM mutations or network changes
        await self.page.wait_for_timeout(2000)
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass

        error_found = False

        # 1. Explicitly scan the DOM for validation error messages
        error_selectors = [
            '[aria-invalid="true"]',
            '.error',
            '.invalid-feedback',
            '.has-error',
            '.just-validate-error-label',
            '.validation-error',
            '.alert-danger',
            '.form-error'
        ]
        
        for sel in error_selectors:
            try:
                loc = self.page.locator(sel)
                count = await loc.count()
                for i in range(count):
                    el = loc.nth(i)
                    if await el.is_visible():
                        # ensure it has some text
                        text = await el.text_content()
                        if text and text.strip():
                            error_found = True
                            break
            except Exception:
                pass
            if error_found:
                break

        # 2. Heuristically check for visible red text (often used for validation)
        if not error_found:
            try:
                has_red_text = await self.page.evaluate('''() => {
                    const elements = Array.from(document.querySelectorAll('span, div, p, label, small'));
                    for (let el of elements) {
                        const style = window.getComputedStyle(el);
                        // Check common red color formats
                        if (style.color === 'rgb(255, 0, 0)' || style.color.includes('220, 53, 69')) {
                            if (el.innerText && el.innerText.trim().length > 0 && el.offsetHeight > 0 && el.offsetWidth > 0) {
                                return true;
                            }
                        }
                    }
                    return false;
                }''')
                if has_red_text:
                    error_found = True
            except Exception:
                pass

        # 3. Check if form elements have completely disappeared (success heuristic)
        # Check if URL changed (likely success)
        url_changed = self.page.url != initial_url
        
        form_still_visible = False
        try:
            # Check if any common form input or submit button is still visible
            form_still_visible = await self.page.evaluate('''() => {
                const inputs = document.querySelectorAll('input[type="text"], input[type="email"], select, textarea');
                for (let el of inputs) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0) return true;
                }
                const buttons = document.querySelectorAll('button[type="submit"], input[type="submit"]');
                for (let el of buttons) {
                    if (el.offsetWidth > 0 && el.offsetHeight > 0) return true;
                }
                return false;
            }''')
        except Exception:
            pass

        if error_found:
            raise Exception("Form validation failed after submit: validation errors detected.")
            
        if not url_changed and form_still_visible:
            raise Exception("Form validation failed after submit: form still visible and URL did not change.")

        # 4. Visual LLM Verification using CustomLLMAgent
        try:
            from scripts.common_stuff.custom_llm_agent import CustomLLMAgent

            prompt = (
                "You are an expert at analyzing web pages. "
                "Look at this screenshot of a job application form. "
                "Determine if the application was submitted successfully (e.g., 'Thank you for applying', a tick mark, etc.) "
                "or if it failed (e.g., validation errors, 'Please fix the errors below'). "
                "Reply EXACTLY with 'SUCCESS' if it was successful, or 'FAILURE' if it failed or if you see validation errors."
            )

            agent = CustomLLMAgent()
            output = await agent.analyze_image(self.page, prompt)

            if output and "FAILURE" in output.upper():
                raise Exception("Visual LLM verification determined that the form validation failed after submit.")

        except Exception as e:
            if "Visual LLM verification determined" in str(e):
                raise e
            # Log or gracefully ignore other visual LLM errors so we don't block success if the LLM call fails
            print(f"[Warning] Visual LLM verification encountered an error: {e}")



