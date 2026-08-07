"""`origami voice` — a spoken conversation with ORIGAMI.

Wake → listen → act → speak, looping until you say goodbye. Everything routes
through the normal orchestrator, so every capability is voice-reachable and
consequential actions stay gated.
"""

from __future__ import annotations

import asyncio
import sys

ICON = {"idle": "○", "listening": "🎙️ ", "thinking": "🧠", "executing": "⚡",
        "speaking": "🔊", "error": "⚠️ "}


def _banner(engine) -> None:
    s = engine.status()
    print("\n🎙️  ORIGAMI VOICE")
    print(f"   hear : {'✅ ' + (s['stt']['provider'] or '') if s['can_hear'] else '⚠️  not available'}"
          f"{'  ' + (s['stt']['model'] or '') if s['can_hear'] else ''}")
    print(f"   speak: {'✅ ' + (s['tts']['provider'] or '') if s['can_speak'] else '⚠️  not available'}")
    if not s["can_hear"]:
        print(f"   → enable hearing: {s['stt'].get('install') or 'pip install faster-whisper sounddevice'}")
        print("   (typing still works below)")
    print("   say “stop” to interrupt · “goodbye” to exit\n")


def run_voice() -> int:
    from engines.voice.engine import VoiceEngine

    def on_state(state: str, detail: str = "") -> None:
        sys.stderr.write(f"\r\033[K{ICON.get(state,'·')} {state}"
                         f"{'  ' + detail[:48] if detail else ''}")
        sys.stderr.flush()

    engine = VoiceEngine(on_state=on_state)
    _banner(engine)

    if not engine.stt.is_available():
        # graceful: speak the replies, read requests from the keyboard
        engine.say("Voice output is ready. I can't hear yet, so type to me.", wait=False)
        while True:
            try:
                text = input("you › ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text or engine.conv.is_ending(text):
                engine.say("Goodbye.")
                break
            ex = asyncio.run(engine.handle(text))
            sys.stderr.write("\r\033[K")
            print(f"origami › {ex.said or '(silent)'}")
        return 0

    try:
        asyncio.run(engine.converse())
    except KeyboardInterrupt:
        engine.stop_speaking()
    finally:
        sys.stderr.write("\r\033[K")
    print("👋 voice session ended.")
    return 0
