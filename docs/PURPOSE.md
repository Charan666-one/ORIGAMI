# ORIGAMI — Original Purpose & North Star

## Omnipresent Robotic General Artificial Modular Intelligence
### The AI Operating System for Human Potential

> **This is the authoritative statement of why ORIGAMI exists.** When any
> decision, roadmap, or refactor seems to drift, come back here first. Other docs
> (`CHECKPOINTS.md`, `VISION.md`, `ROADMAP.md`) describe *how* and *in what order*
> we build — **this describes the destination and must not be diluted.**
>
> *Vision refined in Session 002 (2026-08-05) from the owner's expanded spec.
> Superseding statement of the founding vision; the 5-stage robot endgame stands.*

---

## What ORIGAMI is

ORIGAMI is **not** a chatbot, an AI wrapper, or a voice assistant. It is a
**lifelong Personal AI Operating System** — a digital extension of its user whose
purpose is to **reduce the distance between human intention and completed
execution.**

> Conversation is only one interface. **Execution is the objective.**

It begins as a software operating system and evolves, over years, into the
intelligence behind physical robotic systems. The architecture must support
**decades of growth**.

## Mission

Understand user intentions · convert them into executable plans · execute safely ·
remember everything that matters · monitor long-term goals · learn continuously ·
become more useful every single day. **The user should spend less time managing
work and more time doing meaningful work.**

---

## The Universal Lifecycle

Every request follows one lifecycle. This is the spine of the whole system:

```
Human Intention → Understanding → Reasoning → Planning → Workflow Construction
→ Capability Selection → Execution → Verification → Memory Update → Monitoring
→ Continuous Improvement
```

Note two steps the earliest drafts lacked: **Verification** (confirm the action
achieved the intent) and **Monitoring** (keep watching after the task ends).

## Fundamental Engineering Law

Every new feature must improve at least one of these **five abilities**:

1. **Understand**  2. **Plan**  3. **Execute**  4. **Remember**  5. **Monitor**

> If it improves none of them, it does **not** belong in the ORIGAMI Core.

This is the primary filter for every proposed capability, engine, or refactor.

## Design Principles (non-negotiable)

Modular · Scalable · **Offline-First** · **Provider-Independent** · Privacy-First ·
Capability-Driven · Workflow-Based · Extensible · User-Controlled ·
Long-Term-Maintainable. *No architectural decision may violate these.*

---

## The 5-stage evolution (endgame = the robot)

The software OS is only **Stage 1**. The architecture must carry through all five
without redesign:

| Stage | Becomes | Focus |
|-------|---------|-------|
| **1** | Software AI OS | understand · plan · execute · remember on the desktop |
| **2** | Executive partner | monitoring, goals, daily/weekly briefs, proactivity |
| **3** | Multi-capability intelligence | many capabilities coordinated by workflows |
| **4** | Local AI OS | full desktop/OS automation, parallel workflows |
| **5** | Robotics platform | voice · vision · robotics · smart home · IoT |

The robotics layer **reuses** the planning, memory, reasoning, and monitoring
engines built earlier. Nothing built for Stage 1 is thrown away on the road to the
robot. Robot trees in the repo are **parked, never deleted.**

---

## Architecture — layers, not agents

ORIGAMI is built around **layers**, not a loose collection of agents:

```
                 Conversation Layer
                        │
                Intent Understanding
                        │
                  Context Builder
                        │
                 Planning Engine
                        │
              Workflow Orchestrator
                        │
               Capability Registry
   ┌────────────────────┴─────────────────────┐
   Browser · Files · Terminal · Git · Email · Calendar ·
   VS Code · PDF · Research · Vision · Voice · Robotics · …
   └────────────────────┬─────────────────────┘
                 Execution Engine
                        │
               Verification Engine
                        │
                Long-Term Memory
                        │
                Knowledge Engine
                        │
                 Brain Interface
                        │
    Ollama · LM Studio · GPT · Claude · Gemini · future models
```

