# ORIGAMI — Roadmap

The plan is a sequence of **vertical slices**. Each phase produces something that
*runs* and adds one proven capability of the engine. No phase is "scaffolding."
A phase is done only when its **exit criteria** pass.

> Read `ARCHITECTURE.md` for the contracts referenced below, and
> `RUNNING_FREE.md` for the free/local + Claude Code brain that these phases run
> on (M1 + Claude Max, $0 at the margin).

**Coding-first note:** Phase 1 proves the engine with the safe "play music"
slice, but your daily driver is the **Phase 2 coding core** (local model plans →
Claude Code builds → terminal runs tests). Phase 1.5 wires the local brain in
between. See `RUNNING_FREE.md §6` for the reprioritized emphasis.

Legend: 🎯 goal · ✅ exit criteria · 📦 deliverables

---

## Phase 0 — Make it a real, runnable package (½ day)

🎯 Turn the folder into something that installs and imports without errors.

📦
- Fill `pyproject.toml` (name `origami`, deps: `fastapi`, `uvicorn`, `requests`,
  `pydantic`, `pytest`, `pytest-asyncio`; optional: `anthropic`/`openai`,
  `playwright`).
- Fill `requirements.txt` / `requirements-dev.txt`.
- Minimal `README.md`: what it is + `pip install -e .` + how to run the CLI.
- **Delete** `agents/conversation/agent.py` (broken import) — it returns in Phase 3.
- Add `.env.example` (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `ANTHROPIC_API_KEY`).

✅ `pip install -e .` succeeds · `python -c "import core, skills, adapters"` runs
clean · `pytest` collects 0 tests without import errors.

---

## Phase 1 — The spine + first vertical: "play music" (2–3 days) ⭐

🎯 One command flows through all five layers and plays music. **This is the
proof that the architecture works.** Ship it with `EchoEngine` so it runs with no
LLM key.

**End-to-end path:**
```
$ origami "play some lofi"
  CLI → Goal
      → Orchestrator.handle
          → Planner.plan        (EchoEngine keyword-picks spotify.search_and_play)
          → Executor.run        (confirm skipped: read/no-consequence)
              → registry.call("spotify.search_and_play", query="lofi")
                  → SpotifySkill → SpotifyClient.search_and_play()  [existing adapter]
              → event_bus.publish(SKILL_EXECUTED)
          → memory.store(run)
      ← "▶ Playing: Lofi Girl — beats to relax/study to"
```

📦 files to create (in this order):
1. `core/schemas/{goal,tool,plan,result}.py` — the dataclasses from ARCHITECTURE §2.
2. `skills/base.py` — extend `Skill` with `specs()` + `execute(tool, **kw)`.
3. `skills/registry.py` — `ToolRegistry`, global `registry`, `@tool` decorator.
4. `engines/llm/base.py` + `engines/llm/providers/echo.py` — interface + `EchoEngine`.
5. `engines/memory/base.py` + `engines/memory/json_store.py` — `JSONMemory`.
6. `core/planner.py` — LLM plan + keyword fallback.
7. `core/executor.py` — run steps, confirm gate, publish events.
8. `core/orchestrator.py`, `core/session.py`, `core/context.py` — wire + state.
9. `skills/spotify/skill.py` — wrap the **existing** `SpotifyClient`. Exposes
   `spotify.search_and_play`, `spotify.pause`, `spotify.next_track`,
   `spotify.previous_track` (all map to methods already in `adapters/spotify/client.py`).
10. `interfaces/cli/main.py` — arg → `Goal` → orchestrator → print summary.
11. `main.py` — `build_orchestrator()` composition root.
12. `tests/test_slice_play_music.py` — drives the orchestrator with a **fake**
    Spotify client, asserts the right tool was called with `query="lofi"`.

✅ **Exit criteria (all must pass):**
- `origami "play some lofi"` runs end-to-end and returns a summary.
- With a real Spotify token + active device, music actually plays.
- With **no** API keys, the slice still runs against the fake client (EchoEngine
  + injected fake) — proves the pipeline independent of external services.
