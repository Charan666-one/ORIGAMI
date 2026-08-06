"""EmailSkill — draft an email, keyless (no Gmail API / OAuth).

`email.draft` parses a recipient + message out of plain English and opens a
pre-filled compose window in the default mail app via a `mailto:` link. The user
reviews and sends it themselves — that is the preview→approve contract, with the
final send staying in the user's hands. SAFE (nothing is sent autonomously).

A later upgrade can add `email.send` (CONFIRM) that sends programmatically via the
Gmail API — but that needs OAuth, so the keyless draft path comes first.
"""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.parse
from typing import Any, Callable, List, Optional

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LEADING = re.compile(r"^(to|about|saying|that|:|,|-|\s)+", re.IGNORECASE)


class EmailSkill(Skill):
    def __init__(self, opener: Optional[Callable[[str], None]] = None) -> None:
        self._opener = opener  # injectable for tests

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="email.draft",
                description="Open a pre-filled email draft in your mail app to review and send.",
                params={"text": "recipient email and the message"},
                risk=Risk.SAFE,
                keywords=("email", "e-mail", "draft mail", "draft a mail",
                          "mail to", "send mail", "compose mail", "write mail"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "email.draft":
            return self._draft((kwargs.get("text") or "").strip())
        raise ValueError(f"Unknown tool: {tool}")

    # ------------------------------------------------------------------ helpers

    def _draft(self, text: str) -> str:
        match = _EMAIL.search(text)
        if not match:
            return "I couldn't find a recipient email address in that request."
        to = match.group(0)

        # the message is whatever follows the address, minus connective words
        after = _LEADING.sub("", text[match.end():]).strip()
        body = after or "(write your message here)"
        subject = "Message" if not after else (body[:60] + ("…" if len(body) > 60 else ""))

        url = (
            f"mailto:{to}?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}"
        )
        self._open(url)
        return (f"Drafted an email to {to} (subject: '{subject}') — opened in your "
                f"mail app. Review it and hit send.")

    def _open(self, url: str) -> None:
        if self._opener is not None:
            self._opener(url)
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", url], check=False)
            elif sys.platform.startswith("win"):
                subprocess.run(["cmd", "/c", "start", "", url], check=False)
            else:
                subprocess.run(["xdg-open", url], check=False)
        except Exception:
            pass