**Repo mapping:** conversation/intent/context → `interfaces/` + `core/context`;
planning/workflow/execution/verification → `core/{planner,executor,orchestrator}`;
capability registry → `skills/registry.py`; capabilities → `skills/*` wrapping
`adapters/*`; memory/knowledge → `engines/memory` + `engines/knowledge`; brain
interface → `engines/reasoning/llm.py` + `providers/*`.

### Intelligence Model — the model is NOT ORIGAMI

The AI model is **only the reasoning engine**. ORIGAMI owns planning, memory,
execution, monitoring, workflows, capabilities, automation, and knowledge.

> **The reasoning model is replaceable. ORIGAMI is permanent.**

### Brain Interface — provider independence

ORIGAMI must never depend on one AI provider. Every reasoning model implements one
common interface (`LLMEngine`). Ollama, LM Studio, OpenAI, Claude, Gemini, future
local models — **swapping a model requires zero architectural redesign.**

---

## Capability System

Capabilities are **independent, self-registering plugins**. They **never
communicate directly** — only the Workflow Engine coordinates them.

> **Adding a capability must never require modifying ORIGAMI Core.**

## Workflow Engine

Capabilities perform actions; **workflows combine capabilities.** Every complex
task becomes a workflow, e.g. *Apply for Internship* → search jobs → analyze
requirements → compare resume → generate cover letter → prepare forms → **await
approval** → submit → track status → remind.

## Memory · Knowledge · Monitoring · Executive Engines

- **Long-Term Memory** — projects, goals, preferences, habits, coding style,
  documents, conversations, learning & career progress, mistakes, achievements,
  work sessions. Every interaction should improve the next.
- **Knowledge Engine** — indexes personal notes, PDFs, papers, repos, docs, books.
  **Retrieve from local knowledge before calling external AI.**
- **Monitoring Engine** — continuously observes *user-approved* signals (project/
  git/learning progress, tasks, downloads, calendar, opportunities). **Transparent;
  nothing monitored without consent.**
- **Executive Engine** — turns ORIGAMI from assistant into operational partner:
  analyze progress, prioritize, detect blockers, suggest next actions, produce the
  **Daily Executive Brief** (yesterday's progress · today's priorities · blockers ·
  deadlines · opportunities · suggested next action). The user should never wonder
  *"what should I work on next?"*

---

## Permission Model (3 tiers)

Every capability declares its permission level; the Executor enforces it.

- 🟢 **SAFE** — reading, searching, opening files, summaries, local analysis.
  *Runs immediately.*
- 🟡 **CONFIRM** — emails, applications, git push, browser forms, external
  communication. *User confirmation required.*
- 🔴 **CRITICAL** — deleting files, money, robot movement, system settings, root
  commands, irreversible operations. *Explicit approval always required.*

## Offline-First

ORIGAMI must remain functional without subscriptions. Priority order:
**1. Local software → 2. Local AI → 3. Browser automation → 4. External APIs.**
Paid APIs are **enhancements, never dependencies.**

## Parallel Workflow Execution (future)

Independent workflow branches should execute simultaneously when possible (e.g.
research fan-out across docs/GitHub/YouTube/Reddit → summarize → notes → study
plan).

---

## What makes ORIGAMI different

ChatGPT answers. Claude reasons. Gemini searches. Siri runs commands.
**ORIGAMI manages objectives** — it works continuously toward long-term goals
while keeping the user in control. It does not wait for commands.

## Success Criteria

ORIGAMI succeeds if it becomes **the first application the user opens every morning
and the last one closed every night.** The goal is not an impressive AI — it is a
**lifelong operating system that amplifies human capability.**

> *ORIGAMI is not built to replace human intelligence — it is built to remove
> friction between intention and execution, so its user can think bigger while
> ORIGAMI handles the operational complexity.*

---

## Two guardrails so we never go sideways again

**1. The robot is the destination; "Software OS" is only Stage 1.**
The pragmatic focus on a desktop assistant is a *starting point, not a
replacement.* Robot trees are parked, never deleted. The endgame stands.

**2. Build vertical slices — never scaffold empty folders.**
"Build every module first" is exactly what produced **249 folders / 231 empty
files that do not run.** Honor the architecture above, but fill one complete,
working, tested slice through all layers before scaffolding the next.
**Measure progress by runnable capabilities, never by file count.**