- `pytest tests/test_slice_play_music.py` is green in CI.
- Adding a second Spotify tool required **zero** edits to `core/`.

> The last bullet is the real test of the whole project. If adding a tool touched
> the core, the architecture failed and we fix it before Phase 2.

---

## Phase 1.5 — Wire the free local brain (½–1 day)

🎯 Make the default brain real and free *before* building coding on top of it.
See `RUNNING_FREE.md` for full setup.

📦
- `engines/llm/providers/local.py` → `LocalEngine` (HTTP client to Ollama at
  `localhost:11434`). Model: `qwen2.5-coder:7b` (8GB) or `:14b` (16GB).
- `engines/llm/router.py` → `RouterEngine` (local default; free-tier overflow
  optional). Same `LLMEngine` interface — planner/agents unchanged.
- `configs/environments/dev.yaml` selects `local` as the default engine.

✅ `origami "..."` plans using the local model, offline, with no API key and no
rate limit · `EchoEngine` remains the CI default · swapping `local`↔`echo` is a
one-line config change.

---

## Phase 2 — The coding core: local plans → Claude Code builds (3–5 days) ⭐ your daily driver

🎯 The capability you'll actually use all day. Local model plans; **Claude Code**
(your flat Max sub, $0/request) does the heavy code; the terminal runs it; git
tracks it. All free at the margin. No `core/` changes — proves the registry
extends.

📦
- `skills/claude_code/skill.py` → wraps the `claude` CLI headless mode
  (`claude -p ... --output-format json`) in the target repo. Tools:
  `code.build`, `code.refactor`, `code.test` (**`confirm=True`, `read_only=False`**),
  `code.review` (read-only). See `RUNNING_FREE.md §4`.
- `skills/terminal/skill.py` wrapping `adapters/terminal/executor.py` →
  `terminal.run` (**`confirm=True`, `read_only=False`** — first confirmation-gate
  use for a raw command).
- `skills/github/skill.py` wrapping `adapters/github/client.py` →
  `github.list_prs` (`→ list_pull_requests`), `github.list_issues` (read-only).
- The router escalates only *hard/high-stakes* coding to Claude Code; everything
  else stays local (`RUNNING_FREE.md §1`).
- CLI gains an interactive REPL (`origami` with no args).

✅ `origami "add JWT auth to the backend"` runs the full loop from
`RUNNING_FREE.md §7`: plan (local) → build (Claude Code, confirmed) → test
(terminal) → summary + memory update · write actions ask before touching files ·
`core/` diff for this phase is empty except the composition root's import list ·
a full day of use costs $0 at the margin.

---

## Phase 3 — A brain worth having: real LLM + first agent (3–5 days)

🎯 Swap `EchoEngine` for a real provider; planning becomes genuinely smart;
introduce the first domain agent.

📦
- `engines/llm/providers/anthropic.py` (and/or `openai.py`) behind the same
  interface; provider chosen by config; `EchoEngine` stays the CI default.
- Planner upgraded to real tool-selection + multi-step plans (interface unchanged).
- Rebuild `agents/conversation/agent.py` **on the finished spine** as the first
  real `Agent` (uses `LLMEngine` + `MemoryEngine`, both now real).
- Prompt files in `agents/conversation/prompts.py` (no more `open().read()` hacks).

✅ `"play something chill then tell me what's playing"` produces a 2-step plan and
executes both · CI still runs keyless via EchoEngine · agent answers a
non-tool question conversationally.

---

## Phase 4 — Memory that pays off: "Continue <project>" (4–6 days)

🎯 The differentiator. Structured project memory that makes Origami feel like it
*knows your work*.

📦
- `core/schemas/memory.py` → `ProjectMemory` (purpose, architecture, done,
  pending, bugs, decisions, next milestone).
- `engines/memory/json_store.py` → project CRUD + `get_project(name)`.
- `skills/project/skill.py` → `project.status`, `project.continue`.
- Seed it from the real state of *this* repo as the first stored project.

✅ `origami "continue origami"` returns current phase, remaining work, and a
proposed next step drawn from stored memory — not re-derived each time.

---

