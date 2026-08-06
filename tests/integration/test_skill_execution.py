"""Integration test — the terminal skill and the CONFIRM gate end-to-end.

Proves: terminal.run is CONFIRM-gated (won't run until approved), runs when
approved, and routes through the full orchestrator with the keyword planner.
Keyless — uses a fake executor, no real commands run.
"""

from __future__ import annotations

from core.schemas.goal import Goal
from core.schemas.tool import Risk
from main import build_orchestrator


class FakeExecutor:
    """Stand-in for adapters.terminal.executor.TerminalExecutor."""

    def __init__(self):
        self.ran = None

    def run(self, command):
        self.ran = command
        return _Result(command)


class _Result:
    def __init__(self, command):
        self.command = command
        self.returncode = 0
        self.output = f"ran: {command}"

    @property
    def success(self):
        return True


async def _approve(spec, step):
    return True


async def _decline(spec, step):
    return False


async def test_terminal_run_is_confirm_gated_and_declined_by_default():
    fake = FakeExecutor()
    # no confirmer -> executor denies all consequences by default
    orch = build_orchestrator(terminal_executor=fake)
    result = await orch.handle(Goal(text="run echo hello"))

    assert fake.ran is None                      # command never executed
    assert result.steps[0].skipped               # it was gated, not run
    assert not result.success


async def test_terminal_run_executes_when_approved():
    fake = FakeExecutor()
    orch = build_orchestrator(terminal_executor=fake, confirmer=_approve)
    result = await orch.handle(Goal(text="run echo hello"))

    assert fake.ran == "echo hello"              # command preserved (case + text)
    assert result.success
    assert "echo hello" in result.summary


async def test_terminal_tool_declares_confirm_risk():
    orch = build_orchestrator(terminal_executor=FakeExecutor())
    # planner should route "run ..." to terminal.run, which is CONFIRM
    plan = await orch.planner.plan(Goal(text="run ls -la"))
    assert plan.steps[0].tool == "terminal.run"
    spec = orch.executor.registry.get("terminal.run")
    assert spec.risk is Risk.CONFIRM


async def test_play_still_routes_to_spotify_not_terminal():
    # regression: adding terminal must not steal music goals
    orch = build_orchestrator(terminal_executor=FakeExecutor())
    plan = await orch.planner.plan(Goal(text="play some lofi"))
    assert plan.steps[0].tool == "spotify.search_and_play"


class FakeDesktop:
    def __init__(self):
        self.opened = self.closed = self.url = self.volume = None
        self.muted = self.locked = False

    def open_application(self, app_name):
        self.opened = app_name

    def quit_application(self, app_name):
        self.closed = app_name

    def open_url(self, url, browser="Safari"):
        self.url = url

    def set_volume(self, level):
        self.volume = level

    def mute(self):
        self.muted = True

    def unmute(self):
        self.muted = False

    def take_screenshot(self, output_path=None, window=False):
        return output_path or "/tmp/shot.png"

    def lock_screen(self):
        self.locked = True

    def get_clipboard(self):
        return "clipboard contents"


async def test_desktop_mac_controls():
    from skills.desktop.skill import DesktopSkill
    fake = FakeDesktop()
    skill = DesktopSkill(adapter=fake)

    assert "40" in await skill.execute("desktop.set_volume", level="to 40")
    assert fake.volume == 40
    await skill.execute("desktop.mute")
    assert fake.muted is True
    await skill.execute("desktop.lock")
    assert fake.locked is True
    assert "png" in (await skill.execute("desktop.screenshot")).lower()
    assert "clipboard" in await skill.execute("desktop.clipboard")
    await skill.execute("desktop.open_url", url="reddit.com")
    assert fake.url == "https://reddit.com"  # scheme added


async def test_open_domain_opens_url_not_app():
    from skills.desktop.skill import DesktopSkill
    fake = FakeDesktop()
    await DesktopSkill(adapter=fake).execute("desktop.open_app", app="github.com")
    assert fake.url == "https://github.com" and fake.opened is None


async def test_open_real_app_still_opens_app():
    from skills.desktop.skill import DesktopSkill
    fake = FakeDesktop()
    await DesktopSkill(adapter=fake).execute("desktop.open_app", app="Safari")
    assert fake.opened == "Safari" and fake.url is None


async def test_open_bare_name_falls_back_to_website():
    from skills.desktop.skill import DesktopSkill

    class Raising(FakeDesktop):
        def open_application(self, app_name):
            raise RuntimeError("Unable to find application")

    fake = Raising()
    msg = await DesktopSkill(adapter=fake).execute("desktop.open_app", app="reddit")
    assert fake.url == "https://reddit.com" and "reddit.com" in msg


async def test_open_app_is_safe_and_runs_without_confirm():
    fake = FakeDesktop()
    # no confirmer at all -> a SAFE tool must still run (no consequence)
    orch = build_orchestrator(desktop_adapter=fake, terminal_executor=FakeExecutor())
    result = await orch.handle(Goal(text="open Safari"))

    assert fake.opened == "Safari"
    assert result.success
    assert result.steps[0].step.tool == "desktop.open_app"
    assert result.steps[0].verified


async def test_open_app_declares_safe_risk():
    orch = build_orchestrator(desktop_adapter=FakeDesktop(), terminal_executor=FakeExecutor())
    assert orch.executor.registry.get("desktop.open_app").risk is Risk.SAFE


