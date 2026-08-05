# ORIGAMI — Engineering Journal

> **Maintained by the Project Historian.** This journal is append-only. Each
> work session adds a new dated entry at the **bottom**. History is never removed
> or rewritten — only appended. Read top-to-bottom to understand the entire
> project history from the beginning.
>
> Companion docs: `docs/PURPOSE.md` (the north star / why the project exists),
> `docs/CHECKPOINTS.md` (the completion checklist / what to build), `CLAUDE.md`
> (per-session working brief).

---

## Session 001 — 2026-08-05

### Session Summary

First engineering session. The project was inherited as a large, non-running
skeleton (249 files, 231 empty, only the adapter layer real) with a strong but
uncommitted plan. This session did **no engine coding** — instead it rescued and
committed the plan, made the project a real installable Python package
(Checkpoint C0, tagged `v0.1.0`), recovered and preserved the project's true
founding vision, and converted "finish the project" into an actionable checkpoint
checklist reordered around the owner's real goal (free task automation, not a
coding assistant). The project now installs, imports, and is ready to build; the
next step is C1 (the engine spine).

### Completed Work

- **Analysis & orientation** — mapped the repo: 197 Python files, 179 stubs;
  identified the adapter layer (Spotify, GitHub, Terminal, Browser, Calendar,
  Desktop) as the only real code; identified the whole brain/skills/engines/
  interfaces as empty.
- **Rescued the plan** (commit `5313450`) — the six planning docs and `CLAUDE.md`
  had sat uncommitted for a week; committed and pushed them so the project's
  intellectual asset was no longer at risk.
- **Checkpoint C0 — installable package** (commit `2d95ca9`, tag `v0.1.0`):
  - Filled `pyproject.toml` (package `origami`, deps, dev/llm/browser extras,
    `origami` console script, pytest/black config).
  - Filled `requirements.txt`, `requirements-dev.txt`, `.env.example`, `Makefile`,
    `.pylintrc`, `.gitignore`.
  - Filled the three empty CI workflows (`test.yml`, `lint.yml`, `deploy.yml`) —
    keyless test + advisory lint on push/PR; deploy is a manual no-op.
  - Added `.vscode/settings.json` + `extensions.json` (auto-selects `.venv`,
    pytest integration, black-on-save, 100-col ruler).
  - Refactored `adapters/__init__.py` → moved the `Adapter` ABC into
    `adapters/base.py` where its own header said it belonged; defined the
    previously-undefined `AuthError`; removed a dead example class.
  - Deleted the broken `agents/conversation/agent.py` (imported non-existent
    modules), the empty redundant `setup.py`, and empty `tests/pytest.ini`.
  - Created `.venv` (Python 3.11), verified `pip install -e ".[dev]"`, verified
    all seven packages import cleanly from outside the repo, verified `pytest`
    collects with zero import errors, verified stdlib `platform` is not shadowed.
- **Preserved the founding vision** (commit `7ae3d57`) — created
  `docs/PURPOSE.md` as the authoritative north star after the owner supplied the
  original spec; wired `CLAUDE.md` to read it first.
- **Rewrote the completion checklist** (commit `0e183f3`) — replaced
  `docs/CHECKPOINTS.md` with a reordered, actionable 7-checkpoint ladder; folded
  in the 3-tier permission model; recorded the 8 GB / zero-key cost reality.
- **Persistent memory** — saved `origami-original-purpose` and
  `origami-project-workflow` memories so future sessions don't drift from the
  vision or lose the repo/workflow conventions.

### Important Decisions

- **Recovered the true vision: ORIGAMI is a 5-stage evolution ending in a
  humanoid robot, not merely a "Developer OS."** *Why:* the owner produced the
  founding spec ("Omnipresent Robotic General Artificial Modular Intelligence").
  The robot folders (`platform/robot`, `engines/{vision,navigation,voice}`) are
  Stage 5 placeholders, not dead heritage. The "Developer OS" framing is Stages
  1–2 — a pragmatic starting point, **not** a replacement. Recorded permanently in
  `PURPOSE.md` so the endgame is never quietly dropped.
- **Reordered the roadmap around task automation, demoting the coding assistant.**
  *Why:* the owner's actual daily need is "play a song / message my mom / email my
  professor" at **zero recurring cost**, not an AI coding tool. The coding core
  (Claude Code) became an optional side-track. New ladder: spine → real actions →
  messaging → memory → Goal Mode → proactive brief.
- **Adopted a 3-tier permission model (SAFE / CONFIRM / CRITICAL), replacing the
  binary `confirm` flag.** *Why:* the owner proposed distinguishing "affects other
  people" (send a message → CONFIRM) from "irreversible/costly" (delete, money,
  force push, robot movement → CRITICAL). It is cheap to bake into the `ToolSpec`
  schema before the executor exists and expensive to retrofit after. It also maps
  cleanly to Stage 5 (robot movement = CRITICAL).
- **EchoEngine is the default brain; no checkpoint requires a paid API key.**
  *Why:* the owner is on an 8 GB M1 Air and wants $0 recurring cost. Command-style
  tasks need no reasoning — a keyword matcher suffices. A local 3B model (Ollama)
  and Claude Code are optional accelerators, never requirements. The 7B model
  strains 8 GB, so it is not the default.
- **Excluded `platform/` from packaging.** *Why:* it is out-of-scope robot
  heritage AND its name shadows Python's stdlib `platform` module, which would
  break third-party imports once installed. Verified the stdlib module is intact.