## Phase 5 — Proactive seam: event-driven workflows (5–7 days)

🎯 Flip from reactive to proactive using the `event_bus` that already exists.
This is capability #24 and #23 — the thing that makes Origami feel alive.

📦
- Workflow definitions in plain config: `on <event> do <tools>`.
- A daemon surface (`interfaces/api` background task) that subscribes to events
  and runs workflows through the same orchestrator.
- First workflows: "deployment failed → fetch + summarize logs";
  "GitHub PR opened → summarize the diff."

✅ An emitted event triggers a workflow with zero user input, routed through the
unchanged orchestrator/executor/confirm path.

---

## After the spine (backlog, each = "add a skill")

Once Phases 0–5 hold, every remaining capability from `VISION.md` is an
extension, not a rewrite. Rough value/effort ordering:

| Next up | Why early | Shape |
|---------|-----------|-------|
| Daily executive brief (#12/#14) | high daily value, reuses GitHub+Calendar+memory | read-only skill + schedule |
| Calendar skill | wraps existing `adapters/calendar` | read + confirm-on-write |
| Resume / career subsystem | high personal ROI, one source of truth in memory | memory-heavy skill |
| Browser automation skill | wraps existing `adapters/browser` | confirm-on-action |
| Bug detective, AI CTO review | pure dev-OS payoff | multi-tool agents |
| Voice surface | input method, not core | new surface only |
| Plugin marketplace (#18) | already latent in the import-to-register design | packaging + config |

---

## How to work this plan

- **One phase at a time. One commit per phase minimum.** No starting Phase N+1
  until Phase N's exit criteria are green.
- **Never touch `core/` to add a capability** after Phase 1. If you must, the
  abstraction is wrong — fix the abstraction, not the symptom.
- **Every phase ships a test** that runs keyless in CI via `EchoEngine` + fakes.
- **Delete aggressively.** Empty placeholder files that a phase doesn't need can
  wait; broken files (like the current conversation agent) get removed, not kept.
- Measure progress by **runnable capabilities**, never by file count. 231 empty
  files taught us that lesson already.

---

## Appendix — repo reality check (verified against current code)

Confirmed so the plan matches what's actually on disk:

- **Directories that must be created** (do not exist yet): `engines/llm/`,
  `engines/llm/providers/`, `skills/terminal/`, `skills/project/`. Existing and
  reusable: `engines/memory/`, `skills/spotify/`, `skills/github/`,
  `skills/calendar/`, `interfaces/cli/`, `interfaces/api/`, `core/schemas/`,
  `tests/`.
- **Spotify adapter** (`adapters/spotify/client.py`) already exposes exactly the
  methods Phase 1 needs: `search_and_play(query, track_type)`, `play()`,
  `pause()`, `next_track()`, `previous_track()`, `get_current_track()`. The
  SpotifySkill is a thin wrapper — no adapter changes.
- **GitHub adapter** method names for Phase 2: the tool `github.list_prs` maps to
  `GitHubClient.list_pull_requests(...)`; `github.list_issues` → `list_issues(...)`.
  Write tools later map to `create_issue`, `create_pull_request`,
  `trigger_workflow` (all `confirm=True`).
- **Terminal adapter**: the class is `TerminalExecutor` with `run(...)`,
  `run_checked(...)`, `run_async(...)`. `terminal.run` wraps `run` and is the
  first `confirm=True, read_only=False` tool.
- **`core/schemas/`** already has empty `event.py`, `memory.py`, `skill.py`,
  `task.py`, `user.py`. Phase 1 adds `goal.py`, `tool.py`, `plan.py`, `result.py`
  alongside them.
- **`core/events.py`** already provides `EventBus`, global `event_bus`, and
  `EventTypes.SKILL_EXECUTED` / `SKILL_FAILED` — the executor uses these as-is.

---

## Definition of "the perfect project"

Origami is on track when a stranger can read `VISION.md`, run `origami "play some
lofi"` from a clean clone, and then add a brand-new capability by writing a single
`skills/<x>/skill.py` file without opening `core/`. When that is true, the
architecture is proven and everything else is just time.
