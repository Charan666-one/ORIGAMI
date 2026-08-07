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

---

## Session 002 — 2026-08-05

### Session Summary

A **vision-refinement session**, no engine code. The owner supplied a
significantly expanded and sharpened statement of ORIGAMI's purpose ("The AI
Operating System for Human Potential"). It does not contradict the founding
spec — it deepens it — so `docs/PURPOSE.md` was rewritten as the new canonical
north star, several new principles were absorbed into the build docs, and
persistent memory was updated. The checkpoint ladder still holds; only small
additions were made to reflect the new Verification step and the 5-ability law.

### Completed Work

- **Rewrote `docs/PURPOSE.md`** as the superseding canonical vision, integrating
  the richer spec while preserving the 5-stage robot endgame and the two
  anti-drift guardrails.
- **`docs/CHECKPOINTS.md`** — added the 5-ability law as rule #8; added a
  **verification hook** requirement to the C1 executor box (the lifecycle's
  Verification stage, trivial in C1, grown later).
- **Updated memory** `origami-original-purpose` — replaced the agent-centric
  architecture note with the layer-based stack, the universal lifecycle, the
  5-ability law, the "model is not ORIGAMI" tenet, offline-first ordering, and
  the Monitoring/Executive engines.

### Important Decisions

- **Architecture reframed as LAYERS, not agents.** *Why:* the new spec explicitly
  states ORIGAMI is "built around layers rather than individual agents." This is a
  clarification, not a rewrite — the existing planner→registry→executor spine is
  already layer-based. Effect: we stop thinking in terms of autonomous agents for
  Stages 1–2 and think in terms of a fixed pipeline (Conversation → Intent →
  Context → Planning → Workflow → Capability Registry → Execution → Verification →
  Memory → Knowledge → Brain Interface). Agents, if any, return only in Stage 3.
- **Adopted the Universal Lifecycle with an explicit Verification step.** *Why:*
  the founding spec ended at Execution → Memory; the new one inserts
  **Verification** (did the action achieve the intent?) and makes **Monitoring**
  a first-class ongoing stage. Recorded so the executor grows a verification hook
  from C1 onward rather than bolting it on later.
- **Adopted the Fundamental Engineering Law (5 abilities).** *Why:* the owner
  wants a hard filter against scope creep — every feature must improve Understand,
  Plan, Execute, Remember, or Monitor, or it stays out of Core. Added as an
  explicit checklist rule.
- **Elevated provider-independence to a core tenet ("the model is NOT ORIGAMI").**
  *Why:* the reasoning model must be replaceable behind one `LLMEngine` interface
  with zero redesign. This locks in the already-planned Brain Interface and
  validates EchoEngine-first / local-first: the model is a swappable part, not the
  system.
- **Confirmed the 3-tier permission model.** *Why:* the new spec independently
  specifies exactly the SAFE / CONFIRM / CRITICAL tiers we committed in Session
  001 — external validation that the decision was right. No change needed.
