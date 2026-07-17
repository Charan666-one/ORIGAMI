# ORIGAMI — Checkpoints to Completion

The project is **done in checkpoints, not in features**. Each checkpoint is a git
tag on `main`, cut only when every box below it is checked. This file is the
scoreboard; `ROADMAP.md` holds the build details for each phase.

**Rules of the game**
1. Work on exactly one checkpoint at a time. Never start CN+1 with CN unchecked.
2. A box is checked only by a command you actually ran, not by "should work."
3. Cut the tag the moment the last box is checked: `git tag <tag> && git push --tags`.
4. If a checkpoint stalls > 2 sessions, shrink its scope — never skip its criteria.

---

## The path

| Checkpoint | Tag | You can now… | Est. effort |
|---|---|---|---|
| **C0 Package** | `v0.1.0` | install & import the project | ✅ done 2026-07-17 |
| **C1 Spine** ⭐ | `v0.2.0` | `origami "play some lofi"` end-to-end | 2–3 days |
| **C1.5 Local brain** | `v0.3.0` | plan with free local LLM, offline | ½–1 day |
| **C2 Coding core** ⭐ | `v0.4.0` | describe a coding task → Claude Code builds it | 3–5 days |
| **C3 Agent + API** | `v0.5.0` | POST /goal; smarter multi-step coding | 3–4 days |
| **C4 Project memory** | `v0.6.0` | `origami "continue CareerLens"` | 3–4 days |
| **C5 Proactive** | `v0.7.0` | event-triggered workflows (CI failed → propose fix) | 4–5 days |
| **v1.0** | `v1.0.0` | see "Definition of success" below | — |

⭐ = the two checkpoints that matter most. C1 proves the architecture;
C2 makes Origami your daily driver. Everything after C2 is compounding value.

---

## C0 — Package installs (v0.1.0) ✅ 2026-07-17

- [x] `pip install -e ".[dev]"` succeeds (Python 3.11 venv)
- [x] `import core, skills, adapters, engines, agents, interfaces, storage` clean
- [x] `pytest` collects with zero import errors
- [x] broken `agents/conversation/agent.py` deleted
- [x] stdlib `platform` not shadowed (robot tree excluded from packaging)
- [x] CI workflows run keyless (test + advisory lint)

## C1 — The spine + play music (v0.2.0) ⭐

Build order and contracts: `ROADMAP.md` Phase 1, `ARCHITECTURE.md` §2.

- [ ] `core/schemas/{goal,tool,plan,result}.py` dataclasses exist
- [ ] `skills/registry.py`: `ToolRegistry` + global `registry` + `@tool` decorator
- [ ] `engines/reasoning/`: `LLMEngine` ABC + `providers/echo.py` (EchoEngine)
- [ ] `core/{planner,executor,orchestrator}.py` wired; executor has confirm gate
- [ ] `skills/spotify/skill.py` wraps the existing adapter (no reimplementation)
- [ ] `interfaces/cli/main.py` + root `main.py` composition root
- [ ] `origami "play some lofi"` returns a summary keyless (EchoEngine + fake client)
- [ ] with real Spotify creds + active device, music actually plays
- [ ] `tests/e2e/test_user_journey_basic.py` green in CI
- [ ] **the architecture test:** adding a 2nd Spotify tool touched zero `core/` files

## C1.5 — Free local brain (v0.3.0)

- [ ] `engines/reasoning/providers/local.py` (Ollama, `qwen2.5-coder`) behind the same ABC
- [ ] `engines/reasoning/engine.py` RouterEngine; `local`↔`echo` is a one-line config change
- [ ] `origami "…"` plans offline with no API key; CI still uses EchoEngine

## C2 — Coding core (v0.4.0) ⭐ the daily driver

- [ ] `skills/coding/`: `code.build/refactor/test/review` driving `claude -p` headless
- [ ] graceful fallback: no `claude` CLI → local model (never hard-crash)
- [ ] `skills/terminal/skill.py`: `terminal.run` with `confirm=True` gate proven
- [ ] `skills/github/skill.py`: `github.list_prs/issues` (read-only, no confirm)
- [ ] full loop on a real repo: describe task → plan → build → test → confirm → summary
- [ ] `tests/integration/test_skill_execution.py` green (registry + confirm gate)
- [ ] zero `core/` edits during the entire checkpoint

## C3 — Agent + API (v0.5.0)

- [ ] real LLM provider config hardened; `agents/coding_assistant/` on the spine
- [ ] `interfaces/api/app.py`: FastAPI `POST /goal` → RunResult; health route
- [ ] conversation agent rebuilt properly (the one deleted in C0)

## C4 — Project memory (v0.6.0)

- [ ] `engines/memory/{engine,long_term,short_term,retrieval}.py` JSON-backed
- [ ] runs recorded; `origami "continue <project>"` resumes with context
- [ ] `tests/integration/test_memory_retrieval.py` green

## C5 — Proactive workflows (v0.7.0)

- [ ] event-driven triggers on `core/events.py` (e.g. CI failure → proposed fix)
- [ ] every consequence still behind the confirm gate

---

## Definition of success (when to tag v1.0.0)

Origami is *successful* when it is your default way of working, not a demo:

1. **Used daily:** for 14 consecutive days you route ≥ 1 real coding task per day
   through `origami` instead of doing it by hand.
2. **Free at the margin:** those days cost $0 in API spend (local model +
   Claude Code subscription only).
3. **Trustworthy:** zero incidents of a write/shell action executing without the
   confirm gate.
4. **Extensible in practice:** you have added ≥ 3 tools after C2 and none of
   them required editing `core/`.
5. **Resumable:** `origami "continue <project>"` picks up any of your active
   projects with correct context.

If a criterion is failing, that failure — not new features — is the next work item.

---

## Session ritual (how to work efficiently)

- **Start:** open `origami-robot/` in VS Code / Claude Code (CLAUDE.md autoloads),
  read the current checkpoint's unchecked boxes, pick the top one.
- **During:** vertical slices only; keyless test first; adapters are already
  built — wrap, don't rewrite.
- **End every session:** check boxes you earned, commit (`P<n>: <what>`), push.
  Tag if the checkpoint closed. Never end a session with red tests on `main`.
