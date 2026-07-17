# ORIGAMI — Architecture (the spine)

This document defines the **minimum engine** that every future capability plugs
into. It maps directly onto the existing repo layout, so nothing here requires a
restructure — only filling the right files.

> Read `VISION.md` first. This document is *how* we build the one primitive it
> describes.

---

## 1. Layered map → repo directories

| Layer | Responsibility | Directory | Status today |
|-------|----------------|-----------|--------------|
| Surfaces | turn input into a goal | `interfaces/` (`cli/`, `api/`) | empty |
| Brain | plan, remember, decide | `core/`, `engines/memory`, `engines/reasoning` | only `core/events.py` |
| Agents | domain specialists | `agents/` | 1 broken stub |
| Tools | do the actual work | `skills/` (wrapping `adapters/`) | adapters real, skills empty |
| Models | provide intelligence | `engines/llm` | empty |

The rule: **data flows down the layers, control flows up.** A surface creates a
`Goal`; the orchestrator plans and executes; tools call adapters; results and
events flow back up.

---

## 2. Data contracts (`core/schemas/`)

These small dataclasses are the vocabulary the whole system speaks. Files already
exist as empty placeholders — we fill them.

```python
# core/schemas/goal.py
@dataclass
class Goal:
    text: str                       # "play some lofi"
    source: str = "cli"             # cli | api | event | voice
    context: dict = field(default_factory=dict)
    session_id: str | None = None

# core/schemas/tool.py   (the registry's unit of currency)
@dataclass
class ToolSpec:
    name: str                       # "spotify.play"
    description: str                # what it does, for the planner/LLM
    parameters: dict                # JSON-schema of args
    confirm: bool = False           # requires user approval before running
    read_only: bool = True          # reads never need confirmation

# core/schemas/plan.py
@dataclass
class Step:
    tool: str                       # ToolSpec.name
    args: dict
    rationale: str = ""

@dataclass
class Plan:
    goal: Goal
    steps: list[Step]
    reasoning: str = ""

# core/schemas/result.py  (reuse skills.base.SkillResult shape)
@dataclass
class StepResult:
    step: Step
    success: bool
    output: Any = None
    error: str | None = None

@dataclass
class RunResult:
    goal: Goal
    steps: list[StepResult]
    ok: bool
    summary: str = ""
```

`core/schemas/memory.py`, `task.py`, `user.py`, `event.py` already exist as
placeholders and get filled as their engines come online.

---

## 3. The Tool contract & registry (`skills/base.py`, `skills/registry.py`)

This is **the single most important design decision** in the project. Everything
Origami can do is a Tool. Tools self-register. The core never dispatches with
`if/elif`.

We already have `skills/base.py` with an abstract `Skill` + `SkillResult`. We
extend it minimally so a Skill can describe itself to the planner.

```python
# skills/base.py  (extend existing)
class Skill(ABC):
    name: str
    description: str

    @classmethod
    @abstractmethod
    def specs(cls) -> list[ToolSpec]:
        """The tools this skill exposes to the planner."""

    @abstractmethod
    async def execute(self, tool: str, **kwargs) -> SkillResult: ...
    async def stop(self): ...
    async def status(self) -> dict: ...
```

```python
# skills/registry.py  (currently 0 bytes — this is the keystone)
class ToolRegistry:
    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._specs: dict[str, tuple[Skill, ToolSpec]] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill
        for spec in skill.specs():
            self._specs[spec.name] = (skill, spec)

    def specs(self) -> list[ToolSpec]:
        return [spec for _, spec in self._specs.values()]

    async def call(self, tool: str, **kwargs) -> SkillResult:
        skill, _ = self._specs[tool]
        return await skill.execute(tool, **kwargs)

registry = ToolRegistry()          # global, like event_bus

def tool(skill_cls):               # decorator: auto-register on import
    registry.register(skill_cls())
    return skill_cls
```

**Adding any capability, forever, is this:**

