"""DesktopSkill — control the Mac: apps, volume, screenshot, lock, clipboard, URLs.

Wraps the existing MacDesktopAdapter. Opening/reading is SAFE; there are no
destructive actions here (lock/screenshot/volume are reversible), so all SAFE.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

_NUM = re.compile(r"\d+")
# a target that looks like a URL/domain (has a dot, no spaces) rather than an app
_URLISH = re.compile(r"^(https?://|[\w-]+(\.[\w-]+)+)", re.IGNORECASE)


def _looks_like_url(target: str) -> bool:
    return " " not in target and bool(_URLISH.match(target))


class DesktopSkill(Skill):
    def __init__(self, adapter: Any = None) -> None:
        self._adapter = adapter

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
        # open_url before open_app so "open website X" isn't caught by "open "
        return [
            ToolSpec(name="desktop.open_url", description="Open a website/URL in the browser.",
                     params={"url": "the website or URL"}, risk=Risk.SAFE,
                     keywords=("open website", "open the website", "open url", "open link",
                               "open the site")),
            ToolSpec(name="desktop.open_app", description="Open (launch) an application.",
                     params={"app": "the application name"}, risk=Risk.SAFE,
                     keywords=("open ", "launch ", "start app")),
            ToolSpec(name="desktop.close_app", description="Quit (close) an application.",
                     params={"app": "the application name"}, risk=Risk.SAFE,
                     keywords=("close ", "quit ", "exit ")),
            ToolSpec(name="desktop.set_volume", description="Set the system volume (0–100).",
                     params={"level": "volume level 0-100"}, risk=Risk.SAFE,
                     keywords=("set volume", "volume to", "change volume", "volume ")),
            ToolSpec(name="desktop.unmute", description="Unmute the system.", risk=Risk.SAFE,
                     keywords=("unmute",)),
            ToolSpec(name="desktop.mute", description="Mute the system.", risk=Risk.SAFE,
                     keywords=("mute",)),
            ToolSpec(name="desktop.screenshot", description="Take a screenshot.", risk=Risk.SAFE,
                     keywords=("screenshot", "take a screenshot", "capture the screen",
                               "capture screen")),
            ToolSpec(name="desktop.lock", description="Lock the screen.", risk=Risk.SAFE,
                     keywords=("lock the screen", "lock my mac", "lock screen", "lock the mac")),
            ToolSpec(name="desktop.clipboard", description="Read what's on the clipboard.",
                     risk=Risk.SAFE,
                     keywords=("clipboard", "what did i copy", "what's copied", "whats copied")),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        try:
            return self._dispatch(tool, kwargs)
        except Exception as exc:  # graceful — a failed OS action is data, not a crash
            return f"Couldn't do that: {exc}"

    def _dispatch(self, tool: str, kwargs: dict) -> str:
        if tool == "desktop.open_app":
            target = (kwargs.get("app") or "").strip()
            if not target:
                return "Which app or site should I open?"
            return self._open_target(target)
        if tool == "desktop.close_app":
            app = (kwargs.get("app") or "").strip()
            if not app:
                return "Which app should I close?"
            self.adapter.quit_application(app)
            return f"Closed {app}"
        if tool == "desktop.open_url":
            url = (kwargs.get("url") or "").strip()
            if not url:
                return "Which website should I open?"
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            self.adapter.open_url(url)
            return f"Opened {url}"
        if tool == "desktop.set_volume":
            m = _NUM.search(kwargs.get("level") or "")
            if not m:
                return "Give me a level 0–100, e.g. 'set volume to 40'."
            level = max(0, min(100, int(m.group())))
            self.adapter.set_volume(level)
            return f"🔊 Volume set to {level}"
        if tool == "desktop.mute":
            self.adapter.mute()
            return "🔇 Muted"
        if tool == "desktop.unmute":
            self.adapter.unmute()
            return "🔊 Unmuted"
        if tool == "desktop.screenshot":
            path = Path.home() / "Desktop" / f"origami_{int(time.time())}.png"
            saved = self.adapter.take_screenshot(output_path=path)
            return f"📸 Screenshot saved to {saved}"
        if tool == "desktop.lock":
            self.adapter.lock_screen()
            return "🔒 Locked."
        if tool == "desktop.clipboard":
            text = self.adapter.get_clipboard()
            return f"📋 Clipboard: {text}" if text else "Clipboard is empty."
        raise ValueError(f"Unknown tool: {tool}")

    def _open_target(self, target: str) -> str:
        """Open an app OR a website. 'open github.com' / 'open google.com' are
        websites; 'open Safari' / 'open Notes' are apps; a bare name that isn't an
        app (e.g. 'open reddit') falls back to <name>.com."""
        if _looks_like_url(target):
            url = target if target.startswith(("http://", "https://")) else "https://" + target
            self.adapter.open_url(url)
            return f"Opened {url}"
        try:
            self.adapter.open_application(target)
            return f"Opened {target}"
        except Exception:
            # not an installed app -> treat as a website (reddit -> reddit.com)
            host = target if "." in target else target.replace(" ", "") + ".com"
            url = "https://" + host
            self.adapter.open_url(url)
            return f"'{target}' isn't an app — opened {url} instead."
