# ORIGAMI

**A developer operating system.** One interface that understands your projects,
automates your workflow, coordinates AI models and tools, and gets better at how
*you* build software — running free, all day, on your own machine.

Not a chatbot with integrations. The single app you open in the morning, where
GitHub, the terminal, the browser, Spotify, your calendar, and the AI models
themselves are all **tools** that Origami coordinates.

---

## The one idea

Every capability Origami will ever have reduces to the same primitive:

```
   goal (plain English)  →  PLANNER  →  picks TOOLS  →  EXECUTOR  →  result
                              ▲            (registry)      │
                              └──── memory + context ──────┘
                    (optionally triggered by an event, not just by you)
```

So we don't build 100 features. We build **one engine**, and every feature —
"build authentication", "continue CareerLens", "review this like a staff
engineer", "play some lofi" — becomes a *tool* or a *workflow* plugged into an
unchanged core. Add a capability = add one file. Never touch `core/`.

That single property is the whole project. Get it right and Origami grows for
years; get it wrong (a growing `if command == ...` ladder) and it rots in months.

---

## How it runs — free, all day, coding-first

A **two-speed brain** so unlimited daily use costs $0 at the margin:

| Work | Runs on | Cost |
|------|---------|------|
| Planning, routing, chat, small edits, memory (the frequent 90%) | **Local model** (Qwen2.5-Coder via Ollama on your M1) | $0, unlimited, offline |
| Hard coding — build, refactor, test, review (the 10%) | **Claude Code** (your flat Max subscription) | $0 per request |
| Overflow, optional | Free API tiers (Gemini/Groq) | $0, rate-limited |

Claude Code is **optional** — the project runs fully on the local model alone,
or even with no model at all (`EchoEngine`) for tests. The local model is the
only thing worth installing. Details: [`docs/RUNNING_FREE.md`](docs/RUNNING_FREE.md).

---

## The five layers

```
Layer 1  Surfaces   CLI · API  (later: dashboard, voice, mobile)
Layer 2  Brain      Planner · Executor · Memory · Context · Router
Layer 3  Agents     Developer · (later) Career · Research · Automation …
Layer 4  Tools      Coding(Claude Code) · Terminal · GitHub · Spotify · Calendar · Browser
Layer 5  Models     Local (Ollama) · Claude Code · free tiers · Echo
```

Data flows down, control flows up. A surface makes a `Goal`; the orchestrator
plans and executes; tools call adapters; results and events flow back up.

---

## Status (honest)

- **Built:** the adapter layer (Layer 4 plumbing) — real Spotify, GitHub,
  Terminal, Browser, Calendar, Desktop clients (~300–360 lines each), plus the
  event bus (`core/events.py`) and the skill base class.
- **Empty:** the entire brain (Layer 2), agents (Layer 3), models (Layer 5), and
  surfaces (Layer 1). 231 of 249 files are placeholders. **It does not run yet.**
- **Next:** build the thin spine through all five layers (see the roadmap).

You have working power tools and no robot arm to hold them. The plan builds the
arm.

---

## Quickstart (once the spine exists — Phases 0–1)

```bash
# free local brain (the one thing to install)
brew install ollama && ollama serve &
ollama pull qwen2.5-coder:7b          # :14b if you have 16GB

# the project
pip install -e .
origami "play some lofi"              # proves the engine end-to-end
```

No API key needed — runs on the local model, or on `EchoEngine` offline.

---

## The plan (read in this order)

| Doc | What it answers |
|-----|-----------------|
| [`docs/VISION.md`](docs/VISION.md) | **What** we're building and why — the one idea + full capability catalog |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | **How** — the spine, every core contract, mapped to the repo |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | **In what order** — phased vertical slices with hard exit criteria |
| [`docs/RUNNING_FREE.md`](docs/RUNNING_FREE.md) | **On what brain** — local + Claude Code, $0 at the margin |
| [`docs/STRUCTURE.md`](docs/STRUCTURE.md) | **Where everything goes** — annotated file tree + prepare checklist |

---

## The one rule

> Measure progress by **runnable capabilities, never file count.** A capability is
> done when its slice runs end-to-end and its test is green. Adding the next one
> must not touch `core/`.
