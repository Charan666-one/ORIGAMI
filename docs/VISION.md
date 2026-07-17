# ORIGAMI — Vision

> A developer operating system that understands my projects, automates my
> workflow, coordinates specialized AI agents, and continuously improves how I
> build software.

Origami is not a chatbot with integrations. It is the single interface you open
in the morning. Everything else — GitHub, Spotify, Gmail, Calendar, the browser,
the terminal, Claude/GPT/local models — becomes a **tool** that Origami
coordinates.

---

## The one idea

Read every capability we want (there are 45+ of them, catalogued below) and they
all reduce to the **same primitive**:

```
        goal (natural language)
                 │
                 ▼
            PLANNER  ── reads memory + context
                 │
                 ▼
         selects TOOLS from the registry
                 │
                 ▼
            EXECUTOR  ── runs steps, asks to confirm risky ones
                 │
                 ▼
          result + new memory + events
                 ▲
                 │
     (optionally triggered proactively by an event,
      not only by you typing a command)
```

"Start backend development", "Continue CareerLens", "Review this like a Staff
Engineer", "When I star a repo, summarize it", "A deployment failed → show me
the logs" — every one is *plan → tools → memory → (event trigger)*.

**So we do not build 45 features. We build one engine, and the 45 capabilities
become configuration:** a tool, a workflow definition, or a memory schema.

This is the whole bet. If the engine is right, adding "Interview Coach" or
"Focus Mode" is a weekend of work — a new tool plugged into an unchanged core.
If the engine is wrong (e.g. a growing `if command == ...` ladder), the project
rots after a few months. We have seen that failure mode already: 249 files, 231
empty.

---

## Design principles

1. **Capabilities, not features.** Every addition should make Origami *more
   autonomous*, not just add another command. Prefer "Start backend
   development" (a workflow) over "Open VS Code" (a command).
2. **Everything is a tool.** Models, APIs, the terminal, the browser, the
   filesystem — all uniform tools behind one registry. The planner decides
   when and how to use them.
3. **Self-registration over dispatch.** Tools register themselves. The core
   never grows an `if/elif` ladder. Adding a capability = adding a file.
4. **Memory is a first-class citizen.** Structured, queryable project/skill/
   decision memory — not raw chat logs. This is the real differentiator.
5. **Confirm before consequences.** Anything that writes to an account, spends
   money, deletes, or deploys asks first. Reads are free.
6. **Reactive first, proactive next.** v1 answers commands. The event bus is the
   seam that later lets Origami act on context without being asked (#24).
7. **Vertical slices, never breadth.** One complete path working end-to-end
   beats twelve half-built modules. Prove the loop, then extend.
8. **Provider-agnostic brain.** Claude, GPT, Gemini, and local models sit behind
   one `LLMEngine` interface. Swapping models never touches agents.

---

## The five layers (target)

```
Layer 1  Surfaces     CLI · API · Dashboard · Voice · Mobile · Desktop
Layer 2  Brain        Planner · Memory · Reasoning · Task Queue · Context
Layer 3  Agents       Developer · Career · Research · Automation · Learning …
Layer 4  Tools        GitHub · Spotify · Terminal · Browser · Calendar · Docker …
Layer 5  Models       Claude · GPT · Gemini · Local · Embeddings
```

Today only Layer 4 partially exists (real Spotify/GitHub/Terminal/Browser
adapters). The plan below builds a thin slice through **all five layers** first,
then thickens each.

---

## Capability catalog (the north star, not the v1 scope)

Grouped so we can see that they share the one primitive. **None of these are v1.**
They are the backlog the architecture must make cheap to add.

### Developer OS
Personal environment orchestration ("Start backend development" → open editor,
Docker, DB, services, tabs, PR, terminal, restore workspace) · Autonomous
project manager ("Continue CareerLens" knows state, remaining work, bugs, next
milestone) · AI CTO ("review like a Staff Engineer") · AI pair programmer
(always-on reviewer) · Project generator (idea → repo, schema, issues, starter
code) · Architecture generator · Bug detective (logs → git history → deps →
config → ranked root causes) · Documentation generator · Research assistant
(decision memos) · Context engine (edit a file → know its tables, APIs, tests,
PRs) · Multi-agent collaboration (planner → dev → reviewer → tester →
documenter → deploy) · Self-improvement (weekly review of its own usage).

### Knowledge & memory
Personal knowledge graph · AI memory (projects, decisions, bugs, preferences) ·
AI librarian (summary/tags/embeddings per document) · Memory timeline
("what was I doing last Friday?") · Personal search engine across
PDFs/notes/GitHub/Drive/Downloads.

### Career
Resume intelligence (one source of truth → tailored resume + ATS + cover
letter per job) · Interview simulator (HR/DSA/DBMS/OS/networking/system design,
adapts to weak areas) · Learning engine (personalized path from what you know
and where you struggle) · Goal manager ("Google internship" → resume, DSA,
projects, referrals, applications, interviews).

### Life administration
Email triage & drafts · Calendar (free slots, briefs, summaries) · Documents
(organize Downloads, OCR, merge PDFs, extract tables, invoices) · Financial
organizer · Shopping / decision assistant · Travel assistant · Reading
assistant · News intelligence · Health · Social intelligence · Writing
assistant · Daily executive brief.

### Platform
Voice control · Computer automation · Browser automation · AI workflow builder
("when X happens, do Y, Z") · Context-aware suggestions · Plugin marketplace ·
Home lab (24/7 host, local models, backups) · Digital twin (learns how *you*
work).

> The test for anything on this list is not "is it cool?" but **"what wastes my
> time every single day?"** Origami earns its place by removing that friction.

---

## Non-goals for v1

- No breadth. v1 ships **one** vertical slice (play music) proving the full
  engine, then a second (developer workspace) proving it extends.
- No voice, no dashboard, no mobile in v1. CLI + API only.
- No multi-provider model zoo yet — one provider behind the interface.
- No vector DB / graph DB yet — memory is JSON-backed, interface-compatible with
  a later upgrade.
- No proactivity yet — the event bus exists and is wired, but v1 is
  command-driven.

See `ROADMAP.md` for how each non-goal turns on, phase by phase.
