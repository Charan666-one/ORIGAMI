# ORIGAMI — Project Structure

The complete map of the repository: what every part is for, what state it's in,
and which phase brings it to life. Read this with `ROADMAP.md` open — the phase
tags (P0–P5) match.

## Legend

| Mark | Meaning |
|------|---------|
| ✅ | already built (real code) — reuse as-is |
| ❌ | broken — delete now, rebuild later |
| ⬢ **Pn** | build/fill in this phase |
| ◦ | keep as empty placeholder — future, not v1 |
| ✂ | **robot heritage — out of scope for the Developer OS.** Defer or delete (see §4) |

---

## 1. Top-level map

```
origami/
├── core/          Layer 2 — the brain: schemas, planner, executor, orchestrator, events
├── engines/       Layer 5 + memory — the model brain + memory/knowledge engines
├── skills/        Layer 4 — capabilities (tools) the planner selects; each wraps an adapter
├── adapters/      Layer 4 plumbing — raw API/OS clients (✅ the strongest existing layer)
├── agents/        Layer 3 — domain specialists (developer, research, …) built on the spine
├── interfaces/    Layer 1 — surfaces: CLI, API (later dashboard/voice/mobile)
├── configs/       YAML config per environment / engine / skill
├── storage/       persistence: db, cache, vectors, logging (mostly future)
├── tests/         end-to-end + unit; every phase ships one test
├── docs/          the plan (this folder)
├── platform/      hardware drivers — ✂ mostly robot heritage
├── assets/        models, datasets, prompts, media
├── scripts/       dev/setup/deploy helpers
└── docker/        containerization (future)
```

**In scope for v1 (the Developer OS):** `core`, `engines/{llm-or-reasoning,
memory}`, `skills`, `adapters`, `agents/coding_assistant`, `interfaces/{cli,api}`,
`configs`, `tests`, `docs`.

**Deferred / out of scope (robot heritage):** `platform/robot`,
`platform/simulator`, `engines/{vision,navigation,voice}`, `skills/robot`,
`assets/models/vision`, hardware scripts. See §4 — this is the single biggest
scope decision.

---

## 2. Annotated tree (in-scope parts)

