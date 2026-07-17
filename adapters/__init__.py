"""Layer 4 plumbing — raw API/OS clients. Skills wrap these; never reimplement them."""

from adapters.base import Adapter, AuthError

__all__ = ["Adapter", "AuthError"]
