"""
adapters/terminal/executor.py
Secure shell command executor for ORIGAMI.
Runs commands synchronously or asynchronously with timeout, output capture,
streaming output, and environment isolation.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Optional

logger = logging.getLogger(__name__)


class ExecutorError(Exception):
    """Raised when a command fails or times out."""


@dataclass
class CommandResult:
    """Result of a shell command execution."""

    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """Combined stdout + stderr."""
        parts = [p for p in (self.stdout, self.stderr) if p]
        return "\n".join(parts)

    def __str__(self) -> str:
        status = "OK" if self.success else f"FAIL(rc={self.returncode})"
        return f"[{status}] {self.command!r}\n{self.output[:500]}"


class TerminalExecutor:
    """
    Safe, feature-rich shell command executor.

    Features:
    - Configurable working directory and environment.
    - Per-command timeouts (default 30s).
    - Streaming output via callbacks.
    - Async execution support.
    - Command logging and audit trail.

    Usage:
        exe = TerminalExecutor(cwd=Path("/home/user/project"))
        result = exe.run("ls -la")
        print(result.stdout)
    """

    def __init__(
        self,
        cwd: Optional[Path] = None,
        env: Optional[dict[str, str]] = None,
        default_timeout: int = 30,
        shell: bool = False,
        audit_log_path: Optional[Path] = None,
    ) -> None:
        """
        Args:
            cwd: Default working directory for commands.
            env: Extra environment variables merged with os.environ.
            default_timeout: Seconds before a command is killed.
            shell: If True, run commands through the shell (less safe).
            audit_log_path: If set, every command + result is appended here.
        """
        self.cwd = cwd or Path.cwd()
        self.env = {**os.environ, **(env or {})}
        self.default_timeout = default_timeout
        self.shell = shell
        self.audit_log_path = audit_log_path
        self._history: list[CommandResult] = []

    # ------------------------------------------------------------------
    # Synchronous execution
    # ------------------------------------------------------------------

    def run(
        self,
        command: str,
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
        env_override: Optional[dict[str, str]] = None,
        capture_output: bool = True,
    ) -> CommandResult:
        """
        Execute a shell command synchronously.

        Args:
            command: Shell command string (e.g. 'git status').
            cwd: Working directory for this command (overrides default).
            timeout: Timeout in seconds (overrides default).
            env_override: Extra env vars for this command only.
            capture_output: If False, output streams to terminal directly.

        Returns:
            CommandResult with returncode, stdout, stderr.
        """
        effective_timeout = timeout if timeout is not None else self.default_timeout
        effective_cwd = cwd or self.cwd
        effective_env = {**self.env, **(env_override or {})}

        args = command if self.shell else shlex.split(command)
        logger.debug("Executing: %s (cwd=%s, timeout=%ds)", command, effective_cwd, effective_timeout)

        timed_out = False
        try:
            proc = subprocess.run(
                args,
                cwd=str(effective_cwd),
                env=effective_env,
                capture_output=capture_output,
                text=True,
                timeout=effective_timeout,
                shell=self.shell,
            )
            result = CommandResult(
                command=command,
                returncode=proc.returncode,
                stdout=proc.stdout.strip() if capture_output else "",
                stderr=proc.stderr.strip() if capture_output else "",
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            result = CommandResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {effective_timeout}s.",
                timed_out=True,
            )
            logger.warning("Command timed out: %s", command)
        except FileNotFoundError as exc:
            result = CommandResult(
                command=command,
                returncode=127,
                stdout="",
                stderr=f"Command not found: {exc}",
            )

        self._record(result)
        return result

    def run_checked(self, command: str, **kwargs) -> CommandResult:
        """
        Run a command and raise ExecutorError if it fails.

        Same signature as run() plus raises on non-zero exit.
        """
        result = self.run(command, **kwargs)
        if not result.success:
            raise ExecutorError(
                f"Command failed (rc={result.returncode}): {command}\n"
                f"stderr: {result.stderr}"
            )
        return result

    def run_many(
        self,
        commands: list[str],
        stop_on_failure: bool = True,
        **kwargs,
    ) -> list[CommandResult]:
        """
        Run a list of commands sequentially.

        Args:
            commands: List of command strings.
            stop_on_failure: If True, stop at first non-zero exit.
        """
        results = []
        for cmd in commands:
            result = self.run(cmd, **kwargs)
            results.append(result)
            if stop_on_failure and not result.success:
                logger.error("Stopping pipeline at failed command: %s", cmd)
                break
        return results

    # ------------------------------------------------------------------
    # Streaming output
    # ------------------------------------------------------------------

    def stream(
        self,
        command: str,
        on_stdout: Callable[[str], None],
        on_stderr: Optional[Callable[[str], None]] = None,
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
    ) -> int:
        """
        Execute a command and stream output line-by-line via callbacks.

        Args:
            command: Shell command string.
            on_stdout: Called for each line of stdout.
            on_stderr: Called for each line of stderr. Defaults to on_stdout.
            cwd: Working directory.
            timeout: Timeout in seconds.

        Returns:
            Process return code.
        """
        on_stderr = on_stderr or on_stdout
        args = command if self.shell else shlex.split(command)
        effective_cwd = cwd or self.cwd
        effective_timeout = timeout or self.default_timeout

        proc = subprocess.Popen(
            args,
            cwd=str(effective_cwd),
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=self.shell,
        )

        def _read_stream(stream, callback: Callable[[str], None]) -> None:
            for line in iter(stream.readline, ""):
                callback(line.rstrip())
            stream.close()

        t_out = threading.Thread(target=_read_stream, args=(proc.stdout, on_stdout))
        t_err = threading.Thread(target=_read_stream, args=(proc.stderr, on_stderr))
        t_out.start()
        t_err.start()

        try:
            proc.wait(timeout=effective_timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            logger.warning("Streaming command timed out: %s", command)
        finally:
            t_out.join()
            t_err.join()

        return proc.returncode

    # ------------------------------------------------------------------
    # Async execution
    # ------------------------------------------------------------------

    async def run_async(
        self,
        command: str,
        cwd: Optional[Path] = None,
        timeout: Optional[int] = None,
    ) -> CommandResult:
        """
        Execute a command asynchronously.

        Args:
            command: Shell command string.
        """
        effective_cwd = cwd or self.cwd
        effective_timeout = timeout if timeout is not None else self.default_timeout
        args = shlex.split(command)

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(effective_cwd),
                env=self.env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=effective_timeout
            )
            result = CommandResult(
                command=command,
                returncode=proc.returncode or 0,
                stdout=stdout_bytes.decode().strip(),
                stderr=stderr_bytes.decode().strip(),
            )
        except asyncio.TimeoutError:
            result = CommandResult(
                command=command,
                returncode=-1,
                stdout="",
                stderr=f"Async command timed out after {effective_timeout}s.",
                timed_out=True,
            )

        self._record(result)
        return result

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def which(self, program: str) -> Optional[str]:
        """Return the full path of a program or None if not found."""
        import shutil
        return shutil.which(program)

    def is_available(self, program: str) -> bool:
        """Return True if a program is on PATH."""
        return self.which(program) is not None

    @property
    def history(self) -> list[CommandResult]:
        """Return all commands executed in this session."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear the in-memory command history."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _record(self, result: CommandResult) -> None:
        """Log command to memory and optionally to audit file."""
        self._history.append(result)
        level = logging.DEBUG if result.success else logging.WARNING
        logger.log(level, "CMD %s rc=%d", result.command[:80], result.returncode)

        if self.audit_log_path:
            try:
                from datetime import datetime, timezone
                ts = datetime.now(timezone.utc).isoformat()
                entry = f"{ts} | rc={result.returncode} | {result.command}\n"
                with open(self.audit_log_path, "a") as f:
                    f.write(entry)
            except Exception as exc:
                logger.warning("Failed to write audit log: %s", exc)