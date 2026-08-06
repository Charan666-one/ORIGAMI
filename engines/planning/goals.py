"""GoalBook — persistent store of long-running goals (~/.origami/goals.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from core.persist import atomic_write_json, read_text
from core.schemas.goal_state import GoalState, Milestone

_STOP = {"the", "a", "an", "to", "of", "and", "my", "me", "for", "get", "become", "in"}


def _tokens(text: str) -> set:
    return {w for w in text.lower().split() if w not in _STOP and len(w) > 2}


class GoalBook:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "goals.json"
        self._goals: List[GoalState] = self._load()

    def _load(self) -> List[GoalState]:
        raw = read_text(self.path)
        if not raw:
            return []
        try:
            return [GoalState.from_dict(g) for g in json.loads(raw)]
        except Exception:
            return []

    def _save(self) -> None:
        atomic_write_json(self.path, [g.to_dict() for g in self._goals])

    def add(self, title: str, milestone_texts: List[str]) -> GoalState:
        goal = GoalState(title=title.strip(),
                         milestones=[Milestone(text=t) for t in milestone_texts])
        self._goals.append(goal)
        self._save()
        return goal

    def active(self) -> List[GoalState]:
        return [g for g in self._goals if g.status == "active"]

    def all(self) -> List[GoalState]:
        return list(self._goals)

    def latest(self) -> Optional[GoalState]:
        act = self.active()
        return max(act, key=lambda g: g.created_at) if act else None

    def match(self, query: str) -> Optional[GoalState]:
        """Best active goal for a query (keyword overlap), else the latest active one."""
        q = _tokens(query)
        if q:
            best, best_score = None, 0
            for g in self.active():
                score = len(q & _tokens(g.title))
                if score > best_score:
                    best, best_score = g, score
            if best is not None:
                return best
        return self.latest()

    def complete_milestone(self, goal: GoalState, query: str = "") -> Optional[Milestone]:
        """Mark a milestone done: the best text match, else the next open one."""
        q = _tokens(query)
        target = None
        if q:
            for m in goal.next_open():
                if q & _tokens(m.text):
                    target = m
                    break
        if target is None:
            opens = goal.next_open()
            target = opens[0] if opens else None
        if target is None:
            return None
        target.done = True
        if not goal.next_open():
            goal.status = "achieved"
        self._save()
        return target
