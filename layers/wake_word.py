"""Layer 1: Wake Word Detection using energy detection + Whisper.

Continuously monitors audio for the wake phrase "Hey Jarvis".
Uses simple RMS energy to detect speech presence, then faster-whisper
to transcribe and check if the spoken phrase matches the wake word.
"""

import collections
import difflib
import queue
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from utils.logger import setup_logger
from utils.audio import get_device_sample_rate, resample_audio, TARGET_SAMPLE_RATE

logger = setup_logger("baba.wake_word")

WAKE_PHRASE = "hey jarvis"

# Audio parameters
CHUNK_MS = 100              # 100ms chunks — short enough to catch brief words
ENERGY_THRESHOLD = 0.015    # RMS energy threshold to consider "not silence"
SPEECH_CHUNKS_NEEDED = 3    # need 3 active chunks (~300ms) to trigger capture
SILENCE_CHUNKS_TO_END = 6   # 600ms of silence after speech → end capture
MAX_CAPTURE_SECONDS = 3.0   # max capture duration for a wake word attempt


class WakeWordDetector:
    """Listens for 'Hey Jarvis' wake word using energy detection + Whisper."""

    def __init__(self, sensitivity: float = 0.5, **kwargs):
        self.sensitivity = sensitivity
        self._whisper = None

    def _load_models(self):
        """Lazy-load whisper model — tiny.en is sufficient for wake word detection."""
        if self._whisper is None:
            logger.info("Loading wake word whisper model (tiny.en)")
            self._whisper = WhisperModel("tiny.en", device="cpu", compute_type="int8")
            logger.info("Whisper model loaded")

    @staticmethod
    def _rms(audio: np.ndarray) -> float:
        """Compute RMS energy of audio chunk."""
        return float(np.sqrt(np.mean(audio ** 2)))

    def _matches_wake_word(self, text: str) -> bool:
        """Check if transcribed text contains 'hey jarvis'."""
        text_lower = text.lower().strip()
        if not text_lower:
            return False

        clean = text_lower.replace(",", " ").replace(".", " ").replace("!", " ").replace("?", " ").replace("'", "")

        # Direct match
        if "hey jarvis" in clean or "jarvis" in clean:
            return True

        # Known Whisper variants of "jarvis"
        variants = [
            "hey jarvis", "hey jarves", "hey jervis", "hey travis",
            "hay jarvis", "a jarvis", "hey jarvas", "hey jarvus",
        ]
        for v in variants:
            if v in clean:
                logger.info(f"Variant match: '{v}' in '{text}'")
                return True

        # Word-level checks
        words = clean.split()

        # Any word close to "jarvis"
        for word in words:
            ratio = difflib.SequenceMatcher(None, word, "jarvis").ratio()
            if ratio >= 0.65:
                logger.info(f"Fuzzy match: '{word}' ~ 'jarvis' (ratio={ratio:.2f})")
                return True

        return False

    @staticmethod
    def _extract_trailing(text: str) -> str:
        """Extract meaningful text after the wake word phrase.

        Returns empty string if only the wake word was said (no real command).
        """
        import re
        # Remove "hey <jarvis-variant>" and any variant that fuzzy-matched
        # Use a broad pattern that catches common Whisper mishearings
        cleaned = re.sub(
            r"^(hey[,.]?\s*)?("
            r"jarvis|jarves|jervis|travis|jairis|jarvas|jarvus|jarvis's"
            r")[,.\s!?']*",
            "", text, flags=re.IGNORECASE
        ).strip()
        # If what remains is too short or just punctuation, treat as no trailing text
        words = [w for w in cleaned.split() if len(w) > 1 or w.isalpha()]
        if len(words) < 2:
            return ""
        return cleaned

    def listen(self) -> dict:
        """Block until wake word is detected.

        Returns:
            dict: {"event": "wake_word_detected", "confidence": float}
        """
        self._load_models()

        device_sr = get_device_sample_rate()
        chunk_frames = int(device_sr * CHUNK_MS / 1000)

        audio_queue = queue.Queue()

        def _callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio status: {status}")
            audio_queue.put(indata[:, 0].copy() if indata.ndim > 1 else indata.flatten().copy())

        logger.info(f"Listening for wake word '{WAKE_PHRASE}'...")

        stream = sd.InputStream(
            samplerate=device_sr,
            channels=1,
            dtype="float32",
            blocksize=chunk_frames,
            callback=_callback,
        )
        stream.start()

        try:
            state = "IDLE"
            speech_chunk_count = 0
            silence_chunk_count = 0
            capture_chunks = []
            capture_start = 0.0
            pre_buffer = collections.deque(maxlen=5)

            while True:
                try:
                    data = audio_queue.get(timeout=2.0)
                except queue.Empty:
                    continue

                chunk_16k = resample_audio(data, device_sr)
                energy = self._rms(chunk_16k)

                if state == "IDLE":
                    pre_buffer.append(chunk_16k)
                    if energy > ENERGY_THRESHOLD:
                        speech_chunk_count += 1
                    else:
                        speech_chunk_count = 0

                    if speech_chunk_count >= SPEECH_CHUNKS_NEEDED:
                        state = "CAPTURING"
                        capture_chunks = list(pre_buffer)
                        capture_start = time.time()
                        silence_chunk_count = 0
                        logger.info("Speech detected, capturing...")

                elif state == "CAPTURING":
                    capture_chunks.append(chunk_16k)

                    if energy > ENERGY_THRESHOLD:
                        silence_chunk_count = 0
                    else:
                        silence_chunk_count += 1

                    elapsed = time.time() - capture_start

                    if silence_chunk_count >= SILENCE_CHUNKS_TO_END or elapsed > MAX_CAPTURE_SECONDS:
                        full_audio = np.concatenate(capture_chunks)
                        duration = len(full_audio) / TARGET_SAMPLE_RATE
                        logger.info(f"Captured {duration:.1f}s, transcribing...")

                        segments, _ = self._whisper.transcribe(
                            full_audio, beam_size=1, language="en", vad_filter=True,
                        )
                        text = " ".join(seg.text.strip() for seg in segments).strip()

                        if text:
                            logger.info(f"Heard: '{text}'")

                        if self._matches_wake_word(text):
                            logger.info(f"Wake word detected! Heard: '{text}'")
                            while not audio_queue.empty():
                                try:
                                    audio_queue.get_nowait()
                                except queue.Empty:
                                    break
                            # Extract trailing text after wake word
                            trailing = self._extract_trailing(text)
                            return {
                                "event": "wake_word_detected",
                                "confidence": 1.0,
                                "trailing_text": trailing,
                            }
                        else:
                            if text:
                                logger.info(f"Not wake word, ignoring: '{text}'")

                        state = "IDLE"
                        speech_chunk_count = 0
                        silence_chunk_count = 0
                        capture_chunks = []
                        pre_buffer.clear()

        except KeyboardInterrupt:
            logger.info("Wake word listening interrupted")
            raise
        finally:
            stream.stop()
            stream.close()

    def stop(self):
        """Stop listening (no-op, stream is managed in listen())."""
        pass
