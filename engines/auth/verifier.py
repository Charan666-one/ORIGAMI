"""Speaker verification — "is this the enrolled voice?"

Local and privacy-first: audio becomes a small numeric embedding and the raw
audio is discarded. Nothing leaves the machine.

`SpectralVerifier` is the default and needs only numpy — it computes MFCC
statistics (the classic timbre fingerprint). It is genuinely useful for telling
the owner from a different person, but it is NOT strong security: it can be
fooled by a recording of your voice (replay attack) and by close voice matches.
Treat it as a convenience gate. `ResemblyzerVerifier` (optional install) is more
accurate and drops in through the same interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

SAMPLE_RATE = 16000


class SpeakerVerifier(ABC):
    name = "base"
    #: cosine similarity above which a voice counts as the enrolled speaker
    default_threshold: float = 0.80
    #: True only for verifiers actually able to tell speakers apart reliably.
    #: The engine refuses to gate personal/sensitive levels on a weak verifier.
    reliable: bool = True

    @abstractmethod
    def embed(self, audio) -> List[float]:
        """Audio (float32 mono 16k) -> fixed-length voice embedding."""

    def is_available(self) -> bool:
        return True

    def install_hint(self) -> str:
        return ""

    @staticmethod
    def similarity(a: List[float], b: List[float]) -> float:
        import numpy as np
        x, y = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
        if x.size == 0 or y.size == 0 or x.size != y.size:
            return 0.0
        denom = float(np.linalg.norm(x) * np.linalg.norm(y))
        if denom == 0:
            return 0.0
        return float(np.dot(x, y) / denom)


class SpectralVerifier(SpeakerVerifier):
    """MFCC-mean embedding, numpy only — always available, but NOT reliable.

    Measured on this codebase (3 synthetic voices × 3 phrases): same-speaker
    similarity ranged 0.924–0.99 while different-speaker reached 0.984, i.e. the
    distributions overlap and no threshold separates them (best case ≈22% false
    accepts and ≈22% false rejects). It is therefore marked `reliable = False`:
    it can report a similarity score, but the engine will not gate personal or
    sensitive actions on it. Install `resemblyzer` for real verification.
    """

    name = "spectral-mfcc"
    default_threshold = 0.93
    reliable = False

    def __init__(self, n_mfcc: int = 20, n_mels: int = 40) -> None:
        self.n_mfcc = n_mfcc
        self.n_mels = n_mels

    # --- mel helpers --------------------------------------------------------

    @staticmethod
    def _hz_to_mel(f):
        import numpy as np
        return 2595.0 * np.log10(1.0 + f / 700.0)

    @staticmethod
    def _mel_to_hz(m):
        import numpy as np
        return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    def _filterbank(self, n_fft: int, sr: int):
        import numpy as np
        low, high = self._hz_to_mel(20.0), self._hz_to_mel(sr / 2)
        points = self._mel_to_hz(np.linspace(low, high, self.n_mels + 2))
        bins = np.floor((n_fft + 1) * points / sr).astype(int)
        fb = np.zeros((self.n_mels, n_fft // 2 + 1))
        for i in range(1, self.n_mels + 1):
            left, centre, right = bins[i - 1], bins[i], bins[i + 1]
            if centre == left:
                centre = left + 1
            if right <= centre:
                right = centre + 1
            right = min(right, fb.shape[1] - 1)
            if centre >= fb.shape[1]:
                break
            fb[i - 1, left:centre] = np.linspace(0, 1, max(1, centre - left))
            fb[i - 1, centre:right] = np.linspace(1, 0, max(1, right - centre))
        return fb

    # --- embedding ----------------------------------------------------------

    def embed(self, audio) -> List[float]:
        import numpy as np
        x = np.asarray(audio, dtype=np.float32).flatten()
        if x.size < SAMPLE_RATE // 2:          # need ~0.5s of speech
            return []

        # keep only voiced frames — silence carries no identity
        frame, hop = 400, 160                   # 25ms / 10ms @16k
        n_frames = 1 + (len(x) - frame) // hop
        if n_frames < 8:
            return []
        frames = np.lib.stride_tricks.as_strided(
            x, shape=(n_frames, frame),
            strides=(x.strides[0] * hop, x.strides[0])).copy()
        energy = np.abs(frames).mean(axis=1)
        voiced = frames[energy > max(1e-4, energy.mean() * 0.35)]
        if len(voiced) < 8:
            voiced = frames

        window = np.hamming(frame)
        spec = np.abs(np.fft.rfft(voiced * window, n=512)) ** 2
        fb = self._filterbank(512, SAMPLE_RATE)
        mel = np.log(np.maximum(spec @ fb.T, 1e-10))

        # DCT-II -> MFCC
        k = np.arange(self.n_mfcc)[:, None]
        n = np.arange(self.n_mels)[None, :]
        dct = np.cos(np.pi * k * (2 * n + 1) / (2 * self.n_mels))
        mfcc = mel @ dct.T                       # (frames, n_mfcc)

        # NOTE: deliberately *no* cepstral mean normalisation — it removes the
        # average timbre, which is precisely the speaker signal (measured: it
        # collapsed the same/imposter margin to +0.003). c0 (loudness) is dropped.
        emb = mfcc[:, 1:].mean(axis=0)
        norm = np.linalg.norm(emb)
        return (emb / norm).tolist() if norm else emb.tolist()


class ResemblyzerVerifier(SpeakerVerifier):
    """Neural speaker embedding (GE2E encoder) — the real verifier.

        pip install resemblyzer

    Threshold 0.75 is the encoder's conventional same-speaker cut-off; tune it
    with `origami "auth status"` after enrolling.

    Honesty note: this was NOT validated on this machine, because the only audio
    available for testing was synthetic `say` speech, which the encoder is not
    trained on (that test was inconclusive: gap -0.185). Validate it with your own
    voice after enrolment — and remember any voice check is replay-attackable.
    """

    name = "resemblyzer"
    default_threshold = 0.75
    reliable = True

    def __init__(self) -> None:
        self._encoder = None

    def is_available(self) -> bool:
        try:
            import resemblyzer  # noqa: F401
            return True
        except Exception:
            return False

    def install_hint(self) -> str:
        return "pip install resemblyzer"

    def embed(self, audio) -> List[float]:
        import numpy as np
        from resemblyzer import VoiceEncoder, preprocess_wav
        if self._encoder is None:
            self._encoder = VoiceEncoder()
        wav = preprocess_wav(np.asarray(audio, dtype=np.float32), source_sr=SAMPLE_RATE)
        return self._encoder.embed_utterance(wav).tolist()


def best_verifier() -> SpeakerVerifier:
    """Prefer the neural verifier when installed; always fall back to numpy."""
    for v in (ResemblyzerVerifier(), SpectralVerifier()):
        if v.is_available():
            return v
    return SpectralVerifier()
