# adapters/base.py
from abc import ABC, abstractmethod


class AuthError(Exception):
    """Raised by adapters when a call fails due to expired/invalid auth."""


class Adapter(ABC):
    """All adapters must inherit from this"""

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with external service. Return True if successful."""

    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if still authenticated (token fresh?)"""

    @abstractmethod
    async def refresh(self) -> bool:
        """Refresh auth if needed. Return True if refresh successful."""

    async def _safe_call(self, func, *args, **kwargs):
        """Wrapper: auto-refresh auth if needed, then call."""
        if not await self.is_authenticated():
            await self.refresh()
        try:
            return await func(*args, **kwargs)
        except AuthError:
            await self.refresh()
            return await func(*args, **kwargs)
