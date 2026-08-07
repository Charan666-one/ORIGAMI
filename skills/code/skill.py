"""CodeSkill — understand any codebase with the LOCAL model, and remember it.

`scan <path|project>` walks a repo, has the local brain explain it, and stores
that understanding (~/.origami/codebases.json) so it accumulates knowledge with
each codebase — no API key, no external service. `explain`/`ask` use the stored
knowledge. Project names resolve via ~/.origami/projects.json (the launcher config).

Foundation for the later build/debug phase: once a codebase is understood and
stored, the same local brain can reason about changes with that context.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List, Optional

from core.persist import read_text
from core.schemas.tool import Risk, ToolSpec
from engines.knowledge.codebases import CodebaseStore
from engines.knowledge.scanner import scan_codebase
from engines.reasoning.llm import Task
from skills.base import Skill


class CodeSkill(Skill):
    def __init__(self, brain: Any, store: Optional[CodebaseStore] = None,
                 memory: Any = None, projects_path: Optional[Path] = None) -> None:
        self.brain = brain
        self.store = store or CodebaseStore()
        self.memory = memory
        self.projects_path = projects_path or Path.home() / ".origami" / "projects.json"

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(name="code.scan",
                     description="Scan a codebase (path or project name), understand it, remember it.",
                     params={"text": "path or project name"}, risk=Risk.SAFE,
                     keywords=("scan ", "analyze the code", "analyze codebase",
                               "understand the codebase", "understand this repo",
                               "scan the repo", "scan codebase")),
            ToolSpec(name="code.forget", description="Forget a learned codebase.",
                     params={"text": "codebase name"}, risk=Risk.SAFE,
                     keywords=("forget the codebase", "forget codebase", "remove codebase",
                               "delete codebase")),
            ToolSpec(name="code.list", description="List codebases ORIGAMI has learned.",
                     risk=Risk.SAFE,
                     keywords=("scanned codebases", "my codebases", "learned codebases",
                               "what codebases")),
            ToolSpec(name="code.ask",
                     description="Ask a question about a scanned codebase.",
                     params={"text": "codebase and question"}, risk=Risk.SAFE,
                     keywords=("ask about the code", "about the codebase",
                               "question about the code")),
            ToolSpec(name="code.explain",
                     description="Explain what a scanned codebase does.",
                     params={"text": "codebase name"}, risk=Risk.SAFE,
                     keywords=("explain the code", "explain the codebase",
                               "what does the code", "explain this project's code")),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        raw = (kwargs.get("_raw") or kwargs.get("text") or "").strip()
        if tool == "code.list":
            return self._list()
        if tool == "code.forget":
            target = (kwargs.get("text") or raw).strip()
            name = self._name_in(target) or target
            return (f"🗑️ Forgot codebase '{name}'." if self.store.forget(name)
                    else f"I don't have a codebase called '{name}'.")
        if tool == "code.scan":
            return await self._scan(kwargs.get("text", raw).strip())
        if tool == "code.explain":
            return self._explain(self._name_in(raw))
        if tool == "code.ask":
            return await self._ask(raw)
        raise ValueError(f"Unknown tool: {tool}")

    # ------------------------------------------------------------------ actions

    async def _scan(self, target: str) -> str:
        path, name = self._resolve(target)
        if not path:
            return (f"Couldn't find '{target}'. Give a path, or a project name from "
                    f"~/.origami/projects.json.")
        try:
            profile = scan_codebase(path)
        except Exception as exc:
            return f"Couldn't scan: {exc}"

        # Save the structure FIRST — resilient: a slow/timed-out model never loses the scan.
        record = {
            "path": profile["path"], "languages": profile["languages"],
            "structure": profile["structure"], "total_files": profile["total_files"],
            "summary": "",
        }
        self.store.save(name, record)

        summary = await self._explain_profile(name, profile)
        if summary:
            record["summary"] = summary
            self.store.save(name, record)
            if self.memory is not None:
                try:
                    self.memory.add(f"My codebase '{name}': {summary[:200]}", important=True)
                except Exception:
                    pass

        langs = ", ".join(f"{k} ({v})" for k, v in profile["languages"].items()) or "—"
        head = (f"🔍 Scanned {name} — {profile['total_files']} files\n"
                f"Languages: {langs}\nStructure: {', '.join(profile['structure']) or '—'}")
        if summary:
            return f"{head}\n\n{summary}"
        return head + ("\n(Structure saved. Start `ollama serve` for a written "
                       "explanation — then 'explain the codebase " + name + "'.)")

    async def _explain_profile(self, name: str, profile: dict) -> str:
        if self.brain is None or not self.brain.can_think():
            return ""
        # trim the prompt (3 files, short snippets) and cap output -> fast + bounded
        items = list(profile["key_files"].items())[:3]
        keyfiles = "\n".join(f"### {f}\n{c[:500]}" for f, c in items)
        prompt = (
            f"In 4-6 sentences, explain the codebase '{name}': what it is, its tech "
            f"stack, structure, and entry points. Base it ONLY on:\n"
            f"Languages: {profile['languages']}\nTop-level: {profile['structure']}\n"
            f"Key files:\n{keyfiles}")
        try:  # task=CODE via complete() -> no profile injection; capped length
            resp = await self.brain.complete(prompt, task=Task.CODE, max_tokens=280)
            return resp.text.strip()
        except Exception:
            return ""

    def _explain(self, name: Optional[str]) -> str:
        if not name:
            return "Which codebase? Say 'explain the codebase <name>' (scan it first)."
        entry = self.store.get(name)
        if not entry:
            return f"I haven't scanned '{name}' yet. Try 'scan {name}'."
        return entry.get("summary") or f"I scanned {name} but have no written summary."

    async def _ask(self, raw: str) -> str:
        name = self._name_in(raw)
        entry = self.store.get(name) if name else None
        if entry is None:
            return "Ask about a scanned codebase, e.g. 'ask about ORIGAMI: how does auth work'."
        question = raw.split(":", 1)[1].strip() if ":" in raw else raw
        if self.brain is None or not self.brain.can_think():
            return entry.get("summary", "Scan it first, then install a model to ask questions.")
        resp = await self.brain.complete(
            f"About the codebase '{name}': {entry.get('summary', '')}\n\n"
            f"Question: {question}\nAnswer concisely based on what's known.",
            task=Task.CODE, max_tokens=280)
        return resp.text.strip()

    def _list(self) -> str:
        names = self.store.names()
        if not names:
            return "No codebases learned yet. Try 'scan <path or project>'."
        return "🧠 Codebases I've learned:\n" + "\n".join(f"- {n}" for n in names)

    # ------------------------------------------------------------------ helpers

    def _resolve(self, target: str):
        """Return (path, clean_name). A project alias is used as the clean name so
        'scan wavex' stores 'wavex', not the folder basename."""
        target = re.sub(r"\b(the|repo|codebase|code|project|at|in)\b", " ", target,
                        flags=re.IGNORECASE).strip()
        if not target:
            return None, None
        p = Path(target).expanduser()
        if p.exists() and p.is_dir():
            return str(p), p.name
        for name, cfg in self._projects().items():  # launcher config alias
            if name.lower() == target.lower() and Path(cfg.get("path", "")).exists():
                return cfg["path"], name
        return None, None

    def _projects(self) -> dict:
        raw = read_text(self.projects_path)
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def _name_in(self, text: str) -> Optional[str]:
        for name in self.store.names():
            if name in text.lower():
                return name
        # maybe a just-scanned project name
        for name in self._projects():
            if name in text.lower():
                return name
        return None
