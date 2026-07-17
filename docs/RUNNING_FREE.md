# ORIGAMI — Running It Free, All Day, Coding-First

Your constraints, made concrete:

- **No per-use cost.** Running Origami 500 times a day must cost the same as
  running it once: $0 at the margin.
- **All-day use.** It should be usable continuously without hitting a paywall or
  a hard rate limit on the *frequent* operations.
- **Coding-first.** The priority is building software — Origami should generate,
  refactor, test, and review code as well as possible.
- **"Train it" to be yours.** It should get better at *your* projects and *your*
  style over time.
- **Your setup:** MacBook M1 + Claude Pro/Max subscription.

This document is the money/inference layer. It sits under `VISION.md`,
`ARCHITECTURE.md`, and `ROADMAP.md` and does not change any of the contracts in
them — it only decides *which brain* runs behind the `LLMEngine` interface.

---

## 1. The core idea: a two-speed brain

The mistake that costs money is using one big paid model for everything. The fix
is to route work by how hard it is:

```
                        GOAL
                          │
                    ┌─────▼─────┐
                    │  ROUTER   │   picks the cheapest brain that can do the job
                    └─────┬─────┘
        ┌─────────────────┼──────────────────────┐
        ▼                 ▼                       ▼
   LOCAL MODEL       CLAUDE CODE              FREE API TIER
   (Ollama, M1)      (your Max sub)           (Gemini/Groq, optional)
   $0, unlimited     flat-rate, not/req       $0, rate-limited
   ─────────────     ─────────────            ─────────────
   • planning        • build a feature        • overflow when local
   • tool routing    • big refactor             is busy/too weak and
   • chat / Q&A      • write test suite         you don't want to spend
   • memory summaries• review a PR              a Claude Code turn
   • small edits     • debug hard bugs
   • classify intent • generate a project
```

**Rule of thumb the router follows:**
- High-frequency, low-stakes, short → **local** (free, unlimited).
- Low-frequency, high-stakes, long-context coding → **Claude Code** (your flat sub).
- Local unavailable / too weak and you'd rather not spend a Claude Code turn →
  **free API tier** (optional).

Because 90%+ of an all-day session is the high-frequency stuff (planning,
routing, "what's next", small edits, summarizing), the vast majority of calls
never leave your Mac. Claude Code is spent deliberately, on the hard 10%.

---

## 2. How this maps onto the architecture (no contract changes)

From `ARCHITECTURE.md §4`, the `LLMEngine` interface already abstracts the brain.
We add providers and one router — nothing above them changes.

```
engines/llm/
  base.py                     # LLMEngine ABC + LLMResponse  (already planned)
  router.py                   # RouterEngine(LLMEngine): picks a sub-engine per call
  providers/
    echo.py                   # EchoEngine    — tests / offline CI ($0)
    local.py                  # LocalEngine   — Ollama on M1 ($0, unlimited)  ← DEFAULT
    gemini.py                 # free-tier fallback (optional)
    groq.py                   # free-tier fallback (optional)
```

Claude Code is **not** an `LLMEngine`. It's too powerful and stateful to be "the
brain" — it *is* a coding agent. So it lives where it belongs: as a **tool** in
the registry.

```
skills/claude_code/skill.py   # ClaudeCodeSkill — wraps the `claude` CLI headless mode
                              # tools: code.build, code.refactor, code.test, code.review
                              # confirm=True, read_only=False  (it writes files!)
```

This is elegant: the **local model plans**, and when the plan needs real code
written, it selects the `code.build` tool, which drives Claude Code. The router
governs the *thinking*; the registry governs the *doing*. Both stay free at the
margin.

---

## 3. The local brain: what to run on an M1

Install once:

```bash
brew install ollama          # or download from ollama.com
ollama serve                 # background daemon; runs all day, no rate limit
```

Pick the coding model by your RAM (check with `sysctl hw.memsize` →
bytes; ÷ 1073741824 = GB, or  → About This Mac):

| M1 RAM | Default coding model | Pull command | Notes |
|--------|----------------------|--------------|-------|
| **16 GB** | Qwen2.5-Coder 14B (q4) | `ollama pull qwen2.5-coder:14b` | Strong local codegen; the sweet spot. |
| **8 GB** | Qwen2.5-Coder 7B (q4) | `ollama pull qwen2.5-coder:7b` | Great for planning/routing/small edits; lean on Claude Code for big work. |
| any | tiny router model | `ollama pull qwen2.5:3b` | Optional ultra-fast model just for intent/routing. |

Why Qwen2.5-Coder: as of your setup it's the best open coding model in these
sizes, Apple-Silicon-friendly via Ollama's Metal backend, and Apache-licensed.
DeepSeek-Coder-V2-Lite or Codestral are fine alternatives — swap the model
string, nothing else changes.

`LocalEngine` is a thin HTTP client to `http://localhost:11434/api/chat`. Because
it's local, there is **no token budget and no rate limit** — this is what makes
"use it all day, as many times as possible" true.

---

## 4. The heavy brain: Claude Code as a tool (your Max sub)

You already pay a **flat** Max subscription — that is not per-use cost, which is
exactly what you asked to avoid. Origami calls Claude Code in headless mode so it
becomes an automatable coding tool:

```python
# skills/claude_code/skill.py  (sketch)
# Drives:  claude -p "<prompt>" --output-format json   (headless / print mode)
# in the target repo's working directory, then reports what changed.
class ClaudeCodeSkill(Skill):
    name = "claude_code"
    @classmethod
    def specs(cls):
        return [
          ToolSpec("code.build",    "Implement a feature end-to-end in the repo",
                   {...}, confirm=True, read_only=False),
          ToolSpec("code.refactor", "Refactor a module safely",
                   {...}, confirm=True, read_only=False),
          ToolSpec("code.test",     "Write/run tests for a target",
                   {...}, confirm=True, read_only=False),
          ToolSpec("code.review",   "Staff-engineer review of a diff/PR",
                   {...}, confirm=False, read_only=True),
        ]
```

