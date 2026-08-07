"""CodebaseStore — persistent per-codebase understanding (~/.origami/codebases.json).

This is the 'learning with each codebase': every scan records what ORIGAMI learned
(structure + the local model's explanation), so later questions use stored
knowledge instead of re-scanning or calling anything external.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from core.persist import atomic_write_json, read_text


class CodebaseStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "codebases.json"
        self._data: Dict[str, dict] = self._load()

    def _load(self) -> Dict[str, dict]:
        raw = read_text(self.path)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def save(self, name: str, profile: dict) -> None:
        profile = dict(profile)
        profile["scanned_at"] = time.time()
        self._data[name.lower()] = profile
        atomic_write_json(self.path, self._data)

    def get(self, name: str) -> Optional[dict]:
        return self._data.get(name.lower())

    def names(self) -> List[str]:
        return list(self._data.keys())

    def all(self) -> Dict[str, dict]:
        return dict(self._data)
