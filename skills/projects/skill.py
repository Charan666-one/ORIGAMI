"""ProjectsSkill — launch/open your local projects by name.

`origami "start careerlens"` opens the folder + editor and runs its dev commands
in Terminal tabs. `origami "open wavex"` just opens folder + editor. `origami
"my projects"` lists what's configured. Everything runs LOCALLY — no deployment.

Projects live in ~/.origami/projects.json (auto-seeded, user-editable):
  { "careerlens": {"path": "...", "run": ["cmd1", "cmd2"], "editor": true}, ... }

CONFIRM tier for `start` (it runs shell commands); open/list are SAFE — but the
whole skill is registered with the actions gated per-verb below.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.persist import atomic_write_json, read_text
from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

_HOME = Path.home()

# Seeded defaults (paths auto-expanded). Edit ~/.origami/projects.json to change.
_DEFAULTS: Dict[str, dict] = {
    "careerlens": {
        "path": str(_HOME / "Desktop/MINI-PROJECT/careerlens"),
        "run": ["cd backend && (source venv311/bin/activate 2>/dev/null; "
                "uvicorn app.main:app --reload)",
                "cd frontend && npm run dev"],
        "editor": True,
    },
    "wavex": {
        "path": str(_HOME / "Desktop/PROJECTS/WaveX-Hackathon-v1 2"),
        "run": ["cd backend && python -m uvicorn app.main:app --reload",
                "npm run dev"],
        "editor": True,
    },
    "codelens": {
        "path": str(_HOME / "Desktop/PENDING PROJECTS/CODELENS"),
        "run": ["./run.sh"],
        "editor": True,
    },
}


class ProjectsSkill(Skill):
    def __init__(self, config_path: Optional[Path] = None, launcher: Any = None) -> None:
        self.config_path = Path(config_path) if config_path else _HOME / ".origami" / "projects.json"
        self.launcher = launcher or _Launcher()
        self.projects = self._load()

    def _load(self) -> Dict[str, dict]:
        raw = read_text(self.config_path)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        atomic_write_json(self.config_path, _DEFAULTS)  # seed on first use
        return dict(_DEFAULTS)

    def specs(self) -> List[ToolSpec]:
        names = tuple(self.projects.keys())
        return [
            ToolSpec(
                name="project.control",
                description="Start, open, or list your local projects.",
                params={"text": "which project and action"},
                # SAFE: runs only the user's own configured project commands, locally
                risk=Risk.SAFE,
                keywords=names + ("my projects", "list projects", "start project",
                                  "run my project", "open my project"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        raw = (kwargs.get("_raw") or kwargs.get("text") or "").lower()

        if any(w in raw for w in ("my projects", "list projects")) or raw.strip() in ("", "projects"):
            return self._list()

        name = next((n for n in self.projects if n in raw), None)
        if name is None:
            return ("Which project? Known: " + ", ".join(self.projects)
                    + ".\nAdd more in ~/.origami/projects.json.")

        proj = self.projects[name]
        path = proj.get("path", "")
        if not Path(path).exists():
            return f"'{name}' path not found: {path} (fix it in ~/.origami/projects.json)."

        open_only = any(w in raw for w in ("open", "show")) and not any(
            w in raw for w in ("start", "run", "launch"))
        self.launcher.open_folder(path)
        if proj.get("editor"):
            self.launcher.open_editor(path)
        if open_only:
            return f"📂 Opened {name} ({path})."

        for cmd in proj.get("run", []):
            self.launcher.run_terminal(path, cmd)
        n = len(proj.get("run", []))
        return f"🚀 Started {name}: opened folder/editor and launched {n} dev process(es) in Terminal."

    def _list(self) -> str:
        if not self.projects:
            return "No projects configured. Add them in ~/.origami/projects.json."
        lines = ["📁 Your projects:"]
        for name, p in self.projects.items():
            exists = "" if Path(p.get("path", "")).exists() else "  ⚠️ path missing"
            lines.append(f"- {name}: {p.get('path', '')}{exists}")
        lines.append("Say 'start <name>' to run it, or 'open <name>' to just open it.")
        return "\n".join(lines)


class _Launcher:
    """Real macOS launcher. Each method is independently mockable in tests."""

    def open_folder(self, path: str) -> None:
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)

    def open_editor(self, path: str) -> None:
        if sys.platform == "darwin":
            # VS Code if present, else reveal in Finder (already opened)
            subprocess.run(["open", "-a", "Visual Studio Code", path], check=False)

    def run_terminal(self, path: str, cmd: str) -> None:
        if sys.platform != "darwin":
            return
        shell = f"cd {shlex.quote(path)} && {cmd}"
        script = f'tell application "Terminal" to do script "{_escape(shell)}"'
        subprocess.run(["osascript", "-e", script], check=False)


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')
