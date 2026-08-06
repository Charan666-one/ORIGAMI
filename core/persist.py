"""Atomic JSON/text persistence — write to a temp file then os.replace().

Prevents a corrupted store if a write is interrupted or two processes (e.g. the
CLI and `origami monitor`) write the same file. os.replace is atomic on POSIX.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, data: Any) -> None:
    atomic_write_text(Path(path), json.dumps(data, indent=2))


def read_text(path: Path, default: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return default