async def test_close_app_quits_application():
    fake = FakeDesktop()
    orch = build_orchestrator(desktop_adapter=fake, terminal_executor=FakeExecutor())
    result = await orch.handle(Goal(text="close Safari"))
    assert fake.closed == "Safari"
    assert result.success
    assert result.steps[0].step.tool == "desktop.close_app"


# ---------------------------------------------------------------- YouTube skill

async def test_youtube_routing():
    orch = build_orchestrator(terminal_executor=FakeExecutor())
    plan = await orch.planner.plan(Goal(text="youtube lofi hip hop"))
    assert plan.steps[0].tool == "youtube.play"
    assert plan.steps[0].args.get("query") == "lofi hip hop"


async def test_youtube_opens_top_video_keyless():
    from skills.youtube.skill import YouTubeSkill

    opened = {}
    fake_html = 'garbage...{"videoId":"dQw4w9WgXcQ"}...more'

    skill = YouTubeSkill(
        opener=lambda url: opened.__setitem__("url", url),
        http_get=lambda url: fake_html,
    )
    msg = await skill.execute("youtube.play", query="never gonna give you up")

    assert opened["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert "Playing on YouTube" in msg


async def test_youtube_falls_back_to_search_when_no_video():
    from skills.youtube.skill import YouTubeSkill

    opened = {}
    skill = YouTubeSkill(
        opener=lambda url: opened.__setitem__("url", url),
        http_get=lambda url: "no video ids here",
    )
    msg = await skill.execute("youtube.play", query="xyz")
    assert "results?search_query=" in opened["url"]
    assert "search" in msg.lower()


# ------------------------------------------------------------------ email skill

async def test_email_routing():
    orch = build_orchestrator(terminal_executor=FakeExecutor())
    plan = await orch.planner.plan(
        Goal(text="prepare a draft mail to psrisaicharan5@gmail.com to study hard")
    )
    assert plan.steps[0].tool == "email.draft"


async def test_email_draft_builds_gmail_compose_with_recipient_and_body():
    from skills.email.skill import EmailSkill

    opened = {}
    skill = EmailSkill(opener=lambda url: opened.__setitem__("url", url))
    msg = await skill.execute("email.draft", text="to psrisaicharan5@gmail.com to study hard")

    url = opened["url"]
    assert url.startswith("https://mail.google.com/mail/?view=cm")
    assert "psrisaicharan5%40gmail.com" in url   # recipient, URL-encoded
    assert "study%20hard" in url                 # body, URL-encoded
    assert "psrisaicharan5@gmail.com" in msg


async def test_email_draft_without_address_is_graceful():
    from skills.email.skill import EmailSkill

    skill = EmailSkill(opener=lambda url: None)
    msg = await skill.execute("email.draft", text="just some words no address")
    assert "couldn't find" in msg.lower()


# ------------------------------------------------------- thinking (Brain) skills

from engines.reasoning.llm import LLMEngine, LLMResponse, Task  # noqa: E402


class FakeBrain(LLMEngine):
    """A brain that 'thinks' with predictable output (subclasses the interface so
    it also provides keyword `plan()` for routing tests)."""

    name = "fakebrain"

    def __init__(self, thinks=True):
        self._thinks = thinks

    def can_think(self) -> bool:
        return self._thinks

    async def complete(self, prompt, task=Task.REASON, **kwargs) -> LLMResponse:
        return LLMResponse(text="ok", model="fake")

    async def generate(self, instruction, **kwargs) -> str:
        return f"Subject: Re: your request\nHi,\n\nHere is {instruction}.\n\nThanks."

    async def reason(self, prompt, **kwargs) -> str:
        return f"ANSWER about {prompt}"


async def test_assistant_write_uses_the_brain():
    from skills.assistant.skill import AssistantSkill
    out = await AssistantSkill(FakeBrain(thinks=True)).execute(
        "assistant.write", prompt="an essay about origami")
    assert "an essay about origami" in out


async def test_assistant_points_to_ollama_when_no_model():
    from skills.assistant.skill import AssistantSkill
    out = await AssistantSkill(FakeBrain(thinks=False)).execute("assistant.ask", prompt="hi")
    assert "ollama" in out.lower()


async def test_write_routes_to_assistant():
    orch = build_orchestrator(terminal_executor=FakeExecutor(), brain=FakeBrain())
    plan = await orch.planner.plan(Goal(text="write a haiku about the sea"))
    assert plan.steps[0].tool == "assistant.write"


async def test_email_body_is_composed_by_brain_when_available():
    from skills.email.skill import EmailSkill
    opened = {}
    skill = EmailSkill(opener=lambda url: opened.__setitem__("url", url), brain=FakeBrain(True))
    await skill.execute("email.draft", text="to prof@uni.edu an essay about my project")
    url = opened["url"]
    assert "su=Re%3A%20your%20request" in url        # subject from the model
    assert "Here%20is" in url                          # body composed by the model


async def test_email_falls_back_to_literal_without_brain():
    from skills.email.skill import EmailSkill
    opened = {}
    skill = EmailSkill(opener=lambda url: opened.__setitem__("url", url))  # no brain
    await skill.execute("email.draft", text="to prof@uni.edu study hard")
    assert "study%20hard" in opened["url"]
