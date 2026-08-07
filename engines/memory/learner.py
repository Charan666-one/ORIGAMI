"""MemoryLearner — passively learn personal facts from what the user says.

Runs on every request (keyless, fast — no LLM) and extracts durable personal
statements ("I like jazz", "my professor is Dr. Sharma", "I work on CareerLens"),
storing new ones so ORIGAMI personalizes over time. Deduped so restating a fact
doesn't pile up. Identity facts (name/from/college/professor) are kept permanently;
preferences/activities are ordinary (subject to the 12-day expiry).
"""

from __future__ import annotations

import re
from typing import Any, List, Tuple

_IDENTITY = ("name", "from", "college", "university", "major", "branch",
             "professor", "teacher", "hometown", "birthday", "surname")

_MY = re.compile(r"\bmy ([a-z][a-z ]{1,25}?) (?:is|are) ([a-z0-9][\w ./&-]{0,40})", re.I)
_PREF = re.compile(r"\bi (like|love|prefer|enjoy|hate|dislike) ([a-z0-9][\w ./&-]{1,40})", re.I)
_ACT = re.compile(r"\bi (use|study|work on|work at|am building|am learning|play) "
                  r"([a-z0-9][\w ./&-]{1,40})", re.I)
_FROM = re.compile(r"\bi'?m from ([a-z][\w ./-]{1,30})", re.I)
_CALL = re.compile(r"\bcall me (\w+)", re.I)


def _trim(value: str) -> str:
    """Cut a captured value at the first clause boundary and strip punctuation."""
    value = re.split(r"\b(and|but|because|so|then)\b|[,.!?;]", value, maxsplit=1)[0]
    return value.strip(" .,-&")


def extract_facts(text: str) -> List[Tuple[str, bool]]:
    """Return (fact, important) pairs found in the text. Conservative on purpose."""
    facts: List[Tuple[str, bool]] = []
    t = f" {text.strip()} "

    for m in _MY.finditer(t):
        subject = m.group(1).strip().lower()
        value = _trim(m.group(2))
        if value and subject not in ("problem", "issue", "question"):
            important = any(w in subject for w in _IDENTITY)
            facts.append((f"My {subject} is {value}", important))
    for m in _PREF.finditer(t):
        value = _trim(m.group(2))
        if value:
            facts.append((f"I {m.group(1).lower()} {value}", False))
    for m in _ACT.finditer(t):
        value = _trim(m.group(2))
        if value:
            facts.append((f"I {m.group(1).lower()} {value}", False))
    for m in _FROM.finditer(t):
        value = _trim(m.group(1))
        if value:
            facts.append((f"I'm from {value}", True))
    for m in _CALL.finditer(t):
        facts.append((f"The user goes by {m.group(1)}", True))
    return facts


class MemoryLearner:
    def __init__(self, memory: Any) -> None:
        self.memory = memory

    def learn(self, text: str) -> List[str]:
        """Store any new personal facts from `text`; return the newly-learned ones."""
        learned: List[str] = []
        for fact, important in extract_facts(text):
            if not self._known(fact):
                self.memory.add(fact, kind="learned", important=important)
                learned.append(fact)
        return learned

    def _known(self, fact: str) -> bool:
        words = {w for w in fact.lower().split() if len(w) > 1}
        if not words:
            return True
        for hit in self.memory.search(fact, limit=4):
            overlap = words & {w for w in hit.text.lower().split() if len(w) > 1}
            if len(overlap) >= max(2, len(words) - 1):  # near-identical already stored
                return True
        return False
