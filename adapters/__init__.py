# adapters/base.py
from abc import ABC, abstractmethod
from typing import Optional
import asyncio

class Adapter(ABC):
    """All adapters must inherit from this"""
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with external service. Return True if successful."""
        pass
    
    @abstractmethod
    async def is_authenticated(self) -> bool:
        """Check if still authenticated (token fresh?)"""
        pass
    
    @abstractmethod
    async def refresh(self) -> bool:
        """Refresh auth if needed. Return True if refresh successful."""
        pass
    
    async def _safe_call(self, func, *args, **kwargs):
        """Wrapper: auto-refresh auth if needed, then call."""
        if not await self.is_authenticated():
            await self.refresh()
        try:
            return await func(*args, **kwargs)
        except AuthError:
            await self.refresh()
            return await func(*args, **kwargs)

# Example: Calendar adapter
class CalendarAdapter(Adapter):
    async def authenticate(self) -> bool:
        # OAuth2 flow
        pass
    
    async def get_events(self, start: str, end: str):
        # Safely call API with auto-refresh
        return await self._safe_call(
            self._get_events_impl, start, end
        )
    
    async def _get_events_impl(self, start: str, end: str):
        # Actual API call
        pass