```python
@tool
class MySkill(Skill):
    name = "my_skill"
    description = "..."
    @classmethod
    def specs(cls): return [ToolSpec(name="my_skill.do", ...)]
    async def execute(self, tool, **kw): ...
```

No core file changes. That property is the whole point of the architecture.

---

## 4. The Model interface (`engines/llm/`)

One provider-agnostic brain. Agents and the planner never import an SDK
directly. `configs/_schemas/llm.py` already exists for its config.

```python
# engines/llm/base.py
class LLMEngine(ABC):
    @abstractmethod
    async def reason(self, system: str, user: str,
                     tools: list[ToolSpec] | None = None) -> LLMResponse: ...

# engines/llm/providers/anthropic.py  -> AnthropicEngine(LLMEngine)
# engines/llm/providers/openai.py     -> OpenAIEngine(LLMEngine)
# engines/llm/providers/echo.py       -> EchoEngine  (no API key; for tests/offline)
```

`LLMResponse` carries either text or a chosen tool call (name + args), so the
same interface powers both chat and planning. `EchoEngine` lets the whole system
run in CI and offline — critical for a solo project without always-on keys.

**Free/local default (see `RUNNING_FREE.md`).** The shipping default brain is
`LocalEngine` (Ollama on the M1) — $0, unlimited, offline. A `RouterEngine`
picks the cheapest sub-engine per call (local for the frequent 90%, free API
tiers for overflow). Claude Code is deliberately **not** an `LLMEngine` — it's a
coding *tool* in the registry (`skills/claude_code/`), driven by the local
planner and covered by the flat Max subscription, so heavy codegen stays free at
the margin.

---

## 5. Memory (`engines/memory/`)

Structured, not chat logs. **Interface first, JSON storage first**, so we can
swap in SQLite/vector/graph later without touching callers.

```python
# engines/memory/base.py
class MemoryEngine(ABC):
    async def store(self, record: MemoryRecord) -> str: ...
    async def retrieve(self, query: str, kind: str | None = None,
                       k: int = 5) -> list[MemoryRecord]: ...
    async def get_project(self, name: str) -> ProjectMemory | None: ...

# engines/memory/json_store.py  -> JSONMemory : writes ~/.origami/memory/*.json
```

`MemoryRecord` kinds: `project`, `skill`, `decision`, `bug`, `preference`,
`event`. This is the schema behind "Continue CareerLens" and the knowledge graph
— we start with flat JSON and add links/embeddings later.

---

## 6. Planner (`core/planner.py`)

Turns a `Goal` into a `Plan` by asking the `LLMEngine` to choose from the
registry's `ToolSpec`s. Ships with a **keyword fallback** so it runs with no API
key (proves the pipeline before the brain is smart).

```python
class Planner:
    def __init__(self, llm: LLMEngine, registry: ToolRegistry, memory: MemoryEngine):
        ...
    async def plan(self, goal: Goal) -> Plan:
        memories = await self.memory.retrieve(goal.text)
        specs = self.registry.specs()
        resp = await self.llm.reason(system=PLANNER_PROMPT,
                                     user=render(goal, memories),
                                     tools=specs)
        return parse_plan(resp) or self._keyword_fallback(goal, specs)
```

Later upgrade path: single-tool selection → multi-step plans → multi-agent
delegation. The interface does not change.

---

## 7. Executor (`core/executor.py`)

Runs a `Plan` step by step. Enforces the **confirm-before-consequences** rule and
publishes events on the bus you already built.

```python
class Executor:
    def __init__(self, registry, event_bus, confirm: Callable[[Step], bool]):
        ...
    async def run(self, plan: Plan) -> RunResult:
        results = []
        for step in plan.steps:
            spec = self.registry.spec(step.tool)
            if spec.confirm and not self.confirm(step):
                results.append(StepResult(step, success=False, error="declined"))
                break
            res = await self.registry.call(step.tool, **step.args)
            await self.event_bus.publish(Event(
                EventTypes.SKILL_EXECUTED if res.success else EventTypes.SKILL_FAILED,
                {"tool": step.tool, "result": res.result}, source="executor"))
            results.append(StepResult(step, res.success, res.result, res.error))
        return summarize(plan, results)
```

