# ORIGAMI — Completion Checklist

The project is **done in checkpoints, not in features.** Each checkpoint is a git
tag on `main`, cut only when every box under it is checked. This file is the
scoreboard — the single source of truth for what to build next.

> **North star:** `docs/PURPOSE.md` — the 5-stage evolution ending in a humanoid
> robot. The checkpoints below execute **Stages 1–3**. The robot endgame stands.

---

## Rules of the game

1. **One checkpoint at a time.** Never start C(n+1) with C(n) unchecked.
2. **A box is checked only by a command you actually ran** — never "should work."
3. **Vertical slices only.** Never create an empty folder for a future feature.
   *(249 folders / 231 empty files is the lesson this project already learned.)*
4. **Every checkpoint ships one keyless test** that passes in CI with no API keys.
5. **Tag the moment a checkpoint closes:** `git tag vX.Y.0 && git push --tags`.
6. **Robot trees stay parked, never deleted** — Stage 5 is the destination.
7. If a checkpoint stalls > 2 sessions, **shrink its scope** — never skip criteria.
8. **The 5-ability law** (`PURPOSE.md`): every feature must improve Understand,
   Plan, Execute, Remember, or Monitor — else it does not belong in Core.

## Cost & hardware reality (8 GB M1 Air)

| Brain | Cost | Use |
|-------|------|-----|
| **EchoEngine** | $0 forever, no keys, no install | **Default.** Handles all command-style tasks |
| Local 3B model (Ollama) | $0, offline | Optional — light reasoning; 7B strains 8 GB |
| Claude Code | $0/request (existing sub) | Optional accelerator only — never required |

**No checkpoint below requires a paid API key.**

---

## The ladder

| CP | Tag | You can then… | Stage |
|----|-----|---------------|-------|
| **C0** ✅ | `v0.1.0` | install & import the project | — |
| **C1** ⭐ | `v0.2.0` | run one free command end-to-end + 3-tier permissions | 1 |
| **C2** | `v0.3.0` | real actions: play music, open apps, run commands | 1 |
| **C3** ⭐ | `v0.4.0` | send messages with preview → approve (email first) | 1–2 |
| **C4** | `v0.5.0` | remember projects, people, preferences | 2 |
| **C5** ⭐ | `v0.6.0` | **Goal Mode** — the differentiator | 2–3 |
| **C6** | `v0.7.0` | proactive morning brief | 3 |

⭐ = the three that matter most. **C1** proves the architecture, **C3** makes it
do your real tasks, **C5** is what makes ORIGAMI different from an automation script.

*Optional parallel track:* the coding core (Claude Code) — useful for dogfooding
ORIGAMI to build ORIGAMI, but **not required** by any checkpoint above.

---

## C0 — Package installs (`v0.1.0`) ✅ 2026-07-17

- [x] `pip install -e ".[dev]"` succeeds (Python 3.11 venv)
- [x] `import core, skills, adapters, engines, agents, interfaces, storage` clean
- [x] `pytest` collects with zero import errors
- [x] broken `agents/conversation/agent.py` deleted
- [x] stdlib `platform` not shadowed (robot tree excluded from packaging)
- [x] CI workflows run keyless (test + advisory lint)

---

## C1 — The spine + 3-tier permissions (`v0.2.0`) ⭐

**Goal:** `origami "play some lofi"` flows through every layer with zero keys.
Build in this order — each file is small.

**Schemas & core contracts**
- [ ] `core/schemas/goal.py` — `Goal(text, source, context, session_id)`
- [ ] `core/schemas/tool.py` — `ToolSpec(name, description, params, risk)` with the
      **`Risk` enum below**
- [ ] `core/schemas/plan.py` — `Step`, `Plan`
- [ ] `core/schemas/result.py` — `StepResult`, `RunResult`
- [ ] `core/exceptions.py` — small `OrigamiError` hierarchy

**The permission model (bake in now — expensive to retrofit)**
```python
class Risk(str, Enum):
    SAFE     = "safe"      # 🟢 auto: reads, open app, play music, search
    CONFIRM  = "confirm"   # 🟡 affects others: send message/email, schedule meeting
    CRITICAL = "critical"  # 🔴 explicit approval: delete, money, mass-send,
                           #    force push, robot movement
```

**The keystone**
- [ ] `skills/registry.py` — `ToolRegistry`, global `registry`, `@tool` decorator
      (self-registration; **no `if/elif` on intent anywhere in `core/`**)
- [ ] `skills/base.py` — extend existing `Skill` with `specs()` + `execute(tool, **kw)`

**The brain (free tier)**
- [ ] `engines/reasoning/llm.py` — `LLMEngine` ABC + `LLMResponse`
- [ ] `engines/reasoning/providers/echo.py` — `EchoEngine`, keyword match, keyless

**The spine**
- [ ] `core/planner.py` — Goal → Plan (engine + keyword fallback)
- [ ] `core/executor.py` — run steps; **enforce Risk**: SAFE auto-runs, CONFIRM
      prompts, CRITICAL demands typed approval; publish to existing `event_bus`.
      Include a **verification hook** after each step (trivial in C1: did the tool
      return success?) — the lifecycle's Verification stage, grown later
