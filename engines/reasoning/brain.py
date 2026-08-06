"""BrainManager — chooses the best available model per task, so the Planner and
skills never know which model (or none) answered.

Selection rules (offline-first):
  1. Planning / routing needs no AI  -> keyword matching, always local & free.
  2. Reasoning/generation/etc.       -> first AVAILABLE local provider (Ollama).
  3. If the machine is under load     -> ResourceMonitor may defer / prefer smaller.
  4. If no local model can serve it   -> ask the user (consent) before any CLOUD
     provider; if declined or none, fall back to Echo (honest, no fabrication).

Never automatically depends on a paid/cloud API.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from core.schemas.goal import Goal
from core.schemas.plan import Plan
from core.schemas.tool import ToolSpec
from engines.reasoning.llm import LLMEngine, LLMResponse, Task, keyword_match_plan
from engines.reasoning.providers.echo import EchoEngine
from engines.reasoning.resources import ResourceMonitor

# Asked before using a cloud provider: (provider_name, task) -> approved?
CloudConsent = Callable[[str, Task], bool]


class BrainManager(LLMEngine):
    name = "brain"

    def __init__(self, providers: Optional[List[LLMEngine]] = None,
                 resources: Optional[ResourceMonitor] = None,
                 cloud_consent: Optional[CloudConsent] = None) -> None:
        # ordered by preference; Echo is always the final, always-available fallback
        self._echo = EchoEngine()
        self.providers: List[LLMEngine] = list(providers or []) + [self._echo]
        self.resources = resources or ResourceMonitor()
        self.cloud_consent = cloud_consent

    # --- provider selection -----------------------------------------------------

    def select(self, task: Task) -> LLMEngine:
        """Pick the first provider that can serve this task, honoring offline-first
        (local before cloud) and cloud-consent. Echo is the guaranteed fallback."""
        for provider in self.providers:
            if provider is self._echo:
                continue
            if not provider.is_available():
                continue
            if provider.is_cloud:
                if not self._cloud_approved(provider, task):
                    continue
            return provider
        return self._echo

    def _cloud_approved(self, provider: LLMEngine, task: Task) -> bool:
        if self.cloud_consent is None:
            return False  # never auto-use cloud without an explicit consent hook
        try:
            return bool(self.cloud_consent(provider.name, task))
        except Exception:
            return False

    def can_think(self) -> bool:  # type: ignore[override]
        """True if a real (non-echo) model is available for generation."""
        return self.select(Task.GENERATE) is not self._echo

    def active_model(self, task: Task = Task.REASON) -> str:
        return self.select(task).name

    # --- Brain Interface (delegates to the selected provider) -------------------

    async def complete(self, prompt: str, task: Task = Task.REASON, **kwargs) -> LLMResponse:
        return await self.select(task).complete(prompt, task=task, **kwargs)

    async def reason(self, prompt: str, **kwargs) -> str:
        return await self.select(Task.REASON).reason(prompt, **kwargs)

    async def generate(self, instruction: str, **kwargs) -> str:
        return await self.select(Task.GENERATE).generate(instruction, **kwargs)

    async def summarize(self, text: str, **kwargs) -> str:
        return await self.select(Task.SUMMARIZE).summarize(text, **kwargs)

    async def code(self, instruction: str, **kwargs) -> str:
        return await self.select(Task.CODE).code(instruction, **kwargs)

    # --- planning needs no model ------------------------------------------------

    async def plan(self, goal: Goal, tools: List[ToolSpec]) -> Plan:
        return keyword_match_plan(goal, tools)
