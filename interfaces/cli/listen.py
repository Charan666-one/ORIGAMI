"""`origami listen` — passive, always-on activation.

Say your wake phrase; if the voice is yours, ORIGAMI activates and you can keep
talking without repeating it. An unknown speaker saying the phrase is ignored in
silence.
"""

from __future__ import annotations

import sys

ICON = {"LOCKED": "🔒", "LISTENING": "👂", "WAKE_DETECTED": "❗", "VERIFYING": "🔎",
        "AUTHENTICATED": "✅", "SESSION_ACTIVE": "🟢", "SESSION_LOCKED": "🔒",
        "UNKNOWN_SPEAKER": "🚫", "DISABLED": "⏸"}


def run_listen() -> int:
    from engines.auth.engine import AuthenticationEngine
    from engines.auth.listener import PassiveListener
    from engines.auth.settings import WakeSettingsStore
    from engines.voice.engine import VoiceEngine
    from engines.voice.stt import RecognizerManager

    auth = AuthenticationEngine()
    stt = RecognizerManager()
    settings = WakeSettingsStore()
    cfg = settings.load()

    if not stt.is_available():
        print("🎙️  I need a microphone to listen.")
        print(f"   → {stt.install_hint()}")
        return 1
    if not auth.is_enrolled():
        print('🔒 No voice enrolled yet — run: origami "enroll my voice"')
        print("   (without it I can't tell your voice from anyone else's)")
        return 1

    def on_state(state: str, detail: str = "") -> None:
        sys.stderr.write(f"\r\033[K{ICON.get(state, '·')} {state.lower().replace('_', ' ')}"
                         f"{'  ' + detail[:44] if detail else ''}")
        sys.stderr.flush()

    voice = VoiceEngine(stt=stt)
    listener = PassiveListener(auth=auth, recognizer=stt, settings_store=settings,
                               voice=voice, on_state=on_state)

    print("\n👂 ORIGAMI is listening.")
    print(f'   Wake phrase : "{cfg.wake_phrase}"   (change it: '
          f'origami "change my wake phrase to ...")')
    print(f"   Verification: your enrolled voice must match "
          f"(threshold {cfg.confidence_threshold})")
    print(f"   Session     : stays open {int(cfg.session_timeout // 60)} min after "
          f"activity · say “lock” to close it")
    print("   Ctrl+C to stop listening.\n")

    try:
        listener.run()
    except KeyboardInterrupt:
        pass
    finally:
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()
    print("👋 stopped listening.")
    return 0
