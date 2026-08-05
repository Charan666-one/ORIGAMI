"""ToolRegistry — the keystone. Capabilities self-register here; the planner
selects from it and the executor calls through it. This is what keeps `core/`
free of any `if intent == ...` ladder: adding a tool never edits core.

A plugin registry is a deliberate, legitimate use of module-global state (like a
logger). For test isolation, `build_orchestrator()` can pass a fresh registry.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Dict, List

from core.exceptions import ToolNotFound
from core.schemas.tool import Risk, ToolSpec

# A handler is an async callable taking keyword args and returning any output.
Handler = Callable[..., Awaitable]


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: Dict[str, ToolSpec] = {}
        self._handlers: Dict[str, Handler] = {}

    def register(self, spec: ToolSpec, handler: Handler) -> None:
        """Register (or overwrite) a tool. Overwrite makes re-composition idempotent."""
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler

    def get(self, name: str) -> ToolSpec:
        if name not in self._specs:
            raise ToolNotFound(name)
        return self._specs[name]

    def all(self) -> List[ToolSpec]:
        return list(self._specs.values())

    def has(self, name: str) -> bool:
        return name in self._specs

    async def call(self, name: str, **kwargs):
        if name not in self._handlers:
            raise ToolNotFound(name)
        return await self._handlers[name](**kwargs)


# Global registry for import-time self-registration (via @tool or register_skill).
registry = ToolRegistry()


def tool(name: str, description: str, risk: Risk = Risk.SAFE, params=None, keywords=()):
    """Decorator: register a standalone async function as a tool on the global registry."""

    def decorator(fn: Handler) -> Handler:
        registry.register(
            ToolSpec(
                name=name,
                description=description,
                params=params or {},
                risk=risk,
                keywords=tuple(keywords),
            ),
            fn,
        )
        return fn

    return decorator


def register_skill(reg: ToolRegistry, skill) -> None:
    """Register every tool a Skill exposes, binding each to skill.execute(tool, ...)."""

    for spec in skill.specs():
        reg.register(spec, _bind(skill, spec.name))


def _bind(skill, tool_name: str) -> Handler:
    async def handler(**kwargs):
        return await skill.execute(tool_name, **kwargs)

    return handler
