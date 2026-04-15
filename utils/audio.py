"""Audio capture utilities using sounddevice.

Handles microphone input, resampling from device native rate
to 16kHz mono required by speech models.

Uses callback-based audio capture to prevent buffer overflow.
"""

import queue
import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly
from math import gcd

from utils.logger import setup_logger

logger = setup_logger("baba.audio")

# Speech models require 16kHz mono
TARGET_SAMPLE_RATE = 16000


def get_input_device_info() -> dict:
    """Return info about the default input device."""
    return sd.query_devices(kind="input")


def get_device_sample_rate() -> int:
    """Return the native sample rate of the default input device."""
    info = get_input_device_info()
    return int(info["default_samplerate"])


def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Resample audio from orig_sr to target_sr using polyphase filtering.

    Args:
        audio: 1D float32 numpy array
        orig_sr: Original sample rate
        target_sr: Target sample rate (default 16000)

    Returns:
        Resampled 1D float32 numpy array
    """
    if orig_sr == target_sr:
        return audio
    divisor = gcd(orig_sr, target_sr)
    up = target_sr // divisor
    down = orig_sr // divisor
    return resample_poly(audio, up, down).astype(np.float32)


def record_audio_chunk(duration_seconds: float, sample_rate: int | None = None) -> tuple[np.ndarray, int]:
    """Record a chunk of audio from the microphone.

    Args:
        duration_seconds: How long to record
        sample_rate: Sample rate to use (None = device default)

    Returns:
        Tuple of (audio_data as float32, sample_rate)
    """
    sr = sample_rate or get_device_sample_rate()
    frames = int(duration_seconds * sr)
    logger.debug(f"Recording {duration_seconds}s at {sr}Hz")
    audio = sd.rec(frames, samplerate=sr, channels=1, dtype="float32")
    sd.wait()
    return audio.flatten(), sr


class AudioStream:
    """Continuous audio stream for real-time processing.

    Uses a callback-based sounddevice InputStream that pushes audio
    into a queue. read_chunk() pulls from the queue, so audio capture
    never stalls even if the consumer is slow.
    """

    def __init__(self, chunk_duration: float = 0.08):
        """
        Args:
            chunk_duration: Duration of each chunk in seconds.
                           0.08s = 1280 samples at 16kHz (required by OpenWakeWord)
        """
        self.device_sr = get_device_sample_rate()
        self.target_sr = TARGET_SAMPLE_RATE
        self.chunk_duration = chunk_duration
        self.device_chunk_size = int(self.device_sr * chunk_duration)
        self._stream = None
        self._queue = None

    def _audio_callback(self, indata, frames, time_info, status):
        """Sounddevice callback — runs in a separate thread."""
        if status:
            logger.warning(f"Audio stream status: {status}")
        self._queue.put(indata[:, 0].copy() if indata.ndim > 1 else indata.flatten().copy())

    def start(self):
        """Start the audio stream."""
        logger.info(f"Starting audio stream: device={self.device_sr}Hz, target={self.target_sr}Hz, chunk={self.chunk_duration}s")
        self._queue = queue.Queue()
        self._stream = sd.InputStream(
            samplerate=self.device_sr,
            channels=1,
            dtype="float32",
            blocksize=self.device_chunk_size,
            callback=self._audio_callback,
        )
        self._stream.start()

    def read_chunk(self) -> np.ndarray:
        """Read one chunk of audio, resampled to 16kHz mono.

        Blocks until a chunk is available from the callback queue.

        Returns:
            1D float32 numpy array at 16kHz
        """
        if self._stream is None:
            raise RuntimeError("Audio stream not started. Call start() first.")
        mono = self._queue.get(timeout=2.0)
        return resample_audio(mono, self.device_sr, self.target_sr)

    def stop(self):
        """Stop the audio stream."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            self._queue = None
            logger.info("Audio stream stopped")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()
