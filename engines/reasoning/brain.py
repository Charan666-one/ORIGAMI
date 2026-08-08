"""BrainManager — "use the minimum intelligence required."

Every brain call is classified into a Level and routed to the smallest capable
model, so ORIGAMI feels instant for simple asks and reserves heavy reasoning for
when it's needed. The Planner and skills never know which model (or none) served
a request — they only call reason/generate/summarize/code.

Levels:
  L0  deterministic — no AI at all (handled by non-brain skills; never reaches here)
  L1  fast          — lightweight local model (short/simple asks)
  L2  standard      — standard local reasoning (coding, long writing, planning)
  L3  advanced      — cloud, ONLY if local is insufficient AND the user consents

Decision rules honored: never use AI when software can do it (L0 skills); smallest
capable model (classify_level); prefer local; cloud requires explicit consent;
resource-aware downgrade; Echo as the guaranteed keyless fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from core.schemas.goal import Goal
from core.schemas.plan import Plan
from core.schemas.tool import ToolSpec
from engines.reasoning.llm import (
    Level, LLMEngine, LLMResponse, Task, classify_level, keyword_match_plan,
)
from engines.reasoning.providers.echo import EchoEngine
from engines.reasoning.resources import ResourceMonitor

# Asked before using a cloud provider: (provider_name, task) -> approved?
CloudConsent = Callable[[str, Task], bool]


@dataclass
class Decision:
    """What the manager chose for a request — useful for transparency/logging."""
    provider: str
    level: Level
    reason: str = ""


class BrainManager(LLMEngine):
    name = "brain"

    def __init__(self, providers: Optional[List[LLMEngine]] = None,
                 resources: Optional[ResourceMonitor] = None,
                 cloud_consent: Optional[CloudConsent] = None,
                 system_context: str = "") -> None:
        self._echo = EchoEngine()
        self.providers: List[LLMEngine] = list(providers or []) + [self._echo]
        self.resources = resources or ResourceMonitor()
        self.cloud_consent = cloud_consent
        self.system_context = system_context  # persistent 'who the user is' context
        self.last_decision: Optional[Decision] = None

    # --- availability helpers ---------------------------------------------------

    def _first_local(self) -> Optional[LLMEngine]:
        for p in self.providers:
            if p is not self._echo and not p.is_cloud and p.is_available():
                return p
        return None

    def _first_cloud(self) -> Optional[LLMEngine]:
        for p in self.providers:
            if p.is_cloud and p.is_available():
                return p
        return None

    def _cloud_approved(self, provider: LLMEngine, task: Task) -> bool:
        if self.cloud_consent is None:
            return False  # never auto-use cloud without an explicit consent hook
        try:
            return bool(self.cloud_consent(provider.name, task))
        except Exception:
            return False

    # --- the core decision: which level + provider ------------------------------

    def decide(self, task: Task, text: str) -> Tuple[LLMEngine, Level]:
        level = classify_level(task, text)

        # resource-aware: under memory/CPU/battery pressure, drop to the fast tier
        if level in (Level.L2, Level.L3) and self.resources.is_low():
            level = Level.L1

        # L3 advanced -> cloud only with consent; else fall back to best local (L2)
        if level is Level.L3:
            cloud = self._first_cloud()
            if cloud is not None and self._cloud_approved(cloud, task):
                self.last_decision = Decision(cloud.name, Level.L3, "advanced + consent")
                return cloud, Level.L3
            level = Level.L2  # no cloud/consent — best available local

        local = self._first_local()
        if local is not None:
            self.last_decision = Decision(local.name, level, "local")
            return local, level

        self.last_decision = Decision(self._echo.name, Level.L1, "no model available")
        return self._echo, Level.L1

    #: Quick asks get a brevity instruction and NOTHING else.
    #:
    #: Measured: adding a persona ("You are a personal assistant for Charan") made
    #: the model role-play *doing tasks* — "why finish a project?" came back as
    #: "I'll notify Charan's team the project is complete", while the same model
    #: answers the bare question correctly. Identity helps on substantial requests
    #: (L2+); on a quick factual one it just invites acting instead of answering.
    SHORT_INSTRUCTION = "Answer the question directly in one or two sentences."

    def _short_context(self) -> str:
        return self.SHORT_INSTRUCTION

    async def _run(self, task: Task, text: str, **kwargs) -> str:
        provider, level = self.decide(task, text)  # classify on the raw request
        prompt = text
        # Inject the persistent user context for personal reasoning/writing (not
        # for summarize/code, which act on given content). Quick L1 asks get only
        # a one-line identity: dumping the whole profile turned "say hello" into a
        # career consultation.
        if self.system_context and task in (Task.REASON, Task.GENERATE):
            if level is Level.L1:
                prompt = f"{self._short_context()}\n\n{text}"
            else:
                prompt = (f"{self.system_context}\n\n---\n"
                          f"Given the above about the user, respond to their request:\n{text}")
        method = getattr(provider, task.value)  # provider.reason/generate/summarize/code
        return await method(prompt, level=level, **kwargs)

    # --- Brain Interface --------------------------------------------------------

    async def reason(self, prompt: str, **kwargs) -> str:
        return await self._run(Task.REASON, prompt, **kwargs)

    async def generate(self, instruction: str, **kwargs) -> str:
        return await self._run(Task.GENERATE, instruction, **kwargs)

    async def summarize(self, text: str, **kwargs) -> str:
        return await self._run(Task.SUMMARIZE, text, **kwargs)

    async def code(self, instruction: str, **kwargs) -> str:
        return await self._run(Task.CODE, instruction, **kwargs)

    async def complete(self, prompt: str, task: Task = Task.REASON, **kwargs) -> LLMResponse:
        provider, level = self.decide(task, prompt)
        return await provider.complete(prompt, task=task, level=level, **kwargs)

    # --- status + planning ------------------------------------------------------

    def can_think(self) -> bool:
        """True if a real (non-echo) local model is available."""
        return self._first_local() is not None

    def active_model(self, task: Task = Task.REASON) -> str:
        local = self._first_local()
        return local.name if local is not None else self._echo.name

    async def plan(self, goal: Goal, tools: List[ToolSpec]) -> Plan:
        return keyword_match_plan(goal, tools)  # L0 — routing needs no model
