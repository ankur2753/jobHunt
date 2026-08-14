"""
ATS Adapter Registry
Provides dynamic registration and selection of ATS adapters.
"""

import logging
from typing import List, Type, Optional
from playwright.async_api import Page

from .base_adapter import BaseATSAdapter

logger = logging.getLogger(__name__)


class ATSAdapterRegistry:
    """Registry class for discovering and matching ATS adapters."""

    _adapters: List[Type[BaseATSAdapter]] = []

    @classmethod
    def register(cls, adapter_cls: Type[BaseATSAdapter]) -> Type[BaseATSAdapter]:
        """Decorator to register an ATS adapter class."""
        if adapter_cls not in cls._adapters:
            cls._adapters.append(adapter_cls)
            logger.info(f"Registered ATS Adapter: {adapter_cls.adapter_name()}")
        return adapter_cls

    @classmethod
    def list_registered_adapters(cls) -> List[str]:
        """Return list of registered adapter names."""
        return [adapter.adapter_name() for adapter in cls._adapters]

    @classmethod
    async def get_adapter(cls, page: Page, url: str) -> BaseATSAdapter:
        """
        Find matching registered adapter for URL or page content.
        Falls back to GenericATSAdapter if no specific adapter matches.
        """
        html_snippet = ""
        if page:
            try:
                html_snippet = (await page.content())[:20000]
            except Exception:
                pass

        for adapter_cls in cls._adapters:
            # Avoid matching generic adapter in the loop
            if adapter_cls.adapter_name() == "Generic ATS":
                continue
                
            if adapter_cls.can_handle(url, html_snippet):
                logger.info(f"🎯 Matched ATS Adapter: {adapter_cls.adapter_name()} for URL: {url}")
                return adapter_cls(page)

        # Fallback to GenericATSAdapter
        from .generic_adapter import GenericATSAdapter
        logger.info(f"🌐 No specific ATS matched. Falling back to Generic ATS for URL: {url}")
        return GenericATSAdapter(page)
