"""EmailSkill — draft an email, keyless (no Gmail API / OAuth).

`email.draft` parses a recipient + message out of plain English and opens a
pre-filled **Gmail compose window in the browser** (reliable for Gmail users; no
default-mail-app setup needed). The user reviews and sends it themselves — that is
the preview→approve contract, with the final send staying in the user's hands.
SAFE (nothing is sent autonomously).

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


def _split_subject_body(written: str, fallback_subject: str) -> tuple[str, str]:
    """Parse a 'Subject: ...\\n<body>' model reply into (subject, body)."""
    lines = written.strip().splitlines()
    for i, line in enumerate(lines):
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip() or fallback_subject[:60]
            body = "\n".join(lines[i + 1:]).strip() or written.strip()
            return subject, body
    return fallback_subject[:60], written.strip()


class EmailSkill(Skill):
    def __init__(self, opener: Optional[Callable[[str], None]] = None, brain: Any = None) -> None:
        self._opener = opener  # injectable for tests
        self.brain = brain     # optional Brain Interface for composing the body

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
            return await self._draft((kwargs.get("text") or "").strip())
        raise ValueError(f"Unknown tool: {tool}")

    # ------------------------------------------------------------------ helpers

    async def _draft(self, text: str) -> str:
        match = _EMAIL.search(text)
        if not match:
            return "I couldn't find a recipient email address in that request."
        to = match.group(0)

        # the instruction is whatever follows the address, minus connective words
        instruction = _LEADING.sub("", text[match.end():]).strip()

        # If a real model is available, WRITE a proper email from the instruction;
        # otherwise fall back to using the instruction text verbatim.
        subject, body = await self._compose(instruction)

        # Gmail web compose — opens a draft tab in the browser (no mail-app setup).
        url = (
            "https://mail.google.com/mail/?view=cm&fs=1&tf=1"
            f"&to={urllib.parse.quote(to)}"
            f"&su={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}"
        )
        self._open(url)
        return (f"Opened a Gmail draft to {to} (subject: '{subject}') in your browser. "
                f"Review it and hit send.")

    async def _compose(self, instruction: str) -> tuple[str, str]:
        """Return (subject, body). Uses the brain to write a real email when a
        model is available; otherwise uses the instruction text verbatim."""
        if not instruction:
            return "Message", "(write your message here)"
        if self.brain is not None and self.brain.can_think():
            try:
                written = await self.brain.generate(
                    f"Write a concise, friendly email for this request: {instruction}. "
                    "Format exactly as:\nSubject: <subject line>\n<body text>"
                )
                return _split_subject_body(written, fallback_subject=instruction)
            except Exception:
                pass  # fall back to literal text on any model error
        subject = instruction[:60] + ("…" if len(instruction) > 60 else "")
        return subject, instruction

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
