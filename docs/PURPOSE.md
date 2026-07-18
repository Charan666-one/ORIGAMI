# ORIGAMI — Original Purpose & North Star

> **This is the authoritative statement of why ORIGAMI exists.** It is the
> user's original vision, preserved verbatim in intent. When any decision,
> roadmap, or refactor seems to drift, come back here first. The other docs
> (`VISION.md`, `ROADMAP.md`, `CHECKPOINTS.md`) describe *how* and *in what
> order* we build — **this describes the destination and must not be diluted.**

---

## What ORIGAMI is

**ORIGAMI — Omnipresent Robotic General Artificial Modular Intelligence.**

A modular AI **operating system** — not a chatbot — that acts as a true personal
AI assistant across **software and physical robotics**. It must evolve from a
desktop AI assistant into a fully autonomous humanoid robot **without a major
architectural redesign**. Every part is built as reusable, independent modules
with clearly defined interfaces, so the same planning, memory, and reasoning
engines carry from software all the way to the robot.

The architecture prioritizes **scalability over shortcuts**.

## The need it solves

Today's assistants (Siri, Alexa, Google, plain chatbots) all fail the same way:

- they forget conversations,
- they hold no long-term context,
- they can't reliably perform complex multi-step tasks,
- they integrate poorly with the local operating system,
- they can't coordinate multiple specialized agents,
- they can't evolve naturally into robotics.

ORIGAMI answers these with **persistent memory, modular reasoning, tool
orchestration, and hardware abstraction.**

## The long-term objective

A personal AI companion that can understand spoken language, see through cameras,
listen continuously, keep long-term memory, plan goals independently, execute
software tasks, learn preferences, control devices, navigate physical spaces, and
ultimately operate as a humanoid robot. The software architecture must support
**every stage** of this evolution.

---

## The 5-stage evolution (the endgame is Stage 5 — the robot)

| Stage | Becomes | Core capabilities |
|-------|---------|-------------------|
| **1** | Desktop AI Assistant | conversation · memory · files · browser · terminal · GitHub · calendar · email · Spotify · notifications |
| **2** | Personal Productivity Agent | task planning · goals · scheduling · research · coding · project & knowledge mgmt · context persistence |
| **3** | Multi-Agent Intelligence | conversation / planning / research / coding / memory / vision / navigation / voice agents collaborating via a shared orchestration layer |
| **4** | Local AI Operating System | desktop control · app launching · workflow automation · keyboard/mouse · file indexing · secure command execution |
| **5** | Robotics Platform | sensor fusion · camera · motor control · navigation · environment understanding · autonomous humanoid |

The robotics layer **reuses** the planning, reasoning, and memory engines built
in the earlier stages. That reuse is the whole point — nothing built for the
desktop assistant is thrown away on the road to the robot.

---

## The 8-layer architecture (maps 1:1 onto the repo directories)

| Layer | Directory | Responsibility |
|-------|-----------|----------------|
| Interfaces | `interfaces/` | how users interact — CLI, web, desktop, mobile, voice, robot |
| Core | `core/` | orchestration only — event bus, scheduler, session, config, state. **Never business logic.** |
| Agents | `agents/` | reasoning — each agent solves one type of problem. **Agents decide.** |
| Engines | `engines/` | reusable intelligence — memory, reasoning, planning, voice, vision, navigation, knowledge |
| Skills | `skills/` | actions — calendar, Spotify, GitHub, terminal, robot. **Skills execute, never reason.** |
| Adapters | `adapters/` | isolate external systems — GitHub API, Google, Spotify, desktop, browser, robot hardware |
| Storage | `storage/` | persistence — SQLite/Postgres/Redis, vectors, logs, history. **No business logic.** |
| Platform | `platform/` | hardware-specific — Mac, Windows, Linux, ESP32, Raspberry Pi, robot controllers, simulators |

**Separation of duties (memorize this):** *agents decide · skills execute ·
adapters communicate · storage remembers · core coordinates.*

## Engineering principles (non-negotiable)

- Single responsibility per module.
- Business logic never depends directly on external services.
- Dependencies point inward, toward abstractions.
- Any module is replaceable without affecting unrelated components.
- Composition over inheritance. Avoid global state. Avoid tight coupling.
- Design for testing before optimization.
- **Safety gate:** dangerous actions (file deletion, shell execution, browser
  automation, sending messages, financial ops, robot movement) require explicit
  approval. Never execute destructive actions silently.
- Quality bar: type hints, logging, error handling, docs, unit tests. No
  placeholder implementations merged as if done.

## Success criteria

ORIGAMI succeeds when it is a unified AI OS that understands natural language,
remembers users and projects over long periods, coordinates multiple agents,
executes complex multi-step workflows, integrates with software **and** hardware,
and transitions seamlessly from desktop automation to physical robotics.

---

## Two guardrails so we never go sideways again

Read these before any big decision.

**1. The robot is the destination; "Developer OS" is only Stages 1–2.**
The pragmatic docs in this folder focus on a desktop coding assistant because
that is the achievable, useful slice we can ship first on real hardware. That
framing is a *starting point, not a replacement.* Robot trees
(`platform/robot`, `platform/simulator`, `engines/{vision,navigation,voice}`,
`skills/robot`) are **parked, never deleted.** The endgame stands.

**2. Build vertical slices — never scaffold empty folders.**
The original instinct "build every module first with clean interfaces" is exactly
what produced **249 folders and 231 empty files that do not run.** Honor the
architecture above, but **invert the build order:** fill one complete, working,
tested slice through all the layers before scaffolding the next capability.
**Measure progress by runnable capabilities, never by file count.**

> If a request conflicts with Guardrail 1, protect the vision. If it conflicts
> with Guardrail 2, protect the working-software discipline. Both can be true at
> once: the grand vision, built one honest slice at a time.
