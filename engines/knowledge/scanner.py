"""scan_codebase — walk a repo and extract a structural profile (keyless, no LLM).

Returns languages, top-level structure, key-file contents, and size. The brain
turns this into a human explanation elsewhere; this part is pure filesystem work.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict

_SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "venv311", "__pycache__",
              "dist", "build", ".next", ".pytest_cache", "site-packages", ".idea"}
_KEY_FILES = {"readme.md", "readme", "package.json", "pyproject.toml",
              "requirements.txt", "dockerfile", "docker-compose.yml", "main.py",
              "app.py", "index.js", "index.ts", "server.py", "run.sh", "makefile",
              "cargo.toml", "go.mod"}
_LANG = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
         ".jsx": "JavaScript", ".java": "Java", ".go": "Go", ".rs": "Rust",
         ".c": "C", ".cpp": "C++", ".html": "HTML", ".css": "CSS", ".rb": "Ruby",
         ".ipynb": "Jupyter", ".sh": "Shell"}


def scan_codebase(path: str, max_files: int = 4000, snippet_chars: int = 1500) -> Dict:
    root = Path(path).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Path not found: {path}")

    langs: Counter = Counter()
    key_files: Dict[str, str] = {}
    total = 0

    for p in root.rglob("*"):
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        total += 1
        if total > max_files:
            break
        ext = p.suffix.lower()
        if ext in _LANG:
            langs[_LANG[ext]] += 1
        name = p.name.lower()
        if name in _KEY_FILES and len(key_files) < 8:
            try:
                key_files[str(p.relative_to(root))] = p.read_text(errors="ignore")[:snippet_chars]
            except Exception:
                pass

    structure = sorted(
        d.name for d in root.iterdir()
        if d.is_dir() and d.name not in _SKIP_DIRS and not d.name.startswith("."))

    return {
        "path": str(root),
        "total_files": total,
        "languages": dict(langs.most_common(8)),
        "structure": structure[:20],
        "key_files": key_files,
    }
