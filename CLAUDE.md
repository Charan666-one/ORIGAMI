# CLAUDE.md — working context for Origami

You are helping build **Origami**, a developer operating system. This file is
your standing brief. Read it first every session. The full plan lives in `docs/`
(linked below) — read the relevant doc before touching a layer.

---

## What Origami is (one paragraph)

One interface that turns a plain-English goal into action by planning over a
registry of tools, backed by structured memory, running mostly on a free local
model with Claude Code for heavy coding. Not a chatbot — a coordinator. Every
capability (build auth, continue a project, review a PR, play music) is a *tool*
or *workflow* plugged into an unchanged core.

## The one architectural law (do not break this)

> **Adding a capability must never require editing `core/`.** Tools self-register
> via the registry. If you find yourself adding an `if/elif` on intent, or
> importing a specific skill inside `core/`, stop — the abstraction is wrong.

The only place skills are named is the composition root (`main.py`), which
imports skill modules so their `@tool` decorator registers them.

## How the pieces fit

```
goal → Planner → picks Tools (registry) → Executor (confirm gate) → result
          ↑                                        │
          └──────── Memory + Context ──────────────┘
LLMEngine (local Ollama default; Claude Code is a TOOL, not the engine)
```

Data flows down the layers, control flows up. See `docs/ARCHITECTURE.md`.

---

## Ground rules

1. **Vertical slices only.** Make one path run end-to-end before adding breadth.
   Never leave a layer half-wired to start another.
2. **Every phase ships a test that runs keyless in CI** (via `EchoEngine` + fakes).
   No external API required to prove a slice.
3. **Confirm before consequences.** Any tool that writes files, spends money,
   deletes, deploys, or runs shell commands is `confirm=True, read_only=False`.
   Reads never prompt.
4. **Reuse the adapters — they are already built and tested** (`adapters/`).
   Skills wrap adapters; do not reimplement API clients.
5. **Free at the margin.** Default brain is the local model. Escalate to Claude
   Code only for hard/high-stakes coding. See `docs/RUNNING_FREE.md`.
6. **Degrade gracefully.** If the `claude` CLI or a token is absent, fall back
   (Claude Code → local model; real engine → EchoEngine). Never hard-crash on a
   missing optional dependency.
7. **Measure progress by runnable capabilities, never file count.** (231 empty
   files already taught this lesson.)
8. **Do not build into robot-heritage trees** (`platform/robot`, `engines/vision`,
   `engines/navigation`, `engines/voice`, `skills/robot`, `platform/simulator`).
   Out of scope. See `docs/STRUCTURE.md` §4.

---

## Reconciliation (existing scaffold → plan names)

The docs sometimes use clean conceptual names; build in the existing homes:

- **Brain / LLM engine → `engines/reasoning/`** (`llm.py` = `LLMEngine` ABC,
  `engine.py` = `RouterEngine`, add `providers/` with `echo.py`, `local.py`).
  Where docs say `engines/llm/`, read `engines/reasoning/`.
- **Coding tool → `skills/coding/`** (`skill.py` exposes `code.build/refactor/
  test/review`; `tools.py` drives `claude -p` headless, falls back to local).
  Where docs say `skills/claude_code/`, read `skills/coding/`.
- **Memory → `engines/memory/`** existing files (`long_term.py`, `short_term.py`,
  `retrieval.py`; JSON first, `embeddings.py` later).
- **Events → keep `core/events.py` as-is** (`event_bus`, `EventTypes`).

---

## Current state (updated 2026-07-17 — Phase 0 complete, tag `v0.1.0`)

- ✅ Built: `adapters/*` (Spotify, GitHub, Terminal, Browser, Calendar, Desktop),
  `core/events.py`, `skills/base.py`, `adapters/base.py` (Adapter ABC + AuthError).
- ✅ Phase 0 done: packaging (`pyproject.toml`, requirements), `.env.example`,
  Makefile, pylint, CI workflows, `.vscode/`; broken conversation agent deleted
  (rebuild in Phase 3); `pip install -e ".[dev]"` + all imports + pytest verified.
- ◦ Empty: the whole brain, skills, engines, interfaces. Project does not run yet.
- ✅ **C1 done (`v0.2.0`)**: the engine spine runs. `origami "play some lofi"`
  flows CLI→planner→registry→executor (3-tier risk gate + verification)→Spotify
  skill, keyless via EchoEngine. 4 tests green. Real code now in every layer
  except memory (C4).
