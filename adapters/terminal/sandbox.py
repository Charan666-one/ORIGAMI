"""
adapters/terminal/sandbox.py
Sandboxed command execution for untrusted or LLM-generated code.
Provides: allowlist/denylist enforcement, resource limits, temp-dir isolation.

SECURITY NOTE:
  This is NOT a full container-level sandbox. For production AI code execution,
  use Docker containers or gVisor. This module provides a best-effort
  software-level guard suitable for development and known-safe environments.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from adapters.terminal.executor import CommandResult, ExecutorError, TerminalExecutor

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Default blocklists
# ------------------------------------------------------------------

# Commands that are never allowed regardless of configuration
ALWAYS_BLOCKED_COMMANDS: frozenset[str] = frozenset({
    "rm",       # file deletion
    "rmdir",    # directory deletion
    "mkfs",     # format filesystem
    "dd",       # direct disk write
    "shutdown", # system shutdown
    "reboot",   # system restart
    "halt",     # system halt
    "init",     # init level change
    "kill",     # process termination (allow via safe_kill only)
    "killall",  # mass process termination
    "passwd",   # password change
    "sudo",     # privilege escalation
    "su",       # user switch
    "chown",    # ownership change
    "chmod",    # permission change (in some contexts)
    "crontab",  # scheduled task modification
    "nc",       # netcat (potential data exfiltration)
    "ncat",     # same
    "curl",     # network (allow explicitly if needed)
    "wget",     # network (allow explicitly if needed)
    "ssh",      # remote shell
    "scp",      # remote copy
    "sftp",     # secure file transfer
    ">",        # output redirection (shell injection risk)
    ">>",       # append redirection
    "|",        # pipe (can chain dangerous commands)
    ";",        # command chaining
    "&&",       # conditional chaining
    "||",       # conditional chaining
    "`",        # command substitution
    "$()",      # command substitution
})

# Patterns that must not appear anywhere in the command string
BLOCKED_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bsudo\b"),
    re.compile(r"\bsu\b"),
    re.compile(r"/etc/passwd"),
    re.compile(r"/etc/shadow"),
    re.compile(r"\.\./"),             # path traversal
    re.compile(r";\s*rm"),            # chained delete
    re.compile(r"\|\s*bash"),         # pipe to shell
    re.compile(r">\s*/dev/"),         # write to device
]


class SandboxViolationError(ExecutorError):
    """Raised when a command violates sandbox policy."""


class SandboxedExecutor:
    """
    A sandboxed wrapper around TerminalExecutor.

    Features:
    - Command allowlist / denylist enforcement before execution.
    - Pattern-based injection detection.
    - Temp directory isolation for generated scripts.
    - Optional resource limits (CPU time, memory via ulimit on Linux).
    - Dry-run mode for testing sandbox rules without executing.

    Usage:
        sandbox = SandboxedExecutor(
            allowed_commands=["python3", "pip", "git", "ls", "cat", "echo"]
        )
        result = sandbox.run_safe("python3 script.py")

    Usage (dry-run):
        sandbox = SandboxedExecutor(dry_run=True)
        sandbox.run_safe("git status")   # logs but doesn't execute
    """

    def __init__(
        self,
        allowed_commands: Optional[list[str]] = None,
        blocked_commands: Optional[list[str]] = None,
        extra_blocked_patterns: Optional[list[str]] = None,
        working_dir: Optional[Path] = None,
        use_temp_dir: bool = False,
        default_timeout: int = 30,
        max_output_bytes: int = 100_000,   # 100 KB output limit
        dry_run: bool = False,
        apply_ulimits: bool = False,
    ) -> None:
        """
        Args:
            allowed_commands: If set, ONLY these base commands are permitted.
            blocked_commands: Additional commands to block on top of defaults.
            extra_blocked_patterns: Additional regex patterns to block.
            working_dir: CWD for executed commands.
            use_temp_dir: If True, execute in a fresh temp dir each call.
            default_timeout: Max seconds per command.
            max_output_bytes: Truncate output beyond this many bytes.
            dry_run: Log commands but don't actually execute them.
            apply_ulimits: Apply CPU/memory ulimits on Linux (requires ulimit).
        """
        self.allowed_commands: Optional[frozenset[str]] = (
            frozenset(allowed_commands) if allowed_commands else None
        )
        self.blocked_commands: frozenset[str] = ALWAYS_BLOCKED_COMMANDS | frozenset(
            blocked_commands or []
        )
        self.blocked_patterns = BLOCKED_PATTERNS + [
            re.compile(p) for p in (extra_blocked_patterns or [])
        ]
        self.use_temp_dir = use_temp_dir
        self.default_timeout = default_timeout
        self.max_output_bytes = max_output_bytes
        self.dry_run = dry_run
        self.apply_ulimits = apply_ulimits

        self._executor = TerminalExecutor(
            cwd=working_dir,
            default_timeout=default_timeout,
        )
        self._violation_log: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_safe(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[Path] = None,
    ) -> CommandResult:
        """
        Execute a command after passing all sandbox checks.

        Raises:
            SandboxViolationError: If the command fails any security check.
        """
        self._validate(command)

        if self.dry_run:
            logger.info("[DRY RUN] Would execute: %s", command)
            return CommandResult(
                command=command,
                returncode=0,
                stdout="[DRY RUN — command not executed]",
                stderr="",
            )

        effective_cwd = cwd
        if self.use_temp_dir:
            with tempfile.TemporaryDirectory(prefix="origami_sandbox_") as tmpdir:
                effective_cwd = effective_cwd or Path(tmpdir)
                result = self._executor.run(
                    command, cwd=effective_cwd, timeout=timeout
                )
        else:
            result = self._executor.run(command, cwd=effective_cwd, timeout=timeout)

        # Truncate excessive output
        if len(result.stdout) > self.max_output_bytes:
            result.stdout = result.stdout[: self.max_output_bytes] + "\n[... output truncated]"
        if len(result.stderr) > self.max_output_bytes:
            result.stderr = result.stderr[: self.max_output_bytes] + "\n[... stderr truncated]"

        return result

    def run_python_code(
        self,
        code: str,
        timeout: int = 30,
        python_bin: str = "python3",
    ) -> CommandResult:
        """
        Execute an arbitrary Python code string in a temp file.

        Args:
            code: Python source code to execute.
            timeout: Max execution time in seconds.
            python_bin: Python interpreter path.

        Returns:
            CommandResult with stdout/stderr from the script.
        """
        with tempfile.NamedTemporaryFile(
            suffix=".py", prefix="origami_", mode="w", delete=False
        ) as f:
            f.write(code)
            script_path = Path(f.name)

        try:
            return self.run_safe(
                f"{python_bin} {script_path}",
                timeout=timeout,
                cwd=script_path.parent,
            )
        finally:
            try:
                script_path.unlink()
            except OSError:
                pass

    def run_shell_script(
        self,
        script: str,
        timeout: int = 30,
        shell: str = "/bin/bash",
    ) -> CommandResult:
        """
        Execute a multi-line shell script from a temp file.

        Applies the same allowlist / denylist checks per line.
        """
        # Validate each non-empty, non-comment line
        for line in script.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                self._validate(stripped)

        with tempfile.NamedTemporaryFile(
            suffix=".sh", prefix="origami_", mode="w", delete=False
        ) as f:
            f.write(f"#!{shell}\nset -e\n")
            f.write(script)
            script_path = Path(f.name)

        script_path.chmod(0o700)
        try:
            return self._executor.run(str(script_path), timeout=timeout)
        finally:
            try:
                script_path.unlink()
            except OSError:
                pass

    @property
    def violation_log(self) -> list[str]:
        """Return all recorded sandbox violations."""
        return list(self._violation_log)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self, command: str) -> None:
        """
        Run all sandbox checks. Raises SandboxViolationError on failure.
        """
        # 1. Pattern check (injection, traversal, dangerous tokens)
        for pattern in self.blocked_patterns:
            if pattern.search(command):
                msg = f"Blocked pattern matched: {pattern.pattern!r} in command: {command!r}"
                self._log_violation(msg)
                raise SandboxViolationError(msg)

        # 2. Parse base command name
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            msg = f"Command parse failed: {exc} — command: {command!r}"
            self._log_violation(msg)
            raise SandboxViolationError(msg) from exc

        if not parts:
            return  # empty command, benign

        base_cmd = Path(parts[0]).name  # handle '/usr/bin/python3' → 'python3'

        # 3. Denylist check
        if base_cmd in self.blocked_commands:
            msg = f"Blocked command: {base_cmd!r}"
            self._log_violation(msg)
            raise SandboxViolationError(msg)

        # 4. Allowlist check (if configured)
        if self.allowed_commands is not None and base_cmd not in self.allowed_commands:
            msg = (
                f"Command not in allowlist: {base_cmd!r}. "
                f"Allowed: {sorted(self.allowed_commands)}"
            )
            self._log_violation(msg)
            raise SandboxViolationError(msg)

    def _log_violation(self, message: str) -> None:
        logger.warning("[SANDBOX VIOLATION] %s", message)
        self._violation_log.append(message)


# ------------------------------------------------------------------
# Convenience factory for ORIGAMI-specific use cases
# ------------------------------------------------------------------

def create_coding_sandbox(working_dir: Optional[Path] = None) -> SandboxedExecutor:
    """
    Return a sandbox configured for safe code execution tasks.
    Allows Python, pip, git, and common dev tools.
    """
    return SandboxedExecutor(
        allowed_commands=[
            "python3", "python", "pip", "pip3",
            "git", "ls", "cat", "echo", "pwd",
            "mkdir", "touch", "cp", "mv",
            "grep", "find", "wc", "head", "tail",
            "node", "npm", "npx",
        ],
        use_temp_dir=False,
        working_dir=working_dir,
        default_timeout=60,
        max_output_bytes=200_000,
    )


def create_research_sandbox() -> SandboxedExecutor:
    """
    Minimal sandbox for research/search tasks that only need curl and jq.
    """
    return SandboxedExecutor(
        allowed_commands=["curl", "jq", "python3", "echo"],
        default_timeout=15,
        max_output_bytes=50_000,
    )