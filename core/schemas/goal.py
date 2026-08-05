"""Goal — a user's intention entering the system (top of the Universal Lifecycle)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Goal:
    """A plain-English intention plus where it came from and any context."""

    text: str
    source: str = "cli"  # cli | api | voice | event | ...
    context: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