Governance so you never "burn" the subscription accidentally:
- Claude Code tools are `confirm=True` for anything that writes — Origami shows
  you the plan and waits for "yes".
- The router only escalates to Claude Code when the local model flags the task as
  *hard* or *high-stakes* (big diff, unfamiliar codebase, security-sensitive).
- Everything else — the constant chatter of an all-day session — stays local.

> Note on limits: Claude Code under Pro/Max has generous but not literally
> infinite usage windows. The two-speed design means you spend those windows on
> the 10% of work that actually needs Claude-grade coding, and never on routing
> or "what should I do next" — so in practice you rarely hit them.

---

## 5. "Train it to be mine" — what that actually means (free)

You will not fine-tune a model on day one, and you don't need to. For a solo
project, **personalization = structured memory + a feedback loop**, and it's all
free and local. Three layers, in order of value:

1. **Preference & style memory** (`engines/memory`, from ROADMAP Phase 4).
   Every time you correct Origami — "use the repository pattern", "Tailwind not
   CSS modules", "prefer FastAPI", "tabs bug me" — it stores a `preference`
   record. These are injected into every planner/coder prompt. This is 80% of
   what makes it feel like *yours*, and it works with any model.

2. **Learning-from-failures** (capability from `VISION.md`). Every bug you fix
   becomes a searchable `bug` record: symptom → root cause → fix. Before writing
   new code, Origami retrieves relevant past lessons. The system literally gets
   better at *your* recurring mistakes over time — no training run required.

3. **Project memory** ("Continue \<project\>"). Purpose, architecture, decisions,
   done/pending/next. So Origami never re-asks what your project is.

Optional, much later, and still free: **LoRA fine-tuning** of the local model on
your accumulated sessions (your code style, your commit messages, your Q&A). This
is a Phase-6+ luxury, runnable on the M1 with small adapters or offloaded to a
free Colab/Kaggle GPU. Do **not** start here — memory gets you 90% of the benefit
for 5% of the effort.

---

## 6. Coding-first reprioritization

You said prioritize coding. The `ROADMAP.md` proves the engine with "play music"
(fastest, safest slice), then immediately pivots the priority to the dev OS. The
adjusted emphasis:

| Order | Slice | Brain used | Why |
|-------|-------|-----------|-----|
| Phase 0 | package it | — | must install/import |
| Phase 1 | "play music" (proof) | LocalEngine (or Echo in CI) | smallest proof the 5-layer engine works; throwaway domain |
| **Phase 1.5** | **wire LocalEngine as default** | LocalEngine | make the free brain real before building coding on top |
| **Phase 2** | **Claude Code tool + terminal + git** | Local plans → Claude Code builds | **the coding core — your actual daily driver** |
| Phase 3 | real planning + first agent | Router | smarter tool selection |
| Phase 4 | project memory ("Continue X") | Local + memory | personalization / "training" |
| Phase 5 | proactive workflows | Router | context-aware coding help |

So the *first thing you actually use daily* arrives at Phase 2: describe a coding
task in plain English → local model plans it → Claude Code writes it → tests run
in the terminal → you approve → committed. All free at the margin.

---

## 7. Daily-driver loop (what "using it all day" looks like)

```
You:     origami "add JWT auth to the careerlens backend"
Local:   plans → [code.review repo, code.build auth, terminal.run pytest]
Origami: "Plan: 1) scan repo  2) Claude Code implements auth  3) run tests.
          Step 2 writes files — proceed? [y/N]"
You:     y
ClaudeCode: implements across files (flat sub, $0/req)
Terminal:   runs pytest, streams output (local, $0)
Local:      summarizes the diff + test results, stores a project-memory update
Origami: "Done. 6 files changed, 12 tests pass. Stored decision: JWT + Redis
          session cache. Draft PR? [y/N]"
```

Every step except the one Claude Code call is free and unlimited. That one call
is covered by the subscription you already pay. Run this loop 40 times a day and
your marginal cost is still $0.

---

## 8. Setup checklist (once)

```bash
# 1. Local brain
brew install ollama
ollama serve &
ollama pull qwen2.5-coder:7b        # or :14b if you have 16GB

# 2. Claude Code (you already have the sub)
#    ensure the `claude` CLI is installed and logged in
claude --version

# 3. Origami env (.env)
#    ANTHROPIC_API_KEY not required if using Claude Code via CLI/subscription
#    OLLAMA_HOST=http://localhost:11434
#    ORIGAMI_LLM=local            # default brain
#    ORIGAMI_CODE_TOOL=claude_code # heavy coding

# 4. (optional) free fallback tiers
#    GEMINI_API_KEY=...   GROQ_API_KEY=...
```

`configs/environments/dev.yaml` selects `local` as the default engine and
`claude_code` as the code tool, so the whole system boots into free-mode by
default.

---

## 9. Cost summary

| Operation | Frequency | Runs on | Marginal cost |
|-----------|-----------|---------|---------------|
| Intent / routing | constant | local | $0 |
| Planning | very high | local | $0 |
| Chat / explain / Q&A | high | local | $0 |
| Small edits, summaries | high | local | $0 |
| Memory store/retrieve | constant | local (JSON) | $0 |
| Build / refactor / test-gen | occasional | Claude Code | $0/req (flat sub) |
| Overflow reasoning | rare | free API tier | $0 (rate-limited) |
| **Total to run all day** | | | **$0 at the margin** |

The only money involved is the Max subscription you already have. Nothing in
Origami adds per-use cost. That is the design goal, met.