```
core/                                Layer 2 — the brain
├── events.py                 ✅     EventBus + global event_bus + EventTypes (reuse as-is)
├── schemas/
│   ├── goal.py               ⬢ P1   Goal(text, source, context, session_id)   [NEW]
│   ├── tool.py               ⬢ P1   ToolSpec(name, description, params, confirm, read_only)  [NEW]
│   ├── plan.py               ⬢ P1   Step, Plan                                 [NEW]
│   ├── result.py             ⬢ P1   StepResult, RunResult                      [NEW]
│   ├── memory.py             ⬢ P4   MemoryRecord, ProjectMemory
│   ├── task.py               ◦      task graph — later
│   ├── user.py               ◦      user profile — later
│   └── event.py              ◦      typed events — optional (events.py covers v1)
├── planner.py                ⬢ P1   Planner: Goal → Plan (LLM + keyword fallback)
├── executor.py               ⬢ P1   Executor: run steps, confirm gate, publish events
├── orchestrator.py           ⬢ P1   Orchestrator.handle(goal): plan → execute → remember
├── session.py                ⬢ P1   per-conversation session state (thin)
├── context.py                ⬢ P1   context enrichment for Goal (thin; grows later)
├── constants.py              ◦      shared constants
├── exceptions.py             ⬢ P1   OrigamiError hierarchy (small)
└── reasoner.py               ◦      advanced reasoning — later

engines/                             Layer 5 (models) + memory/knowledge
├── reasoning/                ⬢ P1.5 ← THE BRAIN lives here (see §3 reconciliation)
│   ├── llm.py                ⬢ P1.5 LLMEngine ABC + LLMResponse
│   ├── engine.py             ⬢ P1.5 RouterEngine — picks local / echo / free-tier per call
│   ├── prompts.py            ⬢ P1   PLANNER_PROMPT etc.
│   └── tools.py              ◦      reasoning helpers
│   └── providers/            ⬢ P1.5 [NEW]  echo.py (P1) · local.py Ollama (P1.5) · gemini/groq (opt)
├── memory/                   ⬢ P4   structured memory (great placeholders already here)
│   ├── engine.py             ⬢ P4   MemoryEngine ABC + JSON-backed impl
│   ├── short_term.py         ⬢ P4   session working memory
│   ├── long_term.py          ⬢ P4   projects, decisions, bugs, preferences (JSON first)
│   ├── retrieval.py          ⬢ P4   query → records (keyword first, embeddings later)
│   └── embeddings.py         ◦      vector search — later
├── knowledge/                ◦      knowledge graph — later (VISION #10/#18)
├── planning/                 ◦      advanced multi-step planning — later
├── vision/  navigation/  voice/   ✂ robot heritage — defer (see §4)

skills/                              Layer 4 — capabilities (tools). Each self-registers.
├── base.py                   ✅→⬢P1 Skill ABC (extend: add specs() + execute(tool,**kw))
├── registry.py               ⬢ P1   ⭐ ToolRegistry + global registry + @tool decorator  (KEYSTONE)
├── spotify/skill.py          ⬢ P1   wraps ✅ adapters/spotify — proof-of-engine slice
├── coding/                   ⬢ P2   ⭐ THE CODING CORE (see §3 — Claude Code lives here)
│   ├── skill.py              ⬢ P2   code.build / code.refactor / code.test / code.review
│   ├── tools.py              ⬢ P2   drives `claude -p` headless; falls back to local model
│   └── handlers.py           ◦
├── terminal/skill.py         ⬢ P2   [NEW dir] wraps ✅ adapters/terminal (terminal.run, confirm)
├── github/skill.py           ⬢ P2   wraps ✅ adapters/github (github.list_prs/issues)
├── calendar/skill.py         ⬢ P4+  wraps ✅ adapters/calendar
├── project/skill.py          ⬢ P4   [NEW dir] project.status / project.continue (memory-backed)
├── reminder/  robot/         ◦/✂    reminder later; robot ✂ heritage

adapters/                            Layer 4 plumbing — ✅ ALREADY BUILT, reuse everywhere
├── spotify/{auth,client}.py  ✅     search_and_play, play, pause, next/previous_track
├── github/{auth,client}.py   ✅     list_pull_requests, list_issues, create_*, trigger_workflow
├── terminal/{executor,sandbox}.py ✅ TerminalExecutor.run / run_async / run_checked
├── browser/{config,controller}.py ✅ Playwright automation
├── calendar/{auth,client}.py ✅     Google Calendar
├── desktop/{mac,linux,windows}.py ✅ OS automation (in scope for #8 later)
└── protocols/websocket.py    ✅     ws transport

agents/                              Layer 3 — specialists on top of the spine
├── conversation/agent.py     ❌ P1   BROKEN import (LLMEngine/MemoryEngine/schemas missing) → delete now, rebuild P3
├── coding_assistant/         ⬢ P3   the developer agent (uses coding skill + memory)
├── research/  task_planner/  ◦      later agents

interfaces/                          Layer 1 — surfaces
├── cli/main.py               ⬢ P1   `origami "..."` → Goal → orchestrator → print; REPL in P2
├── cli/{commands,utils}.py   ⬢ P2
├── api/app.py                ⬢ P3   FastAPI: POST /goal → RunResult
├── api/routes/*              ◦/P3   health (P3), orchestrator (P3), rest later
├── web/ desktop/ mobile/     ◦      future surfaces
└── shared/*.ts               ◦      future TS types

configs/
├── environments/dev.yaml     ⬢ P1.5 selects default engine=local, code tool=coding
├── environments/{test,staging,prod}.yaml ⬢ test→echo (P1); others later
├── _schemas/llm.py           ⬢ P1.5 config schema for the brain
├── skills/{spotify,coding,calendar}.yaml ⬢ per-skill config (as each skill lands)
└── engines/*.yaml            ◦/✂    memory (P4); navigation/voice ✂

tests/
├── conftest.py + mocks/mock_llm.py ⬢ P1  fakes (fake Spotify client, EchoEngine)
├── e2e/test_user_journey_basic.py  ⬢ P1  the play-music slice test (keyless, green in CI)
├── integration/test_skill_execution.py ⬢ P2  registry + confirm-gate
├── integration/test_memory_retrieval.py ⬢ P4
└── unit/test_orchestrator.py ⬢ P1

root files
├── pyproject.toml            ⬢ P0   package metadata + deps
├── requirements*.txt         ⬢ P0
├── README.md                 ✅     front door (done)
├── .env.example              ⬢ P0   OLLAMA_HOST, ORIGAMI_LLM, SPOTIFY_*, optional keys
├── main.py                   ⬢ P1   [NEW] build_orchestrator() composition root
├── Makefile / .gitignore / .pylintrc ⬢ P0  dev ergonomics
```

---

