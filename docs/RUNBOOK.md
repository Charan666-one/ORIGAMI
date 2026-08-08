# ORIGAMI — Runbook

Everything you need to run ORIGAMI, and the fix for every problem hit so far.
If something breaks, the answer is almost certainly on this page.

---

## Daily use

```bash
cd ~/Desktop/BOTS/ORIGAMI/origami-robot
source .venv/bin/activate       # needed once per terminal
```

| Command | What it does |
|---|---|
| `origami "<anything>"` | run a request |
| `origami help` | every capability, auto-generated from the live registry |
| `origami dashboard` | open the live UI (reuses a running server) |
| `origami voice` | spoken conversation |
| `origami monitor` | background reminders + follow-ups |
| `origami "brain status"` | model, memory, latency, runtime state |
| `origami "health check"` | architecture/quality audit of the project itself |

You never run `ollama serve` — ORIGAMI starts its own Brain.

---

## The three things that have actually broken

### 1. `origami` says `ModuleNotFoundError: interfaces`
The venv went stale (a homebrew python upgrade, or an editable-install `.pth`
that `site` stopped processing).

```bash
make venv          # rebuild with --copies + non-editable install
```

**Why non-editable:** this machine's `site` intermittently fails to process
`.pth` files, so both setuptools editable modes break the console script.
Non-editable copies the packages into `site-packages` — no `.pth` involved.
**After editing source, run `make reinstall`** so the installed copy updates.

### 2. Anything imports `platform` and explodes
A top-level `platform/` package shadows the standard library. It has been
re-added by accident three times (it broke onnxruntime).

```bash
ls platform        # must NOT exist — the robot-heritage tree is `platforms/`
```

`origami "health check"` now flags stdlib shadowing as CRITICAL, with a
regression test, so this cannot come back silently.

### 3. Answers are wrong / rambling
Almost always the model, not the plumbing. See below.

---

## The Brain (local model)

ORIGAMI manages the runtime itself: it detects Ollama, starts it detached (no
terminal), health-checks it, recovers from crashes, and downgrades to a smaller
model under memory pressure.

**Recommended on 8 GB:** `llama3.2:3b` — follows instructions reliably.
`llama3.2:1b` is faster but too weak: it ignores questions and hallucinates.

```bash
ollama pull llama3.2:3b     # install
ollama rm  llama3.2:1b      # keep ONE model loaded on 8GB — two thrash RAM
origami "brain status"      # confirm which one is in use
```

No config needed — the Brain Runtime picks the best installed model per task
tier automatically (fast / standard / code).

Useful environment overrides (all optional, in `.env`):

```
ORIGAMI_LLM_TIMEOUT=60       # hard cap per inference (seconds)
ORIGAMI_AUTOSTART_BRAIN=1    # 0 disables auto-starting the runtime
ORIGAMI_WHISPER=base.en      # speech-recognition model size
ORIGAMI_VOICE=Samantha       # macOS speech voice
ORIGAMI_CLOUD=groq           # optional cloud brain (still consent-gated)
```

---

## Voice

```bash
origami voice               # spoken session; "stop" interrupts, "goodbye" exits
origami "voice status"      # what's installed
origami "say hello"         # speak text aloud
```

macOS will ask for **microphone** permission the first time. Expect ~2–3s to
transcribe after you stop speaking, plus the model's own reply time.

---

## Identity (optional)

```bash
origami "enroll my voice"   # 3 samples -> local embedding, audio discarded
origami "auth status"
origami "lock origami"
```

Voice auth is a **convenience gate, not strong security** — it is replayable, and
terminal access bypasses it by design.

---

## Dashboard

```bash
origami dashboard           # http://127.0.0.1:8420
```

Keep it running in the background so it survives closing the terminal:

```bash
nohup .venv/bin/uvicorn interfaces.api.app:app --host 127.0.0.1 --port 8420 \
      > /tmp/origami-dash.log 2>&1 &
```

Stop it with `pkill -f "uvicorn interfaces.api.app"`.

---

## Health checks before you ask for help

```bash
pytest -q                   # should be all green
origami "health check"      # architecture/quality/integration scores
origami "brain status"      # is the model loaded and healthy?
tail -20 /tmp/origami-dash.log
```

---

## Data ORIGAMI keeps (all local, `~/.origami/`)

| File | Contents |
|---|---|
| `memory.json` | ordinary facts (expire after 12 days) |
| `memory-important.json` | important facts (never expire) |
| `profile.md` | who you are + how ORIGAMI should respond (editable) |
| `tasks.json` | reminders + streak |
| `goals.json` | long-term goals and milestones |
| `codebases.json` | learned codebases |
| `projects.json` | launcher paths + start commands (editable) |
| `identity.json` | voice embedding (0600) |
| `auth-log.json` | authentication attempts |

Delete any file to reset that feature; nothing else breaks.