- **Scoreboard: `docs/CHECKPOINTS.md`** — one checkpoint at a time, tag when its
  boxes are all checked. Next: **C2 (real actions — terminal + desktop skills)**.
- ⚠️ If the `origami` script raises `ModuleNotFoundError: interfaces`: the macOS
  homebrew-python venv breaks two ways — (1) `brew upgrade` invalidates a
  *symlinked* venv, (2) setuptools' default editable **MAPPING finder** is
  *intermittently* unreliable here (works then fails seconds later). **Durable fix
  (both):** `make venv` — rebuilds with `--copies` (survives brew upgrades) and
  installs editable in **compat mode** (plain `.pth`, no finder). Verified 18/18
  from `/tmp`. Always verify from another dir: `cd /tmp && .../.venv/bin/origami "x"`.

## What to build next — follow `docs/CHECKPOINTS.md` (authoritative ladder)

**Next up: C1 — the spine + 3-tier permissions (tag `v0.2.0`).** Bake the
`Risk` enum (`SAFE` / `CONFIRM` / `CRITICAL`) into `core/schemas/tool.py` from
day one; the executor enforces it. Free/keyless via `EchoEngine` — no paid API
key is required by any checkpoint. Ladder: C1 spine → C2 real actions →
C3 messaging (preview→approve) → C4 memory → C5 **Goal Mode** → C6 proactive brief.

<details>
<summary>Legacy phase notes (superseded by CHECKPOINTS.md ordering)</summary>

- **Phase 0 (½ day):** fill `pyproject.toml` / `requirements*.txt` / `README.md`
  (done) / `.env.example`; delete the broken conversation agent; ensure
  `pip install -e .` and `import core, skills, adapters` succeed; `pytest`
  collects cleanly.
- **Phase 1 (⭐):** the spine + `origami "play some lofi"` end-to-end through all
  five layers, with `EchoEngine` so it runs keyless. Exit test:
  `tests/e2e/test_user_journey_basic.py` green, and adding a 2nd Spotify tool
  touches zero `core/` files.
- **Phase 1.5:** wire `LocalEngine` (Ollama) as the default brain.
- **Phase 2 (⭐ daily driver):** `skills/coding/` (Claude Code) + `skills/terminal/`
  + `skills/github/`. Loop: local plans → Claude Code builds → terminal tests →
  confirm → summary.
- **Phase 3:** real LLM provider + first agent (`agents/coding_assistant/`).
- **Phase 4:** project memory ("continue <project>").
- **Phase 5:** proactive event-driven workflows.

</details>

Work one checkpoint at a time. Do not start C(n+1) until C(n)'s boxes in
`docs/CHECKPOINTS.md` are all checked. One commit per checkpoint minimum; tag on close.

---

## Environment / commands

```bash
# free local brain (default)
ollama serve &                 # http://localhost:11434
ollama pull qwen2.5-coder:7b   # :14b if 16GB RAM

# project
pip install -e .
pytest                         # keyless via EchoEngine
origami "play some lofi"       # the Phase-1 proof
```

Env vars (`.env`): `OLLAMA_HOST`, `ORIGAMI_LLM=local`, `ORIGAMI_CODE_TOOL=coding`,
`SPOTIFY_CLIENT_ID/SECRET` (optional), `ANTHROPIC_API_KEY` (optional — Claude Code
via CLI/subscription doesn't need it).

## Conventions

- Python 3.11+, `async` throughout the core (planner/executor/skills are async).
- Type hints + small dataclasses for schemas (`core/schemas/`).
- Keep `core/` free of any concrete skill/provider import.
- Prefer editing the existing empty placeholder over creating a new file/dir.

---

## The plan docs (read before building each layer)

| Doc | Read when |
|-----|-----------|
| `docs/PURPOSE.md` | **the north star — read FIRST.** Original vision: modular AI OS → humanoid robot in 5 stages. The robot is the endgame; Developer OS is Stages 1–2. Two guardrails against drift. |
| `docs/VISION.md` | you need the why / the capability backlog |
| `docs/ARCHITECTURE.md` | building any `core/` or engine contract |
| `docs/ROADMAP.md` | deciding what to build next (phase + exit criteria) |
| `docs/RUNNING_FREE.md` | anything about models, cost, or Claude Code |
| `docs/STRUCTURE.md` | placing a file / checking scope |

If a request conflicts with these rules, say so and propose the in-architecture
way to do it.
