"""TTS Engine using Microsoft Edge Neural Voices (edge-tts).

Supports barge-in: monitors microphone during playback and stops
speaking if the user starts talking.

Includes phrase caching to eliminate network latency for common responses.
"""

import asyncio
import hashlib
import os
import queue
import subprocess
import tempfile
import threading

import numpy as np
import sounddevice as sd
import edge_tts

from utils.logger import setup_logger
from utils.audio import get_device_sample_rate

logger = setup_logger("baba.tts")

# Barge-in: if mic RMS exceeds this during playback, stop TTS
BARGEIN_ENERGY_THRESHOLD = 0.025
BARGEIN_CHUNKS_NEEDED = 3  # consecutive loud chunks to trigger barge-in
BARGEIN_CHECK_INTERVAL = 0.1  # seconds between checks

# Common phrases to pre-generate at startup
PRECACHE_PHRASES = [
    "I'm listening.",
    "Session ended. Say hey Jarvis when you need me.",
    "Jarvis is ready.",
    "Cancelled.",
    "Are you still there?",
    "Accessibility permission is missing.",
    "Done.",
    "I didn't understand that command.",
]


class TTSEngine:
    """Text-to-speech with barge-in support and phrase caching."""

    def __init__(self, voice: str = "en-US-AndrewNeural", rate: str = "+0%"):
        self.voice = voice
        self.rate = rate
        self._process = None
        self._lock = threading.Lock()
        self.barged_in = False  # set to True if user interrupted
        self._cache_dir = os.path.join(tempfile.gettempdir(), "baba_tts_cache")
        os.makedirs(self._cache_dir, exist_ok=True)
        self._cache_ready = threading.Event()
        self._precache_thread = None

    def precache(self):
        """Pre-generate audio for common phrases in background."""
        self._precache_thread = threading.Thread(
            target=self._precache_worker, daemon=True
        )
        self._precache_thread.start()

    def _precache_worker(self):
        """Generate and cache common phrases."""
        for phrase in PRECACHE_PHRASES:
            path = self._cache_path(phrase)
            if not os.path.exists(path):
                try:
                    asyncio.run(self._generate(phrase, path))
                    logger.debug(f"Cached TTS: '{phrase[:40]}'")
                except Exception as e:
                    logger.warning(f"Failed to cache '{phrase[:30]}': {e}")
        self._cache_ready.set()
        logger.info(f"TTS cache ready ({len(PRECACHE_PHRASES)} phrases)")

    def _cache_path(self, text: str) -> str:
        """Get cache file path for a phrase."""
        key = hashlib.md5(f"{self.voice}:{self.rate}:{text}".encode()).hexdigest()
        return os.path.join(self._cache_dir, f"{key}.mp3")

    def _get_cached(self, text: str) -> str | None:
        """Return cached audio path if available."""
        path = self._cache_path(text)
        if os.path.exists(path):
            return path
        return None

    def speak(self, text: str):
        """Speak text aloud asynchronously."""
        self.stop()
        self.barged_in = False
        logger.info(f"TTS: {text[:80]}{'...' if len(text) > 80 else ''}")
        threading.Thread(target=self._speak_blocking, args=(text,), daemon=True).start()

    def _speak_blocking(self, text: str):
        """Generate and play speech."""
        try:
            # Check cache first
            cached = self._get_cached(text)
            if cached:
                logger.debug("Using cached TTS audio")
                audio_path = cached
                is_temp = False
            else:
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.close()
                asyncio.run(self._generate(text, tmp.name))
                audio_path = tmp.name
                is_temp = True

            with self._lock:
                self._process = subprocess.Popen(
                    ["afplay", audio_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            self._process.wait()

            if is_temp:
                os.unlink(audio_path)
        except Exception as e:
            logger.warning(f"Edge-tts failed ({e}), falling back to macOS say")
            self._fallback_say(text)

    async def _generate(self, text: str, output_path: str):
        """Generate speech audio using edge-tts."""
        comm = edge_tts.Communicate(text, self.voice, rate=self.rate)
        await comm.save(output_path)

    def _fallback_say(self, text: str):
        """Fallback to macOS say command."""
        with self._lock:
            self._process = subprocess.Popen(
                ["say", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        self._process.wait()

    def stop(self):
        """Stop any current speech."""
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None

    def is_speaking(self) -> bool:
        """Return True if TTS is currently playing."""
        with self._lock:
            return self._process is not None and self._process.poll() is None

    def speak_sync(self, text: str):
        """Speak and block until finished. Supports barge-in for long responses."""
        self.stop()
        self.barged_in = False
        logger.info(f"TTS: {text[:80]}{'...' if len(text) > 80 else ''}")

        try:
            # Check cache first
            cached = self._get_cached(text)
            if cached:
                logger.debug("Using cached TTS audio")
                audio_path = cached
                is_temp = False
            else:
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.close()
                asyncio.run(self._generate(text, tmp.name))
                audio_path = tmp.name
                is_temp = True

                # Cache this phrase for next time
                cache_path = self._cache_path(text)
                try:
                    import shutil
                    shutil.copy2(audio_path, cache_path)
                except OSError:
                    pass

            with self._lock:
                self._process = subprocess.Popen(
                    ["afplay", audio_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            # Monitor mic for barge-in while playing
            self._monitor_bargein()

            # Cleanup temp files only
            if is_temp:
                try:
                    os.unlink(audio_path)
                except OSError:
                    pass
        except Exception as e:
            logger.warning(f"Edge-tts failed ({e}), falling back to macOS say")
            self._fallback_say(text)

    def _monitor_bargein(self):
        """Poll mic energy while TTS plays. Stop TTS if user speaks."""
        device_sr = get_device_sample_rate()
        chunk_frames = int(device_sr * BARGEIN_CHECK_INTERVAL)
        audio_q = queue.Queue()

        def _cb(indata, frames, time_info, status):
            audio_q.put(indata[:, 0].copy() if indata.ndim > 1 else indata.flatten().copy())

        stream = sd.InputStream(
            samplerate=device_sr, channels=1, dtype="float32",
            blocksize=chunk_frames, callback=_cb,
        )
        stream.start()

        loud_count = 0
        try:
            while self.is_speaking():
                try:
                    data = audio_q.get(timeout=0.2)
                except queue.Empty:
                    continue
                rms = float(np.sqrt(np.mean(data ** 2)))
                if rms > BARGEIN_ENERGY_THRESHOLD:
                    loud_count += 1
                    if loud_count >= BARGEIN_CHUNKS_NEEDED:
                        logger.info(f"Barge-in detected (RMS={rms:.3f}), stopping TTS")
                        self.stop()
                        self.barged_in = True
                        break
                else:
                    loud_count = 0
        finally:
            stream.stop()
            stream.close()

    @staticmethod
    def list_voices() -> list[str]:
        """List available edge-tts voices."""
        voices = asyncio.run(edge_tts.list_voices())
        return [v["ShortName"] for v in voices if "Neural" in v["ShortName"]]