## 3. Reconciliation decisions (existing scaffold vs the plan)

The earlier docs used clean conceptual names; the repo already has homes for
most of them. Where they differ, this is the ruling so there's one source of
truth:

1. **The brain: use `engines/reasoning/`, not a new `engines/llm/`.** The repo
   already scaffolds `engines/reasoning/{llm.py, engine.py, prompts.py, tools.py}`.
   Put `LLMEngine` in `llm.py`, the `RouterEngine` in `engine.py`, and add a
   `providers/` subfolder. Wherever `ARCHITECTURE.md`/`RUNNING_FREE.md` say
   `engines/llm/…`, read it as `engines/reasoning/…`.

2. **The coding tool: use `skills/coding/`, not a new `skills/claude_code/`.** The
   repo already has `skills/coding/{skill,tools,handlers}.py` and
   `configs/skills/coding.yaml`. The Claude-Code driver lives in
   `skills/coding/tools.py`; the skill exposes `code.build/refactor/test/review`.
   It degrades gracefully: if the `claude` CLI is absent, it uses the local model.

3. **Memory: use the existing `engines/memory/` files.** `long_term.py` (projects/
   decisions/bugs/preferences), `short_term.py` (session), `retrieval.py`
   (query). Start JSON-backed; `embeddings.py` stays empty until you want vector
   search. This is richer than the single `json_store.py` the earlier draft
   proposed — prefer these files.

4. **Events: keep `core/events.py` as-is.** It already provides `event_bus` and
   `EventTypes.SKILL_EXECUTED/FAILED`. Don't duplicate in `core/schemas/event.py`.

---

## 4. The big scope call: Developer OS vs Robot heritage

The folder is named `origami-robot` and carries a full physical-robot skeleton —
`platform/robot/{motors,sensors,camera,esp32,battery}`, `platform/simulator`,
`engines/{vision,navigation,voice}`, `skills/robot`, `assets/models/vision`,
`scripts/{enroll_face,test_hardware}`. **None of it is part of the Developer OS
vision** you described.

Decision to make (recommended: **A**):

- **A. Park it.** Leave the folders empty and ignore them. Zero effort, no
  confusion as long as the roadmap only touches in-scope dirs. Revisit only if
  Origami ever gets hardware (VISION "Home Lab" #19).
- **B. Prune it.** Delete the robot-only trees for a clean, focused repo that
  matches the vision. Best if you want the project to read as a Developer OS to
  anyone (e.g. a portfolio reviewer).

Either way: **do not build into the robot trees during Phases 0–5.** They are
not on the critical path.

---

## 5. Start preparing — setup checklist

Do these once, in order, to be ready to build Phase 0:

```bash
# 1. Confirm your M1 RAM (picks the local model size)
sysctl hw.memsize            # bytes ÷ 1073741824 = GB   (16GB → 14B, 8GB → 7B)

# 2. Free local brain — the one required install
brew install ollama
ollama serve &               # leave running; no rate limit, no cost
ollama pull qwen2.5-coder:7b # or :14b

# 3. Claude Code (optional heavy-coding tier; you have Max)
claude --version             # ensure CLI installed + logged in

# 4. Python env
python3 -m venv .venv && source .venv/bin/activate
python --version             # 3.11+ recommended

# 5. Sanity: the repo imports without the broken agent
#    (Phase 0 deletes agents/conversation/agent.py and fills pyproject.toml)
```

Then the build order is simply: **P0 package → P1 spine + play-music →
P1.5 local brain → P2 coding core** (`ROADMAP.md`). After P2 you have a daily
driver: *describe a coding task → local plans → Claude Code builds → tests run →
you approve.*

---

## 6. One-glance status

| Layer | Dir(s) | Built | Empty | v1 action |
|-------|--------|:----:|:----:|-----------|
| 1 Surfaces | `interfaces/` | 0 | all | fill cli (P1), api (P3) |
| 2 Brain | `core/` | events.py | rest | fill spine (P1) |
| 3 Agents | `agents/` | 0 | all (1 broken) | delete broken (P1), build coding agent (P3) |
| 4 Tools | `skills/` | base.py | rest | registry + skills (P1–P2) |
| 4 Plumbing | `adapters/` | **all ✅** | — | reuse |
| 5 Models | `engines/reasoning` | 0 | all | brain (P1.5) |
| Memory | `engines/memory` | 0 | all | fill (P4) |
| — | robot heritage | 0 | all | ✂ park (§4) |

The adapters are your head start. Everything else is the spine — and the spine
is the whole project.
