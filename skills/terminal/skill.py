"""TerminalSkill — wraps the existing adapters/terminal/executor.py.

`terminal.run` is the first CONFIRM-gated tool: it runs a shell command, so the
executor stops and asks the user to approve before anything executes. Reads never
prompt; this does, because it has consequences.
"""

from __future__ import annotations

from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill


class TerminalSkill(Skill):
    def __init__(self, executor: Any = None) -> None:
        self._executor = executor  # injected fake in tests; real one built lazily

    @property
    def executor(self):
        if self._executor is None:
            from adapters.terminal.executor import TerminalExecutor  # lazy import
            # shell=True so natural commands (pipes, globs) work; the CONFIRM gate
            # means the user always sees and approves the exact command first.
            self._executor = TerminalExecutor(shell=True)
        return self._executor

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="terminal.run",
                description="Run a shell command on this machine.",
                params={"command": "the shell command to run"},
                risk=Risk.CONFIRM,
                keywords=("run ", "execute ", "run command"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "terminal.run":
            command = (kwargs.get("command") or "").strip()
            if not command:
                return "No command given."
            result = self.executor.run(command)
            body = result.output.strip() if result.output else "(no output)"
            status = "✓" if result.success else f"✗ exit {result.returncode}"
            return f"{status}  $ {command}\n{body}"
        raise ValueError(f"Unknown tool: {tool}")
