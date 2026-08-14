"""
OTP & 2FA Handler Interface

Provides an abstract interface and fallback handler for requesting and retrieving 
One-Time Passwords (OTPs) or verification codes during automated job applications.
Allows easy integration with external messaging bots (e.g. Telegram, WhatsApp, SMS/Email Webhooks).
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BaseOTPProvider(ABC):
    """Abstract interface for external OTP providers (e.g. Telegram Bot, Webhook, CLI Input)."""

    @abstractmethod
    async def request_otp(
        self,
        portal_name: str,
        user_identifier: str,
        context_msg: str = "",
        timeout_seconds: int = 120
    ) -> Optional[str]:
        """
        Send a notification to the user requesting an OTP, and wait for their response.

        Args:
            portal_name: Name of portal requiring OTP (e.g. 'Moody's', 'Workday', 'Naukri')
            user_identifier: User email or phone associated with the account
            context_msg: Optional guidance message or prompt text from page
            timeout_seconds: Maximum time in seconds to wait for user response

        Returns:
            str: Entered OTP digits/string, or None if timed out / cancelled
        """
        pass


class ConsoleOTPProvider(BaseOTPProvider):
    """Fallback interactive console OTP provider for local execution/testing."""

    async def request_otp(
        self,
        portal_name: str,
        user_identifier: str,
        context_msg: str = "",
        timeout_seconds: int = 120
    ) -> Optional[str]:
        logger.info(f"🔑 OTP Required for {portal_name} ({user_identifier})")
        if context_msg:
            logger.info(f"Context: {context_msg}")
        
        loop = asyncio.get_event_loop()
        try:
            print(f"\n[OTP REQUEST] Enter code for {portal_name} ({user_identifier}): ", end="", flush=True)
            otp = await asyncio.wait_for(
                loop.run_in_executor(None, input),
                timeout=timeout_seconds
            )
            return otp.strip()
        except asyncio.TimeoutError:
            logger.error(f"❌ OTP request timed out after {timeout_seconds} seconds")
            return None


class TelegramOTPProviderPlaceholder(BaseOTPProvider):
    """
    Placeholder/Interface for Telegram Bot OTP integration.
    To be fully implemented in the dedicated Telegram bot project.
    """

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def request_otp(
        self,
        portal_name: str,
        user_identifier: str,
        context_msg: str = "",
        timeout_seconds: int = 120
    ) -> Optional[str]:
        logger.info(f"📱 Telegram Bot OTP Interface Invoked for {portal_name}")
        logger.info("Hook into your Telegram Bot service here by dispatching a message & listening for callback.")
        # Fallback to console if token/chat_id not configured yet
        fallback = ConsoleOTPProvider()
        return await fallback.request_otp(portal_name, user_identifier, context_msg, timeout_seconds)


class OTPManager:
    """Central manager for requesting OTPs during form filling and authentication flows."""

    def __init__(self, provider: Optional[BaseOTPProvider] = None):
        self.provider = provider or ConsoleOTPProvider()

    def set_provider(self, provider: BaseOTPProvider):
        """Register a custom OTP provider (e.g. Telegram, Webhook)."""
        self.provider = provider

    async def get_otp(
        self,
        portal_name: str,
        user_identifier: str,
        context_msg: str = "",
        timeout_seconds: int = 120
    ) -> Optional[str]:
        return await self.provider.request_otp(portal_name, user_identifier, context_msg, timeout_seconds)