- [ ] `core/orchestrator.py` + `session.py` + `context.py`

**First skill + surface**
- [ ] `skills/spotify/skill.py` — wrap existing `adapters/spotify/client.py`
      (`spotify.search_and_play` = SAFE). **Wrap, don't reimplement.**
- [ ] `interfaces/cli/main.py` + root `main.py` composition root
- [ ] `tests/e2e/test_user_journey_basic.py` — fake Spotify client + EchoEngine

**Exit criteria — all must pass**
- [ ] `origami "play some lofi"` returns a summary with **no keys at all**
- [ ] `pytest` green in CI, keyless
- [ ] a `CRITICAL` test tool **refuses** to run without explicit approval
- [ ] **the architecture test:** adding a 2nd Spotify tool touches **zero** `core/` files
- [ ] tag `v0.2.0`

> If that last box fails, the abstraction is wrong. **Stop and fix it before C2.**

---

## C2 — Real actions (`v0.3.0`)

- [ ] `skills/terminal/skill.py` wrapping `adapters/terminal/` → `terminal.run` (CONFIRM)
- [ ] `skills/desktop/skill.py` wrapping `adapters/desktop/mac.py` → open apps (SAFE)
- [ ] Spotify credentials configured → real playback works
- [ ] `configs/skills/*.yaml` per-skill config loading
- [ ] `tests/integration/test_skill_execution.py` — registry + all three risk tiers
- [ ] verify live: `origami "play lofi"` plays music; `origami "open Terminal"` works
- [ ] tag `v0.3.0`

---

## C3 — Messaging with preview → approve (`v0.4.0`) ⭐

Email first: most useful, most reliable, free API (OAuth login, no paid key).

- [ ] `adapters/email/client.py` — Gmail API
- [ ] `skills/email/skill.py` — `email.draft` (SAFE) + `email.send` (**CONFIRM**)
- [ ] **preview contract:** draft and send are always *separate steps, never fused* —
      the executor renders the full message and waits
- [ ] `tests/integration/test_message_preview.py` — asserts send **cannot** fire
      without approval (keyless, fake client)
- [ ] verify live: `origami "email my professor I'll submit tomorrow"` → shows
      draft → you approve → sends
- [ ] tag `v0.4.0`

*Deferred to later, same pattern:* WhatsApp (UI-automation only — brittle, account
risk, keep strictly CONFIRM) and Slack.

---

## C4 — Memory (`v0.5.0`)

- [ ] `engines/memory/engine.py` — `MemoryEngine` ABC + JSON-backed impl
- [ ] `long_term.py` (projects, decisions, people, preferences) + `short_term.py`
- [ ] `retrieval.py` — relevance-ranked, keyword first (embeddings later)
- [ ] orchestrator records every run; planner reads memory for context
- [ ] `tests/integration/test_memory_retrieval.py`
- [ ] verify: `origami "continue <project>"` resumes with correct context
- [ ] tag `v0.5.0`

---

## C5 — Goal Mode (`v0.6.0`) ⭐ the differentiator

You state *what you want*, not *how*. Needs C4 memory underneath.

- [ ] `core/schemas/goal_state.py` — long-running goal: milestones, deadlines, progress
- [ ] `skills/goals/skill.py` — `goal.create` / `goal.status` / `goal.next_steps`
- [ ] planner decomposes a goal into **tracked milestones**, not one-shot steps
- [ ] progress persists across sessions via memory
- [ ] `tests/integration/test_goal_mode.py`
- [ ] verify: `origami "help me get a Google internship"` creates a tracked goal;
      days later `origami "goal status"` reports progress + next actions
- [ ] tag `v0.6.0`

---

## C6 — Proactive morning brief (`v0.7.0`)

- [ ] scheduler/trigger built on the existing `core/events.py` event bus
- [ ] `origami brief` — calendar + email summary + goal progress + today's priorities
- [ ] every consequence still passes the risk gate
- [ ] tag `v0.7.0`

---

## Definition of success — when to tag `v1.0.0`

ORIGAMI succeeds when it is your default way of working, not a demo:

- [ ] **Used daily:** 14 consecutive days routing ≥1 real task through `origami`
- [ ] **Free:** $0 recurring cost across those days (no paid API keys)
- [ ] **Trustworthy:** zero incidents of a CONFIRM/CRITICAL action firing without approval
- [ ] **Extensible in practice:** ≥3 skills added after C2, none touching `core/`
- [ ] **Goal-driven:** Goal Mode actively tracking ≥1 real long-term goal

If a criterion is failing, **that failure — not new features — is the next work item.**

---

## Session ritual

- **Start:** open `origami-robot/` in VS Code (CLAUDE.md autoloads) → read
  `docs/PURPOSE.md` if direction feels fuzzy → open this file → take the top
  unchecked box of the current checkpoint.
- **During:** vertical slices only. Keyless test first. Adapters are already built —
  wrap them, don't rewrite them.
- **End:** check the boxes you earned, commit (`C<n>: <what>`), push. Tag if the
  checkpoint closed. **Never end a session with red tests on `main`.**
