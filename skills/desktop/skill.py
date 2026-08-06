"""DesktopSkill — wraps the existing OS desktop adapters (macOS today).

`desktop.open_app` is SAFE — launching an app has no consequence to others, so it
runs immediately without a prompt (same tier as playing music).
"""

from __future__ import annotations

import sys
from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill


class DesktopSkill(Skill):
    def __init__(self, adapter: Any = None) -> None:
        self._adapter = adapter  # injected fake in tests; real one built lazily

    @property
    def adapter(self):
        if self._adapter is None:
            if sys.platform == "darwin":
                from adapters.desktop.mac import MacDesktopAdapter  # lazy import
                self._adapter = MacDesktopAdapter()
            else:
                raise RuntimeError("Desktop control is macOS-only for now.")
        return self._adapter

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="desktop.open_app",
                description="Open (launch) an application by name.",
                params={"app": "the application name, e.g. Safari"},
                risk=Risk.SAFE,
                keywords=("open ", "launch ", "start app"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "desktop.open_app":
            app = (kwargs.get("app") or "").strip()
            if not app:
                return "Which app should I open?"
            try:
                self.adapter.open_application(app)
                return f"Opened {app}"
            except Exception as exc:
                return f"Couldn't open '{app}': {exc}"
        raise ValueError(f"Unknown tool: {tool}")
