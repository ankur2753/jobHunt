"""
Retry Utilities for Naukri Automation

Provides decorator and utility functions for retrying failed operations with:
- Exponential backoff
- Maximum retry attempts
- Logging at each attempt
- Customizable exceptions to catch

Usage:
    @retry_async(max_attempts=3, backoff=2, initial_delay=1)
    async def my_flaky_operation():
        ...
"""

import asyncio
import logging
import functools
from typing import Callable, Type, Tuple, Any, Optional

logger = logging.getLogger(__name__)


class RetryException(Exception):
    """Raised when all retry attempts are exhausted."""
    
    def __init__(self, message: str, last_exception: Exception = None):
        self.message = message
        self.last_exception = last_exception
        super().__init__(self.message)


def retry_async(
    max_attempts: int = 3,
    backoff: float = 2.0,
    initial_delay: float = 0.5,
    catch_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator for retrying async functions with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff: Exponential backoff multiplier (delay *= backoff each retry)
        initial_delay: Initial delay in seconds before first retry
        catch_exceptions: Tuple of exception types to catch and retry on
        on_retry: Optional callback function(attempt, delay, exception) on each retry
    
    Returns:
        Decorated async function
        
    Example:
        @retry_async(max_attempts=3, backoff=2, initial_delay=1)
        async def fetch_data():
            # May fail transiently
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = initial_delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.debug(f"Attempt {attempt}/{max_attempts} for {func.__name__}")
                    result = await func(*args, **kwargs)
                    
                    if attempt > 1:
                        logger.info(f"✅ {func.__name__} succeeded on attempt {attempt}")
                    
                    return result
                
                except catch_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts:
                        logger.warning(
                            f"⚠️  Attempt {attempt} failed for {func.__name__}: {str(e)[:100]}"
                        )
                        
                        # Call on_retry callback if provided
                        if on_retry:
                            on_retry(attempt, delay, e)
                        
                        logger.debug(f"   Retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        delay *= backoff
                    else:
                        logger.error(
                            f"❌ All {max_attempts} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            # All attempts exhausted
            raise RetryException(
                f"Failed after {max_attempts} attempts: {func.__name__}",
                last_exception
            )
        
        return wrapper
    
    return decorator


def retry_selector(
    selector: str,
    max_attempts: int = 3,
    timeout_per_attempt: int = 5000
):
    """
    Decorator for retrying selector queries with timeout.
    
    Args:
        selector: CSS selector to find
        max_attempts: Maximum attempts to find selector
        timeout_per_attempt: Timeout in ms for each attempt
    
    Returns:
        Decorated function
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.debug(
                        f"Selector attempt {attempt}/{max_attempts}: {selector[:50]}"
                    )
                    
                    # Try to find selector with timeout
                    element = await self.page.query_selector(selector)
                    
                    if element:
                        logger.debug(f"✅ Selector found: {selector[:50]}")
                        return await func(self, element, *args, **kwargs)
                    else:
                        raise ValueError(f"Selector not found: {selector}")
                
                except Exception as e:
                    if attempt < max_attempts:
                        logger.debug(
                            f"⚠️  Attempt {attempt} failed: {str(e)[:80]}"
                        )
                        await asyncio.sleep(1)  # Wait before retry
                    else:
                        logger.error(
                            f"❌ Failed to find selector after {max_attempts} attempts: {selector}"
                        )
                        raise
        
        return wrapper
    
    return decorator


async def retry_until_visible(
    page,
    selector: str,
    max_attempts: int = 5,
    timeout_ms: int = 1000,
    initial_delay: float = 0.5
) -> bool:
    """
    Retry until element matching selector is visible.
    
    Args:
        page: Playwright page object
        selector: CSS selector to find
        max_attempts: Maximum retry attempts
        timeout_ms: Timeout for each visibility check
        initial_delay: Delay before first check
    
    Returns:
        True if element became visible, False otherwise
    """
    delay = initial_delay
    
    for attempt in range(1, max_attempts + 1):
        await asyncio.sleep(delay)
        
        try:
            element = await page.query_selector(selector)
            if element:
                is_visible = await element.is_visible()
                if is_visible:
                    logger.debug(f"✅ Element visible: {selector[:40]}")
                    return True
                else:
                    logger.debug(f"Element found but not visible (attempt {attempt}/{max_attempts})")
            else:
                logger.debug(f"Element not found (attempt {attempt}/{max_attempts})")
        
        except Exception as e:
            logger.debug(f"Error checking visibility: {str(e)}")
        
        delay *= 1.5  # Exponential backoff
    
    logger.warning(f"Element did not become visible after {max_attempts} attempts: {selector}")
    return False


async def retry_until_enabled(
    page,
    selector: str,
    max_attempts: int = 5,
    timeout_ms: int = 1000
) -> bool:
    """
    Retry until element matching selector is enabled.
    
    Args:
        page: Playwright page object
        selector: CSS selector to find
        max_attempts: Maximum retry attempts
        timeout_ms: Timeout for each check
    
    Returns:
        True if element became enabled, False otherwise
    """
    for attempt in range(1, max_attempts + 1):
        try:
            element = await page.query_selector(selector)
            if element:
                is_enabled = await element.is_enabled()
                if is_enabled:
                    logger.debug(f"✅ Element enabled: {selector[:40]}")
                    return True
                else:
                    logger.debug(f"Element not enabled (attempt {attempt}/{max_attempts})")
            
            if attempt < max_attempts:
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.debug(f"Error checking enabled state: {str(e)}")
    
    logger.warning(f"Element did not become enabled after {max_attempts} attempts: {selector}")
    return False


if __name__ == "__main__":
    print("Retry utilities for Naukri automation")
    print("Usage: from scripts.common_stuff.retry_utils import retry_async")