`confirm` is injected by the surface: the CLI prompts on stdin; the API returns a
"needs confirmation" response; a future autonomous mode auto-approves read-only
steps only.

---

## 8. Orchestrator (`core/orchestrator.py`)

The one object a surface talks to. Wires everything and owns the request loop.

```python
class Orchestrator:
    def __init__(self, planner, executor, memory, session_store):
        ...
    async def handle(self, goal: Goal) -> RunResult:
        plan   = await self.planner.plan(goal)
        result = await self.executor.run(plan)
        await self.memory.store(MemoryRecord.from_run(result))
        return result
```

`core/session.py` and `core/context.py` hold per-conversation state (history,
current project, open files) that enrich `Goal.context` — thin in v1, richer as
the context engine (#11) grows.

---

## 9. Surfaces (`interfaces/`)

Two in v1, sharing the same orchestrator:

```
interfaces/cli/main.py     origami "play some lofi"   -> print RunResult.summary
interfaces/api/app.py      POST /goal {text}          -> JSON RunResult   (FastAPI)
```

Both do exactly one thing: build a `Goal`, call `orchestrator.handle`, render the
result. All intelligence lives below them, so adding voice/dashboard later is
just another surface.

---

## 10. Composition root (`main.py`)

One place assembles the graph so every surface shares identical wiring:

```python
def build_orchestrator(env: str = "dev") -> Orchestrator:
    cfg      = load_config(env)
    llm      = make_llm(cfg)                 # EchoEngine if no key
    memory   = JSONMemory(cfg.memory_path)
    import skills.spotify.skill              # side-effect: @tool registers it
    planner  = Planner(llm, registry, memory)
    executor = Executor(registry, event_bus, confirm=cli_confirm)
    return Orchestrator(planner, executor, memory, SessionStore())
```

Importing a skill module is what registers it. Enabling/disabling capabilities
becomes a config list of module paths — the seed of the plugin marketplace (#18).

---

## 11. Directory-by-directory: what fills in, and when

| Directory | v1 (spine) | later |
|-----------|-----------|-------|
| `core/schemas/` | Goal, ToolSpec, Plan, Result | Memory, Task, User graphs |
| `core/` | planner, executor, orchestrator, session, context | reasoner, planner upgrades |
| `skills/` | `base` (+specs), `registry`, `spotify/skill` | every capability lives here |
| `engines/llm/` | base + one provider + echo | multi-provider, embeddings |
| `engines/memory/` | base + json_store | sqlite → vector → graph |
| `engines/{reasoning,planning,voice,vision,...}` | untouched | Layer-2/agent growth |
| `agents/` | untouched (fix the broken import or delete) | Developer/Career/… agents |
| `adapters/` | reuse Spotify (+ Terminal, GitHub next) | already the strong layer |
| `interfaces/` | cli/main, api/app | dashboard, voice, mobile |
| `configs/` | dev.yaml drives composition | per-skill + per-engine config |
| `tests/` | one end-to-end slice test | per-layer coverage |

---

## 12. Known cleanups the spine forces us to make

- `agents/conversation/agent.py` imports `core.schemas.AgentDecision`,
  `LLMEngine`, `MemoryEngine`, `load_config` — **none exist**, so the module
  cannot import. Either delete it now or rewrite it as the first real agent on
  top of the finished spine. Recommend: **delete in Phase 1, rebuild in Phase 3.**
- Root `pyproject.toml`, `requirements.txt`, `README.md` are empty → filled in
  Phase 0.
- Only one git commit exists → adopt per-phase commits so the roadmap is legible
  in history.
