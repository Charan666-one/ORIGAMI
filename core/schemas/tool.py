"""ToolSpec — the self-describing contract every capability registers.

The `Risk` enum is the 3-tier permission model from PURPOSE.md. It replaces a
binary confirm flag so the executor can distinguish "affects other people"
(CONFIRM) from "irreversible / costly" (CRITICAL). Baked in from C1 because
retrofitting a risk gate after the executor exists is expensive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Tuple


class Risk(str, Enum):
    SAFE = "safe"          # 🟢 reads, search, open app, play music — runs immediately
    CONFIRM = "confirm"    # 🟡 send message/email, git push — needs user confirmation
    CRITICAL = "critical"  # 🔴 delete, money, robot movement — explicit approval always


@dataclass
class ToolSpec:
    """Describes one callable capability. `keywords` let the keyless EchoEngine
    map a goal to this tool with zero core/engine edits when new tools are added."""

    name: str                       # e.g. "spotify.search_and_play"
    description: str
    params: Dict[str, str] = field(default_factory=dict)  # param name -> description
    risk: Risk = Risk.SAFE
    keywords: Tuple[str, ...] = ()  # phrases that route intent to this tool
    fallback: bool = False          # catch-all when no keyword matches (chat -> brain)