- **Kept the checkpoint ladder unchanged.** *Why:* the new engines (Monitoring,
  Executive, Knowledge, Verification) already map onto existing checkpoints
  (C4 memory, C5 Goal Mode, C6 brief) and lifecycle stages. No reorder warranted;
  only annotations added. Avoided the temptation to scaffold new engine folders
  (guardrail #2).

### Current Architecture

Refined framing (see `PURPOSE.md`): a **layered pipeline**, not agents. Control
spine = the Universal Lifecycle. The reasoning model sits behind a **Brain
Interface** and is replaceable. New named engines on the roadmap: **Verification**
(after execution), **Knowledge** (local retrieval before external AI),
**Monitoring** (consent-based, continuous), **Executive** (proactive briefs).
Repo directory mapping is unchanged; no code moved. Real code today is still only
`adapters/*`, `core/events.py`, base classes.

### Current Project Status

- **Current Version:** `v0.1.0` (unchanged — this was a docs/vision session)
- **Completed Milestones:** C0 — Package installs.
- **Current Milestone:** C1 — The spine + 3-tier permissions (`v0.2.0`). Not started.
- **Current Branch:** `main` (clean; committed & pushed).
- **Project Health:** 🟢 Healthy. Vision is now richer, current, and committed;
  build plan is consistent with it; no runnable capability yet (expected).

### Remaining Tasks (highest priority first)

Unchanged from Session 001: **C1 spine** → C2 real actions → C3 messaging →
C4 memory → C5 Goal Mode → C6 proactive brief → v1.0.0. The new Monitoring/
Executive/Knowledge/Verification concepts are folded into C4–C6 and the executor,
not added as separate checkpoints.

### Blockers

None.

### Lessons Learned

- **Capture vision revisions as first-class history.** A sharpened vision is a real
  project event; recording *what changed and why* prevents future confusion about
  when "layers, not agents" or "the 5-ability law" entered the design.
- **Validation is a decision too.** The new spec independently re-derived the
  3-tier permission model — worth recording as confirmation, not silently skipping.
- **Resist scaffolding on inspiration.** A richer vision tempts new empty folders
  (Monitoring/Executive engines). Guardrail #2 held: annotate the plan, build the
  slice when its checkpoint arrives.

### Next Session — resume here (unchanged from Session 001)

- **Current module:** `core/schemas/` (start of Checkpoint C1).
- **Current files (empty, waiting):** `core/schemas/goal.py`, `tool.py`, `plan.py`,
  `result.py`, `core/exceptions.py`.
- **Expected first task:** `core/schemas/goal.py` →
  `Goal(text, source, context, session_id)`, then `core/schemas/tool.py` with the
  `Risk(SAFE|CONFIRM|CRITICAL)` enum. Follow the C1 build order in
  `docs/CHECKPOINTS.md` top-to-bottom. `source .venv/bin/activate` first. No empty
  folders ahead of need. Remember the executor now needs a verification hook.

---

## Session 003 — 2026-08-05

### Session Summary

**First code session — Checkpoint C1 is DONE.** Built the entire engine spine as
one vertical slice: `origami "play some lofi"` now flows through all layers
(CLI → Goal → Planner → EchoEngine → Registry → Executor with the 3-tier risk
gate + verification hook → Spotify skill wrapping the existing adapter) and
returns a summary. Four keyless tests pass. The architecture law holds: adding a
tool touches zero `core/` files. A significant chunk of the session was spent
diagnosing a broken virtualenv (see Blockers/Lessons). Tagged `v0.2.0`.

### Completed Work

- **Schemas** (`core/schemas/`): `goal.py` (Goal), `tool.py` (ToolSpec + **Risk**
  enum SAFE/CONFIRM/CRITICAL), `plan.py` (Step, Plan), `result.py` (StepResult,
  RunResult with `success` + `verified` + `skipped`), and `__init__.py` exports.
- **Exceptions** (`core/exceptions.py`): OrigamiError hierarchy.
- **Registry** (`skills/registry.py`, the keystone): `ToolRegistry`, global
  `registry`, `@tool` decorator, `register_skill()` helper. Overwrite-on-register
  makes re-composition idempotent.
- **Skill base** (`skills/base.py`): reworked to `specs()` + `execute(tool, **kw)`.
- **Brain Interface** (`engines/reasoning/llm.py`): `LLMEngine` ABC + `LLMResponse`
  + a concrete `keyword_match_plan()` default (the planner's keyword fallback).
  `providers/echo.py`: `EchoEngine` (keyless, offline).
- **Spine** (`core/`): `planner.py` (delegates to engine, duck-typed registry —
  no core→skills import), `executor.py` (**3-tier risk gate**: SAFE auto,
  CONFIRM/CRITICAL via injected confirmer; **verification hook**; publishes
  SKILL_EXECUTED/FAILED; graceful per-step error capture), `context.py`,
  `session.py`, `orchestrator.py`.
- **First capability** (`skills/spotify/skill.py`): wraps the existing
  `adapters/spotify/client.py` (lazy client so building never needs creds);
  exposes search_and_play / pause / next / previous, all SAFE.
- **Surfaces**: `interfaces/cli/main.py` (argv → Goal → summary; CLI confirmer
  prompts y/N for CONFIRM, typed-name for CRITICAL) and root `main.py`
  (`build_orchestrator()` composition root — the one place skills are named).
- **Test** (`tests/e2e/test_user_journey_basic.py`): 4 keyless tests — play-music
  slice success (fake client), unknown-goal graceful summary, CRITICAL refused
  without approval / runs with it, new-tool-registers-without-core-edit.
- **Packaging**: added `py-modules = ["main"]` so the `origami` console script can
  import the composition root when installed. Created `interfaces/__init__.py`.
- **Verified live**: `origami "play some lofi"` runs end-to-end from outside the
  repo and degrades gracefully without Spotify creds ("...must be set."); unknown
  goal → "couldn't map"; no args → usage; `pytest` → 4 passed.

### Important Decisions

- **Keyword matching lives in the base `LLMEngine.plan()`, not in core.** *Why:*
  EchoEngine inherits it as-is (keyless); a real LLM engine overrides `plan()` and
  calls `super().plan()` as the fallback. This gives "LLM plan + keyword fallback"
  with zero duplication and no bad layering (core never imports an engine).
- **Tools carry their own `keywords` in the ToolSpec.** *Why:* the keyless matcher
  stays fully generic — a new tool becomes reachable by declaring keywords + a
  `query` param, needing zero edits to the engine or core. Directly serves the
  architecture test.
- **`build_orchestrator()` uses a fresh `ToolRegistry`, not the global.** *Why:*
  avoids cross-test state leakage and honors "avoid global state," while the global
  registry + `@tool` remain available for import-time self-registration.
- **Core stays free of concrete skill/engine imports** via dependency injection +
  `TYPE_CHECKING` hints. *Why:* the one architectural law — adding a capability
  must never edit core. Verified by a test that registers a brand-new tool.
- **The Spotify client is created lazily inside the skill.** *Why:* building the
  orchestrator (and importing anything) must never require credentials; only
  actually calling a tool touches the network. Enables keyless CI + graceful CLI.
- **Reverted to setuptools' default editable mode after a fresh venv.** *Why:* see
  Blockers — the compat `.pth` mode depends on `site` processing `.pth` files,
  which the corrupted venv had silently disabled. A clean venv restored the
  default MAPPING finder, which works.

### Current Architecture

No shape change — the C1 slice *realizes* the layered pipeline from `PURPOSE.md`:
CLI (interfaces) → Goal → ContextBuilder → Planner → EchoEngine (Brain Interface)
→ ToolRegistry → Executor (risk gate + Verification hook, publishes to the
existing `event_bus`) → SpotifySkill → adapters/spotify. Real code now exists in
every layer except memory/knowledge (C4) and agents (later).

### Current Project Status

- **Current Version:** `v0.2.0` (C1 shipped).
- **Completed Milestones:** C0 (package installs), **C1 (spine + 3-tier permissions)**.
- **Current Milestone:** C2 — Real actions (terminal + desktop skills, real
  Spotify creds). Not started.
- **Current Branch:** `main` (clean after commit; pushed).
- **Project Health:** 🟢 Healthy and now **runnable**. `origami "..."` works
  end-to-end keyless. 4 tests green. First user-facing capability exists.

### Remaining Tasks (highest priority first)

1. **C2 — real actions** (`v0.3.0`): `skills/terminal/skill.py` (terminal.run,
   CONFIRM), `skills/desktop/skill.py` (open apps, SAFE), real Spotify creds for
   live playback, per-skill YAML config, integration test across all 3 risk tiers.
2. C3 — messaging with preview→approve (Gmail). 3. C4 — memory. 4. C5 — Goal Mode.
   5. C6 — proactive brief. 6. v1.0.0.

### Blockers

None outstanding, but one was resolved this session: **the project virtualenv was
corrupted** — `site` had stopped processing `.pth` files, so editable installs
silently failed to expose packages to the `origami` console script (while
`python -c` from the repo root still worked via cwd, which masked the problem).
Root cause: a homebrew Python 3.11 point-upgrade after the venv was created, so
`.venv/bin/python3.11` pointed at a changed runtime. **Fix:** delete and recreate
`.venv` (`python3.11 -m venv .venv`), reinstall `-e ".[dev]"`. If the console
script ever raises `ModuleNotFoundError: interfaces` again, rebuild the venv first.

### Lessons Learned

- **cwd can mask a broken install.** Because the Bash tool runs from the repo root,
  `import interfaces` "worked" in diagnostics while the real console script (run
  from elsewhere) failed. Always verify installed entry points from a *different*
  directory (`cd /tmp && origami ...`).
- **A stale venv is a real failure mode after OS package upgrades.** Rebuilding is
  cheaper than debugging `.pth`/finder internals.
- **Graceful degradation paid off immediately.** Missing Spotify creds produced a
  clear one-line message, not a stack trace — the executor's per-step try/except
  is why the keyless CLI is usable at all.
- **A vertical slice forces every layer to be real.** Wiring one command end-to-end
  surfaced the packaging (`py-modules`), the missing `interfaces/__init__.py`, and
  the venv bug — none of which a folder-by-folder build would have caught.

### Next Session — resume here

- **Current milestone:** C2 (`docs/CHECKPOINTS.md`).
- **Current module:** `skills/terminal/` and `skills/desktop/`.
- **Expected first task:** create `skills/terminal/skill.py` wrapping
  `adapters/terminal/executor.py` → expose `terminal.run` at **Risk.CONFIRM**
  (first real use of the confirm gate for a raw command). Register it in
  `main.py:build_orchestrator`. Add `skills/desktop/skill.py` (open apps, SAFE)
  wrapping `adapters/desktop/mac.py`. Then `tests/integration/test_skill_execution.py`
  exercising all three risk tiers. **Sanity first:** `source .venv/bin/activate`;
  if the `origami` script errors on import, rebuild the venv (see Blockers).
  Verify live with `origami "run echo hello"` (expect a CONFIRM prompt).

---

## Session 004 — 2026-08-05 (consolidated: C2→C5 + Brain + Monitoring)

### Session Summary

A long, high-output session that took ORIGAMI from "the spine runs" to a genuinely
useful daily assistant with a brain, memory, monitoring, and goal tracking. Covers
several phases in one sitting (the journal fell behind during the build; this entry
catches it up). Tags cut: `v0.3.0` (C2/C3 + Brain). Test suite grew 4 → 68, all green.

### Completed Work

- **Spotify connected end-to-end** (real playback). OAuth PKCE via the existing
  adapter; fixes: env `.env` autoload, `SPOTIFY_REDIRECT_URI` default `127.0.0.1`
  (Spotify dropped `localhost`), tolerate empty API bodies, show song names,
  friendlier errors, **auto-launch the Spotify app + target a device** so "play X"
  just works.
- **C2 real actions:** terminal skill (`run`, first CONFIRM gate — verified
  approve/decline live), desktop skill (`open`/`close` apps, SAFE).
- **YouTube skill** (keyless top-video via results-page scrape) + `desktop.close_app`.
- **C3 email:** `email.draft` opens a prefilled **Gmail compose tab** (switched
  from `mailto:` which no-ops without a default mail app) — preview→approve.
- **Brain Manager** (provider-independent, offline-first): Brain Interface
  (reason/generate/summarize/code), Ollama + optional cloud (Groq/OpenAI, consent-
  gated) + Echo fallback, `ResourceMonitor` (RAM/CPU/battery/temp via psutil).
- **4-level intelligence** (L0 deterministic / L1 fast / L2 standard / L3 cloud):
  `classify_level`, tiered models, resource-aware downgrade, cloud only with consent.
- **Conversational fallback:** unmatched requests → `assistant.ask` (chat), so
  "motivate me…" reaches the brain instead of "couldn't map".
- **Speed tuning for 8GB:** switched default to `llama3.2:1b` (~4-5s vs 17s),
  `num_ctx` 2048, keep-alive, CLI "working…" spinner, one-model-at-a-time guidance.
- **C4 memory:** `JSONMemory` (facts, keyword retrieval, context injection into the
  brain so answers use what ORIGAMI knows), `remember`/`recall`; **12-day expiry**
  for ordinary facts + a **separate permanent store** for important ones.
- **Monitoring Mode:** natural-time parsing (`in N sec/min/hours`, `at 5pm`,
  `tomorrow`), `Scheduler` (~/.origami/tasks.json), `reminder.set/list/done/change`,
  **streaks**, and `origami monitor` — a loop that fires macOS notifications at due
  time and **repeats follow-ups until the task is marked done**.
- **C5 Goal Mode:** `GoalState`/`Milestone`, `GoalBook`, `goal.create` (brain
  decomposes an objective into 5-7 tracked milestones), `goal.status` (progress
  bar), `goal.next`, `goal.done`. Verified: "help me get a Google internship" →
  7-step plan, ticked off with progress.

### Important Decisions

- **Non-editable install is mandatory on this machine.** *Why:* the homebrew-python
  venv's `site` intermittently fails to process `.pth` files, so BOTH setuptools
  editable modes break `origami` with `ModuleNotFoundError: interfaces` (observed
  0/10 after 18/18). Non-editable copies packages into site-packages (no `.pth`).
  Trade-off: `make reinstall` after editing source. `make venv` uses `--copies`
  (survives brew upgrades). This ate real time before being diagnosed.
- **Renamed `platform/` → `platforms/`.** *Why:* compat/non-editable puts the repo
  root on `sys.path`; the old `platform/` shadowed the stdlib `platform` module and
  would break `requests`/`uvicorn`. Out-of-scope robot heritage; nothing imports it.
- **Keyless-first everything (offline, no OAuth sagas):** email via Gmail web
  compose, YouTube via HTML scrape, brain via local Ollama, memory/goals/tasks via
  local JSON. Cloud is always optional + consent-gated. Matches offline-first.
- **`llama3.2:1b` as the default model on 8GB.** *Why:* qwen3:4b (a reasoning model)
  took 17s–120s and thrashed RAM; the 1B instruct model is ~4-5s and adequate for
  chat/emails/goals. Quality tuning deferred by the user ("later").
- **Reasoning models get `think:false`** and outputs are length-capped — reasoning
  chains are too slow on 8GB.
- **Registration order encodes routing priority** (keyword engine): Terminal before
  Desktop; Goals before Reminder (so "completed milestone" is a goal step);
  reminder.list before reminder.set; `assistant.ask` is the catch-all fallback.
- **The architecture law held throughout:** ~9 new skills added, **zero `core/`
  edits**, proven by routing/regression tests.

### Current Architecture

Unchanged in shape; every layer is now real except vision/navigation/voice (robot,
parked). Brain sits behind the Brain Interface; skills depend only on injected
abstractions (brain, memory, scheduler, goals). Composition root `main.py` builds
one of each and injects them. `origami monitor` is a second entry alongside the
one-shot CLI.

### Current Project Status

- **Version:** `v0.3.0` tagged (C2/C3 + Brain); C4/C5 committed, `v0.4.0` next.
- **Completed:** C0, C1, C2, C3(email), Brain Manager + levels, C4 memory,
  Monitoring Mode, C5 Goal Mode.
- **Branch:** `main`, clean, pushed to `github.com/Charan666-one/ORIGAMI`.
- **Health:** 🟢 68/68 tests green; genuinely usable daily assistant.
- **Capabilities (Level 0 unless noted):** music (play/pause/skip), youtube,
  open/close apps, terminal (CONFIRM), email draft (L1/L2), memory
  remember/recall, reminders + monitor + streaks, goals create/status/next/done,
  and conversational chat (L1/L2 via the brain).

### Remaining Tasks (priority order)

1. **C6 — proactive daily brief** (morning summary of goals/reminders/priorities),
   and make `origami monitor` a macOS login-item so it auto-starts.
2. Response-quality tuning (bigger/cloud model option; better prompts).
3. Streaming output (perceived speed).
4. Later: real vector memory, calendar/github skills, the Stage 3+ agents, robot.

### Blockers

None open. Resolved this session: the corrupted-venv / `.pth` saga (fix: non-
editable + `--copies`), Spotify redirect-URI policy, `mailto:` no-op, platform
shadowing, qwen3 slowness.

### Lessons Learned

- **Match the model to the hardware, not the ambition.** A 1B instruct model that
  answers in 5s beats a 4B reasoner that stalls for two minutes on 8GB.
- **"Keyless-first" avoids setup sagas.** Every capability that dodged OAuth (Gmail
  web compose, YouTube scrape, local brain) shipped and worked immediately; the one
  OAuth flow (Spotify) cost the most support back-and-forth.
- **Verify installed entry points from another directory.** cwd on the path masked
  a broken install repeatedly.
- **Registration order IS the router.** With a keyword engine, skill order and
  keyword specificity are the whole routing logic — test regressions guard it.

### Next Session — resume here

- **Current milestone:** C6 (proactive brief) — `docs/CHECKPOINTS.md`.
- **First task:** an `origami brief` command + a daily trigger in `origami monitor`
  that summarizes today's reminders, goal progress, and priorities (reuse Scheduler
  + GoalBook + brain). Then a macOS login-item installer so `origami monitor`
  auto-starts. **Sanity first:** `cd origami-robot`; if `origami` errors on import,
  `make venv`. After editing source, `make reinstall`. Keep ONE Ollama model loaded.

---

## Session 005 — 2026-08-07

### Session Summary

Productivity polish + a new core engine. Filled UX gaps (daily brief, auto-generated
help, codebase cleanup), made GitHub *reason* over repos instead of listing them, and
built the **Project Health Engine** — a self-auditing engine that keeps ORIGAMI
architecturally clean for its whole life. Suite grew 113 → 130, all green.

### Completed Work

- **GitHub analysis**: `github.analyze` feeds the repo table (name/language/description)
  to the local brain — "best project", "my javascript projects", "which repo to polish"
  now get reasoned answers (~8s), not a raw dump. Robust routing: specific actions
  first, `github.repos` as catch-all (0 mismatches in audit).
- **Productivity polish**: `brief.today` (streak + reminders + goals + codebases at a
  glance, instant/no model), auto-generated `origami help`, `code.forget` cleanup,
  clean codebase names from project aliases.
- **Project Health Engine** (`engines/health/`): AST-based architecture/structure/
  quality/docs/dependency/capability/integration/scalability analysis with severity
  scoring, capability health cards, and a simulated future-integration matrix.
  Exposed via `health.check` / `health.audit` / `health.capabilities`.
- **Perf/robustness earlier in the session**: hard 60s model timeout (no infinite
  waits), 3× faster code scans (47s → 14s), scan structure persisted before the model
  call so a timeout never loses work.

### Important Decisions

- **The Health Engine only recommends — never edits.** *Why:* an engine that could
  rewrite core would itself become an architectural risk. Observation-only keeps it
  safe to run continuously and honest as a referee. It also imports no project code
  (pure AST), so analysis can never disturb a running ORIGAMI.
- **False positives are worse than no engine.** *Why:* the first run scored Integration
  38% by flagging dormant scaffold (`skills/coding`, `skills/robot`) as "broken
  capabilities" and stdlib/optional imports as undeclared deps. Fixed to treat empty
  placeholders as `info` and to whitelist stdlib + lazily-imported optional deps.
  Score went 87.6% → 96.6% with *no code change* — the difference was analyzer honesty.
- **Source-repo detection.** *Why:* run from the installed console script, the engine
  analysed site-packages (no tests/) and reported a hollow 82.8%. Now resolves
  $ORIGAMI_ROOT → cwd → module, and warns when it isn't analysing a real checkout.
- **Capability = skill.** *Why:* ORIGAMI's plug-in unit is a skill; scoring each on
  contract/registration/tests/docs/size gives a per-capability health card that maps
  directly to the "can it plug in?" question.

### Current Architecture

Unchanged in shape — the Health Engine is a *new engine*, not a core change; it reads
the repo and reports. It confirms the founding law still holds: **architecture 100%,
integration 100%** — core imports no concrete capability, and all six simulated future
integrations (new capability, CodeLens, Study, Vision, Robotics, external plugins) can
plug in through the registry/Skill contract without touching core.

### Current Project Status

- **Version:** `v0.4.0` tagged; well ahead of it on main.
- **Health:** 97.4% overall (architecture 100 · integration 100 · quality 100 ·
  dependencies 100 · performance 100 · docs 94 · scalability 94 · structure 91).
- **Scale:** 17 capabilities · 52 tools · 130 tests green.
- **Branch:** `main`, clean, pushed.

### Remaining Tasks (priority order)

1. Act on the engine's own findings: split `engines/health/analyzers.py` (489 lines),
   add module docstrings, delete `skills/{coding,robot}` empty scaffold.
2. **Routing upgrade** — the engine flags keyword routing as collision-prone at 17
   capabilities (we have hit this repeatedly). Plan an intent classifier before ~50.
3. Streaming output (perceived speed); CareerLens/CodeLens API skills; the build/debug
   phase (autonomous coding); C6 proactive brief automation.

### Blockers

None. GitHub CI failures earlier were GitHub-side ("Failed to resolve action download
info" / "Service Unavailable"), not project failures — re-run when Actions is healthy.

### Lessons Learned

- **A self-auditing tool must be calibrated before it is trusted.** The first run's
  score was wrong in both directions; tuning the analyzers (not the code) fixed it.
- **The engine caught its own author's mistakes** — flagged `analyzers.py` as oversized
  and predicted the routing-collision problem we had been fixing by hand all session.
  That is the strongest evidence it is measuring something real.
- **Installed vs source matters for any self-analysis tool** — resolve the target
  explicitly rather than assuming the module's location.

### Next Session — resume here

- **Current module:** `engines/health/` (act on its findings) or routing.
- **First task:** either (a) split `engines/health/analyzers.py` into
  `architecture.py` / `structure.py` / `capabilities.py`, or (b) start the intent
  classifier to replace keyword routing. Run `origami "health check"` first — it is
  now the fastest way to see what needs attention. **Sanity:** `cd origami-robot`;
  `make reinstall` after source edits; keep ONE Ollama model loaded.