- **Kept the capability-registry + centralized-planner architecture** (inherited,
  affirmed). *Why:* the "one architectural law" is that adding a capability must
  never edit `core/`. Tools self-register via a `@tool` decorator into a global
  registry; the planner selects from that registry. This prevents the
  `if command == ...` dispatch ladder that rots such projects, and is the single
  property the whole project bets on.
- **Build in vertical slices; never scaffold empty folders.** *Why:* the project's
  own history (231 empty files, nothing runnable) proves that "build all modules
  first" fails. Progress is measured by runnable capabilities, not file count.

### Current Architecture

Unchanged in shape from the inherited design (it is sound); this session made it
*real* at the packaging layer only. The 8-layer model, mapped 1:1 to directories:

```
interfaces/  Layer 1  surfaces (CLI now; API/web/mobile later)
core/        Layer 2  brain — schemas, planner, executor, orchestrator, events
agents/      Layer 3  reasoning specialists (built on the spine, later)
engines/     Layer 5  reusable intelligence — reasoning(LLM), memory, ...
skills/      Layer 4  capabilities (tools) that self-register; wrap adapters
adapters/    Layer 4  raw API/OS clients  ← ONLY layer with real code today
storage/              persistence (later)
platform/             hardware — robot heritage, PARKED, excluded from packaging
```

Control law: goal → Planner → picks Tools (registry) → Executor (risk gate) →
result + memory + events. `agents decide · skills execute · adapters communicate ·
storage remembers · core coordinates.` Default brain = `EchoEngine` (keyless).
Risk gate = SAFE / CONFIRM / CRITICAL (to be implemented in C1).

**Real code today:** `adapters/*`, `adapters/base.py`, `core/events.py`,
`skills/base.py` (stub-level). Everything in `core/` (except events), `engines/`,
`skills/` (except base), `interfaces/` is still empty.

### Current Project Status

- **Current Version:** `v0.1.0`
- **Completed Milestones:** C0 — Package installs (installable, imports clean,
  pytest collects keyless, CI green).
- **Current Milestone:** C1 — The spine + 3-tier permissions (target `v0.2.0`).
  Not started.
- **Current Branch:** `main` (working tree clean; all work committed & pushed to
  `github.com/Charan666-one/ORIGAMI`).
- **Project Health:** 🟢 Healthy. Installs and imports cleanly; plan and vision are
  committed and unambiguous; no runnable user-facing capability yet (expected at
  this stage). Note: git author-dates on this session's commits span 2026-07-17→21
  while the working date is 2026-08-05 — a clock/metadata quirk, not a concern.

### Remaining Tasks (highest priority first)

1. **C1 — build the engine spine** (target `v0.2.0`): schemas (`goal`, `tool` w/
   `Risk` enum, `plan`, `result`), `skills/registry.py` (the keystone),
   `engines/reasoning/llm.py` + `providers/echo.py`, `core/{planner,executor,
   orchestrator,session,context}.py`, `skills/spotify/skill.py`,
   `interfaces/cli/main.py` + root `main.py`, and
   `tests/e2e/test_user_journey_basic.py`. Exit: `origami "play some lofi"` runs
   keyless; a CRITICAL tool refuses without approval; adding a 2nd tool touches
   zero `core/` files.
2. **C2 — real actions** (`v0.3.0`): terminal + desktop skills; real Spotify creds.
3. **C3 — messaging with preview→approve** (`v0.4.0`): Gmail adapter + email skill.
4. **C4 — memory** (`v0.5.0`).
5. **C5 — Goal Mode** (`v0.6.0`) — the differentiator.
6. **C6 — proactive morning brief** (`v0.7.0`).
7. **v1.0.0** — 14 days of real daily use at $0, zero unapproved sends.

### Blockers

None. The path to C1 is fully unblocked — no external accounts, keys, or installs
are required to build and test it (EchoEngine + fake Spotify client).

### Lessons Learned

- **Uncommitted work is invisible work.** A week of excellent planning sat one
  disk failure away from oblivion. Commit early; the plan is an asset.
- **A folder is not progress.** 231 empty files created the *illusion* of a nearly
  built system while nothing ran. Only runnable, tested slices count.
- **Naming can break you silently.** `platform/` shadowing the stdlib is the kind
  of latent bug that only detonates after install — worth catching at packaging.
- **Recover intent before optimizing execution.** The single most valuable act was
  getting the owner's true 5-stage vision on the record; every roadmap decision
  flows from it.

### Next Session — resume here

- **Current module:** `core/schemas/` (start of Checkpoint C1).
- **Current files:** all empty and waiting — `core/schemas/goal.py`,
  `core/schemas/tool.py`, `core/schemas/plan.py`, `core/schemas/result.py`,
  `core/exceptions.py`.
- **Expected first task:** create `core/schemas/goal.py` with
  `Goal(text, source, context, session_id)`, then `core/schemas/tool.py` with
  `ToolSpec(name, description, params, risk)` where `risk` is the
  `Risk(SAFE|CONFIRM|CRITICAL)` enum. Follow the C1 build order in
  `docs/CHECKPOINTS.md` top-to-bottom. Activate the venv first:
  `source .venv/bin/activate`. Do not create empty folders ahead of need.
- **Definition of done for the session:** as many C1 boxes checked as possible,
  `pytest` green keyless, committed. Do not end with red tests on `main`.
